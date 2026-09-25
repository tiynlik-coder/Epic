"""Night: offering actions to players and resolving all of them at dawn.

resolve_night_effects runs fixed stages, so the result never depends on player order:
  1. blocks (Kezuvchi), Veyron swaps, Advokat marks, Manipulyator redirects
  2. Minior mines: whoever visits a mined house steps on the mine instead of acting
  3. actions: visits, checks, heals and shields, gifts, conversions (attacks are only collected)
  4. hero actions
  5. attacks in selection order, each through hit(): immunities, shields, items, HP
  6. after-effects: G‘azabkor, Kamikaze, La’natchi, bounties, Joker cards, reports
"""

import random
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from config import HARMFUL_ACTION_ROLES, LOOKS_TOWN_TO_KOMISSAR, MAFIA, NIGHT_IMMUNE, ORDINARY_KILLERS, TOWN
from keyboards.game_keyboard import name_buttons
from models.database import db
from models.heroes import hero_damage_range, hero_level, hero_max_shield, hero_row
from models.users import add_balance, add_item, consume_inventory, get_user, inv, transfer
from utils.players import ability_role, dead_targets, getp, kill_player, living, mention, role_label, visible_name
from utils.state import games, persist_games
from utils.telegram_utils import send_private

# Roles with nothing to do at night.
PASSIVE_ROLES = {"Tinch axoli","Serjant","Suidsid","Kamikaze","Sehrgar","Afsungar","Omadli","Janob","Admiral","Hamshira","Bo‘ri"}
# Roles that pick a mode before the target (callback amode:...).
ACTION_MODES = {
    "Kimyogar": [("heal","💉 Davolash"),("kill","☠️ O‘ldirish")],
    "Qaroqchi": [("pul","💵 Pulini olish"),("jon","👊 Do‘pposlash")],
    "Joker": [(str(n),f"🃏 {n}-karta") for n in range(1,5)],
}
KONCHI_KONS = ["dollar"]*5 + ["olmos"]*2 + ["o‘lim"]*3

NIGHT_PROMPTS = {
    "Shifokor":"🩺 Bugun kimni davolaymiz?",
    "Daydi":"🌙 Bugun kimning derazasidan kuzatamiz?",
    "Kezuvchi":"🚶 Bugun kimni bloklaymiz?",
    "Koldun":"⚡ Bugun kimni tanlaymiz?",
    "Don":"🎩 Bugun kimni nishonga olamiz?",
    "Mafia":"🔪 Bugun kimni nishonga olamiz?",
    "Advokat":"⚖️ Bugun kimni himoya qilamiz?",
    "Ayg‘oqchi":"🕵️ Bugun kimni kuzatamiz?",
    "Labarant":"🧪 Kimni tanlaymiz? Mafiyani davolaysiz, boshqani o‘ldirasiz.",
    "Manipulyator":"🪄 Bugun kimning harakatini o‘zgartiramiz?",
    "Undiruvchi":"💰 Bugun kimdan pul undiramiz?",
    "Sotqin":"🦎 Bugun kimni tanlaymiz?",
    "Folbin":"🧿 Bugun kimning tarafini aniqlaymiz?",
    "Zodagon":"👑 Bugun kimni tanlaymiz?",
    "La’natchi":"🕸️ Bugun kimni la’natlaymiz?",
    "Qotil":"🔪 Bugun kimni nishonga olamiz?",
    "Minior":"☠️ Kimning eshigiga mina qo‘yamiz?",
    "Snayper":"👨🏻‍🎤 Bugun kimni nishonga olamiz?",
    "Qorbobo":"🎅 Bugun kimga sovg‘a beramiz? 🎁",
    "Qorbola":"🌨️ Bugun kimni Qorbo‘ron qilamiz?",
    "Tabib":"🩺 Bugun kimga dori qutisini beramiz?",
    "Yollanma qotil":"🥷 Bugun kimni ovlaymiz?",
    "Jurnalist":"👩🏼‍💻 Bugun kimdan intervyu olamiz?",
    "Robin Gud":"🏹 Bugun kimni nishonga olamiz?",
    "Fotoparatchi":"📸 Bugun kimni kuzatib rasmga olamiz?",
    "Aferist":"🤹🏻 Bugun kimning ovozini o‘g‘irlaymiz?",
    "Rais":"🤑 Bugun kimga pul tarqatamiz?",
    "Tulki":"🦊 Kimning tarafiga o‘tamiz?",
    "G‘azabkor":"🧌 Bugun kimni tanlaymiz? O‘zingizni tanlasangiz, tanlaganlaringiz bilan birga ketasiz.",
    "Kimyogar":"👨‍🔬 Kimni tanlaymiz?",
    "Qaroqchi":"⚔️ Kimnikiga boramiz?",
    "Joker":"🤡 Kartalarni kimga yuboramiz?",
}


def expects_action(g, p):
    """Does this player have a night action to use tonight? (for the idle-player rule)"""
    r=ability_role(p)
    if r in PASSIVE_ROLES or (r=="Tulki" and p.get("tulki_used")): return False
    if r=="Ruhoniy": return bool(dead_targets(g))
    if r=="Zombi": return g.get("mode")=="zombie"
    return r in NIGHT_PROMPTS or r in ACTION_MODES or r in {"Komissar Katani","Professor","Veyron","Konchi"}


def konchi_kons(g, uid):
    """Remaining mines of a Konchi: {"1": "dollar", ...}. Created once per game and player."""
    kons=g.setdefault("konchi",{})
    if str(uid) not in kons:
        types=KONCHI_KONS[:]; random.shuffle(types)
        kons[str(uid)]={str(i+1):t for i,t in enumerate(types)}
    return kons[str(uid)]


async def offer_night_action(app,g,p):
    r=ability_role(p)
    if not p["alive"]: return
    if hero_row(p["id"]):
        await send_private(app.bot,p["id"],"🥷 Geroy harakati:",InlineKeyboardMarkup([[InlineKeyboardButton("👊 Hujum",callback_data=f"heroact:attack:{g['id']}:{p['id']}")],[InlineKeyboardButton("🛡 Himoyalanish",callback_data=f"heroact:shield:{g['id']}:{p['id']}")],[InlineKeyboardButton("⏭ O‘tkazib yuborish",callback_data=f"heroact:skip:{g['id']}:{p['id']}")]]))
    if r in PASSIVE_ROLES: return
    if r=="Tulki" and p.get("tulki_used"): return
    if g.get("mode")=="zombie" and r=="Zombi":
        await send_private(app.bot,p["id"],"🧟 Bugun kimni Zombi qilamiz?",name_buttons(g,"zombie",p["id"]))
        return
    if r=="Ruhoniy":
        dead=dead_targets(g)
        if not dead:
            await send_private(app.bot,p["id"],"✝️ Hozircha qaytariladigan o‘yinchi yo‘q.")
            return
        rows=[[InlineKeyboardButton(visible_name(g,x)[:32],callback_data=f"res:{g['id']}:{p['id']}:{x['id']}")] for x in dead]
        await send_private(app.bot,p["id"],"✝️ Bugun kimni qaytaramiz?",InlineKeyboardMarkup(rows)); return
    if r=="Professor":
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("☠️ O‘lim qutisi",callback_data=f"prof:{g['id']}:{p['id']}:death")],[InlineKeyboardButton("💼 Oddiy yo‘l",callback_data=f"prof:{g['id']}:{p['id']}:normal")]])
        await send_private(app.bot,p["id"],"🎩 Bugun qaysi yo‘lni tanlaysiz?",kb); return
    if r=="Komissar Katani":
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 Tekshirish",callback_data=f"katani_mode:{g['id']}:{p['id']}:check")],[InlineKeyboardButton("🔫 Nishonga olish",callback_data=f"katani_mode:{g['id']}:{p['id']}:kill")]])
        await send_private(app.bot,p["id"],"🕵🏻‍♂️ Bugun nima qilamiz?",kb); return
    if r=="Veyron":
        await send_private(app.bot,p["id"],"🧲 Magnitlash uchun kimni tanlaymiz?",name_buttons(g,"vey1",p["id"])) ; return
    if r in ACTION_MODES:
        rows=[[InlineKeyboardButton(label,callback_data=f"amode:{g['id']}:{p['id']}:{m}")] for m,label in ACTION_MODES[r]]
        text="🤡 O‘lim kartasini tanlang. Nishoningiz 4 ta kartadan birini tanlaydi." if r=="Joker" else "Bugun nima qilamiz?"
        await send_private(app.bot,p["id"],text,InlineKeyboardMarkup(rows)); return
    if r=="Konchi":
        kons=konchi_kons(g,p["id"])
        buttons=[InlineKeyboardButton(f"⛏ {n}",callback_data=f"kon:{g['id']}:{p['id']}:{n}") for n in sorted(kons,key=int)]
        rows=[buttons[i:i+5] for i in range(0,len(buttons),5)]
        await send_private(app.bot,p["id"],"👷🏻‍♂️ Qaysi konga tushamiz? Ba’zilarida 💵, ba’zilarida 💎, ba’zilarida o‘lim bor.",InlineKeyboardMarkup(rows)); return
    await send_private(app.bot,p["id"],NIGHT_PROMPTS.get(r,"🎭 Bugun kimni tanlaymiz?"),name_buttons(g,"act",p["id"],allow_self=(r=="G‘azabkor")))


def apply_protection(target, killer_role, actor=None):
    if target["supper"]:
        target["supper"]=False; consume_inventory(target,"supper_shield"); return "supper"
    if killer_role in {"Qotil","Snayper","Professor"}: return None
    if target["protection_used"]: return None
    if target["protected"] and actor and actor.get("rifle"):
        # Rifle pierces ordinary protection (not Supper qalqon); one rifle per shot.
        consume_inventory(actor,"rifle"); actor["rifle"]=inv(actor["id"]).get("rifle",0)>0
        return None
    if target["protected"]:
        target["protected"]=False; target["protection_used"]=True
        consume_inventory(target,"protection")
        return "protection"
    return None


def bounty_killer(attacks, victim_id):
    """Return the earliest-selected attacker whose attack is recorded as a real candidate for the victim."""
    candidates=[]
    for actor,target,killer_role in attacks:
        if not target or target.get("id")!=victim_id or not actor or not killer_role:
            continue
        action=actor.get("action") or {}
        selected=action.get("selected_at", float("inf"))
        candidates.append((selected, actor))
    if not candidates: return None
    candidates.sort(key=lambda x:x[0])
    return candidates[0][1]


async def send_zombie_rosters(bot,g):
    zombies=[p for p in g.get("players",{}).values() if p.get("alive") and p.get("role")=="Zombi"]
    if not zombies: return
    text="🧟 <b>Zombie tarafidagi o‘yinchilar:</b>\n"+"\n".join(f"• {p['name']}" for p in zombies)
    for z in zombies:
        await send_private(bot,z["id"],text)


async def veyron_notice_job(ctx):
    d=ctx.job.data; g=next((x for x in games.values() if x.get("id")==d.get("gid")),None)
    if not g or g.get("phase")!="night": return
    for pair in g.get("veyron_notice", []):
        x=getp(g,pair.get("x")); y=getp(g,pair.get("y"))
        if x and y:
            await send_private(ctx.bot,x["id"],f"🧲 Keyingi tunda siz {role_label(y['role'])} qobiliyatidan foydalanasiz.")
            await send_private(ctx.bot,y["id"],f"🧲 Keyingi tunda siz {role_label(x['role'])} qobiliyatidan foydalanasiz.")
    g["veyron_notice"]=[]


async def zombie_convert_job(ctx):
    d=ctx.job.data; g=next((x for x in games.values() if x.get("id")==d.get("gid")),None)
    if not g or g.get("phase")!="night" or g.get("mode")!="zombie": return
    pending=g.get("mode_state",{}).get("zombie_pending") or []
    if not pending: return
    pending=sorted(pending,key=lambda x:x.get("selected_at",0))
    item=pending[0]; target=getp(g,item["target"])
    if not target or not target.get("alive") or target.get("role")=="Zombi": return
    target["role"]="Zombi"
    g["mode_state"]["zombie_ids"]=list(set(g["mode_state"].get("zombie_ids",[])+[target["id"]]))
    g["mode_state"]["zombie_pending"]=[]
    await send_private(ctx.bot,target["id"],"🧟 Siz Zombi bo‘ldingiz!\nEndi siz Zombi tarafida o‘ynaysiz va keyingi tundan Zombi harakatini bajarasiz.")
    await send_zombie_rosters(ctx.bot,g)
    persist_games()


def _alive_with_roles(g, roles):
    return [p for p in living(g) if p.get("role") in roles]


async def resolve_night_effects(ctx,g):
    """Apply every night action at dawn. Returns True when a Sehrgar decision is pending."""
    bot=ctx.bot
    everyone=list(g["players"].values())

    # ---- 1. Blocks, swaps, marks, redirects ----
    for p in everyone:
        a=p.get("action") or {}
        if ability_role(p)!="Kezuvchi" or not a.get("target"): continue
        t=getp(g,a["target"])
        if not t or not t["alive"] or t["role"] in NIGHT_IMMUNE: continue
        if t.get("medicine") and consume_inventory(t,"medicine_protection"):
            t["medicine"]=False
            await send_private(bot,t["id"],"💊 Doridan himoya sizni Kezuvchining dorisidan saqlab qoldi!")
            continue
        t["blocked"]=True
        await send_private(bot,t["id"],"💃 “Ana dori ta’sir qila boshladi, bir tun uxlab qolding...” — dedi Kezuvchi.")
    # Veyron's swap applies on the NEXT night only. It never changes roles/factions.
    g["next_ability_swaps"]={}
    g["veyron_notice"]=[]
    for p in everyone:
        a=p.get("action") or {}
        if ability_role(p)=="Veyron" and a.get("type")=="veyron" and a.get("second") and not p.get("blocked"):
            x=getp(g,a["first"]); y=getp(g,a["second"])
            if not x or not y: continue
            # Veyron's already-selected swap resolves even if Veyron dies later.
            # If exactly one selected player survives, that survivor receives the dead player's ability.
            if x.get("alive") and y.get("alive"):
                g["next_ability_swaps"][str(x["id"])] = y["role"]
                g["next_ability_swaps"][str(y["id"])] = x["role"]
            elif x.get("alive") and not y.get("alive") and y.get("role") != "Don":
                g["next_ability_swaps"][str(x["id"])] = y.get("role")
            elif y.get("alive") and not x.get("alive") and x.get("role") != "Don":
                g["next_ability_swaps"][str(y["id"])] = x.get("role")
            else:
                continue
            g["veyron_notice"].append({"x":x["id"],"y":y["id"]})
    for actor in everyone:
        a=actor.get("action") or {}
        if actor.get("blocked") or not a.get("target"): continue
        target=getp(g,a.get("target"))
        if target and ability_role(actor)=="Advokat":
            target["advokat_result"]=True
    # Manipulyator redirects the selected player's already-selected action to a second target.
    # Kezuvchi and Snayper are immune to manipulation. The fifth control still executes, then Manipulyator dies.
    for manip in everyone:
        if ability_role(manip)!="Manipulyator" or manip.get("blocked"): continue
        ma=manip.get("action") or {}
        controlled=getp(g,ma.get("controlled")) if ma.get("controlled") else None
        redirected=getp(g,ma.get("redirect_target")) if ma.get("redirect_target") else None
        if not controlled or not redirected or controlled.get("role") in {"Kezuvchi","Snayper"}: continue
        ca=controlled.get("action") or {}
        if ca.get("target") is not None:
            ca["original_target"]=ca.get("target")
            ca["target"]=redirected["id"]
        elif ca.get("type")=="professor" and ca.get("choice")=="death":
            ca["target"]=redirected["id"]
        controlled["action"]=ca
        manip["manipulations"]=manip.get("manipulations",0)+1
        if manip["manipulations"]>=5:
            manip["alive"]=False; manip["hp"]=0
            await bot.send_message(g["chat_id"],"🧠 Manipulyator boshqaruv jarayonida halok bo‘ldi.")

    # ---- 2. Minior mines ----
    # Every visitor steps on the mine except the Minior, the owner, a plain Mafia and the Yollanma qotil (Baku rule).
    mine_attacks=[]
    for minior in everyone:
        a=minior.get("action") or {}
        if ability_role(minior)!="Minior" or not minior["alive"] or minior.get("blocked") or not a.get("target"): continue
        for v in everyone:
            va=v.get("action") or {}
            if v is minior or v["id"]==a["target"] or not v["alive"] or v.get("blocked"): continue
            if va.get("target")!=a["target"] or ability_role(v) in {"Mafia","Yollanma qotil"}: continue
            v["action_cancelled"]=True
            mine_attacks.append((minior,v,"Minior"))

    # ---- 3. Actions ----
    attacks=[]; deaths=[]; late=[]  # late: reports that need every visit registered first
    yollanma_caught=[]; gazab_triggered=[]; joker_cards=[]
    for actor in list(living(g)):
        a=actor.get("action") or {}; typ=a.get("type"); target=getp(g,a.get("target")) if a.get("target") else None
        if actor["blocked"] or actor.get("action_cancelled"): continue
        er=ability_role(actor)
        if er=="Konchi" and typ=="kon":
            late.append((actor,None)); continue
        if not target: continue
        if er=="Ruhoniy" and typ=="resurrect":
            if not target["alive"] and actor.get("resurrections",0)<3:
                target["alive"]=True; target["hp"]=target["max_hp"]; actor["resurrections"]=actor.get("resurrections",0)+1
                await send_private(bot,target["id"],"✝️ Siz Ruhoniy tomonidan qaytarildingiz!")
                await bot.send_message(g["chat_id"],f"✝️ {visible_name(g,target,True)} o‘yinga qaytdi.")
            continue

        if target["alive"]: target["visits"].append(actor["id"])
        if g.get("mode")=="zombie" and er=="Zombi":
            # Zombie conversion is resolved at dawn; protection/heal does not block it.
            if target["role"]!="Zombi":
                ms=g.setdefault("mode_state",{})
                ms["zombie_pending"]=(ms.get("zombie_pending") or [])+[{"target":target["id"],"selected_at":a.get("selected_at",time.time()),"zombie":actor["id"]}]
            continue
        if er in ORDINARY_KILLERS: attacks.append((actor,target,er))
        elif er=="Snayper": attacks.append((actor,target,"Snayper"))
        elif er=="Professor" and typ=="professor" and a.get("choice")=="death": attacks.append((actor,target,"Professor"))
        elif er=="Komissar Katani" and typ=="check":
            looks_town=target["role"] in TOWN or target["role"] in LOOKS_TOWN_TO_KOMISSAR or target.get("advokat_result") or target.get("fake_document")
            result="Tinch aholi" if looks_town else "Mafia/Yakka"
            text=f"🕵🏻‍♂️ Tekshiruv natijasi: {mention(target)} — {result}."
            await send_private(bot,actor["id"],text)
            for helper in _alive_with_roles(g,{"Serjant","Admiral"}):
                await send_private(bot,helper["id"],"🕵🏻‍♂️ Komissardan xabar: "+text)
        elif er=="Komissar Katani" and typ=="kill": attacks.append((actor,target,"Komissar Katani"))
        elif er=="Koldun":
            if target["role"] in TOWN:
                target["koldun_hanging"]=True
            else: attacks.append((actor,target,"Koldun"))
        elif er in {"Shifokor","Tabib"}:
            target["hp"] += 50
            target["temp_hp_bonus"] = target.get("temp_hp_bonus",0) + 50
        elif er=="Kimyogar":
            if a.get("mode")=="heal": target["kimyo_shield"]=actor["id"]
            else: attacks.append((actor,target,"Kimyogar"))
        elif er=="Labarant":
            if target["role"] in MAFIA: target["lab_shield"]=actor["id"]
            else: attacks.append((actor,target,"Labarant"))
        elif er=="Yollanma qotil":
            if target["role"]=="Komissar Katani": yollanma_caught.append((actor,target))
            else: attacks.append((actor,target,"Yollanma qotil"))
        elif er=="G‘azabkor":
            if target["id"]==actor["id"]: gazab_triggered.append(actor)
            elif target["id"] not in actor.setdefault("gazab_picks",[]): actor["gazab_picks"].append(target["id"])
        elif er=="Joker":
            joker_cards.append((actor,target,a.get("mode") or "1"))
        elif er=="Qaroqchi":
            price=random.choice([70,80,90,100])
            row=get_user(target["id"])
            if a.get("mode")=="pul" and row and int(row["money"] or 0)>=price and transfer(target["id"],actor["id"],"money",price):
                await send_private(bot,actor["id"],f"⚔️ Siz {visible_name(g,target)}dan {price}💷 oldingiz!")
                await send_private(bot,target["id"],f"⚔️ Qaroqchi sizdan {price}💷 olib ketdi.")
            else:
                attacks.append((actor,target,"Qaroqchi"))
        elif er=="Rais":
            amount=random.randint(1,100)
            field,sign=("diamonds","💎") if amount<=2 else ("money","💷")
            add_balance(target["id"],field,amount)
            await send_private(bot,target["id"],f"🤑 Rais sizga {amount}{sign} sovg‘a qildi!")
            await send_private(bot,actor["id"],f"🤑 Siz {visible_name(g,target)}ga {amount}{sign} sovg‘a qildingiz!")
        elif er=="Tulki" and not actor.get("tulki_used"):
            new_role="Serjant" if target["role"] in TOWN else "Mafia" if target["role"] in MAFIA else "Qotil"
            actor["role"]=new_role; actor["tulki_used"]=True
            await send_private(bot,actor["id"],f"🦊 Siz endi {role_label(new_role)}siz!")
        elif er=="Aferist":
            g.setdefault("aferist",{})[str(target["id"])]=actor["id"]
        elif er=="Undiruvchi":
            # Fictional in-game money action.
            row=get_user(target["id"])
            amount=min(random.randint(1,200),int(row["money"] or 0) if row else 0)
            if amount>0 and transfer(target["id"],actor["id"],"money",amount): await send_private(bot,actor["id"],f"💰 Siz {amount}💷 undirdingiz.")
        elif er=="Zodagon":
            if target["role"] in TOWN: await bot.send_message(g["chat_id"],"👑 Zodagon tanlovida adashdi.")
            else:
                add_balance(target["id"],"money",random.randint(1,200)); await bot.send_message(g["chat_id"],"👑 Zodagon kimnidir xursand qilmoqchi.")
        elif er=="Folbin":
            result="Tinch aholi" if target["role"] in TOWN else "Mafia" if target["role"] in MAFIA else "Yakka"
            if target.get("advokat_result") or target.get("fake_document"): result="Tinch aholi"
            await send_private(bot,actor["id"],f"🧿 Tonggi natija: {mention(target)} — {result} taraf.")
            for cp in living(g):
                if ability_role(cp)=="Komissar Katani":
                    await send_private(bot,cp["id"],"🧿 Sizga Folbindan yangi xabar bor.",InlineKeyboardMarkup([[InlineKeyboardButton("📖 Xabarni o‘qish",callback_data=f"read_f:{g['id']}:{target['id']}:{result}" )],[InlineKeyboardButton("❌ Bekor qilish",callback_data=f"cancel_f:{g['id']}")]]))
        elif er=="Ayg‘oqchi":
            # The role read goes to the Ayg‘oqchi and the mafia; a Fake Document masks it.
            result_role="Tinch axoli" if target.get("fake_document") else target["role"]
            text=f"🦇 Ayg‘oqchi: {mention(target)} — {role_label(result_role)}."
            for m in [actor]+[x for x in _alive_with_roles(g,{"Don","Mafia","Advokat"}) if x is not actor]:
                await send_private(bot,m["id"],text)
        elif er=="Qorbobo":
            gift=random.choice(["protection","hanging_protection","supper_shield","mask","rifle","active_role","killer_protection","medicine_protection"])
            if target.get("alive"):
                add_item(target["id"],gift)
                await send_private(bot,target["id"],f"🎅 Sizga tasodifiy sovg‘a keldi: {gift} 🎁")
        elif er=="Sotqin":
            if target["role"] in MAFIA or target["role"] in HARMFUL_ACTION_ROLES:
                if not target.get("fake_document"):
                    await bot.send_message(g["chat_id"],f"🦎 Sotqin [ {mention(target)} ]ning yovuz/harmli ekanini aniqladi. {role_label(target['role'])}",parse_mode=ParseMode.HTML)
            else: await bot.send_message(g["chat_id"],"🦎 Sotqinning izlanishlari bekor ketdi.")
        elif er in {"Daydi","Jurnalist","Fotoparatchi"}:
            late.append((actor,target))

    # ---- 4. Hero actions (independent of role/faction) ----
    for actor in everyone:
        ha=actor.get("hero_action") or {}
        if actor.get("blocked"):
            actor["hero_action"]=None
            continue
        if not ha: continue
        h=hero_row(actor["id"])
        if not h: continue
        if ha.get("type")=="attack" and ha.get("target") and h["patron"]>0:
            target=getp(g,ha["target"])
            if target and target.get("alive"):
                if target.get("hero_protection"):
                    target["hero_protection"]=False; consume_inventory(target,"hero_protection")
                    await send_private(bot,target["id"],"🔰 Geroydan himoya sizni Geroy hujumidan saqlab qoldi.")
                else:
                    dmg=random.randint(*hero_damage_range(h["level"]))
                    target_hero=hero_row(target["id"])
                    if target_hero and target_hero["shield"]>0:
                        absorbed=min(target_hero["shield"],dmg); dmg-=absorbed
                        con=db(); con.execute("UPDATE heroes SET shield=shield-? WHERE user_id=?",(absorbed,target["id"])); con.commit(); con.close()
                    con=db(); con.execute("UPDATE heroes SET patron=patron-1 WHERE user_id=?",(actor["id"],)); con.commit(); con.close()
                    target["hp"]-=dmg
                    actor_h=hero_row(actor["id"]); killed=target["hp"]<=0
                    newball=actor_h["ball"]+actor_h["level"]+(1 if killed else 0)
                    con=db(); con.execute("UPDATE heroes SET ball=?,level=? WHERE user_id=?",(newball,hero_level(newball),actor["id"])); con.commit(); con.close()
                    if killed:
                        kill_player(target,"hero")
                        await bot.send_message(g["chat_id"],f"🥷 {visible_name(g,actor,True)}ning Geroyi {visible_name(g,target,True)}ni mag‘lub etdi.")
                    else:
                        await bot.send_message(g["chat_id"],f"🥷 Geroy hujumi {visible_name(g,target,True)}ga {dmg}% zarar yetkazdi. Qolgan HP: {max(0,target['hp'])}%.")
        elif ha.get("type")=="shield":
            mx=hero_max_shield(h["level"])
            con=db(); con.execute("UPDATE heroes SET shield=? WHERE user_id=?",(mx,actor["id"])); con.commit(); con.close()
            await send_private(bot,actor["id"],f"🛡 Geroy himoyasi yangilandi: {mx}.")
        actor["hero_action"]=None

    # ---- 5. Attacks ----
    shield_saves=[]  # (shield owner id, target, attacker role)

    async def hit(actor,target,kr):
        """One attack through every defence. Returns True when the target died."""
        if not target["alive"] or target["role"] in NIGHT_IMMUNE: return False
        if target["role"]=="Sehrgar" and kr=="Snayper": return False  # the sniper's bullet cannot reach the Sehrgar
        target.setdefault("last_attackers",[]).append(kr)
        if target.get("kimyo_shield") and target["kimyo_shield"]!=actor["id"]:
            shield_saves.append((target["kimyo_shield"],target,kr))
            await send_private(bot,actor["id"],"👨‍🔬 Bu o‘yinchi Kimyogar himoyasida!")
            return False
        if target.get("lab_shield") and kr!="Labarant":
            shield_saves.append((target["lab_shield"],target,kr)); return False
        if target["role"]=="Sehrgar":
            # Sehrgar decides the attacker's fate in the short phase after the night.
            target["afsungar_decisions"].setdefault(actor["id"],None)
            await bot.send_message(g["chat_id"],f"⚠️ {role_label(kr)} Sehrgarni o‘ldirishga urindi! 🧙‍♀️ Sehrgar uni kechiradimi yoki o‘ldiradimi? Buni tongda bilamiz.")
            await send_private(bot,target["id"],f"⚠️ {mention(actor)} ({role_label(kr)}) sizni o‘ldirishga urindi!\nEndi uning taqdirini siz hal qilasiz.",InlineKeyboardMarkup([[InlineKeyboardButton("🕊️ Kechirish",callback_data=f"af:{g['id']}:{target['id']}:{actor['id']}:forgive")],[InlineKeyboardButton("☠️ O‘ldirish",callback_data=f"af:{g['id']}:{target['id']}:{actor['id']}:kill")]]))
            return False
        wolf_turns=kr in {"Komissar Katani","Don","Mafia"} or (kr=="Qotil" and g.get("roleset")=="real")
        if target["role"]=="Bo‘ri" and wolf_turns:
            target["role"]={"Komissar Katani":"Serjant","Qotil":"Qotil"}.get(kr,"Mafia")
            await bot.send_message(g["chat_id"],f"🐺 Bo‘ri {role_label(target['role'])}ga aylandi!")
            await send_private(bot,target["id"],f"🐺 Siz endi {role_label(target['role'])}siz!")
            return False
        if kr in {"Qotil","Yollanma qotil"} and target.get("killer_protection") and consume_inventory(target,"killer_protection"):
            target["killer_protection"]=inv(target["id"]).get("killer_protection",0)>0
            await send_private(bot,target["id"],"⛑️ Qotildan himoya sizni saqlab qoldi!")
            await bot.send_message(g["chat_id"],"💫 Kimningdir qotildan himoyasi ishladi!")
            return False
        if target["supper"] or target["protected"]:
            if apply_protection(target,kr,actor):
                await send_private(bot,target["id"],f"🛡 Sizning uyingizga {role_label(kr)} hujum qildi, ammo himoya sizni saqlab qoldi.")
                return False
        # Snayper, Yollanma qotil and the Professor's box against Kamikaze ignore heals.
        instant=kr in {"Snayper","Yollanma qotil"} or (kr=="Professor" and target["role"]=="Kamikaze")
        if not instant:
            target["hp"]-=50 if kr=="Qaroqchi" else 100
            if target["hp"]>0:
                if kr=="Qaroqchi": await send_private(bot,target["id"],f"⚔️ Qaroqchi sizni do‘pposladi. Qolgan HP: {target['hp']}%.")
                return False
        if target["role"]=="Omadli" and random.random()<0.85:
            target["hp"]=max(target["hp"],1)
            await bot.send_message(g["chat_id"],"💫 Kimningdir omadi keldi va omon qoldi!")
            return False
        kill_player(target); deaths.append((target,actor,kr))
        if target["role"]=="Afsungar" and actor["alive"] and actor["role"] not in NIGHT_IMMUNE:
            # Afsungar takes the killer down too; it is a win if the killer was evil.
            kill_player(actor); deaths.append((actor,target,"Afsungar"))
            if actor["role"] in MAFIA or actor["role"] in {"Qotil","Kimyogar"}: target["won_flag"]=True
        if kr=="Minior": actor["won_flag"]=True
        if kr=="Robin Gud" and target["role"] in TOWN:
            actor["robin_mistakes"]=actor.get("robin_mistakes",0)+1
            if actor["robin_mistakes"]>=2 and actor["alive"]:
                kill_player(actor); deaths.append((actor,None,None))
                await bot.send_message(g["chat_id"],f"🏹 Robin Gud {mention(actor)} ikkinchi marta tinch aholiga hujum qildi va xatosini kechira olmay o‘z joniga qasd qildi.",parse_mode=ParseMode.HTML)
        return True

    for minior,visitor,kr in mine_attacks:
        await hit(minior,visitor,kr)
    for komissar_victim in yollanma_caught:
        actor,komissar=komissar_victim
        if actor["alive"]:
            kill_player(actor); deaths.append((actor,komissar,"Komissar Katani"))
    # All night attacks resolve together, ordered only by immutable selection time.
    attacks.sort(key=lambda item: (item[0].get("action") or {}).get("selected_at", float("inf")))
    for actor,target,kr in attacks:
        if not actor["alive"]: continue
        await hit(actor,target,kr)
    pending_afsungar = [af for af in g["players"].values() if af.get("afsungar_decisions")]

    # ---- 6. After-effects ----
    for gz in gazab_triggered:
        if not gz["alive"]: continue
        killed=0
        for pid in gz.get("gazab_picks",[]):
            pick=getp(g,pid)
            if pick and await hit(gz,pick,"G‘azabkor"): killed+=1
        kill_player(gz); deaths.append((gz,None,None))
        if killed>=2: gz["won_flag"]=True
        await bot.send_message(g["chat_id"],f"🧌 G‘azabkor o‘zini tanladi va tanlaganlaridan {killed} tasini o‘zi bilan olib ketdi!")

    # Konchi goes down a mine he picked.
    for actor,_ in [x for x in late if x[1] is None]:
        n=str((actor.get("action") or {}).get("kon"))
        kind=konchi_kons(g,actor["id"]).pop(n,None)
        if kind=="o‘lim":
            if actor.get("slip_protection") and consume_inventory(actor,"slip_protection"):
                actor["slip_protection"]=inv(actor["id"]).get("slip_protection",0)>0
                await send_private(bot,actor["id"],"🪤 Konda sirpanib ketdingiz, ammo sirpanishdan himoya sizni saqlab qoldi!")
            elif actor["alive"]:
                kill_player(actor); deaths.append((actor,None,None))
                await send_private(bot,actor["id"],"👷🏻‍♂️ Siz konda sirpanib halok bo‘ldingiz!")
        elif kind=="olmos":
            add_balance(actor["id"],"diamonds",1); await send_private(bot,actor["id"],"👷🏻‍♂️ Kondan 1💎 topdingiz!")
        elif kind=="dollar":
            reward=random.randrange(10,500,10); add_balance(actor["id"],"money",reward)
            await send_private(bot,actor["id"],f"👷🏻‍♂️ Kondan {reward}💷 topdingiz!")

    # La’natchi: damage only the exact selected actor when that actor really caused a kill.
    for lp in living(g):
        if lp.get("role")!="La’natchi": continue
        marked=(lp.get("action") or {}).get("target")
        if not marked: continue
        caused=[(victim,killer,kr) for victim,killer,kr in deaths if killer and killer.get("id")==marked]
        if not caused: continue
        killer=getp(g,marked)
        if not killer or killer.get("role") in {"Minior","Sehrgar"}: continue
        damage=25 if any(kr in {"Snayper","Professor"} for _,_,kr in caused) else 50
        killer["hp"]-=damage
        if killer["hp"]<=0 and kill_player(killer,"la'natchi"): deaths.append((killer,lp,"La’natchi"))
    # Bounty payout: only the killer whose action actually caused the death qualifies.
    for victim,killer,kr in list(deaths):
        if not killer: continue
        for bounty in list(g.get("bounties", [])):
            if bounty["target"] != victim["id"]: continue
            add_balance(killer["id"],"money",bounty["amount"])
            await bot.send_message(g["chat_id"], f"🎯 {visible_name(g,victim,True)} uchun {bounty['amount']}💷 bounty {visible_name(g,killer,True)}ga berildi!")
            g["bounties"].remove(bounty)
    persist_games()

    # Kamikaze retaliation: every actual killer of Kamikaze is taken out, except Professor.
    for victim,killer,kr in list(deaths):
        if victim.get("role")!="Kamikaze" or victim.get("kamikaze_used"): continue
        killers=[]
        for a,t,krole in attacks:
            if t.get("id")==victim.get("id") and krole!="Professor" and a.get("alive"):
                if a not in killers: killers.append(a)
        if killers:
            victim["kamikaze_used"]=True
            for k in killers:
                if k.get("alive"):
                    kill_player(k,"kamikaze")
                    deaths.append((k,victim,"Kamikaze"))
            await bot.send_message(g["chat_id"],f"💥 Kamikaze {mention(victim)} halok bo‘ldi va hujumchilarni ham o‘zi bilan olib ketdi.")

    # Joker's cards: the target must pick one before the next night.
    for joker,target,card in joker_cards:
        if not target["alive"]: continue
        if target["role"]=="Yollanma qotil":
            await send_private(bot,joker["id"],"🤡 Nishoningiz kartalarga qaramadi ham..."); continue
        g.setdefault("joker_cards",{})[str(target["id"])]={"joker":joker["id"],"death":str(card)}
        rows=[[InlineKeyboardButton(f"🃏 {n}",callback_data=f"card:{g['id']}:{target['id']}:{n}") for n in range(1,5)]]
        await send_private(bot,target["id"],"🤡🎈 Joker seni tanladi! Kechgacha bitta kartani tanla — omading kulsa yashaysan, tanlamasang o‘lasan!",InlineKeyboardMarkup(rows))

    # Reports that need every visit: Daydi, Jurnalist, Fotoparatchi.
    for actor,target in [x for x in late if x[1] is not None]:
        er=ability_role(actor)
        if er=="Daydi":
            visitors=[getp(g,x) for x in target["visits"] if getp(g,x) and x not in {target["id"],actor["id"]}]
            shown=["🎭 Noma’lum" if v.get("mask") else role_label(v["role"]) for v in visitors if v.get("role")!="Snayper"]
            if not shown:
                text=f"🏠 Xavfsiz yotibdi. Bugun siz {mention(target)}ning derazasidan kuzatdingiz va hech qanday shubhali harakat sezmadingiz."
            else:
                text="🌙 Siz "+mention(target)+"ning derazasidan kuzatdingiz.\n\nKelganlar:\n"+"\n".join(shown)
            await send_private(bot,actor["id"],text)
        elif er=="Jurnalist":
            visitors=[getp(g,x) for x in target["visits"] if getp(g,x) and x not in {target["id"],actor["id"]}]
            shown=[] if target["role"]=="Komissar Katani" else ["maskali" if v.get("mask") else f"{visible_name(g,v)} — {role_label(v['role'])}" for v in visitors if v["role"] not in {"Don","Mafia"}]
            if shown:
                text=f"👩🏼‍💻 {visible_name(g,target)}dan intervyu oldim, unikiga kelganlar: "+", ".join(shown)
                await send_private(bot,actor["id"],text)
                for don in _alive_with_roles(g,{"Don"}):
                    await send_private(bot,don["id"],"📬 Jurnalistdan xat:\n\n"+text)
            else:
                await send_private(bot,actor["id"],f"👩🏼‍💻 {visible_name(g,target)}dan intervyu oldingiz, ammo hech kimni aniqlay olmadingiz.")
        elif er=="Fotoparatchi":
            ta=target.get("action") or {}
            went=getp(g,ta.get("target")) if ta.get("target") and not target.get("blocked") else None
            if went and went["id"]!=target["id"] and target["role"]!="Mafia":
                await send_private(bot,actor["id"],f"📸 {visible_name(g,target)} tunda {visible_name(g,went)}nikiga borganini rasmga oldingiz!")
            else:
                await send_private(bot,actor["id"],f"📸 Afsuski, {visible_name(g,target)} bugun hech kimnikiga bormadi.")

    # Every attacked player hears who came; healers hear whether their patient made it.
    for victim in g["players"].values():
        attackers=victim.get("last_attackers") or []
        if not attackers: continue
        await send_private(bot,victim["id"],"Sizning uyingizga tunda "+", ".join(role_label(k) for k in attackers)+" keldi.")
        for doc in [p for p in g["players"].values() if ability_role(p)=="Shifokor"]:
            da=doc.get("action") or {}
            if doc.get("blocked") or da.get("target")!=victim["id"]: continue
            text=f"🩺 Davolash natijasi: {visible_name(g,victim,True)} — {'saqlandi' if victim.get('alive') else 'saqlanmadi'}."
            await send_private(bot,doc["id"],text)
            for nurse in _alive_with_roles(g,{"Hamshira"}):
                await send_private(bot,nurse["id"],"👩🏻‍⚕️ Shifokordan: "+text)
    for owner_id,target,kr in shield_saves:
        owner=getp(g,owner_id)
        if owner: await send_private(bot,owner["id"],f"🛡 Siz {visible_name(g,target,True)}ni {role_label(kr)} hujumidan qutqardingiz!")
    # Daydi death witness at dawn: only if the visited owner died; owner is not a visitor.
    for p in list(g["players"].values()):
        if ability_role(p)=="Daydi" and p["action"] and p["action"].get("target") and not p.get("blocked"):
            target=getp(g,p["action"]["target"])
            if target and not target["alive"]:
                killers=[(a,k) for a,t,k in attacks if t["id"]==target["id"]]
                if killers:
                    await send_private(bot,p["id"],f"👁 Siz qotillik guvohi bo‘ldingiz. Murdaning ustida {role_label(killers[0][1])} {mention(killers[0][0])} turardi.")
    g["night_deaths"]=[{"victim":v["id"],"killer":k["id"] if k else None,"role":kr} for v,k,kr in deaths]
    return bool(pending_afsungar)

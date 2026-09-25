"""Night: offering actions to players and resolving all of them at dawn."""

import random
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from config import HARMFUL_ACTION_ROLES, MAFIA, ORDINARY_KILLERS, TOWN
from keyboards.game_keyboard import name_buttons
from models.database import db
from models.heroes import hero_damage_range, hero_level, hero_max_shield, hero_row
from models.users import add_item, consume_inventory, get_user, inv, transfer
from utils.players import ability_role, dead_targets, getp, kill_player, living, mention, role_label, visible_name
from utils.state import games, persist_games
from utils.telegram_utils import send_private


async def offer_night_action(app,g,p):
    r=ability_role(p)
    if not p["alive"]: return
    if hero_row(p["id"]):
        await send_private(app.bot,p["id"],"🥷 Geroy harakati:",InlineKeyboardMarkup([[InlineKeyboardButton("👊 Hujum",callback_data=f"heroact:attack:{g['id']}:{p['id']}")],[InlineKeyboardButton("🛡 Himoyalanish",callback_data=f"heroact:shield:{g['id']}:{p['id']}")],[InlineKeyboardButton("⏭ O‘tkazib yuborish",callback_data=f"heroact:skip:{g['id']}:{p['id']}")]]))
    if r in {"Tinch axoli","Serjant","Suidsid","Kamikaze"}: return
    if r=="Afsungar": return
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
    texts={
        "Shifokor":"🩺 Bugun kimni davolaymiz?",
        "Daydi":"🌙 Bugun kimning derazasidan kuzatamiz?",
        "Kezuvchi":"🚶 Bugun kimni bloklaymiz?",
        "Koldun":"⚡ Bugun kimni tanlaymiz?",
        "Don":"🎩 Bugun kimni nishonga olamiz?",
        "Mafia":"🔪 Bugun kimni nishonga olamiz?",
        "Advokat":"⚖️ Bugun kimni himoya qilamiz?",
        "Ayg‘oqchi":"🕵️ Bugun kimni kuzatamiz?",
        "Labarant":"🧪 Bugun kimni nishonga olamiz?",
        "Manipulyator":"🪄 Bugun kimning harakatini o‘zgartiramiz?",
        "Ruhoniy":"✝️ Bugun kimni qaytarishga urinib ko‘ramiz?",
        "Undiruvchi":"💰 Bugun kimdan pul undiramiz?",
        "Sotqin":"🦎 Bugun kimni tanlaymiz?",
        "Folbin":"🧿 Bugun kimning tarafini aniqlaymiz?",
        "Zodagon":"👑 Bugun kimni tanlaymiz?",
        "La’natchi":"🕸️ Bugun kimni la’natlaymiz?",
        "Qotil":"🔪 Bugun kimni nishonga olamiz?",
        "Minior":"💣 Bugun kimni tanlaymiz?",
        "Snayper":"👨🏻‍🎤 Bugun kimni nishonga olamiz?",
        
        "Afsungar":"🧙‍♀️ Siz hujum bo‘lsa tongda qaror qilasiz.",
        "Qorbobo":"🎅 Bugun kimga sovg‘a beramiz? 🎁",
        "Qorbola":"🌨️ Bugun kimni Qorbo‘ron qilamiz?",
        "Tabib":"🩺 Bugun kimga dori qutisini beramiz?",
    }
    if r=="Afsungar": return
    await send_private(app.bot,p["id"],texts.get(r,"🎭 Bugun kimni tanlaymiz?"),name_buttons(g,"act",p["id"]))


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


async def resolve_night_effects(ctx,g):
    """Apply every night action at dawn. Returns True when an Afsungar decision is pending."""
    # Kezuvchi blocks target's action; first resolve blocks before other actions.
    blocks={}
    for p in list(g["players"].values()):
        if ability_role(p)=="Kezuvchi" and p["action"] and p["action"].get("target"):
            t=getp(g,p["action"]["target"])
            if t: blocks[t["id"]]=True; t["blocked"]=True
    # Veyron's swap applies on the NEXT night only. It never changes roles/factions.
    g.setdefault("next_ability_swaps", {})
    g["next_ability_swaps"]={}
    g["veyron_notice"]=[]
    for p in list(g["players"].values()):
        a=p.get("action") or {}
        if ability_role(p)=="Veyron" and a.get("type")=="veyron" and a.get("second") and not p.get("blocked"):
            x=getp(g,a["first"]); y=getp(g,a["second"])
            if not x or not y: continue
            # Veyron's already-selected swap resolves even if Veyron dies later.
            # If exactly one selected player survives, that survivor receives the dead player's ability.
            if x.get("alive") and y.get("alive"):
                g["next_ability_swaps"][str(x["id"])] = y["role"]
                g["next_ability_swaps"][str(y["id"])] = x["role"]
            elif x.get("alive") and not y.get("alive"):
                if y.get("role") != "Don":
                    g["next_ability_swaps"][str(x["id"])] = y.get("role")
                else:
                    continue
            elif y.get("alive") and not x.get("alive"):
                if x.get("role") != "Don":
                    g["next_ability_swaps"][str(y["id"])] = x.get("role")
                else:
                    continue
            else:
                continue
            g["veyron_notice"].append({"x":x["id"],"y":y["id"]})
    deaths=[]; attacks=[]
    def effective_role(p): return ability_role(p)

    # Pre-compute night effects that must not depend on actor iteration order.
    for actor in list(g["players"].values()):
        a=actor.get("action") or {}
        if actor.get("blocked") or not a.get("target"): continue
        target=getp(g,a.get("target"))
        if not target: continue
        er=effective_role(actor)
        if er=="Advokat":
            target["advokat_result"]=True
        if er=="Manipulyator":
            actor["manipulations"]=actor.get("manipulations",0)+1
            if actor["manipulations"]>=5:
                actor["alive"]=False; actor["hp"]=0
    # Manipulyator redirects the selected player's already-selected action to a second target.
    # Kezuvchi and Snayper are immune to manipulation. The fifth control still executes, then Manipulyator dies.
    for manip in list(g["players"].values()):
        if ability_role(manip)!="Manipulyator" or manip.get("blocked"): continue
        ma=manip.get("action") or {}
        controlled=getp(g,ma.get("controlled")) if ma.get("controlled") else None
        redirected=getp(g,ma.get("redirect_target")) if ma.get("redirect_target") else None
        if not controlled or not redirected or controlled.get("role") in {"Kezuvchi","Snayper"}: continue
        ca=controlled.get("action") or {}
        if ca.get("target") is not None:
            ca["original_target"]=ca.get("target")
            ca["target"]=redirected["id"]
        elif ca.get("type")=="veyron":
            # Veyron's two-person selection is not redirectable.
            pass
        elif ca.get("type")=="professor" and ca.get("choice")=="death":
            ca["target"]=redirected["id"]
        controlled["action"]=ca
        manip["manipulations"]=manip.get("manipulations",0)+1
        if manip["manipulations"]>=5:
            manip["alive"]=False; manip["hp"]=0
            await ctx.bot.send_message(g["chat_id"],"🧠 Manipulyator boshqaruv jarayonida halok bo‘ldi.")

    # Register visits for Daydi: owner is not a visitor.
    for actor in list(living(g)):
        a=actor.get("action") or {}; typ=a.get("type"); target=getp(g,a.get("target")) if a.get("target") else None
        if not target or not actor["alive"]: continue
        if actor["blocked"]: continue
        er=effective_role(actor)
        if er=="Ruhoniy" and typ=="resurrect":
            if not target["alive"] and actor.get("resurrections",0)<3:
                target["alive"]=True; target["hp"]=target["max_hp"]; actor["resurrections"]=actor.get("resurrections",0)+1
                await send_private(ctx.bot,target["id"],"✝️ Siz Ruhoniy tomonidan qaytarildingiz!")
                await ctx.bot.send_message(g["chat_id"],f"✝️ {visible_name(g,target,True)} o‘yinga qaytdi.")
            continue

        if target["alive"]: target["visits"].append(actor["id"])
        if g.get("mode")=="zombie" and er=="Zombi":
            # Zombie conversion is resolved at dawn; protection/heal does not block it.
            if target["role"]!="Zombi":
                ms=g.setdefault("mode_state",{})
                ms["zombie_pending"]=(ms.get("zombie_pending") or [])+[{"target":target["id"],"selected_at":a.get("selected_at",time.time()),"zombie":actor["id"]}]
            continue
        # ordinary / special actions
        if er in ORDINARY_KILLERS: attacks.append((actor,target,er))
        elif er=="Snayper": attacks.append((actor,target,"Snayper"))
        elif er=="Minior": attacks.append((actor,target,"Minior"))
        elif er=="Professor" and a.get("type")=="professor" and a.get("choice")=="death": attacks.append((actor,target,"Professor"))
        elif er=="Komissar Katani" and typ=="check":
            # Advokat's protection and a Fake Document both make the target read as Town.
            looks_town=target["role"] in TOWN or target.get("advokat_result") or target.get("fake_document")
            result="Tinch aholi" if looks_town else "Mafia/Yakka"
            await send_private(ctx.bot,actor["id"],f"🕵🏻‍♂️ Tekshiruv natijasi: {mention(target)} — {result}.")
        elif er=="Komissar Katani" and typ=="kill": attacks.append((actor,target,"Komissar Katani"))
        elif er=="Koldun":
            if target["role"] in TOWN:
                target["koldun_hanging"]=True
            else: attacks.append((actor,target,"Koldun"))
        elif er in {"Shifokor","Tabib"}:
            target["hp"] += 50
            target["temp_hp_bonus"] = target.get("temp_hp_bonus",0) + 50
        elif er=="Undiruvchi":
            # Fictional in-game money action.
            row=get_user(target["id"])
            amount=min(random.randint(1,200),int(row["money"] or 0) if row else 0)
            if amount>0 and transfer(target["id"],actor["id"],"money",amount): await send_private(ctx.bot,actor["id"],f"💰 Siz {amount}💷 undirdingiz.")
        elif er=="Zodagon":
            if target["role"] in TOWN: await ctx.bot.send_message(g["chat_id"],"👑 Zodagon tanlovida adashdi.")
            else:
                amount=random.randint(1,200); con=db(); con.execute("UPDATE users SET money=money+? WHERE user_id=?",(amount,target["id"])); con.commit(); con.close(); await ctx.bot.send_message(g["chat_id"],"👑 Zodagon kimnidir xursand qilmoqchi.")
        elif er=="Folbin":
            result="Tinch aholi" if target["role"] in TOWN else "Mafia" if target["role"] in MAFIA else "Yakka"
            if target.get("advokat_result") or target.get("fake_document"): result="Tinch aholi"
            await send_private(ctx.bot,actor["id"],f"🧿 Tonggi natija: {mention(target)} — {result} taraf.")
            for cp in living(g):
                if ability_role(cp)=="Komissar Katani":
                    await send_private(ctx.bot,cp["id"],"🧿 Sizga Folbindan yangi xabar bor.",InlineKeyboardMarkup([[InlineKeyboardButton("📖 Xabarni o‘qish",callback_data=f"read_f:{g['id']}:{target['id']}:{result}" )],[InlineKeyboardButton("❌ Bekor qilish",callback_data=f"cancel_f:{g['id']}")]]))
        elif er=="Ayg‘oqchi":
            # Ayg‘oqchi receives a private role read; Fake Document masks it.
            result_role="Tinch axoli" if target.get("fake_document") else target["role"]
            await send_private(ctx.bot,actor["id"],f"🕵️ Siz {mention(target)}ning {role_label(result_role)} ekanini aniqladingiz.")
        elif er=="Advokat":
            pass
        elif er=="Qorbobo":
            gifts=["protection","hanging_protection","supper_shield","mask","rifle","active_role"]
            gift=random.choice(gifts)
            if target.get("alive"):
                add_item(target["id"],gift)
                await send_private(ctx.bot,target["id"],f"🎅 Sizga tasodifiy sovg‘a keldi: {gift} 🎁")
        elif er=="Sotqin":
            if target["role"] in MAFIA or target["role"] in HARMFUL_ACTION_ROLES:
                if not target.get("fake_document"):
                    await ctx.bot.send_message(g["chat_id"],f"🦎 Sotqin [ {mention(target)} ]ning yovuz/harmli ekanini aniqladi. {role_label(target['role'])}",parse_mode=ParseMode.HTML)
            else: await ctx.bot.send_message(g["chat_id"],"🦎 Sotqinning izlanishlari bekor ketdi.")
        elif er=="Daydi":
            visitors=[getp(g,x) for x in target["visits"] if getp(g,x)]
            if not visitors:
                text=f"🏠 Xavfsiz yotibdi. Bugun siz {mention(target)}ning derazasidan kuzatdingiz va hech qanday shubhali harakat sezmadingiz."
            else:
                visible_visitors=[]
                for v in visitors:
                    if v["id"]==target["id"]: continue
                    if v.get("role")=="Snayper": continue
                    rr="🎭 Noma’lum" if v.get("mask") else role_label(v["role"])
                    visible_visitors.append(rr)
                text="🌙 Siz "+mention(target)+"ning derazasidan kuzatdingiz.\n\nKelganlar:\n"+"\n".join(visible_visitors)
            await send_private(ctx.bot,actor["id"],text)
    # Hero actions resolve at dawn alongside the game actions. They are independent of role/faction.
    for actor in list(g["players"].values()):
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
                    await send_private(ctx.bot,target["id"],"🔰 Geroydan himoya sizni Geroy hujumidan saqlab qoldi.")
                else:
                    dmg=random.randint(*hero_damage_range(h["level"]))
                    target_hero=hero_row(target["id"])
                    if target_hero and target_hero["shield"]>0:
                        absorbed=min(target_hero["shield"],dmg); dmg-=absorbed
                        con=db(); con.execute("UPDATE heroes SET shield=shield-? WHERE user_id=?",(absorbed,target["id"])); con.commit(); con.close()
                    con=db(); con.execute("UPDATE heroes SET patron=patron-1 WHERE user_id=?",(actor["id"],)); con.commit(); con.close()
                    target["hp"]-=dmg
                    if target["hp"]<=0:
                        kill_player(target,"hero")
                        actor_h=hero_row(actor["id"]); newball=actor_h["ball"]+actor_h["level"]+1
                        con=db(); con.execute("UPDATE heroes SET ball=?,level=? WHERE user_id=?",(newball,hero_level(newball),actor["id"])); con.commit(); con.close()
                        await ctx.bot.send_message(g["chat_id"],f"🥷 {visible_name(g,actor,True)}ning Geroyi {visible_name(g,target,True)}ni mag‘lub etdi.")
                    else:
                        actor_h=hero_row(actor["id"]); newball=actor_h["ball"]+actor_h["level"]
                        con=db(); con.execute("UPDATE heroes SET ball=?,level=? WHERE user_id=?",(newball,hero_level(newball),actor["id"])); con.commit(); con.close()
                        await ctx.bot.send_message(g["chat_id"],f"🥷 Geroy hujumi {visible_name(g,target,True)}ga {dmg}% zarar yetkazdi. Qolgan HP: {max(0,target['hp'])}%.")
        elif ha.get("type")=="shield":
            mx=hero_max_shield(h["level"])
            con=db(); con.execute("UPDATE heroes SET shield=? WHERE user_id=?",(mx,actor["id"])); con.commit(); con.close()
            await send_private(ctx.bot,actor["id"],f"🛡 Geroy himoyasi yangilandi: {mx}.")
        actor["hero_action"]=None

    # All night actions resolve together, ordered only by immutable selection time.
    attacks.sort(key=lambda item: (item[0].get("action") or {}).get("selected_at", float("inf")))
    # Manipulator redirection is applied before attacks in a full implementation; for safety, action targets are redirected here.
    for actor,target,kr in attacks:
        if not actor["alive"] or not target["alive"]: continue
        if kr=="Snayper" and target["role"]=="Afsungar": continue
        if target["role"]=="Afsungar":
            # Afsungar gets a decision, attacker waits.
            target["afsungar_decisions"].setdefault(actor["id"],None)
            await ctx.bot.send_message(g["chat_id"],f"⚠️ {role_label(kr)} Afsungarni o‘ldirishga urindi! 🧙‍♀️ Afsungar uni kechiradimi yoki o‘ldiradimi? Buni tongda bilamiz.")
            await send_private(ctx.bot,target["id"],f"⚠️ {mention(actor)} ({role_label(kr)}) sizni o‘ldirishga urindi!\nEndi uning taqdirini siz hal qilasiz.",InlineKeyboardMarkup([[InlineKeyboardButton("🕊️ Kechirish",callback_data=f"af:{g['id']}:{target['id']}:{actor['id']}:forgive")],[InlineKeyboardButton("☠️ O‘ldirish",callback_data=f"af:{g['id']}:{target['id']}:{actor['id']}:kill")]]))
            continue
        if target["supper"] or target["protected"]:
            blocked=apply_protection(target,kr,actor)
            if blocked:
                await send_private(ctx.bot,target["id"],f"🛡 Sizning uyingizga {role_label(kr)} hujum qildi, ammo himoya sizni saqlab qoldi.")
                continue
        if kr=="Professor" and target["role"]=="Kamikaze":
            kill_player(target); deaths.append((target,actor,kr)); continue
        if kr=="Snayper":
            kill_player(target); deaths.append((target,actor,kr)); continue
        if kr=="Minior":
            kill_player(target); deaths.append((target,actor,kr)); continue
        # HP-based ordinary damage; Tabib +50 is already applied.
        target["hp"]-=100
        if target["hp"]<=0:
            kill_player(target); deaths.append((target,actor,kr))
    # Afsungar decisions are made after the attack is reported, then resolved by a short
    # decision phase before dawn. Do not resolve immediately: the player must be able to click.
    pending_afsungar = [af for af in g["players"].values() if af.get("afsungar_decisions")]

    # La’natchi: damage only the exact selected actor when that actor really caused a kill.
    for lp in living(g):
        if lp.get("role")!="La’natchi": continue
        action=lp.get("action") or {}
        marked=action.get("target")
        if not marked: continue
        caused=[(victim,killer,kr) for victim,killer,kr in deaths if killer and killer.get("id")==marked]
        if not caused: continue
        killer=getp(g,marked)
        if not killer or killer.get("role") in {"Minior","Afsungar"}: continue
        damage=25 if any(kr in {"Snayper","Professor"} for _,_,kr in caused) else 50
        killer["hp"]-=damage
        if killer["hp"]<=0: kill_player(killer,"la'natchi")
    # Bounty payout: only the killer whose action actually caused the death qualifies.
    # Bounty winner is the killer whose attack actually caused the death.
    # Attacks are resolved by the immutable night selection timestamp.
    for victim,killer,kr in list(deaths):
        if not killer: continue
        for bounty in list(g.get("bounties", [])):
            if bounty["target"] != victim["id"]: continue
            con=db(); con.execute("UPDATE users SET money=money+? WHERE user_id=?",(bounty["amount"],killer["id"])); con.commit(); con.close()
            amount=bounty["amount"]
            await ctx.bot.send_message(g["chat_id"], f"🎯 {visible_name(g,victim,True)} uchun {amount}💷 bounty {visible_name(g,killer,True)}ga berildi!")
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
            await ctx.bot.send_message(g["chat_id"],f"💥 Kamikaze {mention(victim)} halok bo‘ldi va hujumchilarni ham o‘zi bilan olib ketdi.")
    # Shifokor report: every attacked target gets a dawn report; the Doctor gets a result too.
    for victim in g["players"].values():
        attackers=[(a,k) for a,t,k in attacks if t["id"]==victim["id"]]
        if not attackers: continue
        victim["last_attackers"]=[k for _,k in attackers]
        roles_text=", ".join(role_label(k) for _,k in attackers)
        await send_private(ctx.bot,victim["id"],f"Sizning uyingizga tunda {roles_text} keldi.")
        for doc in [p for p in g["players"].values() if ability_role(p)=="Shifokor"]:
            da=doc.get("action") or {}
            if doc.get("blocked") or da.get("target")!=victim["id"]: continue
            await send_private(ctx.bot,doc["id"],f"🩺 Sizning davolashingiz natijasi: {visible_name(g,victim,True)} — {'saqlandi' if victim.get('alive') else 'saqlanmadi'}.")
    # Daydi death witness at dawn: only if the visited owner died; owner is not a visitor.
    for p in list(g["players"].values()):
        if ability_role(p)=="Daydi" and p["action"] and p["action"].get("target"):
            target=getp(g,p["action"]["target"])
            if target and not target["alive"]:
                killers=[(a,k) for a,t,k in attacks if t["id"]==target["id"]]
                if killers:
                    k=killers[0][1]
                    await send_private(ctx.bot,p["id"],f"👁 Siz qotillik guvohi bo‘ldingiz. Murdaning ustida {role_label(k)} {mention(killers[0][0])} turardi.")
    g["night_deaths"]=[{"victim":v["id"],"killer":k["id"] if k else None,"role":kr} for v,k,kr in deaths]
    return bool(pending_afsungar)

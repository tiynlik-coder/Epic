"""Game phase cycle: start -> night -> (sehrgar) -> day -> voting -> (confirm) -> (revenge) -> ... -> end.

Phase lengths and rules come from the chat's settings (models/chat_settings.py), snapshotted into
g["settings"] when the lobby opens and refreshed when the game starts.
"""

import html
import random
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config import EMOJI, MAFIA, UNIFORM_KILLERS, WIN_REWARD
from models.chat_settings import get_settings, item_enabled
from models.database import db
from models.users import add_stats, consume_inventory, inv
from utils.game_roles import apply_admin_roles, build_role_list
from utils.night_actions import expects_action, offer_night_action, resolve_night_effects, send_zombie_rosters, zombie_convert_job
from utils.players import NIGHT_FIELDS, getp, kill_player, living, mention, numbered_name, role_label, role_lists, side, team_icon, visible_mention, visible_name
from utils.state import cancel_jobs, find_game, games, persist_games, refund_bounties, schedule_phase, valid_job
from utils.telegram_utils import is_epic_channel_member, night_image_path, send_private, unpin_lobby
from utils.texts import ROLE_INTRO
from utils.victory import game_over, winners

# Private night chats: members of a team read each other's messages (Baku rule: hidden agents stay hidden).
TEAMS = [
    ("🤵🏻 Mafiya", {"Don","Mafia","Advokat","Ayg‘oqchi","Manipulyator","Ruhoniy","Undiruvchi"}),
    ("🕵🏻 Komissar", {"Komissar Katani","Serjant","Admiral"}),
    ("🧑🏻‍⚕️ Shifokor", {"Shifokor","Hamshira"}),
]
REVENGE_TIME = 20
SEHRGAR_TIME = 10


def settings_of(g):
    if not g.get("settings"): g["settings"]=get_settings(g["chat_id"])
    return g["settings"]


def team_of(p):
    return next(((name,roles) for name,roles in TEAMS if p.get("role") in roles),(None,None))


def apply_role_bans(role_list, settings):
    """Banned roles become Tinch axoli (the mega set's filler for Baku role sets). Core roles cannot be banned."""
    banned=set(settings.get("banned_roles") or []) - {"Don","Mafia","Komissar Katani","Tinch axoli"}
    filler=settings.get("wolf") if settings.get("roleset")=="mega" else "Tinch axoli"
    return [filler if r in banned else r for r in role_list]


async def start_game(app,g):
    if g["phase"]!="lobby": return
    cancel_jobs(g); g["phase"]="starting"; g["phase_id"]+=1; g["start_time"]=time.time()
    settings=g["settings"]=get_settings(g["chat_id"])
    g["roleset"]=settings["roleset"]; g["wolf"]=settings["wolf"]
    n=len(g["players"])
    if g.get("mode") == "uniform":
        chosen=random.choice(UNIFORM_KILLERS)
        role_list=[chosen]*n
        g["mode_state"]={"uniform_role":chosen}
    else:
        role_list=apply_role_bans(build_role_list(g,n),settings)
        if g.get("mode") == "vs":
            g["mode_state"]["teams_count"]=int(g.get("mode_state",{}).get("teams_count",2))
        elif g.get("mode") == "zombie":
            g["mode_state"]={"zombie_ids":[],"zombie_pending":None}
    role_list=apply_admin_roles(g, role_list, use_active=item_enabled(settings,"active_role"))
    order=list(g["players"].values()); random.shuffle(order)
    for num,p in enumerate(order,1): p["num"]=num
    items=settings.get("items",{})
    for p,r in zip(g["players"].values(),role_list):
        p["role"]=r; p["alive"]=True; p["base_hp"]=150 if r=="Tabib" else 100; p["max_hp"]=p["base_hp"]; p["hp"]=p["base_hp"]; p["temp_hp_bonus"]=0
        d=inv(p["id"])
        has=lambda key: items.get(key,True) and d.get(key,0)>0
        p["protected"]=has("protection")
        p["hanging_protected"]=has("hanging_protection")
        p["supper"]=has("supper_shield")
        p["mask"]=items.get("mask",True) and consume_inventory(p,"mask")
        p["fake_document"]=items.get("fake_document",True) and consume_inventory(p,"fake_document")
        p["rifle"]=has("rifle")
        p["hero_protection"]=d.get("hero_protection",0)>0
        p["killer_protection"]=has("killer_protection")
        p["slip_protection"]=has("slip_protection")
        p["medicine"]=has("medicine_protection")
        add_stats(p["id"],game=True)
        body=ROLE_INTRO.get(r,f"Siz {side(r)} tarafdasiz.")
        intro=f"{EMOJI.get(r,'🎭')} Siz — {r}siz!\n\n{body}"
        if g.get("mode") == "vs":
            intro += f"\n\n⚔️ Sizning jamoangiz: {team_icon(p)}"
        await send_private(app.bot,p["id"],intro)
    if g.get("mode") == "zombie":
        # Zombie role tables already contain the first Zombi; otherwise pick one at random.
        zombies=[p for p in living(g) if p["role"]=="Zombi"]
        if not zombies:
            first=random.choice(living(g)); first["role"]="Zombi"; zombies=[first]
            await send_private(app.bot,first["id"],"🧟 Siz — Zombisiz!\nSiz Zombie tarafidasiz. Har tun bir o‘yinchini Zombi qilishingiz mumkin.")
        g["mode_state"]["zombie_ids"]=[z["id"] for z in zombies]
        await send_zombie_rosters(app.bot,g)
    await app.bot.send_message(g["chat_id"],"⚔️ <b>VS O‘YIN BOSHLANDI!</b>" if g.get("mode")=="vs" else "🎭 <b>O‘YIN BOSHLANDI!</b>",parse_mode=ParseMode.HTML)
    await unpin_lobby(app.bot,g)
    g["phase"]="night"; g["phase_id"]+=1; g["night"]=1; await start_night(app,g)


async def send_team_rosters(bot,g):
    for name,roles in TEAMS:
        members=[p for p in living(g) if p.get("role") in roles]
        if len(members)<2: continue
        text=f"<b>{name} jamoasi — sheriklaringiz:</b>\n"+"\n".join(f"• {html.escape(visible_name(g,p))} — {role_label(p['role'])}" for p in members)
        text+="\n\n💬 Tunda botga yozgan xabaringiz sheriklaringizga yetib boradi."
        for p in members: await send_private(bot,p["id"],text)


async def start_night(app,g):
    if g["ended"]: return
    cancel_jobs(g); g["phase"]="night"; g["phase_id"]+=1
    pending=g.get("next_ability_swaps", {})
    for p in g["players"].values():
        for k,v in NIGHT_FIELDS.items(): p[k]=v.copy() if isinstance(v,(list,dict)) else v
        p["temp_ability"]=pending.get(str(p["id"]))
        if p.get("alive"):
            p["max_hp"]=p.get("base_hp", 150 if p.get("role")=="Tabib" else 100)
            p["hp"]=min(p.get("hp",p["max_hp"]),p["max_hp"])
    g["next_ability_swaps"]={}
    g["aferist"]={}
    night_time=settings_of(g)["night_time"]
    try: bot_username=(await app.bot.get_me()).username or ""
    except TelegramError: bot_username=""
    night_kb=InlineKeyboardMarkup([[InlineKeyboardButton("🤖 Botga o‘tish",url=f"https://t.me/{bot_username}")]]) if bot_username else None
    caption=f"🌙 <b>Tun {g['night']}</b> boshlandi.\nBarcha tungi harakatlar tongda birgalikda hal qilinadi. Tonggacha ⏳ {night_time} soniya."
    path=await night_image_path()
    try:
        if path:
            with open(path,'rb') as f: await app.bot.send_photo(g["chat_id"],InputFile(f),caption=caption,parse_mode=ParseMode.HTML,reply_markup=night_kb)
        else: await app.bot.send_message(g["chat_id"],caption,parse_mode=ParseMode.HTML,reply_markup=night_kb)
    except TelegramError: await app.bot.send_message(g["chat_id"],caption,parse_mode=ParseMode.HTML,reply_markup=night_kb)
    names="\n".join(html.escape(numbered_name(g,p)) for p in sorted(living(g),key=lambda x:x.get("num",0)))
    await app.bot.send_message(g["chat_id"],f"👥 <b>Tirik o‘yinchilar:</b>\n{names}",parse_mode=ParseMode.HTML)
    await send_team_rosters(app.bot,g)
    for p in living(g): await offer_night_action(app,g,p)
    if g.get("mode")=="zombie":
        app.job_queue.run_once(zombie_convert_job,max(0,night_time-5),data={"gid":g["id"]},name=f"zombie-convert-{g['id']}")
    schedule_phase(app,g,night_time,resolve_night,"night")
    persist_games()


async def kick_idle_players(bot,g):
    """Two nights in a row without using an active role: the player is out (Baku rule)."""
    if not settings_of(g).get("afk_kick",True): return
    for p in living(g):
        if not expects_action(g,p) or p.get("blocked"): continue
        if p.get("action") is not None:
            p["missed_nights"]=0; continue
        p["missed_nights"]=p.get("missed_nights",0)+1
        if p["missed_nights"]>=2:
            kill_player(p,"afk")
            g.setdefault("night_deaths",[]).append({"victim":p["id"],"killer":None,"role":None})
            await bot.send_message(g["chat_id"],f"😴 Aholidan kimdir {role_label(p['role'])} {visible_mention(g,p,True)} o‘limidan oldin: “Men o‘yin paytida boshqa uxlamayma-a-a-an!” deb qichqirganini eshitgan.",parse_mode=ParseMode.HTML)


async def resolve_night(ctx):
    d=ctx.job.data; chat_id=next((cid for cid,g in games.items() if g["id"]==d["gid"]),None)
    if chat_id is None:return
    g=games[chat_id]
    if not valid_job(g,d) or g["phase"]!="night":return
    sehrgar_pending=await resolve_night_effects(ctx,g)
    await kick_idle_players(ctx.bot,g)
    if sehrgar_pending:
        g["phase"]="afsungar"; g["phase_id"]+=1
        persist_games()
        await schedule_afsungar_decision(ctx.application,g)
        return
    g["phase"]="day"; g["phase_id"]+=1
    await start_day(ctx.application,g)


async def offer_last_words(bot,g,players):
    """Freshly killed players may send one private message to the group within word_time."""
    settings=settings_of(g)
    if not settings.get("last_words",True): return
    words=g.setdefault("last_words",{})
    for p in players:
        words[str(p["id"])]=time.time()+settings["word_time"]
        await send_private(bot,p["id"],f"☠️ Sizni o‘ldirishdi! So‘nggi so‘zingizni shu yerga yozing — {settings['word_time']} soniya ichida guruhga yetkaziladi.")


async def start_day(app,g):
    if g["ended"]: return
    cancel_jobs(g)
    # Promotions happen before terminal-win evaluation.
    await promote_successors(app.bot,g)
    if game_over(g): return await end_game(app,g)
    nd=g.get("night_deaths",[])
    if nd:
        lines=["☠️ <b>Tunda o‘ldirilganlar:</b>"]
        for item in nd:
            vp=getp(g,item["victim"])
            if not vp: continue
            kr=item.get("role")
            if kr:
                lines.append(f"• {visible_mention(g,vp,True)} — {role_label(vp['role'])} — {role_label(kr)} o‘ldirdi")
            else:
                lines.append(f"• {visible_mention(g,vp,True)} — {role_label(vp['role'])}")
        await app.bot.send_message(g["chat_id"],"\n".join(lines),parse_mode=ParseMode.HTML)
        await offer_last_words(app.bot,g,[vp for vp in (getp(g,i["victim"]) for i in nd) if vp and not vp["alive"]])
    else:
        await app.bot.send_message(g["chat_id"],"<i>Ishonish qiyin! Lekin bu tunda hech kim o‘lmadi...</i>",parse_mode=ParseMode.HTML)
    g["night_deaths"]=[]
    # Keep the active game in memory through discussion/voting/night.
    # It is removed only by end_game(), so callbacks and timers remain valid.
    persist_games()
    a,b,c=role_lists(g)
    day_time=settings_of(g)["day_time"]
    await app.bot.send_message(g["chat_id"],f"☀️ <b>TONG O‘TDI</b>\n\n{a}\n\n{b}\n\n{c}\n\nJami tirik o'yinchilar: {len(living(g))}\n\nEndi kecha tunda bo'lgan voqealarni muhokama qilamiz. Ovoz berishgacha ⏳ {day_time} soniya.",parse_mode=ParseMode.HTML)
    # Temporary +50 HP from Shifokor/Tabib expires at dawn.
    for p in g["players"].values():
        # The bonus is temporary capacity, not damage: any remaining HP stays,
        # but the temporary ceiling disappears at dawn.
        p["temp_hp_bonus"]=0
        p["max_hp"]=p.get("base_hp",150 if p.get("role")=="Tabib" else 100)
        if p["alive"]: p["hp"]=min(p["hp"],p["max_hp"])
    g["phase"]="discussion"; g["phase_id"]+=1
    persist_games()
    schedule_phase(app,g,day_time,start_voting,"discussion")


# When a key role has no living holder, the first living successor takes it over.
SUCCESSION = [("Komissar Katani",("Serjant","Admiral")),("Shifokor",("Hamshira",)),("Don",("Mafia",))]


async def promote_successors(bot,g):
    for role,heirs in SUCCESSION:
        if any(p.get("alive") and p.get("role")==role for p in g["players"].values()): continue
        heir=next((p for h in heirs for p in g["players"].values() if p.get("alive") and p.get("role")==h),None)
        if not heir: continue
        old=heir["role"]; heir["role"]=role
        await send_private(bot,heir["id"],f"{role_label(role)} o‘ldi. Siz endi {role_label(role)}siz!")
        await bot.send_message(g["chat_id"],f"{role_label(old)} {role_label(role)}ga aylandi.")


async def schedule_afsungar_decision(app,g):
    # Give the Sehrgar a short real callback window at the end of night.
    schedule_phase(app,g,SEHRGAR_TIME,resolve_afsungar,"afsungar")


async def resolve_afsungar(ctx):
    d=ctx.job.data; g=find_game(d.get("gid"))
    if not g or not valid_job(g,d) or g.get("phase")!="afsungar": return
    for af in g["players"].values():
        if af.get("role")!="Sehrgar": continue
        for attacker_id, decision in list(af.get("afsungar_decisions",{}).items()):
            attacker=getp(g,int(attacker_id))
            if not attacker: continue
            if decision=="kill" and attacker.get("alive"):
                kill_player(attacker,"afsungar")
                g.setdefault("night_deaths",[]).append({"victim":attacker["id"],"killer":af["id"],"role":"Sehrgar"})
                await ctx.bot.send_message(g["chat_id"],f"🧙‍♀️ Sehrgar {mention(af)} {role_label(attacker['role'])}ni kechira olmadi va o‘ldirishga qaror qildi.",parse_mode=ParseMode.HTML)
                await send_private(ctx.bot,attacker["id"],"🧙‍♀️ Sehrgar sizni o‘ldirishga qaror qildi.")
            elif decision=="forgive":
                await ctx.bot.send_message(g["chat_id"],f"🕊️ Sehrgar {mention(af)} {role_label(attacker['role'])}ni kechirishga qaror qildi.",parse_mode=ParseMode.HTML)
                await send_private(ctx.bot,attacker["id"],"🕊️ 🧙‍♀️ Sehrgar sizni kechirishga qaror qildi.")
    for p in g["players"].values(): p["afsungar_decisions"]={}
    g["phase"]="day"; g["phase_id"]+=1
    persist_games()
    await start_day(ctx.application,g)


# ---------------- DAY VOTE ----------------

def vote_weight(p):
    return 2 if p.get("role")=="Janob" else 1


def can_vote(g,p):
    """Alive, awake (not put to sleep by Kezuvchi) and not fooled by the Aferist."""
    return bool(p and p.get("alive") and not p.get("blocked") and str(p["id"]) not in (g.get("aferist") or {}))


async def start_voting(ctx):
    d=ctx.job.data
    g=find_game(d.get("gid"))
    if not g or not valid_job(g,d) or g.get("phase")!="discussion": return
    g["phase"]="voting"; g["phase_id"]+=1; g["votes"]={}; cancel_jobs(g); persist_games()
    vote_time=settings_of(g)["vote_time"]
    await ctx.bot.send_message(g["chat_id"],f"🗳 <b>Aybdorlarni aniqlash vaqti keldi.</b>\nHar bir tirik o‘yinchi shaxsiy chatda ovoz beradi. ⏳ {vote_time} soniya.",parse_mode=ParseMode.HTML)
    for p in living(g):
        if p.get("blocked"):
            await send_private(ctx.bot,p["id"],"💤 Kezuvchining dorisidan uxlab qoldingiz — bugun ovoz bera olmaysiz."); continue
        if str(p["id"]) in (g.get("aferist") or {}):
            await send_private(ctx.bot,p["id"],"🤹🏻 Aferist sizni aldadi: bugun u sizning nomingizdan ovoz beradi."); continue
        rows=[[InlineKeyboardButton(numbered_name(g,t)[:40],callback_data=f"vote:{g['id']}:{t['id']}")] for t in sorted(living(g),key=lambda x:x.get("num",0)) if t["id"]!=p["id"]]
        rows.append([InlineKeyboardButton("⏭ Ovoz bermaslik",callback_data=f"skip:{g['id']}")])
        await send_private(ctx.bot,p["id"],"🗳 <b>Kimni osamiz?</b>\nTanlang:",InlineKeyboardMarkup(rows))
    schedule_phase(ctx.application,g,vote_time,resolve_vote,"vote")


async def resolve_vote(ctx):
    d=ctx.job.data; g=find_game(d.get("gid"))
    if not g or not valid_job(g,d) or g["phase"]!="voting":return
    counts={}
    for voter_id,target in g["votes"].items():
        voter=getp(g,int(voter_id))
        if target is not None and voter: counts[target]=counts.get(target,0)+vote_weight(voter)
    if not counts:
        await ctx.bot.send_message(g["chat_id"],"🗳 Ovoz berish yakunlandi: aholi kelisha olmadi, hech kim osilmadi."); return await after_vote(ctx.application,g)
    mx=max(counts.values()); top=[uid for uid,c in counts.items() if c==mx]
    if len(top)>1:
        await ctx.bot.send_message(g["chat_id"],"🤝 Ovozlar teng bo‘ldi. Hech kim osilmadi."); return await after_vote(ctx.application,g)
    victim=getp(g,top[0])
    if not victim or not victim["alive"]: return await after_vote(ctx.application,g)
    if settings_of(g).get("confirm_hanging",True):
        return await start_confirm(ctx.application,g,victim)
    await hang(ctx.application,g,victim)


def confirm_markup(g):
    yes,no=confirm_counts(g)
    return InlineKeyboardMarkup([[InlineKeyboardButton(f"👍 {yes}",callback_data=f"hang:{g['id']}:yes"),InlineKeyboardButton(f"👎 {no}",callback_data=f"hang:{g['id']}:no")]])


def confirm_counts(g):
    """Janob's 👍/👎 weighs 4 (Baku rule)."""
    yes=no=0
    for uid,v in (g.get("hang_votes") or {}).items():
        p=getp(g,int(uid)); w=4 if p and p.get("role")=="Janob" else 1
        if v: yes+=w
        else: no+=w
    return yes,no


async def start_confirm(app,g,victim):
    g["phase"]="confirm"; g["phase_id"]+=1; g["hang_votes"]={}; g["hang_target"]=victim["id"]
    like_time=settings_of(g)["like_time"]
    msg=await app.bot.send_message(g["chat_id"],f"⚖️ Rostdan ham {visible_mention(g,victim)}ni osmoqchimisiz? ⏳ {like_time} soniya.",parse_mode=ParseMode.HTML,reply_markup=confirm_markup(g))
    g["hang_message_id"]=msg.message_id
    persist_games()
    schedule_phase(app,g,like_time,resolve_confirm,"confirm")


async def resolve_confirm(ctx):
    d=ctx.job.data; g=find_game(d.get("gid"))
    if not g or not valid_job(g,d) or g.get("phase")!="confirm": return
    try: await ctx.bot.delete_message(g["chat_id"],g.get("hang_message_id"))
    except TelegramError: pass
    yes,no=confirm_counts(g)
    victim=getp(g,g.get("hang_target"))
    if yes<=no or not victim or not victim["alive"]:
        await ctx.bot.send_message(g["chat_id"],f"Aholi kelisha olmadi ({yes} 👍 | {no} 👎)... Hech kim osilmadi.")
        return await after_vote(ctx.application,g)
    await ctx.bot.send_message(g["chat_id"],f"Ovoz berish natijalari: {yes} 👍 | {no} 👎")
    await hang(ctx.application,g,victim)


async def hang(app,g,victim):
    bot=app.bot
    if victim.get("advokat_result"):
        await bot.send_message(g["chat_id"],f"⚖️ Advokat osish payti {visible_mention(g,victim)}ni himoyasiga oldi.",parse_mode=ParseMode.HTML); return await after_vote(app,g)
    if victim.get("koldun_hanging"):
        victim["koldun_hanging"]=False
        await bot.send_message(g["chat_id"],f"⚡ {visible_mention(g,victim)}ni Koldun osilishdan himoya qildi.",parse_mode=ParseMode.HTML); return await after_vote(app,g)
    if victim["hanging_protected"] and victim["role"] not in {"Suidsid","Afsungar"}:
        victim["hanging_protected"]=False; consume_inventory(victim,"hanging_protection")
        await bot.send_message(g["chat_id"],f"🛡 {visible_mention(g,victim)} osilishdan himoya yordamida qutulib qoldi!",parse_mode=ParseMode.HTML); return await after_vote(app,g)
    kill_player(victim,"vote")
    await bot.send_message(g["chat_id"],f"⚖️ {visible_mention(g,victim,True)} kunduzgi yig‘ilishda osildi!\nU {role_label(victim['role'])} edi.",parse_mode=ParseMode.HTML)
    await offer_last_words(bot,g,[victim])
    if victim["role"]=="Suidsid":
        await bot.send_message(g["chat_id"],"🪢 Suidsid o‘zining g‘alaba shartini bajardi."); g["forced_winners"]=[victim]
    if victim["role"]=="Afsungar" and len(living(g))>0:
        return await start_revenge(app,g,victim)
    await after_vote(app,g)


async def start_revenge(app,g,afsungar):
    """A hanged Afsungar takes one player along."""
    g["phase"]="revenge"; g["phase_id"]+=1; g["revenge_by"]=afsungar["id"]
    rows=[[InlineKeyboardButton(numbered_name(g,t)[:40],callback_data=f"afs:{g['id']}:{t['id']}")] for t in sorted(living(g),key=lambda x:x.get("num",0))]
    await send_private(app.bot,afsungar["id"],f"💣 Kimni o‘zingiz bilan olib ketasiz? ⏳ {REVENGE_TIME} soniya.",InlineKeyboardMarkup(rows))
    await app.bot.send_message(g["chat_id"],"💣 Afsungar osildi... U kimni o‘zi bilan olib ketarkin?")
    persist_games()
    schedule_phase(app,g,REVENGE_TIME,resolve_revenge,"revenge")


async def take_along(app,g,target):
    afs=getp(g,g.get("revenge_by"))
    if not afs or not target or not target["alive"]: return
    kill_player(target,"afsungar")
    if target["role"] in MAFIA or target["role"] in {"Qotil","Aferist"}: afs["won_flag"]=True
    await app.bot.send_message(g["chat_id"],f"💣 Afsungar {visible_mention(g,target,True)}ni o‘zi bilan jahannamga olib ketdi! U {role_label(target['role'])} edi.",parse_mode=ParseMode.HTML)
    await offer_last_words(app.bot,g,[target])


async def resolve_revenge(ctx):
    d=ctx.job.data; g=find_game(d.get("gid"))
    if not g or not valid_job(g,d) or g.get("phase")!="revenge": return
    await after_vote(ctx.application,g)


async def expire_joker_cards(bot,g):
    """A Joker target who did not pick a card by nightfall dies."""
    for tid in list((g.get("joker_cards") or {})):
        g["joker_cards"].pop(tid,None)
        t=getp(g,int(tid))
        if t and t["alive"]:
            kill_player(t,"joker")
            await bot.send_message(g["chat_id"],f"🤡 {visible_mention(g,t,True)} Joker kartasini tanlamadi va o‘ldirildi! U {role_label(t['role'])} edi.",parse_mode=ParseMode.HTML)


async def after_vote(app,g):
    if g.get("ended"): return
    cancel_jobs(g)
    await expire_joker_cards(app.bot,g)
    await promote_successors(app.bot,g)
    if g.get("forced_winners"):
        return await end_game(app,g,g["forced_winners"])
    if game_over(g): return await end_game(app,g)
    g["night"]+=1; await start_night(app,g)


async def end_game(app,g,forced=None):
    if g.get("ended"): return
    cancel_jobs(g); g["ended"]=True; g["phase"]="ended"; g["phase_id"]+=1
    await unpin_lobby(app.bot,g)
    win=forced if forced is not None else winners(g)
    win_ids={p["id"] for p in win}
    refund_bounties(g)
    rewards={}
    for p in win:
        add_stats(p["id"],win=True)
        rewards[p["id"]]=WIN_REWARD*(2 if await is_epic_channel_member(app.bot,p["id"]) else 1)
    if rewards:
        con=db(); con.executemany("UPDATE users SET money=money+? WHERE user_id=?",[(v,k) for k,v in rewards.items()]); con.commit(); con.close()
    elapsed=max(0,int(time.time()-(g.get("start_time") or time.time())))
    mm,ss=divmod(elapsed,60)
    lines=["<b>O’yin tugadi!</b>","","<b>G’oliblar:</b>"]
    if win:
        for i,p in enumerate(win,1): lines.append(f"{i}. {mention(p)} — {role_label(p['role'])}")
    else: lines.append("—")
    lines += ["","<b>Qolgan o’yinchilar:</b>"]
    remaining=[p for p in g["players"].values() if p["id"] not in win_ids]
    if remaining:
        for i,p in enumerate(remaining,1): lines.append(f"{i}. {mention(p)} — {role_label(p['role'])}")
    else: lines.append("—")
    lines += ["",f"O’yin davomiyligi: {mm:02d} daqiqa {ss:02d} soniya"]
    await app.bot.send_message(g["chat_id"],"\n".join(lines),parse_mode=ParseMode.HTML)
    games.pop(g.get("chat_id"), None)
    persist_games()

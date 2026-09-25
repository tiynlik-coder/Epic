"""Game phase cycle: start -> night -> day -> voting -> ... -> end."""

import html
import random
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config import DISCUSSION_TIME, EMOJI, NIGHT_TIME, ORDINARY_KILLERS, ROLES, VOTING_TIME, WIN_REWARD
from models.database import db
from models.users import add_stats, consume_inventory, inv
from utils.game_roles import apply_admin_roles, role_balance
from utils.night_actions import offer_night_action, resolve_night_effects, send_zombie_rosters, zombie_convert_job
from utils.players import getp, kill_player, living, mention, role_label, role_lists, side, team_icon, visible_mention, visible_name
from utils.state import cancel_jobs, find_game, games, persist_games, refund_bounties, schedule_phase, valid_job
from utils.telegram_utils import is_epic_channel_member, night_image_path, send_private, unpin_lobby
from utils.texts import ROLE_INTRO
from utils.victory import game_over, winners


async def start_game(app,g):
    if g["phase"]!="lobby": return
    cancel_jobs(g); g["phase"]="starting"; g["phase_id"]+=1; g["start_time"]=time.time()
    if g.get("mode") == "uniform":
        killer_pool=sorted(ORDINARY_KILLERS | {"Snayper","Professor","Minior"})
        chosen=random.choice(killer_pool)
        role_list=[chosen]*len(g["players"])
        g["mode_state"]={"uniform_role":chosen}
    elif g.get("mode") == "vs":
        role_list=role_balance(len(g["players"]))
        g["mode_state"]["teams_count"]=int(g.get("mode_state",{}).get("teams_count",2))
    elif g.get("mode") == "zombie":
        role_list=role_balance(len(g["players"]))
        g["mode_state"]={"zombie_ids":[],"zombie_pending":None}
    else:
        role_list=role_balance(len(g["players"]))
        if len(g["players"])==30: role_list=ROLES[:]; random.shuffle(role_list)
    role_list=apply_admin_roles(g, role_list)
    for p,r in zip(g["players"].values(),role_list):
        p["role"]=r; p["alive"]=True; p["base_hp"]=150 if r=="Tabib" else 100; p["max_hp"]=p["base_hp"]; p["hp"]=p["base_hp"]; p["temp_hp_bonus"]=0
        d=inv(p["id"])
        p["protected"]=d.get("protection",0)>0
        p["hanging_protected"]=d.get("hanging_protection",0)>0
        p["supper"]=d.get("supper_shield",0)>0
        p["mask"]=consume_inventory(p,"mask")
        p["fake_document"]=consume_inventory(p,"fake_document")
        p["rifle"]=d.get("rifle",0)>0
        p["hero_protection"]=d.get("hero_protection",0)>0
        add_stats(p["id"],game=True)
        body=ROLE_INTRO.get(r,f"Siz {side(r)} tarafdasiz.")
        intro=f"{EMOJI.get(r,'🎭')} Siz — {r}siz!\n\n{body}"
        if g.get("mode") == "vs":
            intro += f"\n\n⚔️ Sizning jamoangiz: {team_icon(p)}"
        await send_private(app.bot,p["id"],intro)
    if g.get("mode") == "zombie":
        first=random.choice(living(g))
        first["role"]="Zombi"
        g["mode_state"]["zombie_ids"]=[first["id"]]
        await send_private(app.bot,first["id"],"🧟 Siz — Zombisiz!\nSiz Zombie tarafidasiz. Har tun bir o‘yinchini Zombi qilishingiz mumkin.")
        await send_zombie_rosters(app.bot,g)
    await app.bot.send_message(g["chat_id"],"⚔️ <b>VS O‘YIN BOSHLANDI!</b>" if g.get("mode")=="vs" else "🎭 <b>O‘YIN BOSHLANDI!</b>",parse_mode=ParseMode.HTML)
    await unpin_lobby(app.bot,g)
    g["phase"]="night"; g["phase_id"]+=1; g["night"]=1; await start_night(app,g)


async def start_night(app,g):
    if g["ended"]: return
    cancel_jobs(g); g["phase"]="night"; g["phase_id"]+=1
    pending=g.get("next_ability_swaps", {})
    for p in g["players"].values():
        p["action"]=None; p["hero_action"]=None; p["visits"]=[]; p["blocked"]=False; p["afsungar_decisions"]={}; p["last_attackers"]=[]
        p["temp_ability"]=pending.get(str(p["id"]))
        p["temp_hp_bonus"]=0; p["advokat_result"]=False; p["koldun_hanging"]=False
        if p.get("alive"):
            p["max_hp"]=p.get("base_hp", 150 if p.get("role")=="Tabib" else 100)
            p["hp"]=min(p.get("hp",p["max_hp"]),p["max_hp"])
    g["next_ability_swaps"]={}
    try: bot_username=(await app.bot.get_me()).username or ""
    except TelegramError: bot_username=""
    night_kb=InlineKeyboardMarkup([[InlineKeyboardButton("🤖 Botga o‘tish",url=f"https://t.me/{bot_username}")]]) if bot_username else None
    path=await night_image_path()
    if path:
        try:
            with open(path,'rb') as f: await app.bot.send_photo(g["chat_id"],InputFile(f),caption=f"🌙 <b>Tun {g['night']}</b> boshlandi.\nBarcha tungi harakatlar tongda birgalikda hal qilinadi.",parse_mode=ParseMode.HTML,reply_markup=night_kb)
        except TelegramError: await app.bot.send_message(g["chat_id"],f"🌙 <b>Tun {g['night']}</b> boshlandi.",parse_mode=ParseMode.HTML,reply_markup=night_kb)
    else: await app.bot.send_message(g["chat_id"],f"🌙 <b>Tun {g['night']}</b> boshlandi.",parse_mode=ParseMode.HTML,reply_markup=night_kb)
    names="\n".join(f"• {html.escape(str(visible_name(g,p)))}" for p in living(g))
    await app.bot.send_message(g["chat_id"],f"👥 <b>Tirik o‘yinchilar:</b>\n{names}",parse_mode=ParseMode.HTML)
    for p in living(g): await offer_night_action(app,g,p)
    if g.get("mode")=="zombie":
        app.job_queue.run_once(zombie_convert_job,max(0,NIGHT_TIME-5),data={"gid":g["id"]},name=f"zombie-convert-{g['id']}")
    schedule_phase(app,g,NIGHT_TIME,resolve_night,"night")
    persist_games()


async def resolve_night(ctx):
    d=ctx.job.data; chat_id=next((cid for cid,g in games.items() if g["id"]==d["gid"]),None)
    if chat_id is None:return
    g=games[chat_id]
    if not valid_job(g,d) or g["phase"]!="night":return
    if await resolve_night_effects(ctx,g):
        g["phase"]="afsungar"; g["phase_id"]+=1
        persist_games()
        await schedule_afsungar_decision(ctx.application,g)
        return
    # End temp Veyron abilities after this night; actual swap is for NEXT night.
    g["phase"]="day"; g["phase_id"]+=1
    await start_day(ctx.application,g)


async def start_day(app,g):
    if g["ended"]: return
    cancel_jobs(g)
    # Serjant promotion happens before terminal-win evaluation.
    if not any(p.get("alive") and p.get("role")=="Komissar Katani" for p in g["players"].values()):
        for p in g["players"].values():
            if p.get("alive") and p.get("role")=="Serjant":
                p["role"]="Komissar Katani"; await send_private(app.bot,p["id"],"👮🏻‍♂️ Komissar Katani o‘ldi. Siz endi Komissar Katanisiz.")
                await app.bot.send_message(g["chat_id"],"👮🏻‍♂️ Serjant Komissar Kataniga aylandi."); break
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
    # Keep the active game in memory through discussion/voting/night.
    # It is removed only by end_game(), so callbacks and timers remain valid.
    persist_games()
    a,b,c=role_lists(g)
    await app.bot.send_message(g["chat_id"],f"☀️ <b>TONG O‘TDI</b>\n\n{a}\n\n{b}\n\n{c}\n\nJami tirik o'yinchilar: {len(living(g))}\n\nEndi kecha tunda bo'lgan voqealarni muhokama qilamiz.",parse_mode=ParseMode.HTML)
    # Temporary +50 HP from Shifokor/Tabib expires at dawn.
    for p in g["players"].values():
        # The bonus is temporary capacity, not damage: any remaining HP stays,
        # but the temporary ceiling disappears at dawn.
        p["temp_hp_bonus"]=0
        p["max_hp"]=p.get("base_hp",150 if p.get("role")=="Tabib" else 100)
        if p["alive"]: p["hp"]=min(p["hp"],p["max_hp"])
    g["phase"]="discussion"; g["phase_id"]+=1
    persist_games()
    schedule_phase(app,g,DISCUSSION_TIME,start_voting,"discussion")


async def schedule_afsungar_decision(app,g):
    # Give Afsungar a short real callback window at the end of night.
    schedule_phase(app,g,10,resolve_afsungar,"afsungar")


async def resolve_afsungar(ctx):
    d=ctx.job.data; g=find_game(d.get("gid"))
    if not g or not valid_job(g,d) or g.get("phase")!="afsungar": return
    for af in g["players"].values():
        if af.get("role")!="Afsungar": continue
        for attacker_id, decision in list(af.get("afsungar_decisions",{}).items()):
            attacker=getp(g,int(attacker_id))
            if not attacker: continue
            if decision=="kill" and attacker.get("alive"):
                kill_player(attacker,"afsungar")
                await ctx.bot.send_message(g["chat_id"],f"🧙‍♀️ Afsungar {mention(af)} {role_label(attacker['role'])}ni kechira olmadi va o‘ldirishga qaror qildi.")
                await send_private(ctx.bot,attacker["id"],"🧙‍♀️ Afsungar sizni o‘ldirishga qaror qildi.")
            elif decision=="forgive":
                await ctx.bot.send_message(g["chat_id"],f"🕊️ Afsungar {mention(af)} {role_label(attacker['role'])}ni kechirishga qaror qildi.")
                await send_private(ctx.bot,attacker["id"],"🕊️ 🧙‍♀️ Afsungar sizni kechirishga qaror qildi.")
    for p in g["players"].values(): p["afsungar_decisions"]={}
    g["phase"]="day"; g["phase_id"]+=1
    persist_games()
    await start_day(ctx.application,g)


async def start_voting(ctx):
    d=ctx.job.data
    g=find_game(d.get("gid"))
    if not g or not valid_job(g,d) or g.get("phase")!="discussion": return
    g["phase"]="voting"; g["phase_id"]+=1; g["votes"]={}; cancel_jobs(g); persist_games()
    await ctx.bot.send_message(g["chat_id"],"🗳 <b>Ovoz berish boshlandi.</b>\nHar bir tirik o‘yinchi shaxsiy chatda ovoz beradi.",parse_mode=ParseMode.HTML)
    for p in living(g):
        rows=[[InlineKeyboardButton(visible_name(g,t)[:32],callback_data=f"vote:{g['id']}:{t['id']}")] for t in living(g) if t["id"]!=p["id"]]
        rows.append([InlineKeyboardButton("⏭ Ovoz bermaslik",callback_data=f"skip:{g['id']}")])
        await send_private(ctx.bot,p["id"],"🗳 <b>Kimni osamiz?</b>\nTanlang:",InlineKeyboardMarkup(rows))
    schedule_phase(ctx.application,g,VOTING_TIME,resolve_vote,"vote")


async def resolve_vote(ctx):
    d=ctx.job.data; chat_id=next((cid for cid,g in games.items() if g["id"]==d["gid"]),None)
    if chat_id is None:return
    g=games[chat_id]
    if not valid_job(g,d) or g["phase"]!="voting":return
    counts={}
    for target in g["votes"].values():
        if target is not None: counts[target]=counts.get(target,0)+1
    if not counts:
        await ctx.bot.send_message(g["chat_id"],"🗳 Ovoz berilmadi."); return await after_vote(ctx.application,g)
    mx=max(counts.values()); top=[uid for uid,c in counts.items() if c==mx]
    if len(top)>1:
        await ctx.bot.send_message(g["chat_id"],"🤝 Ovozlar teng bo‘ldi. Hech kim osilmadi."); return await after_vote(ctx.application,g)
    victim=getp(g,top[0])
    if victim.get("koldun_hanging"):
        victim["koldun_hanging"]=False
        await ctx.bot.send_message(g["chat_id"],f"⚡ {mention(victim)}ni Koldun osilishdan himoya qildi.",parse_mode=ParseMode.HTML); return await after_vote(ctx.application,g)
    if victim["hanging_protected"]:
        victim["hanging_protected"]=False; consume_inventory(victim,"hanging_protection")
        await ctx.bot.send_message(g["chat_id"],f"🛡 {mention(victim)} osilishdan himoyalangan edi."); return await after_vote(ctx.application,g)
    kill_player(victim,"vote")
    await ctx.bot.send_message(g["chat_id"],f"⚖️ {mention(victim)} ovoz bilan o‘yindan chiqarildi.")
    if victim["role"]=="Suidsid":
        await ctx.bot.send_message(g["chat_id"],"🪢 Suidsid o‘zining g‘alaba shartini bajardi."); g["forced_winners"]=[victim]
    await after_vote(ctx.application,g)


async def after_vote(app,g):
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
    lines=["O’yin tugadi!","","G’oliblar:"]
    if win:
        for i,p in enumerate(win,1): lines.append(f"{i}. {mention(p)} — {role_label(p['role'])}")
    else: lines.append("—")
    lines += ["","Qolgan o’yinchilar:"]
    remaining=[p for p in g["players"].values() if p["id"] not in win_ids]
    if remaining:
        for i,p in enumerate(remaining,1): lines.append(f"{i}. {mention(p)} — {role_label(p['role'])}")
    else: lines.append("—")
    lines += ["",f"O’yin davomiyligi: {mm:02d} daqiqa {ss:02d} soniya"]
    await app.bot.send_message(g["chat_id"],"\n".join(lines),parse_mode=ParseMode.HTML)
    games.pop(g.get("chat_id"), None)
    persist_games()

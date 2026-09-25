"""Lobby creation, joining and closing."""

import math
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config import LOBBY_TIME, MAX_PLAYERS, MIN_PLAYERS, VS_TEAM_COLORS
from keyboards.game_keyboard import lobby_markup
from models.chat_settings import get_settings
from models.users import ensure_user
from utils.game_logic import start_game
from utils.players import getp, mention, new_player, visible_mention
from utils.permissions import has_perm
from utils.state import cancel_game, find_game, game_id, games, persist_games, schedule_phase, valid_job
from utils.telegram_utils import group_return_url, unpin_lobby


def lobby_player_list(g):
    players=list(g.get("players",{}).values())
    lines=["", f"👥 <b>Ro‘yxatdan o‘tganlar ({len(players)}):</b>"]
    if not players:
        lines.append("—")
    for i,p in enumerate(players,1):
        lines.append(f"{i}. {mention(p)}")
    return "\n".join(lines)


def standard_lobby_text(g):
    title={"name":"🏷️ Name mode","uniform":"🎭 Uniform mode","zombie":"🧟 Zombie mode","para":"💞 Para mode — faqat juftlar o‘ynaydi (/para)"}.get(g.get("mode"))
    head=f"{title}\n\n" if title else ""
    return "📌 <b>Ro‘yxatdan o‘tish boshlandi!</b>\n\n"+head+"⏳ Ro‘yxatdan o‘tish: <b>30 daqiqa</b>" + lobby_player_list(g)


def vs_lobby_text(g):
    teams={k:[] for k in list(VS_TEAM_COLORS.keys())[:int(g.get("mode_state",{}).get("teams_count",2))]}
    for p in g.get("players",{}).values():
        if p.get("team") in teams:
            teams[p["team"]].append(visible_mention(g,p,True))
    lines=["⚔️ <b>VS mode</b>", "", "<b>Jamoalar:</b>"]
    for k, members in teams.items():
        lines.append(f"{VS_TEAM_COLORS[k]} <b>{k.title()}</b>")
        lines.extend(f"  {i}. {m}" for i,m in enumerate(members,1))
        if not members: lines.append("  —")
    lines += ["", f"Jami: <b>{len(g.get('players',{}))}</b>/{player_limit(g)}", "⏳ Ro‘yxatdan o‘tish: 30 daqiqa"]
    return "\n".join(lines)


def vs_team_capacity(g):
    teams=int(g.get("mode_state",{}).get("teams_count",2))
    teams=max(2,min(9,teams))
    return math.ceil(player_limit(g)/teams)


def player_limit(g):
    return min(MAX_PLAYERS, int((g.get("settings") or {}).get("max_players", MAX_PLAYERS)))


def busy_elsewhere(uid, g):
    """True when the user already sits in another lobby or is alive in another running game."""
    for other in games.values():
        if other is g or other.get("phase") in {"ended","cancelled"}: continue
        p=other["players"].get(uid)
        if p and (other.get("phase")=="lobby" or p.get("alive")): return True
    return False


async def refresh_lobby(bot, g):
    me=await bot.get_me()
    text=vs_lobby_text(g) if g.get("mode")=="vs" else standard_lobby_text(g)
    try: await bot.edit_message_text(chat_id=g["chat_id"],message_id=g["lobby_message_id"],text=text,reply_markup=lobby_markup(g,me.username or ""),parse_mode=ParseMode.HTML)
    except TelegramError: pass


async def start_if_full(app, g):
    if g.get("phase")=="lobby" and len(g["players"])>=player_limit(g):
        await start_game(app,g)


async def create_lobby(update, ctx, mode=None, mode_value=None):
    if update.effective_chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return
    chat=update.effective_chat
    settings=get_settings(chat.id)
    if not await has_perm(ctx.bot,chat.id,update.effective_user.id,settings["perm_game"]):
        return await update.message.reply_text("❌ Bu guruhda o‘yinni faqat ruxsat berilganlar boshlay oladi.")
    if chat.id in games and games[chat.id].get("phase") not in {"ended","cancelled"}:
        return await update.message.reply_text("⚠️ Bu guruhda allaqachon o‘yin/lobby mavjud.")
    gid=game_id()
    g={"id":gid,"chat_id":chat.id,"phase":"lobby","phase_id":1,"created":time.time(),"players":{},"jobs":[],"start_time":None,"night":0,"night_log":[],"votes":{},"lobby_message_id":None,"ended":False,"night_message_ids":[],"mode":mode,"mode_value":mode_value,"bounties":[],"mode_state":{},"settings":settings}
    if mode == "vs":
        g["mode_state"]={"teams_count":int(mode_value or 2)}
    games[chat.id]=g
    me=await ctx.bot.get_me()
    text=vs_lobby_text(g) if mode == "vs" else standard_lobby_text(g)
    msg=await update.message.reply_text(text,reply_markup=lobby_markup(g,me.username or ""),parse_mode=ParseMode.HTML)
    g["lobby_message_id"]=msg.message_id
    # Pin the registration message like the reference lobby.
    try:
        await ctx.bot.pin_chat_message(chat.id,msg.message_id,disable_notification=True)
    except TelegramError:
        pass
    persist_games()
    schedule_phase(ctx.application,g,LOBBY_TIME,finish_lobby,"lobby")


async def finish_lobby(ctx:ContextTypes.DEFAULT_TYPE):
    d=ctx.job.data; chat_id=next((cid for cid,g in games.items() if g["id"]==d["gid"]),None)
    if chat_id is None:return
    g=games[chat_id]
    if not valid_job(g,d) or g["phase"]!="lobby": return
    if len(g["players"])<MIN_PLAYERS:
        cancel_game(g); await unpin_lobby(ctx.bot,g)
        try: await ctx.bot.edit_message_text(chat_id=chat_id,message_id=g["lobby_message_id"],text="🛑 O‘yinchilar soni yetarli emasligi sabab o'yin bekor qilindi.")
        except TelegramError: pass
        return
    if g.get("mode") == "vs":
        teams=int(g.get("mode_state",{}).get("teams_count",2))
        active_teams={p.get("team") for p in g["players"].values() if p.get("team")}
        if len(active_teams) < teams:
            cancel_game(g); await unpin_lobby(ctx.bot,g)
            try: await ctx.bot.edit_message_text(chat_id=chat_id,message_id=g["lobby_message_id"],text="❌ VS o‘yini bekor qilindi. Har bir jamoada kamida 1 ta o‘yinchi bo‘lishi kerak.")
            except TelegramError: pass
            return
    await start_game(ctx.application,g)


async def join_lobby_deeplink(update:Update,ctx:ContextTypes.DEFAULT_TYPE,token_value:str):
    parts=token_value.split("_",2)
    if len(parts)!=3 or parts[0]!="join":
        return False
    try:
        chat_id=int(parts[1]); gid=parts[2]
    except ValueError:
        return False
    g=games.get(chat_id)
    if not g or g.get("id")!=gid or g.get("phase")!="lobby":
        await update.message.reply_text("❌ Bu lobby topilmadi yoki ro‘yxatdan o‘tish yopilgan.")
        return True
    user=update.effective_user
    uid=user.id
    ensure_user(user)
    if uid not in g["players"]:
        if busy_elsewhere(uid,g):
            await update.message.reply_text("❌ Siz boshqa guruhdagi o‘yinda qatnashyapsiz. Avval uni tugating yoki /leave qiling.")
            return True
        if len(g["players"])>=player_limit(g):
            await update.message.reply_text(f"❌ O‘yin {player_limit(g)} kishiga to‘ldi.")
            return True
        g["players"][uid]=new_player(user)
        g["players"][uid]["lobby_joined_at"]=time.time()
        persist_games()
        await refresh_lobby(ctx.bot,g)
    return_url=await group_return_url(ctx.bot,g)
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("↗️ Guruhga o‘tish",url=return_url)]]) if return_url else None
    await update.message.reply_text("<b>Siz o‘yinga muvaffaqiyatli qo‘shildingiz! 🎭</b>",reply_markup=kb,parse_mode=ParseMode.HTML)
    await start_if_full(ctx.application,g)
    return True


async def join_vs_deeplink(update:Update,ctx:ContextTypes.DEFAULT_TYPE,token_value:str):
    parts=token_value.split("_")
    if len(parts)!=3 or parts[0]!="vsgame": return False
    gid,team=parts[1],parts[2].lower()
    g=find_game(gid)
    if not g or g.get("mode")!="vs" or g.get("phase")!="lobby":
        await update.message.reply_text("❌ VS lobby topilmadi yoki yopilgan.")
        return True
    if team not in VS_TEAM_COLORS:
        await update.message.reply_text("❌ Bunday VS jamoasi mavjud emas.")
        return True
    allowed=set(list(VS_TEAM_COLORS.keys())[:int(g.get("mode_state",{}).get("teams_count",2))])
    if team not in allowed:
        await update.message.reply_text("❌ Bu jamoa ushbu VS o‘yinida mavjud emas.")
        return True
    uid=update.effective_user.id; ensure_user(update.effective_user)
    p=getp(g,uid)
    max_team=vs_team_capacity(g)
    current=[x for x in g["players"].values() if x.get("alive") and x.get("team")==team]
    if len(current)>=max_team and (not p or p.get("team")!=team):
        await update.message.reply_text("❌ Bu jamoa to‘lgan.")
        return True
    if not p and busy_elsewhere(uid,g):
        await update.message.reply_text("❌ Siz boshqa guruhdagi o‘yinda qatnashyapsiz. Avval uni tugating yoki /leave qiling.")
        return True
    if not p and len(g["players"])>=player_limit(g):
        await update.message.reply_text(f"❌ O‘yin {player_limit(g)} kishiga to‘ldi.")
        return True
    if p and p.get("alive"):
        p["team"]=team
        await update.message.reply_text(f"✅ Siz {VS_TEAM_COLORS[team]} jamoaga qo‘shildingiz.")
    else:
        g["players"][uid]=new_player(update.effective_user); g["players"][uid]["team"]=team
        await update.message.reply_text(f"✅ Siz {VS_TEAM_COLORS[team]} jamoaga qo‘shildingiz.")
    await refresh_lobby(ctx.bot,g)
    persist_games()
    await start_if_full(ctx.application,g)
    return True

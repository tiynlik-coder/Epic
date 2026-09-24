"""Lobby, target selection and mode keyboards."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import VS_TEAM_COLORS
from utils.players import living, visible_name


def lobby_markup(g, bot_username=None):
    # Standard lobby: one button only. It opens the bot private chat via a deep link.
    if g.get("mode") == "vs" and bot_username:
        teams=int(g.get("mode_state",{}).get("teams_count",2))
        names=list(VS_TEAM_COLORS.keys())[:max(2,min(9,teams))]
        return InlineKeyboardMarkup([[InlineKeyboardButton(VS_TEAM_COLORS[n], url=f"https://t.me/{bot_username}?start=vsgame_{g['id']}_{n}") for n in names[i:i+3]] for i in range(0,len(names),3)])
    if bot_username:
        return InlineKeyboardMarkup([[InlineKeyboardButton("👨‍💼 Qo‘shilish",url=f"https://t.me/{bot_username}?start=join_{g['chat_id']}_{g['id']}")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton("👨‍💼 Qo‘shilish",callback_data=f"join:{g['id']}")]])


def name_buttons(g, prefix, uid, allow_self=False):
    rows=[]
    for p in living(g):
        if not allow_self and p["id"]==uid: continue
        rows.append([InlineKeyboardButton(visible_name(g,p)[:32],callback_data=f"{prefix}:{g['id']}:{uid}:{p['id']}")])
    return InlineKeyboardMarkup(rows)


def modes_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏷️ Name mode",callback_data="mode:name")],[InlineKeyboardButton("🎭 Uniform mode",callback_data="mode:uniform")],[InlineKeyboardButton("🧟 Zombie mode",callback_data="mode:zombie")],[InlineKeyboardButton("⚔️ VS mode",callback_data="mode:vs")]])

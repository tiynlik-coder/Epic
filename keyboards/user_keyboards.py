"""Profile, market, roles and hero keyboards."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_ACTIVE_ROLE_PRICES, EMOJI, ROLES
from models.database import db
from models.heroes import hero_row


def profile_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🥷 Mening Geroyim",callback_data="menu:hero")],[InlineKeyboardButton("📊 Reyting",callback_data="menu:rating")],[InlineKeyboardButton("🛒 Do‘kon",callback_data="menu:market")],[InlineKeyboardButton("🔙 Orqaga",callback_data="menu:home")]])


def roles_menu_markup():
    # All 30 canonical roles, two per row. Clicking a role edits the same message.
    rows=[]
    for i in range(0, len(ROLES), 2):
        pair=ROLES[i:i+2]
        rows.append([InlineKeyboardButton(f"{EMOJI.get(r, '🎭')} {r}", callback_data=f"role:{i+j}") for j,r in enumerate(pair)])
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def market_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistikani nollash — 600💷",callback_data="buy:stats")],
        [InlineKeyboardButton("📃 Soxta Hujjat — 200💷",callback_data="buy:fake")],
        [InlineKeyboardButton("🛡 Himoya — 200💷",callback_data="buy:protection")],
        [InlineKeyboardButton("⚖️ Osilishdan himoya — 2💎",callback_data="buy:hanging")],
        [InlineKeyboardButton("🔰 Supper qalqon — 3💎",callback_data="buy:supper")],
        [InlineKeyboardButton("🔫 Miltiq — 1💎",callback_data="buy:rifle")],
        [InlineKeyboardButton("🎭 Maska — 1💎",callback_data="buy:mask")],
        [InlineKeyboardButton("🎭 Faol rol",callback_data="buy:active")],
        [InlineKeyboardButton("🔙 Orqaga",callback_data="menu:home")],
    ])


def hero_menu_markup(uid):
    if not hero_row(uid):
        return InlineKeyboardMarkup([[InlineKeyboardButton("🥷 Geroy sotib olish — 90💎",callback_data="hero:buy")],
                                     [InlineKeyboardButton("🔙 Orqaga",callback_data="menu:home")]])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ 1000 Ball",callback_data="hero:ball"), InlineKeyboardButton("🛡 Himoyani yangilash",callback_data="hero:shield")],
        [InlineKeyboardButton("🩸 Qurolni o‘qlash",callback_data="hero:gun")],
        [InlineKeyboardButton("🖋 Nomini o‘zgartirish",callback_data="hero:name")],
        [InlineKeyboardButton("⭐️ Darajalar haqida",callback_data="hero:levels")],
        [InlineKeyboardButton("🛒 Geroy Market",callback_data="hero:market")],
        [InlineKeyboardButton("🔙 Orqaga",callback_data="menu:profile")],
    ])


def hero_market_markup():
    con=db(); rows=con.execute("SELECT id,seller_id,price FROM hero_market WHERE active=1 ORDER BY id DESC LIMIT 20").fetchall(); con.close()
    kb=[]
    for r in rows:
        h=hero_row(r["seller_id"])
        if h:
            kb.append([InlineKeyboardButton(f"🥷 {h['name']} • Lv.{h['level']} • {r['price']}💎",callback_data=f"hero:listing:{r['id']}")])
    kb.append([InlineKeyboardButton("➕ Geroyimni sotuvga qo‘yish",callback_data="hero:list")])
    kb.append([InlineKeyboardButton("🔙 Orqaga",callback_data="menu:hero")])
    return InlineKeyboardMarkup(kb)


def active_role_market_markup():
    rows=[]
    for role,(price,currency) in ADMIN_ACTIVE_ROLE_PRICES.items():
        symbol='💎' if currency=='diamonds' else '💷'
        rows.append([InlineKeyboardButton(f"{EMOJI.get(role,'🎭')} {role} — {price}{symbol}",callback_data=f"ar:buy:{role}")])
    rows.append([InlineKeyboardButton("🗑 Faol rolni o‘chirish — 100💷",callback_data="ar:delete")])
    rows.append([InlineKeyboardButton("🔙 Orqaga",callback_data="ar:back")])
    return InlineKeyboardMarkup(rows)

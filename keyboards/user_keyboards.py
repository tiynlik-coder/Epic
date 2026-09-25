"""Profile, market, roles and hero keyboards."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_ACTIVE_ROLE_PRICES, CURRENCY_SIGN, EMOJI, ROLES, SHOP_ITEMS
from models.database import db
from models.heroes import hero_row


def profile_markup():
    b=InlineKeyboardButton
    return InlineKeyboardMarkup([
        [b("🥷 Mening Geroyim",callback_data="menu:hero"),b("📊 Reyting",callback_data="menu:rating")],
        [b("🛒 Do‘kon",callback_data="menu:market"),b("🃏 Faol rol",callback_data="buy:active")],
        [b("💎 Olmos sotib olish",callback_data="eco:diamonds"),b("💷 Pul sotib olish",callback_data="eco:money")],
        [b("🎁 Sandiqlar",callback_data="eco:chests"),b("⭐️ VIP",callback_data="eco:vip")],
        [b("🎚 Buyumlarni yoqish/o‘chirish",callback_data="eco:items")],
        [b("🔄 Profil almashish",callback_data="eco:swap"),b("🌟 Premium guruhlar",callback_data="eco:groups")],
        [b("🔙 Orqaga",callback_data="menu:home")],
    ])


def roles_menu_markup():
    # Every role, two per row. Clicking a role edits the same message.
    rows=[]
    for i in range(0, len(ROLES), 2):
        pair=ROLES[i:i+2]
        rows.append([InlineKeyboardButton(f"{EMOJI.get(r, '🎭')} {r}", callback_data=f"role:{i+j}") for j,r in enumerate(pair)])
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def market_keyboard():
    rows=[[InlineKeyboardButton("📊 Statistikani nollash — 600💷",callback_data="buy:stats")]]
    rows+=[[InlineKeyboardButton(f"{label} — {price}{CURRENCY_SIGN[cur]}",callback_data=f"buy:{key}")] for key,(label,cur,price) in SHOP_ITEMS.items()]
    rows+=[[InlineKeyboardButton("🎭 Faol rol",callback_data="buy:active")],[InlineKeyboardButton("🔙 Orqaga",callback_data="menu:profile")]]
    return InlineKeyboardMarkup(rows)


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

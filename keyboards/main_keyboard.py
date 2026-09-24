"""Private /start menu."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import EPIC_CHANNEL_URL, EPIC_PREMIUM_URL, EPIC_SUPPORT_URL


def main_menu(bot_username=""):
    # Private /start menu: only the requested navigation buttons.
    # Profile and Market remain available through the private command menu.
    rows=[]
    if bot_username:
        rows.append([InlineKeyboardButton("➕ Guruhga qo‘shish",url=f"https://t.me/{bot_username}?startgroup=true")])
    if EPIC_PREMIUM_URL:
        rows.append([InlineKeyboardButton("🌟 Premium guruhlar",url=EPIC_PREMIUM_URL)])
    else:
        rows.append([InlineKeyboardButton("🌟 Premium guruhlar",callback_data="menu:premium")])
    rows.append([InlineKeyboardButton("🎭 Rollar",callback_data="menu:roles")])
    support_btn = InlineKeyboardButton("🆘 Yordam",url=EPIC_SUPPORT_URL) if EPIC_SUPPORT_URL else InlineKeyboardButton("🆘 Yordam",callback_data="menu:help")
    channel_btn = InlineKeyboardButton("📡 Kanal",url=EPIC_CHANNEL_URL) if EPIC_CHANNEL_URL else InlineKeyboardButton("📡 Kanal",callback_data="menu:channel")
    rows.append([support_btn, channel_btn])
    return InlineKeyboardMarkup(rows)

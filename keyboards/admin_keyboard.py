"""Admin panel keyboard."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistika",callback_data="admin:stats"),InlineKeyboardButton("👥 Userlar",callback_data="admin:users")],
        [InlineKeyboardButton("🏠 Guruhlar",callback_data="admin:groups"),InlineKeyboardButton("🎮 O‘yinlar",callback_data="admin:games")],
        [InlineKeyboardButton("🚫 Bloklar",callback_data="admin:blocks"),InlineKeyboardButton("🎭 Aktiv rollar",callback_data="admin:active")],
        [InlineKeyboardButton("💰 Valyuta / Inventar",callback_data="admin:money"),InlineKeyboardButton("🥷 Geroylar",callback_data="admin:heroes")],
        [InlineKeyboardButton("🌟 VIP",callback_data="admin:vips"),InlineKeyboardButton("📝 Loglar",callback_data="admin:logs")],
        [InlineKeyboardButton("📢 Broadcast",callback_data="admin:broadcast")],
    ])

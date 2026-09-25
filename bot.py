"""Entry point: builds the Telegram application and starts polling.

Run:  .venv/bin/python bot.py   (BOT_TOKEN is read from the environment or .env)
"""

import os
import sys

from telegram import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats, BotCommandScopeChat, Update
from telegram.error import TelegramError
from telegram.ext import ApplicationBuilder

from config import ADMIN_IDS, log
from handlers import register_handlers
from models.database import init_db
from utils.game_loop import resume_games
from utils.state import load_games_state


async def setup_bot_commands(app):
    # Shaxsiy chatda faqat /start va /profile ko'rinadi.
    # Guruh menyusi to'liq qaytarildi. Qolgan buyruqlar yozib ishlatilaveradi.
    private_cmds = [
        BotCommand("start", "Botni qayta ishga tushirish"),
        BotCommand("profile", "Profilni ko‘rish"),
        BotCommand("leave", "O‘yindan chiqish"),
    ]
    await app.bot.set_my_commands(private_cmds, scope=BotCommandScopeAllPrivateChats())
    for admin_id in ADMIN_IDS:
        try: await app.bot.set_my_commands(private_cmds, scope=BotCommandScopeChat(admin_id))
        except TelegramError: log.warning("admin %s has not started the bot yet", admin_id)

    group_commands = [
        BotCommand("start", "Botni qayta ishga tushirish"),
        BotCommand("game", "Oddiy o‘yinni boshlash"),
        BotCommand("ngame", "Name mode"),
        BotCommand("ugame", "Uniform mode"),
        BotCommand("zgame", "Zombie mode"),
        BotCommand("pgame", "Para mode (juftlar)"),
        BotCommand("vsgame", "VS mode"),
        BotCommand("vsgame2", "VS — 2 jamoa"),
        BotCommand("vsgame3", "VS — 3 jamoa"),
        BotCommand("vsgame4", "VS — 4 jamoa"),
        BotCommand("vsgame5", "VS — 5 jamoa"),
        BotCommand("vsgame6", "VS — 6 jamoa"),
        BotCommand("vsgame7", "VS — 7 jamoa"),
        BotCommand("vsgame8", "VS — 8 jamoa"),
        BotCommand("vsgame9", "VS — 9 jamoa"),
        BotCommand("bounty", "Bounty qo‘yish"),
        BotCommand("modes", "Mode tanlash"),
        BotCommand("stop", "O‘yinni to‘xtatish"),
        BotCommand("leave", "O‘yindan chiqish"),
        BotCommand("settings", "O‘yin sozlamalari (adminlar)"),
    ]
    await app.bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())


def token():
    t=os.getenv("BOT_TOKEN")
    if t:return t.strip()
    if sys.stdin.isatty():
        t=input("BOT_TOKEN kiriting: ").strip()
        if t:return t
    raise RuntimeError("BOT_TOKEN topilmadi. .env fayliga BOT_TOKEN=... qatorini yozing.")


def build_app(t):
    app=ApplicationBuilder().token(t).post_init(setup_bot_commands).build()
    register_handlers(app)
    return app


def main():
    init_db()
    load_games_state()
    app=build_app(token())
    resume_games(app)
    log.info("Epic Mafia starting. PTB 20+ polling.")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__=="__main__":
    main()

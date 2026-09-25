"""Periodic jobs: group balances expire every GROUP_BALANCE_RESET_DAYS; endless games are stopped."""

import time

from telegram.error import TelegramError

from config import GROUP_BALANCE_RESET_DAYS, MAX_GAME_MINUTES, log
from models.economy import reset_old_group_balances
from utils.state import cancel_game, games
from utils.telegram_utils import unpin_lobby


async def periodic_tasks(ctx):
    for chat_id in reset_old_group_balances():
        try: await ctx.bot.send_message(chat_id,f"💎 Guruh hisobining {GROUP_BALANCE_RESET_DAYS} kunlik muddati tugadi va u nollandi.\nQayta to‘ldirish: /gsend <olmos>")
        except TelegramError: log.info("group %s did not get the balance reset notice", chat_id)


async def stop_endless_games(ctx):
    """Games running longer than MAX_GAME_MINUTES are cancelled (bounties are refunded)."""
    limit=time.time()-MAX_GAME_MINUTES*60
    for g in list(games.values()):
        if g.get("phase") in {"lobby","ended","cancelled"} or not g.get("start_time") or g["start_time"]>limit: continue
        cancel_game(g); await unpin_lobby(ctx.bot,g)
        try: await ctx.bot.send_message(g["chat_id"],f"⚠️ O‘yin {MAX_GAME_MINUTES//60} soatdan uzoq davom etgani uchun to‘xtatildi.")
        except TelegramError: pass

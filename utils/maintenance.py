"""Periodic jobs: group balances expire every GROUP_BALANCE_RESET_DAYS."""

from telegram.error import TelegramError

from config import GROUP_BALANCE_RESET_DAYS, log
from models.economy import reset_old_group_balances


async def periodic_tasks(ctx):
    for chat_id in reset_old_group_balances():
        try: await ctx.bot.send_message(chat_id,f"💎 Guruh hisobining {GROUP_BALANCE_RESET_DAYS} kunlik muddati tugadi va u nollandi.\nQayta to‘ldirish: /gsend <olmos>")
        except TelegramError: log.info("group %s did not get the balance reset notice", chat_id)

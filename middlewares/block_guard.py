"""Runs before every handler: drops updates from blocked users/groups."""

from telegram.constants import ChatType
from telegram.ext import ApplicationHandlerStop

from config import ADMIN_ID
from models.admin_data import _blocked_group, _blocked_user, _register_group


async def admin_guard_message(update, ctx):
    u=update.effective_user; c=update.effective_chat
    if c and c.type in {ChatType.GROUP, ChatType.SUPERGROUP}:
        _register_group(c)
        if u and u.id != ADMIN_ID and (_blocked_group(c.id) or _blocked_user(u.id)):
            raise ApplicationHandlerStop
    elif u and u.id != ADMIN_ID and _blocked_user(u.id):
        raise ApplicationHandlerStop


async def admin_guard_callback(update, ctx):
    q=update.callback_query; u=q.from_user if q else None; c=q.message.chat if q and q.message else None
    if c and c.type in {ChatType.GROUP, ChatType.SUPERGROUP} and u and u.id != ADMIN_ID and (_blocked_group(c.id) or _blocked_user(u.id)):
        await q.answer("🚫 Siz uchun bu funksiya bloklangan.", show_alert=True)
        raise ApplicationHandlerStop
    if u and u.id != ADMIN_ID and _blocked_user(u.id):
        await q.answer("🚫 Siz botdan bloklangansiz.", show_alert=True)
        raise ApplicationHandlerStop

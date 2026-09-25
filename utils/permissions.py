"""Who may do what in a group: chat admins (cached for a few minutes) and the per-chat permission levels."""

import time

from telegram.error import TelegramError

from config import is_bot_admin

_ADMIN_CACHE = {}  # chat_id -> (expires_at, admin ids, owner id)
_ADMIN_TTL = 300


async def chat_admins(bot, chat_id):
    now=time.time(); cached=_ADMIN_CACHE.get(chat_id)
    if cached and cached[0]>now: return cached[1],cached[2]
    try: admins=await bot.get_chat_administrators(chat_id)
    except TelegramError: return set(),None
    ids={a.user.id for a in admins}
    owner=next((a.user.id for a in admins if a.status=="creator"),None)
    _ADMIN_CACHE[chat_id]=(now+_ADMIN_TTL,ids,owner)
    return ids,owner


async def is_chat_admin(bot, chat_id, uid):
    if is_bot_admin(uid): return True
    ids,_=await chat_admins(bot,chat_id)
    return uid in ids


async def has_perm(bot, chat_id, uid, level):
    """level: all | admin | owner (group creator). Bot admins may always."""
    if level=="all" or is_bot_admin(uid): return True
    ids,owner=await chat_admins(bot,chat_id)
    if level=="owner": return uid==owner
    return uid in ids

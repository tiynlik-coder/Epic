"""Telegram API helpers: safe edits, rate-limited private messages, membership checks."""

import asyncio
import time

from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError

from config import NIGHT_IMAGE, log


_PRIVATE_SEND_LOCK = asyncio.Lock()


_PRIVATE_SEND_LAST = 0.0


async def safe_edit(q, text, markup=None):
    try:
        await q.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    except BadRequest as e:
        if "Message is not modified" not in str(e): log.debug("edit: %s",e)
    except TelegramError as e: log.warning("edit failed: %s",e)


async def cb_answer(q, text=None, alert=False):
    try: await q.answer(text or "", show_alert=alert)
    except TelegramError: pass


async def unpin_lobby(bot, g):
    """Lobby pini faqat o‘yin boshlangunicha yoki bekor qilingunicha turadi."""
    try:
        mid=g.get("lobby_message_id")
        if not mid: return
        await bot.unpin_chat_message(chat_id=g.get("chat_id"),message_id=mid)
    except TelegramError: pass
    except Exception: pass


async def send_private(bot, uid, text, markup=None):
    global _PRIVATE_SEND_LAST
    try:
        async with _PRIVATE_SEND_LOCK:
            wait=max(0.0,0.04-(time.monotonic()-_PRIVATE_SEND_LAST))
            if wait: await asyncio.sleep(wait)
            result=await bot.send_message(uid,text,reply_markup=markup,parse_mode=ParseMode.HTML)
            _PRIVATE_SEND_LAST=time.monotonic()
            return result
    except TelegramError as e:
        log.info("private send failed uid=%s: %s",uid,e); return None


async def night_image_path():
    if NIGHT_IMAGE.exists(): return NIGHT_IMAGE
    try:
        from PIL import Image, ImageDraw, ImageFont
        im=Image.new("RGB",(900,500),(7,11,28)); d=ImageDraw.Draw(im)
        # simple reusable night-city artwork
        for x,h in [(40,180),(150,260),(290,210),(410,330),(560,230),(690,290),(800,190)]:
            d.rectangle((x,500-h,x+80,500),fill=(18,25,50))
            for yy in range(500-h+25,470,35):
                for xx in range(x+12,x+70,25): d.rectangle((xx,yy,xx+8,yy+12),fill=(160,150,80))
        d.ellipse((700,55,790,145),fill=(235,235,205))
        d.text((35,25),"EPIC MAFIA • NIGHT",fill=(240,240,240))
        im.save(NIGHT_IMAGE)
    except Exception:
        return None
    return NIGHT_IMAGE


async def group_return_url(bot, g):
    """Build a button that returns the user to the exact lobby group."""
    try:
        chat=await bot.get_chat(g["chat_id"])
        if chat.username:
            return f"https://t.me/{chat.username}"
        # Supergroup message links are exact and do not require the group to be public.
        cid=str(g["chat_id"])
        if cid.startswith("-100") and g.get("lobby_message_id"):
            return f"https://t.me/c/{cid[4:]}/{g['lobby_message_id']}"
        # Fallback: a fresh invite to the exact group.
        inv=await bot.create_chat_invite_link(g["chat_id"], name="Epic Mafia lobby")
        return inv.invite_link
    except TelegramError:
        return ""


async def is_epic_channel_member(bot, user_id: int) -> bool:
    """Check @epicmafianews membership. Bot must be an admin/member of the channel."""
    try:
        m = await bot.get_chat_member("@epicmafianews", user_id)
        if m.status in {"creator", "administrator", "member"}:
            return True
        if m.status == "restricted" and getattr(m, "is_member", False):
            return True
        return False
    except TelegramError:
        # If Telegram cannot verify membership, do not falsely claim that the user is subscribed.
        return False

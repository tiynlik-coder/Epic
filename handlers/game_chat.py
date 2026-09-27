"""Messages around a running game: last words, private night team chats and group write rules."""

import html
import time

from telegram import ChatPermissions
from telegram.constants import ChatType, ParseMode
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop

from utils.game_logic import settings_of, team_of
from utils.permissions import is_chat_admin
from utils.players import getp, living, role_label, visible_mention, visible_name
from utils.state import games
from utils.telegram_utils import send_private


async def private_game_text(update, ctx):
    """A dead player's last words go to the group; at night a team member's text goes to the team."""
    msg=update.message
    if not msg or not msg.text or update.effective_chat.type!=ChatType.PRIVATE: return
    uid=update.effective_user.id
    for g in list(games.values()):
        deadline=(g.get("last_words") or {}).pop(str(uid),None)
        if deadline is None: continue
        p=getp(g,uid)
        if time.time()>deadline or not p:
            return await msg.reply_text("⏳ Kechirasiz, so‘nggi so‘zni aytishga kechikdingiz.")
        await ctx.bot.send_message(g["chat_id"],f"💬 O‘limidan oldin kimdir {visible_mention(g,p,True)}ning qichqirganini eshitdi:\n\n<i>{html.escape(msg.text[:1000])}</i>",parse_mode=ParseMode.HTML)
        return await msg.reply_text("✅ So‘nggi so‘zingiz guruhga yuborildi.")
    for g in list(games.values()):
        p=getp(g,uid)
        if not p or not p.get("alive") or g.get("phase")!="night": continue
        name,roles=team_of(p)
        if not roles: return
        mates=[m for m in living(g) if m.get("role") in roles and m["id"]!=uid]
        if not mates: return
        text=f"{role_label(p['role'])} {html.escape(visible_name(g,p))}: {html.escape(msg.text[:1000])}"
        for m in mates: await send_private(ctx.bot,m["id"],text)
        return


MUTE_SECONDS = 30


async def mute_briefly(bot, chat_id, user_id):
    """Read-only for MUTE_SECONDS. Telegram treats restrictions under 30 s as permanent, so add one second."""
    try: await bot.restrict_chat_member(chat_id,user_id,ChatPermissions.no_permissions(),until_date=int(time.time())+MUTE_SECONDS+1)
    except TelegramError: pass


async def group_write_guard(update, ctx):
    """During a game: people outside it (or dead) may not write at all, living players not at night.
    Such a message is deleted and its author muted for 30 seconds. Otherwise the chat's write rule applies."""
    msg=update.effective_message; chat=update.effective_chat; user=update.effective_user
    if not msg or not user or not chat or chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return
    if msg.text and msg.text.startswith("/"): return
    g=games.get(chat.id)
    if not g or g.get("phase") in {"lobby","starting","ended","cancelled"}: return
    if user.is_bot or msg.sender_chat or await is_chat_admin(ctx.bot,chat.id,user.id): return
    p=getp(g,user.id)
    night=g.get("phase") in {"night","afsungar"}
    in_game=bool(p and p.get("alive"))
    if not in_game or night:
        try: await msg.delete()
        except TelegramError: pass
        await mute_briefly(ctx.bot,chat.id,user.id)
        raise ApplicationHandlerStop
    level=settings_of(g).get("write_day","all")
    allowed={"all":True,"players":True,"alive":not p.get("blocked")}.get(level,False)
    if allowed: return
    try: await msg.delete()
    except TelegramError: return
    raise ApplicationHandlerStop

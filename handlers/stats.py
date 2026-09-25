"""Ratings: /top (this chat), /gtop (everyone), /boylar, profile rating; admin /tchat and /eboylar."""

import html
import io
import re

from telegram.constants import ChatType, ParseMode

from config import is_bot_admin
from models.stats import PERIODS, market_totals, richest, top_groups, top_players, user_rank

MEDALS = ["🥇","🥈","🥉"]


def _period(ctx, text):
    """/top7 or /top 7 -> '7'."""
    m=re.search(r"(\d+)$",(text or "").split()[0].split("@")[0]) if text else None
    arg=m.group(1) if m else (ctx.args[0] if ctx.args else "")
    return arg if arg in PERIODS else ""


def _lines(rows):
    out=[]
    for i,r in enumerate(rows,1):
        mark=MEDALS[i-1] if i<=3 else f"{i}."
        out.append(f"{mark} {html.escape(str(r[1] or r[0]))} — {int(r[2] or 0)} ball ({int(r[3])} o‘yin, {int(r[4] or 0)} g‘alaba)")
    return "\n".join(out) or "— Hali o‘yinlar yo‘q"


async def cmd_top(update, ctx):
    chat=update.effective_chat
    if chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}:
        return await update.message.reply_text("📊 /top guruhda ishlaydi. Umumiy reyting: /gtop")
    period=_period(ctx,update.message.text)
    await update.message.reply_text(f"📊 <b>{html.escape(chat.title or '')} — {PERIODS[period]} reyting</b>\n\n{_lines(top_players(chat.id,period))}\n\n/top1 · /top7 · /top30 · /top",parse_mode=ParseMode.HTML)


async def cmd_gtop(update, ctx):
    period=_period(ctx,update.message.text)
    await update.message.reply_text(f"🌍 <b>Umumiy reyting — {PERIODS[period]}</b>\n\n{_lines(top_players(None,period))}\n\n/gtop1 · /gtop7 · /gtop30 · /gtop",parse_mode=ParseMode.HTML)


async def cmd_boylar(update, ctx):
    rows=richest()
    text="\n".join(f"{MEDALS[i-1] if i<=3 else f'{i}.'} {html.escape(str(r[1] or r[0]))} — {r[2]}💎 · {r[3]}💷" for i,r in enumerate(rows,1)) or "—"
    await update.message.reply_text(f"💰 <b>Eng boylar</b>\n\n{text}",parse_mode=ParseMode.HTML)


def rating_text(uid):
    lines=["📊 <b>Sizning reytingingiz</b>",""]
    for period,label in (("1","🕐 Bugun"),("7","📅 Hafta"),("30","📆 Oy"),("","🌍 Umumiy")):
        rank=user_rank(uid,period)
        lines.append(f"{label}: {rank[0]}-o‘rin, {rank[1]} ball, {rank[2]} o‘yin" if rank else f"{label}: — (o‘ynamagansiz)")
    return "\n".join(lines)


async def cmd_tchat(update, ctx):
    if not is_bot_admin(update.effective_user.id): return
    period=_period(ctx,update.message.text)
    rows=top_groups(period,20)
    text="\n".join(f"{i}. {html.escape(str(r[1] or r[0]))} ({r[0]}) — {r[2]} o‘yin, {r[3]} ishtirok" for i,r in enumerate(rows,1)) or "—"
    await update.message.reply_text(f"🏠 <b>Faol guruhlar — {PERIODS[period]}</b>\n\n{text}",parse_mode=ParseMode.HTML)


async def cmd_market_stats(update, ctx):
    if not is_bot_admin(update.effective_user.id): return
    (users,money,diamonds),paid,games=market_totals()
    pays="\n".join(f"• {p[0]}: {p[1]} ta, {p[2]}💎" for p in paid) or "—"
    await update.message.reply_text(f"📊 <b>Statistika</b>\n\n👥 Userlar: {users}\n💷 Jami pul: {money}\n💎 Jami olmos: {diamonds}\n🎮 So‘nggi 24 soatdagi o‘yinlar: {games}\n\n💳 To‘lovlar:\n{pays}",parse_mode=ParseMode.HTML)


async def cmd_eboylar(update, ctx):
    """Excel file with the 1000 richest users."""
    if not is_bot_admin(update.effective_user.id): return
    from openpyxl import Workbook
    wb=Workbook(); ws=wb.active; ws.title="Boylar"; ws.append(["#","User ID","Ism","Olmos","Pul"])
    for i,r in enumerate(richest(1000),1): ws.append([i,r[0],r[1] or "",r[2],r[3]])
    buf=io.BytesIO(); wb.save(buf); buf.seek(0)
    await update.message.reply_document(buf,filename="boylar.xlsx",caption="💰 Eng boy 1000 foydalanuvchi")

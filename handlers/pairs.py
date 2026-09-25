"""Para mode partners: /para (reply), /mypara, /dpara."""

import html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from models.pairs import break_pair, make_pair, partner_of
from models.users import ensure_user, get_user
from utils.telegram_utils import cb_answer, safe_edit


def _name(uid):
    r=get_user(uid)
    return html.escape(str(r["first_name"] or uid)) if r else str(uid)


async def cmd_para(update, ctx):
    msg=update.message; me=update.effective_user
    target=msg.reply_to_message.from_user if msg.reply_to_message else None
    if not target or target.is_bot or target.id==me.id:
        return await msg.reply_text("💞 Juftlik taklif qilish uchun o‘sha odamning xabariga reply qilib /para yozing.")
    ensure_user(me); ensure_user(target)
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Qabul qilaman",callback_data=f"para:ok:{me.id}:{target.id}"),
                              InlineKeyboardButton("❌ Rad etaman",callback_data=f"para:no:{me.id}:{target.id}")]])
    await msg.reply_text(f"💞 {_name(me.id)} {_name(target.id)}ga para bo‘lishni taklif qilmoqda!\nFaqat {_name(target.id)} javob bera oladi.",reply_markup=kb,parse_mode=ParseMode.HTML)


async def cb_para(update, ctx):
    q=update.callback_query; parts=q.data.split(":")
    if len(parts)!=4 or not parts[2].isdigit() or not parts[3].isdigit(): return await cb_answer(q)
    _,answer,from_id,to_id=parts; from_id,to_id=int(from_id),int(to_id)
    if q.from_user.id!=to_id: return await cb_answer(q,"Bu taklif sizga emas.",True)
    if answer=="ok":
        make_pair(from_id,to_id)
        await safe_edit(q,f"💞 {_name(from_id)} va {_name(to_id)} endi para!",None)
    else:
        await safe_edit(q,f"💔 {_name(to_id)} para taklifini rad etdi.",None)
    await cb_answer(q)


async def cmd_mypara(update, ctx):
    pid=partner_of(update.effective_user.id)
    await update.message.reply_text(f"💞 Sizning paringiz: {_name(pid)}" if pid else "💔 Sizda para yo‘q. Reply qilib /para yozing.",parse_mode=ParseMode.HTML)


async def cmd_dpara(update, ctx):
    ok=break_pair(update.effective_user.id)
    await update.message.reply_text("💔 Para bekor qilindi." if ok else "ℹ️ Sizda para yo‘q.")

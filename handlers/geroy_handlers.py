"""Hero (Geroy) menu, market and rename flow."""

import sqlite3
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType, ParseMode

from config import HERO_BALL_PRICE, HERO_GUN_BASE, HERO_MARKET_FEE, HERO_NAME_PRICE, HERO_PRICE, HERO_SHIELD_BASE
from keyboards.user_keyboards import hero_market_markup, hero_menu_markup
from models.database import db
from models.heroes import hero_damage_range, hero_level, hero_max_shield, hero_row, hero_text
from utils.telegram_utils import cb_answer, safe_edit


async def show_hero(q, uid):
    await safe_edit(q, hero_text(uid), hero_menu_markup(uid))


async def hero_buy(q):
    uid=q.from_user.id
    con=db()
    try:
        con.execute("BEGIN IMMEDIATE")
        if con.execute("SELECT 1 FROM heroes WHERE user_id=?",(uid,)).fetchone():
            con.rollback(); return await cb_answer(q,"Sizda Geroy allaqachon mavjud.",True)
        r=con.execute("SELECT diamonds FROM users WHERE user_id=?",(uid,)).fetchone()
        if not r or r[0] < HERO_PRICE:
            con.rollback(); return await cb_answer(q,"Sizda yetarli 💎 mavjud emas❌",True)
        con.execute("UPDATE users SET diamonds=diamonds-? WHERE user_id=?",(HERO_PRICE,uid))
        con.execute("INSERT INTO heroes(user_id,name,created_at) VALUES(?,?,?)",(uid,"Nomsiz",time.time()))
        con.commit()
    except sqlite3.IntegrityError:
        con.rollback(); return await cb_answer(q,"Sizda Geroy allaqachon mavjud.",True)
    finally:
        con.close()
    await q.message.edit_text(hero_text(uid),reply_markup=hero_menu_markup(uid),parse_mode=ParseMode.HTML)
    await cb_answer(q,"Geroy xarid qilindi✅",True)


async def hero_callback(update,ctx):
    q=update.callback_query
    if q.message.chat.type!=ChatType.PRIVATE: return await cb_answer(q,"Faqat shaxsiy chatda.",True)
    uid=q.from_user.id; a=q.data.split(":"); action=a[1] if len(a)>1 else ""
    h=hero_row(uid)
    if action=="buy": return await hero_buy(q)
    if action=="menu": return await show_hero(q,uid)
    if action=="market":
        return await safe_edit(q,"🛒 <b>Geroy Market</b>\n\nSotuvdagi Geroylarni tanlang:",hero_market_markup())
    if action=="listing" and len(a)==3:
        con=db(); row=con.execute("SELECT * FROM hero_market WHERE id=? AND active=1",(int(a[2]),)).fetchone(); con.close()
        if not row: return await cb_answer(q,"Bu e’lon mavjud emas.",True)
        if row["seller_id"]==uid: return await cb_answer(q,"O‘zingizning Geroyingizni sotib olmaysiz.",True)
        seller_h=hero_row(row["seller_id"])
        if not seller_h: return await cb_answer(q,"Geroy topilmadi.",True)
        kb=InlineKeyboardMarkup([[InlineKeyboardButton(f"💎 {row['price']} ga sotib olish",callback_data=f"hero:buylisting:{row['id']}")],[InlineKeyboardButton("🔙 Orqaga",callback_data="hero:market")]])
        return await safe_edit(q,hero_text(row["seller_id"]) + f"\n\n💎 <b>Narxi:</b> {row['price']}",kb)
    if action=="buylisting" and len(a)==3:
        con=db(); row=con.execute("SELECT * FROM hero_market WHERE id=? AND active=1",(int(a[2]),)).fetchone(); con.close()
        if not row: return await cb_answer(q,"Bu Geroy allaqachon sotilgan.",True)
        if row["seller_id"]==uid: return await cb_answer(q,"O‘zingizning Geroyingizni sotib olmaysiz.",True)
        if hero_row(uid): return await cb_answer(q,"Avval o‘zingizdagi Geroyni boshqa yo‘l bilan topshirishingiz kerak.",True)
        con=db()
        try:
            con.execute("BEGIN IMMEDIATE")
            row2=con.execute("SELECT * FROM hero_market WHERE id=? AND active=1",(int(a[2]),)).fetchone()
            if not row2:
                con.rollback(); return await cb_answer(q,"Bu Geroy allaqachon sotilgan.",True)
            price=int(row2["price"]); seller=int(row2["seller_id"])
            bal=con.execute("SELECT diamonds FROM users WHERE user_id=?",(uid,)).fetchone()
            if not bal or bal[0] < price:
                con.rollback(); return await cb_answer(q,"Sizda yetarli 💎 mavjud emas❌",True)
            if con.execute("SELECT 1 FROM heroes WHERE user_id=?",(uid,)).fetchone():
                con.rollback(); return await cb_answer(q,"Avval o‘zingizdagi Geroyni topshiring.",True)
            con.execute("UPDATE users SET diamonds=diamonds-? WHERE user_id=?",(price,uid))
            con.execute("UPDATE users SET diamonds=diamonds+? WHERE user_id=?",(max(0,price-HERO_MARKET_FEE),seller))
            con.execute("UPDATE heroes SET user_id=? WHERE user_id=?",(uid,seller))
            con.execute("UPDATE hero_market SET active=0 WHERE id=? AND active=1",(row2["id"],))
            con.commit()
        finally:
            con.close()
        try: await ctx.bot.send_message(seller,f"🥷 Geroyingiz {q.from_user.full_name} tomonidan {price}💎 ga sotib olindi.")
        except Exception: pass
        return await show_hero(q,uid)
    if not h: return await cb_answer(q,"🥷 Sizda Geroy mavjud emas.",True)
    if action=="ball":
        con=db(); r=con.execute("SELECT diamonds FROM users WHERE user_id=?",(uid,)).fetchone()
        if not r or r[0] < HERO_BALL_PRICE: con.close(); return await cb_answer(q,"Sizda yetarli 💎 mavjud emas❌",True)
        ball=h["ball"]+1000; lvl=hero_level(ball)
        con.execute("UPDATE users SET diamonds=diamonds-? WHERE user_id=?",(HERO_BALL_PRICE,uid)); con.execute("UPDATE heroes SET ball=?,level=? WHERE user_id=?",(ball,lvl,uid)); con.commit(); con.close()
        return await show_hero(q,uid)
    if action=="shield":
        cost=HERO_SHIELD_BASE+h["level"]*100; mx=hero_max_shield(h["level"])
        if h["shield"]>=mx: return await cb_answer(q,"Geroyingizda maksimal himoya bor.",True)
        con=db(); r=con.execute("SELECT money FROM users WHERE user_id=?",(uid,)).fetchone()
        if not r or r[0]<cost: con.close(); return await cb_answer(q,"Sizda yetarli 💷 mavjud emas❌",True)
        con.execute("UPDATE users SET money=money-? WHERE user_id=?",(cost,uid)); con.execute("UPDATE heroes SET shield=? WHERE user_id=?",(mx,uid)); con.commit(); con.close()
        return await show_hero(q,uid)
    if action=="gun":
        cost=HERO_GUN_BASE+h["level"]*100
        if h["patron"]>=10: return await cb_answer(q,"Geroyingizda maksimal zaryad bor.",True)
        con=db(); r=con.execute("SELECT money FROM users WHERE user_id=?",(uid,)).fetchone()
        if not r or r[0]<cost: con.close(); return await cb_answer(q,"Sizda yetarli 💷 mavjud emas❌",True)
        con.execute("UPDATE users SET money=money-? WHERE user_id=?",(cost,uid)); con.execute("UPDATE heroes SET patron=10 WHERE user_id=?",(uid,)); con.commit(); con.close()
        return await show_hero(q,uid)
    if action=="name":
        ctx.user_data["hero_rename_pending"]=True
        return await safe_edit(q,"🖋 Yangi Geroy nomini oddiy xabar qilib yuboring.\n\n💷 Narxi: 780",InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga",callback_data="hero:menu")]]))
    if action=="levels":
        lines=["⭐️ <b>Geroy darajalari</b>",""]
        for i in range(1,13):
            lo,hi=hero_damage_range(i); dmg="maksimal" if lo>=100 else f"{lo}–{hi}"
            lines.append(f"⭐️ {i}-daraja — {1100*(i-1)} ball — 👊 {dmg} — 🖤 Max himoya {hero_max_shield(i)}")
        return await safe_edit(q,"\n".join(lines),InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga",callback_data="hero:menu")]]))
    if action=="list":
        if ctx.user_data.get("hero_market_pending"): return await cb_answer(q,"Avval narx yuboring.",True)
        ctx.user_data["hero_market_pending"]=True
        return await safe_edit(q,"🛒 Geroyingizni sotuvga qo‘yish uchun narxni 💎 bilan yuboring.\n\nMinimal narx: 20💎\nSavdodan 5💎 ushlab qolinadi.",InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Bekor qilish",callback_data="hero:menu")]]))
    return await cb_answer(q)


async def hero_private_text(update,ctx):
    if update.effective_chat.type!=ChatType.PRIVATE or not update.message or not update.message.text: return False
    uid=update.effective_user.id; text=update.message.text.strip()
    if ctx.user_data.get("hero_rename_pending"):
        h=hero_row(uid)
        if not h: ctx.user_data.pop("hero_rename_pending",None); return False
        con=db(); r=con.execute("SELECT money FROM users WHERE user_id=?",(uid,)).fetchone()
        if not r or r[0]<HERO_NAME_PRICE:
            con.close(); await update.message.reply_text("Sizda yetarli 💷 mavjud emas❌"); return True
        if not 2<=len(text)<=24:
            await update.message.reply_text("Geroy nomi 2–24 belgidan iborat bo‘lsin."); return True
        con.execute("UPDATE users SET money=money-? WHERE user_id=?",(HERO_NAME_PRICE,uid)); con.execute("UPDATE heroes SET name=? WHERE user_id=?",(text,uid)); con.commit(); con.close()
        ctx.user_data.pop("hero_rename_pending",None); await update.message.reply_text("✅ Geroy nomi o‘zgartirildi!"); return True
    if ctx.user_data.get("hero_market_pending"):
        try: price=int(text)
        except ValueError: await update.message.reply_text("Narxni butun son ko‘rinishida yuboring."); return True
        if price<20: await update.message.reply_text("Minimal narx 20💎."); return True
        if not hero_row(uid): ctx.user_data.pop("hero_market_pending",None); return False
        con=db(); exists=con.execute("SELECT id FROM hero_market WHERE seller_id=? AND active=1",(uid,)).fetchone()
        if exists: con.close(); ctx.user_data.pop("hero_market_pending",None); await update.message.reply_text("Sizning Geroyingiz allaqachon Marketda."); return True
        con.execute("INSERT INTO hero_market(seller_id,price,created_at) VALUES(?,?,?)",(uid,price,time.time())); con.commit(); con.close(); ctx.user_data.pop("hero_market_pending",None)
        await update.message.reply_text("✅ Geroyingiz Geroy Marketga qo‘yildi!",reply_markup=hero_market_markup()); return True
    return False

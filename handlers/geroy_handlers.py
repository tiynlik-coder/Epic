"""Hero (Geroy) menu, market and rename flow."""

import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType, ParseMode

from config import HERO_BALL_PRICE, HERO_GUN_BASE, HERO_MARKET_FEE, HERO_NAME_PRICE, HERO_PRICE, HERO_SHIELD_BASE
from keyboards.user_keyboards import hero_market_markup, hero_menu_markup
from models.database import IntegrityError, db
from models.users import add_balance, spend
from models.heroes import hero_damage_range, hero_level, hero_max_shield, hero_row, hero_text
from utils.telegram_utils import cb_answer, safe_edit


def _charge(uid, currency, cost, hero_sql, hero_args):
    """Take `cost` from the balance and apply the hero change in one transaction; False if funds are short."""
    con=db()
    try:
        con.begin()
        if not spend(uid,currency,cost,con):
            con.rollback(); return False
        con.execute(hero_sql,hero_args)
        con.commit(); return True
    finally:
        con.close()


async def show_hero(q, uid):
    await safe_edit(q, hero_text(uid), hero_menu_markup(uid))


async def hero_buy(q):
    uid=q.from_user.id
    con=db()
    try:
        con.begin()
        if con.execute("SELECT 1 FROM heroes WHERE user_id=?",(uid,)).fetchone():
            con.rollback(); return await cb_answer(q,"Sizda Geroy allaqachon mavjud.",True)
        if not spend(uid,"diamonds",HERO_PRICE,con):
            con.rollback(); return await cb_answer(q,"Sizda yetarli 💎 mavjud emas❌",True)
        con.execute("INSERT INTO heroes(user_id,name,created_at) VALUES(?,?,?)",(uid,"Nomsiz",time.time()))
        con.commit()
    except IntegrityError:
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
            con.begin()
            # Claim the listing first: only one buyer can flip active 1 -> 0.
            row2=con.execute("UPDATE hero_market SET active=0 WHERE id=? AND active=1 RETURNING seller_id,price",(int(a[2]),)).fetchone()
            if not row2:
                con.rollback(); return await cb_answer(q,"Bu Geroy allaqachon sotilgan.",True)
            price=int(row2["price"]); seller=int(row2["seller_id"])
            if con.execute("SELECT 1 FROM heroes WHERE user_id=?",(uid,)).fetchone():
                con.rollback(); return await cb_answer(q,"Avval o‘zingizdagi Geroyni topshiring.",True)
            if not spend(uid,"diamonds",price,con):
                con.rollback(); return await cb_answer(q,"Sizda yetarli 💎 mavjud emas❌",True)
            add_balance(seller,"diamonds",max(0,price-HERO_MARKET_FEE),con)
            con.execute("UPDATE heroes SET user_id=? WHERE user_id=?",(uid,seller))
            con.commit()
        finally:
            con.close()
        try: await ctx.bot.send_message(seller,f"🥷 Geroyingiz {q.from_user.full_name} tomonidan {price}💎 ga sotib olindi.")
        except Exception: pass
        return await show_hero(q,uid)
    if not h: return await cb_answer(q,"🥷 Sizda Geroy mavjud emas.",True)
    if action=="ball":
        # Level is computed in SQL from the stored ball (same formula as hero_level) so rapid taps stay consistent.
        if not _charge(uid,"diamonds",HERO_BALL_PRICE,"UPDATE heroes SET ball=ball+1000,level=(ball+1000)/1100+1 WHERE user_id=?",(uid,)):
            return await cb_answer(q,"Sizda yetarli 💎 mavjud emas❌",True)
        return await show_hero(q,uid)
    if action=="shield":
        cost=HERO_SHIELD_BASE+h["level"]*100; mx=hero_max_shield(h["level"])
        if h["shield"]>=mx: return await cb_answer(q,"Geroyingizda maksimal himoya bor.",True)
        if not _charge(uid,"money",cost,"UPDATE heroes SET shield=? WHERE user_id=?",(mx,uid)):
            return await cb_answer(q,"Sizda yetarli 💷 mavjud emas❌",True)
        return await show_hero(q,uid)
    if action=="gun":
        cost=HERO_GUN_BASE+h["level"]*100
        if h["patron"]>=10: return await cb_answer(q,"Geroyingizda maksimal zaryad bor.",True)
        if not _charge(uid,"money",cost,"UPDATE heroes SET patron=10 WHERE user_id=?",(uid,)):
            return await cb_answer(q,"Sizda yetarli 💷 mavjud emas❌",True)
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
        if not 2<=len(text)<=24:
            await update.message.reply_text("Geroy nomi 2–24 belgidan iborat bo‘lsin."); return True
        if not _charge(uid,"money",HERO_NAME_PRICE,"UPDATE heroes SET name=? WHERE user_id=?",(text,uid)):
            await update.message.reply_text("Sizda yetarli 💷 mavjud emas❌"); return True
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

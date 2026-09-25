"""/start, profile, market and menu callbacks."""

import html
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from config import ADMIN_ACTIVE_ROLE_PRICES, EPIC_CHANNEL_URL, EPIC_SUPPORT_URL, HERO_PROTECTION_PRICE, MIN_PLAYERS, ROLES
from handlers.geroy_handlers import show_hero
from keyboards.main_keyboard import main_menu
from keyboards.user_keyboards import active_role_market_markup, market_keyboard, profile_markup, roles_menu_markup
from models.chat_settings import get_settings
from models.database import db
from models.users import buy, ensure_user, grant_first_start, spend
from utils.game_logic import start_game
from utils.lobby import join_lobby_deeplink, join_vs_deeplink
from utils.permissions import has_perm
from utils.profile import active_role_text, build_profile_text
from utils.state import games
from utils.telegram_utils import cb_answer, safe_edit
from utils.texts import MARKET_TEXT, START_PRIVATE_TEXT, role_detail_text, roles_menu_text


async def cmd_start(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_user: ensure_user(update.effective_user)
    if update.effective_chat.type == ChatType.PRIVATE and ctx.args:
        if await join_lobby_deeplink(update,ctx,ctx.args[0]):
            return
        if await join_vs_deeplink(update,ctx,ctx.args[0]):
            return
    if update.effective_chat.type in {ChatType.GROUP,ChatType.SUPERGROUP}:
        g=games.get(update.effective_chat.id)
        if g and g.get("phase")=="lobby":
            if not await has_perm(ctx.bot,update.effective_chat.id,update.effective_user.id,get_settings(update.effective_chat.id)["perm_start"]):
                return await update.message.reply_text("❌ Sizda o‘yinni boshlash huquqi yo‘q.")
            n=len(g.get("players",{}))
            if n>=MIN_PLAYERS:
                if g.get("mode")=="vs":
                    teams=int(g.get("mode_state",{}).get("teams_count",2))
                    active={p.get("team") for p in g["players"].values() if p.get("team")}
                    if len(active)<teams:
                        return await update.message.reply_text("❌ VS o‘yini uchun har bir jamoada kamida 1 ta o‘yinchi bo‘lishi kerak.")
                await start_game(ctx.application,g)
                return
            return await update.message.reply_text(f"👥 Hozir {n} ta o‘yinchi. O‘yinni boshlash uchun kamida {MIN_PLAYERS} ta kerak.")
        await update.message.reply_text("🤖 Epic Mafia bot ishlayapti. O‘yinni boshlash uchun /game yuboring.")
        return
    grant_first_start(update.effective_user.id)
    me=await ctx.bot.get_me()
    await update.message.reply_text(START_PRIVATE_TEXT,reply_markup=main_menu(me.username or ""),parse_mode=ParseMode.HTML)


async def cmd_profile(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in {ChatType.PRIVATE}: return
    ensure_user(update.effective_user)
    text = await build_profile_text(ctx.bot, update.effective_user.id)
    await update.message.reply_text(text,reply_markup=profile_markup(),parse_mode=ParseMode.HTML)


async def cmd_market(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in {ChatType.PRIVATE}: return
    ensure_user(update.effective_user)
    await send_market_reply(update.message)


async def send_market_reply(msg):
    await msg.reply_text(MARKET_TEXT,reply_markup=market_keyboard(),parse_mode=ParseMode.HTML)


async def send_market(msg):
    await msg.edit_text(MARKET_TEXT,reply_markup=market_keyboard(),parse_mode=ParseMode.HTML)


async def cb_menu(update,ctx):
    q=update.callback_query; await cb_answer(q)
    if q.message.chat.type!=ChatType.PRIVATE:return
    key=q.data.split(":",1)[1]
    if key=="home":
        me=await ctx.bot.get_me()
        await safe_edit(q,"🎭 <b>EPIC MAFIA</b>\n\nXush kelibsiz!",main_menu(me.username or ""))
    elif key=="profile":
        ensure_user(q.from_user)
        text=await build_profile_text(ctx.bot,q.from_user.id)
        await safe_edit(q,text,profile_markup())
    elif key=="roles":
        await safe_edit(q,roles_menu_text(),roles_menu_markup())
    elif key=="hero": await show_hero(q,q.from_user.id)
    elif key=="rating":
        con=db(); rows=con.execute("SELECT first_name,wins,games,money FROM users ORDER BY wins DESC,games DESC LIMIT 10").fetchall(); con.close()
        lines=["🏆 <b>Epic Mafia reytingi</b>",""]
        for i,r in enumerate(rows,1): lines.append(f"{i}. {html.escape(str(r['first_name'] or 'Nomsiz'))} — 🏆 {r['wins']} / 🎮 {r['games']}")
        await safe_edit(q,"\n".join(lines),InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga",callback_data="menu:profile")]]))
    elif key=="market":
        ensure_user(q.from_user)
        await send_market(q.message)
    elif key in {"premium","help","channel"}:
        texts={"premium":"🌟 <b>Premium guruhlar</b>\n\nPremium guruhlar ro‘yxati tez orada qo‘shiladi.",
               "help":f"🆘 <b>Yordam</b>\n\nSavollar bo‘yicha: {EPIC_SUPPORT_URL or 'admin bilan bog‘laning'}",
               "channel":f"📡 <b>Kanal</b>\n\n{EPIC_CHANNEL_URL or 'Tez orada'}"}
        await safe_edit(q,texts[key],InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga",callback_data="menu:home")]]))


async def cb_role(update,ctx):
    q=update.callback_query
    if q.message.chat.type != ChatType.PRIVATE:
        return await cb_answer(q,"Faqat shaxsiy chatda.",True)
    try:
        idx=int(q.data.split(":",1)[1])
        role=ROLES[idx]
    except (ValueError, IndexError):
        return await cb_answer(q,"Rol topilmadi.",True)
    await cb_answer(q)
    await safe_edit(q,role_detail_text(role),InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga",callback_data="menu:roles")]]))


async def cb_buy(update,ctx):
    q=update.callback_query
    item=q.data.split(":",1)[1] if q.data else ''
    if item=='active':
        # The Active Role button opens the real role list.
        if q.message.chat.type!=ChatType.PRIVATE:
            return await cb_answer(q,"Faqat shaxsiy chatda.",True)
        await cb_answer(q)
        await safe_edit(q,active_role_text(q.from_user.id),active_role_market_markup())
        return
    await cb_answer(q)
    if q.message.chat.type!=ChatType.PRIVATE:return
    uid=q.from_user.id
    mapping={"fake":("fake_document","money",200,"Soxta hujjat"),"protection":("protection","money",200,"Himoya"),"mask":("mask","diamonds",1,"Niqob"),"rifle":("rifle","diamonds",1,"Miltiq"),"hanging":("hanging_protection","diamonds",2,"Osilishdan himoya"),"supper":("supper_shield","diamonds",3,"Supper qalqon"),"hero_protection":("hero_protection","diamonds",HERO_PROTECTION_PRICE,"Geroydan himoya")}
    if item=="stats":
        con=db(); cur=con.execute("UPDATE users SET money=money-600,wins=0,games=0 WHERE user_id=? AND money>=600",(uid,)); con.commit(); con.close()
        return await cb_answer(q,"Statistika nollandi✅" if cur.rowcount==1 else "Sizda yetarli 💷 mavjud emas❌",True)
    key,currency,cost,title=mapping[item]; ok,msg=buy(uid,key,currency,cost)
    await cb_answer(q,(f"{title} xarid qilindi✅" if ok else f"Sizda yetarli {'💎' if currency=='diamonds' else '💷'} mavjud emas❌"),True)


async def cb_active_role(update,ctx):
    q=update.callback_query; a=q.data.split(":",2); uid=q.from_user.id
    if q.message.chat.type!=ChatType.PRIVATE: return await cb_answer(q,"Faqat shaxsiy chatda.",True)
    if a[1]=='back':
        return await send_market(q.message)
    if a[1]=='delete':
        con=db()
        try:
            con.begin()
            r=con.execute("SELECT id,role FROM admin_active_roles WHERE user_id=? AND is_active=1 ORDER BY created_at,id LIMIT 1",(uid,)).fetchone()
            if not r: con.rollback(); return await cb_answer(q,"❌ Sizda faol rol yo‘q!",True)
            if not spend(uid,"money",100,con): con.rollback(); return await cb_answer(q,"❌ Mablag‘ yetarli emas.",True)
            con.execute("UPDATE admin_active_roles SET is_active=0 WHERE id=?",(r[0],)); con.commit()
        finally: con.close()
        return await safe_edit(q,active_role_text(uid),active_role_market_markup())
    if a[1]=='buy':
        role=a[2]
        if role not in ADMIN_ACTIVE_ROLE_PRICES: return await cb_answer(q,"❌ Bu rol mavjud emas.",True)
        price,currency=ADMIN_ACTIVE_ROLE_PRICES[role]
        # Prevent duplicate active copies of the same role for one user.
        con=db(); exists=con.execute("SELECT 1 FROM admin_active_roles WHERE user_id=? AND role=? AND is_active=1",(uid,role)).fetchone(); con.close()
        if exists: return await cb_answer(q,"❌ Bu faol rol sizda allaqachon bor.",True)
        con=db()
        try:
            con.begin()
            if not spend(uid,currency,price,con):
                con.rollback(); return await cb_answer(q,f"❌ Sizda yetarli {'💎' if currency=='diamonds' else '💷'} mavjud emas.",True)
            con.execute("INSERT INTO admin_active_roles(user_id,role,is_active,created_at) VALUES(?,?,1,?)",(uid,role,time.time()))
            con.commit()
        finally: con.close()
        return await safe_edit(q,active_role_text(uid),active_role_market_markup())
    return await cb_answer(q)

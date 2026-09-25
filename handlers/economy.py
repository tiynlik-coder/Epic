"""Economy commands and buttons.

Transfers (/money, /give, /sgive), group balance (/gsend, /ginfo), giveaways (/send, /ghimoya, ...),
the diamond lottery (/change), chests, VIP, buying diamonds (Telegram Stars) and money,
item switches, profile swap and hero transfer (/tgeroy).

Amounts and prices always come from config or the database, never from callback data.
"""

import html
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.constants import ChatType, ParseMode
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop

from config import (CHEST_COOLDOWN_DAYS, CURRENCY_SIGN, DIAMOND_SELLER_URL, MEGA_CHEST_PRICE, MONEY_PACKS,
                    PROFILE_SWAP_PRICE, REPORT_CHAT_ID, SHOP_ITEMS, STAR_PACKS, SUPER_CHEST_PRICE, TRANSFER_FEE_MONEY,
                    VIP_DAYS, VIP_PRICE, is_bot_admin)
from models import economy
from models.chat_settings import get_settings
from models.database import db
from models.heroes import hero_row
from models.users import add_balance, ensure_user, get_user, spend, transfer
from utils.telegram_utils import cb_answer, safe_edit

GIVEAWAY_ITEMS = {"send":"diamonds","ghimoya":"protection","gqotil":"killer_protection","govoz":"hanging_protection",
                  "gdori":"medicine_protection","gslip":"slip_protection","ggeroy":"hero_protection","gmiltiq":"rifle"}
MAX_AMOUNT = 1_000_000
BIG_TRANSFER = {"money": 5000, "diamonds": 5}


def _name(user): return html.escape(user.full_name or str(user.id))


def _uname(uid):
    r=get_user(uid)
    return html.escape(str((r["first_name"] if r else "") or uid))


def _amount(text):
    return int(text) if text and text.isdigit() and 0<int(text)<=MAX_AMOUNT else None


def _item_label(item):
    return "💎 Olmos" if item=="diamonds" else SHOP_ITEMS[item][0]


async def report(bot, text):
    if not REPORT_CHAT_ID: return
    try: await bot.send_message(REPORT_CHAT_ID,text,parse_mode=ParseMode.HTML)
    except TelegramError: pass


def _back(to="menu:profile"): return [InlineKeyboardButton("🔙 Orqaga",callback_data=to)]


# ---------------- TRANSFERS ----------------

async def _transfer(update, ctx, field, to_id, amount, fee=0):
    me=update.effective_user; chat=update.effective_chat
    if to_id==me.id: return
    ensure_user(me)
    if is_bot_admin(me.id):
        economy_ok=True
        con=db(); con.execute("INSERT INTO users(user_id) VALUES(?) ON CONFLICT DO NOTHING",(to_id,)); con.commit(); con.close()
        add_balance(to_id,field,amount)
    else:
        if chat.type!=ChatType.PRIVATE and not economy.use_group_quota(chat.id,field,amount):
            return await update.message.reply_text(f"❗️ Bu guruhda bugungi o‘tkazma limiti tugadi.\nGuruh hisobini /gsend bilan {economy.GROUP_UNLIMITED_BALANCE}💎 gacha to‘ldirsangiz, limit olib tashlanadi.")
        economy_ok=transfer(me.id,to_id,field,amount,fee)
    if not economy_ok:
        return await update.message.reply_text(f"❌ Hisobingizda yetarli {CURRENCY_SIGN[field]} yo‘q"+(f" (komissiya {fee}{CURRENCY_SIGN[field]})." if fee else "."))
    note=" ".join(ctx.args[1:])[:200] if ctx.args and len(ctx.args)>1 else ""
    await update.message.reply_text(f"{_name(me)} ➔ {_uname(to_id)}: {amount}{CURRENCY_SIGN[field]}"+(f"\nIzoh: {html.escape(note)}" if note else ""),parse_mode=ParseMode.HTML)
    try: await ctx.bot.send_message(to_id,f"💸 {_name(me)} sizga {amount}{CURRENCY_SIGN[field]} o‘tkazdi."+(f"\nIzoh: {html.escape(note)}" if note else ""),parse_mode=ParseMode.HTML)
    except TelegramError: pass
    if amount>=BIG_TRANSFER[field]:
        where=html.escape(chat.title or "shaxsiy chat")
        await report(ctx.bot,f"<b>{CURRENCY_SIGN[field]} {amount} o‘tkazildi</b>\n💸 {_name(me)} ({me.id}) ➔ {_uname(to_id)} ({to_id})\n🏠 {where} ({chat.id})")


def _reply_target(update):
    r=update.message.reply_to_message
    return r.from_user if r and r.from_user and not r.from_user.is_bot else None


async def cmd_money(update, ctx):
    """/money N (reply) — send 💷, the sender pays a small fee."""
    target=_reply_target(update); amount=_amount(ctx.args[0] if ctx.args else "")
    if not target or not amount: return await update.message.reply_text("💷 Foydalanish: odamning xabariga reply qilib /money 100")
    ensure_user(target)
    await _transfer(update,ctx,"money",target.id,amount,TRANSFER_FEE_MONEY)


async def cmd_give(update, ctx):
    """/give N (reply) — send 💎."""
    target=_reply_target(update); amount=_amount(ctx.args[0] if ctx.args else "")
    if not target or not amount: return await update.message.reply_text("💎 Foydalanish: odamning xabariga reply qilib /give 5")
    ensure_user(target)
    await _transfer(update,ctx,"diamonds",target.id,amount)


async def cmd_sgive(update, ctx):
    """/sgive ID N — send 💎 by Telegram id (works in private chat)."""
    if len(ctx.args or [])<2 or not ctx.args[0].isdigit() or not _amount(ctx.args[1]):
        return await update.message.reply_text("💎 Foydalanish: /sgive <ID> <olmos> [izoh]")
    to_id=int(ctx.args[0])
    if not get_user(to_id): return await update.message.reply_text("❌ Bu foydalanuvchi botda yo‘q.")
    ctx.args=ctx.args[1:]
    await _transfer(update,ctx,"diamonds",to_id,int(ctx.args[0]))


# ---------------- GROUP BALANCE ----------------

async def cmd_gsend(update, ctx):
    chat=update.effective_chat
    if chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return
    amount=_amount(ctx.args[0] if ctx.args else "")
    if not amount: return await update.message.reply_text("💎 Foydalanish: /gsend 10 — guruh hisobiga olmos qo‘shish")
    ensure_user(update.effective_user)
    if not economy.donate_to_group(update.effective_user.id,chat.id,amount):
        return await update.message.reply_text("❌ Hisobingizda yetarli 💎 yo‘q.")
    await update.message.reply_text(f"💎 {_name(update.effective_user)} guruh hisobiga {amount} olmos hadya qildi!",parse_mode=ParseMode.HTML)


async def cmd_ginfo(update, ctx):
    chat=update.effective_chat
    if chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return
    con=db(); games_n=con.execute("SELECT COUNT(DISTINCT game_id) FROM game_results WHERE chat_id=?",(chat.id,)).fetchone()[0]; con.close()
    bal=economy.group_balance(chat.id)
    limit="cheksiz" if bal>=economy.GROUP_UNLIMITED_BALANCE else "kunlik limit bilan"
    await update.message.reply_text(f"<b>{html.escape(chat.title or '')}</b>\n\n🎮 O‘yinlar: {games_n}\n💎 Guruh hisobi: {bal}\n💸 O‘tkazmalar: {limit}\n\nHisobni to‘ldirish: /gsend <olmos>",parse_mode=ParseMode.HTML)


# ---------------- GIVEAWAYS ----------------

def giveaway_text(gw, creator_name):
    head=f"🎁 {creator_name} guruhga {gw['total']} ta {_item_label(gw['item'])} sovg‘a qildi!"
    if gw["remaining"]<=0: return head+"\n\n✅ Sovg‘alar tugadi."
    return head+f"\n\nBittadan olish uchun bosing. Qoldi: {gw['remaining']}"


async def cmd_giveaway(update, ctx):
    chat=update.effective_chat
    if chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return
    cmd=update.message.text.split()[0].lstrip("/").split("@")[0].lower()
    item=GIVEAWAY_ITEMS.get(cmd)
    count=_amount(ctx.args[0] if ctx.args else "1")
    if not item or not count or count>500: return await update.message.reply_text("🎁 Foydalanish: /send 10 (1–500 ta)")
    me=update.effective_user; ensure_user(me)
    currency,cost=("diamonds",count) if item=="diamonds" else (SHOP_ITEMS[item][1],count*SHOP_ITEMS[item][2])
    if not is_bot_admin(me.id):
        if not economy.use_group_quota(chat.id,currency,cost):
            return await update.message.reply_text("❗️ Bu guruhda bugungi limit tugadi. /gsend bilan guruh hisobini to‘ldiring.")
        if not spend(me.id,currency,cost):
            return await update.message.reply_text(f"❌ Buning uchun {cost}{CURRENCY_SIGN[currency]} kerak.")
    gid=economy.create_giveaway(chat.id,me.id,item,count)
    gw=economy.get_giveaway(gid)
    msg=await update.message.reply_text(giveaway_text(gw,_name(me)),parse_mode=ParseMode.HTML,
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 Olish",callback_data=f"gw:{gid}")]]))
    economy.set_giveaway_message(gid,msg.message_id)
    try: await msg.pin(disable_notification=True)
    except TelegramError: pass


async def cb_giveaway(update, ctx):
    q=update.callback_query; parts=q.data.split(":")
    if len(parts)!=2 or not parts[1].isdigit(): return await cb_answer(q)
    gid=int(parts[1]); uid=q.from_user.id
    gw=economy.get_giveaway(gid)
    if not gw: return await cb_answer(q,"❌ Bu sovg‘a tugagan.",True)
    need=get_settings(gw["chat_id"]).get("give_min_games",0)
    if need and economy.games_in_chat(uid,gw["chat_id"])<need:
        return await cb_answer(q,f"❗ Sovg‘ani olish uchun bu guruhda kamida {need} ta o‘yinda qatnashgan bo‘lishingiz kerak.",True)
    ensure_user(q.from_user)
    status,gw=economy.claim_giveaway(gid,uid)
    answers={"own":"❗ O‘zingiz tarqatgan sovg‘ani ololmaysiz.","again":"❗ Siz allaqachon oldingiz.","empty":"❌ Sovg‘alar tugadi.","gone":"❌ Bu sovg‘a tugagan."}
    if status!="ok": return await cb_answer(q,answers[status],True)
    await cb_answer(q,f"🎉 Tabriklaymiz! 1 ta {_item_label(gw['item'])} oldingiz!",True)
    creator=_uname(gw["creator_id"])
    if gw["remaining"]>0:
        return await safe_edit(q,giveaway_text(gw,creator),InlineKeyboardMarkup([[InlineKeyboardButton("🎁 Olish",callback_data=f"gw:{gid}")]]))
    takers=economy.giveaway_claimers(gid)
    lines=[f"{i}) {html.escape(str(r[1] or r[0]))}" for i,r in enumerate(takers,1)]
    await safe_edit(q,(giveaway_text(gw,creator)+"\n\nOlganlar:\n"+"\n".join(lines))[:4000],None)
    try: await q.message.unpin()
    except TelegramError: pass


# ---------------- LOTTERY (/change) ----------------

def lottery_markup(lid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Qo‘shilish",callback_data=f"lot:join:{lid}"),InlineKeyboardButton("🎲 Yakunlash",callback_data=f"lot:draw:{lid}")]])


def lottery_text(lot, creator_name):
    entries=economy.lottery_entries(lot["id"])
    names="\n".join(f"{i}) {html.escape(str(r[1] or r[0]))}" for i,r in enumerate(entries,1)) or "<i>Hali hech kim qo‘shilmadi.</i>"
    return f"🎲 {creator_name} kimgadir {lot['amount']} 💎 sovg‘a qilmoqchi!\n\n<b>Ishtirokchilar ({len(entries)}/50):</b>\n{names}\n\nG‘olibni egasi «Yakunlash» bilan aniqlaydi."


async def cmd_change(update, ctx):
    chat=update.effective_chat
    if chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return
    amount=_amount(ctx.args[0] if ctx.args else "")
    if not amount: return await update.message.reply_text("🎲 Foydalanish: /change 10 — olmos lotereyasi")
    me=update.effective_user; ensure_user(me)
    if not is_bot_admin(me.id):
        if not economy.use_group_quota(chat.id,"diamonds",amount):
            return await update.message.reply_text("❗️ Bu guruhda bugungi limit tugadi. /gsend bilan guruh hisobini to‘ldiring.")
        if not spend(me.id,"diamonds",amount): return await update.message.reply_text("❌ Hisobingizda yetarli 💎 yo‘q.")
    lid=economy.create_lottery(chat.id,me.id,amount)
    msg=await update.message.reply_text(lottery_text(economy.get_lottery(lid),_name(me)),parse_mode=ParseMode.HTML,reply_markup=lottery_markup(lid))
    try: await msg.pin(disable_notification=True)
    except TelegramError: pass


async def cb_lottery(update, ctx):
    q=update.callback_query; parts=q.data.split(":")
    if len(parts)!=3 or not parts[2].isdigit(): return await cb_answer(q)
    action,lid,uid=parts[1],int(parts[2]),q.from_user.id
    if action=="join":
        ensure_user(q.from_user)
        status=economy.join_lottery(lid,uid)
        answers={"own":"❗ Siz egasiz.","again":"❗ Siz allaqachon qo‘shilgansiz.","full":"❗ Joy qolmadi.","gone":"❌ Lotereya tugagan."}
        if status!="ok": return await cb_answer(q,answers[status],True)
        lot=economy.get_lottery(lid)
        await safe_edit(q,lottery_text(lot,_uname(lot["creator_id"])),lottery_markup(lid))
        return await cb_answer(q,"✅ Qo‘shildingiz!")
    if action=="draw":
        status,winner,amount=economy.draw_lottery(lid,uid)
        if status=="not_creator": return await cb_answer(q,"❗ Faqat egasi yakunlay oladi.",True)
        if status=="gone": return await cb_answer(q,"❌ Lotereya tugagan.",True)
        text=f"🎉 {amount} 💎 egasi: {_uname(winner)}!" if status=="ok" else "❗ Hech kim qatnashmadi — olmoslar egasiga qaytarildi."
        await safe_edit(q,text,None)
        try: await q.message.unpin()
        except TelegramError: pass
        return await cb_answer(q)
    await cb_answer(q)


# ---------------- PROFILE MENUS (eco:...) ----------------

def diamonds_menu():
    rows=[]
    stars=[InlineKeyboardButton(f"{d}💎 — ⭐️{s}",callback_data=f"eco:stars:{d}") for d,s in STAR_PACKS.items()]
    rows+=[stars[i:i+2] for i in range(0,len(stars),2)]
    if DIAMOND_SELLER_URL: rows.append([InlineKeyboardButton("💳 Admin orqali sotib olish",url=DIAMOND_SELLER_URL)])
    return InlineKeyboardMarkup(rows+[_back()])


def items_menu(uid):
    off=economy.disabled_items(uid)
    rows=[[InlineKeyboardButton(("❌ " if k in off else "✅ ")+label,callback_data=f"eco:itog:{k}")] for k,(label,_,_) in SHOP_ITEMS.items()]
    return InlineKeyboardMarkup(rows+[_back()])


def _days(seconds): return max(1,round(seconds/86400))


async def cb_eco(update, ctx):
    q=update.callback_query; parts=q.data.split(":"); uid=q.from_user.id
    if q.message.chat.type!=ChatType.PRIVATE: return await cb_answer(q,"Faqat shaxsiy chatda.",True)
    ensure_user(q.from_user)
    action,arg=parts[1],(parts[2] if len(parts)>2 else "")
    if action=="diamonds":
        await safe_edit(q,"💎 <b>Olmos sotib olish</b>\n\nPaketni tanlang — to‘lovdan so‘ng olmos avtomatik beriladi.",diamonds_menu())
    elif action=="stars" and arg.isdigit() and int(arg) in STAR_PACKS:
        d=int(arg)
        await ctx.bot.send_invoice(uid,title=f"💎 {d} olmos",description=f"Epic Mafia: {d} ta olmos",payload=f"stars:{d}",
                                   provider_token="",currency="XTR",prices=[LabeledPrice(f"{d} 💎",STAR_PACKS[d])])
    elif action=="money":
        rows=[[InlineKeyboardButton(f"{m}💷 — {d}💎",callback_data=f"eco:mpack:{i}")] for i,(m,d) in enumerate(MONEY_PACKS)]
        await safe_edit(q,"💷 <b>Olmos evaziga pul</b>",InlineKeyboardMarkup(rows+[_back()]))
    elif action=="mpack" and arg.isdigit() and int(arg)<len(MONEY_PACKS):
        money,cost=MONEY_PACKS[int(arg)]
        con=db()
        try:
            con.begin()
            ok=spend(uid,"diamonds",cost,con)
            if ok: add_balance(uid,"money",money,con); con.commit()
            else: con.rollback()
        finally: con.close()
        return await cb_answer(q,f"✅ {cost}💎 evaziga {money}💷 oldingiz!" if ok else "❌ Olmos yetarli emas.",True)
    elif action=="chests":
        kb=InlineKeyboardMarkup([[InlineKeyboardButton(f"💰 Super sandiq — {SUPER_CHEST_PRICE}💷",callback_data="eco:chest:super")],
                                 [InlineKeyboardButton(f"💎 Mega sandiq — {MEGA_CHEST_PRICE}💎",callback_data="eco:chest:mega")],_back()])
        await safe_edit(q,f"🎁 <b>Sandiqlar</b> (har biri {CHEST_COOLDOWN_DAYS} kunda bir marta, VIP — cheksiz)\n\n"
                          f"💰 <b>Super</b>: {SUPER_CHEST_PRICE}💷 → 2–5 💎\n"
                          f"💎 <b>Mega</b>: {MEGA_CHEST_PRICE}💎 → 9 dan 1 imkoniyat: 💷 va 💎 ikki baravar! Qolgan holatda — bankrot (hammasi yo‘qoladi).",kb)
    elif action=="chest" and arg in {"super","mega"}:
        status,value=economy.open_super_chest(uid) if arg=="super" else economy.open_mega_chest(uid)
        texts={"ok":f"🎉 Super sandiqdan {value} 💎 chiqdi!","double":"✌️ Omad! 💷 va 💎 ikki baravar oshdi!",
               "bankrupt":"☠️ Afsus... bankrot bo‘ldingiz — 💷 va 💎 yo‘qoldi.",
               "money":"❌ Mablag‘ yetarli emas.","wait":f"⏳ Keyingi sandiq {_days(value or 0)} kundan so‘ng."}
        await cb_answer(q,texts[status],True)
        if status in {"ok","double","bankrupt"}:
            await report(ctx.bot,f"🎁 {html.escape(q.from_user.full_name)} ({uid}) {arg} sandiq: {status} {value or ''}")
    elif action=="vip":
        until=economy.vip_until(uid)
        state="⭐️ Siz VIPsiz" + ("" if until in (None,0) else f" — yana {_days(until-time.time())} kun") if until is not None else "Siz hali VIP emassiz."
        kb=InlineKeyboardMarkup([[InlineKeyboardButton(f"⭐️ {VIP_DAYS} kun — {VIP_PRICE}💎",callback_data="eco:vipbuy")],_back()])
        await safe_edit(q,f"⭐️ <b>VIP</b>\n\nVIP foydalanuvchi sandiqlarni cheklovsiz ochadi.\n\n{state}",kb)
    elif action=="vipbuy":
        until=economy.buy_vip(uid)
        return await cb_answer(q,"❌ Olmos yetarli emas." if until is None else "⭐️ VIP faollashtirildi!",True)
    elif action=="items":
        await safe_edit(q,"🎚 <b>Qaysi buyumlar o‘yinda ishlasin?</b>\n❌ bo‘lgan buyum sarflanmaydi.",items_menu(uid))
    elif action=="itog" and arg in SHOP_ITEMS:
        economy.toggle_item(uid,arg)
        await safe_edit(q,"🎚 <b>Qaysi buyumlar o‘yinda ishlasin?</b>\n❌ bo‘lgan buyum sarflanmaydi.",items_menu(uid))
    elif action=="swap":
        ctx.user_data["swap_pending"]=True
        await safe_edit(q,f"🔄 <b>Profil almashish</b>\n\nHamma pul, olmos, buyum, statistika, geroy va VIP almashadi. Narxi: {PROFILE_SWAP_PRICE}💎 (siz to‘laysiz).\n\nAlmashmoqchi bo‘lgan odamning Telegram ID raqamini yuboring.",InlineKeyboardMarkup([_back()]))
    elif action in {"swapok","swapno"} and arg.isdigit():
        from_id=int(arg)
        if action=="swapno":
            con=db(); con.execute("DELETE FROM profile_offers WHERE from_id=? AND to_id=?",(from_id,uid)); con.commit(); con.close()
            await safe_edit(q,"❌ Profil almashish rad etildi.",None)
            try: await ctx.bot.send_message(from_id,f"❌ {html.escape(q.from_user.full_name)} profil almashishni rad etdi.")
            except TelegramError: pass
            return await cb_answer(q)
        status=economy.accept_swap(from_id,uid)
        texts={"ok":"✅ Profillar almashildi!","no_offer":"❌ Taklif topilmadi yoki muddati o‘tgan.","money":f"❌ Taklif egasida {PROFILE_SWAP_PRICE}💎 yo‘q."}
        await safe_edit(q,texts[status],None)
        if status=="ok":
            try: await ctx.bot.send_message(from_id,f"✅ {html.escape(q.from_user.full_name)} bilan profillar almashildi.")
            except TelegramError: pass
            await report(ctx.bot,f"🔄 Profil almashildi: {from_id} ⇄ {uid}")
    elif action=="groups":
        rows=[]
        for chat_id,balance,title,username in economy.top_groups():
            label=f"{html.escape(str(title or chat_id))} — {balance}💎"
            rows.append([InlineKeyboardButton(label,url=f"https://t.me/{username}")] if username else [InlineKeyboardButton(label,callback_data="ignore")])
        await safe_edit(q,"🌟 <b>Premium guruhlar</b> (guruh hisobi bo‘yicha)" if rows else "Hozircha premium guruhlar yo‘q. Guruh hisobini /gsend bilan to‘ldiring.",InlineKeyboardMarkup(rows+[_back()]))
    await cb_answer(q)


async def swap_id_text(update, ctx):
    """Private text after «Profil almashish»: the Telegram id of the other user."""
    if not ctx.user_data.get("swap_pending") or update.effective_chat.type!=ChatType.PRIVATE: return
    ctx.user_data.pop("swap_pending",None)
    text=(update.message.text or "").strip(); me=update.effective_user
    if not text.isdigit() or int(text)==me.id or not get_user(int(text)):
        await update.message.reply_text("❌ Bunday foydalanuvchi topilmadi.")
        raise ApplicationHandlerStop
    to_id=int(text)
    economy.offer_swap(me.id,to_id)
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Qabul qilaman",callback_data=f"eco:swapok:{me.id}"),InlineKeyboardButton("❌ Rad etaman",callback_data=f"eco:swapno:{me.id}")]])
    try:
        await ctx.bot.send_message(to_id,f"🔄 {_name(me)} siz bilan profil almashishni taklif qilmoqda (10 daqiqa amal qiladi). Hamma pul, olmos, buyum va statistika almashadi.",reply_markup=kb,parse_mode=ParseMode.HTML)
        await update.message.reply_text("✅ Taklif yuborildi. Javobni kuting.")
    except TelegramError:
        await update.message.reply_text("❌ Bu foydalanuvchiga xabar yuborib bo‘lmadi (botni ishga tushirmagan).")
    raise ApplicationHandlerStop


# ---------------- TELEGRAM STARS ----------------

def _stars_pack(payload):
    parts=(payload or "").split(":")
    return int(parts[1]) if len(parts)==2 and parts[0]=="stars" and parts[1].isdigit() and int(parts[1]) in STAR_PACKS else None


async def precheckout(update, ctx):
    pq=update.pre_checkout_query; d=_stars_pack(pq.invoice_payload)
    ok=d is not None and pq.currency=="XTR" and pq.total_amount==STAR_PACKS[d]
    await pq.answer(ok=ok,error_message=None if ok else "To‘lov ma’lumotlari noto‘g‘ri.")


async def successful_payment(update, ctx):
    pay=update.message.successful_payment; d=_stars_pack(pay.invoice_payload)
    if d is None or pay.currency!="XTR" or pay.total_amount!=STAR_PACKS[d]: return
    uid=update.effective_user.id; ensure_user(update.effective_user)
    economy.record_payment(pay.telegram_payment_charge_id,uid,"stars",d,pay.total_amount)
    if economy.complete_payment(pay.telegram_payment_charge_id):
        await update.message.reply_text(f"⭐️ Xarid uchun rahmat! Sizga {d} 💎 berildi.")
        await report(ctx.bot,f"⭐️ {_name(update.effective_user)} ({uid}) {d}💎 sotib oldi ({pay.total_amount}⭐️).")


# ---------------- HERO TRANSFER ----------------

async def cmd_tgeroy(update, ctx):
    """/tgeroy (reply) — give your hero to someone; costs 💎 equal to its level."""
    target=_reply_target(update); me=update.effective_user
    if not target or target.id==me.id: return await update.message.reply_text("🥷 Geroyni o‘tkazish uchun odamning xabariga reply qilib /tgeroy yozing.")
    h=hero_row(me.id)
    if not h: return await update.message.reply_text("🥷 Sizda Geroy yo‘q.")
    ensure_user(target)
    con=db()
    try:
        con.begin()
        if con.execute("SELECT 1 FROM heroes WHERE user_id=?",(target.id,)).fetchone():
            con.rollback(); return await update.message.reply_text("❌ Unda allaqachon Geroy bor.")
        if not spend(me.id,"diamonds",int(h["level"]),con):
            con.rollback(); return await update.message.reply_text(f"❌ O‘tkazish uchun {h['level']}💎 kerak.")
        con.execute("UPDATE heroes SET user_id=? WHERE user_id=?",(target.id,me.id))
        con.execute("UPDATE hero_market SET active=0 WHERE seller_id=? AND active=1",(me.id,))
        con.commit()
    finally:
        con.close()
    await update.message.reply_text(f"🥷 {_name(me)} ➔ {_name(target)}: {h['level']}-darajali Geroy o‘tkazildi!",parse_mode=ParseMode.HTML)


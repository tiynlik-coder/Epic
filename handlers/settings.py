"""Group game settings menu. /settings in a group sends the menu to the admin's private chat.

Every button re-checks that the presser is an admin of that group: the chat id travels in the
callback data, so it must never be trusted on its own.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType, ParseMode
from telegram.error import TelegramError

from config import EMOJI, ROLES
from models.chat_settings import DEFAULTS, LIMITS, get_settings, save_settings, update_setting
from utils.permissions import is_chat_admin
from utils.role_tables import ROLESETS
from utils.telegram_utils import cb_answer, safe_edit

ITEM_LABELS = {"protection":"🛡 Himoya","fake_document":"📃 Soxta hujjat","hanging_protection":"⚖️ Osilishdan himoya",
               "killer_protection":"⛑️ Qotildan himoya","rifle":"🔫 Miltiq","medicine_protection":"💊 Doridan himoya",
               "slip_protection":"🪤 Sirpanishdan himoya","mask":"🎭 Maska","supper_shield":"🔰 Supper qalqon",
               "hero":"🥷 Geroy","active_role":"🃏 Faol rol"}
TIME_LABELS = {"night_time":"🌙 Tun","day_time":"☀️ Muhokama","vote_time":"🗳 Ovoz","like_time":"👍 Tasdiqlash","word_time":"💬 So‘nggi so‘z"}
RULE_LABELS = {"allow_leave":"🚪 /leave ruxsat","last_words":"💬 So‘nggi so‘z","anonymous_votes":"🕶 Anonim ovoz",
               "confirm_hanging":"⚖️ Osishni 👍/👎 tasdiqlash","afk_kick":"😴 2 tun harakatsizni chiqarish"}
PERM_LEVELS = ["admin","all","owner"]
PERM_NAMES = {"admin":"adminlar","all":"hamma","owner":"guruh egasi"}
PERM_LABELS = {"perm_game":"/game","perm_start":"/start","perm_stop":"/stop"}
WRITE_LEVELS = ["all","players","alive","admins"]
WRITE_NAMES = {"all":"hamma","players":"o‘yinchilar","alive":"tirik o‘yinchilar","admins":"faqat adminlar"}
ROLESET_NAMES = {"epic":"🎭 Epic (aralash)","classic":"Classic","super":"Super","mega":"Mega","real":"Real"}
ROLES_PAGE = 16


def _btn(text, cid, *parts): return InlineKeyboardButton(text, callback_data=":".join(["cset",str(cid),*map(str,parts)]))


def _back(cid): return [_btn("🔙 Orqaga",cid,"menu")]


def main_menu(cid, title=""):
    rows=[[_btn("⏱ Vaqtlar",cid,"times"),_btn("🎭 Rollar to‘plami",cid,"roleset")],
          [_btn("🚫 Rollarni taqiqlash",cid,"roles",0),_btn("🛡 Buyumlar",cid,"items")],
          [_btn("⚙️ Qoidalar",cid,"rules"),_btn("🔐 Buyruq ruxsatlari",cid,"perms")],
          [_btn("✍️ Guruhda yozish",cid,"write")],
          [_btn("♻️ Standart sozlamalar",cid,"reset")]]
    text=f"⚙️ <b>{title or 'Guruh'} — o‘yin sozlamalari</b>\n\nO‘zgarishlar keyingi o‘yindan kuchga kiradi."
    return text,InlineKeyboardMarkup(rows)


def section(cid, name, s, page=0):
    if name=="times":
        rows=[[_btn("−",cid,"t",k,-15),InlineKeyboardButton(f"{label}: {s[k]} s",callback_data="ignore"),_btn("+",cid,"t",k,15)] for k,label in TIME_LABELS.items()]
        return "⏱ <b>Bosqichlar davomiyligi</b>",InlineKeyboardMarkup(rows+[_back(cid)])
    if name=="roleset":
        rows=[[_btn(("✅ " if s["roleset"]==r else "")+ROLESET_NAMES[r],cid,"rs",r)] for r in ("epic",)+ROLESETS]
        rows.append([_btn(f"Mega to‘ldiruvchisi: {EMOJI[s['wolf']]} {s['wolf']}",cid,"wolf")])
        text=("🎭 <b>Rollar to‘plami</b>\n\nEpic — barcha rollardan muvozanatli aralash.\n"
              "Classic / Super / Mega / Real — o‘yinchilar soniga qarab qat’iy tartib (Baku Mafia).")
        return text,InlineKeyboardMarkup(rows+[_back(cid)])
    if name=="roles":
        banned=set(s["banned_roles"]); start=page*ROLES_PAGE; chunk=list(enumerate(ROLES))[start:start+ROLES_PAGE]
        buttons=[_btn(("🚫 " if r in banned else "")+f"{EMOJI.get(r,'')} {r}",cid,"ban",i,page) for i,r in chunk]
        rows=[buttons[i:i+2] for i in range(0,len(buttons),2)]
        nav=[]
        if page>0: nav.append(_btn("⬅️",cid,"roles",page-1))
        if start+ROLES_PAGE<len(ROLES): nav.append(_btn("➡️",cid,"roles",page+1))
        if nav: rows.append(nav)
        return "🚫 <b>Taqiqlangan rollar</b>\n\nTaqiqlangan rol o‘rniga Tinch axoli beriladi. Don, Mafia, Komissar va Tinch axolini taqiqlab bo‘lmaydi.",InlineKeyboardMarkup(rows+[_back(cid)])
    if name=="items":
        rows=[[_btn(("✅ " if s["items"].get(k,True) else "❌ ")+label,cid,"it",k)] for k,label in ITEM_LABELS.items()]
        return "🛡 <b>O‘yinda ishlaydigan buyumlar</b>",InlineKeyboardMarkup(rows+[_back(cid)])
    if name=="rules":
        rows=[[_btn(("✅ " if s[k] else "❌ ")+label,cid,"rl",k)] for k,label in RULE_LABELS.items()]
        rows.append([_btn("−",cid,"t","max_players",-5),InlineKeyboardButton(f"👥 Maks. o‘yinchi: {s['max_players']}",callback_data="ignore"),_btn("+",cid,"t","max_players",5)])
        rows.append([_btn("−",cid,"t","give_min_games",-1),InlineKeyboardButton(f"🎁 Sovg‘a uchun min o‘yin: {s['give_min_games']}",callback_data="ignore"),_btn("+",cid,"t","give_min_games",1)])
        return "⚙️ <b>Qoidalar</b>",InlineKeyboardMarkup(rows+[_back(cid)])
    if name=="perms":
        rows=[[_btn(f"{label}: {PERM_NAMES[s[k]]}",cid,"pm",k)] for k,label in PERM_LABELS.items()]
        return "🔐 <b>Kim ishlata oladi?</b> (bosib almashtiring)",InlineKeyboardMarkup(rows+[_back(cid)])
    if name=="write":
        rows=[[_btn(f"🌙 Tunda: {WRITE_NAMES[s['write_night']]}",cid,"wr","write_night")],
              [_btn(f"☀️ Kunduzi: {WRITE_NAMES[s['write_day']]}",cid,"wr","write_day")]]
        return "✍️ <b>O‘yin paytida guruhga kim yoza oladi?</b>\nRuxsatsiz xabarlar o‘chiriladi (bot admin bo‘lishi kerak).",InlineKeyboardMarkup(rows+[_back(cid)])
    return main_menu(cid)


async def cmd_settings(update, ctx):
    chat=update.effective_chat
    if chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}:
        return await update.message.reply_text("⚙️ /settings buyrug‘ini guruhda yuboring — menyu shaxsiy chatingizga keladi.")
    if not await is_chat_admin(ctx.bot,chat.id,update.effective_user.id):
        return await update.message.reply_text("❌ Sozlamalar faqat guruh adminlari uchun.")
    text,markup=main_menu(chat.id,chat.title)
    try:
        await ctx.bot.send_message(update.effective_user.id,text,reply_markup=markup,parse_mode=ParseMode.HTML)
        await update.message.reply_text("⚙️ Sozlamalar menyusi shaxsiy chatingizga yuborildi.")
    except TelegramError:
        await update.message.reply_text("❗️ Avval botga shaxsiy chatda /start bosing.")


async def cb_settings(update, ctx):
    q=update.callback_query; parts=q.data.split(":")
    if len(parts)<3 or q.message.chat.type!=ChatType.PRIVATE: return await cb_answer(q)
    try: cid=int(parts[1])
    except ValueError: return await cb_answer(q)
    if not await is_chat_admin(ctx.bot,cid,q.from_user.id): return await cb_answer(q,"❌ Siz bu guruhning admini emassiz.",True)
    action,args=parts[2],parts[3:]
    s=get_settings(cid); show="menu"; page=0
    if action=="menu":
        text,markup=main_menu(cid); return await safe_edit(q,text,markup)
    if action in {"times","roleset","items","rules","perms","write"}: show=action
    elif action=="roles": show="roles"; page=int(args[0]) if args and args[0].isdigit() else 0
    elif action=="t" and len(args)==2 and args[0] in LIMITS:
        s=update_setting(cid,args[0],int(s[args[0]])+int(args[1])); show="rules" if args[0] in {"max_players","give_min_games"} else "times"
    elif action=="rs" and args and args[0] in ("epic",)+ROLESETS:
        s=update_setting(cid,"roleset",args[0]); show="roleset"
    elif action=="wolf":
        s=update_setting(cid,"wolf","Tulki" if s["wolf"]=="Bo‘ri" else "Bo‘ri"); show="roleset"
    elif action=="ban" and len(args)==2 and args[0].isdigit() and int(args[0])<len(ROLES):
        role=ROLES[int(args[0])]; banned=set(s["banned_roles"])
        if role in {"Don","Mafia","Komissar Katani","Tinch axoli"}: return await cb_answer(q,"Bu rolni taqiqlab bo‘lmaydi.",True)
        banned^={role}; s=update_setting(cid,"banned_roles",sorted(banned)); show="roles"; page=int(args[1]) if args[1].isdigit() else 0
    elif action=="it" and args and args[0] in ITEM_LABELS:
        s["items"][args[0]]=not s["items"].get(args[0],True); save_settings(cid,s); show="items"
    elif action=="rl" and args and args[0] in RULE_LABELS:
        s=update_setting(cid,args[0],not s[args[0]]); show="rules"
    elif action=="pm" and args and args[0] in PERM_LABELS:
        s=update_setting(cid,args[0],PERM_LEVELS[(PERM_LEVELS.index(s[args[0]])+1)%len(PERM_LEVELS)]); show="perms"
    elif action=="wr" and args and args[0] in {"write_night","write_day"}:
        s=update_setting(cid,args[0],WRITE_LEVELS[(WRITE_LEVELS.index(s[args[0]])+1)%len(WRITE_LEVELS)]); show="write"
    elif action=="reset":
        save_settings(cid,dict(DEFAULTS)); s=get_settings(cid); await cb_answer(q,"♻️ Standart sozlamalar tiklandi.",True)
        text,markup=main_menu(cid); return await safe_edit(q,text,markup)
    text,markup=section(cid,show,s,page)
    await safe_edit(q,text,markup); await cb_answer(q)

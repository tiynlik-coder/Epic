"""Game commands and in-game button callbacks."""

import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config import MAX_PLAYERS, is_bot_admin
from keyboards.game_keyboard import modes_keyboard
from models.users import spend
from models.heroes import hero_row
from utils.lobby import create_lobby
from utils.night_actions import veyron_notice_job
from utils.players import ability_role, getp, living, mention, targets, visible_mention, visible_name
from utils.state import cancel_game, find_game, games, persist_games
from utils.telegram_utils import cb_answer, safe_edit, unpin_lobby
from utils.texts import mode_detail


async def cmd_game(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    return await create_lobby(update,ctx)


async def cmd_ngame(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return
    raw=(update.message.text or "").split(maxsplit=1)
    if len(raw)<2 or not raw[1].strip():
        return await update.message.reply_text("❌ /ngame dan keyin nom, belgi, emoji yoki boshqa qiymat yozing.")
    return await create_lobby(update,ctx,"name",raw[1].strip())


async def cmd_ugame(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return
    return await create_lobby(update,ctx,"uniform",None)


async def cmd_zgame(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return
    return await create_lobby(update,ctx,"zombie",None)


async def cmd_vsgame(update:Update,ctx:ContextTypes.DEFAULT_TYPE, teams_override=None):
    if update.effective_chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return
    raw=(update.message.text or "").strip().lower()
    teams=teams_override
    if teams is None:
        tail=raw[len("/vsgame"):].strip()
        if tail.isdigit(): teams=int(tail)
        elif ctx.args and ctx.args[0].isdigit(): teams=int(ctx.args[0])
        else: teams=2
    if not 2 <= teams <= 9:
        return await update.message.reply_text("❌ VS mode jamoalari 2–9 oralig‘ida bo‘lishi kerak.")
    return await create_lobby(update,ctx,"vs",teams)


async def cmd_bounty(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return
    g=games.get(update.effective_chat.id)
    if not g or g.get("phase") in {"lobby","ended","cancelled"}:
        return await update.message.reply_text("❌ Bounty faqat faol o‘yin vaqtida ishlaydi.")
    reply=update.message.reply_to_message
    if not reply or not reply.from_user: return await update.message.reply_text("❌ Bounty qo‘yish uchun o‘yinchi xabariga reply qiling.")
    try: amount=int((ctx.args or [])[0])
    except (ValueError,IndexError): return await update.message.reply_text("❌ Foydalanish: /bounty <pul>")
    if amount<=0 or amount>10_000_000: return await update.message.reply_text("❌ Pul miqdori 1–10 000 000 oralig‘ida bo‘lishi kerak.")
    target=getp(g,reply.from_user.id)
    owner=getp(g,update.effective_user.id)
    if not target or not target["alive"]: return await update.message.reply_text("❌ Bounty faqat tirik o‘yinchiga qo‘yiladi.")
    if not owner or not owner["alive"]: return await update.message.reply_text("❌ Faqat tirik o‘yinchi bounty qo‘ya oladi.")
    if not spend(owner["id"],"money",amount):
        return await update.message.reply_text("❌ Hisobingizda yetarli mablag‘ mavjud emas.")
    g.setdefault("bounties",[]).append({"owner":owner["id"],"target":target["id"],"amount":amount,"created":time.time()})
    persist_games()
    await update.message.reply_text(f"🎯 {visible_name(g,target)}ni o‘ldirganga {amount}💷 mukofot beriladi!")


async def cmd_modes(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return
    member=await ctx.bot.get_chat_member(update.effective_chat.id,update.effective_user.id)
    if member.status not in {"administrator","creator"}: return await update.message.reply_text("❌ Bu buyruq faqat guruh adminlari uchun.")
    try: await update.message.delete()
    except TelegramError: pass
    await ctx.bot.send_message(update.effective_chat.id,"🎮 <b>Marhamat, kerakli mode'ni tanlang.</b>",reply_markup=modes_keyboard(),parse_mode=ParseMode.HTML)


async def cb_mode(update,ctx):
    q=update.callback_query
    if q.message.chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return await cb_answer(q,"Faqat guruhda.",True)
    member=await ctx.bot.get_chat_member(q.message.chat.id,q.from_user.id)
    if member.status not in {"administrator","creator"}: return await cb_answer(q,"Faqat guruh admini tanlay oladi.",True)
    key=q.data.split(":",1)[1]
    if key=="back": return await safe_edit(q,"🎮 <b>Marhamat, kerakli mode'ni tanlang.</b>",modes_keyboard())
    return await safe_edit(q,mode_detail(key),InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ortga",callback_data="mode:back")]]))


async def cb_join(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await cb_answer(q)
    gid=q.data.split(":",1)[1]
    g=next((x for x in games.values() if x["id"]==gid),None)
    if not g or g.get("phase")!="lobby": return await cb_answer(q,"Lobby yopilgan.",True)
    if len(g.get("players",{}))>=MAX_PLAYERS: return await cb_answer(q,"O‘yin to‘ldi.",True)
    me=await ctx.bot.get_me()
    link=f"https://t.me/{me.username}?start=join_{g['chat_id']}_{g['id']}"
    await q.message.reply_text("🎭 O‘yinga qo‘shilish uchun botning shaxsiy chatiga o‘ting.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤖 Botga o‘tish",url=link)]]))


def parse_target(data):
    a=data.split(":"); return a


async def cb_zombie(update,ctx):
    q=update.callback_query; a=q.data.split(":")
    if len(a)!=4: return
    _,gid,actor,target=a
    g=next((x for x in games.values() if x["id"]==gid),None)
    if not g or g.get("mode")!="zombie" or g["phase"]!="night": return await cb_answer(q,"Bu tanlov mavjud emas.",True)
    if q.from_user.id!=int(actor): return await cb_answer(q,"Bu tanlov siz uchun emas.",True)
    p=getp(g,int(actor)); t=getp(g,int(target))
    if not p or p.get("role")!="Zombi" or not p["alive"] or not t or not t["alive"] or t["id"]==p["id"]: return await cb_answer(q,"Nishon mavjud emas.",True)
    if p.get("action") is not None: return await cb_answer(q,"Tanlovingiz allaqachon tasdiqlangan.",True)
    p["action"]={"type":"zombie","target":t["id"],"selected_at":time.time()}
    await safe_edit(q,f"🧟 Sizning tanlovingiz:\n\n{visible_name(g,t)}",None); await cb_answer(q,"Tanlov saqlandi.")


async def cb_res(update,ctx):
    q=update.callback_query; a=q.data.split(":")
    if len(a)!=4: return
    _,gid,uid,target=a
    g=next((x for x in games.values() if x.get("id")==gid),None)
    if not g or g.get("phase")!="night" or q.from_user.id!=int(uid): return await cb_answer(q,"Bu tanlov mavjud emas.",True)
    p=getp(g,int(uid)); t=getp(g,int(target))
    if not p or ability_role(p)!="Ruhoniy" or not p.get("alive") or p.get("resurrections",0)>=3 or not t or t.get("alive"): return await cb_answer(q,"Bu tanlov mavjud emas.",True)
    if p.get("action") is not None: return await cb_answer(q,"Tanlovingiz allaqachon tasdiqlangan.",True)
    p["action"]={"type":"resurrect","target":t["id"],"selected_at":time.time()}
    await safe_edit(q,f"✝️ Sizning tanlovingiz:\n\n{visible_name(g,t,True)}",None); persist_games(); await cb_answer(q,"Tanlov saqlandi.")


async def cb_heroact(update,ctx):
    q=update.callback_query; a=q.data.split(":")
    if len(a)<4: return
    _,action,gid,uid=a
    g=next((x for x in games.values() if x.get("id")==gid),None)
    if not g or g.get("phase")!="night" or q.from_user.id!=int(uid): return await cb_answer(q,"Bu tanlov mavjud emas.",True)
    p=getp(g,int(uid)); h=hero_row(int(uid))
    if not p or not p.get("alive") or not h: return await cb_answer(q,"Geroy mavjud emas.",True)
    if p.get("hero_action") is not None: return await cb_answer(q,"Geroy tanlovi allaqachon saqlandi.",True)
    if action=="attack":
        if h["patron"]<1: return await cb_answer(q,"Geroyingizda zaryad qolmagan.",True)
        rows=[]
        for t in living(g):
            if t["id"]!=p["id"]: rows.append([InlineKeyboardButton(visible_name(g,t)[:32],callback_data=f"heroact:target:{gid}:{uid}:{t['id']}")])
        return await safe_edit(q,"👊 Geroy bilan kimga hujum qilamiz?",InlineKeyboardMarkup(rows))
    if action=="shield":
        p["hero_action"]={"type":"shield","selected_at":time.time()}
        return await safe_edit(q,"🥷 Geroy harakati:\n\nSizning tanlovingiz: 🛡 Himoyalanish",None)
    if action=="skip":
        p["hero_action"]={"type":"skip","selected_at":time.time()}
        return await safe_edit(q,"🥷 Geroy harakati:\n\nSizning tanlovingiz: ⏭ O‘tkazib yuborish",None)
    if action=="target" and len(a)==5:
        target=getp(g,int(a[4]))
        if not target or not target.get("alive") or target["id"]==p["id"]: return await cb_answer(q,"Nishon mavjud emas.",True)
        p["hero_action"]={"type":"attack","target":target["id"],"selected_at":time.time()}
        return await safe_edit(q,f"🥷 Geroy harakati:\n\nSizning tanlovingiz: 👊 {visible_name(g,target)}",None)
    return await cb_answer(q)


async def cb_action(update,ctx):
    q=update.callback_query; a=parse_target(q.data)
    if len(a)<4: return
    _,gid,actor,target=a[:4]
    g=next((x for x in games.values() if x["id"]==gid),None)
    if not g or g["phase"]!="night": return await cb_answer(q,"Bu tun tugagan.",True)
    if q.from_user.id!=int(actor): return await cb_answer(q,"Bu tanlov siz uchun emas.",True)
    p=getp(g,int(actor)); t=getp(g,int(target))
    if not p or not t or not p["alive"] or not t["alive"]: return await cb_answer(q,"O‘yinchi endi mavjud emas.",True)
    if p["action"] is not None: return await cb_answer(q,"Tanlovingiz allaqachon tasdiqlangan.",True)
    r=ability_role(p)
    if r=="Manipulyator":
        rows=[[InlineKeyboardButton(visible_name(g,x)[:32],callback_data=f"manip2:{gid}:{actor}:{x['id']}")] for x in living(g) if x["id"] not in {p["id"],t["id"]}]
        p["action"]={"type":"manipulator","controlled":t["id"],"selected_at":time.time()}
        await safe_edit(q,"🪄 Endi harakatni kimga yo‘naltiramiz?",InlineKeyboardMarkup(rows))
        persist_games(); return await cb_answer(q,"Birinchi tanlov saqlandi.")
    p["action"]={"type":"target","target":t["id"],"selected_at":time.time()}
    texts={"Shifokor":"🩺 Sizning tanlovingiz:","Daydi":"🌙 Sizning tanlovingiz:","Kezuvchi":"🚶 Sizning tanlovingiz:","Koldun":"⚡ Sizning tanlovingiz:","Don":"🎩 Sizning tanlovingiz:","Mafia":"🔪 Sizning tanlovingiz:","Advokat":"⚖️ Sizning tanlovingiz:","Ayg‘oqchi":"🕵️ Sizning tanlovingiz:","Labarant":"🧪 Sizning tanlovingiz:","Manipulyator":"🪄 Sizning tanlovingiz:","Ruhoniy":"✝️ Sizning tanlovingiz:","Undiruvchi":"💰 Sizning tanlovingiz:","Sotqin":"🦎 Sizning tanlovingiz:","Folbin":"🧿 Sizning tanlovingiz:","Zodagon":"👑 Sizning tanlovingiz:","Qotil":"🔪 Sizning tanlovingiz:","Minior":"💣 Sizning tanlovingiz:","Snayper":"👨🏻‍🎤 Sizning tanlovingiz:","Qorbobo":"🎅 Sizning tanlovingiz:","Qorbola":"🌨️ Sizning tanlovingiz:","Tabib":"🩺 Sizning tanlovingiz:"}
    await safe_edit(q,texts.get(r,"Sizning tanlovingiz:")+f"\n\n{visible_name(g,t)}",None)
    persist_games()
    await cb_answer(q,"Tanlov saqlandi.")


async def cb_manip2(update,ctx):
    q=update.callback_query; parts=q.data.split(":")
    if len(parts)!=4: return await cb_answer(q,"Bu tanlov mavjud emas.",True)
    _,gid,uid,target=parts; g=find_game(gid)
    if not g or g.get("phase")!="night" or q.from_user.id!=int(uid): return await cb_answer(q,"Bu tun tugagan.",True)
    p=getp(g,int(uid)); t=getp(g,int(target))
    if not p or not t or not p.get("alive") or not t.get("alive") or ability_role(p)!="Manipulyator": return await cb_answer(q,"Nishon mavjud emas.",True)
    a=p.get("action") or {}
    if a.get("type")!="manipulator" or a.get("redirect_target") is not None: return await cb_answer(q,"Tanlovingiz allaqachon saqlandi.",True)
    if t["id"] in {p["id"],a.get("controlled")}: return await cb_answer(q,"Bu o‘yinchini tanlab bo‘lmaydi.",True)
    a["redirect_target"]=t["id"]
    p["action"]=a
    await safe_edit(q, f"🪄 Sizning tanlovingiz:\n\n{visible_name(g,getp(g,a['controlled']))} → {visible_name(g,t)}", None)
    persist_games(); await cb_answer(q,"Tanlov saqlandi.")


async def cb_katani_mode(update,ctx):
    q=update.callback_query; a=q.data.split(":"); _,gid,uid,mode=a
    g=next((x for x in games.values() if x["id"]==gid),None)
    if not g or g["phase"]!="night" or q.from_user.id!=int(uid): return await cb_answer(q,"Bu tanlov mavjud emas.",True)
    p=getp(g,int(uid));
    if not p or not p.get("alive") or ability_role(p)!="Komissar Katani" or p["action"] is not None:return await cb_answer(q,"Tanlovingiz allaqachon saqlandi.",True)
    kb=[]
    for t in targets(g,p["id"]): kb.append([InlineKeyboardButton(visible_name(g,t)[:32],callback_data=f"katani:{gid}:{uid}:{t['id']}:{mode}")])
    await safe_edit(q,"🕵🏻‍♂️ Bugun kimni tanlaymiz?",InlineKeyboardMarkup(kb)); await cb_answer(q)


async def cb_katani(update,ctx):
    q=update.callback_query; _,gid,uid,target,mode=q.data.split(":")
    g=next((x for x in games.values() if x["id"]==gid),None)
    if not g or g["phase"]!="night" or q.from_user.id!=int(uid): return await cb_answer(q,"Bu tun tugagan.",True)
    p=getp(g,int(uid)); t=getp(g,int(target))
    if not p or not t or not p.get("alive") or ability_role(p)!="Komissar Katani" or p["action"] is not None:return await cb_answer(q,"Tanlov saqlandi yoki mavjud emas.",True)
    p["action"]={"type":mode,"target":t["id"],"selected_at":time.time()}
    await safe_edit(q,"🕵🏻‍♂️ Sizning tanlovingiz:\n\n"+visible_name(g,t)+(" — 🔎 Tekshirish" if mode=="check" else " — 🔫 Nishonga olish"),None); await cb_answer(q,"Tanlov saqlandi.")


async def cb_prof(update,ctx):
    q=update.callback_query; parts=q.data.split(":")
    if len(parts)!=4: return await cb_answer(q,"Bu tanlov mavjud emas.",True)
    _,gid,uid,choice=parts
    g=next((x for x in games.values() if x.get("id")==gid),None)
    if not g or g.get("phase")!="night" or q.from_user.id!=int(uid): return await cb_answer(q,"Bu tun tugagan.",True)
    p=getp(g,int(uid));
    if not p or not p.get("alive") or ability_role(p)!="Professor" or p.get("action") is not None:
        return await cb_answer(q,"Tanlov saqlandi yoki mavjud emas.",True)
    if choice=="death":
        rows=[[InlineKeyboardButton(visible_name(g,t)[:32],callback_data=f"prof_target:{gid}:{uid}:{t['id']}")] for t in targets(g,p["id"])]
        if not rows: return await cb_answer(q,"Nishon yo‘q.",True)
        return await safe_edit(q,"🎩 O‘lim qutisi uchun nishonni tanlang.",InlineKeyboardMarkup(rows))
    p["action"]={"type":"professor","choice":"normal","selected_at":time.time()}
    await safe_edit(q,"🎩 Sizning tanlovingiz:\n💼 Oddiy yo‘l",None); await cb_answer(q,"Tanlov saqlandi.")


async def cb_prof_target(update,ctx):
    q=update.callback_query; parts=q.data.split(":")
    if len(parts)!=4: return await cb_answer(q,"Bu tanlov mavjud emas.",True)
    _,gid,uid,target=parts
    g=next((x for x in games.values() if x.get("id")==gid),None)
    if not g or g.get("phase")!="night" or q.from_user.id!=int(uid): return await cb_answer(q,"Bu tun tugagan.",True)
    p=getp(g,int(uid)); t=getp(g,int(target))
    if not p or not t or not p.get("alive") or not t.get("alive") or ability_role(p)!="Professor" or p.get("action") is not None:
        return await cb_answer(q,"Nishon mavjud emas.",True)
    p["action"]={"type":"professor","choice":"death","target":t["id"],"selected_at":time.time()}
    await safe_edit(q,f"🎩 Sizning tanlovingiz:\n☠️ O‘lim qutisi — {visible_name(g,t)}",None); persist_games(); await cb_answer(q,"Tanlov saqlandi.")


async def cb_vey1(update,ctx):
    q=update.callback_query; _,gid,uid,target=q.data.split(":")
    g=next((x for x in games.values() if x["id"]==gid),None)
    if not g or g["phase"]!="night" or q.from_user.id!=int(uid):return await cb_answer(q,"Bu tun tugagan.",True)
    p=getp(g,int(uid)); t=getp(g,int(target));
    if not p or not t or not p.get("alive") or ability_role(p)!="Veyron" or p["action"] is not None:return await cb_answer(q,"Tanlov mavjud emas.",True)
    p["action"]={"type":"veyron","first":t["id"],"selected_at":time.time()}
    rows=[[InlineKeyboardButton(visible_name(g,x)[:32],callback_data=f"vey2:{gid}:{uid}:{x['id']}" )] for x in living(g) if x["id"] not in {p["id"],t["id"]}]
    await safe_edit(q,"🧲 Ikkinchi o‘yinchini tanlang.",InlineKeyboardMarkup(rows)); await cb_answer(q)


async def cb_vey2(update,ctx):
    q=update.callback_query; _,gid,uid,target=q.data.split(":")
    g=next((x for x in games.values() if x["id"]==gid),None); p=getp(g,int(uid)) if g else None
    if not g or g["phase"]!="night" or q.from_user.id!=int(uid) or not p:return await cb_answer(q,"Bu tun tugagan.",True)
    if p["action"] is None or p["action"].get("type")!="veyron":return await cb_answer(q,"Birinchi tanlov topilmadi.",True)
    if p["action"].get("second"):return await cb_answer(q,"Tanlov saqlandi.",True)
    t=getp(g,int(target)); first=getp(g,p["action"]["first"])
    if not t or not first or not t["alive"] or t["id"] in {p["id"], first["id"]}:
        return await cb_answer(q,"Ikkinchi o‘yinchi mavjud emas.",True)
    p["action"]["second"]=t["id"]
    await safe_edit(q,f"🧲 Sizning tanlovingiz:\n\n{visible_name(g,first)} ↔ {visible_name(g,t)}",None)
    remaining=max(0,int(g.get("phase_ends_at",time.time())-time.time())-5)
    ctx.job_queue.run_once(veyron_notice_job,remaining,data={"gid":g["id"]},name=f"veyron-notice-{g['id']}-{uid}")
    persist_games(); await cb_answer(q,"Tanlov saqlandi.")


async def cb_vote(update,ctx):
    q=update.callback_query; a=q.data.split(":"); typ=a[0]; gid=a[1]; target=int(a[2]) if len(a)>2 else None
    g=next((x for x in games.values() if x["id"]==gid),None)
    if not g or g["phase"]!="voting":return await cb_answer(q,"Ovoz berish tugagan.",True)
    voter=getp(g,q.from_user.id)
    if not voter or not voter["alive"]:return await cb_answer(q,"Siz tirik emassiz.",True)
    if q.from_user.id in g["votes"]:return await cb_answer(q,"Ovozingiz allaqachon qabul qilingan.",True)
    if typ=="vote":
        t=getp(g,target)
        if not t or not t["alive"]:return await cb_answer(q,"Nishon mavjud emas.",True)
        if t["id"]==voter["id"]:return await cb_answer(q,"O‘zingizga ovoz bera olmaysiz.",True)
        g["votes"][q.from_user.id]=target; persist_games()
        await safe_edit(q,f"🗳 Sizning ovozingiz: {visible_name(g,t)}",None)
        await cb_answer(q,"Ovoz qabul qilindi.")
        try: await ctx.bot.send_message(g["chat_id"],f"🗳 {visible_mention(g,voter)} ➡️ {visible_mention(g,t)}ga ovoz berdi.",parse_mode=ParseMode.HTML)
        except TelegramError: pass
    else:
        g["votes"][q.from_user.id]=None; persist_games()
        await safe_edit(q,"⏭ Ovoz bermaslik tanlandi.",None)
        await cb_answer(q,"Ovoz bermaslik tanlandi.")
        try: await ctx.bot.send_message(g["chat_id"],f"🗳 {visible_mention(g,voter)} ovoz bermaslikni tanladi.",parse_mode=ParseMode.HTML)
        except TelegramError: pass


async def cb_af(update,ctx):
    q=update.callback_query; parts=q.data.split(":")
    if len(parts)!=5: return await cb_answer(q,"Bu qaror mavjud emas.",True)
    _,gid,afid,attid,decision=parts
    g=next((x for x in games.values() if x.get("id")==gid),None)
    if not g or q.from_user.id!=int(afid) or g.get("phase") not in {"night","afsungar"}: return await cb_answer(q,"Bu qaror mavjud emas.",True)
    a=getp(g,int(attid)); af=getp(g,int(afid))
    if not af or not a or not af.get("alive") or af.get("role")!="Afsungar": return await cb_answer(q,"O‘yinchi topilmadi.",True)
    if int(attid) not in af.get("afsungar_decisions",{}): return await cb_answer(q,"Bu hujum topilmadi.",True)
    if af["afsungar_decisions"].get(int(attid)) is not None: return await cb_answer(q,"Qaror allaqachon tanlangan.",True)
    af["afsungar_decisions"][int(attid)]=decision
    await safe_edit(q,("🕊️ Kechirish" if decision=="forgive" else "☠️ O‘ldirish")+" tanlandi. Natija tongda qo‘llanadi.",None); await cb_answer(q,"Qaror saqlandi.")


async def cb_folbin_msg(update,ctx):
    q=update.callback_query; a=q.data.split(":")
    if a[0]=="cancel_f": return await safe_edit(q,"❌ Xabar bekor qilindi.",None)
    if len(a)!=4: return await cb_answer(q,"Xabar mavjud emas.",True)
    _,gid,target,result=a
    g=next((x for x in games.values() if x.get("id")==gid),None)
    if not g or q.from_user.id not in [p["id"] for p in g.get("players",{}).values() if p.get("role")=="Komissar Katani"]:
        return await cb_answer(q,"Bu xabar siz uchun emas.",True)
    p=getp(g,int(target))
    if not p: return await cb_answer(q,"O‘yinchi topilmadi.",True)
    await safe_edit(q,f"🧿 Folbin yarim tunda o‘z sehrini ishga soldi va {mention(p)}ning {result} ekanini aniqladi.",None)


async def cmd_stop(update,ctx):
    if update.effective_chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}:return
    if not is_bot_admin(update.effective_user.id):
        member=await ctx.bot.get_chat_member(update.effective_chat.id,update.effective_user.id)
        if member.status not in {"administrator","creator"}:
            return await update.message.reply_text("❌ Bu buyruq faqat guruh adminlari uchun.")
    g=games.get(update.effective_chat.id)
    if not g or g.get("phase") in {"ended","cancelled"}: return await update.message.reply_text("ℹ️ Faol o‘yin yo‘q.")
    cancel_game(g); await unpin_lobby(ctx.bot,g); await update.message.reply_text("🛑 O‘yin admin tomonidan to‘xtatildi.")

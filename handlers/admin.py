"""Admin commands and admin panel."""

import asyncio
import html
import time
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType

from config import ADMIN_ID, EMOJI
from keyboards.admin_keyboard import admin_menu_markup
from models.admin_data import _blocked_user, _role_from_text, admin_log
from models.database import db
from models.users import get_user, inv
from utils.state import cancel_game, games, persist_games
from utils.telegram_utils import cb_answer, safe_edit


def _admin_only(update):
    return bool(update.effective_user and update.effective_user.id == ADMIN_ID)


def _target_id(update):
    if getattr(update,'message',None) and update.message.reply_to_message and update.message.reply_to_message.from_user:
        return update.message.reply_to_message.from_user.id
    parts=(update.message.text or '').split() if getattr(update,'message',None) else []
    if len(parts)>1 and parts[1].lstrip('-').isdigit(): return int(parts[1])
    return None


async def cmd_admin(update,ctx):
    if not _admin_only(update): return
    if update.effective_chat.type!=ChatType.PRIVATE:
        return await update.message.reply_text("⚙️ Admin paneli shaxsiy chatda ishlaydi. /admin ni botga PMda yuboring.")
    admin_log("open_panel")
    await update.message.reply_text("🛠 <b>Epic Mafia Admin Panel</b>\n\nKerakli bo‘limni tanlang:",reply_markup=admin_menu_markup())


async def admin_callback(update,ctx):
    q=update.callback_query
    if q.from_user.id!=ADMIN_ID: return await cb_answer(q,"Ruxsat yo‘q.",True)
    await cb_answer(q)
    key=q.data.split(":",1)[1]
    if key=='home': return await safe_edit(q,"🛠 <b>Epic Mafia Admin Panel</b>",admin_menu_markup())
    if key=='stats':
        con=db(); u=con.execute("SELECT COUNT(*) c FROM users").fetchone()[0]; g=len([x for x in games.values() if x.get('phase') not in {'ended','cancelled'}]); blocked_u=con.execute("SELECT COUNT(*) c FROM admin_blocked_users").fetchone()[0]; blocked_g=con.execute("SELECT COUNT(*) c FROM admin_blocked_groups").fetchone()[0]; con.close()
        return await safe_edit(q,f"📊 <b>Statistika</b>\n\n👥 Userlar: {u}\n🎮 Faol o‘yinlar: {g}\n🚫 Bloklangan userlar: {blocked_u}\n🚫 Bloklangan guruhlar: {blocked_g}",InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Orqaga',callback_data='admin:home')]]))
    if key=='users':
        return await safe_edit(q,"👥 <b>User boshqaruvi</b>\n\nID yuborish uchun quyidagi buyruqlardan foydalaning:\n/checkuser ID\n/block ID\n/unblock ID\n/bust ID",InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Orqaga',callback_data='admin:home')]]))
    if key=='groups':
        return await safe_edit(q,"🏠 <b>Guruh boshqaruvi</b>\n\n/gsearch nom\n/groups\n/gblock — joriy guruh\n/ungblock — joriy guruh\n/id — joriy chat ID",InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Orqaga',callback_data='admin:home')]]))
    if key=='games':
        lines=["🎮 <b>Faol o‘yinlar</b>",""]
        active=[g for g in games.values() if g.get('phase') not in {'ended','cancelled'}]
        if not active: lines.append("— Hozircha faol o‘yin yo‘q")
        else:
            for g in active: lines.append(f"• {html.escape(str(g.get('chat_id')))} — {g.get('mode','classic')} — {len(g.get('players',{}))} ta — {g.get('phase')}")
        return await safe_edit(q,"\n".join(lines),InlineKeyboardMarkup([[InlineKeyboardButton('🛑 Barchasini to‘xtatish',callback_data='admin:stopgames')],[InlineKeyboardButton('🔙 Orqaga',callback_data='admin:home')]]))
    if key=='stopgames':
        n=0
        for g in list(games.values()):
            if g.get('phase') not in {'ended','cancelled'}:
                cancel_game(g); n+=1
        admin_log('stop_all_games',n)
        return await safe_edit(q,f"🛑 {n} ta o‘yin to‘xtatildi.",InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Orqaga',callback_data='admin:home')]]))
    if key=='blocks':
        con=db(); bu=con.execute("SELECT user_id FROM admin_blocked_users ORDER BY created_at DESC LIMIT 50").fetchall(); bg=con.execute("SELECT chat_id,title FROM admin_blocked_groups ORDER BY created_at DESC LIMIT 50").fetchall(); con.close()
        text="🚫 <b>Bloklar</b>\n\n<b>Userlar:</b>\n"+('\n'.join(f'• {r[0]}' for r in bu) if bu else '—')+"\n\n<b>Guruhlar:</b>\n"+('\n'.join(f'• {html.escape(str(r[1] or r[0]))} ({r[0]})' for r in bg) if bg else '—')
        return await safe_edit(q,text,InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Orqaga',callback_data='admin:home')]]))
    if key=='active':
        con=db(); rows=con.execute("SELECT user_id,role FROM admin_forced_roles ORDER BY user_id").fetchall(); ar=con.execute("SELECT user_id,role FROM admin_active_roles WHERE is_active=1 ORDER BY user_id,created_at").fetchall(); con.close()
        text="🎭 <b>Aktiv rollar</b>\n\n<b>Admin majburiy rollari:</b>\n"+('\n'.join(f'• {r[0]} → {r[1]}' for r in rows) if rows else '—')+"\n\n<b>Sotib olingan:</b>\n"+('\n'.join(f'• {r[0]} → {r[1]}' for r in ar) if ar else '—')
        return await safe_edit(q,text,InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Orqaga',callback_data='admin:home')]]))
    if key=='money':
        return await safe_edit(q,"💰 <b>Valyuta / Inventar</b>\n\n/pul ID amount\n/olmos ID amount\n/coin ID amount\n/inventory ID\n/bust ID",InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Orqaga',callback_data='admin:home')]]))
    if key=='heroes':
        con=db(); rows=con.execute("SELECT user_id,name,level,ball,patron,shield FROM heroes ORDER BY level DESC LIMIT 100").fetchall(); con.close();
        text="🥷 <b>Geroylar</b>\n\n"+('\n'.join(f"• {r[0]} — {html.escape(str(r[1]))} — Lv.{r[2]} — {r[3]} ball" for r in rows) if rows else '—')
        return await safe_edit(q,text,InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Orqaga',callback_data='admin:home')]]))
    if key=='vips':
        con=db(); rows=con.execute("SELECT user_id FROM admin_vips ORDER BY created_at DESC").fetchall(); con.close(); text="🌟 <b>VIP userlar</b>\n\n"+('\n'.join(f'• {r[0]}' for r in rows) if rows else '—')+"\n\n/vip ID — qo‘shish\n/unvip ID — olib tashlash"; return await safe_edit(q,text,InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Orqaga',callback_data='admin:home')]]))
    if key=='logs':
        con=db(); rows=con.execute("SELECT action,target,created_at FROM admin_logs ORDER BY id DESC LIMIT 30").fetchall(); con.close(); text="📝 <b>Admin loglari</b>\n\n"+('\n'.join(f"• {datetime.fromtimestamp(r[2]).strftime('%d.%m %H:%M')} — {html.escape(str(r[0]))} {html.escape(str(r[1]))}" for r in rows) if rows else '—'); return await safe_edit(q,text,InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Orqaga',callback_data='admin:home')]]))
    if key=='broadcast':
        ctx.user_data['admin_state']={'kind':'broadcast'}
        return await safe_edit(q,"📢 Yuboriladigan xabarni oddiy matn qilib yuboring.\nBekor qilish: /cancel",InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Orqaga',callback_data='admin:home')]]))
    return await cb_answer(q)


async def cmd_aktiv(update,ctx):
    if not _admin_only(update) or not update.message: return
    uid=_target_id(update)
    raw=(update.message.text or '').split(maxsplit=1)
    role=_role_from_text(raw[1] if len(raw)>1 else '')
    if not uid or not role: return await update.message.reply_text("❌ Reply qiling va /aktiv <rol> yozing.\nMasalan: /aktiv Don")
    con=db(); con.execute("INSERT INTO admin_forced_roles(user_id,role,set_by,created_at) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET role=excluded.role,set_by=excluded.set_by,created_at=excluded.created_at",(uid,role,ADMIN_ID,time.time())); con.commit(); con.close(); admin_log('aktiv',f'{uid}:{role}')
    await update.message.reply_text(f"✅ {uid} uchun doimiy aktiv rol: {EMOJI.get(role,'🎭')} {role}")


async def cmd_unaktiv(update,ctx):
    if not _admin_only(update) or not update.message: return
    uid=_target_id(update)
    if not uid: return await update.message.reply_text("❌ User ID yoki reply kerak.")
    con=db(); cur=con.execute("DELETE FROM admin_forced_roles WHERE user_id=?",(uid,)); con.commit(); con.close(); admin_log('unaktiv',uid)
    await update.message.reply_text("✅ Aktiv rol olib tashlandi." if cur.rowcount else "ℹ️ Bu userda admin aktiv roli yo‘q.")


async def cmd_block(update,ctx):
    if not _admin_only(update) or not update.message: return
    uid=_target_id(update)
    if not uid: return await update.message.reply_text("❌ /block ID yoki user xabariga reply qiling.")
    con=db(); con.execute("INSERT OR REPLACE INTO admin_blocked_users(user_id,reason,created_at) VALUES(?,?,?)",(uid,'admin',time.time())); con.commit(); con.close(); admin_log('block_user',uid)
    # Remove the blocked user from current lobbies/games.
    for g in list(games.values()):
        p=g.get('players',{}).get(uid)
        if p:
            if g.get('phase')=='lobby': g['players'].pop(uid,None)
            else: p['alive']=False
    persist_games(); await update.message.reply_text("🚫 Foydalanuvchi bloklandi.")


async def cmd_unblock(update,ctx):
    if not _admin_only(update) or not update.message: return
    uid=_target_id(update)
    if not uid: return await update.message.reply_text("❌ /unblock ID yoki reply.")
    con=db(); cur=con.execute("DELETE FROM admin_blocked_users WHERE user_id=?",(uid,)); con.commit(); con.close(); admin_log('unblock_user',uid); await update.message.reply_text("🔓 Blok olib tashlandi." if cur.rowcount else "ℹ️ User bloklanmagan.")


async def cmd_gblock(update,ctx):
    if not _admin_only(update) or update.effective_chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return
    cid=update.effective_chat.id; title=update.effective_chat.title or ''
    con=db(); con.execute("INSERT OR REPLACE INTO admin_blocked_groups(chat_id,title,created_at) VALUES(?,?,?)",(cid,title,time.time())); con.commit(); con.close(); admin_log('block_group',cid)
    g=games.get(cid)
    if g: cancel_game(g)
    await update.message.reply_text("🚫 Bu guruh bloklandi. Bot bu guruhda o‘yin buyruqlariga javob bermaydi.")


async def cmd_gunblock(update,ctx):
    if not _admin_only(update) or update.effective_chat.type not in {ChatType.GROUP,ChatType.SUPERGROUP}: return
    cid=update.effective_chat.id; con=db(); cur=con.execute("DELETE FROM admin_blocked_groups WHERE chat_id=?",(cid,)); con.commit(); con.close(); admin_log('unblock_group',cid); await update.message.reply_text("🔓 Guruh blokdan chiqarildi." if cur.rowcount else "ℹ️ Guruh bloklanmagan.")


async def cmd_checkuser(update,ctx):
    if not _admin_only(update): return
    uid=_target_id(update) or ADMIN_ID; r=get_user(uid)
    if not r: return await update.message.reply_text("❌ Foydalanuvchi topilmadi.")
    con=db(); blocked=bool(con.execute("SELECT 1 FROM admin_blocked_users WHERE user_id=?",(uid,)).fetchone()); forced=con.execute("SELECT role FROM admin_forced_roles WHERE user_id=?",(uid,)).fetchone(); ar=con.execute("SELECT role FROM admin_active_roles WHERE user_id=? AND is_active=1",(uid,)).fetchall(); con.close()
    await update.message.reply_text(f"👤 <b>{html.escape(str(r['first_name'] or 'Nomsiz'))}</b>\nID: <code>{uid}</code>\n💷 {r['money']}\n💎 {r['diamonds']}\n🪙 {r['coins']}\n🎮 {r['games']}\n🏆 {r['wins']}\n🚫 Blok: {'Ha' if blocked else 'Yo‘q'}\n🎭 /aktiv: {forced[0] if forced else 'Yo‘q'}\n🃏 Faol: {', '.join(x[0] for x in ar) if ar else 'Yo‘q'}")


async def cmd_inventory(update,ctx):
    if not _admin_only(update): return
    uid=_target_id(update) or (int(ctx.args[0]) if ctx.args and ctx.args[0].isdigit() else None)
    if not uid: return await update.message.reply_text("/inventory ID")
    d=inv(uid); await update.message.reply_text("🎒 <b>Inventory</b>\n\n"+"\n".join(f"• {k}: {v}" for k,v in d.items()))


async def _give_currency(update, field, symbol):
    if not _admin_only(update): return
    parts=(update.message.text or '').split(); uid=_target_id(update)
    if not uid and len(parts)>=3 and parts[1].lstrip('-').isdigit(): uid=int(parts[1])
    if uid and len(parts)>=2 and parts[-1].lstrip('-').isdigit():
        amount=int(parts[-1])
    else:
        return await update.message.reply_text("Foydalanish: /pul ID amount yoki user xabariga reply qilib /pul amount")
    con=db(); con.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)",(uid,)); con.execute(f"UPDATE users SET {field}={field}+? WHERE user_id=?",(amount,uid)); con.commit(); con.close(); admin_log('give',f'{uid}:{field}:{amount}'); await update.message.reply_text(f"✅ {amount}{symbol} berildi.")


async def cmd_pul(update,ctx): await _give_currency(update,'money','💷')


async def cmd_olmos(update,ctx): await _give_currency(update,'diamonds','💎')


async def cmd_coin(update,ctx): await _give_currency(update,'coins','🪙')


async def cmd_bust(update,ctx):
    if not _admin_only(update): return
    uid=_target_id(update)
    if not uid: return await update.message.reply_text("/bust ID yoki reply")
    con=db(); con.execute("UPDATE users SET money=0,diamonds=0,coins=0 WHERE user_id=?",(uid,)); con.commit(); con.close(); admin_log('bust',uid); await update.message.reply_text("💥 User hisoblari 0 qilindi.")


async def cmd_vip(update,ctx,remove=False):
    if not _admin_only(update): return
    uid=_target_id(update) or (int(ctx.args[0]) if ctx.args and ctx.args[0].isdigit() else None)
    if not uid: return await update.message.reply_text("/vip ID")
    con=db()
    if remove: cur=con.execute("DELETE FROM admin_vips WHERE user_id=?",(uid,))
    else: cur=con.execute("INSERT OR IGNORE INTO admin_vips(user_id,created_at) VALUES(?,?)",(uid,time.time()))
    con.commit(); con.close(); admin_log('unvip' if remove else 'vip',uid); await update.message.reply_text("🔓 VIP olib tashlandi." if remove else "🌟 VIP berildi.")


async def cmd_unvip(update,ctx): await cmd_vip(update,ctx,True)


async def cmd_blocks(update,ctx):
    if not _admin_only(update): return
    con=db(); u=con.execute("SELECT user_id FROM admin_blocked_users ORDER BY created_at DESC").fetchall(); g=con.execute("SELECT chat_id,title FROM admin_blocked_groups ORDER BY created_at DESC").fetchall(); con.close(); await update.message.reply_text("🚫 Userlar:\n"+('\n'.join(str(x[0]) for x in u) if u else '—')+"\n\n🚫 Guruhlar:\n"+('\n'.join(f'{x[1]} ({x[0]})' for x in g) if g else '—'))


async def cmd_id(update,ctx):
    if _admin_only(update): await update.message.reply_text(f"🆔 Chat ID: <code>{update.effective_chat.id}</code>\n👤 User ID: <code>{update.effective_user.id}</code>")


async def cmd_gsearch(update,ctx):
    if not _admin_only(update): return
    q=' '.join(ctx.args or []).lower().strip()
    if not q: return await update.message.reply_text("/gsearch guruh nomi")
    con=db(); rows=con.execute("SELECT chat_id,title,username FROM admin_known_groups WHERE lower(title) LIKE ? ORDER BY title LIMIT 30",('%'+q+'%',)).fetchall(); con.close(); await update.message.reply_text("🔎 Topildi:\n\n"+('\n'.join(f"• {r[1]} — {r[0]}" for r in rows) if rows else '—'))


async def cmd_groups(update,ctx):
    if not _admin_only(update): return
    con=db(); rows=con.execute("SELECT chat_id,title,username FROM admin_known_groups ORDER BY title LIMIT 100").fetchall(); con.close(); await update.message.reply_text("🏠 <b>Guruhlar</b>\n\n"+('\n'.join(f"• {html.escape(str(r[1] or 'Nomsiz'))} — <code>{r[0]}</code>" for r in rows) if rows else '—'))


async def cmd_active_games(update,ctx):
    if not _admin_only(update): return
    rows=[g for g in games.values() if g.get('phase') not in {'ended','cancelled'}]
    await update.message.reply_text("🎮 <b>Faol o‘yinlar</b>\n\n"+('\n'.join(f"• {g['chat_id']} — {g.get('mode')} — {len(g.get('players',{}))} — {g.get('phase')}" for g in rows) if rows else '—'))


async def cmd_checkgaming(update,ctx):
    if not _admin_only(update): return
    uid=int(ctx.args[0]) if ctx.args and ctx.args[0].isdigit() else _target_id(update)
    if not uid: return await update.message.reply_text('/checkgaming ID')
    rows=[]
    for g in games.values():
        if uid in g.get('players',{}): rows.append(f"• {g['chat_id']} — {g.get('mode')} — {g.get('phase')}")
    await update.message.reply_text("🎮 User o‘ynayotgan guruhlar:\n\n"+('\n'.join(rows) if rows else '—'))


async def cmd_stopgames(update,ctx):
    if not _admin_only(update): return
    n=0
    for g in list(games.values()):
        if g.get('phase') not in {'ended','cancelled'}: cancel_game(g); n+=1
    admin_log('stop_all_games',n); await update.message.reply_text(f'🛑 {n} ta o‘yin to‘xtatildi.')


async def cmd_stats(update,ctx):
    if not _admin_only(update): return
    con=db(); row=con.execute("SELECT COUNT(*),COALESCE(SUM(games),0),COALESCE(SUM(wins),0),COALESCE(SUM(money),0),COALESCE(SUM(diamonds),0) FROM users").fetchone(); con.close(); await update.message.reply_text(f"📊 Userlar: {row[0]}\n🎮 O‘yinlar: {row[1]}\n🏆 G‘alabalar: {row[2]}\n💷 Pullar: {row[3]}\n💎 Olmos: {row[4]}")


async def cmd_top(update,ctx):
    if not _admin_only(update): return
    con=db(); rows=con.execute("SELECT first_name,user_id,wins,games,money,diamonds FROM users ORDER BY wins DESC,games DESC LIMIT 100").fetchall(); con.close(); await update.message.reply_text("🏆 <b>TOP userlar</b>\n\n"+('\n'.join(f"{i}. {html.escape(str(r[0] or 'Nomsiz'))} — {r[2]}🏆 / {r[3]}🎮 — {r[4]}💷 / {r[5]}💎" for i,r in enumerate(rows,1)) if rows else '—'))


async def cmd_heroes(update,ctx):
    if not _admin_only(update): return
    con=db(); rows=con.execute("SELECT user_id,name,level,ball FROM heroes ORDER BY level DESC LIMIT 100").fetchall(); con.close(); await update.message.reply_text("🥷 <b>Geroylar</b>\n\n"+('\n'.join(f"• {r[0]} — {html.escape(str(r[1]))} — Lv.{r[2]} — {r[3]} ball" for r in rows) if rows else '—'))


async def cmd_rgm(update,ctx):
    if not _admin_only(update): return
    uid=int(ctx.args[0]) if ctx.args and ctx.args[0].isdigit() else _target_id(update)
    if not uid: return await update.message.reply_text('/rgm ID')
    con=db(); cur=con.execute("DELETE FROM hero_market WHERE seller_id=?",(uid,)); con.commit(); con.close(); await update.message.reply_text('✅ Geroy Market e’loni olib tashlandi.' if cur.rowcount else '❌ E’lon topilmadi.')


async def cmd_broadcast(update,ctx):
    if not _admin_only(update): return
    text=(update.message.text or '').split(maxsplit=1)
    if len(text)<2:
        ctx.user_data['admin_state']={'kind':'broadcast'}; return await update.message.reply_text('📢 Xabar matnini yuboring. /cancel — bekor qilish')
    await do_broadcast(ctx.bot,text[1],update.message)


async def do_broadcast(bot,text,reply=None):
    con=db(); ids=[r[0] for r in con.execute('SELECT user_id FROM users').fetchall()]; con.close(); ok=fail=0
    for uid in ids:
        if _blocked_user(uid): continue
        try: await bot.send_message(uid,text); ok+=1
        except Exception: fail+=1
        await asyncio.sleep(0.05)
    admin_log('broadcast',f'ok={ok},fail={fail}')
    if reply: await reply.reply_text(f'📢 Broadcast tugadi.\n✅ {ok}\n❌ {fail}')


async def admin_text_handler(update,ctx):
    if not _admin_only(update) or not update.message: return
    state=ctx.user_data.get('admin_state')
    if not state: return
    text=(update.message.text or '').strip()
    if text=='/cancel': ctx.user_data.pop('admin_state',None); return await update.message.reply_text('❌ Bekor qilindi.')
    if state.get('kind')=='broadcast': ctx.user_data.pop('admin_state',None); return await do_broadcast(ctx.bot,text,update.message)


async def cmd_zapravka1(update,ctx):
    if not _admin_only(update): return
    con=db(); con.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)",(ADMIN_ID,)); con.execute("UPDATE users SET diamonds=diamonds+100 WHERE user_id=?",(ADMIN_ID,)); con.commit(); con.close(); await update.message.reply_text("✅ Sizga 100 💎 berildi!")


async def cmd_zapravka7(update,ctx):
    if not _admin_only(update): return
    con=db(); con.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)",(ADMIN_ID,)); con.execute("UPDATE users SET money=money+10000 WHERE user_id=?",(ADMIN_ID,)); con.commit(); con.close(); await update.message.reply_text("✅ Sizga 10 000 💷 berildi!")

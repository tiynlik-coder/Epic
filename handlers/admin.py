"""Admin commands and admin panel."""

import asyncio
import html
import time
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from telegram.error import TelegramError

from config import EMOJI, is_bot_admin
from keyboards.admin_keyboard import admin_menu_markup
from models.admin_data import _blocked_user, _role_from_text, active_roles_for, admin_log, forced_role
from models.database import db
from models.heroes import hero_max_shield, hero_row
from models.users import get_user, inv
from utils.state import cancel_game, games, persist_games
from utils.telegram_utils import cb_answer, safe_edit, unpin_lobby


def _admin_only(update):
    return bool(update.effective_user and is_bot_admin(update.effective_user.id))


def _target_id(update):
    if getattr(update,'message',None) and update.message.reply_to_message and update.message.reply_to_message.from_user:
        return update.message.reply_to_message.from_user.id
    parts=(update.message.text or '').split() if getattr(update,'message',None) else []
    if len(parts)>1 and parts[1].lstrip('-').isdigit(): return int(parts[1])
    return None


def _nums(text):
    return [int(x) for x in (text or '').split() if x.lstrip('-').isdigit()]


def _resolve_id_amount(update):
    """Parse (uid, amount) from reply+amount or ID+amount in any order.

    Standard: /smoney ID amount. Reply: reply + /smoney amount.
    For two numbers without reply both orders are accepted: the number
    matching a known user wins, otherwise longer (9+ digits) wins,
    otherwise first=ID, second=amount.
    """
    msg=getattr(update,'message',None)
    reply_uid=msg.reply_to_message.from_user.id if msg and msg.reply_to_message and msg.reply_to_message.from_user else None
    nums=_nums(msg.text if msg else '')
    if reply_uid:
        if not nums: return None,None
        return reply_uid,nums[0]
    if len(nums)<2: return None,None
    a,b=nums[0],nums[1]
    try:
        ea=get_user(a) is not None
        eb=get_user(b) is not None
    except Exception:
        ea=eb=False
    if ea!=eb:
        return (a,b) if ea else (b,a)
    la=len(str(abs(a))); lb=len(str(abs(b)))
    if lb>=9 and la<9: return b,a
    if la>=9 and lb<9: return a,b
    return a,b


def _display_name(uid):
    try:
        r=get_user(uid)
        if r and r['first_name']: return html.escape(str(r['first_name']))
    except Exception:
        pass
    return html.escape(str(uid))


async def _delete_cmd(update):
    try:
        if getattr(update,'message',None): await update.message.delete()
    except TelegramError:
        pass
    except Exception:
        pass


async def _ok(update,ctx,text):
    await _delete_cmd(update)
    try:
        await ctx.bot.send_message(update.effective_chat.id,text,parse_mode='HTML')
    except Exception:
        pass


async def cmd_admin(update,ctx):
    if not _admin_only(update): return
    if update.effective_chat.type!=ChatType.PRIVATE:
        return await update.message.reply_text("⚙️ Admin paneli shaxsiy chatda ishlaydi. /admin ni botga PMda yuboring.")
    admin_log("open_panel")
    await update.message.reply_text("🛠 <b>Epic Mafia Admin Panel</b>\n\nKerakli bo‘limni tanlang:",reply_markup=admin_menu_markup())


async def admin_callback(update,ctx):
    q=update.callback_query
    if not is_bot_admin(q.from_user.id): return await cb_answer(q,"Ruxsat yo‘q.",True)
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
                cancel_game(g); await unpin_lobby(ctx.bot,g); n+=1
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
    con=db(); con.execute("INSERT INTO admin_forced_roles(user_id,role,set_by,created_at) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET role=excluded.role,set_by=excluded.set_by,created_at=excluded.created_at",(uid,role,update.effective_user.id,time.time())); con.commit(); con.close(); admin_log('aktiv',f'{uid}:{role}')
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
    con=db(); con.execute("INSERT INTO admin_blocked_users(user_id,reason,created_at) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET reason=excluded.reason,created_at=excluded.created_at",(uid,'admin',time.time())); con.commit(); con.close(); admin_log('block_user',uid)
    # Remove the blocked user from current lobbies/games.
    for g in list(games.values()):
        p=g.get('players',{}).get(uid)
        if p:
            if g.get('phase')=='lobby': g['players'].pop(uid,None)
            else: p['alive']=False
    persist_games(); await _ok(update,ctx,f"{_display_name(uid)} muvaffaqiyatli bloklandi✅")


async def cmd_unblock(update,ctx):
    if not _admin_only(update) or not update.message: return
    uid=_target_id(update)
    if not uid: return await update.message.reply_text("❌ /unblock ID yoki reply.")
    con=db(); cur=con.execute("DELETE FROM admin_blocked_users WHERE user_id=?",(uid,)); con.commit(); con.close(); admin_log('unblock_user',uid)
    if cur.rowcount: await _ok(update,ctx,f"{_display_name(uid)} muvaffaqiyatli blokdan chiqarildi✅")
    else: await update.message.reply_text("ℹ️ User bloklanmagan.")


async def cmd_gblock(update,ctx):
    if not _admin_only(update) or not update.message: return
    if update.effective_chat.type in {ChatType.GROUP,ChatType.SUPERGROUP}:
        cid=update.effective_chat.id; title=update.effective_chat.title or ''
    else:
        nums=_nums(update.message.text or '')
        if not nums: return await update.message.reply_text("❌ /gblock — guruhda yuboring yoki /gblock <chat_id> yozing.")
        cid=nums[0]; title=str(cid)
    con=db(); con.execute("INSERT INTO admin_blocked_groups(chat_id,title,created_at) VALUES(?,?,?) ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title,created_at=excluded.created_at",(cid,title,time.time())); con.commit(); con.close(); admin_log('block_group',cid)
    g=games.get(cid)
    if g: cancel_game(g); await unpin_lobby(ctx.bot,g)
    await _ok(update,ctx,f"🚫 Guruh ({html.escape(str(title))}) muvaffaqiyatli bloklandi✅")


async def cmd_gunblock(update,ctx):
    if not _admin_only(update) or not update.message: return
    if update.effective_chat.type in {ChatType.GROUP,ChatType.SUPERGROUP}:
        cid=update.effective_chat.id
    else:
        nums=_nums(update.message.text or '')
        if not nums: return await update.message.reply_text("❌ /gunblock — guruhda yuboring yoki /gunblock <chat_id> yozing.")
        cid=nums[0]
    con=db(); cur=con.execute("DELETE FROM admin_blocked_groups WHERE chat_id=?",(cid,)); con.commit(); con.close(); admin_log('unblock_group',cid)
    if cur.rowcount: await _ok(update,ctx,"🔓 Guruh muvaffaqiyatli blokdan chiqarildi✅")
    else: await update.message.reply_text("ℹ️ Guruh bloklanmagan.")


async def cmd_checkuser(update,ctx):
    if not _admin_only(update): return
    uid=_target_id(update) or update.effective_user.id; r=get_user(uid)
    if not r: return await update.message.reply_text("❌ Foydalanuvchi topilmadi.")
    con=db(); blocked=bool(con.execute("SELECT 1 FROM admin_blocked_users WHERE user_id=?",(uid,)).fetchone()); forced=con.execute("SELECT role FROM admin_forced_roles WHERE user_id=?",(uid,)).fetchone(); ar=con.execute("SELECT role FROM admin_active_roles WHERE user_id=? AND is_active=1",(uid,)).fetchall(); con.close()
    await update.message.reply_text(f"👤 <b>{html.escape(str(r['first_name'] or 'Nomsiz'))}</b>\nID: <code>{uid}</code>\n💷 {r['money']}\n💎 {r['diamonds']}\n🪙 {r['coins']}\n🎮 {r['games']}\n🏆 {r['wins']}\n🚫 Blok: {'Ha' if blocked else 'Yo‘q'}\n🎭 /aktiv: {forced[0] if forced else 'Yo‘q'}\n🃏 Faol: {', '.join(x[0] for x in ar) if ar else 'Yo‘q'}")


async def cmd_inventory(update,ctx):
    if not _admin_only(update): return
    uid=_target_id(update) or (int(ctx.args[0]) if ctx.args and ctx.args[0].isdigit() else None)
    if not uid: return await update.message.reply_text("/inventory ID")
    d=inv(uid); await update.message.reply_text("🎒 <b>Inventory</b>\n\n"+"\n".join(f"• {k}: {v}" for k,v in d.items()))


async def _give_new(update,ctx,field,symbol,label):
    if not _admin_only(update) or not update.message: return
    uid,amount=_resolve_id_amount(update)
    cmd=(update.message.text or '').split(maxsplit=1)[0] if (update.message.text or '').split() else '/give'
    if not uid or amount is None or amount<=0:
        return await update.message.reply_text(f"❌ Foydalanish: {cmd} ID amount yoki user xabariga reply qilib {cmd} amount")
    con=db(); con.execute("INSERT INTO users(user_id) VALUES(?) ON CONFLICT DO NOTHING",(uid,)); con.execute(f"UPDATE users SET {field}={field}+? WHERE user_id=?",(amount,uid)); con.commit(); con.close(); admin_log('give',f'{uid}:{field}:{amount}')
    await _ok(update,ctx,f"{_display_name(uid)}ga {amount}{symbol} ({label}) muvaffaqiyatli yuborildi✅")


async def cmd_sdiamond(update,ctx): await _give_new(update,ctx,'diamonds','💎','almaz')
async def cmd_smoney(update,ctx): await _give_new(update,ctx,'money','💷','money')
async def cmd_scoin(update,ctx): await _give_new(update,ctx,'coins','🪙','coin')


async def cmd_pul(update,ctx): await _give_new(update,ctx,'money','💷','money')


async def cmd_olmos(update,ctx): await _give_new(update,ctx,'diamonds','💎','almaz')


async def cmd_coin(update,ctx): await _give_new(update,ctx,'coins','🪙','coin')


async def cmd_sgeroy(update,ctx):
    if not _admin_only(update) or not update.message: return
    uid,level=_resolve_id_amount(update)
    cmd=(update.message.text or '').split(maxsplit=1)[0] if (update.message.text or '').split() else '/sgeroy'
    if not uid or level is None:
        return await update.message.reply_text(f"❌ Foydalanish: {cmd} ID daraja yoki user xabariga reply qilib {cmd} daraja")
    if not 1<=level<=30:
        return await update.message.reply_text("❌ Geroy darajasi 1–30 oralig‘ida bo‘lishi kerak.")
    ball=(level-1)*1100; mx=hero_max_shield(level)
    con=db(); con.execute("INSERT INTO users(user_id) VALUES(?) ON CONFLICT DO NOTHING",(uid,))
    h=con.execute("SELECT user_id FROM heroes WHERE user_id=?",(uid,)).fetchone()
    if h:
        con.execute("UPDATE heroes SET level=?,ball=?,patron=10,shield=? WHERE user_id=?",(level,ball,mx,uid))
    else:
        con.execute("INSERT INTO heroes(user_id,name,level,ball,patron,shield,created_at) VALUES(?,?,?,?,?,?,?)",(uid,"Sovg‘a",level,ball,10,mx,time.time()))
    con.commit(); con.close(); admin_log('sgeroy',f'{uid}:{level}')
    await _ok(update,ctx,f"{_display_name(uid)}ga {level}-darajali Geroy muvaffaqiyatli sovg‘a qilindi✅")


async def cmd_rgeroy(update,ctx):
    if not _admin_only(update) or not update.message: return
    uid=_target_id(update)
    if not uid:
        nums=_nums(update.message.text or '')
        if nums: uid=nums[0]
    if not uid: return await update.message.reply_text("❌ /rgeroy ID yoki user xabariga reply qiling.")
    con=db(); cur=con.execute("DELETE FROM heroes WHERE user_id=?",(uid,)); con.execute("UPDATE hero_market SET active=0 WHERE seller_id=? AND active=1",(uid,)); con.commit(); con.close(); admin_log('rgeroy',uid)
    if cur.rowcount: await _ok(update,ctx,f"{_display_name(uid)}ning Geroysi muvaffaqiyatli o‘chirildi✅")
    else: await update.message.reply_text("❌ Bu foydalanuvchida Geroy mavjud emas.")


async def _bust_field(update,ctx,field,symbol,label):
    if not _admin_only(update) or not update.message: return
    uid=_target_id(update)
    if not uid:
        nums=_nums(update.message.text or '')
        if nums: uid=nums[0]
    if not uid: return await update.message.reply_text("❌ ID yoki user xabariga reply qiling.")
    con=db(); con.execute("INSERT INTO users(user_id) VALUES(?) ON CONFLICT DO NOTHING",(uid,)); con.execute(f"UPDATE users SET {field}=0 WHERE user_id=?",(uid,)); con.commit(); con.close(); admin_log('bust_'+field,uid)
    await _ok(update,ctx,f"{_display_name(uid)}ning barcha {symbol} ({label}) si muvaffaqiyatli 0 qilindi✅")


async def cmd_bust(update,ctx): await _bust_field(update,ctx,'diamonds','💎','almaz')
async def cmd_bust1(update,ctx): await _bust_field(update,ctx,'money','💷','pul')
async def cmd_bust2(update,ctx): await _bust_field(update,ctx,'coins','🪙','coin')


async def cmd_fullbust(update,ctx):
    if not _admin_only(update) or not update.message: return
    uid=_target_id(update)
    if not uid:
        nums=_nums(update.message.text or '')
        if nums: uid=nums[0]
    if not uid: return await update.message.reply_text("❌ /fullbust ID yoki user xabariga reply qiling.")
    con=db(); con.execute("INSERT INTO users(user_id) VALUES(?) ON CONFLICT DO NOTHING",(uid,))
    con.execute("UPDATE users SET money=0,diamonds=0,coins=0,wins=0,games=0,inventory='{}',protection=0,fake_document=0,hanging_protection=0,rifle=0,mask=0,supper_shield=0,active_role=0,hero_protection=0,medicine_protection=0 WHERE user_id=?",(uid,))
    con.execute("DELETE FROM heroes WHERE user_id=?",(uid,))
    con.execute("DELETE FROM admin_forced_roles WHERE user_id=?",(uid,))
    con.execute("DELETE FROM admin_active_roles WHERE user_id=?",(uid,))
    con.execute("UPDATE hero_market SET active=0 WHERE seller_id=? AND active=1",(uid,))
    con.execute("DELETE FROM admin_vips WHERE user_id=?",(uid,))
    con.commit(); con.close(); admin_log('fullbust',uid)
    await _ok(update,ctx,f"{_display_name(uid)}ning barcha hisobi muvaffaqiyatli 0 qilindi✅")


async def cmd_you(update,ctx):
    if not _admin_only(update) or not update.message: return
    uid=_target_id(update)
    if not uid:
        nums=_nums(update.message.text or '')
        if nums: uid=nums[0]
    if not uid: return await update.message.reply_text("❌ /you ID yoki user xabariga reply qiling.")
    r=get_user(uid)
    if not r: return await update.message.reply_text("❌ Foydalanuvchi topilmadi.")
    ar=active_roles_for(uid); fr=forced_role(uid); h=hero_row(uid)
    lines=[f"👤 <b>{_display_name(uid)}</b>",f"🆔 <code>{uid}</code>","",f"💷 Pul: {int(r['money'] or 0)}",f"💎 Almaz: {int(r['diamonds'] or 0)}",f"🪙 Coin: {int(r['coins'] or 0)}","",f"🎮 O‘yinlar: {int(r['games'] or 0)} | 🏆 G‘alaba: {int(r['wins'] or 0)}"]
    if h: lines.append(f"🥷 Geroy: {html.escape(str(h['name']))} — Lv.{h['level']}")
    else: lines.append("🥷 Geroy: yo‘q")
    if fr: lines.append(f"🎭 Admin roli (/aktiv): {html.escape(str(fr))}")
    if ar: lines.extend(["","🃏 Faol rollar (ishlatilmagan):"]+ [f"• {EMOJI.get(x[1],'🎭')} {html.escape(str(x[1]))}" for x in ar])
    else: lines.append("🃏 Faol rollar: yo‘q")
    await _delete_cmd(update)
    try: await ctx.bot.send_message(update.effective_chat.id,"\n".join(lines),parse_mode='HTML')
    except Exception: pass


async def cmd_vip(update,ctx,remove=False):
    if not _admin_only(update): return
    uid=_target_id(update) or (int(ctx.args[0]) if ctx.args and ctx.args[0].isdigit() else None)
    if not uid: return await update.message.reply_text("/vip ID")
    con=db()
    if remove: cur=con.execute("DELETE FROM admin_vips WHERE user_id=?",(uid,))
    else: cur=con.execute("INSERT INTO admin_vips(user_id,created_at) VALUES(?,?) ON CONFLICT DO NOTHING",(uid,time.time()))
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
        if g.get('phase') not in {'ended','cancelled'}: cancel_game(g); await unpin_lobby(ctx.bot,g); n+=1
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
    con=db(); con.execute("INSERT INTO users(user_id) VALUES(?) ON CONFLICT DO NOTHING",(update.effective_user.id,)); con.execute("UPDATE users SET diamonds=diamonds+100 WHERE user_id=?",(update.effective_user.id,)); con.commit(); con.close(); await update.message.reply_text("✅ Sizga 100 💎 berildi!")


async def cmd_zapravka7(update,ctx):
    if not _admin_only(update): return
    con=db(); con.execute("INSERT INTO users(user_id) VALUES(?) ON CONFLICT DO NOTHING",(update.effective_user.id,)); con.execute("UPDATE users SET money=money+10000 WHERE user_id=?",(update.effective_user.id,)); con.commit(); con.close(); await update.message.reply_text("✅ Sizga 10 000 💷 berildi!")

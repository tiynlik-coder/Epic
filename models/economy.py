"""Economy rules: group limits, giveaways, lotteries, chests, VIP, payments, profile swaps.

Every function that moves value does it in one transaction with guarded updates, so repeated or
concurrent button presses cannot pay out twice.
"""

import random
import time

from config import (CHEST_COOLDOWN_DAYS, DAILY_GROUP_LIMIT, GROUP_BALANCE_RESET_DAYS, GROUP_UNLIMITED_BALANCE,
                    MEGA_CHEST_PRICE, SHOP_ITEMS, PROFILE_SWAP_PRICE, SUPER_CHEST_PRICE, VIP_DAYS, VIP_PRICE)
from models.database import db
from models.users import INVENTORY_KEYS, add_balance, spend

DAY = 86400


# ---------------- VIP ----------------

def vip_until(uid):
    """None = not VIP, 0 = VIP without expiry (admin grant), else unix time it ends."""
    con=db(); r=con.execute("SELECT until FROM admin_vips WHERE user_id=?",(uid,)).fetchone(); con.close()
    if not r: return None
    until=float(r[0] or 0)
    return until if until==0 or until>time.time() else None


def is_vip(uid): return vip_until(uid) is not None


def buy_vip(uid):
    """30 days of VIP for VIP_PRICE 💎; extends an active VIP. Returns the new end time or None."""
    current=vip_until(uid)
    if current==0: return 0
    con=db()
    try:
        con.begin()
        if not spend(uid,"diamonds",VIP_PRICE,con): con.rollback(); return None
        until=max(time.time(),current or 0)+VIP_DAYS*DAY
        con.execute("INSERT INTO admin_vips(user_id,created_at,until) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET until=excluded.until",(uid,time.time(),until))
        con.commit(); return until
    finally:
        con.close()


# ---------------- CHESTS ----------------

def chest_wait(uid, kind):
    """Seconds until this chest can be opened again (0 = now)."""
    if is_vip(uid): return 0
    con=db(); r=con.execute("SELECT opened_at FROM chest_opens WHERE user_id=? AND kind=?",(uid,kind)).fetchone(); con.close()
    if not r: return 0
    return max(0,int(float(r[0])+CHEST_COOLDOWN_DAYS*DAY-time.time()))


def _mark_opened(con, uid, kind):
    con.execute("INSERT INTO chest_opens(user_id,kind,opened_at) VALUES(?,?,?) ON CONFLICT(user_id,kind) DO UPDATE SET opened_at=excluded.opened_at",(uid,kind,time.time()))


def open_super_chest(uid):
    """SUPER_CHEST_PRICE 💷 -> 2..5 💎. Returns ("ok", diamonds) | ("wait", seconds) | ("money", None)."""
    wait=chest_wait(uid,"super")
    if wait: return "wait",wait
    con=db()
    try:
        con.begin()
        if not spend(uid,"money",SUPER_CHEST_PRICE,con): con.rollback(); return "money",None
        won=random.randint(2,5)
        add_balance(uid,"diamonds",won,con); _mark_opened(con,uid,"super")
        con.commit(); return "ok",won
    finally:
        con.close()


def open_mega_chest(uid):
    """MEGA_CHEST_PRICE 💎: one chance in nine to double 💷 and 💎, otherwise both are lost.
    Returns ("double"|"bankrupt", None) | ("wait", seconds) | ("money", None)."""
    wait=chest_wait(uid,"mega")
    if wait: return "wait",wait
    con=db()
    try:
        con.begin()
        if not spend(uid,"diamonds",MEGA_CHEST_PRICE,con): con.rollback(); return "money",None
        outcome="double" if random.randrange(9)==0 else "bankrupt"
        if outcome=="double": con.execute("UPDATE users SET money=money*2, diamonds=diamonds*2 WHERE user_id=?",(uid,))
        else: con.execute("UPDATE users SET money=0, diamonds=0 WHERE user_id=?",(uid,))
        _mark_opened(con,uid,"mega")
        con.commit(); return outcome,None
    finally:
        con.close()


# ---------------- GROUPS ----------------

def group_balance(chat_id):
    con=db(); r=con.execute("SELECT balance FROM group_balance WHERE chat_id=?",(chat_id,)).fetchone(); con.close()
    return int(r[0]) if r else 0


def donate_to_group(uid, chat_id, amount):
    con=db()
    try:
        con.begin()
        if not spend(uid,"diamonds",amount,con): con.rollback(); return False
        con.execute("INSERT INTO group_balance(chat_id,balance,reset_at) VALUES(?,?,?) ON CONFLICT(chat_id) DO UPDATE SET balance=group_balance.balance+excluded.balance",(chat_id,amount,time.time()))
        con.commit(); return True
    finally:
        con.close()


def top_groups(limit=5):
    con=db(); rows=con.execute("SELECT g.chat_id,g.balance,k.title,k.username FROM group_balance g LEFT JOIN admin_known_groups k ON k.chat_id=g.chat_id WHERE g.balance>0 ORDER BY g.balance DESC LIMIT ?",(limit,)).fetchall(); con.close()
    return rows


def use_group_quota(chat_id, field, amount):
    """Groups without enough balance may move only DAILY_GROUP_LIMIT per day. True = allowed (and counted)."""
    if group_balance(chat_id)>=GROUP_UNLIMITED_BALANCE: return True
    col={"money":"moved_money","diamonds":"moved_diamonds"}[field]
    today=time.strftime("%Y-%m-%d")
    con=db()
    try:
        con.begin()
        con.execute("INSERT INTO group_balance(chat_id,reset_at,day) VALUES(?,?,?) ON CONFLICT DO NOTHING",(chat_id,time.time(),today))
        con.execute("UPDATE group_balance SET day=?,moved_money=0,moved_diamonds=0 WHERE chat_id=? AND day<>?",(today,chat_id,today))
        cur=con.execute(f"UPDATE group_balance SET {col}={col}+? WHERE chat_id=? AND {col}+?<=?",(amount,chat_id,amount,DAILY_GROUP_LIMIT[field]))
        con.commit(); return cur.rowcount==1
    finally:
        con.close()


def reset_old_group_balances():
    """Group balances last GROUP_BALANCE_RESET_DAYS; returns the chats that were reset."""
    cutoff=time.time()-GROUP_BALANCE_RESET_DAYS*DAY
    con=db()
    rows=con.execute("UPDATE group_balance SET balance=0,reset_at=? WHERE reset_at<? AND balance>0 RETURNING chat_id",(time.time(),cutoff)).fetchall()
    con.execute("UPDATE group_balance SET reset_at=? WHERE reset_at<?",(time.time(),cutoff))
    con.commit(); con.close()
    return [r[0] for r in rows]


def games_in_chat(uid, chat_id):
    con=db(); r=con.execute("SELECT COUNT(*) FROM game_results WHERE user_id=? AND chat_id=?",(uid,chat_id)).fetchone(); con.close()
    return int(r[0])


# ---------------- GIVEAWAYS ----------------
# item: "diamonds" (1 💎 per claim) or an inventory key (1 item per claim).

def create_giveaway(chat_id, creator_id, item, total):
    con=db()
    r=con.execute("INSERT INTO giveaways(chat_id,creator_id,item,total,remaining,created_at) VALUES(?,?,?,?,?,?) RETURNING id",(chat_id,creator_id,item,total,total,time.time())).fetchone()
    con.commit(); con.close()
    return int(r[0])


def set_giveaway_message(gid, message_id):
    con=db(); con.execute("UPDATE giveaways SET message_id=? WHERE id=?",(message_id,gid)); con.commit(); con.close()


def get_giveaway(gid):
    con=db(); r=con.execute("SELECT * FROM giveaways WHERE id=?",(gid,)).fetchone(); con.close(); return r


def claim_giveaway(gid, uid):
    """Returns (status, giveaway row). status: ok | gone | own | again | empty."""
    con=db()
    try:
        con.begin()
        gw=con.execute("SELECT * FROM giveaways WHERE id=?",(gid,)).fetchone()
        if not gw: con.rollback(); return "gone",None
        if gw["creator_id"]==uid: con.rollback(); return "own",gw
        if con.execute("INSERT INTO giveaway_claims(giveaway_id,user_id) VALUES(?,?) ON CONFLICT DO NOTHING",(gid,uid)).rowcount!=1:
            con.rollback(); return "again",gw
        if con.execute("UPDATE giveaways SET remaining=remaining-1 WHERE id=? AND remaining>0",(gid,)).rowcount!=1:
            con.rollback(); return "empty",gw
        con.execute("INSERT INTO users(user_id) VALUES(?) ON CONFLICT DO NOTHING",(uid,))
        if gw["item"]=="diamonds": add_balance(uid,"diamonds",1,con)
        elif gw["item"] in INVENTORY_KEYS: con.execute(f"UPDATE users SET {gw['item']}={gw['item']}+1 WHERE user_id=?",(uid,))
        con.commit()
    finally:
        con.close()
    return "ok",get_giveaway(gid)


def giveaway_claimers(gid):
    con=db(); rows=con.execute("SELECT c.user_id,u.first_name FROM giveaway_claims c LEFT JOIN users u ON u.user_id=c.user_id WHERE c.giveaway_id=?",(gid,)).fetchall(); con.close()
    return rows


# ---------------- LOTTERY (/change) ----------------

def create_lottery(chat_id, creator_id, amount):
    con=db(); r=con.execute("INSERT INTO lotteries(chat_id,creator_id,amount,created_at) VALUES(?,?,?,?) RETURNING id",(chat_id,creator_id,amount,time.time())).fetchone(); con.commit(); con.close()
    return int(r[0])


def get_lottery(lid):
    con=db(); r=con.execute("SELECT * FROM lotteries WHERE id=?",(lid,)).fetchone(); con.close(); return r


def lottery_entries(lid):
    con=db(); rows=con.execute("SELECT e.user_id,u.first_name FROM lottery_entries e LEFT JOIN users u ON u.user_id=e.user_id WHERE e.lottery_id=?",(lid,)).fetchall(); con.close()
    return rows


def join_lottery(lid, uid, limit=50):
    con=db()
    try:
        con.begin()
        lot=con.execute("SELECT creator_id FROM lotteries WHERE id=?",(lid,)).fetchone()
        if not lot: con.rollback(); return "gone"
        if lot[0]==uid: con.rollback(); return "own"
        if con.execute("SELECT COUNT(*) FROM lottery_entries WHERE lottery_id=?",(lid,)).fetchone()[0]>=limit: con.rollback(); return "full"
        if con.execute("INSERT INTO lottery_entries(lottery_id,user_id) VALUES(?,?) ON CONFLICT DO NOTHING",(lid,uid)).rowcount!=1:
            con.rollback(); return "again"
        con.commit(); return "ok"
    finally:
        con.close()


def draw_lottery(lid, uid):
    """Only the creator draws. The row is deleted first, so a lottery pays out at most once.
    Returns (status, winner id or None, amount); with no entries the creator gets the diamonds back."""
    con=db()
    try:
        con.begin()
        lot=con.execute("SELECT creator_id,amount FROM lotteries WHERE id=?",(lid,)).fetchone()
        if not lot: con.rollback(); return "gone",None,0
        if lot[0]!=uid: con.rollback(); return "not_creator",None,0
        con.execute("DELETE FROM lotteries WHERE id=?",(lid,))
        entries=[r[0] for r in con.execute("SELECT user_id FROM lottery_entries WHERE lottery_id=?",(lid,)).fetchall()]
        con.execute("DELETE FROM lottery_entries WHERE lottery_id=?",(lid,))
        winner=random.choice(entries) if entries else lot[0]
        add_balance(winner,"diamonds",lot[1],con)
        con.commit()
        return ("ok" if entries else "refunded"),winner,lot[1]
    finally:
        con.close()


# ---------------- PAYMENTS ----------------

def record_payment(invoice_id, uid, provider, diamonds, amount):
    con=db(); con.execute("INSERT INTO payments(invoice_id,user_id,provider,diamonds,amount,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT DO NOTHING",(str(invoice_id),uid,provider,diamonds,amount,time.time())); con.commit(); con.close()


def get_payment(invoice_id):
    con=db(); r=con.execute("SELECT * FROM payments WHERE invoice_id=?",(str(invoice_id),)).fetchone(); con.close(); return r


def complete_payment(invoice_id):
    """pending -> paid and credit the diamonds stored with the invoice. None if already paid/unknown."""
    con=db()
    try:
        con.begin()
        row=con.execute("UPDATE payments SET status='paid' WHERE invoice_id=? AND status='pending' RETURNING user_id,diamonds",(str(invoice_id),)).fetchone()
        if not row: con.rollback(); return None
        add_balance(row[0],"diamonds",row[1],con)
        con.commit(); return row
    finally:
        con.close()


# ---------------- PROFILE SWAP ----------------

SWAP_COLUMNS = ("money","diamonds","coins","wins","games","disabled_items")+INVENTORY_KEYS
SWAP_OFFER_TTL = 600


def offer_swap(from_id, to_id):
    con=db()
    con.execute("INSERT INTO profile_offers(from_id,to_id,created_at) VALUES(?,?,?) ON CONFLICT(from_id,to_id) DO UPDATE SET created_at=excluded.created_at",(from_id,to_id,time.time()))
    con.commit(); con.close()


def accept_swap(from_id, to_id):
    """to_id accepts from_id's recent offer: every balance, item, stat, hero, VIP and active role change hands.
    The proposer pays PROFILE_SWAP_PRICE 💎 first. Returns ok | no_offer | money."""
    con=db()
    try:
        con.begin()
        offer=con.execute("DELETE FROM profile_offers WHERE from_id=? AND to_id=? AND created_at>? RETURNING from_id",(from_id,to_id,time.time()-SWAP_OFFER_TTL)).fetchone()
        if not offer: con.rollback(); return "no_offer"
        if not spend(from_id,"diamonds",PROFILE_SWAP_PRICE,con): con.rollback(); return "money"
        con.execute("INSERT INTO users(user_id) VALUES(?) ON CONFLICT DO NOTHING",(to_id,))
        a=con.execute(f"SELECT {','.join(SWAP_COLUMNS)} FROM users WHERE user_id=?",(from_id,)).fetchone()
        b=con.execute(f"SELECT {','.join(SWAP_COLUMNS)} FROM users WHERE user_id=?",(to_id,)).fetchone()
        sets=",".join(f"{c}=?" for c in SWAP_COLUMNS)
        con.execute(f"UPDATE users SET {sets} WHERE user_id=?",(*b,from_id))
        con.execute(f"UPDATE users SET {sets} WHERE user_id=?",(*a,to_id))
        for table in ("heroes","admin_vips"):
            # Primary keys: move one owner out of the way first.
            con.execute(f"UPDATE {table} SET user_id=? WHERE user_id=?",(-from_id,from_id))
            con.execute(f"UPDATE {table} SET user_id=? WHERE user_id=?",(from_id,to_id))
            con.execute(f"UPDATE {table} SET user_id=? WHERE user_id=?",(to_id,-from_id))
        con.execute("UPDATE admin_active_roles SET user_id=CASE WHEN user_id=? THEN ? ELSE ? END WHERE user_id IN (?,?)",(from_id,to_id,from_id,from_id,to_id))
        con.execute("UPDATE hero_market SET active=0 WHERE seller_id IN (?,?) AND active=1",(from_id,to_id))
        con.commit(); return "ok"
    finally:
        con.close()


# ---------------- ITEM SWITCHES ----------------

def disabled_items(uid):
    con=db(); r=con.execute("SELECT disabled_items FROM users WHERE user_id=?",(uid,)).fetchone(); con.close()
    return {x for x in ((r[0] if r else "") or "").split(",") if x}


def toggle_item(uid, key):
    if key not in SHOP_ITEMS: return disabled_items(uid)
    off=disabled_items(uid) ^ {key}
    con=db(); con.execute("UPDATE users SET disabled_items=? WHERE user_id=?",(",".join(sorted(off)),uid)); con.commit(); con.close()
    return off

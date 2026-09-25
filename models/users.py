"""Users: balances, stats and inventory items.

Balance changes go through spend()/add_balance()/transfer(): a spend is a single guarded
UPDATE (`... WHERE money>=?`), so two concurrent requests can never overdraw an account.
"""

from models.database import db

BALANCE_FIELDS = ("money", "diamonds", "coins")
INVENTORY_KEYS = ("protection","fake_document","hanging_protection","rifle","mask","supper_shield","active_role","hero_protection","medicine_protection","killer_protection","slip_protection")


def _balance_field(field):
    if field not in BALANCE_FIELDS: raise ValueError(f"unknown balance field: {field}")
    return field


def _inventory_key(key):
    if key not in INVENTORY_KEYS: raise ValueError(f"unknown inventory item: {key}")
    return key


def ensure_user(u):
    con=db()
    con.execute("INSERT INTO users(user_id,username,first_name) VALUES(?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,first_name=excluded.first_name",
                (u.id,u.username or '',u.first_name or ''))
    con.commit(); con.close()


def ensure_user_id(uid):
    """Make sure a row exists for a bare id (admin grants to users who never pressed /start)."""
    con=db(); con.execute("INSERT INTO users(user_id) VALUES(?) ON CONFLICT DO NOTHING",(uid,)); con.commit(); con.close()


def get_user(uid):
    con=db(); r=con.execute("SELECT * FROM users WHERE user_id=?",(uid,)).fetchone(); con.close(); return r


def grant_first_start(uid):
    con=db()
    try:
        cur=con.execute("UPDATE users SET money=money+1000, first_start_granted=1 WHERE user_id=? AND first_start_granted=0",(uid,))
        con.commit(); return cur.rowcount==1
    finally:
        con.close()


def add_stats(uid, game=False, win=False):
    con=db();
    if game: con.execute("UPDATE users SET games=games+1 WHERE user_id=?",(uid,))
    if win: con.execute("UPDATE users SET wins=wins+1 WHERE user_id=?",(uid,))
    con.commit(); con.close()


def add_balance(uid, field, amount, con=None):
    own = con is None
    if own: con=db()
    con.execute(f"UPDATE users SET {_balance_field(field)}={field}+? WHERE user_id=?",(int(amount),uid))
    if own: con.commit(); con.close()


def spend(uid, field, amount, con=None):
    """Take `amount` from the balance only if it is there. Returns True when charged."""
    own = con is None
    if own: con=db()
    try:
        cur=con.execute(f"UPDATE users SET {_balance_field(field)}={field}-? WHERE user_id=? AND {field}>=?",(int(amount),uid,int(amount)))
        if own: con.commit()
        return cur.rowcount==1
    finally:
        if own: con.close()


def transfer(from_uid, to_uid, field, amount, fee=0):
    """Move `amount` to another user (sender also pays `fee`). All or nothing."""
    con=db()
    try:
        con.begin()
        if not spend(from_uid, field, amount+fee, con):
            con.rollback(); return False
        con.execute("INSERT INTO users(user_id) VALUES(?) ON CONFLICT DO NOTHING",(to_uid,))
        add_balance(to_uid, field, amount, con)
        con.commit(); return True
    except Exception:
        con.rollback(); raise
    finally:
        con.close()


def inv(uid):
    r=get_user(uid)
    if not r: return {}
    return {k:int(r[k] or 0) for k in INVENTORY_KEYS}


def set_inv(uid, d):
    values=[max(0,int(d.get(k,0))) for k in INVENTORY_KEYS]
    con=db(); con.execute("UPDATE users SET "+",".join(f"{k}=?" for k in INVENTORY_KEYS)+" WHERE user_id=?",(*values,uid)); con.commit(); con.close()


def add_item(uid, key, count=1):
    con=db(); con.execute(f"UPDATE users SET {_inventory_key(key)}={key}+? WHERE user_id=?",(int(count),uid)); con.commit(); con.close()


def buy(uid, item, cost_type, cost):
    if cost_type not in {"money", "diamonds"}: return False,"Noto‘g‘ri valyuta"
    con=db()
    try:
        cur=con.execute(f"UPDATE users SET {cost_type}={cost_type}-?, {_inventory_key(item)}={item}+1 WHERE user_id=? AND {cost_type}>=?",(cost,uid,cost))
        con.commit()
        return (True,"OK") if cur.rowcount==1 else (False,"Sizda yetarli resurs mavjud emas❌")
    finally:
        con.close()


def consume_inventory(p,key):
    con=db()
    try:
        cur=con.execute(f"UPDATE users SET {_inventory_key(key)}={key}-1 WHERE user_id=? AND {key}>0",(p["id"],))
        con.commit(); return cur.rowcount==1
    finally:
        con.close()

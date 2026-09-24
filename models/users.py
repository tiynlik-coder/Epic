"""Users: balances, stats and inventory items."""

from models.database import db


def ensure_user(u):
    con=db(); cur=con.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (u.id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users(user_id,username,first_name) VALUES(?,?,?)", (u.id,u.username or '',u.first_name or ''))
    else:
        cur.execute("UPDATE users SET username=?,first_name=? WHERE user_id=?", (u.username or '',u.first_name or '',u.id))
    con.commit(); con.close()


def get_user(uid):
    con=db(); r=con.execute("SELECT * FROM users WHERE user_id=?",(uid,)).fetchone(); con.close(); return r


def grant_first_start(uid):
    con=db()
    try:
        con.execute("BEGIN IMMEDIATE")
        cur=con.execute("UPDATE users SET money=money+1000, first_start_granted=1 WHERE user_id=? AND first_start_granted=0",(uid,))
        if cur.rowcount==1:
            con.commit(); return True
        con.rollback(); return False
    finally:
        con.close()


def add_stats(uid, game=False, win=False):
    con=db();
    if game: con.execute("UPDATE users SET games=games+1 WHERE user_id=?",(uid,))
    if win: con.execute("UPDATE users SET wins=wins+1 WHERE user_id=?",(uid,))
    con.commit(); con.close()


def inv(uid):
    r=get_user(uid)
    if not r: return {}
    keys=("protection","fake_document","hanging_protection","rifle","mask","supper_shield","active_role","hero_protection","medicine_protection")
    return {k:int(r[k] or 0) for k in keys}


def set_inv(uid, d):
    keys=("protection","fake_document","hanging_protection","rifle","mask","supper_shield","active_role","hero_protection","medicine_protection")
    values=[max(0,int(d.get(k,0))) for k in keys]
    con=db(); con.execute("UPDATE users SET "+",".join(f"{k}=?" for k in keys)+" WHERE user_id=?",(*values,uid)); con.commit(); con.close()


def buy(uid, item, cost_type, cost):
    if cost_type not in {"money", "diamonds"}: return False,"Noto‘g‘ri valyuta"
    con=db()
    try:
        con.execute("BEGIN IMMEDIATE")
        r=con.execute(f"SELECT {cost_type}, {item} FROM users WHERE user_id=?",(uid,)).fetchone()
        if not r: con.rollback(); return False,"Foydalanuvchi topilmadi"
        bal=int(r[0] or 0)
        if bal<cost: con.rollback(); return False,"Sizda yetarli resurs mavjud emas❌"
        con.execute(f"UPDATE users SET {cost_type}={cost_type}-?, {item}={item}+1 WHERE user_id=?",(cost,uid))
        con.commit(); return True,"OK"
    except Exception:
        con.rollback(); raise
    finally:
        con.close()


def consume_inventory(p,key):
    d=inv(p["id"])
    if d.get(key,0)<=0:return False
    d[key]-=1
    if d[key]<=0: d.pop(key,None)
    set_inv(p["id"],d); return True

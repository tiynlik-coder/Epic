"""Para mode partners. Each pair is stored twice (a->b and b->a) so lookups are one row."""

import time

from models.database import db


def partner_of(uid):
    con=db(); r=con.execute("SELECT partner_id FROM pairs WHERE user_id=?",(uid,)).fetchone(); con.close()
    return r[0] if r else None


def make_pair(a, b):
    """Pair two users, dissolving any pair either of them had."""
    con=db()
    try:
        con.begin()
        con.execute("DELETE FROM pairs WHERE user_id IN (?,?) OR partner_id IN (?,?)",(a,b,a,b))
        now=time.time()
        con.executemany("INSERT INTO pairs(user_id,partner_id,created_at) VALUES(?,?,?)",[(a,b,now),(b,a,now)])
        con.commit()
    finally:
        con.close()


def break_pair(uid):
    con=db(); cur=con.execute("DELETE FROM pairs WHERE user_id=? OR partner_id=?",(uid,uid)); con.commit(); con.close()
    return cur.rowcount>0

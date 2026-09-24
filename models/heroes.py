"""Hero (Geroy) records and level/damage math."""

import html
import time

from models.database import db


def hero_row(uid):
    con=db(); r=con.execute("SELECT * FROM heroes WHERE user_id=?",(uid,)).fetchone(); con.close(); return r


def ensure_hero(uid, name="Nomsiz"):
    if hero_row(uid): return
    con=db(); con.execute("INSERT INTO heroes(user_id,name,created_at) VALUES(?,?,?)",(uid,name,time.time())); con.commit(); con.close()


def hero_max_shield(level):
    return int(10 * (level / 1.2))


def hero_level(ball):
    return max(1, int(ball)//1100 + 1)


def hero_damage_range(level):
    lo=40+(level-1)*7; hi=40+level*7
    return (100,100) if lo>=100 else (lo,hi)


def hero_text(uid):
    h=hero_row(uid)
    if not h: return "🥷 <b>Geroy</b>\n\nSizda hozircha Geroy yo‘q."
    lo,hi=hero_damage_range(h["level"])
    dmg="maksimal" if lo>=100 else f"{lo}–{hi}"
    return (f"🥷 <b>Geroy:</b> {html.escape(str(h['name']))}\n\n"
            f"⭐️ <b>Daraja:</b> {h['level']}\n"
            f"👊 <b>Kuch:</b> {dmg}\n"
            f"🖤 <b>Himoya:</b> {h['shield']} / {hero_max_shield(h['level'])}\n"
            f"🩸 <b>Zaryad:</b> {h['patron']} / 10\n"
            f"☑️ <b>Ball:</b> {h['ball']}\n"
            f"⏫ <b>Keyingi daraja:</b> {h['level']+1} → {1100*h['level']} ball")

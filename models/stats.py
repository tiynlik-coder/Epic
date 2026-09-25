"""Leaderboards from game_results: rating points by chat and period."""

import time
from datetime import datetime, timedelta

from models.database import db

PERIODS = {"1": "Bugun", "7": "Shu hafta", "30": "Shu oy", "": "Umumiy"}


def period_start(period):
    """'1' = today, '7' = this week (from Monday), '30' = this month, '' = all time."""
    now=datetime.now(); day=now.replace(hour=0,minute=0,second=0,microsecond=0)
    if period=="1": return day.timestamp()
    if period=="7": return (day-timedelta(days=day.weekday())).timestamp()
    if period=="30": return day.replace(day=1).timestamp()
    return 0.0


def top_players(chat_id=None, period="", limit=10):
    where="created_at>=?"+(" AND chat_id=?" if chat_id else "")
    args=(period_start(period),)+((chat_id,) if chat_id else ())
    con=db()
    rows=con.execute(f"""SELECT r.user_id, u.first_name, SUM(r.points) pts, COUNT(*) games, SUM(r.won) wins
        FROM game_results r LEFT JOIN users u ON u.user_id=r.user_id WHERE {where}
        GROUP BY r.user_id, u.first_name ORDER BY pts DESC, wins DESC LIMIT ?""",(*args,limit)).fetchall()
    con.close(); return rows


def user_rank(uid, period=""):
    """(place, points, games) in the global rating for the period, or None when the user has not played."""
    since=period_start(period)
    con=db()
    mine=con.execute("SELECT SUM(points), COUNT(*) FROM game_results WHERE user_id=? AND created_at>=?",(uid,since)).fetchone()
    if not mine or not mine[1]: con.close(); return None
    better=con.execute("SELECT COUNT(*) FROM (SELECT user_id FROM game_results WHERE created_at>=? GROUP BY user_id HAVING SUM(points)>?) t",(since,mine[0])).fetchone()[0]
    con.close()
    return better+1,int(mine[0]),int(mine[1])


def top_groups(period="", limit=10):
    con=db()
    rows=con.execute("""SELECT r.chat_id, k.title, COUNT(DISTINCT r.game_id) games, COUNT(*) players
        FROM game_results r LEFT JOIN admin_known_groups k ON k.chat_id=r.chat_id WHERE r.created_at>=?
        GROUP BY r.chat_id, k.title ORDER BY games DESC LIMIT ?""",(period_start(period),limit)).fetchall()
    con.close(); return rows


def richest(limit=10):
    con=db(); rows=con.execute("SELECT user_id, first_name, diamonds, money FROM users ORDER BY diamonds DESC, money DESC LIMIT ?",(limit,)).fetchall(); con.close()
    return rows


def market_totals():
    con=db()
    row=con.execute("SELECT COUNT(*), COALESCE(SUM(money),0), COALESCE(SUM(diamonds),0) FROM users").fetchone()
    paid=con.execute("SELECT provider, COUNT(*), COALESCE(SUM(diamonds),0) FROM payments WHERE status='paid' GROUP BY provider").fetchall()
    games=con.execute("SELECT COUNT(DISTINCT game_id) FROM game_results WHERE created_at>=?",(time.time()-86400,)).fetchone()[0]
    con.close()
    return row,paid,games

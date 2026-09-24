"""SQLite connection and schema (created/migrated on startup)."""

import json
import sqlite3

from config import DB_FILE


def db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db(); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, username TEXT DEFAULT '', first_name TEXT DEFAULT '',
        money INTEGER DEFAULT 0, diamonds INTEGER DEFAULT 0, coins INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0, games INTEGER DEFAULT 0, inventory TEXT DEFAULT '{}',
        protection INTEGER DEFAULT 0, fake_document INTEGER DEFAULT 0, hanging_protection INTEGER DEFAULT 0,
        rifle INTEGER DEFAULT 0, mask INTEGER DEFAULT 0, supper_shield INTEGER DEFAULT 0, active_role INTEGER DEFAULT 0,
        hero_protection INTEGER DEFAULT 0, medicine_protection INTEGER DEFAULT 0, first_start_granted INTEGER DEFAULT 0
    )""")
    # Safe migrations for databases created by older Epic Mafia builds.
    existing={r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()}
    for col in ["protection","fake_document","hanging_protection","rifle","mask","supper_shield","active_role","hero_protection","medicine_protection"]:
        if col not in existing:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 0")
    # Migrate legacy JSON inventory once; the canonical inventory is now stored in dedicated columns.
    legacy_rows=cur.execute("SELECT user_id, inventory FROM users WHERE inventory IS NOT NULL AND inventory!='{}'").fetchall()
    for lr in legacy_rows:
        try: old=json.loads(lr[1] or "{}")
        except Exception: old={}
        if not old: continue
        vals={k:max(0,int(old.get(k,0))) for k in ("protection","fake_document","hanging_protection","rifle","mask","supper_shield","active_role","hero_protection","medicine_protection")}
        cur.execute("UPDATE users SET "+",".join(f"{k}=MAX({k},?)" for k in vals)+" WHERE user_id=?",(*vals.values(),lr[0]))
    cur.execute("""CREATE TABLE IF NOT EXISTS heroes(
        user_id INTEGER PRIMARY KEY, name TEXT DEFAULT 'Nomsiz', level INTEGER DEFAULT 1,
        ball INTEGER DEFAULT 0, patron INTEGER DEFAULT 10, shield INTEGER DEFAULT 0,
        created_at REAL DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS hero_market(
        id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER NOT NULL, price INTEGER NOT NULL,
        active INTEGER DEFAULT 1, created_at REAL DEFAULT 0
    )""")
    con.commit(); con.close()
    _admin_db_init()


def _admin_db_init():
    con = db()
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS admin_blocked_users(
        user_id INTEGER PRIMARY KEY, reason TEXT DEFAULT '', created_at REAL DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admin_blocked_groups(
        chat_id INTEGER PRIMARY KEY, title TEXT DEFAULT '', created_at REAL DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admin_known_groups(
        chat_id INTEGER PRIMARY KEY, title TEXT DEFAULT '', username TEXT DEFAULT '',
        type TEXT DEFAULT '', last_seen REAL DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admin_forced_roles(
        user_id INTEGER PRIMARY KEY, role TEXT NOT NULL, set_by INTEGER NOT NULL, created_at REAL DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admin_active_roles(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, role TEXT NOT NULL,
        is_active INTEGER DEFAULT 1, created_at REAL DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admin_vips(
        user_id INTEGER PRIMARY KEY, created_at REAL DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admin_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, action TEXT, target TEXT DEFAULT '', created_at REAL DEFAULT 0
    )""")
    con.commit(); con.close()

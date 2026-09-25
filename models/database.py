"""Database access and schema.

PostgreSQL is used when DATABASE_URL is set (postgresql://user:pass@host/db); otherwise a
local SQLite file (EPIC_DB_FILE). Both backends expose the same small sqlite3-like API:

    con = db()
    row = con.execute("SELECT money FROM users WHERE user_id=?", (uid,)).fetchone()
    row[0] == row["money"]
    con.begin()      # start a write transaction (BEGIN IMMEDIATE on SQLite)
    con.commit(); con.close()

Write SQL that runs on both: `?` placeholders, INSERT ... ON CONFLICT, RETURNING, and
guarded updates (`UPDATE ... WHERE money>=?` + rowcount) instead of read-then-write.
"""

import json
import sqlite3

from config import DATABASE_URL, DB_FILE

IS_PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))

if IS_PG:
    import psycopg
    from psycopg_pool import ConnectionPool
    IntegrityError = psycopg.IntegrityError
else:
    IntegrityError = sqlite3.IntegrityError


class Row(tuple):
    """Result row readable both by position and by column name (like sqlite3.Row)."""

    def __new__(cls, values, index):
        row = super().__new__(cls, values)
        row._index = index
        return row

    def __getitem__(self, key):
        if isinstance(key, str): key = self._index[key]
        return tuple.__getitem__(self, key)

    def keys(self): return list(self._index)


def _pg_row_factory(cursor):
    index = {c.name: i for i, c in enumerate(cursor.description or [])}
    return lambda values: Row(values, index)


_SQL_CACHE = {}


def _pg_sql(sql):
    out = _SQL_CACHE.get(sql)
    if out is None:
        out = _SQL_CACHE[sql] = sql.replace("%", "%%").replace("?", "%s")
    return out


_pool = None


def _pg_pool():
    global _pool
    if _pool is None:
        _pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=10, open=True)
    return _pool


class _PgConnection:
    def __init__(self):
        self._con = _pg_pool().getconn()

    def execute(self, sql, params=()):
        cur = self._con.cursor(row_factory=_pg_row_factory)
        cur.execute(_pg_sql(sql), params)
        return cur

    def executemany(self, sql, seq):
        cur = self._con.cursor()
        cur.executemany(_pg_sql(sql), seq)
        return cur

    def begin(self): pass  # psycopg opens a transaction on the first statement

    def commit(self): self._con.commit()

    def rollback(self): self._con.rollback()

    def close(self):
        if self._con is None: return
        self._con.rollback()  # drop anything left uncommitted before returning to the pool
        _pg_pool().putconn(self._con)
        self._con = None


class _SqliteConnection(sqlite3.Connection):
    def begin(self): self.execute("BEGIN IMMEDIATE")


def db():
    if IS_PG: return _PgConnection()
    con = sqlite3.connect(DB_FILE, factory=_SqliteConnection, timeout=10)
    con.row_factory = sqlite3.Row
    return con


# ---------------- SCHEMA ----------------
# BIGINT: Telegram ids do not fit into a 32-bit integer. {pk} is the auto-increment key.

_TABLES = [
    """CREATE TABLE IF NOT EXISTS users(
        user_id BIGINT PRIMARY KEY, username TEXT DEFAULT '', first_name TEXT DEFAULT '',
        money BIGINT DEFAULT 0, diamonds BIGINT DEFAULT 0, coins BIGINT DEFAULT 0,
        wins BIGINT DEFAULT 0, games BIGINT DEFAULT 0, inventory TEXT DEFAULT '{}',
        protection INTEGER DEFAULT 0, fake_document INTEGER DEFAULT 0, hanging_protection INTEGER DEFAULT 0,
        rifle INTEGER DEFAULT 0, mask INTEGER DEFAULT 0, supper_shield INTEGER DEFAULT 0, active_role INTEGER DEFAULT 0,
        hero_protection INTEGER DEFAULT 0, medicine_protection INTEGER DEFAULT 0, first_start_granted INTEGER DEFAULT 0,
        killer_protection INTEGER DEFAULT 0, slip_protection INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS heroes(
        user_id BIGINT PRIMARY KEY, name TEXT DEFAULT 'Nomsiz', level INTEGER DEFAULT 1,
        ball BIGINT DEFAULT 0, patron INTEGER DEFAULT 10, shield INTEGER DEFAULT 0,
        created_at DOUBLE PRECISION DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS hero_market(
        id {pk}, seller_id BIGINT NOT NULL, price BIGINT NOT NULL,
        active INTEGER DEFAULT 1, created_at DOUBLE PRECISION DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS admin_blocked_users(
        user_id BIGINT PRIMARY KEY, reason TEXT DEFAULT '', created_at DOUBLE PRECISION DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS admin_blocked_groups(
        chat_id BIGINT PRIMARY KEY, title TEXT DEFAULT '', created_at DOUBLE PRECISION DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS admin_known_groups(
        chat_id BIGINT PRIMARY KEY, title TEXT DEFAULT '', username TEXT DEFAULT '',
        type TEXT DEFAULT '', last_seen DOUBLE PRECISION DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS admin_forced_roles(
        user_id BIGINT PRIMARY KEY, role TEXT NOT NULL, set_by BIGINT NOT NULL, created_at DOUBLE PRECISION DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS admin_active_roles(
        id {pk}, user_id BIGINT NOT NULL, role TEXT NOT NULL,
        is_active INTEGER DEFAULT 1, created_at DOUBLE PRECISION DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS admin_vips(
        user_id BIGINT PRIMARY KEY, created_at DOUBLE PRECISION DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS admin_logs(
        id {pk}, admin_id BIGINT, action TEXT, target TEXT DEFAULT '', created_at DOUBLE PRECISION DEFAULT 0
    )""",
]

_INVENTORY_COLUMNS = ("protection","fake_document","hanging_protection","rifle","mask","supper_shield","active_role","hero_protection","medicine_protection","killer_protection","slip_protection")


def _columns(con, table):
    if IS_PG:
        rows=con.execute("SELECT column_name FROM information_schema.columns WHERE table_name=?",(table,)).fetchall()
        return {r[0] for r in rows}
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}


def init_db():
    con = db()
    pk = "BIGSERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    for ddl in _TABLES:
        con.execute(ddl.replace("{pk}", pk))
    # Databases created by older Epic Mafia builds may miss inventory columns.
    existing = _columns(con, "users")
    for col in _INVENTORY_COLUMNS:
        if col not in existing:
            con.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 0")
    if not IS_PG:
        _migrate_legacy_inventory(con)
    con.commit(); con.close()


def _migrate_legacy_inventory(con):
    """Very old SQLite builds kept the inventory as JSON; fold it into the dedicated columns."""
    rows = con.execute("SELECT user_id, inventory FROM users WHERE inventory IS NOT NULL AND inventory!='{}'").fetchall()
    for r in rows:
        try: old = json.loads(r[1] or "{}")
        except Exception: old = {}
        if not old: continue
        vals = {k: max(0, int(old.get(k, 0))) for k in _INVENTORY_COLUMNS}
        con.execute("UPDATE users SET "+",".join(f"{k}=MAX({k},?)" for k in vals)+",inventory='{}' WHERE user_id=?", (*vals.values(), r[0]))

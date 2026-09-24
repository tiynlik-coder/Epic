"""Admin data: logs, blocked users/groups, forced and purchased active roles."""

import time

from telegram.constants import ChatType

from config import ADMIN_ID, ROLES
from models.database import db


_ADMIN_ROLE_ALIASES = {}


for _r in ROLES:
    _ADMIN_ROLE_ALIASES[_r.lower().replace("’", "'")] = _r
_ADMIN_ROLE_ALIASES.update({
    "doktor": "Shifokor", "doctor": "Shifokor", "komissar": "Komissar Katani",
    "katani": "Komissar Katani", "citizen": "Tinch axoli", "fuqaro": "Tinch axoli",
})


def admin_log(action, target=""):
    try:
        con=db(); con.execute("INSERT INTO admin_logs(admin_id,action,target,created_at) VALUES(?,?,?,?)",(ADMIN_ID,action,str(target),time.time())); con.commit(); con.close()
    except Exception: pass


def _blocked_user(uid):
    con=db(); r=con.execute("SELECT 1 FROM admin_blocked_users WHERE user_id=?",(int(uid),)).fetchone(); con.close(); return bool(r)


def _blocked_group(cid):
    con=db(); r=con.execute("SELECT 1 FROM admin_blocked_groups WHERE chat_id=?",(int(cid),)).fetchone(); con.close(); return bool(r)


_GROUP_SEEN = {}


def _register_group(chat):
    if not chat or chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}: return
    # At most one DB write per group per 10 minutes instead of one per message.
    now=time.time()
    if now-_GROUP_SEEN.get(chat.id,0)<600: return
    _GROUP_SEEN[chat.id]=now
    try:
        con=db(); con.execute("INSERT INTO admin_known_groups(chat_id,title,username,type,last_seen) VALUES(?,?,?,?,?) ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title,username=excluded.username,type=excluded.type,last_seen=excluded.last_seen",(chat.id,chat.title or '',getattr(chat,'username','') or '',chat.type,time.time())); con.commit(); con.close()
    except Exception: pass


def _role_from_text(raw):
    s=(raw or '').strip().lower().replace('’',"'").replace('`',"'")
    # Allow an emoji before the role name.
    for r in sorted(ROLES, key=len, reverse=True):
        if s == r.lower().replace('’',"'") or s.endswith(" "+r.lower().replace('’',"'")):
            return r
    return _ADMIN_ROLE_ALIASES.get(s)


def forced_role(uid):
    con=db(); r=con.execute("SELECT role FROM admin_forced_roles WHERE user_id=?",(int(uid),)).fetchone(); con.close(); return r[0] if r else None


def active_roles_for(uid, only_active=True):
    con=db(); q="SELECT id,role,created_at FROM admin_active_roles WHERE user_id=?" + (" AND is_active=1" if only_active else "") + " ORDER BY created_at,id"; rows=con.execute(q,(int(uid),)).fetchall(); con.close(); return rows

"""In-memory game registry, persistence to STATE_FILE and phase timers."""

import json
import random
import time

from config import REDIS_URL, STATE_FILE, log
from models.database import db
from utils.players import NIGHT_FIELDS, PLAYER_DEFAULTS


games = {}


def _json_game(g):
    out=dict(g)
    out.pop("jobs", None)
    out["players"]={str(uid):dict(p) for uid,p in g.get("players",{}).items()}
    return out


# Running games survive restarts: kept in Redis when REDIS_URL is set, else in STATE_FILE.
REDIS_STATE_KEY = "epic_mafia:games"
_redis = None


def _redis_client():
    global _redis
    if _redis is None and REDIS_URL:
        import redis
        _redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


def persist_games():
    try:
        payload=json.dumps({str(cid):_json_game(g) for cid,g in games.items() if g.get("phase") not in {"ended","cancelled"}}, ensure_ascii=False)
        r=_redis_client()
        if r: r.set(REDIS_STATE_KEY, payload)
        else: STATE_FILE.write_text(payload, encoding="utf-8")
    except Exception:
        log.exception("state save failed")


def _read_state():
    r=_redis_client()
    if r: return r.get(REDIS_STATE_KEY)
    return STATE_FILE.read_text(encoding="utf-8") if STATE_FILE.exists() else None


def load_games_state():
    try:
        text=_read_state()
        if not text: return
        raw=json.loads(text)
        for cid,g in raw.items():
            g["chat_id"]=int(cid); g["players"]={int(uid):p for uid,p in g.get("players",{}).items()}
            g["jobs"]=[]; g.setdefault("next_ability_swaps",{}); g.setdefault("veyron_notice",[]); g.setdefault("bounties",[])
            for p in g["players"].values():
                p.setdefault("base_hp",150 if p.get("role")=="Tabib" else 100); p.setdefault("team",None)
                for k,v in {**NIGHT_FIELDS,**PLAYER_DEFAULTS}.items(): p.setdefault(k, v.copy() if isinstance(v,(list,dict)) else v)
            games[int(cid)]=g
    except Exception:
        log.exception("state restore failed")


def game_id(): return f"{time.time_ns()}-{random.randrange(1000,9999)}"


def cancel_jobs(g):
    for job in g.get("jobs",[]):
        try: job.schedule_removal()
        except Exception: pass
    g["jobs"]=[]


def schedule_phase(app,g,seconds,fn,name):
    cancel_jobs(g)
    phase=g["phase_id"]
    job=app.job_queue.run_once(fn,seconds,data={"gid":g["id"],"phase":phase},name=name)
    g["jobs"]=[job]; g["phase_ends_at"]=time.time()+seconds


def refund_bounties(g):
    """Return unclaimed bounty money to the players who posted it."""
    bounties=g.get("bounties") or []
    if not bounties: return
    con=db()
    for b in bounties:
        con.execute("UPDATE users SET money=money+? WHERE user_id=?",(int(b["amount"]),b["owner"]))
    con.commit(); con.close()
    g["bounties"]=[]


def cancel_game(g):
    cancel_jobs(g); g["phase"]="cancelled"; g["ended"]=True
    refund_bounties(g)
    if games.get(g.get("chat_id")) is g: games.pop(g["chat_id"],None)
    persist_games()


def find_game(gid):
    return next((x for x in games.values() if x.get("id")==gid), None)


def valid_job(g,job): return bool(g) and job.get("phase")==g.get("phase_id")

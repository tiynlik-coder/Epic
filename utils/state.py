"""In-memory game registry, persistence to STATE_FILE and phase timers."""

import json
import random
import time

from config import STATE_FILE, log
from models.database import db


games = {}


def _json_game(g):
    out=dict(g)
    out.pop("jobs", None)
    out["players"]={str(uid):dict(p) for uid,p in g.get("players",{}).items()}
    return out


def persist_games():
    try:
        STATE_FILE.write_text(json.dumps({str(cid):_json_game(g) for cid,g in games.items() if g.get("phase") not in {"ended","cancelled"}}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        log.exception("state save failed")


def load_games_state():
    if not STATE_FILE.exists(): return
    try:
        raw=json.loads(STATE_FILE.read_text(encoding="utf-8"))
        for cid,g in raw.items():
            g["chat_id"]=int(cid); g["players"]={int(uid):p for uid,p in g.get("players",{}).items()}
            g["jobs"]=[]; g.setdefault("next_ability_swaps",{}); g.setdefault("veyron_notice",[]); g.setdefault("bounties",[])
            for p in g["players"].values():
                p.setdefault("base_hp",150 if p.get("role")=="Tabib" else 100); p.setdefault("temp_hp_bonus",0); p.setdefault("last_attackers",[])
                p.setdefault("hero_action",None); p.setdefault("afsungar_decisions",{}); p.setdefault("advokat_result",False); p.setdefault("team",None)
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

"""Player records and how they are displayed."""

import html

from config import EMOJI, MAFIA, SOLO, TOWN, VS_TEAM_COLORS
from models.users import ensure_user


def new_player(u):
    ensure_user(u)
    return {
        "id":u.id,"name":u.first_name or u.username or str(u.id),"username":u.username or "",
        "role":None,"alive":True,"hp":100,"max_hp":100,
        "protected":False,"protection_used":False,"hanging_protected":False,"supper":False,
        "mask":False,"fake_document":False,"rifle":False,"active_role":False,
        "blocked":False,"action":None,"visits":[],"inactive":0,"resurrections":0,
        "prof_box":None,"prof_bonus":0,"manipulations":0,"kamikaze_used":False,
        "afsungar_decisions":{},"temp_ability":None,"temp_from":None,"base_hp":100,"temp_hp_bonus":0,"last_attackers":[],"team":None,
        **{k:(v.copy() if isinstance(v,list) else v) for k,v in PLAYER_DEFAULTS.items()},
    }


PLAYER_DEFAULTS = {
    # Items bought in the market (set at game start), consumed when they fire.
    "killer_protection":False,"slip_protection":False,"medicine":False,
    # Role state brought over from Baku Mafia.
    "won_flag":False,"gazab_picks":[],"robin_mistakes":0,"tulki_used":False,"pending_mode":None,
    "kimyo_shield":None,"lab_shield":None,"action_cancelled":False,
}


# Per-night fields reset in start_night; also the defaults for games restored from older state.
NIGHT_FIELDS = {"action":None,"hero_action":None,"visits":[],"blocked":False,"afsungar_decisions":{},"last_attackers":[],
                "temp_hp_bonus":0,"advokat_result":False,"koldun_hanging":False,"kimyo_shield":None,"lab_shield":None,
                "action_cancelled":False,"pending_mode":None}


def mention(p):
    try: uid=int(p.get("id"))
    except (TypeError,ValueError): uid=0
    name=str(p.get("name") or "").strip() or "O‘yinchi"
    return f'<a href="tg://user?id={uid}">{html.escape(name)}</a>'


def side(r):
    if r == "Zombi": return "Zombi"
    return "Tinch" if r in TOWN else "Mafia" if r in MAFIA else "Yakka"


def living(g): return [p for p in g["players"].values() if p["alive"]]


def getp(g,uid): return g["players"].get(uid)


def targets(g,uid=None): return [p for p in living(g) if p["id"]!=uid]


def dead_targets(g): return [p for p in g["players"].values() if not p["alive"]]


def role_label(r): return f"{EMOJI.get(r, '🧟' if r == "Zombi" else '🎭')} {r}"


def ability_role(p):
    """Role ability currently granted to the player for this night."""
    return p.get("temp_ability") or p.get("role")


def team_icon(p):
    return VS_TEAM_COLORS.get(p.get("team"), "") if p else ""


def visible_name(g, p, reveal=False):
    if not p: return "O‘yinchi"
    if g.get("mode") == "name" and not reveal:
        base = g.get("mode_value") or "1"
    else:
        base = p["name"]
    if g.get("mode") == "vs" and p.get("team"):
        return f"{team_icon(p)} {base}"
    return base


def visible_mention(g, p, reveal=False):
    if g.get("mode") == "name" and not reveal:
        base = html.escape(str(visible_name(g,p,reveal)))
        return base
    m = mention(p)
    if g.get("mode") == "vs" and p.get("team"):
        return f"{team_icon(p)} {m}"
    return m


def alive_counts(g):
    t=[p for p in living(g) if p["role"] in TOWN]; m=[p for p in living(g) if p["role"] in MAFIA]; s=[p for p in living(g) if p["role"] in SOLO]
    return t,m,s


def role_lists(g):
    if g.get("mode")=="zombie":
        # Zombie mode hides every living role; Zombies participate in the day like everyone else.
        alive=living(g)
        return ("🟢 Tinch aholi ["+str(len(alive))+"]", "", "")
    t,m,s=alive_counts(g)
    def rl(p):
        prefix = team_icon(p) + " " if g.get("mode") == "vs" and p.get("team") else ""
        return prefix + role_label(p["role"])
    return ("🟢 Tinch aholi ["+str(len(t))+"]\n"+"\n".join(rl(p) for p in t) if t else "🟢 Tinch aholi [0]",
            "🔴 Mafia ["+str(len(m))+"]\n"+"\n".join(rl(p) for p in m) if m else "🔴 Mafia [0]",
            "🟣 Yakkalar ["+str(len(s))+"]\n"+"\n".join(rl(p) for p in s) if s else "🟣 Yakkalar [0]")


def kill_player(p, reason=""):
    if not p["alive"]: return False
    p["alive"]=False; p["hp"]=0; return True

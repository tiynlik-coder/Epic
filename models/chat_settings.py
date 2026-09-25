"""Per-group game settings, stored as one JSON document per chat (missing keys = defaults)."""

import json
import time

from models.database import db

ITEM_KEYS = ("protection","fake_document","hanging_protection","killer_protection","rifle","medicine_protection",
             "slip_protection","mask","supper_shield","hero","active_role")

DEFAULTS = {
    # Phase lengths, seconds.
    "night_time": 45, "day_time": 60, "vote_time": 30, "like_time": 20, "word_time": 45,
    # "epic" = Epic role pool; classic/super/mega/real = Baku line-ups. wolf: filler of mega tables.
    "roleset": "epic", "wolf": "Bo‘ri", "banned_roles": [],
    # Market items that work in this chat.
    "items": {k: True for k in ITEM_KEYS},
    "allow_leave": True, "last_words": True, "anonymous_votes": False, "confirm_hanging": True, "afk_kick": True,
    "max_players": 50,
    # Giveaways in this chat can be claimed only after this many games here.
    "give_min_games": 0,
    # Who may use /game, /start, /stop: admin | all | owner.
    "perm_game": "admin", "perm_start": "admin", "perm_stop": "admin",
    # Who may write in the group during a game: all | players | alive | admins.
    "write_night": "all", "write_day": "all",
}

LIMITS = {"night_time": (20, 180), "day_time": (20, 300), "vote_time": (15, 120), "like_time": (10, 60),
          "word_time": (15, 120), "max_players": (4, 50), "give_min_games": (0, 100)}


def get_settings(chat_id):
    con=db(); r=con.execute("SELECT data FROM chat_settings WHERE chat_id=?",(chat_id,)).fetchone(); con.close()
    stored=json.loads(r[0]) if r and r[0] else {}
    out={k:(v.copy() if isinstance(v,(dict,list)) else v) for k,v in DEFAULTS.items()}
    for k,v in stored.items():
        if k=="items" and isinstance(v,dict): out["items"].update({i:bool(x) for i,x in v.items() if i in ITEM_KEYS})
        elif k in DEFAULTS: out[k]=v
    return out


def save_settings(chat_id, settings):
    data=json.dumps({k:settings[k] for k in DEFAULTS if k in settings},ensure_ascii=False)
    con=db()
    con.execute("INSERT INTO chat_settings(chat_id,data,updated_at) VALUES(?,?,?) ON CONFLICT(chat_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at",(chat_id,data,time.time()))
    con.commit(); con.close()


def update_setting(chat_id, key, value):
    s=get_settings(chat_id)
    if key in LIMITS:
        lo,hi=LIMITS[key]; value=max(lo,min(hi,int(value)))
    s[key]=value; save_settings(chat_id,s)
    return s


def item_enabled(settings, key):
    return settings.get("items",{}).get(key,True)

"""Settings (.env + constants) and role factions."""

import logging
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_env(path):
    """Minimal .env reader: KEY=VALUE lines; real environment variables win."""
    if not path.exists(): return
    for line in path.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k,v=line.split("=",1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env(BASE_DIR / ".env")

# ---------------- CONFIG ----------------
LOBBY_TIME = 1800
NIGHT_TIME = 30
DISCUSSION_TIME = 60
VOTING_TIME = 30
MAX_PLAYERS = 50
MIN_PLAYERS = 4
ADMIN_ID = int(os.getenv("ADMIN_ID", "5500951019"))
DB_FILE = Path(os.getenv("EPIC_DB_FILE") or BASE_DIR / "epic_mafia.db")
STATE_FILE = Path(os.getenv("EPIC_STATE_FILE") or BASE_DIR / "epic_mafia_state.json")
NIGHT_IMAGE = BASE_DIR / "epic_mafia_night.png"
EPIC_CHANNEL_URL = "https://t.me/epicmafianews"
EPIC_SUPPORT_URL = "https://t.me/insitutdan"
EPIC_PREMIUM_URL = os.getenv("EPIC_PREMIUM_URL", "").strip()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("epic_mafia")
# httpx logs every request URL, which contains the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)

# ---------------- ROLE POOL ----------------
# Fixed 30 role types. No role type is generated dynamically.
ROLES = [
    "Tinch axoli", "Shifokor", "Daydi", "Komissar Katani", "Kezuvchi",
    "Serjant", "Koldun", "Sotqin", "Folbin", "Zodagon",
    "Don", "Mafia", "Advokat", "Ayg‘oqchi", "Labarant", "Manipulyator",
    "Ruhoniy", "Undiruvchi",
    "Qotil", "Minior", "Snayper", "Suidsid", "La’natchi", "Professor",
    "Afsungar", "Kamikaze", "Veyron", "Qorbobo", "Qorbola", "Tabib",
]
TOWN = {"Tinch axoli", "Shifokor", "Daydi", "Komissar Katani", "Kezuvchi", "Serjant", "Koldun", "Sotqin", "Folbin", "Zodagon", "Kamikaze"}
MAFIA = {"Don", "Mafia", "Advokat", "Ayg‘oqchi", "Labarant", "Manipulyator", "Ruhoniy", "Undiruvchi"}
SOLO = set(ROLES) - TOWN - MAFIA
# Solo killers win only when they outlast both factions; survival solos win just by staying alive.
HOSTILE_SOLO = {"Qotil", "Minior", "Snayper", "Professor", "Qorbola"}
SURVIVAL_SOLO = {"Afsungar", "Veyron", "Tabib", "Qorbobo", "La’natchi"}
WIN_REWARD = 100

EMOJI = {
    "Tinch axoli":"👤", "Shifokor":"🧑🏻‍⚕️", "Daydi":"👁", "Komissar Katani":"🕵🏻", "Kezuvchi":"💃🏻",
    "Serjant":"👮🏻‍♂️", "Koldun":"⚡", "Sotqin":"🦎", "Folbin":"🧿", "Zodagon":"👑", "La’natchi":"🕸️",
    "Don":"🤵🏻", "Mafia":"🧑🏻‍💼", "Advokat":"⚖️", "Ayg‘oqchi":"🦇", "Labarant":"🧪", "Manipulyator":"🪄",
    "Ruhoniy":"✝️", "Undiruvchi":"💰", "Qotil":"🔪", "Minior":"👣", "Snayper":"👨🏻‍🎤",
    "Suidsid":"🪢", "Professor":"🎩", "Afsungar":"🧙‍♀️", "Kamikaze":"💥",
    "Veyron":"🧲", "Qorbobo":"🎅", "Qorbola":"🌨️", "Tabib":"🩺", "Zombi":"🧟",
}

NIGHT_ACTIVE = TOWN | MAFIA | SOLO - {"Tinch axoli", "Serjant", "Suidsid", "Kamikaze"}
# Explicitly active with no action: Professor etc are in set; Afsungar reacts only.

HARMFUL_ACTION_ROLES = {"Don", "Mafia", "Labarant", "Qotil", "Minior", "Snayper", "Professor", "Komissar Katani", "Koldun", "Qorbola"}
ORDINARY_KILLERS = {"Don", "Mafia", "Labarant", "Qotil", "Qorbola"}
SPECIAL_KILLERS = {"Snayper", "Professor", "Minior"}

VS_TEAM_COLORS = {
    "red":"🔴", "blue":"🔵", "green":"🟢", "yellow":"🟡",
    "purple":"🟣", "orange":"🟠", "black":"⚫", "white":"⚪", "brown":"🟤",
}

# ---------------- HERO PRICES ----------------
HERO_PRICE = 90                 # diamond
HERO_BALL_PRICE = 50            # diamond -> +1000 ball
HERO_SHIELD_BASE = 64            # Epic Coin + level*100
HERO_GUN_BASE = 95               # Epic Coin + level*100
HERO_NAME_PRICE = 780             # Epic Coin
HERO_PROTECTION_PRICE = 7         # diamond
HERO_MARKET_FEE = 5               # diamond

# ---------------- ACTIVE ROLE MARKET ----------------
ADMIN_ACTIVE_ROLE_PRICES = {
    "Minior": (6, "diamonds"),
    "Sotqin": (4, "diamonds"),
    "Qorbobo": (4, "diamonds"),
    "Komissar Katani": (2, "diamonds"),
    "Don": (2, "diamonds"),
    "Qotil": (2, "diamonds"),
    "Labarant": (2, "diamonds"),
    "Koldun": (2, "diamonds"),
    "Mafia": (1, "diamonds"),
    "Serjant": (1, "diamonds"),
    "Shifokor": (600, "money"),
    "Kezuvchi": (500, "money"),
    "Advokat": (500, "money"),
    "Afsungar": (500, "money"),
    "Daydi": (400, "money"),
    "Suidsid": (300, "money"),
    "Ayg‘oqchi": (300, "money"),
    "Tinch axoli": (100, "money"),
}

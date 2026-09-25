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

# ---------------- DEPLOYMENT (.env) ----------------
# Nothing deployment-specific is hard-coded: ids, channels and links all come from .env.
def _ids(value):
    return frozenset(int(x) for x in (value or "").replace(" ", "").split(",") if x.lstrip("-").isdigit())


ADMIN_IDS = _ids(os.getenv("ADMIN_IDS") or os.getenv("ADMIN_ID"))


def is_bot_admin(uid):
    return uid in ADMIN_IDS


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
REDIS_URL = os.getenv("REDIS_URL", "").strip()
DB_FILE = Path(os.getenv("EPIC_DB_FILE") or BASE_DIR / "epic_mafia.db")
STATE_FILE = Path(os.getenv("EPIC_STATE_FILE") or BASE_DIR / "epic_mafia_state.json")
NIGHT_IMAGE = BASE_DIR / "epic_mafia_night.png"
# @username of the news channel: subscribers get double rewards. Empty = no channel bonus.
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "").strip()
if CHANNEL_USERNAME and not CHANNEL_USERNAME.startswith("@"): CHANNEL_USERNAME = "@" + CHANNEL_USERNAME
EPIC_CHANNEL_URL = os.getenv("CHANNEL_URL", "").strip() or (f"https://t.me/{CHANNEL_USERNAME[1:]}" if CHANNEL_USERNAME else "")
EPIC_SUPPORT_URL = os.getenv("SUPPORT_URL", "").strip()
EPIC_PREMIUM_URL = os.getenv("PREMIUM_URL", os.getenv("EPIC_PREMIUM_URL", "")).strip()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("epic_mafia")
# httpx logs every request URL, which contains the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)

# ---------------- ROLE POOL ----------------
# Epic roles plus the roles brought over from Baku Mafia. Role names are the ids used everywhere.
ROLES = [
    # Town
    "Tinch axoli", "Shifokor", "Hamshira", "Daydi", "Komissar Katani", "Serjant", "Admiral", "Kezuvchi",
    "Koldun", "Sotqin", "Folbin", "Zodagon", "Kamikaze", "Omadli", "Janob", "Robin Gud", "Fotoparatchi",
    # Mafia
    "Don", "Mafia", "Advokat", "Ayg‘oqchi", "Labarant", "Manipulyator", "Ruhoniy", "Undiruvchi",
    "Yollanma qotil", "Jurnalist",
    # Solo
    "Qotil", "Minior", "Snayper", "Suidsid", "La’natchi", "Professor", "Sehrgar", "Afsungar", "Veyron",
    "Qorbobo", "Qorbola", "Tabib", "Aferist", "Bo‘ri", "G‘azabkor", "Joker", "Kimyogar", "Rais",
    "Konchi", "Qaroqchi", "Tulki",
]
TOWN = {"Tinch axoli", "Shifokor", "Hamshira", "Daydi", "Komissar Katani", "Serjant", "Admiral", "Kezuvchi",
        "Koldun", "Sotqin", "Folbin", "Zodagon", "Kamikaze", "Omadli", "Janob", "Robin Gud", "Fotoparatchi"}
MAFIA = {"Don", "Mafia", "Advokat", "Ayg‘oqchi", "Labarant", "Manipulyator", "Ruhoniy", "Undiruvchi",
         "Yollanma qotil", "Jurnalist"}
SOLO = set(ROLES) - TOWN - MAFIA
# Solo killers win only when they outlast both factions; survival solos win just by staying alive;
# conditional solos win (dead or alive) once their goal is met during the game (player["won_flag"]).
HOSTILE_SOLO = {"Qotil", "Snayper", "Professor", "Qorbola"}
SURVIVAL_SOLO = {"Sehrgar", "Veyron", "Tabib", "Qorbobo", "La’natchi", "Aferist", "Bo‘ri", "Kimyogar",
                 "Rais", "Konchi", "Qaroqchi", "Tulki"}
CONDITIONAL_SOLO = {"Minior", "Joker", "G‘azabkor", "Afsungar"}
WIN_REWARD = 100

EMOJI = {
    "Tinch axoli":"👤", "Shifokor":"🧑🏻‍⚕️", "Hamshira":"👩🏻‍⚕️", "Daydi":"👁", "Komissar Katani":"🕵🏻",
    "Serjant":"👮🏻‍♂️", "Admiral":"🧑🏻‍✈️", "Kezuvchi":"💃🏻", "Koldun":"⚡", "Sotqin":"🦎", "Folbin":"🧿",
    "Zodagon":"👑", "Kamikaze":"💥", "Omadli":"🤞🏼", "Janob":"🎖", "Robin Gud":"🏹", "Fotoparatchi":"📸",
    "Don":"🤵🏻", "Mafia":"🧑🏻‍💼", "Advokat":"⚖️", "Ayg‘oqchi":"🦇", "Labarant":"🧪", "Manipulyator":"🪄",
    "Ruhoniy":"✝️", "Undiruvchi":"💰", "Yollanma qotil":"🥷", "Jurnalist":"👩🏼‍💻",
    "Qotil":"🔪", "Minior":"☠️", "Snayper":"👨🏻‍🎤", "Suidsid":"🪢", "La’natchi":"🕸️", "Professor":"🎩",
    "Sehrgar":"🧙‍♀️", "Afsungar":"💣", "Veyron":"🧲", "Qorbobo":"🎅", "Qorbola":"🌨️", "Tabib":"🩺",
    "Aferist":"🤹🏻", "Bo‘ri":"🐺", "G‘azabkor":"🧌", "Joker":"🤡", "Kimyogar":"👨‍🔬", "Rais":"🤑",
    "Konchi":"👷🏻‍♂️", "Qaroqchi":"⚔️", "Tulki":"🦊", "Zombi":"🧟",
}

# Sotqin exposes these; Komissar sees these as Town.
HARMFUL_ACTION_ROLES = {"Don", "Mafia", "Labarant", "Qotil", "Minior", "Snayper", "Professor", "Komissar Katani",
                        "Koldun", "Qorbola", "Yollanma qotil", "Kimyogar", "Qaroqchi", "G‘azabkor"}
LOOKS_TOWN_TO_KOMISSAR = {"Yollanma qotil", "Joker"}
# A plain 100-damage attack. Special attackers are resolved by name in night_actions.
ORDINARY_KILLERS = {"Don", "Mafia", "Qotil", "Qorbola", "Robin Gud"}
# Nobody can kill these at night (they can still be hanged).
NIGHT_IMMUNE = {"Admiral", "Yollanma qotil"}
UNIFORM_KILLERS = ["Don", "Mafia", "Qotil", "Qorbola", "Snayper", "Professor"]

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

# ---------------- MARKET ----------------
# item: (label, currency, price). Currencies: money (💷) or diamonds (💎).
SHOP_ITEMS = {
    "fake_document": ("📃 Soxta hujjat", "money", 200),
    "protection": ("🛡 Himoya", "money", 200),
    "slip_protection": ("🪤 Sirpanishdan himoya", "money", 1000),
    "hanging_protection": ("⚖️ Osilishdan himoya", "diamonds", 2),
    "killer_protection": ("⛑️ Qotildan himoya", "diamonds", 2),
    "medicine_protection": ("💊 Doridan himoya", "diamonds", 2),
    "supper_shield": ("🔰 Supper qalqon", "diamonds", 3),
    "rifle": ("🔫 Miltiq", "diamonds", 1),
    "mask": ("🎭 Maska", "diamonds", 1),
    "hero_protection": ("🖍️ Geroydan himoya", "diamonds", HERO_PROTECTION_PRICE),
}
CURRENCY_SIGN = {"money": "💷", "diamonds": "💎", "coins": "🪙"}
# 💷 bought with 💎: (money, diamonds)
MONEY_PACKS = [(250, 1), (500, 2), (750, 3), (1000, 4), (5000, 18), (10000, 30)]
# 💎 bought with Telegram Stars: diamonds -> stars
STAR_PACKS = {1: 7, 10: 70, 30: 200, 70: 450, 250: 1300, 1000: 5000}
# Where large purchases/transfers are reported (a group id). Empty = no reports.
REPORT_CHAT_ID = int(os.getenv("REPORT_CHAT_ID")) if os.getenv("REPORT_CHAT_ID", "").lstrip("-").isdigit() else None
# @username or link of whoever sells diamonds by card manually. Empty = no button.
DIAMOND_SELLER_URL = os.getenv("DIAMOND_SELLER_URL", "").strip()

TRANSFER_FEE_MONEY = 10          # 💷 fee on /money
# Groups whose balance is below GROUP_UNLIMITED_BALANCE may move at most this much per day.
DAILY_GROUP_LIMIT = {"money": 5000, "diamonds": 50}
GROUP_UNLIMITED_BALANCE = 50
GROUP_BALANCE_RESET_DAYS = 15

SUPER_CHEST_PRICE = 5000         # 💷 -> 2..5 💎
MEGA_CHEST_PRICE = 15            # 💎 -> 1 in 9: double everything, else bankrupt
CHEST_COOLDOWN_DAYS = 30         # VIPs are not limited
VIP_PRICE = 30                   # 💎
VIP_DAYS = 30
PROFILE_SWAP_PRICE = 5           # 💎, paid by whoever proposes
MAX_GAME_MINUTES = 120           # longer games (usually a killer-less stalemate) are stopped

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
    "Sehrgar": (3, "diamonds"),
    "Daydi": (400, "money"),
    "Suidsid": (300, "money"),
    "Ayg‘oqchi": (300, "money"),
    "Tinch axoli": (100, "money"),
    "Joker": (6, "diamonds"),
    "Kimyogar": (6, "diamonds"),
    "Yollanma qotil": (5, "diamonds"),
    "Konchi": (5, "diamonds"),
    "Admiral": (4, "diamonds"),
    "Janob": (3, "diamonds"),
    "Qaroqchi": (2, "diamonds"),
    "G‘azabkor": (1, "diamonds"),
    "Aferist": (1, "diamonds"),
    "Tulki": (1, "diamonds"),
    "Fotoparatchi": (1, "diamonds"),
    "Robin Gud": (1000, "money"),
    "Afsungar": (500, "money"),
    "Bo‘ri": (500, "money"),
    "Jurnalist": (500, "money"),
    "Hamshira": (400, "money"),
    "Rais": (400, "money"),
    "Omadli": (250, "money"),
}

EPIC MAFIA — Telegram bot (python-telegram-bot 22, PostgreSQL + Redis, polling)

Ishga tushirish
  pip install -r requirements.txt
  cp .env.example .env      va qiymatlarni to'ldiring
  python bot.py              (eski `python main.py` ham ishlaydi)

Testlar
  python -m unittest discover tests      (vaqtinchalik SQLite bazada ishlaydi)
  EPIC_TEST_DATABASE_URL=postgresql://... python -m unittest discover tests   (Postgres'da)

.env sozlamalari (to'liq ro'yxat: .env.example). Kodda hech qanday ID yoki kanal yozilmagan.
  BOT_TOKEN          — bot tokeni (majburiy)
  ADMIN_IDS          — bot adminlari, vergul bilan
  DATABASE_URL       — postgresql://user:parol@host:5432/db  (bo'sh = SQLite fayl)
  REDIS_URL          — redis://localhost:6379/0  (bo'sh = o'yin holati JSON faylda)
  CHANNEL_USERNAME   — @kanal: obunachilarga 2x mukofot (bo'sh = bonus yo'q)
  CHANNEL_URL, SUPPORT_URL, PREMIUM_URL — tugmalar havolalari
  EPIC_DB_FILE, EPIC_STATE_FILE — SQLite / JSON fayllar yo'li

Tuzilish (raqamlar — qatorlar soni)

Epic/
├── bot.py                   88  ← kirish nuqtasi: ilova, buyruqlar menyusi, davriy vazifalar, polling
├── config.py               202  ← .env, rollar va taraflar, do'kon narxlari, paketlar
├── .env.example                 ← barcha sozlamalar namunasi
│
├── handlers/                    ← Telegram buyruq va tugmalarini qabul qiladi
│   ├── __init__.py         263  ← handlerlarni ulash tartibi (guard'lar birinchi)
│   ├── game.py             493  ← o'yin buyruqlari, tungi harakat, ovoz, 👍/👎, /leave, /tep
│   ├── game_chat.py         56  ← so'nggi so'z, tungi jamoa chati, guruhda yozish qoidasi
│   ├── settings.py         134  ← /settings: guruh sozlamalari menyusi
│   ├── economy.py          424  ← o'tkazmalar, giveaway, lotereya, sandiq, VIP, Stars to'lovi
│   ├── stats.py             79  ← /top, /gtop, /boylar, reyting
│   ├── pairs.py             49  ← /para, /mypara, /dpara
│   ├── other_handlers.py   170  ← /start, profil, do'kon, menyu
│   ├── admin.py            466  ← admin buyruqlari va panel
│   ├── geroy_handlers.py   148  ← geroy tizimi
│   └── errors.py             6
│
├── middlewares/block_guard.py   ← bloklangan user/guruhni hamma handlerdan oldin to'xtatadi
│
├── models/                      ← baza (PostgreSQL yoki SQLite)
│   ├── database.py         237  ← ulanish, jadvallar, migratsiyalar
│   ├── users.py            123  ← balans (atomar spend/transfer), inventar
│   ├── economy.py          315  ← guruh balansi, giveaway, lotereya, sandiq, VIP, to'lov, profil almashish
│   ├── chat_settings.py     58  ← guruh sozlamalari (standart qiymatlar)
│   ├── stats.py             60  ← reytinglar (game_results)
│   ├── pairs.py, heroes.py, admin_data.py
│
├── utils/                       ← ASOSIY MANTIQ
│   ├── game_logic.py       494  ← fazalar: start → tun → (Sehrgar) → kun → ovoz → (👍/👎) → ... → tugash
│   ├── night_actions.py    621  ← tungi harakatlar: bosqichma-bosqich, bitta hit() orqali hujumlar
│   ├── role_tables.py      136  ← classic/super/mega/real rol tartiblari (Baku)
│   ├── game_roles.py       115  ← rol taqsimlash (Epic aralash yoki jadval), faol/majburiy rollar
│   ├── victory.py           95  ← g'alaba: taraflar, yakkalar, real, para, vs, zombie
│   ├── lobby.py            200  ← lobbi, qo'shilish, limitlar
│   ├── permissions.py       35  ← guruh adminlari (kesh), ruxsat darajalari
│   ├── state.py            106  ← xotiradagi o'yinlar, Redis/JSON'ga saqlash, taymerlar
│   ├── game_loop.py         52  ← restartdan keyin taymerlarni tiklash
│   ├── players.py, profile.py, texts.py, telegram_utils.py, maintenance.py
│
├── keyboards/                   ← tugmalar
└── tests/                       ← 56 ta test: rollar, kun, iqtisodiyot, reyting (SQLite va Postgres)

Rejimlar: /game (oddiy), /ngame <nik>, /ugame, /zgame, /vsgame 2–9, /pgame (para).
Rollar to'plami (/settings): Epic aralash yoki Baku classic / super / mega / real.

O'yinchi buyruqlari: /start, /profile, /leave, /money N, /give N, /sgive ID N, /gsend N, /ginfo,
/send N, /ghimoya /gqotil /govoz /gdori /gslip /ggeroy /gmiltiq N, /change N, /para, /mypara, /dpara,
/tgeroy, /top[1|7|30], /gtop[1|7|30], /boylar, /bounty.
Guruh adminlari: /settings, /stop, /tep N, /modes.
Bot adminlari (ADMIN_IDS): /admin, /block, /unblock, /gblock, /ungblock, /aktiv, /unaktiv, /pul, /olmos, /coin,
/bust, /fullbust, /gbust, /checkuser, /inventory, /stats, /tchat, /eboylar, /broadcast, /stopgames, /vip ...
Bloklangan userlarga bot umuman javob bermaydi; bloklangan guruhda o'yin buyruqlari ishlamaydi.

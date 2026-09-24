EPIC MAFIA — Telegram bot (python-telegram-bot 22, SQLite, polling)

Ishga tushirish
  pip install -r requirements.txt
  .env fayliga:  BOT_TOKEN=123456:ABC...
  python bot.py              (eski `python main.py` ham ishlaydi)

Testlar
  python -m unittest discover tests      (vaqtinchalik bazada ishlaydi)

.env sozlamalari (ixtiyoriy)
  BOT_TOKEN          — bot tokeni (majburiy)
  ADMIN_ID           — bot egasi (standart: 5500951019)
  EPIC_PREMIUM_URL   — "Premium guruhlar" tugmasi havolasi
  EPIC_DB_FILE, EPIC_STATE_FILE — baza / o'yin holati fayllari yo'li

Tuzilish (raqamlar — qatorlar soni)

Epic/
├── bot.py                   88  ← kirish nuqtasi: ilova, buyruqlar menyusi, polling
├── config.py               110  ← .env, sozlamalar, rollar va fraksiyalar, narxlar
├── main.py                   5  ← eski kirish nuqtasi (bot.py ni chaqiradi)
├── epic_mafia.db                ← SQLite baza
├── epic_mafia_state.json        ← restartdan keyin tiklanadigan o'yinlar
│
├── handlers/                    ← Telegram buyruq va tugmalarini qabul qiladi
│   ├── __init__.py         164  ← handlerlarni ulash tartibi (guard'lar birinchi)
│   ├── errors.py             6  ← global xato ushlagich
│   ├── other_handlers.py   152  ← /start, profil, do'kon, menyu
│   ├── game.py             345  ← o'yin buyruqlari, tungi harakat va ovoz tugmalari
│   ├── admin.py            301  ← admin buyruqlari va panel
│   └── geroy_handlers.py   144  ← geroy tizimi
│
├── middlewares/
│   └── block_guard.py       27  ← bloklangan user/guruhni hamma handlerdan oldin to'xtatadi
│
├── models/                      ← baza
│   ├── database.py          77  ← ulanish, jadvallar, migratsiyalar
│   ├── users.py             74  ← balans, statistika, inventar
│   ├── heroes.py            42  ← geroy yozuvlari va daraja hisobi
│   └── admin_data.py        64  ← loglar, bloklar, majburiy/sotib olingan rollar
│
├── utils/                       ← ASOSIY MANTIQ
│   ├── game_logic.py       239  ← fazalar sikli: start → tun → kun → ovoz → ... → tugash
│   ├── night_actions.py    434  ← tungi harakatlarni taklif qilish va tongda hal qilish
│   ├── lobby.py            170  ← lobbi yaratish, qo'shilish, yopish
│   ├── game_loop.py         30  ← restartdan keyin taymerlarni tiklash
│   ├── game_roles.py        99  ← rollarni taqsimlash
│   ├── victory.py           59  ← g'alaba shartlari
│   ├── players.py           98  ← o'yinchi yozuvi va ko'rinishi
│   ├── state.py             82  ← xotiradagi o'yinlar, saqlash, taymerlar
│   ├── profile.py           59  ← profil matni
│   ├── telegram_utils.py    90  ← xavfsiz edit/send, kanal a'zoligi
│   └── texts.py             79  ← rol tavsiflari va boshqa matnlar
│
├── keyboards/
│   ├── main_keyboard.py     22  ← /start menyusi
│   ├── user_keyboards.py    71  ← profil, do'kon, rollar, geroy
│   ├── game_keyboard.py     29  ← lobbi, nishon tanlash, modelar
│   └── admin_keyboard.py    14
│
└── tests/test_game.py           ← g'alaba, inventar, bounty, mukofot, handlerlar

Bog'liqlik yo'nalishi (aylanma import yo'q):
  config → models → utils (state/players → victory/night_actions → game_logic → lobby → game_loop)
         → keyboards → handlers → bot.py

Admin: /admin (shaxsiy chatda), /block, /unblock, /gblock, /ungblock, /aktiv, /unaktiv,
/pul, /olmos, /coin, /bust, /checkuser, /inventory, /stats, /top, /broadcast, /stopgames, /vip ...
Bloklangan userlarga bot umuman javob bermaydi; bloklangan guruhda o'yin buyruqlari ishlamaydi.

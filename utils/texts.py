"""Static user-facing texts."""

import html

from config import EMOJI


ROLE_INTRO = {
    "Tinch axoli": "Siz Tinch aholi tarafdasiz. Maxsus tungi harakatingiz yo‘q. Maqsadingiz — tirik qolib, Tinch aholi g‘alabasiga yordam berish.",
    "Shifokor": "Siz Tinch aholi tarafdasiz. Har tun bir o‘yinchini davolab, uni oddiy hujumdan saqlashga harakat qilasiz.",
    "Daydi": "Siz Tinch aholi tarafdasiz. Har tun bir uyni kuzatib, u yerga kelgan mehmonlarni aniqlaysiz.",
    "Komissar Katani": "Siz Tinch aholi tarafdasiz. Har tun tekshirish yoki nishonga olishdan birini tanlaysiz.",
    "Kezuvchi": "Siz Tinch aholi tarafdasiz. Har tun bir o‘yinchini kuzatib, uning tungi harakatini bloklaysiz.",
    "Serjant": "Siz Tinch aholi tarafdasiz. Komissar Katani o‘lsa, siz Komissar Kataniga aylanasiz va uning vazifalarini davom ettirasiz.",
    "Koldun": "Siz Tinch aholi tarafdasiz. Har tun bir o‘yinchini tanlaysiz: Tinch aholi bo‘lsa, kunduzgi osilishdan himoya qilasiz; boshqa taraf bo‘lsa, unga chaqmoq hujumi qilasiz.",
    "Sotqin": "Siz Tinch aholi tarafdasiz. Har tun bir o‘yinchini tekshirasiz. Zararli faoliyat aniqlansa, tongda bu haqda ma’lumot ochiladi.",
    "Folbin": "Siz Tinch aholi tarafdasiz. Har tun bir o‘yinchining qaysi tarafga mansubligini aniqlaysiz.",
    "Zodagon": "Siz Tinch aholi tarafdasiz. Har tun bir o‘yinchini tanlaysiz: tanlovingizga qarab unga yashirin tarzda tasodifiy pul beriladi.",
    "Don": "Siz Mafia tarafdasiz. Mafia jamoasining asosiy tungi nishonini belgilaysiz.",
    "Mafia": "Siz Mafia tarafdasiz. Mafia jamoasining tungi hujumida qatnashasiz.",
    "Advokat": "Siz Mafia tarafdasiz. Har tun bir o‘yinchini himoya qilib, ayrim tekshiruvlarning natijasini o‘zgartira olasiz.",
    "Ayg‘oqchi": "Siz Mafia tarafdasiz. Har tun tanlangan o‘yinchi haqida yashirin ma’lumot to‘playsiz.",
    "Labarant": "Siz Mafia tarafdasiz. Har tun o‘ziga xos hujum/ta’sir qobiliyatingizdan foydalanasiz.",
    "Manipulyator": "Siz Mafia tarafdasiz. Har tun boshqa o‘yinchining harakatini o‘zgartirishga urinishingiz mumkin.",
    "Ruhoniy": "Siz Mafia tarafdasiz. Tunda o‘lgan o‘yinchini qaytarishga urinishingiz mumkin. Sizda cheklangan miqdorda qayta tiriltirish imkoniyati bor.",
    "Undiruvchi": "Siz Mafia tarafdasiz. Har tun tanlangan o‘yinchidan pul undirishga harakat qilasiz.",
    "Qotil": "Siz Yakka tarafdasiz. Har tun bir o‘yinchini nishonga olib, uni o‘ldirishga harakat qilasiz.",
    "Minior": "Siz Yakka tarafdasiz. Siz portlovchi hujumga ega bo‘lgan maxsus rol sifatida tunda nishon tanlaysiz.",
    "Snayper": "Siz Yakka tarafdasiz. Sizning maxsus o‘qingiz ayrim oddiy himoyalardan ta’sirlanmaydi.",
    "Suidsid": "Siz Yakka tarafdasiz. Faqat kunduzgi ovoz berishda osilganingizda g‘alaba qozonasiz.",
    "La’natchi": "Siz Yakka tarafdasiz. Har tun bir o‘yinchini la’natlaysiz; agar u o‘sha tun haqiqiy o‘ldirishga sabab bo‘lsa, la’nat ta’sir qiladi.",
    "Professor": "Siz Yakka tarafdasiz. Har tun maxsus yo‘llardan birini tanlaysiz; o‘lim qutisini tanlash alohida xavfli ta’sirga ega.",
    "Afsungar": "Siz hech bir tarafga bo‘ysunmaysiz. Tunda sizga hujum qilinsa, hujum qilganlarning taqdirini o‘zingiz hal qilasiz. Maqsadingiz — tirik qolish.",
    "Kamikaze": "Siz Tinch aholi tarafdasiz. Sizni o‘ldirgan hujumchiga qarshi o‘ziga xos qasos imkoniyatingiz bor. Shartlar bajarilsa, mustaqil ravishda ham g‘alaba qozonasiz.",
    "Veyron": "Siz Yakka tarafdasiz. Har tun ikki o‘yinchini tanlab, ularning qobiliyatlarini keyingi tun uchun almashtirasiz. Rollari va taraflari o‘zgarmaydi.",
    "Qorbobo": "Siz Yakka tarafdasiz. Har tun bir tirik o‘yinchiga bot tasodifiy tanlagan sovg‘ani berasiz.",
    "Qorbola": "Siz Yakka tarafdasiz. Har tun bir o‘yinchini tanlab, unga Qorbo‘ron yuborib o‘ldirishga harakat qilasiz.",
    "Tabib": "Siz Yakka tarafdasiz. Har tun bir o‘yinchini tanlab, unga shu tun uchun +50 HP berasiz. Maqsadingiz — tirik qolish.",
}


START_PRIVATE_TEXT = (
    "<b>Salom! 👋</b>\n\n"
    "Men Epic mafiyaning rasmiy botiman. Do‘stlaringiz bilan mafiya o‘ynash uchun "
    "meni guruhingizga qo‘shing va <b>50 kishilik o‘yindan zavqlaning! 🎭</b>\n\n"
    "Meni <b>admin</b> qilganingizdan so‘ng o‘yinni boshlashingiz mumkin."
)


MARKET_TEXT = (
    "🛒 <b>Nima sotib olamiz?</b>\n\n"
    "📃 <b>Soxta Hujjat</b>\nKimdir sizning rolingizni tekshirmoqchi bo‘lsa, soxta hujjatlar yordam berishi mumkin. Har o‘yinda 1 ta sarflanadi.\n\n"
    "🛡 <b>Himoya</b>\nBir marta hayotingizni saqlab qoladi.\n\n"
    "⚖️ <b>Osilishdan himoya</b>\nKun davomida sizni osishga hukm qilishsa, bir marta qutqaradi.\n\n"
    "🔰 <b>Supper qalqon</b>\nTungi hujumlardan himoyalanishga yordam beradi.\n\n"
    "🔫 <b>Miltiq</b>\nTungi hujumingiz nishonning oddiy 🛡 Himoyasini teshib o‘tadi (Supper qalqonni emas). Har otishda 1 ta sarflanadi.\n\n"
    "🎭 <b>Maska</b>\nBuni olsangiz, Daydi sizni tanib olishda niqoblangan rolni ko‘radi. Har o‘yinda 1 ta sarflanadi.\n\n"
    "🎭 <b>Faol rol</b>\nKeyingi o‘yin uchun faol rol olish imkonini beradi.\n\n"
    "📊 <b>Statistikani nollash</b>\nG‘alaba va o‘yinlar statistikasini 0 ga tushiradi."
)


def roles_menu_text():
    return "🎭 <b>Rollar ro‘yxati:</b>\n\nKerakli rolni tanlang:"


def role_detail_text(role):
    # Role emoji is kept exactly from the canonical/old Epic Mafia role mapping.
    intro = ROLE_INTRO.get(role, "Bu rolning maxsus qobiliyati o‘yin davomida ishlaydi.")
    return f"{EMOJI.get(role, '🎭')} <b>{html.escape(role)}</b>\n\n{intro}"


def mode_detail(mode):
    texts={
      "name":"🏷️ <b>Name mode</b>\n\nBu modeni tanlasangiz, o‘yindagi hamma ishtirokchining ismlari bir xil bo‘lib qoladi.",
      "uniform":"🎭 <b>Uniform mode</b>\n\nBu modeni tanlasangiz, hammaga random tarzda bir xil killer rol beriladi. O‘yinda faqat 1 o‘yinchi tirik qolguncha davom etadi va oxirgi tirik o‘yinchi g‘olib bo‘ladi.",
      "zombie":"🧟 <b>Zombie mode</b>\n\nButun o‘yin uchun bitta Zombi bo‘ladi. Har tun u bitta tirik o‘yinchini tanlaydi. Tanlangan o‘yinchi tongdan 5 soniya oldin Zombi bo‘lgani haqida shaxsiy xabar oladi va keyingi tundan Zombi tarafida o‘ynaydi. O‘yin Zombilar yoki qolganlar tomonlaridan biri tugaguncha davom etadi.",
      "vs":"⚔️ <b>VS mode</b>\n\nYangi VS tizimida 2–9 ta jamoa bo‘ladi. Jamoalar ranglar bilan belgilanadi. O‘yinchilar shaxsiy chatdagi rang tugmasi orqali jamoa tanlaydi va lobby davomida jamoasini almashtira oladi. Faqat bitta jamoa tirik qolsa, shu jamoa g‘olib bo‘ladi.\n\n▶️ Boshlash: <code>/vsgame 2</code> yoki <code>/vsgame3</code>"}
    return texts[mode]

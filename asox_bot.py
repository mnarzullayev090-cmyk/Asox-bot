import os
import json
import asyncio
import logging
import fcntl
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, BotCommand, BotCommandScopeChat
from telegram.error import Conflict
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters, PicklePersistence

import aiohttp
from aiohttp import web

logger = logging.getLogger(__name__)

USERS_FILE = "/home/muxa/users.json"
PROMOTIONS_FILE = "/home/muxa/promotions.json"
SELLERS_FILE = "/home/muxa/sellers.json"
SELLER_WHITELIST_FILE = "/home/muxa/seller_whitelist.json"
REQUEST_COUNTER_FILE = "/home/muxa/request_counter.json"
REQUESTS_LOG_FILE = "/home/muxa/requests_log.json"

def atomic_write_json(path, data, **dump_kwargs):
    """Faylni qulf (flock) ostida vaqtinchalik faylga yozib, keyin atomik almashtiradi —
    parallel yozishda yoki jarayon qulab tushganda fayl buzilib qolmasligi uchun."""
    lock_path = path + ".lock"
    with open(lock_path, "a+") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            tmp_path = path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(data, f, **dump_kwargs)
            os.replace(tmp_path, path)
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)

def load_promotions():
    try:
        with open(PROMOTIONS_FILE, "r") as f:
            promos = json.load(f)
        today = date.today()
        active = [p for p in promos if date.fromisoformat(p["end_date"]) >= today]
        if len(active) != len(promos):
            save_promotions(active)
        return active
    except Exception:
        return []

def save_promotions(promos):
    atomic_write_json(PROMOTIONS_FILE, promos, ensure_ascii=False, indent=2)

def build_aksiya_text(lang):
    promos = load_promotions()
    today = date.today()

    if lang == "uz":
        header = "🔥 *Aksiyalar va chegirmalar*\n\n🎉 Hozirgi maxsus takliflar:\n\n"
        footer = "\n\n📲 Buyurtma berish uchun saytga o'ting:"
        date_label = "⏳ *Aksiya tugash sanasi:* "
        no_promos = "😔 Hozirda faol aksiyalar yo'q."
    elif lang == "ru":
        header = "🔥 *Акции и скидки*\n\n🎉 Текущие специальные предложения:\n\n"
        footer = "\n\n📲 Перейдите на сайт для заказа:"
        date_label = "⏳ *Акция до:* "
        no_promos = "😔 Сейчас нет активных акций."
    else:
        header = "🔥 *Promotions and discounts*\n\n🎉 Current special offers:\n\n"
        footer = "\n\n📲 Visit the website to order:"
        date_label = "⏳ *Promotion until:* "
        no_promos = "😔 No active promotions at the moment."

    if not promos:
        return no_promos

    lines = []
    grouped = {}
    for p in promos:
        end = p.get("end_date", "")
        grouped.setdefault(end, []).append(p)

    for end_date, items in grouped.items():
        for p in items:
            lines.append(f"{p['emoji']} *{p['name']}* — {p['discount']}")
        lines.append(f"{date_label}{end_date}\n")

    return header + "\n".join(lines) + footer

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_user(user_id, name, phone):
    users = load_users()
    existing = users.get(str(user_id), {})
    users[str(user_id)] = {"name": name, "phone": phone, "lang": existing.get("lang", "uz")}
    atomic_write_json(USERS_FILE, users, ensure_ascii=False)

def save_lang(user_id, lang):
    users = load_users()
    if str(user_id) in users:
        users[str(user_id)]["lang"] = lang
    else:
        users[str(user_id)] = {"name": "", "phone": "", "lang": lang}
    atomic_write_json(USERS_FILE, users, ensure_ascii=False)

def get_user(user_id):
    return load_users().get(str(user_id))

def load_sellers():
    try:
        with open(SELLERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_seller(user_id, name, phone, username):
    sellers = load_sellers()
    sellers[str(user_id)] = {
        "name": name,
        "phone": phone,
        "username": username,
        "registered_at": datetime.now().isoformat(),
    }
    atomic_write_json(SELLERS_FILE, sellers, ensure_ascii=False, indent=2)

def normalize_phone(phone):
    return "".join(ch for ch in phone if ch.isdigit())[-9:]

def get_seller(user_id):
    return load_sellers().get(str(user_id))

def find_seller_by_phone(phone):
    target = normalize_phone(phone)
    if not target:
        return None
    for uid, data in load_sellers().items():
        if normalize_phone(data.get("phone", "")) == target:
            return uid, data
    return None

def is_valid_phone(phone):
    digits = "".join(ch for ch in phone if ch.isdigit())
    return 7 <= len(digits) <= 15

def load_seller_whitelist():
    try:
        with open(SELLER_WHITELIST_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def is_phone_whitelisted(phone):
    target = normalize_phone(phone or "")
    if not target:
        return False
    return any(normalize_phone(p) == target for p in load_seller_whitelist())

def next_request_id():
    lock_path = REQUEST_COUNTER_FILE + ".lock"
    with open(lock_path, "a+") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            try:
                with open(REQUEST_COUNTER_FILE, "r") as f:
                    n = json.load(f).get("counter", 0)
            except Exception:
                n = 0
            n += 1
            tmp_path = REQUEST_COUNTER_FILE + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump({"counter": n}, f)
            os.replace(tmp_path, REQUEST_COUNTER_FILE)
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)
    return f"A{1000 + n}"

def log_request(request_id, req_type, user, summary):
    entry = {
        "id": request_id,
        "type": req_type,
        "user_id": user.id,
        "name": user.full_name or "",
        "summary": (summary or "")[:150],
        "created_at": datetime.now().isoformat(),
    }
    lock_path = REQUESTS_LOG_FILE + ".lock"
    with open(lock_path, "a+") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            try:
                with open(REQUESTS_LOG_FILE, "r") as f:
                    log = json.load(f)
            except Exception:
                log = []
            log.append(entry)
            log = log[-1000:]
            tmp_path = REQUESTS_LOG_FILE + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(log, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, REQUESTS_LOG_FILE)
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")
ADMIN_IDS = [int(os.getenv("ADMIN_ID")), int(os.getenv("ADMIN_ID2"))]
ORDER_API_KEY = os.getenv("ORDER_API_KEY", "")
ORDER_API_PORT = int(os.getenv("ORDER_API_PORT", "8088"))

ASK_NAME, ASK_PHONE, DESIGN_CHOOSE, DESIGN_PHOTO = range(4)
SELLER_REQUEST_COOLDOWN = timedelta(hours=6)

TEXTS = {
    "uz": {
        "welcome": (
            "👋 Assalomu alaykum!\n"
            "🛒 *ASOX Market* botiga xush kelibsiz!\n\n"
            "Quyidagi bo'limlardan birini tanlang:"
        ),
        "about": (
            "ℹ️ *ASOX Market haqida*\n\n"
            "ASOX Market — O'zbekistondagi premium e-commerce platformasi.\n\n"
            "✅ *Bizning xizmatlarimiz:*\n"
            "🎨 Shaxsiy dizayn studiyasi\n"
            "🖨 Poligraf marketplace\n"
            "📹 Jonli efirlar (Live shopping)\n"
            "🤖 AI yordamchi\n"
            "🔒 Xavfsiz to'lov (Click, Payme, Uzcard, Humo)\n\n"
            "📲 Ilovani yuklab oling va birinchi buyurtmaga chegirma oling!"
        ),
        "catalog_title": "📦 *Mahsulotlar katalogi*\n\nKategoriyani tanlang:",
        "clothes_title": (
            "👕 *Kiyimlar*\n\n"
            "O'z dizayningiz bilan bezatilgan kiyimlar:\n\n"
            "👕 T-shirt\n"
            "🧥 Hoodie\n"
            "🥻 Polo ko'ylak\n"
            "🩳 Shorts\n"
            "🧦 Paypoq\n"
            "🧤 Qo'lqop\n"
            "🏃 Sport kiyim\n"
            "🎽 Forma\n\n"
            "🌐 Batafsil ma'lumot uchun saytga o'ting:"
        ),
        "gifts_title": (
            "🎁 *Sovg'alar*\n\n"
            "Yaqinlaringizga maxsus sovg'alar:\n\n"
            "☕ Krujka\n"
            "🧴 Termos\n"
            "🛏 Yostiq\n"
            "🖼 Poster\n"
            "🖼 Canvas\n"
            "🗓 Kalendar\n"
            "📒 Daftar\n"
            "🎀 Sovg'a to'plami\n\n"
            "🌐 Batafsil ma'lumot uchun saytga o'ting:"
        ),
        "accessories_title": (
            "📱 *Aksessuarlar*\n\n"
            "Shaxsiy dizaynli aksessuarlar:\n\n"
            "📱 Telefon qopqog'i\n"
            "🎒 Ryukzak\n"
            "👜 Sumka\n"
            "🧢 Kepka\n"
            "⌚ Soat qayishi\n"
            "🖱 Sichqoncha gilami\n\n"
            "🌐 Batafsil ma'lumot uchun saytga o'ting:"
        ),
        "design_title": (
            "🎨 *Dizayn mahsulotlari*\n\n"
            "O'z rasmingiz yoki logotipingizni quyidagi mahsulotlarga joylashtiring:\n\n"
            "👕 T-shirt\n"
            "🧥 Hoodie\n"
            "☕ Mug (Krujka)\n"
            "🖼 Poster\n"
            "🖼 Canvas\n"
            "🛏 Yostiq\n"
            "🧴 Termos\n"
            "🏃 Sport kiyim\n\n"
            "➕ Va yana 40+ mahsulot!\n\n"
            "🌐 Batafsil ma'lumot uchun saytga o'ting:"
        ),
        "print_title": (
            "🖨 *Print xizmatlari*\n\n"
            "O'zbekistondagi sertifikatlangan poligraf ustalarini toping:\n\n"
            "🔵 UV print — Qattiq yuzalar\n"
            "🟡 DTF — To'qimachilik\n"
            "🟢 DTG — To'g'ridan-to'g'ri mato\n"
            "🟠 Sublimatsiya — Foto sifat\n"
            "🔴 Eco-solvent — Bannerlar\n"
            "⚪ 3D print — Hajmli mahsulotlar\n"
            "🔶 Lazer — O'yma va kesish\n"
            "🔷 CNC — Aniq ishlov\n\n"
            "🌐 Usta topish uchun saytga o'ting:"
        ),
        "aksiya": (
            "🔥 *Aksiyalar va chegirmalar*\n\n"
            "🎉 Hozirgi maxsus takliflar:\n\n"
            "👕 *T-shirt* — 20% chegirma\n"
            "🧥 *Hoodie* — 15% chegirma\n"
            "☕ *Krujka* — 2 ta olsang 1 tasi bepul\n"
            "🎒 *Ryukzak* — 25% chegirma\n"
            "🖼 *Poster + Canvas* — To'plamda 30% arzon\n\n"
            "⏳ *Aksiya muddati:* 2026-yil 31-iyulgacha\n\n"
            "📲 Buyurtma berish uchun saytga o'ting:"
        ),
        "contact": (
            "📞 *Aloqa*\n\n"
            "📲 Asosiy: +998 90 009 00 38\n"
            "📲 Zaxira: +998 90 657 81 45\n\n"
            "📱 Telegram: @asoxmarket\n"
            "📸 Instagram: [asox.uz](https://www.instagram.com/asox.uz?igsh=MWxibzN1aW52bXo5)\n"
            "▶️ YouTube: @asoxmarket\n"
            "🌐 Sayt: https://asox.uz/"
        ),
        "btn_about": "🎨 O'z dizayningizni baham ko'ring",
        "btn_design_add": "➕ Dizayn qo'shish",
        "btn_catalog": "📦 Mahsulotlar katalogi",
        "btn_aksiya": "🔥 Aksiyalar",
        "btn_contact": "📞 Aloqa",
        "btn_site": "🌐 Saytga o'tish",
        "btn_clothes": "👕 Kiyimlar",
        "btn_gifts": "🎁 Sovg'alar",
        "btn_accessories": "📱 Aksessuarlar",
        "btn_design": "🎨 Dizayn mahsulotlari",
        "btn_print": "🖨 Print xizmatlari",
        "btn_back": "⬅️ Orqaga",
        "btn_lang": "🌐 Tilni o'zgartirish | Сменить язык",
        "btn_izoh": "📝 Izoh qo'shish",
        "izoh_prompt": (
            "📝 *Izoh yoki qo'shimcha ma'lumot*\n\n"
            "Qanday mahsulot olmoqchi ekanligingizni batafsil yozing:\n"
            "_(Masalan: rang, o'lcham, miqdor, maxsus talab va hokazo)_"
        ),
        "izoh_done": "✅ *Izohingiz qabul qilindi!*",
        "izoh_cancel_btn": "❌ Bekor qilish",
        "izoh_skip_btn": "⏭ O'tkazib yuborish",
        "btn_taklif": "💡 Taklif kiritish",
        "taklif_prompt": "💡 *Taklifingizni yozing*\n\nQanday mahsulot yoki xizmat qo'shishimizni xohlaysiz?",
        "taklif_done": "✅ *Taklifingiz qabul qilindi! Rahmat!*\n\n🔖 So'rov raqami: #{id}",
        "taklif_cancel_btn": "❌ Bekor qilish",
        "btn_faq_ask": "✍️ Savol berish",
        "faq_ask_prompt": "✍️ *Savolingizni yozing*\n\nMutaxassislarimiz tez orada javob beradi:",
        "faq_ask_done": "✅ *Savolingiz qabul qilindi! Tez orada javob beramiz.*\n\n🔖 So'rov raqami: #{id}",
        "faq_ask_cancel_btn": "❌ Bekor qilish",
        "narx_prompt": "💰 *Dizayningizga qancha narx bera olasiz?*\n\nFaqat raqam kiriting _(masalan: 50, 100, 200)_\nBot avtomatik so'mga o'tkazadi.",
        "narx_invalid": "❗ Iltimos, faqat raqam kiriting _(masalan: 50, 100, 200)_",
        "narx_skip_btn": "⏭ O'tkazib yuborish",
        "narx_done": "✅ *Rahmat! Ma'lumotlaringiz qabul qilindi.*\n\nTez orada mutaxassislarimiz siz bilan bog'lanadi!\n\n🔖 So'rov raqami: #{id}",
        "lang_changed": "✅ Til o'zgartirildi!",
        "btn_faq": "❓ FAQ",
        "faq_title": "❓ *FAQ*\n\nQaysi bo'lim sizni qiziqtiradi?",
        "faq_btn_order": "💳 Buyurtma va to'lov",
        "faq_btn_product": "📦 Mahsulot",
        "faq_btn_tech": "🖨 Texnik savollar",
        "faq_btn_general": "🏢 Umumiy",
        "faq_order": (
            "💳 *Buyurtma va to'lov*\n\n"
            "❓ *Qanday to'lov usullari bor?*\n"
            "✅ Click, Payme, Uzcard, Humo orqali to'lash mumkin.\n\n"
            "❓ *Buyurtma qancha kunda tayyor bo'ladi?*\n"
            "✅ Oddiy buyurtma 3-5 ish kuni, dizaynli mahsulot 5-7 ish kuni.\n\n"
            "❓ *Yetkazib berish bormi? Narxi qancha?*\n"
            "✅ Ha, butun O'zbekiston bo'ylab yetkazib beramiz. Narxi manzilga qarab belgilanadi.\n\n"
            "❓ *Buyurtmani bekor qilish mumkinmi?*\n"
            "✅ Ishlab chiqarish boshlangunga qadar bekor qilish mumkin. Operatorga murojaat qiling."
        ),
        "faq_product": (
            "📦 *Mahsulot haqida*\n\n"
            "❓ *Dizayn uchun rasm qanday formatda bo'lishi kerak?*\n"
            "✅ PNG yoki JPG formatida, minimal 300 DPI sifatida.\n\n"
            "❓ *O'lchamlar qanday?*\n"
            "✅ XS dan 3XL gacha. Buyurtma berishda o'lcham jadvalini yuboramiz.\n\n"
            "❓ *Mahsulot yoqmasa qaytarish mumkinmi?*\n"
            "✅ Ishlab chiqarishdagi nuqson bo'lsa 100% qaytaramiz. Shaxsiy dizaynlar qaytarilmaydi.\n\n"
            "❓ *Minimal buyurtma miqdori bormi?*\n"
            "✅ Bitta mahsulotdan buyurtma berish mumkin. Ulgurji uchun alohida narxlar mavjud."
        ),
        "faq_tech": (
            "🖨 *Texnik savollar*\n\n"
            "❓ *Dizayn tayyorlanish muddati qancha?*\n"
            "✅ Dizayn tasdiqlash 1-2 soat, ishlab chiqarish 3-7 ish kuni.\n\n"
            "❓ *Rasm sifati past bo'lsa nima bo'ladi?*\n"
            "✅ Mutaxassislarimiz siz bilan bog'lanib, yaxshiroq rasm so'raydi.\n\n"
            "❓ *Qaysi bosma usuli yaxshiroq?*\n"
            "✅ Kiyim uchun DTF yoki DTG, qattiq yuzalar uchun UV print, foto sifat uchun sublimatsiya tavsiya etiladi."
        ),
        "faq_general": (
            "🏢 *Umumiy savollar*\n\n"
            "❓ *Ofis manzili qayerda?*\n"
            "✅ Toshkent sh. Manzilni operatordan so'rashingiz mumkin: @asoxmarket\n\n"
            "❓ *Ish vaqti qachon?*\n"
            "✅ Dushanba — Shanba: 09:00 — 18:00\n\n"
            "❓ *Ulgurji buyurtma bo'ladimi?*\n"
            "✅ Ha! 10 dona va undan ko'p buyurtmada maxsus chegirmalar mavjud. Operatorga murojaat qiling."
        ),
        "design_custom_title": (
            "🎨 *O'z dizayningizni joylashtiring*\n\n"
            "Quyidagi mahsulotlardan birini tanlang —\n"
            "ustiga o'z rasmingiz yoki logotipingizni joylashtiramiz!"
        ),
        "design_photo_prompt": "📸 *{product}* tanlandi!\n\nIltimos, dizayn rasmingizni yuboring 👇\n_(Galereyadan tanlang)_",
        "design_done": (
            "✅ *Rahmat! Dizayningiz qabul qilindi.*\n\n"
            "📦 Mahsulot: {product}\n\n"
            "🕐 Tez orada mutaxassislarimiz siz bilan bog'lanadi!"
        ),
        "design_cancel_btn": "❌ Bekor qilish",
        "btn_sotuvchi": "🏪 Men sotuvchiman",
        "sotuvchi_not_yet": (
            "⏳ *Siz hali sotuvchi emassiz.*\n\n"
            "So'rovingiz administratorga yuborildi. Tasdiqlangach, sizga xabar beramiz.\n\n"
            "🔖 So'rov raqami: #{id}"
        ),
        "sotuvchi_prompt": (
            "🏪 *Sotuvchi sifatida ro'yxatdan o'tish*\n\n"
            "Telefon raqamingizni kiriting yoki quyidagi tugma orqali ulashing _(masalan: +998901234567)_:"
        ),
        "sotuvchi_invalid": "❗ Iltimos, to'g'ri telefon raqam kiriting _(masalan: +998901234567)_",
        "sotuvchi_done": (
            "✅ *Siz sotuvchi sifatida ro'yxatdan o'tdingiz!*\n\n"
            "Asox.uz orqali sizga zakaz kelganda shu botdan xabar beramiz."
        ),
        "sotuvchi_cancel_btn": "❌ Bekor qilish",
        "sotuvchi_cancelled": "❌ Bekor qilindi.",
        "btn_sotuvchi_contact": "📱 Kontaktni ulashish",
        "sotuvchi_panel_title": (
            "🏪 *Siz sotuvchi sifatida ro'yxatdan o'tgansiz*\n\n"
            "📞 Telefon: {phone}\n\n"
            "Asox.uz orqali sizga zakaz kelganda shu botdan xabar beramiz."
        ),
        "btn_sotuvchi_update": "🔄 Telefonni yangilash",
    },
    "ru": {
        "welcome": (
            "👋 Добро пожаловать!\n"
            "🛒 Добро пожаловать в бот *ASOX Market*!\n\n"
            "Выберите один из разделов:"
        ),
        "about": (
            "ℹ️ *Об ASOX Market*\n\n"
            "ASOX Market — премиум e-commerce платформа в Узбекистане.\n\n"
            "✅ *Наши услуги:*\n"
            "🎨 Студия личного дизайна\n"
            "🖨 Маркетплейс полиграфии\n"
            "📹 Прямые эфиры (Live shopping)\n"
            "🤖 AI-помощник\n"
            "🔒 Безопасная оплата (Click, Payme, Uzcard, Humo)\n\n"
            "📲 Скачайте приложение и получите скидку на первый заказ!"
        ),
        "catalog_title": "📦 *Каталог товаров*\n\nВыберите категорию:",
        "clothes_title": (
            "👕 *Одежда*\n\n"
            "Одежда с вашим уникальным дизайном:\n\n"
            "👕 Футболка\n"
            "🧥 Худи\n"
            "🥻 Поло\n"
            "🩳 Шорты\n"
            "🧦 Носки\n"
            "🧤 Перчатки\n"
            "🏃 Спортивная одежда\n"
            "🎽 Форма\n\n"
            "🌐 Перейдите на сайт для подробной информации:"
        ),
        "gifts_title": (
            "🎁 *Подарки*\n\n"
            "Особенные подарки для близких:\n\n"
            "☕ Кружка\n"
            "🧴 Термос\n"
            "🛏 Подушка\n"
            "🖼 Постер\n"
            "🖼 Холст\n"
            "🗓 Календарь\n"
            "📒 Блокнот\n"
            "🎀 Подарочный набор\n\n"
            "🌐 Перейдите на сайт для подробной информации:"
        ),
        "accessories_title": (
            "📱 *Аксессуары*\n\n"
            "Аксессуары с персональным дизайном:\n\n"
            "📱 Чехол для телефона\n"
            "🎒 Рюкзак\n"
            "👜 Сумка\n"
            "🧢 Кепка\n"
            "⌚ Ремешок для часов\n"
            "🖱 Коврик для мыши\n\n"
            "🌐 Перейдите на сайт для подробной информации:"
        ),
        "design_title": (
            "🎨 *Дизайн товары*\n\n"
            "Разместите своё изображение или логотип на следующих товарах:\n\n"
            "👕 Футболка\n"
            "🧥 Худи\n"
            "☕ Кружка\n"
            "🖼 Постер\n"
            "🖼 Холст\n"
            "🛏 Подушка\n"
            "🧴 Термос\n"
            "🏃 Спортивная одежда\n\n"
            "➕ И ещё 40+ товаров!\n\n"
            "🌐 Перейдите на сайт для подробной информации:"
        ),
        "print_title": (
            "🖨 *Услуги печати*\n\n"
            "Найдите сертифицированных полиграфистов в Узбекистане:\n\n"
            "🔵 UV печать — Твёрдые поверхности\n"
            "🟡 DTF — Текстиль\n"
            "🟢 DTG — Прямо на ткань\n"
            "🟠 Сублимация — Фото качество\n"
            "🔴 Eco-solvent — Баннеры\n"
            "⚪ 3D печать — Объёмные изделия\n"
            "🔶 Лазер — Гравировка и резка\n"
            "🔷 ЧПУ — Точная обработка\n\n"
            "🌐 Перейдите на сайт чтобы найти мастера:"
        ),
        "aksiya": (
            "🔥 *Акции и скидки*\n\n"
            "🎉 Текущие специальные предложения:\n\n"
            "👕 *Футболка* — скидка 20%\n"
            "🧥 *Худи* — скидка 15%\n"
            "☕ *Кружка* — купи 2, получи 1 бесплатно\n"
            "🎒 *Рюкзак* — скидка 25%\n"
            "🖼 *Постер + Холст* — в наборе на 30% дешевле\n\n"
            "⏳ *Срок акции:* до 31 июля 2026 года\n\n"
            "📲 Перейдите на сайт для заказа:"
        ),
        "contact": (
            "📞 *Контакты*\n\n"
            "📲 Основной: +998 90 009 00 38\n"
            "📲 Запасной: +998 90 657 81 45\n\n"
            "📱 Telegram: @asoxmarket\n"
            "📸 Instagram: [asox.uz](https://www.instagram.com/asox.uz?igsh=MWxibzN1aW52bXo5)\n"
            "▶️ YouTube: @asoxmarket\n"
            "🌐 Сайт: https://asox.uz/"
        ),
        "btn_about": "🎨 Поделитесь своим дизайном",
        "btn_design_add": "➕ Добавить дизайн",
        "btn_catalog": "📦 Каталог товаров",
        "btn_aksiya": "🔥 Акции",
        "btn_contact": "📞 Контакты",
        "btn_site": "🌐 Перейти на сайт",
        "btn_clothes": "👕 Одежда",
        "btn_gifts": "🎁 Подарки",
        "btn_accessories": "📱 Аксессуары",
        "btn_design": "🎨 Дизайн товары",
        "btn_print": "🖨 Услуги печати",
        "btn_back": "⬅️ Назад",
        "btn_lang": "🌐 Tilni o'zgartirish | Сменить язык",
        "btn_izoh": "📝 Оставить комментарий",
        "izoh_prompt": (
            "📝 *Комментарий или дополнительная информация*\n\n"
            "Опишите подробно, какой товар вы хотите:\n"
            "_(Например: цвет, размер, количество, особые требования и т.д.)_"
        ),
        "izoh_done": "✅ *Ваш комментарий принят!*",
        "izoh_cancel_btn": "❌ Отмена",
        "izoh_skip_btn": "⏭ Пропустить",
        "btn_taklif": "💡 Оставить предложение",
        "taklif_prompt": "💡 *Напишите ваше предложение*\n\nКакой товар или услугу вы хотите видеть у нас?",
        "taklif_done": "✅ *Ваше предложение принято! Спасибо!*\n\n🔖 Номер запроса: #{id}",
        "taklif_cancel_btn": "❌ Отмена",
        "btn_faq_ask": "✍️ Задать вопрос",
        "faq_ask_prompt": "✍️ *Напишите ваш вопрос*\n\nНаши специалисты скоро ответят:",
        "faq_ask_done": "✅ *Ваш вопрос принят! Скоро ответим.*\n\n🔖 Номер запроса: #{id}",
        "faq_ask_cancel_btn": "❌ Отмена",
        "narx_prompt": "💰 *Сколько вы готовы заплатить за дизайн?*\n\nВведите только цифру _(например: 50, 100, 200)_\nБот автоматически переведёт в сумы.",
        "narx_invalid": "❗ Пожалуйста, введите только цифру _(например: 50, 100, 200)_",
        "narx_skip_btn": "⏭ Пропустить",
        "narx_done": "✅ *Спасибо! Ваша информация принята.*\n\nНаши специалисты свяжутся с вами в ближайшее время!\n\n🔖 Номер запроса: #{id}",
        "lang_changed": "✅ Язык изменён!",
        "btn_faq": "❓ Часто задаваемые вопросы",
        "faq_title": "❓ *Часто задаваемые вопросы*\n\nКакой раздел вас интересует?",
        "faq_btn_order": "💳 Заказ и оплата",
        "faq_btn_product": "📦 Товар",
        "faq_btn_tech": "🖨 Технические вопросы",
        "faq_btn_general": "🏢 Общие вопросы",
        "faq_order": (
            "💳 *Заказ и оплата*\n\n"
            "❓ *Какие способы оплаты есть?*\n"
            "✅ Можно оплатить через Click, Payme, Uzcard, Humo.\n\n"
            "❓ *Сколько дней готовится заказ?*\n"
            "✅ Обычный заказ 3-5 рабочих дней, товар с дизайном 5-7 рабочих дней.\n\n"
            "❓ *Есть ли доставка? Сколько стоит?*\n"
            "✅ Да, доставляем по всему Узбекистану. Стоимость зависит от адреса.\n\n"
            "❓ *Можно ли отменить заказ?*\n"
            "✅ Можно до начала производства. Обратитесь к оператору."
        ),
        "faq_product": (
            "📦 *О товаре*\n\n"
            "❓ *В каком формате должно быть изображение для дизайна?*\n"
            "✅ PNG или JPG, минимум 300 DPI.\n\n"
            "❓ *Какие размеры доступны?*\n"
            "✅ От XS до 3XL. При заказе отправим таблицу размеров.\n\n"
            "❓ *Можно ли вернуть товар?*\n"
            "✅ При производственном дефекте возврат 100%. Персональный дизайн возврату не подлежит.\n\n"
            "❓ *Есть ли минимальный объём заказа?*\n"
            "✅ Можно заказать от одного изделия. Для оптовых заказов — отдельные цены."
        ),
        "faq_tech": (
            "🖨 *Технические вопросы*\n\n"
            "❓ *Сколько времени занимает подготовка дизайна?*\n"
            "✅ Согласование дизайна 1-2 часа, производство 3-7 рабочих дней.\n\n"
            "❓ *Что если качество изображения низкое?*\n"
            "✅ Наши специалисты свяжутся с вами и попросят изображение лучшего качества.\n\n"
            "❓ *Какой метод печати лучше?*\n"
            "✅ Для одежды — DTF или DTG, для твёрдых поверхностей — UV печать, для фото качества — сублимация."
        ),
        "faq_general": (
            "🏢 *Общие вопросы*\n\n"
            "❓ *Где находится офис?*\n"
            "✅ г. Ташкент. Точный адрес можно узнать у оператора: @asoxmarket\n\n"
            "❓ *Какой режим работы?*\n"
            "✅ Понедельник — Суббота: 09:00 — 18:00\n\n"
            "❓ *Возможен ли оптовый заказ?*\n"
            "✅ Да! При заказе от 10 штук действуют специальные скидки. Обратитесь к оператору."
        ),
        "design_custom_title": (
            "🎨 *Разместите свой дизайн*\n\n"
            "Выберите товар из списка —\n"
            "нанесём ваше изображение или логотип!"
        ),
        "design_photo_prompt": "📸 Выбран *{product}*!\n\nПожалуйста, отправьте изображение дизайна 👇\n_(Выберите из галереи)_",
        "design_done": (
            "✅ *Спасибо! Ваш дизайн принят.*\n\n"
            "📦 Товар: {product}\n\n"
            "🕐 Наши специалисты свяжутся с вами в ближайшее время!"
        ),
        "design_cancel_btn": "❌ Отмена",
        "btn_sotuvchi": "🏪 Я продавец",
        "sotuvchi_not_yet": (
            "⏳ *Вы ещё не продавец.*\n\n"
            "Ваш запрос отправлен администратору. Мы сообщим вам после подтверждения.\n\n"
            "🔖 Номер запроса: #{id}"
        ),
        "sotuvchi_prompt": (
            "🏪 *Регистрация продавца*\n\n"
            "Введите номер телефона или поделитесь им через кнопку ниже _(например: +998901234567)_:"
        ),
        "sotuvchi_invalid": "❗ Пожалуйста, введите корректный номер телефона _(например: +998901234567)_",
        "sotuvchi_done": (
            "✅ *Вы зарегистрированы как продавец!*\n\n"
            "Когда на Asox.uz придёт заказ для вас, мы сообщим об этом в этом боте."
        ),
        "sotuvchi_cancel_btn": "❌ Отмена",
        "sotuvchi_cancelled": "❌ Отменено.",
        "btn_sotuvchi_contact": "📱 Поделиться контактом",
        "sotuvchi_panel_title": (
            "🏪 *Вы зарегистрированы как продавец*\n\n"
            "📞 Телефон: {phone}\n\n"
            "Когда на Asox.uz придёт заказ для вас, мы сообщим об этом в этом боте."
        ),
        "btn_sotuvchi_update": "🔄 Обновить телефон",
    },
    "en": {
        "welcome": (
            "👋 Hello!\n"
            "🛒 Welcome to *ASOX Market* bot!\n\n"
            "Please choose a section:"
        ),
        "about": (
            "ℹ️ *About ASOX Market*\n\n"
            "ASOX Market — premium e-commerce platform in Uzbekistan.\n\n"
            "✅ *Our services:*\n"
            "🎨 Personal design studio\n"
            "🖨 Print marketplace\n"
            "📹 Live shopping\n"
            "🤖 AI assistant\n"
            "🔒 Secure payment (Click, Payme, Uzcard, Humo)\n\n"
            "📲 Download the app and get a discount on your first order!"
        ),
        "catalog_title": "📦 *Product catalog*\n\nChoose a category:",
        "clothes_title": (
            "👕 *Clothing*\n\n"
            "Clothing with your unique design:\n\n"
            "👕 T-shirt\n"
            "🧥 Hoodie\n"
            "🥻 Polo shirt\n"
            "🩳 Shorts\n"
            "🧦 Socks\n"
            "🧤 Gloves\n"
            "🏃 Sportswear\n"
            "🎽 Uniform\n\n"
            "🌐 Visit the website for more information:"
        ),
        "gifts_title": (
            "🎁 *Gifts*\n\n"
            "Special gifts for your loved ones:\n\n"
            "☕ Mug\n"
            "🧴 Thermos\n"
            "🛏 Pillow\n"
            "🖼 Poster\n"
            "🖼 Canvas\n"
            "🗓 Calendar\n"
            "📒 Notebook\n"
            "🎀 Gift set\n\n"
            "🌐 Visit the website for more information:"
        ),
        "accessories_title": (
            "📱 *Accessories*\n\n"
            "Accessories with personal design:\n\n"
            "📱 Phone case\n"
            "🎒 Backpack\n"
            "👜 Bag\n"
            "🧢 Cap\n"
            "⌚ Watch strap\n"
            "🖱 Mouse pad\n\n"
            "🌐 Visit the website for more information:"
        ),
        "design_title": (
            "🎨 *Design products*\n\n"
            "Place your image or logo on the following products:\n\n"
            "👕 T-shirt\n"
            "🧥 Hoodie\n"
            "☕ Mug\n"
            "🖼 Poster\n"
            "🖼 Canvas\n"
            "🛏 Pillow\n"
            "🧴 Thermos\n"
            "🏃 Sportswear\n\n"
            "➕ And 40+ more products!\n\n"
            "🌐 Visit the website for more information:"
        ),
        "print_title": (
            "🖨 *Print services*\n\n"
            "Find certified print masters in Uzbekistan:\n\n"
            "🔵 UV print — Hard surfaces\n"
            "🟡 DTF — Textile\n"
            "🟢 DTG — Direct to fabric\n"
            "🟠 Sublimation — Photo quality\n"
            "🔴 Eco-solvent — Banners\n"
            "⚪ 3D print — Volumetric products\n"
            "🔶 Laser — Engraving and cutting\n"
            "🔷 CNC — Precision processing\n\n"
            "🌐 Visit the website to find a master:"
        ),
        "aksiya": (
            "🔥 *Promotions and discounts*\n\n"
            "🎉 Current special offers:\n\n"
            "👕 *T-shirt* — 20% off\n"
            "🧥 *Hoodie* — 15% off\n"
            "☕ *Mug* — buy 2 get 1 free\n"
            "🎒 *Backpack* — 25% off\n"
            "🖼 *Poster + Canvas* — 30% cheaper as a set\n\n"
            "⏳ *Promotion valid until:* July 31, 2026\n\n"
            "📲 Visit the website to order:"
        ),
        "contact": (
            "📞 *Contact*\n\n"
            "📲 Main: +998 90 009 00 38\n"
            "📲 Backup: +998 90 657 81 45\n\n"
            "📱 Telegram: @asoxmarket\n"
            "📸 Instagram: [asox.uz](https://www.instagram.com/asox.uz?igsh=MWxibzN1aW52bXo5)\n"
            "▶️ YouTube: @asoxmarket\n"
            "🌐 Website: https://asox.uz/"
        ),
        "btn_about": "🎨 Share your design",
        "btn_design_add": "➕ Add design",
        "btn_catalog": "📦 Product catalog",
        "btn_aksiya": "🔥 Promotions",
        "btn_contact": "📞 Contact",
        "btn_site": "🌐 Go to website",
        "btn_clothes": "👕 Clothing",
        "btn_gifts": "🎁 Gifts",
        "btn_accessories": "📱 Accessories",
        "btn_design": "🎨 Design products",
        "btn_print": "🖨 Print services",
        "btn_back": "⬅️ Back",
        "btn_lang": "🌐 Change language",
        "btn_izoh": "📝 Add comment",
        "izoh_prompt": (
            "📝 *Comment or additional info*\n\n"
            "Describe in detail what product you want:\n"
            "_(e.g.: color, size, quantity, special requirements, etc.)_"
        ),
        "izoh_done": "✅ *Your comment has been accepted!*",
        "izoh_cancel_btn": "❌ Cancel",
        "izoh_skip_btn": "⏭ Skip",
        "btn_taklif": "💡 Leave a suggestion",
        "taklif_prompt": "💡 *Write your suggestion*\n\nWhat product or service would you like us to add?",
        "taklif_done": "✅ *Your suggestion has been accepted! Thank you!*\n\n🔖 Request ID: #{id}",
        "taklif_cancel_btn": "❌ Cancel",
        "btn_faq_ask": "✍️ Ask a question",
        "faq_ask_prompt": "✍️ *Write your question*\n\nOur specialists will reply soon:",
        "faq_ask_done": "✅ *Your question has been received! We'll reply soon.*\n\n🔖 Request ID: #{id}",
        "faq_ask_cancel_btn": "❌ Cancel",
        "narx_prompt": "💰 *How much would you pay for the design?*\n\nEnter only a number _(e.g.: 50, 100, 200)_\nThe bot will automatically convert to soums.",
        "narx_invalid": "❗ Please enter only a number _(e.g.: 50, 100, 200)_",
        "narx_skip_btn": "⏭ Skip",
        "narx_done": "✅ *Thank you! Your information has been received.*\n\nOur specialists will contact you shortly!\n\n🔖 Request ID: #{id}",
        "lang_changed": "✅ Language changed!",
        "btn_faq": "❓ FAQ",
        "faq_title": "❓ *Frequently Asked Questions*\n\nWhich section interests you?",
        "faq_btn_order": "💳 Order & Payment",
        "faq_btn_product": "📦 Product",
        "faq_btn_tech": "🖨 Technical Questions",
        "faq_btn_general": "🏢 General",
        "faq_order": (
            "💳 *Order & Payment*\n\n"
            "❓ *What payment methods are available?*\n"
            "✅ You can pay via Click, Payme, Uzcard, Humo.\n\n"
            "❓ *How long does an order take?*\n"
            "✅ Regular orders take 3-5 business days, design products 5-7 business days.\n\n"
            "❓ *Is delivery available? How much does it cost?*\n"
            "✅ Yes, we deliver across all of Uzbekistan. Cost depends on the address.\n\n"
            "❓ *Can I cancel an order?*\n"
            "✅ You can cancel before production starts. Contact the operator."
        ),
        "faq_product": (
            "📦 *About Products*\n\n"
            "❓ *What format should the design image be?*\n"
            "✅ PNG or JPG format, minimum 300 DPI quality.\n\n"
            "❓ *What sizes are available?*\n"
            "✅ From XS to 3XL. We'll send you a size chart when ordering.\n\n"
            "❓ *Can I return a product?*\n"
            "✅ 100% return for manufacturing defects. Custom design products cannot be returned.\n\n"
            "❓ *Is there a minimum order quantity?*\n"
            "✅ You can order from 1 item. Special prices available for wholesale."
        ),
        "faq_tech": (
            "🖨 *Technical Questions*\n\n"
            "❓ *How long does design preparation take?*\n"
            "✅ Design approval takes 1-2 hours, production 3-7 business days.\n\n"
            "❓ *What if the image quality is low?*\n"
            "✅ Our specialists will contact you and ask for a higher quality image.\n\n"
            "❓ *Which print method is best?*\n"
            "✅ DTF or DTG for clothing, UV print for hard surfaces, sublimation for photo quality."
        ),
        "faq_general": (
            "🏢 *General Questions*\n\n"
            "❓ *Where is the office located?*\n"
            "✅ Tashkent city. You can get the exact address from the operator: @asoxmarket\n\n"
            "❓ *What are the working hours?*\n"
            "✅ Monday — Saturday: 09:00 — 18:00\n\n"
            "❓ *Is wholesale ordering available?*\n"
            "✅ Yes! Special discounts for orders of 10+ items. Contact the operator."
        ),
        "design_custom_title": (
            "🎨 *Place your design*\n\n"
            "Choose a product from the list —\n"
            "we'll put your image or logo on it!"
        ),
        "design_photo_prompt": "📸 *{product}* selected!\n\nPlease send your design image 👇\n_(Choose from gallery)_",
        "design_done": (
            "✅ *Thank you! Your design has been accepted.*\n\n"
            "📦 Product: {product}\n\n"
            "🕐 Our specialists will contact you shortly!"
        ),
        "design_cancel_btn": "❌ Cancel",
        "btn_sotuvchi": "🏪 I'm a seller",
        "sotuvchi_not_yet": (
            "⏳ *You are not a seller yet.*\n\n"
            "Your request has been sent to the administrator. We'll notify you once approved.\n\n"
            "🔖 Request ID: #{id}"
        ),
        "sotuvchi_prompt": (
            "🏪 *Seller registration*\n\n"
            "Enter your phone number or share it with the button below _(e.g.: +998901234567)_:"
        ),
        "sotuvchi_invalid": "❗ Please enter a valid phone number _(e.g.: +998901234567)_",
        "sotuvchi_done": (
            "✅ *You are now registered as a seller!*\n\n"
            "When you get an order on Asox.uz, we'll notify you here."
        ),
        "sotuvchi_cancel_btn": "❌ Cancel",
        "sotuvchi_cancelled": "❌ Cancelled.",
        "btn_sotuvchi_contact": "📱 Share contact",
        "sotuvchi_panel_title": (
            "🏪 *You are registered as a seller*\n\n"
            "📞 Phone: {phone}\n\n"
            "When you get an order on Asox.uz, we'll notify you here."
        ),
        "btn_sotuvchi_update": "🔄 Update phone",
    }
}

user_lang = {}
bot_photo_id = None
http_session = None
_photo_tasks = {}

DESIGN_PRODUCT_NAMES = {
    "dp_tshirt":    "👕 T-shirt",
    "dp_hoodie":    "🧥 Hoodie",
    "dp_mug":       "☕ Krujka",
    "dp_poster":    "🖼 Poster",
    "dp_pillow":    "🛏 Yostiq",
    "dp_backpack":  "🎒 Ryukzak",
    "dp_phone":     "📱 Telefon chexoli",
    "dp_cap":       "🧢 Kepka",
    "dp_socks":     "🧦 Noski",
    "dp_vizitka":   "💳 Vizitka",
    "dp_afisha":    "📋 Afisha",
    "dp_banner":    "🏳 Banner",
    "dp_kalendar":  "📅 Kalendar",
    "dp_broshyura": "📄 Broshyura",
    "dp_flayer":    "📃 Flayer",
    "dp_liflet":    "📑 Liflet",
    "dp_buklet":    "📒 Buklet",
}

def get_lang(user_id):
    if user_id in user_lang:
        return user_lang[user_id]
    saved = get_user(user_id)
    if saved and saved.get("lang"):
        return saved["lang"]
    return "uz"

def design_products_menu(lang):
    t = TEXTS[lang]
    products = list(DESIGN_PRODUCT_NAMES.items())
    rows = []
    # agar mahsulotlar soni toq bo'lsa, oxirgi mahsulotni "Bekor qilish" bilan yonma-yon qo'yamiz
    last_paired = len(products) - 1 if len(products) % 2 != 0 else len(products)
    for i in range(0, last_paired, 2):
        row = [InlineKeyboardButton(products[i][1], callback_data=products[i][0])]
        if i + 1 < last_paired:
            row.append(InlineKeyboardButton(products[i + 1][1], callback_data=products[i + 1][0]))
        rows.append(row)
    if len(products) % 2 != 0:
        last = products[-1]
        rows.append([
            InlineKeyboardButton(last[1], callback_data=last[0]),
            InlineKeyboardButton(t["design_cancel_btn"], callback_data="back"),
        ])
    else:
        rows.append([InlineKeyboardButton(t["design_cancel_btn"], callback_data="back")])
    rows.append([InlineKeyboardButton(t["btn_taklif"], callback_data="taklif")])
    return InlineKeyboardMarkup(rows)

def main_menu(lang):
    t = TEXTS[lang]
    keyboard = [
        [InlineKeyboardButton(t["btn_about"], callback_data="design_custom")],
        [InlineKeyboardButton(t["btn_catalog"], callback_data="catalog")],
        [InlineKeyboardButton(t["btn_aksiya"], callback_data="aksiya")],
        [InlineKeyboardButton(t["btn_contact"], callback_data="contact")],
        [InlineKeyboardButton(t["btn_site"], url="https://asox.uz/")],
        [InlineKeyboardButton(t["btn_faq"], callback_data="faq")],
        [InlineKeyboardButton(t["btn_sotuvchi"], callback_data="sotuvchi")],
        [InlineKeyboardButton(t["btn_lang"], callback_data="lang")],
    ]
    return InlineKeyboardMarkup(keyboard)

def faq_menu(lang):
    t = TEXTS[lang]
    keyboard = [
        [InlineKeyboardButton(t["faq_btn_order"], callback_data="faq_order")],
        [InlineKeyboardButton(t["faq_btn_product"], callback_data="faq_product")],
        [InlineKeyboardButton(t["faq_btn_tech"], callback_data="faq_tech")],
        [InlineKeyboardButton(t["faq_btn_general"], callback_data="faq_general")],
        [InlineKeyboardButton(t["btn_faq_ask"], callback_data="faq_ask")],
        [InlineKeyboardButton(t["btn_back"], callback_data="back")],
    ]
    return InlineKeyboardMarkup(keyboard)

def catalog_menu(lang):
    t = TEXTS[lang]
    keyboard = [
        [InlineKeyboardButton(t["btn_clothes"], callback_data="clothes")],
        [InlineKeyboardButton(t["btn_gifts"], callback_data="gifts")],
        [InlineKeyboardButton(t["btn_accessories"], callback_data="accessories")],
        [InlineKeyboardButton(t["btn_design"], callback_data="design")],
        [InlineKeyboardButton(t["btn_print"], callback_data="print")],
        [InlineKeyboardButton(t["btn_back"], callback_data="back")],
    ]
    return InlineKeyboardMarkup(keyboard)

def back_menu(lang):
    t = TEXTS[lang]
    keyboard = [
        [InlineKeyboardButton(t["btn_site"], url="https://asox.uz/")],
        [InlineKeyboardButton(t["btn_back"], callback_data="catalog")],
    ]
    return InlineKeyboardMarkup(keyboard)

def back_to_main(lang):
    t = TEXTS[lang]
    keyboard = [[InlineKeyboardButton(t["btn_back"], callback_data="back")]]
    return InlineKeyboardMarkup(keyboard)

def lang_menu():
    keyboard = [
        [InlineKeyboardButton("🇺🇿 O'zbek", callback_data="set_uz")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="set_ru")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="set_en")],
    ]
    return InlineKeyboardMarkup(keyboard)

def phone_keyboard():
    keyboard = [[KeyboardButton("📱 Kontakt qo'shish", request_contact=True)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def sotuvchi_phone_keyboard(t):
    keyboard = [
        [KeyboardButton(t["btn_sotuvchi_contact"], request_contact=True)],
        [KeyboardButton(t["sotuvchi_cancel_btn"])],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

async def promo_check_loop(app):
    while True:
        try:
            now = datetime.now()
            next_run = now.replace(hour=10, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run = next_run + timedelta(days=1)
            await asyncio.sleep((next_run - now).total_seconds())

            today = date.today()
            promos = load_promotions()
            ending_soon = {}
            for p in promos:
                try:
                    end = date.fromisoformat(p["end_date"])
                    days_left = (end - today).days
                    if days_left == 2:
                        ending_soon.setdefault(p["end_date"], []).append(p)
                except Exception:
                    pass

            if ending_soon:
                lines = ["⚠️ *Aksiya tugashiga 2 kun qoldi!*\n"]
                for end_date, items in ending_soon.items():
                    for p in items:
                        lines.append(f"{p['emoji']} *{p['name']}* — {p['discount']}")
                    lines.append(f"📅 Tugash sanasi: {end_date}")
                lines.append("\n➕ Yangi aksiya qo'shmoqchimisiz?")
                msg = "\n".join(lines)
                await _notify_admins(msg, log_tag="AKSIYA")
        except Exception as e:
            print(f"[Promo check] Xato: {e}")

_promo_task = None

async def post_init(app):
    global bot_photo_id, http_session, _promo_task
    http_session = aiohttp.ClientSession()
    try:
        photos = await app.bot.get_user_profile_photos(user_id=app.bot.id)
        if photos.total_count > 0:
            bot_photo_id = photos.photos[0][0].file_id
    except Exception:
        bot_photo_id = None
    _promo_task = asyncio.create_task(promo_check_loop(app))
    await start_order_api(app)

    try:
        await app.bot.set_my_commands([
            BotCommand("start", "Botni ishga tushirish / qayta boshlash"),
        ])
        admin_commands = [
            BotCommand("start", "Botni ishga tushirish / qayta boshlash"),
            BotCommand("admin", "Admin panel"),
            BotCommand("xabar", "Barcha foydalanuvchilarga xabar yuborish"),
        ]
        for admin_id in ADMIN_IDS:
            try:
                await app.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception:
                pass
    except Exception as e:
        print(f"[COMMANDS] Komandalar menyusini o'rnatishda xato: {e}")

async def post_shutdown(app):
    if _promo_task and not _promo_task.done():
        _promo_task.cancel()
        try:
            await _promo_task
        except asyncio.CancelledError:
            pass
    if http_session:
        await http_session.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    saved = get_user(user.id)
    if saved:
        context.user_data["name"] = saved["name"]
        context.user_data["phone"] = saved["phone"]
        lang = get_lang(user.id)
        if bot_photo_id:
            await update.message.reply_photo(
                photo=bot_photo_id,
                caption=TEXTS[lang]["welcome"],
                parse_mode="Markdown",
                reply_markup=main_menu(lang)
            )
        else:
            await update.message.reply_text(
                TEXTS[lang]["welcome"],
                parse_mode="Markdown",
                reply_markup=main_menu(lang)
            )
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 Assalomu alaykum!\n\n"
        "✍️ Iltimos, *ism va familiyangizni* kiriting:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text(
        "📱 Endi *telefon raqamingizni* kiriting\n"
        "yoki quyidagi tugmani bosing:",
        parse_mode="Markdown",
        reply_markup=phone_keyboard()
    )
    return ASK_PHONE

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text.strip()
        if not is_valid_phone(phone):
            await update.message.reply_text(
                "❗ Iltimos, to'g'ri telefon raqam kiriting\n"
                "yoki quyidagi tugmani bosing:\n"
                "_(masalan: +998901234567)_",
                parse_mode="Markdown",
                reply_markup=phone_keyboard()
            )
            return ASK_PHONE

    context.user_data["phone"] = phone
    name = context.user_data.get("name", "Noma'lum")
    user = update.effective_user
    lang = get_lang(user.id)
    save_user(user.id, name, phone)

    admin_text = (
        f"🔔 *Yangi foydalanuvchi!*\n\n"
        f"👤 Ism: {name}\n"
        f"📱 Telefon: {phone}\n"
        f"🆔 ID: `{user.id}`\n"
        f"👤 Username: @{user.username if user.username else 'yoq'}"
    )
    await _notify_admins(admin_text, log_tag="YANGI_FOYDALANUVCHI")

    await update.message.reply_text(
        "✅ *Rahmat! Ma'lumotlaringiz qabul qilindi.*\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

    if bot_photo_id:
        await update.message.reply_photo(
            photo=bot_photo_id,
            caption=TEXTS[lang]["welcome"],
            parse_mode="Markdown",
            reply_markup=main_menu(lang)
        )
    else:
        await update.message.reply_text(
            TEXTS[lang]["welcome"],
            parse_mode="Markdown",
            reply_markup=main_menu(lang)
        )
    return ConversationHandler.END

async def edit_msg(query, text, reply_markup, parse_mode="Markdown"):
    if query.message.photo:
        await query.edit_message_caption(caption=text, parse_mode=parse_mode, reply_markup=reply_markup)
    else:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)

CALLBACK_TOASTS = {
    "narx_skip": "✅ So'rov yuborildi!",
    "design_confirm_yes": "✅ Tanlandi!",
    "izoh_skip": "⏭ O'tkazib yuborildi",
    "set_uz": "🇺🇿 O'zbek",
    "set_ru": "🇷🇺 Русский",
    "set_en": "🇬🇧 English",
}

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer(text=CALLBACK_TOASTS.get(data))
    user_id = query.from_user.id
    lang = get_lang(user_id)
    t = TEXTS[lang]

    if data == "design_custom":
        await edit_msg(query, t["design_custom_title"], design_products_menu(lang))
    elif data.startswith("dp_"):
        product = DESIGN_PRODUCT_NAMES.get(data, data)
        if context.user_data.get("choosing_per_photo"):
            idx = context.user_data.get("design_current_idx", 0)
            if "design_products" not in context.user_data:
                context.user_data["design_products"] = []
            context.user_data["design_products"].append(product)
            context.user_data["design_current_idx"] = idx + 1
            photos = context.user_data.get("design_photos", [])
            next_idx = idx + 1
            if next_idx < len(photos):
                await query.message.delete()
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=photos[next_idx],
                    caption=f"📸 *{next_idx + 1}-rasm* uchun mahsulot tanlang 👇",
                    parse_mode="Markdown",
                    reply_markup=design_products_menu(lang),
                )
            else:
                chat_id = query.message.chat_id
                await query.message.delete()
                await _process_photos_final(
                    chat_id, query.from_user, context,
                    photos, context.user_data["design_products"]
                )
        else:
            context.user_data["design_product"] = product
            context.user_data["awaiting_design"] = True
            cancel_markup = InlineKeyboardMarkup([[
                InlineKeyboardButton(t["design_cancel_btn"], callback_data="design_cancel")
            ]])
            await query.message.reply_text(
                t["design_photo_prompt"].format(product=product),
                parse_mode="Markdown",
                reply_markup=cancel_markup,
            )
    elif data == "design_confirm_yes":
        photos = context.user_data.get("design_photos", [])
        product = context.user_data.get("design_product", "Noma'lum")
        await query.message.delete()
        await _process_photos_final(query.message.chat_id, query.from_user, context, photos, [product] * len(photos))
    elif data == "design_confirm_no":
        context.user_data["choosing_per_photo"] = True
        context.user_data["design_current_idx"] = 0
        context.user_data["design_products"] = []
        context.user_data.pop("awaiting_design_confirm", None)
        photos = context.user_data.get("design_photos", [])
        await query.message.delete()
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=photos[0],
            caption="📸 *1-rasm* uchun mahsulot tanlang 👇",
            parse_mode="Markdown",
            reply_markup=design_products_menu(lang),
        )
    elif data == "taklif":
        context.user_data["awaiting_taklif"] = True
        await query.message.reply_text(
            t["taklif_prompt"], parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t["taklif_cancel_btn"], callback_data="taklif_cancel")
            ]])
        )
    elif data == "taklif_cancel":
        context.user_data.pop("awaiting_taklif", None)
        await edit_msg(query, t["welcome"], main_menu(lang))
    elif data == "izoh":
        context.user_data["awaiting_izoh"] = True
        cancel_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton(t["izoh_cancel_btn"], callback_data="izoh_cancel")
        ]])
        await query.message.reply_text(
            t["izoh_prompt"],
            parse_mode="Markdown",
            reply_markup=cancel_markup,
        )
    elif data == "izoh_cancel":
        context.user_data.pop("awaiting_izoh", None)
        context.user_data.pop("pending_photos", None)
        context.user_data.pop("pending_products", None)
        context.user_data.pop("pending_user", None)
        await edit_msg(query, t["welcome"], main_menu(lang))
    elif data == "izoh_skip":
        context.user_data.pop("awaiting_izoh", None)
        context.user_data["saved_izoh"] = ""
        context.user_data["awaiting_narx"] = True
        await query.message.reply_text(
            t["narx_prompt"], parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t["narx_skip_btn"], callback_data="narx_skip")]])
        )
    elif data == "narx_skip":
        context.user_data.pop("awaiting_narx", None)
        user = query.from_user
        photos = context.user_data.get("pending_photos", [])
        products = context.user_data.get("pending_products", [])
        izoh_text = context.user_data.get("saved_izoh", "")
        request_id = next_request_id()
        log_request(request_id, "dizayn", user, ", ".join(products))
        for file_id, product in zip(photos, products):
            await _send_to_admin(file_id, product, user, context, izoh=izoh_text, narx="", request_id=request_id)
        context.user_data.pop("saved_izoh", None)
        context.user_data.pop("pending_photos", None)
        context.user_data.pop("pending_products", None)
        context.user_data.pop("pending_user", None)
        await query.message.reply_text(t["narx_done"].format(id=request_id), parse_mode="Markdown", reply_markup=main_menu(lang))
    elif data == "design_cancel":
        context.user_data.pop("awaiting_design", None)
        context.user_data.pop("design_product", None)
        context.user_data.pop("design_photos", None)
        await edit_msg(query, t["welcome"], main_menu(lang))
    elif data == "aksiya":
        await edit_msg(query, build_aksiya_text(lang), InlineKeyboardMarkup([
            [InlineKeyboardButton(t["btn_site"], url="https://asox.uz/")],
            [InlineKeyboardButton(t["btn_back"], callback_data="back")],
        ]))
    elif data == "about":
        await edit_msg(query, t["about"], back_to_main(lang))
    elif data == "catalog":
        await edit_msg(query, t["catalog_title"], catalog_menu(lang))
    elif data == "clothes":
        await edit_msg(query, t["clothes_title"], back_menu(lang))
    elif data == "gifts":
        await edit_msg(query, t["gifts_title"], back_menu(lang))
    elif data == "accessories":
        await edit_msg(query, t["accessories_title"], back_menu(lang))
    elif data == "design":
        await edit_msg(query, t["design_title"], back_menu(lang))
    elif data == "print":
        await edit_msg(query, t["print_title"], back_menu(lang))
    elif data == "faq":
        await edit_msg(query, t["faq_title"], faq_menu(lang))
    elif data == "faq_ask":
        context.user_data["awaiting_faq_ask"] = True
        await edit_msg(query, t["faq_ask_prompt"], InlineKeyboardMarkup([
            [InlineKeyboardButton(t["faq_ask_cancel_btn"], callback_data="faq_ask_cancel")]
        ]))
    elif data == "faq_ask_cancel":
        context.user_data.pop("awaiting_faq_ask", None)
        await edit_msg(query, t["faq_title"], faq_menu(lang))
    elif data == "faq_order":
        await edit_msg(query, t["faq_order"], InlineKeyboardMarkup([
            [InlineKeyboardButton(t["btn_back"], callback_data="faq")]
        ]))
    elif data == "faq_product":
        await edit_msg(query, t["faq_product"], InlineKeyboardMarkup([
            [InlineKeyboardButton(t["btn_back"], callback_data="faq")]
        ]))
    elif data == "faq_tech":
        await edit_msg(query, t["faq_tech"], InlineKeyboardMarkup([
            [InlineKeyboardButton(t["btn_back"], callback_data="faq")]
        ]))
    elif data == "faq_general":
        await edit_msg(query, t["faq_general"], InlineKeyboardMarkup([
            [InlineKeyboardButton(t["btn_back"], callback_data="faq")]
        ]))
    elif data == "contact":
        await edit_msg(query, t["contact"], back_to_main(lang))
    elif data == "lang":
        await edit_msg(query, "🌐 Tilni tanlang / Выберите язык:", lang_menu())
    elif data == "set_uz":
        user_lang[user_id] = "uz"
        save_lang(user_id, "uz")
        await edit_msg(query, TEXTS["uz"]["lang_changed"] + "\n\n" + TEXTS["uz"]["welcome"], main_menu("uz"))
    elif data == "set_ru":
        user_lang[user_id] = "ru"
        save_lang(user_id, "ru")
        await edit_msg(query, TEXTS["ru"]["lang_changed"] + "\n\n" + TEXTS["ru"]["welcome"], main_menu("ru"))
    elif data == "set_en":
        user_lang[user_id] = "en"
        save_lang(user_id, "en")
        await edit_msg(query, TEXTS["en"]["lang_changed"] + "\n\n" + TEXTS["en"]["welcome"], main_menu("en"))
    elif data == "sotuvchi":
        seller = get_seller(user_id)
        if seller:
            await edit_msg(
                query,
                t["sotuvchi_panel_title"].format(phone=seller.get("phone", "")),
                InlineKeyboardMarkup([
                    [InlineKeyboardButton(t["btn_sotuvchi_update"], callback_data="sotuvchi_update")],
                    [InlineKeyboardButton(t["btn_back"], callback_data="back")],
                ])
            )
        else:
            saved = get_user(user_id)
            phone = (saved or {}).get("phone") or context.user_data.get("phone", "")
            if is_phone_whitelisted(phone):
                context.user_data["awaiting_sotuvchi"] = True
                await query.message.reply_text(
                    t["sotuvchi_prompt"], parse_mode="Markdown",
                    reply_markup=sotuvchi_phone_keyboard(t)
                )
            else:
                last_sent = context.user_data.get("seller_request_sent_at")
                request_id = context.user_data.get("seller_request_id", "")
                now = datetime.now()
                if not last_sent or now - datetime.fromisoformat(last_sent) > SELLER_REQUEST_COOLDOWN:
                    request_id = next_request_id()
                    context.user_data["seller_request_sent_at"] = now.isoformat()
                    context.user_data["seller_request_id"] = request_id
                    log_request(request_id, "sotuvchi", query.from_user, phone)
                    await _notify_admin_seller_request(query.from_user, phone, context, request_id)
                await edit_msg(query, t["sotuvchi_not_yet"].format(id=request_id or "—"), main_menu(lang))
    elif data == "sotuvchi_update":
        context.user_data["awaiting_sotuvchi"] = True
        await query.message.reply_text(
            t["sotuvchi_prompt"], parse_mode="Markdown",
            reply_markup=sotuvchi_phone_keyboard(t)
        )
    elif data == "back":
        await edit_msg(query, t["welcome"], main_menu(lang))

async def _notify_admins(text, reply_markup=None, log_tag="ADMIN XABAR"):
    """Barcha adminlarga xabar yuboradi; javobni tekshiradi va markdown
    xatosi bo'lsa formatsiz qayta yuboradi, aks holda xabar sezilmasdan yo'qolmasin."""
    url = f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage"
    for admin_id in ADMIN_IDS:
        payload = {"chat_id": admin_id, "text": text, "parse_mode": "Markdown"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            resp = await http_session.post(url, json=payload)
            result = await resp.json()
            if not result.get("ok"):
                print(f"[{log_tag}] {admin_id} ga yuborilmadi: {result.get('description')}")
                payload.pop("parse_mode", None)
                retry_resp = await http_session.post(url, json=payload)
                retry_result = await retry_resp.json()
                if not retry_result.get("ok"):
                    print(f"[{log_tag}] {admin_id} ga qayta urinish ham muvaffaqiyatsiz: {retry_result.get('description')}")
        except Exception as e:
            print(f"[{log_tag}] {admin_id} ga yuborishda xato: {e}")

async def _notify_admin_seller_request(user, phone, context, request_id=""):
    reg_name = context.user_data.get("name", "")
    name_line = reg_name if reg_name else (user.full_name or "")
    username = f"@{user.username}" if user.username else "username yo'q"
    phone_line = f"\n📞 Telefon: {phone}" if phone else ""

    admin_text = (
        f"🏪 *'Men sotuvchiman' bosildi* #{request_id}\n\n"
        f"👤 Ism: {name_line}\n"
        f"💬 Telegram: {username}\n"
        f"🆔 ID: `{user.id}`"
        f"{phone_line}\n\n"
        f"Bu odamni sotuvchilar ro'yxatiga qo'shasizmi?"
    )
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Ha, qo'shish", "callback_data": f"approve_seller_{user.id}"}
        ]]
    }
    await _notify_admins(admin_text, reply_markup=keyboard, log_tag="SOTUVCHI_SOROV")

async def _send_to_admin(file_id, product, user, context, izoh="", narx="", request_id=""):
    reg_name = context.user_data.get("name", "")
    reg_phone = context.user_data.get("phone", "")
    name_line = reg_name if reg_name else (user.full_name or "")
    username = f"@{user.username}" if user.username else "username yo'q"
    phone_line = f"\n📞 Telefon: {reg_phone}" if reg_phone else ""
    izoh_line = f"\n📝 Izoh: {izoh}" if izoh else ""
    narx_line = f"\n💰 Narx taklifi: {narx}" if narx else ""

    admin_text = (
        f"🎨 *Yangi dizayn so'rovi!* #{request_id}\n\n"
        f"👤 Ism: {name_line}\n"
        f"💬 Telegram: {username}\n"
        f"🆔 ID: `{user.id}`"
        f"{phone_line}\n\n"
        f"🛍 Mahsulot: *{product}*"
        f"{izoh_line}"
        f"{narx_line}"
    )
    print(f"[DIZAYN] {user.id} → {product}")
    try:
        await context.bot.send_chat_action(chat_id=user.id, action="upload_photo")
    except Exception:
        pass
    try:
        tg_file = await context.bot.get_file(file_id)
        file_bytes = await tg_file.download_as_bytearray()
    except Exception as e:
        print(f"[DIZAYN] Fayl yuklab olishda xato: {e}")
        file_bytes = None

    for admin_id in ADMIN_IDS:
        try:
            if file_bytes:
                url = f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendPhoto"
                form = aiohttp.FormData()
                form.add_field("chat_id", str(admin_id))
                form.add_field("caption", admin_text)
                form.add_field("parse_mode", "Markdown")
                form.add_field("photo", bytes(file_bytes), filename="photo.jpg", content_type="image/jpeg")
                resp = await http_session.post(url, data=form)
                result = await resp.json()
                if not result.get("ok"):
                    print(f"[DIZAYN] Admin {admin_id} ga yuborilmadi: {result.get('description')}")
                    retry_form = aiohttp.FormData()
                    retry_form.add_field("chat_id", str(admin_id))
                    retry_form.add_field("caption", admin_text)
                    retry_form.add_field("photo", bytes(file_bytes), filename="photo.jpg", content_type="image/jpeg")
                    retry_resp = await http_session.post(url, data=retry_form)
                    retry_result = await retry_resp.json()
                    if not retry_result.get("ok"):
                        print(f"[DIZAYN] Admin {admin_id} qayta urinish ham muvaffaqiyatsiz: {retry_result.get('description')}")
            else:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=admin_text, parse_mode="Markdown")
                except Exception:
                    await context.bot.send_message(chat_id=admin_id, text=admin_text)
        except Exception as e:
            print(f"[DIZAYN] Admin {admin_id} xato: {e}")

async def _process_photos_final(chat_id, user, context, photos, products):
    lang = get_lang(user.id)
    # Rasmlar va mahsulotlarni saqlaymiz, hali adminga yubormaymiz
    context.user_data["pending_photos"] = list(photos)
    context.user_data["pending_products"] = list(products)
    context.user_data["pending_user"] = user
    context.user_data.pop("awaiting_design", None)
    context.user_data.pop("design_photos", None)
    context.user_data.pop("design_products", None)
    context.user_data.pop("choosing_per_photo", None)
    context.user_data.pop("design_current_idx", None)
    context.user_data.pop("awaiting_design_confirm", None)
    t = TEXTS[lang]
    context.user_data["awaiting_izoh"] = True
    await context.bot.send_message(
        chat_id=chat_id,
        text=t["izoh_prompt"],
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t["izoh_cancel_btn"], callback_data="izoh_cancel")],
            [InlineKeyboardButton(t["izoh_skip_btn"], callback_data="izoh_skip")],
        ])
    )

async def _delayed_process(chat_id, user_id, user, context):
    await asyncio.sleep(2.5)
    photos = context.user_data.get("design_photos", [])
    product = context.user_data.get("design_product", "Noma'lum")
    lang = get_lang(user_id)

    if len(photos) == 1:
        await _process_photos_final(chat_id, user, context, photos, [product])
    else:
        context.user_data["awaiting_design_confirm"] = True
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Ha", callback_data="design_confirm_yes"),
            InlineKeyboardButton("❌ Yo'q", callback_data="design_confirm_no"),
        ]])
        text = (
            f"📸 *{len(photos)} ta rasm* qabul qilindi.\n\n"
            f"Barchasini *{product}* ga joylashtirmoqchimisiz?"
            if lang == "uz" else
            f"📸 Получено *{len(photos)} изображений*.\n\n"
            f"Разместить все на *{product}*?"
        )
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=keyboard)

async def design_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_design"):
        return
    user = update.effective_user
    chat_id = update.effective_chat.id

    file_id = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
    media_group_id = update.message.media_group_id

    if "design_photos" not in context.user_data:
        context.user_data["design_photos"] = []
    context.user_data["design_photos"].append(file_id)

    if not media_group_id:
        product = context.user_data.get("design_product", "Noma'lum")
        photos = context.user_data.get("design_photos", [])
        await _process_photos_final(chat_id, user, context, photos, [product])
    else:
        old_task = _photo_tasks.pop(user.id, None)
        if old_task and not old_task.done():
            old_task.cancel()
        task = asyncio.create_task(_delayed_process(chat_id, user.id, user, context))
        _photo_tasks[user.id] = task

async def izoh_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_izoh"):
        return
    user = update.effective_user
    lang = get_lang(user.id)
    t = TEXTS[lang]
    context.user_data["saved_izoh"] = update.message.text
    context.user_data.pop("awaiting_izoh", None)
    context.user_data["awaiting_narx"] = True
    await update.message.reply_text(
        t["narx_prompt"], parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t["narx_skip_btn"], callback_data="narx_skip")]])
    )

async def faq_ask_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_lang(user.id)
    t = TEXTS[lang]
    reg_name = context.user_data.get("name", "")
    name_line = reg_name if reg_name else (user.full_name or "")
    username = f"@{user.username}" if user.username else "username yo'q"

    request_id = next_request_id()
    log_request(request_id, "savol", user, update.message.text)
    admin_text = (
        f"❓ *Foydalanuvchidan savol!* #{request_id}\n\n"
        f"👤 Ism: {name_line}\n"
        f"💬 Telegram: {username}\n"
        f"🆔 ID: `{user.id}`\n\n"
        f"❓ Savol:\n{update.message.text}"
    )
    await _notify_admins(admin_text, log_tag="FAQ")

    context.user_data.pop("awaiting_faq_ask", None)
    await update.message.reply_text(t["faq_ask_done"].format(id=request_id), parse_mode="Markdown", reply_markup=main_menu(lang))

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_narx"):
        await narx_received(update, context)
    elif context.user_data.get("awaiting_izoh"):
        await izoh_received(update, context)
    elif context.user_data.get("awaiting_taklif"):
        await taklif_received(update, context)
    elif context.user_data.get("awaiting_faq_ask"):
        await faq_ask_received(update, context)
    elif context.user_data.get("awaiting_sotuvchi"):
        await sotuvchi_received(update, context)

async def taklif_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_lang(user.id)
    t = TEXTS[lang]
    reg_name = context.user_data.get("name", "")
    reg_phone = context.user_data.get("phone", "")
    name_line = reg_name if reg_name else (user.full_name or "")
    username = f"@{user.username}" if user.username else "username yo'q"
    phone_line = f"\n📞 Telefon: {reg_phone}" if reg_phone else ""

    request_id = next_request_id()
    log_request(request_id, "taklif", user, update.message.text)
    admin_text = (
        f"💡 *Yangi taklif!* #{request_id}\n\n"
        f"👤 Ism: {name_line}\n"
        f"💬 Telegram: {username}\n"
        f"🆔 ID: `{user.id}`"
        f"{phone_line}\n\n"
        f"💬 Taklif:\n{update.message.text}"
    )
    await _notify_admins(admin_text, log_tag="TAKLIF")

    context.user_data.pop("awaiting_taklif", None)
    await update.message.reply_text(t["taklif_done"].format(id=request_id), parse_mode="Markdown", reply_markup=main_menu(lang))

async def narx_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_narx"):
        return
    user = update.effective_user
    lang = get_lang(user.id)
    t = TEXTS[lang]
    raw = update.message.text.strip().replace(" ", "").replace(",", "").replace(".", "")
    if not raw.isdigit():
        await update.message.reply_text(
            t["narx_invalid"], parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t["narx_skip_btn"], callback_data="narx_skip")]])
        )
        return

    narx_formatted = f"{int(raw) * 1000:,}".replace(",", " ") + " so'm"
    izoh_text = context.user_data.get("saved_izoh", "")
    photos = context.user_data.get("pending_photos", [])
    products = context.user_data.get("pending_products", [])
    request_id = next_request_id()
    log_request(request_id, "dizayn", user, ", ".join(products))

    for file_id, product in zip(photos, products):
        await _send_to_admin(file_id, product, user, context, izoh=izoh_text, narx=narx_formatted, request_id=request_id)

    context.user_data.pop("awaiting_narx", None)
    context.user_data.pop("saved_izoh", None)
    context.user_data.pop("pending_photos", None)
    context.user_data.pop("pending_products", None)
    context.user_data.pop("pending_user", None)
    await update.message.reply_text(t["narx_done"].format(id=request_id), parse_mode="Markdown", reply_markup=main_menu(lang))

async def _sotuvchi_return_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, lang, text_msg):
    t = TEXTS[lang]
    await update.message.reply_text(text_msg, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    if bot_photo_id:
        await update.message.reply_photo(
            photo=bot_photo_id, caption=t["welcome"], parse_mode="Markdown", reply_markup=main_menu(lang)
        )
    else:
        await update.message.reply_text(t["welcome"], parse_mode="Markdown", reply_markup=main_menu(lang))

async def _save_sotuvchi(update: Update, context: ContextTypes.DEFAULT_TYPE, phone):
    user = update.effective_user
    lang = get_lang(user.id)
    t = TEXTS[lang]
    context.user_data.pop("awaiting_sotuvchi", None)
    reg_name = context.user_data.get("name", "")
    name_line = reg_name if reg_name else (user.full_name or "")
    username = user.username or ""
    save_seller(user.id, name_line, phone, username)

    admin_text = (
        f"🏪 *Yangi sotuvchi ro'yxatdan o'tdi!*\n\n"
        f"👤 Ism: {name_line}\n"
        f"💬 Telegram: @{username if username else 'yoq'}\n"
        f"🆔 ID: `{user.id}`\n"
        f"📞 Telefon: {phone}"
    )
    await _notify_admins(admin_text, log_tag="SOTUVCHI")

    await _sotuvchi_return_to_menu(update, context, lang, t["sotuvchi_done"])

async def sotuvchi_contact_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_sotuvchi"):
        return
    await _save_sotuvchi(update, context, update.message.contact.phone_number)

async def sotuvchi_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_sotuvchi"):
        return
    user = update.effective_user
    lang = get_lang(user.id)
    t = TEXTS[lang]
    text = update.message.text.strip()

    if text == t["sotuvchi_cancel_btn"]:
        context.user_data.pop("awaiting_sotuvchi", None)
        await _sotuvchi_return_to_menu(update, context, lang, t["sotuvchi_cancelled"])
        return

    if not is_valid_phone(text):
        await update.message.reply_text(
            t["sotuvchi_invalid"], parse_mode="Markdown",
            reply_markup=sotuvchi_phone_keyboard(t)
        )
        return

    await _save_sotuvchi(update, context, text)

async def handle_order_notify(request):
    if not ORDER_API_KEY or request.headers.get("X-API-Key") != ORDER_API_KEY:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    phone = str(data.get("phone", ""))
    result = find_seller_by_phone(phone)
    if not result:
        return web.json_response({"ok": False, "error": "seller not found"}, status=404)

    seller_id, seller = result

    lines = ["🛒 *Sizga zakaz keldi!*\n"]
    order_id = data.get("order_id", "")
    product = data.get("product", "")
    quantity = data.get("quantity", "")
    price = data.get("price", "")
    customer_name = data.get("customer_name", "")
    customer_phone = data.get("customer_phone", "")
    address = data.get("address", "")
    comment = data.get("comment", "")

    if order_id:
        lines.append(f"🧾 Buyurtma raqami: `{order_id}`")
    if product:
        lines.append(f"📦 Mahsulot: {product}")
    if quantity:
        lines.append(f"🔢 Miqdor: {quantity}")
    if price:
        lines.append(f"💰 Narx: {price}")
    if customer_name:
        lines.append(f"👤 Mijoz: {customer_name}")
    if customer_phone:
        lines.append(f"📞 Mijoz telefoni: {customer_phone}")
    if address:
        lines.append(f"📍 Manzil: {address}")
    if comment:
        lines.append(f"📝 Izoh: {comment}")
    lines.append("\n🌐 Batafsil ma'lumot uchun https://asox.uz/ ga kiring.")
    text = "\n".join(lines)

    bot_app = request.app["bot_app"]
    try:
        await bot_app.bot.send_message(chat_id=int(seller_id), text=text, parse_mode="Markdown")
    except Exception:
        try:
            await bot_app.bot.send_message(chat_id=int(seller_id), text=text)
        except Exception as e:
            print(f"[ORDER API] Sotuvchiga xabar yuborishda xato: {e}")
            return web.json_response({"ok": False, "error": "send failed"}, status=500)

    return web.json_response({"ok": True})

async def start_order_api(app):
    if not ORDER_API_KEY:
        print("[ORDER API] ORDER_API_KEY sozlanmagan, API o'chirilgan.")
        return
    web_app = web.Application()
    web_app["bot_app"] = app
    web_app.add_routes([web.post("/api/order-notify", handle_order_notify)])
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", ORDER_API_PORT)
    await site.start()
    print(f"[ORDER API] {ORDER_API_PORT}-portda ishga tushdi.")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return
    total = len(load_users())
    await update.message.reply_text(
        f"👨‍💼 *Admin panel*\n\n"
        f"👥 Foydalanuvchilar: {total} ta\n\n"
        f"📢 Barcha foydalanuvchilarga xabar yuborish uchun:\n"
        f"`/xabar Salom hammaga!`",
        parse_mode="Markdown"
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return
    if not context.args:
        await update.message.reply_text("❗ Xabar yozing: /xabar Salom!")
        return
    text = " ".join(context.args)
    sent, failed = 0, 0
    for uid in load_users().keys():
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 *ASOX Market:*\n\n{text}", parse_mode="Markdown")
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(f"✅ Yuborildi: {sent} ta\n❌ Xato: {failed} ta")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, Conflict):
        logger.warning("Conflict: getUpdates to'qnashuvi (tarmoq uzilishi/qayta urinish): %s", context.error)
        return
    logger.error("Kutilmagan xatolik: %s", context.error, exc_info=context.error)

def main():
    persistence = PicklePersistence(filepath="/home/muxa/asox_bot_data.pickle")
    app = Application.builder().token(TOKEN).connect_timeout(30).read_timeout(30).post_init(post_init).post_shutdown(post_shutdown).persistence(persistence).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_PHONE: [
                MessageHandler(filters.CONTACT, ask_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        name="registration_conv",
        persistent=True,
        conversation_timeout=1800,
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.CONTACT, sotuvchi_contact_received))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, design_photo_received))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("xabar", broadcast))
    app.add_handler(CallbackQueryHandler(button))
    app.add_error_handler(error_handler)
    print("✅ Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

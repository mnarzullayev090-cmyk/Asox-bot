import os
import json
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

import aiohttp

USERS_FILE = "/home/muxa/users.json"

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_user(user_id, name, phone):
    users = load_users()
    users[str(user_id)] = {"name": name, "phone": phone}
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, ensure_ascii=False)

def get_user(user_id):
    return load_users().get(str(user_id))

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")
ADMIN_IDS = [int(os.getenv("ADMIN_ID")), int(os.getenv("ADMIN_ID2"))]

ASK_NAME, ASK_PHONE, DESIGN_CHOOSE, DESIGN_PHOTO = range(4)

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
        "btn_about": "🎨 O'z dizayningizni yarating",
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
        "izoh_done": "✅ *Izohingiz qabul qilindi!*\n\nTez orada mutaxassislarimiz siz bilan bog'lanadi.",
        "izoh_cancel_btn": "❌ Bekor qilish",
        "lang_changed": "✅ Til o'zgartirildi!",
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
        "btn_about": "🎨 Создайте свой дизайн",
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
        "izoh_done": "✅ *Ваш комментарий принят!*\n\nНаши специалисты свяжутся с вами в ближайшее время.",
        "izoh_cancel_btn": "❌ Отмена",
        "lang_changed": "✅ Язык изменён!",
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
    }
}

user_lang = {}
bot_photo_id = None
http_session = None

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
    return user_lang.get(user_id, "uz")

def design_products_menu(lang):
    t = TEXTS[lang]
    products = list(DESIGN_PRODUCT_NAMES.items())
    rows = []
    for i in range(0, len(products), 2):
        row = [InlineKeyboardButton(products[i][1], callback_data=products[i][0])]
        if i + 1 < len(products):
            row.append(InlineKeyboardButton(products[i + 1][1], callback_data=products[i + 1][0]))
        rows.append(row)
    rows.append([InlineKeyboardButton(t["design_cancel_btn"], callback_data="back")])
    return InlineKeyboardMarkup(rows)

def main_menu(lang):
    t = TEXTS[lang]
    keyboard = [
        [InlineKeyboardButton(t["btn_about"], callback_data="design_custom")],
        [InlineKeyboardButton(t["btn_catalog"], callback_data="catalog")],
        [InlineKeyboardButton(t["btn_aksiya"], callback_data="aksiya")],
        [InlineKeyboardButton(t["btn_contact"], callback_data="contact")],
        [InlineKeyboardButton(t["btn_site"], url="https://asox.uz/")],
        [InlineKeyboardButton(t["btn_lang"], callback_data="lang")],
        [InlineKeyboardButton(t["btn_izoh"], callback_data="izoh")],
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
    ]
    return InlineKeyboardMarkup(keyboard)

def phone_keyboard():
    keyboard = [[KeyboardButton("📱 Kontakt qo'shish", request_contact=True)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

async def post_init(app):
    global bot_photo_id, http_session
    http_session = aiohttp.ClientSession()
    try:
        photos = await app.bot.get_user_profile_photos(user_id=app.bot.id)
        if photos.total_count > 0:
            bot_photo_id = photos.photos[0][0].file_id
    except Exception:
        bot_photo_id = None

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
        phone = update.message.text

    context.user_data["phone"] = phone
    name = context.user_data.get("name", "Noma'lum")
    user = update.effective_user
    lang = get_lang(user.id)
    save_user(user.id, name, phone)

    admin_text = (
        f"🔔 *Yangi foydalanuvchi!*\n\n"
        f"👤 Ism: {name}\n"
        f"📱 Telefon: {phone}\n"
        f"🆔 Telegram ID: {user.id}\n"
        f"👤 Username: @{user.username if user.username else 'yoq'}"
    )
    try:
        url = f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage"
        for admin_id in ADMIN_IDS:
            await http_session.post(url, json={
                "chat_id": admin_id,
                "text": admin_text,
                "parse_mode": "Markdown"
            })
    except Exception as e:
        print(f"Admin xabar yuborishda xato: {e}")

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

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = get_lang(user_id)
    t = TEXTS[lang]
    data = query.data

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
        await edit_msg(query, t["welcome"], main_menu(lang))
    elif data == "design_cancel":
        context.user_data.pop("awaiting_design", None)
        context.user_data.pop("design_product", None)
        context.user_data.pop("design_photos", None)
        await edit_msg(query, t["welcome"], main_menu(lang))
    elif data == "aksiya":
        await edit_msg(query, t["aksiya"], InlineKeyboardMarkup([
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
    elif data == "contact":
        await edit_msg(query, t["contact"], back_to_main(lang))
    elif data == "lang":
        await edit_msg(query, "🌐 Tilni tanlang / Выберите язык:", lang_menu())
    elif data == "set_uz":
        user_lang[user_id] = "uz"
        await edit_msg(query, TEXTS["uz"]["lang_changed"] + "\n\n" + TEXTS["uz"]["welcome"], main_menu("uz"))
    elif data == "set_ru":
        user_lang[user_id] = "ru"
        await edit_msg(query, TEXTS["ru"]["lang_changed"] + "\n\n" + TEXTS["ru"]["welcome"], main_menu("ru"))
    elif data == "back":
        await edit_msg(query, t["welcome"], main_menu(lang))

async def _send_to_admin(file_id, product, user, context):
    reg_name = context.user_data.get("name", "")
    reg_phone = context.user_data.get("phone", "")
    name_line = reg_name if reg_name else (user.full_name or "")
    username = f"@{user.username}" if user.username else "username yo'q"
    phone_line = f"\n📞 Telefon: {reg_phone}" if reg_phone else ""

    admin_text = (
        f"🎨 *Yangi dizayn so'rovi!*\n\n"
        f"👤 Ism: {name_line}\n"
        f"💬 Telegram: {username}\n"
        f"🆔 ID: `{user.id}`"
        f"{phone_line}\n\n"
        f"🛍 Mahsulot: *{product}*\n"
        f"📸 Foydalanuvchi dizayn yubordi!"
    )
    print(f"[DIZAYN] {user.id} → {product}")
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
                    print(f"[DIZAYN] Admin {admin_id} xato: {result}")
            else:
                await context.bot.send_message(chat_id=admin_id, text=admin_text, parse_mode="Markdown")
        except Exception as e:
            print(f"[DIZAYN] Admin {admin_id} xato: {e}")

async def _process_photos_final(chat_id, user, context, photos, products):
    for file_id, product in zip(photos, products):
        await _send_to_admin(file_id, product, user, context)
    lang = get_lang(user.id)
    context.user_data.pop("awaiting_design", None)
    context.user_data.pop("design_photos", None)
    context.user_data.pop("design_products", None)
    context.user_data.pop("choosing_per_photo", None)
    context.user_data.pop("design_current_idx", None)
    context.user_data.pop("awaiting_design_confirm", None)
    done_text = (
        "✅ *Rahmat! Dizayn(lar) qabul qilindi.*\n\n"
        "🕐 Tez orada mutaxassislarimiz siz bilan bog'lanadi!"
        if lang == "uz" else
        "✅ *Спасибо! Дизайн(ы) приняты.*\n\n"
        "🕐 Наши специалисты свяжутся с вами в ближайшее время!"
    )
    await context.bot.send_message(chat_id=chat_id, text=done_text, parse_mode="Markdown")

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
        old_task = context.user_data.pop("_photo_task", None)
        if old_task and not old_task.done():
            old_task.cancel()
        task = asyncio.create_task(_delayed_process(chat_id, user.id, user, context))
        context.user_data["_photo_task"] = task

async def izoh_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_izoh"):
        return
    user = update.effective_user
    lang = get_lang(user.id)
    t = TEXTS[lang]
    izoh_text = update.message.text

    reg_name = context.user_data.get("name", "")
    reg_phone = context.user_data.get("phone", "")
    name_line = reg_name if reg_name else (user.full_name or "")
    username = f"@{user.username}" if user.username else "username yo'q"
    phone_line = f"\n📞 Telefon: {reg_phone}" if reg_phone else ""

    admin_text = (
        f"📝 *Yangi izoh!*\n\n"
        f"👤 Ism: {name_line}\n"
        f"💬 Telegram: {username}\n"
        f"🆔 ID: `{user.id}`"
        f"{phone_line}\n\n"
        f"💬 Izoh:\n{izoh_text}"
    )
    try:
        url = f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage"
        for admin_id in ADMIN_IDS:
            await http_session.post(url, json={
                "chat_id": admin_id,
                "text": admin_text,
                "parse_mode": "Markdown"
            })
    except Exception as e:
        print(f"Izoh yuborishda xato: {e}")

    context.user_data.pop("awaiting_izoh", None)
    await update.message.reply_text(t["izoh_done"], parse_mode="Markdown", reply_markup=main_menu(lang))

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return
    total = len(user_lang) if user_lang else 0
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
    for uid in list(user_lang.keys()):
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 *ASOX Market:*\n\n{text}", parse_mode="Markdown")
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(f"✅ Yuborildi: {sent} ta\n❌ Xato: {failed} ta")

def main():
    app = Application.builder().token(TOKEN).connect_timeout(30).read_timeout(30).post_init(post_init).build()

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
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, design_photo_received))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, izoh_received))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("xabar", broadcast))
    app.add_handler(CallbackQueryHandler(button))
    print("✅ Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

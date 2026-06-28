from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = "***REMOVED_LEAKED_TOKEN***"

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
        "contact": (
            "📞 *Aloqa*\n\n"
            "📱 Telegram: @asoxmarket\n"
            "📸 Instagram: @asoxmarket\n"
            "▶️ YouTube: @asoxmarket\n"
            "🌐 Sayt: https://asox.uz/"
        ),
        "btn_about": "ℹ️ Biz haqimizda",
        "btn_catalog": "📦 Mahsulotlar katalogi",
        "btn_contact": "📞 Aloqa",
        "btn_site": "🌐 Saytga o'tish",
        "btn_design": "🎨 Dizayn mahsulotlari",
        "btn_print": "🖨 Print xizmatlari",
        "btn_back": "⬅️ Orqaga",
        "btn_lang": "🌐 Tilni o'zgartirish | Сменить язык",
        "lang_changed": "✅ Til o'zgartirildi!",
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
        "contact": (
            "📞 *Контакты*\n\n"
            "📱 Telegram: @asoxmarket\n"
            "📸 Instagram: @asoxmarket\n"
            "▶️ YouTube: @asoxmarket\n"
            "🌐 Сайт: https://asox.uz/"
        ),
        "btn_about": "ℹ️ О нас",
        "btn_catalog": "📦 Каталог товаров",
        "btn_contact": "📞 Контакты",
        "btn_site": "🌐 Перейти на сайт",
        "btn_design": "🎨 Дизайн товары",
        "btn_print": "🖨 Услуги печати",
        "btn_back": "⬅️ Назад",
        "btn_lang": "🌐 Tilni o'zgartirish | Сменить язык",
        "lang_changed": "✅ Язык изменён!",
    }
}

user_lang = {}

def get_lang(user_id):
    return user_lang.get(user_id, "uz")

def main_menu(lang):
    t = TEXTS[lang]
    keyboard = [
        [InlineKeyboardButton(t["btn_about"], callback_data="about")],
        [InlineKeyboardButton(t["btn_catalog"], callback_data="catalog")],
        [InlineKeyboardButton(t["btn_contact"], callback_data="contact")],
        [InlineKeyboardButton(t["btn_site"], url="https://asox.uz/")],
        [InlineKeyboardButton(t["btn_lang"], callback_data="lang")],
    ]
    return InlineKeyboardMarkup(keyboard)

def catalog_menu(lang):
    t = TEXTS[lang]
    keyboard = [
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

def lang_menu():
    keyboard = [
        [InlineKeyboardButton("🇺🇿 O'zbek", callback_data="set_uz")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="set_ru")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    await update.message.reply_text(
        TEXTS[lang]["welcome"],
        parse_mode="Markdown",
        reply_markup=main_menu(lang)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = get_lang(user_id)
    t = TEXTS[lang]
    data = query.data

    if data == "about":
        await query.edit_message_text(t["about"], parse_mode="Markdown", reply_markup=back_to_main(lang))
    elif data == "catalog":
        await query.edit_message_text(t["catalog_title"], parse_mode="Markdown", reply_markup=catalog_menu(lang))
    elif data == "design":
        await query.edit_message_text(t["design_title"], parse_mode="Markdown", reply_markup=back_menu(lang))
    elif data == "print":
        await query.edit_message_text(t["print_title"], parse_mode="Markdown", reply_markup=back_menu(lang))
    elif data == "contact":
        await query.edit_message_text(t["contact"], parse_mode="Markdown", reply_markup=back_to_main(lang))
    elif data == "lang":
        await query.edit_message_text("🌐 Tilni tanlang / Выберите язык:", reply_markup=lang_menu())
    elif data == "set_uz":
        user_lang[user_id] = "uz"
        await query.edit_message_text(TEXTS["uz"]["lang_changed"] + "\n\n" + TEXTS["uz"]["welcome"],
                                      parse_mode="Markdown", reply_markup=main_menu("uz"))
    elif data == "set_ru":
        user_lang[user_id] = "ru"
        await query.edit_message_text(TEXTS["ru"]["lang_changed"] + "\n\n" + TEXTS["ru"]["welcome"],
                                      parse_mode="Markdown", reply_markup=main_menu("ru"))
    elif data == "back":
        await query.edit_message_text(t["welcome"], parse_mode="Markdown", reply_markup=main_menu(lang))

def back_to_main(lang):
    t = TEXTS[lang]
    keyboard = [[InlineKeyboardButton(t["btn_back"], callback_data="back")]]
    return InlineKeyboardMarkup(keyboard)

def main():
    app = Application.builder().token(TOKEN).connect_timeout(30).read_timeout(30).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    print("✅ Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

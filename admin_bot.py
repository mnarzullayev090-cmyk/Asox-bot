import os
import json
import aiohttp
from datetime import date
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

load_dotenv()
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(os.getenv("ADMIN_ID")), int(os.getenv("ADMIN_ID2"))]
PROMOTIONS_FILE = "/home/muxa/promotions.json"
USERS_FILE = "/home/muxa/users.json"

ASK_NAME, ASK_EMOJI, ASK_DISCOUNT, ASK_DATE = range(4)
ASK_MSG_ID, ASK_MSG_TEXT = range(4, 6)

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
    with open(PROMOTIONS_FILE, "w") as f:
        json.dump(promos, f, ensure_ascii=False, indent=2)

def get_user(user_id):
    try:
        with open(USERS_FILE, "r") as f:
            users = json.load(f)
        return users.get(str(user_id))
    except Exception:
        return None

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def send_to_user(user_id, text):
    async with aiohttp.ClientSession() as session:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        resp = await session.post(url, json={"chat_id": user_id, "text": text, "parse_mode": "Markdown"})
        return await resp.json()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return
    await update.message.reply_text(
        "👋 *ASOX Admin Bot*\n\n"
        "✅ Bot ishlayapti.\n\n"
        "📦 *Buyurtma xabarlari:*\n"
        "`/tayyor <id>` — buyurtma tayyor\n"
        "`/yetkazildi <id>` — yetkazib berildi\n"
        "`/bekor <id>` — buyurtma bekor qilindi\n"
        "`/xabar <id>` — foydalanuvchiga maxsus xabar\n\n"
        "🔥 *Aksiyalar:*\n"
        "`/aksiyalar` — ro'yxat\n"
        "`/aksiya_qush` — qo'shish\n"
        "`/aksiya_ochir <raqam>` — o'chirish",
        parse_mode="Markdown"
    )

async def get_user_info(user_id):
    saved = get_user(user_id)
    if saved:
        name = saved.get("name", "")
        phone = saved.get("phone", "")
        return name, phone
    return "", ""

async def tayyor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return
    if not context.args:
        await update.message.reply_text("❗ ID kiriting:\n`/tayyor 123456789`", parse_mode="Markdown")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❗ ID noto'g'ri.")
        return

    name, _ = await get_user_info(user_id)
    murojaat = f"hurmatli *{name}*" if name else "hurmatli mijoz"

    text = (
        f"✅ *Assalomu aleykum, {murojaat}!*\n\n"
        f"📦 Sizning buyurtmangiz tayyor!\n\n"
        f"🚚 *Yetkazib berish yoki olib ketish?*\n\n"
        f"1️⃣ *Yetkazib berish* — manzilingizni yuboring, tez orada yetkazamiz.\n"
        f"2️⃣ *O'zingiz olib ketish* — eng yaqin filialimizdan qulay vaqtda olib ketishingiz mumkin.\n\n"
        f"📞 Tanlash uchun operatorga yozing: @asoxmarket\n"
        f"📲 Yoki qo'ng'iroq qiling: +998 90 009 00 38\n\n"
        f"Rahmat! 🙏"
    )
    try:
        result = await send_to_user(user_id, text)
        if result.get("ok"):
            await update.message.reply_text(f"✅ {user_id} ga 'Buyurtma tayyor' xabari yuborildi.")
        else:
            await update.message.reply_text(f"❌ Xato: {result.get('description')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

async def yetkazildi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return
    if not context.args:
        await update.message.reply_text("❗ ID kiriting:\n`/yetkazildi 123456789`", parse_mode="Markdown")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❗ ID noto'g'ri.")
        return

    name, _ = await get_user_info(user_id)
    murojaat = f"hurmatli *{name}*" if name else "hurmatli mijoz"

    text = (
        f"🎉 *Assalomu aleykum, {murojaat}!*\n\n"
        f"✅ Buyurtmangiz yetkazib berildi!\n\n"
        f"💛 ASOX Market dan xarid qilganingiz uchun rahmat!\n"
        f"⭐ Fikr-mulohazangizni qoldiring: @asoxmarket"
    )
    try:
        result = await send_to_user(user_id, text)
        if result.get("ok"):
            await update.message.reply_text(f"✅ {user_id} ga 'Yetkazildi' xabari yuborildi.")
        else:
            await update.message.reply_text(f"❌ Xato: {result.get('description')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

async def bekor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return
    if not context.args:
        await update.message.reply_text("❗ ID kiriting:\n`/bekor 123456789`", parse_mode="Markdown")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❗ ID noto'g'ri.")
        return

    name, _ = await get_user_info(user_id)
    murojaat = f"hurmatli *{name}*" if name else "hurmatli mijoz"

    text = (
        f"ℹ️ *Assalomu aleykum, {murojaat}!*\n\n"
        f"❌ Afsuski, buyurtmangiz bekor qilindi.\n\n"
        f"📞 Sababi haqida ma'lumot olish uchun:\n"
        f"+998 90 009 00 38\n\n"
        f"Tushunganingiz uchun rahmat! 🙏"
    )
    try:
        result = await send_to_user(user_id, text)
        if result.get("ok"):
            await update.message.reply_text(f"✅ {user_id} ga 'Bekor qilindi' xabari yuborildi.")
        else:
            await update.message.reply_text(f"❌ Xato: {result.get('description')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

async def xabar_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return ConversationHandler.END
    if context.args:
        try:
            user_id = int(context.args[0])
            saved = get_user(user_id)
            name = saved.get("name", "") if saved else ""
            context.user_data["xabar_user_id"] = user_id
            info = f"👤 *{name}* (ID: `{user_id}`)" if name else f"ID: `{user_id}`"
            await update.message.reply_text(
                f"✍️ {info} ga yuboriladigan xabarni yozing:\n\n`/bekor_xabar` — bekor qilish",
                parse_mode="Markdown"
            )
            return ASK_MSG_TEXT
        except ValueError:
            pass
    await update.message.reply_text("✍️ Foydalanuvchi ID sini yozing:")
    return ASK_MSG_ID

async def ask_msg_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❗ Faqat raqam kiriting:")
        return ASK_MSG_ID
    saved = get_user(user_id)
    name = saved.get("name", "") if saved else ""
    context.user_data["xabar_user_id"] = user_id
    info = f"👤 *{name}* (ID: `{user_id}`)" if name else f"ID: `{user_id}`"
    await update.message.reply_text(
        f"✅ Topildi: {info}\n\n✍️ Xabar matnini yozing:\n\n`/bekor_xabar` — bekor qilish",
        parse_mode="Markdown"
    )
    return ASK_MSG_TEXT

async def ask_msg_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.user_data.get("xabar_user_id")
    matn = update.message.text.strip()
    saved = get_user(user_id)
    name = saved.get("name", "") if saved else ""
    murojaat = f"hurmatli *{name}*" if name else "hurmatli mijoz"

    text = f"📩 *Assalomu aleykum, {murojaat}!*\n\n{matn}\n\n— ASOX Market"
    try:
        result = await send_to_user(user_id, text)
        if result.get("ok"):
            await update.message.reply_text(f"✅ {user_id} ga xabar yuborildi.")
        else:
            await update.message.reply_text(f"❌ Xato: {result.get('description')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")
    return ConversationHandler.END

async def bekor_xabar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END

async def aksiyalar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return
    promos = load_promotions()
    if not promos:
        await update.message.reply_text("😔 Hozirda faol aksiyalar yo'q.\n\nQo'shish: /aksiya_qush")
        return
    lines = ["🔥 *Faol aksiyalar:*\n"]
    for i, p in enumerate(promos, 1):
        lines.append(f"{i}. {p['emoji']} *{p['name']}* — {p['discount']}\n   📅 Tugash: {p['end_date']}")
    lines.append("\n❌ O'chirish: `/aksiya_ochir <raqam>`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def aksiya_qush_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return ConversationHandler.END
    await update.message.reply_text(
        "➕ *Yangi aksiya qo'shish*\n\n1️⃣ Mahsulot nomini yozing:\n_(Masalan: T-shirt)_",
        parse_mode="Markdown"
    )
    return ASK_NAME

async def ask_aksiya_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_promo_name"] = update.message.text.strip()
    await update.message.reply_text("2️⃣ Emoji kiriting:\n_(Masalan: 👕)_")
    return ASK_EMOJI

async def ask_aksiya_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_promo_emoji"] = update.message.text.strip()
    await update.message.reply_text("3️⃣ Chegirma yozing:\n_(Masalan: 20% yoki 2 ta olsang 1 tasi bepul)_")
    return ASK_DISCOUNT

async def ask_aksiya_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_promo_discount"] = update.message.text.strip()
    await update.message.reply_text("4️⃣ Tugash sanasini kiriting:\n_(Masalan: 2026-08-31)_")
    return ASK_DATE

async def ask_aksiya_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_str = update.message.text.strip()
    try:
        date.fromisoformat(date_str)
    except ValueError:
        await update.message.reply_text("❗ Sana noto'g'ri. Yana kiriting:\n_(Masalan: 2026-08-31)_")
        return ASK_DATE
    promos = load_promotions()
    promos.append({
        "name": context.user_data["new_promo_name"],
        "emoji": context.user_data["new_promo_emoji"],
        "discount": context.user_data["new_promo_discount"],
        "end_date": date_str
    })
    save_promotions(promos)
    await update.message.reply_text(
        f"✅ *Aksiya qo'shildi!*\n\n"
        f"{context.user_data['new_promo_emoji']} *{context.user_data['new_promo_name']}* — {context.user_data['new_promo_discount']}\n"
        f"📅 Tugash: {date_str}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def aksiya_ochir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return
    if not context.args:
        await update.message.reply_text("❗ Raqam kiriting:\n`/aksiya_ochir 1`", parse_mode="Markdown")
        return
    try:
        idx = int(context.args[0]) - 1
    except ValueError:
        await update.message.reply_text("❗ Faqat raqam kiriting.")
        return
    promos = load_promotions()
    if idx < 0 or idx >= len(promos):
        await update.message.reply_text(f"❗ Bunday raqam yo'q. Jami {len(promos)} ta aksiya bor.")
        return
    removed = promos.pop(idx)
    save_promotions(promos)
    await update.message.reply_text(
        f"✅ O'chirildi:\n{removed['emoji']} *{removed['name']}* — {removed['discount']}",
        parse_mode="Markdown"
    )

def main():
    app = Application.builder().token(ADMIN_BOT_TOKEN).connect_timeout(30).read_timeout(30).build()

    xabar_conv = ConversationHandler(
        entry_points=[CommandHandler("xabar", xabar_start)],
        states={
            ASK_MSG_ID:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_msg_id)],
            ASK_MSG_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_msg_text)],
        },
        fallbacks=[CommandHandler("bekor_xabar", bekor_xabar)],
    )

    aksiya_conv = ConversationHandler(
        entry_points=[CommandHandler("aksiya_qush", aksiya_qush_start)],
        states={
            ASK_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_aksiya_name)],
            ASK_EMOJI:    [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_aksiya_emoji)],
            ASK_DISCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_aksiya_discount)],
            ASK_DATE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_aksiya_date)],
        },
        fallbacks=[CommandHandler("bekor_xabar", bekor_xabar)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tayyor", tayyor))
    app.add_handler(CommandHandler("yetkazildi", yetkazildi))
    app.add_handler(CommandHandler("bekor", bekor))
    app.add_handler(CommandHandler("aksiyalar", aksiyalar))
    app.add_handler(CommandHandler("aksiya_ochir", aksiya_ochir))
    app.add_handler(xabar_conv)
    app.add_handler(aksiya_conv)
    print("✅ Admin bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

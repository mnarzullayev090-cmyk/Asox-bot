import os
import aiohttp
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(os.getenv("ADMIN_ID")), int(os.getenv("ADMIN_ID2"))]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return
    await update.message.reply_text(
        "👋 *ASOX Admin Bot*\n\n"
        "✅ Bot ishlayapti.\n"
        "📩 Yangi foydalanuvchilar ro'yxatdan o'tganda shu yerga xabar keladi.\n\n"
        "📦 Buyurtmani tayyorlanganini bildirish:\n"
        "`/tayyor <user_id>`",
        parse_mode="Markdown"
    )

async def tayyor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return

    if not context.args:
        await update.message.reply_text(
            "❗ Foydalanuvchi ID sini kiriting:\n`/tayyor 123456789`",
            parse_mode="Markdown"
        )
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❗ ID noto'g'ri. Faqat raqam kiriting.")
        return

    text = "✅ *Sizning dizayningiz tayyor!*\n\nTez orada yetkazib beramiz. Rahmat!"

    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            resp = await session.post(url, json={
                "chat_id": user_id,
                "text": text,
                "parse_mode": "Markdown",
            })
            result = await resp.json()
            if result.get("ok"):
                await update.message.reply_text(f"✅ Foydalanuvchi {user_id} ga xabar yuborildi.")
            else:
                await update.message.reply_text(f"❌ Xato: {result.get('description')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

def main():
    app = Application.builder().token(ADMIN_BOT_TOKEN).connect_timeout(30).read_timeout(30).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tayyor", tayyor))
    print("✅ Admin bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

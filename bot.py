import os
import logging
import aiosqlite
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Logging setup
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
DATABASE_PATH = "bot.db"

ADMIN_UPLOAD_STATE = {}

# --- Database Setup ---
async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                service_name TEXT, 
                country TEXT,
                phone_number TEXT, 
                status TEXT DEFAULT 'Available'
            )
        """)
        await db.commit()

# --- Broadcast Function ---
async def send_broadcast(context: ContextTypes.DEFAULT_TYPE, text: str, keyboard=None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        users = await cursor.fetchall()
    
    for u in users:
        try:
            await context.bot.send_message(chat_id=u[0], text=text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            pass

# --- Keyboards ---
def main_menu(user_id):
    keyboard = [
        [KeyboardButton("📱 GET NUMBER"), KeyboardButton("🔎 SEARCH NUMBER")],
        [KeyboardButton("🚦 TRAFFIC"), KeyboardButton("👥 REFERRAL")],
        [KeyboardButton("💸 WITHDRAW"), KeyboardButton("🆘 SUPPORT")]
    ]
    if user_id == OWNER_ID:
        keyboard.append([KeyboardButton("👑 ADMIN PANEL")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()
    
    await update.message.reply_text(
        "🌐 *NUMBER PANEL*\n\nWelcome to Premium Number System.\n⚡ Fast • Simple • Secure",
        parse_mode="Markdown", reply_markup=main_menu(user_id)
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text if update.message.text else ""
    
    # ADMIN UPLOAD PROCESS
    if user_id == OWNER_ID and user_id in ADMIN_UPLOAD_STATE:
        state = ADMIN_UPLOAD_STATE[user_id]
        
        if state['step'] == "SERVICE":
            ADMIN_UPLOAD_STATE[user_id] = {"step": "COUNTRY", "service": text}
            await update.message.reply_text("🌍 এখন কান্ট্রির নাম লিখুন:")
            return
        elif state['step'] == "COUNTRY":
            ADMIN_UPLOAD_STATE[user_id] = {"step": "NUMBERS", "service": state['service'], "country": text}
            await update.message.reply_text("📂 এখন নাম্বারগুলো পেস্ট করুন:")
            return
        elif state['step'] == "NUMBERS":
            nums = [l.strip() for l in text.splitlines() if l.strip()]
            async with aiosqlite.connect(DATABASE_PATH) as db:
                for n in nums:
                    await db.execute("INSERT INTO numbers (service_name, country, phone_number) VALUES (?, ?, ?)", 
                                     (state['service'], state['country'], n))
                await db.commit()
            del ADMIN_UPLOAD_STATE[user_id]
            msg = f"🆕 *New Stock Added*\n\n🌍 {state['country']} | 📱 {state['service']}\n📦 Total: {len(nums)} Numbers"
            kbd = InlineKeyboardMarkup([[InlineKeyboardButton("📞 Get Number", url=f"https://t.me/{context.bot.username}")]])
            await send_broadcast(context, msg, kbd)
            await update.message.reply_text("✅ সফল!", reply_markup=main_menu(user_id))
            return

    # USER MENU
    if text == "📱 GET NUMBER":
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT service_name, country, phone_number FROM numbers WHERE status='Available' LIMIT 20") as cursor:
                rows = await cursor.fetchall()
        if not rows:
            await update.message.reply_text("⚠️ বর্তমানে কোনো স্টক নেই।")
        else:
            msg = "\n".join([f"🔹 *{r[0]}* ({r[1]}): `{r[2]}`" for r in rows])
            await update.message.reply_text(f"📱 *Available Numbers:*\n\n{msg}", parse_mode="Markdown")
    
    elif text == "👑 ADMIN PANEL" and user_id == OWNER_ID:
        ADMIN_UPLOAD_STATE[user_id] = {"step": "SERVICE"}
        await update.message.reply_text("⚙️ সার্ভিসের নাম লিখুন:")
    else:
        await start(update, context)

async def main():
    await init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, message_handler))
    print("Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())

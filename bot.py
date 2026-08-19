import os
import logging
import aiosqlite
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Logging setup
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# --- Database Setup ---
async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0.0,
                referred_by INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS force_channels (
                channel_username TEXT PRIMARY KEY,
                channel_title TEXT
            )
        """)
        await db.commit()

# --- Force Join Check ---
async def check_force_join(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT channel_username FROM force_channels") as cursor:
            channels = await cursor.fetchall()
    
    for (channel,) in channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            pass
    return True

# --- Reply Keyboards (Chat Box Keyboard) ---
def main_menu_keyboard(user_id: int):
    keyboard = [
        [KeyboardButton("📱 GET NUMBER"), KeyboardButton("🔎 SEARCH NUMBER")],
        [KeyboardButton("🚦 TRAFFIC"), KeyboardButton("👥 REFERRAL")],
        [KeyboardButton("💸 WITHDRAW"), KeyboardButton("🆘 SUPPORT")]
    ]
    if user_id == OWNER_ID:
        keyboard.append([KeyboardButton("👑 ADMIN PANEL")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def back_menu_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("🏠 Main Menu")]], resize_keyboard=True)

def admin_panel_keyboard():
    keyboard = [
        [KeyboardButton("📊 Overview"), KeyboardButton("📢 Broadcast")],
        [KeyboardButton("⚙️ Number Management"), KeyboardButton("👥 User Management")],
        [KeyboardButton("🔗 Force Join Setup"), KeyboardButton("🏠 Main Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username))
        await db.commit()

    # Check Force Join
    is_joined = await check_force_join(user.id, context)
    if not is_joined:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [[InlineKeyboardButton("📢 Join Channel", url="https://t.me/YourChannelName")],
                    [InlineKeyboardButton("✅ Joined / Check", callback_data="check_join")]]
        await update.message.reply_text("⚠️ Please join our update channel first to use this bot!", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    welcome_text = (
        f"🌐 **NUMBER PANEL**\n\n"
        f"👋 Welcome, **{user.first_name}**\n"
        f"🚀 Premium Number Management System\n\n"
        f"📱 Manage your available numbers\n"
        f"🌍 Browse services & countries\n"
        f"💰 Balance & referral management\n\n"
        f"⚡ Fast • Simple • Secure"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=main_menu_keyboard(user.id))

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text in ["🏠 Main Menu", "/start"]:
        await start(update, context)
    
    elif text == "📱 GET NUMBER":
        await update.message.reply_text("📱 **Get Number Menu**\nSelect your service below:", parse_mode="Markdown", reply_markup=back_menu_keyboard())
    
    elif text == "🔎 SEARCH NUMBER":
        await update.message.reply_text("🔎 Send the number or country code you want to search.", reply_markup=back_menu_keyboard())
    
    elif text == "🚦 TRAFFIC":
        await update.message.reply_text("🚦 Traffic & Status overview.", reply_markup=back_menu_keyboard())
    
    elif text == "👥 REFERRAL":
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        await update.message.reply_text(f"👥 **Referral System**\n\nShare this link to earn:\n`{ref_link}`", parse_mode="Markdown", reply_markup=back_menu_keyboard())
    
    elif text == "💸 WITHDRAW":
        await update.message.reply_text("💸 Your current balance is insufficient for withdrawal.", reply_markup=back_menu_keyboard())
    
    elif text == "🆘 SUPPORT":
        await update.message.reply_text("🆘 For any support, contact admin directly.", reply_markup=back_menu_keyboard())

    elif text == "👑 ADMIN PANEL" and user_id == OWNER_ID:
        await update.message.reply_text("👑 **Admin Control Panel**", parse_mode="Markdown", reply_markup=admin_panel_keyboard())
    
    elif text == "📊 Overview" and user_id == OWNER_ID:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                total_users = (await cursor.fetchone())[0]
        await update.message.reply_text(f"📊 **Database Overview**\n\nTotal Users: `{total_users}`", parse_mode="Markdown", reply_markup=admin_panel_keyboard())

async def main():
    await init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    # Set Menu Button (/start command) in the left 3-lines menu
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot & Open Menu")
    ])

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("Bot is running...")
    
    async def main_runner():
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        stop_signal = asyncio.Event()
        try:
            await stop_signal.wait()
        finally:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()

    import asyncio
    try:
        await main_runner()
    except (KeyboardInterrupt, RuntimeError):
        pass

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

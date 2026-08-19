import os
import logging
import aiosqlite
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Logging setup
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# --- Database ---
async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT)")
        await db.commit()

# --- Reply Keyboards ---
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
        [KeyboardButton("🏠 Main Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username))
        await db.commit()

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

    if text == "/start" or text == "🏠 Main Menu":
        await start(update, context)
        
    elif text == "📱 GET NUMBER":
        await update.message.reply_text(
            "📱 **Get Number Menu**\n\n"
            "আমাদের সিস্টেমে বর্তমানে বিভিন্ন দেশের নাম্বার এভেইলেবল আছে।\n"
            "সার্ভিস সিলেক্ট করার অপশন খুব শীঘ্রই যুক্ত করা হচ্ছে।",
            parse_mode="Markdown",
            reply_markup=back_menu_keyboard()
        )
        
    elif text == "🔎 SEARCH NUMBER":
        await update.message.reply_text(
            "🔎 আপনি যে নাম্বার বা কান্ট্রি কোড খুঁজতে চান তা লিখে পাঠান:",
            reply_markup=back_menu_keyboard()
        )
        
    elif text == "🚦 TRAFFIC":
        await update.message.reply_text(
            "🚦 সিস্টেমের বর্তমান ট্রাফিক ও স্ট্যাটাস স্বাভাবিক আছে।",
            reply_markup=back_menu_keyboard()
        )
        
    elif text == "👥 REFERRAL":
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        await update.message.reply_text(
            f"👥 **Referral System**\n\n"
            f"আপনার রেফাল লিংকটি বন্ধুদের সাথে শেয়ার করুন:\n`{ref_link}`",
            parse_mode="Markdown",
            reply_markup=back_menu_keyboard()
        )
        
    elif text == "💸 WITHDRAW":
        await update.message.reply_text(
            "💸 আপনার বর্তমান ব্যালেন্স অপর্যাপ্ত। উইথড্র করতে মিনিমাম ব্যালেন্স প্রয়োজন।",
            reply_markup=back_menu_keyboard()
        )
        
    elif text == "🆘 SUPPORT":
        await update.message.reply_text(
            "🆘 কোনো সমস্যায় পড়লে সরাসরি এডমিনের সাথে যোগাযোগ করুন।",
            reply_markup=back_menu_keyboard()
        )
        
    elif text == "👑 ADMIN PANEL" and user_id == OWNER_ID:
        await update.message.reply_text(
            "👑 **Admin Control Panel**\nনিচের অপশনগুলো থেকে ম্যানেজ করুন:",
            parse_mode="Markdown",
            reply_markup=admin_panel_keyboard()
        )
        
    elif text == "📊 Overview" and user_id == OWNER_ID:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                total_users = (await cursor.fetchone())[0]
        await update.message.reply_text(
            f"📊 **Database Overview**\n\nTotal Registered Users: `{total_users}`",
            parse_mode="Markdown",
            reply_markup=admin_panel_keyboard()
        )
        
    elif text in ["📢 Broadcast", "⚙️ Number Management", "👥 User Management"] and user_id == OWNER_ID:
        await update.message.reply_text(
            f"⚙️ `{text}` ফিচারটি ডেভেলপমেন্ট পর্যায়ে রয়েছে।",
            parse_mode="Markdown",
            reply_markup=admin_panel_keyboard()
        )
        
    else:
        await update.message.reply_text("দয়া করে নিচের বাটনগুলো ব্যবহার করুন অথবা /start দিন।")

async def main():
    await init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    # Menu Button setup
    await application.bot.set_my_commands([BotCommand("start", "Start the bot")])

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("Bot is running...")
    
    async def main_runner():
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        stop_signal = asyncio.Event()
        await stop_signal.wait()

    try:
        await main_runner()
    except (KeyboardInterrupt, RuntimeError):
        pass

if __name__ == "__main__":
    asyncio.run(main())

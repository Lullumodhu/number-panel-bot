import os
import logging
import aiosqlite
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

# Logging setup
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# --- Permanent Links & Info ---
MAIN_CHANNEL_URL = "https://t.me/Zentrix_Officiall"
MAIN_CHANNEL_ID = "@Zentrix_Officiall"  # ইউজারনেম বা আইডি (এডমিন থাকতে হবে)

UPDATE_CHANNEL_URL = "https://t.me/Zentrix_Update"
UPDATE_CHANNEL_ID = "@Zentrix_Update"

OTP_GROUP_URL = "https://t.me/+pBpZWtQC4qswODI1"
OTP_GROUP_ID = "-100..." # প্রাইভেট গ্রুপের ক্ষেত্রে গ্রুপ আইডি বসাতে হয়, তবে আপাতত ইউজারনেম চেক মেথড ব্যবহার করা হচ্ছে

SUPPORT_ADMIN = "@ranaXvou"

# --- Database ---
async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT)")
        await db.commit()

# --- Force Join Check Function (Multiple Channels/Groups) ---
async def check_force_join(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    channels_to_check = [
        ("Main Channel", MAIN_CHANNEL_ID, MAIN_CHANNEL_URL),
        ("Update Channel", UPDATE_CHANNEL_ID, UPDATE_CHANNEL_URL)
    ]
    
    for name, chat_id, url in channels_to_check:
        try:
            # বট যদি চ্যানেলে এডমিন না থাকে বা ভুল আইডি হয়, তবে এরর হ্যান্ডেল করার জন্য try-except
            member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception as e:
            logger.info(f"Could not check chat {chat_id}: {e}")
            # যদি প্রাইভেট গ্রুপ বা চ্যাট আইডি কনফিগারেশনের কারণে চেক না করা যায়, ট্রু রিটার্ন করবে যাতে বট আটকে না যায়
            pass
            
    return True

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
    
    # Force Join Check (প্রতিবার কমান্ড দিলে চেক করবে, লিভ নিলে আটকে দিবে)
    is_joined = await check_force_join(user.id, context)
    if not is_joined:
        keyboard = [
            [InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_URL)],
            [InlineKeyboardButton("📢 Join Update Channel", url=UPDATE_CHANNEL_URL)],
            [InlineKeyboardButton("💬 Join OTP Group", url=OTP_GROUP_URL)],
            [InlineKeyboardButton("✅ Joined / Check", callback_data="check_join")]
        ]
        await update.message.reply_text(
            "⚠️ **বটটি ব্যবহার করতে হলে অবশ্যই আমাদের চ্যানেল এবং গ্রুপগুলোতে জয়েন থাকতে হবে!**\n\n"
            "দয়া করে নিচের লিংকগুলোতে জয়েন করে তারপর **'Joined / Check'** বাটনে চাপুন।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

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

# Inline Callback Handler for Force Join Check Button
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "check_join":
        is_joined = await check_force_join(user_id, context)
        if is_joined:
            try:
                await query.message.delete()
            except Exception:
                pass
                
            user = query.from_user
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username))
                await db.commit()
            
            welcome_text = (
                f"🌐 **NUMBER PANEL**\n\n"
                f"👋 Welcome, **{user.first_name}**\n"
                f"🚀 Premium Number Management System\n\n"
                f"⚡ Fast • Simple • Secure"
            )
            await context.bot.send_message(chat_id=user_id, text=welcome_text, parse_mode="Markdown", reply_markup=main_menu_keyboard(user_id))
        else:
            await query.answer("❌ আপনি এখনো সবকটি চ্যানেল বা গ্রুপে জয়েন করেননি!", show_alert=True)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # কোনো বাটন চাপলেও আগে ফোর্স জয়েন চেক করবে, যাতে লিভ নিলেও ধরা খায়
    is_joined = await check_force_join(user_id, context)
    if not is_joined and text != "/start" and text != "🏠 Main Menu":
        keyboard = [
            [InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_URL)],
            [InlineKeyboardButton("📢 Join Update Channel", url=UPDATE_CHANNEL_URL)],
            [InlineKeyboardButton("💬 Join OTP Group", url=OTP_GROUP_URL)],
            [InlineKeyboardButton("✅ Joined / Check", callback_data="check_join")]
        ]
        await update.message.reply_text(
            "⚠️ আপনি চ্যানেল বা গ্রুপ থেকে লিভ নিয়েছেন! দয়া করে আবার জয়েন করুন:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if text == "/start" or text == "🏠 Main Menu":
        await start(update, context)
        
    elif text == "📱 GET NUMBER":
        await update.message.reply_text(
            f"📱 **Get Number Menu**\n\n"
            f"🔗 Main Channel: {MAIN_CHANNEL_URL}\n"
            f"💬 OTP Group: {OTP_GROUP_URL}\n\n"
            f"সার্ভিস থেকে নাম্বার নিতে উপরোক্ত গ্রুপ ও চ্যানেল ফলো করুন।",
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
            f"🚦 সিস্টেমের বর্তমান ট্রাফিক স্বাভাবিক আছে।\n\nঅফিশিয়াল আপডেট পেতে ভিজিট করুন: {UPDATE_CHANNEL_URL}",
            parse_mode="Markdown",
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
            f"🆘 কোনো সমস্যায় পড়লে সরাসরি এডমিনের সাথে যোগাযোগ করুন:\n\n"
            f"👤 Support Admin: {SUPPORT_ADMIN}\n"
            f"💬 OTP Discussion Group: {OTP_GROUP_URL}",
            parse_mode="Markdown",
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
    application.add_handler(CallbackQueryHandler(callback_handler))
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

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
MAIN_CHANNEL_ID = "@Zentrix_Officiall"

UPDATE_CHANNEL_URL = "https://t.me/Zentrix_Update"
UPDATE_CHANNEL_ID = "@Zentrix_Update"

OTP_GROUP_URL = "https://t.me/+pBpZWtQC4qswODI1"
SUPPORT_ADMIN = "@ranaXvou"

# Temporary dictionary to track admin state for uploading numbers
ADMIN_UPLOAD_STATE = {}

# --- Database Setup ---
async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT)")
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

# --- Force Join Check Function ---
async def check_force_join(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    channels_to_check = [
        ("Main Channel", MAIN_CHANNEL_ID),
        ("Update Channel", UPDATE_CHANNEL_ID)
    ]
    
    for name, chat_id in channels_to_check:
        try:
            member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
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
            "দয়া করে নিচের লিংকগুলোতে জয়েন করুন এবং তারপর **'Joined / Check'** বাটনে চাপুন।",
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
    user_id = query.from_user.id

    is_joined = await check_force_join(user_id, context)
    if is_joined:
        await query.answer("✅ ধন্যবাদ! সফলভাবে ভেরিফাই করা হয়েছে।", show_alert=False)
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
        await query.answer("❌ আপনি এখনো সবকটি চ্যানেল বা গ্রুপে জয়েন করেননি! দয়া করে আগে জয়েন করুন।", show_alert=True)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    is_joined = await check_force_join(user_id, context)
    if not is_joined and text != "/start" and text != "🏠 Main Menu":
        keyboard = [
            [InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_URL)],
            [InlineKeyboardButton("📢 Join Update Channel", url=UPDATE_CHANNEL_URL)],
            [InlineKeyboardButton("💬 Join OTP Group", url=OTP_GROUP_URL)],
            [InlineKeyboardButton("✅ Joined / Check", callback_data="check_join")]
        ]
        await update.message.reply_text(
            "⚠️ আপনি চ্যানেল বা গ্রুপ থেকে লিভ নিয়েছেন!\nবট ব্যবহার করতে হলে আবার জয়েন করে **'Joined / Check'** বাটনে চাপুন:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Check if Admin is in the middle of uploading numbers via text/file
    if user_id == OWNER_ID and user_id in ADMIN_UPLOAD_STATE:
        state = ADMIN_UPLOAD_STATE[user_id]
        
        if state == "WAITING_FOR_DETAILS":
            # Expected format: ServiceName | CountryName
            parts = text.split("|")
            if len(parts) < 2:
                await update.message.reply_text("❌ সঠিক ফরম্যাটে দিন!\nব্যবহার: `Service Name | Country`\nউদাহরণ: `Telegram | USA`", parse_mode="Markdown")
                return
            
            service_name = parts[0].strip()
            country = parts[1].strip()
            
            ADMIN_UPLOAD_STATE[user_id] = {"state": "WAITING_FOR_NUMBERS", "service": service_name, "country": country}
            await update.message.reply_text(
                f"✅ সার্ভিস: `{service_name}` এবং কান্ট্রি: `{country}` সেট হয়েছে।\n\n"
                "اب আপনি একসাথে যতখুশি **নম্বরগুলো পেস্ট করুন** (প্রতি লাইনে একটি করে নাম্বার) অথবা একটি `.txt` ফাইল আপলোড করুন।",
                parse_mode="Markdown"
            )
            return
            
        elif isinstance(state, dict) and state.get("state") == "WAITING_FOR_NUMBERS":
            service_name = state["service"]
            country = state["country"]
            
            # Process text lines of numbers
            numbers_list = [line.strip() for line in text.split("\n") if line.strip()]
            
            if not numbers_list:
                await update.message.reply_text("❌ কোনো নাম্বার পাওয়া যায়নি। দয়া করে সঠিক লাইনে নাম্বারগুলো পেস্ট করুন।")
                return
                
            async with aiosqlite.connect(DATABASE_PATH) as db:
                for num in numbers_list:
                    await db.execute(
                        "INSERT INTO numbers (service_name, country, phone_number, status) VALUES (?, ?, ?, 'Available')",
                        (service_name, country, num)
                    )
                await db.commit()
                
            del ADMIN_UPLOAD_STATE[user_id]
            await update.message.reply_text(
                f"🎉 সফলভাবে **{len(numbers_list)}টি** নাম্বার স্টক এ যুক্ত করা হয়েছে!\n\n"
                f"🔹 সার্ভিস: `{service_name}`\n"
                f"🌍 কান্ট্রি: `{country}`",
                parse_mode="Markdown",
                reply_markup=admin_panel_keyboard()
            )
            return

    # Document / File Upload Handler for Bulk Numbers
    if user_id == OWNER_ID and update.message.document and user_id in ADMIN_UPLOAD_STATE:
        state = ADMIN_UPLOAD_STATE[user_id]
        if isinstance(state, dict) and state.get("state") == "WAITING_FOR_NUMBERS":
            service_name = state["service"]
            country = state["country"]
            
            doc = update.message.document
            file = await context.bot.get_file(doc.file_id)
            file_path = "temp_numbers.txt"
            await file.download_to_drive(file_path)
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            if os.path.exists(file_path):
                os.remove(file_path)
                
            numbers_list = [line.strip() for line in content.split("\n") if line.strip()]
            
            if not numbers_list:
                await update.message.reply_text("❌ ফাইলটি খালি রয়েছে বা সঠিক ফরম্যাটে নেই।")
                return
                
            async with aiosqlite.connect(DATABASE_PATH) as db:
                for num in numbers_list:
                    await db.execute(
                        "INSERT INTO numbers (service_name, country, phone_number, status) VALUES (?, ?, ?, 'Available')",
                        (service_name, country, num)
                    )
                await db.commit()
                
            del ADMIN_UPLOAD_STATE[user_id]
            await update.message.reply_text(
                f"🎉 ফাইল থেকে সফলভাবে **{len(numbers_list)}টি** নাম্বার স্টক এ যুক্ত করা হয়েছে!\n\n"
                f"🔹 সার্ভিস: `{service_name}`\n"
                f"🌍 কান্ট্রি: `{country}`",
                parse_mode="Markdown",
                reply_markup=admin_panel_keyboard()
            )
            return

    if text == "/start" or text == "🏠 Main Menu":
        # Clear any pending upload state
        if user_id in ADMIN_UPLOAD_STATE:
            del ADMIN_UPLOAD_STATE[user_id]
        await start(update, context)
        
    elif text == "📱 GET NUMBER":
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT service_name, country, phone_number FROM numbers WHERE status='Available'") as cursor:
                numbers = await cursor.fetchall()
        
        if numbers:
            num_list = "\n".join([f"🔹 *{row[0]}* ({row[1]}): `{row[2]}`" for row in numbers[:20]]) # বেশি হলে প্রথম ২০টি দেখাবে
            response_text = f"📱 **Available Numbers (Stock):**\n\n{num_list}\n\n🔗 Main Channel: {MAIN_CHANNEL_URL}\n💬 OTP Group: {OTP_GROUP_URL}"
        else:
            response_text = (
                f"📱 **Get Number Menu**\n\n"
                f"⚠️ বর্তমানে কোনো নাম্বার স্টক এ নেই!\n\n"
                f"🔗 Main Channel: {MAIN_CHANNEL_URL}\n"
                f"💬 OTP Group: {OTP_GROUP_URL}"
            )
        
        await update.message.reply_text(response_text, parse_mode="Markdown", reply_markup=back_menu_keyboard())
        
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
        if user_id in ADMIN_UPLOAD_STATE:
            del ADMIN_UPLOAD_STATE[user_id]
        await update.message.reply_text(
            "👑 **Admin Control Panel**\nনিচের অপশনগুলো থেকে ম্যানেজ করুন:",
            parse_mode="Markdown",
            reply_markup=admin_panel_keyboard()
        )
        
    elif text == "📊 Overview" and user_id == OWNER_ID:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                total_users = (await cursor.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM numbers WHERE status='Available'") as cursor:
                total_nums = (await cursor.fetchone())[0]
                
        await update.message.reply_text(
            f"📊 **Database Overview**\n\n"
            f"👥 Total Registered Users: `{total_users}`\n"
            f"📱 Available Numbers: `{total_nums}`",
            parse_mode="Markdown",
            reply_markup=admin_panel_keyboard()
        )
        
    elif text == "⚙️ Number Management" and user_id == OWNER_ID:
        # Bulk Upload Process Start
        ADMIN_UPLOAD_STATE[user_id] = "WAITING_FOR_DETAILS"
        await update.message.reply_text(
            "⚙️ **Bulk Number Upload System**\n\n"
            "প্রথমে কোন সার্ভিসের জন্য এবং কোন দেশের নাম্বার আপলোড করবেন তা এই ফরম্যাটে লিখে পাঠান:\n\n"
            "`Service Name | Country`\n\n"
            "উদাহরণ:\n`Telegram | USA`\n`WhatsApp | India`",
            parse_mode="Markdown",
            reply_markup=back_menu_keyboard()
        )
        
    elif text in ["📢 Broadcast", "👥 User Management"] and user_id == OWNER_ID:
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
    # Document handler for file uploads
    application.add_handler(MessageHandler(filters.Document.ALL, message_handler))

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

import os
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import motor.motor_asyncio

# Logging setup
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# --- MongoDB Setup ---
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client.zentrix_bot
users_col = db.users
numbers_col = db.numbers

# --- Permanent Links & Info ---
MAIN_CHANNEL_URL = "https://t.me/Zentrix_Officiall"
MAIN_CHANNEL_ID = "@Zentrix_Officiall"

UPDATE_CHANNEL_URL = "https://t.me/Zentrix_Update"
UPDATE_CHANNEL_ID = "@Zentrix_Update"

OTP_GROUP_URL = "https://t.me/+pBpZWtQC4qswODI1"
SUPPORT_ADMIN = "@ranaXvou"

# Temporary dictionary to track admin state for multi-step uploading
ADMIN_UPLOAD_STATE = {}

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

# --- Broadcast Function to All Users ---
async def send_broadcast_to_all(context: ContextTypes.DEFAULT_TYPE, message_text: str, keyboard=None):
    async for user_row in users_col.find({}):
        user_id = user_row["user_id"]
        try:
            await context.bot.send_message(
                chat_id=user_id, 
                text=message_text, 
                parse_mode="Markdown", 
                reply_markup=keyboard
            )
            await asyncio.sleep(0.03)
        except Exception as e:
            logging.info(f"Could not send message to {user_id}: {e}")

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

def back_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("🔙 Back")]], resize_keyboard=True)

def admin_panel_keyboard():
    keyboard = [
        [KeyboardButton("📊 Overview"), KeyboardButton("📢 Broadcast")],
        [KeyboardButton("⚙️ Number Management"), KeyboardButton("👥 User Management")],
        [KeyboardButton("🔙 Back")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id in ADMIN_UPLOAD_STATE:
        del ADMIN_UPLOAD_STATE[user.id]

    await users_col.update_one(
        {"user_id": user.id},
        {"$set": {"username": user.username}},
        upsert=True
    )

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

# Inline Callback Handler
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == "check_join":
        is_joined = await check_force_join(user_id, context)
        if is_joined:
            await query.answer("✅ ধন্যবাদ! সফলভাবে ভেরিফাই করা হয়েছে.", show_alert=False)
            try:
                await query.message.delete()
            except Exception:
                pass
                
            user = query.from_user
            await users_col.update_one(
                {"user_id": user.id},
                {"$set": {"username": user.username}},
                upsert=True
            )
            
            welcome_text = (
                f"🌐 **NUMBER PANEL**\n\n"
                f"👋 Welcome, **{user.first_name}**\n"
                f"🚀 Premium Number Management System\n\n"
                f"⚡ Fast • Simple • Secure"
            )
            await context.bot.send_message(chat_id=user_id, text=welcome_text, parse_mode="Markdown", reply_markup=main_menu_keyboard(user_id))
        else:
            await query.answer("❌ আপনি এখনো সবকটি চ্যানেল বা গ্রুপে জয়েন করেননি! দয়া করে আগে জয়েন করুন।", show_alert=True)

    # 1. Get Number Menu -> Show Services List
    elif query.data in ["get_stock_click", "get_number_menu"]:
        await query.answer()
        services = await numbers_col.distinct("service_name", {"status": "Available"})
        
        if services:
            keyboard = []
            for serv in services:
                keyboard.append([InlineKeyboardButton(f"📱 {serv}", callback_data=f"sel_serv:{serv}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            text_msg = "📱 Select a Service:"
        else:
            reply_markup = None
            text_msg = (
                f"📱 Get Number Menu\n\n"
                f"⚠️ বর্তমানে কোনো নাম্বার স্টক এ নেই!\n\n"
                f"🔗 Main Channel: {MAIN_CHANNEL_URL}\n"
                f"💬 OTP Group: {OTP_GROUP_URL}"
            )
        
        try:
            await query.message.edit_text(text_msg, reply_markup=reply_markup)
        except Exception:
            await query.message.reply_text(text_msg, reply_markup=reply_markup)

    # 2. Click Service -> Show Countries List for that Service
    elif query.data.startswith("sel_serv:"):
        await query.answer()
        service_name = query.data.split(":", 1)[1].strip()
        
        countries = await numbers_col.distinct("country", {"service_name": service_name, "status": "Available"})
        
        if countries:
            keyboard = []
            for country in countries:
                keyboard.append([InlineKeyboardButton(f"🌍 {country}", callback_data=f"sel_count:{service_name}:{country}")])
            keyboard.append([InlineKeyboardButton("🔙 Back to Services", callback_data="get_number_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            text_msg = f"🌍 Select Country for '{service_name}':"
        else:
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Services", callback_data="get_number_menu")]])
            text_msg = f"⚠️ '{service_name}' সার্ভিসে বর্তমানে কোনো কান্ট্রি এভেইলেবল নেই!"
        
        try:
            await query.message.edit_text(text_msg, reply_markup=reply_markup)
        except Exception:
            await query.message.reply_text(text_msg, reply_markup=reply_markup)

    # 3. Click Country -> Show Numbers for that Service & Country (Fixed & Crash-Free)
    elif query.data.startswith("sel_count:"):
        await query.answer()
        parts = query.data.split(":", 2)
        if len(parts) >= 3:
            service_name = parts[1].strip()
            country = parts[2].strip()
        else:
            service_name = "Unknown"
            country = "Unknown"
        
        cursor = numbers_col.find({
            "service_name": {"$regex": f"^{service_name}$", "$options": "i"},
            "country": {"$regex": f"^{country}$", "$options": "i"},
            "status": "Available"
        })
        numbers = await cursor.to_list(length=100)
        
        if numbers:
            num_list = "\n".join([f"🔹 {row['phone_number']}" for row in numbers])
            text_msg = f"📱 Available Numbers ({service_name} - {country}):\n\n{num_list}\n\n🔗 Main Channel: {MAIN_CHANNEL_URL}"
        else:
            text_msg = f"⚠️ দুঃখিত! {service_name} ({country}) এ বর্তমানে কোনো নাম্বার এভেইলেবল নেই।"
            
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Countries", callback_data=f"sel_serv:{service_name}")]])
        
        try:
            await query.message.edit_text(text_msg, reply_markup=reply_markup)
        except Exception:
            await query.message.reply_text(text_msg, reply_markup=reply_markup)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text if update.message.text else ""

    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"username": update.effective_user.username}},
        upsert=True
    )

    # --- Back Button Logic ---
    if text == "🔙 Back":
        if user_id in ADMIN_UPLOAD_STATE:
            del ADMIN_UPLOAD_STATE[user_id]
            if user_id == OWNER_ID:
                await update.message.reply_text("👑 **Admin Control Panel**", parse_mode="Markdown", reply_markup=admin_panel_keyboard())
                return
        
        await update.message.reply_text("👇 Main Menu:", reply_markup=main_menu_keyboard(user_id))
        return

    is_joined = await check_force_join(user_id, context)
    if not is_joined and text != "/start":
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

    # --- Step-by-Step Admin Upload Flow (Text Numbers) ---
    if user_id == OWNER_ID and user_id in ADMIN_UPLOAD_STATE:
        state_data = ADMIN_UPLOAD_STATE[user_id]
        current_step = state_data.get("step")

        if current_step == "GET_SERVICE":
            service_name = text.strip()
            if not service_name:
                await update.message.reply_text("❌ সার্ভিসের নাম খালি রাখা যাবে না। সঠিক নাম লিখে পাঠান:")
                return
            
            ADMIN_UPLOAD_STATE[user_id] = {"step": "GET_COUNTRY", "service": service_name}
            await update.message.reply_text(
                f"✅ সার্ভিস সিলেক্ট হয়েছে: `{service_name}`\n\n"
                "🌍 এখন কান্ট্রির নাম বা কোড লিখে পাঠান (যেমন: `USA` বা `Malaysia`):",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
            return

        elif current_step == "GET_COUNTRY":
            country = text.strip()
            if not country:
                await update.message.reply_text("❌ কান্ট্রির নাম খালি রাখা যাবে না। সঠিক নাম লিখে পাঠান:")
                return
            
            service_name = state_data["service"]
            ADMIN_UPLOAD_STATE[user_id] = {"step": "GET_NUMBERS", "service": service_name, "country": country}
            await update.message.reply_text(
                f"✅ সার্ভিস: `{service_name}` | কান্ট্রি: `{country}`\n\n"
                "📂 এখন আপনার `.txt` ফাইলটি আপলোড করুন অথবা একসাথে নাম্বারগুলো কপি করে চ্যাটে পেস্ট করে দিন:",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
            return

        elif current_step == "GET_NUMBERS" and text:
            service_name = state_data["service"]
            country = state_data["country"]
            
            numbers_list = [line.strip() for line in text.split("\n") if line.strip()]
            if not numbers_list:
                await update.message.reply_text("❌ কোনো নাম্বার পাওয়া যায়নি। সঠিক লাইনে নাম্বারগুলো পেস্ট করুন বা ফাইল দিন।")
                return
                
            docs = [{"service_name": service_name, "country": country, "phone_number": num, "status": "Available"} for num in numbers_list]
            await numbers_col.insert_many(docs)
                
            del ADMIN_UPLOAD_STATE[user_id]
            
            broadcast_notification = (
                f"🆕 **New Stock Added** 🔵\n\n"
                f"🌍 `{country}` | 📱 `{service_name}`\n"
                f"📦 **TOTAL :** `{len(numbers_list)}` Numbers\n"
                f"💵 **OTP Price :** `0.0$`"
            )
            keyboard_broadcast = InlineKeyboardMarkup([[InlineKeyboardButton("📞 Get Number", callback_data="get_stock_click")]])
            
            await send_broadcast_to_all(context, broadcast_notification, keyboard_broadcast)

            await update.message.reply_text(
                f"🎉 সফলভাবে **{len(numbers_list)}টি** নাম্বার স্টক এ যুক্ত করা হয়েছে এবং ব্রডকাস্ট পাঠানো হয়েছে!\n\n"
                f"🔹 সার্ভিস: `{service_name}`\n"
                f"🌍 কান্ট্রি: `{country}`",
                parse_mode="Markdown",
                reply_markup=admin_panel_keyboard()
            )
            return

    # --- Handle Document (.txt file) Upload in Step 3 ---
    if user_id == OWNER_ID and update.message.document and user_id in ADMIN_UPLOAD_STATE:
        state_data = ADMIN_UPLOAD_STATE[user_id]
        if state_data.get("step") == "GET_NUMBERS":
            service_name = state_data["service"]
            country = state_data["country"]
            
            doc = update.message.document
            file = await context.bot.get_file(doc.file_id)
            file_path = f"temp_{user_id}.txt"
            await file.download_to_drive(file_path)
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                with open(file_path, "r", encoding="latin-1") as f:
                    content = f.read()
                    
            if os.path.exists(file_path):
                os.remove(file_path)
                
            numbers_list = [line.strip() for line in content.split("\n") if line.strip()]
            if not numbers_list:
                await update.message.reply_text("❌ ফাইলটি খালি রয়েছে বা সঠিক ফরম্যাটে নেই।")
                return
                
            docs = [{"service_name": service_name, "country": country, "phone_number": num, "status": "Available"} for num in numbers_list]
            await numbers_col.insert_many(docs)
                
            del ADMIN_UPLOAD_STATE[user_id]
            
            broadcast_notification = (
                f"🆕 **New Stock Added** 🔵\n\n"
                f"🌍 `{country}` | 📱 `{service_name}`\n"
                f"📦 **TOTAL :** `{len(numbers_list)}` Numbers\n"
                f"💵 **OTP Price :** `0.0$`"
            )
            keyboard_broadcast = InlineKeyboardMarkup([[InlineKeyboardButton("📞 Get Number", callback_data="get_stock_click")]])
            
            await send_broadcast_to_all(context, broadcast_notification, keyboard_broadcast)

            await update.message.reply_text(
                f"🎉 ফাইল থেকে সফলভাবে **{len(numbers_list)}টি** নাম্বার স্টক এ যুক্ত করা হয়েছে এবং সকল ইউজারের কাছে ব্রডকাস্ট পাঠানো হয়েছে!\n\n"
                f"🔹 সার্ভিস: `{service_name}`\n"
                f"🌍 কান্ট্রি: `{country}`",
                parse_mode="Markdown",
                reply_markup=admin_panel_keyboard()
            )
            return

    # --- Main Menu Options ---
    if text == "/start":
        await start(update, context)
        
    elif text == "📱 GET NUMBER":
        services = await numbers_col.distinct("service_name", {"status": "Available"})
        
        if services:
            keyboard = []
            for serv in services:
                keyboard.append([InlineKeyboardButton(f"📱 {serv}", callback_data=f"sel_serv:{serv}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            text_msg = "📱 Select a Service:"
        else:
            reply_markup = None
            text_msg = (
                f"📱 Get Number Menu\n\n"
                f"⚠️ বর্তমানে কোনো নাম্বার স্টক এ নেই!\n\n"
                f"🔗 Main Channel: {MAIN_CHANNEL_URL}\n"
                f"💬 OTP Group: {OTP_GROUP_URL}"
            )
        
        await update.message.reply_text(text_msg, reply_markup=reply_markup)
        
    elif text == "🔎 SEARCH NUMBER":
        await update.message.reply_text(
            "🔎 আপনি যে নাম্বার বা কান্ট্রি কোড খুঁজতে চান তা লিখে পাঠান:",
            reply_markup=back_keyboard()
        )
        
    elif text == "🚦 TRAFFIC":
        await update.message.reply_text(
            f"🚦 সিস্টেমের বর্তমান ট্রাফিক স্বাভাবিক আছে।\n\nঅফিশিয়াল আপডেট পেতে ভিজিট করুন: {UPDATE_CHANNEL_URL}",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(user_id)
        )
        
    elif text == "👥 REFERRAL":
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        await update.message.reply_text(
            f"👥 **Referral System**\n\n"
            f"আপনার রেফাল লিংকটি বন্ধুদের সাথে শেয়ার করুন:\n`{ref_link}`",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(user_id)
        )
        
    elif text == "💸 WITHDRAW":
        await update.message.reply_text(
            "💸 আপনার বর্তমান ব্যালেন্স অপর্যাপ্ত। উইথড্র করতে মিনিমাম ব্যালেন্স প্রয়োজন।",
            reply_markup=main_menu_keyboard(user_id)
        )
        
    elif text == "🆘 SUPPORT":
        await update.message.reply_text(
            f"🆘 কোনো সমস্যায় পড়লে সরাসরি এডমিনের সাথে যোগাযোগ করুন:\n\n"
            f"👤 Support Admin: {SUPPORT_ADMIN}\n"
            f"💬 OTP Discussion Group: {OTP_GROUP_URL}",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(user_id)
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
        total_users = await users_col.count_documents({})
        total_nums = await numbers_col.count_documents({"status": "Available"})
                
        await update.message.reply_text(
            f"📊 **Database Overview**\n\n"
            f"👥 Total Registered Users: `{total_users}`\n"
            f"📱 Available Numbers: `{total_nums}`",
            parse_mode="Markdown",
            reply_markup=admin_panel_keyboard()
        )
        
    elif text == "⚙️ Number Management" and user_id == OWNER_ID:
        ADMIN_UPLOAD_STATE[user_id] = {"step": "GET_SERVICE"}
        await update.message.reply_text(
            "⚙️ **Number Management (Step 1/3)**\n\n"
            "প্রথমে কোন সার্ভিসের জন্য নাম্বার আপলোড করবেন তার নাম লিখে পাঠান (যেমন: `Telegram` বা `WhatsApp`):",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )
        
    elif text in ["📢 Broadcast", "👥 User Management"] and user_id == OWNER_ID:
        await update.message.reply_text(
            f"⚙️ `{text}` ফিচারটি ডেভেলপমেন্ট পর্যায়ে রয়েছে।",
            parse_mode="Markdown",
            reply_markup=admin_panel_keyboard()
        )
        
    else:
        if not update.message.document and user_id not in ADMIN_UPLOAD_STATE:
            await update.message.reply_text("দয়া করে নিচের বাটনগুলো ব্যবহার করুন অথবা /start দিন।", reply_markup=main_menu_keyboard(user_id))

async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    await application.bot.set_my_commands([BotCommand("start", "Start the bot")])

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, message_handler))

    print("Bot is running with MongoDB...")
    
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

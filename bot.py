import os
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import motor.motor_asyncio

# Logging setup
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("DATABASE_URL") or os.getenv("MONGO_URL")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# --- MongoDB Setup ---
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client.zentrix_bot
users_col = db.users
numbers_col = db.numbers
assigned_col = db.assigned_numbers

# --- Permanent Links & Info ---
MAIN_CHANNEL_URL = "https://t.me/Zentrix_Officiall"
MAIN_CHANNEL_ID = "@Zentrix_Officiall"

UPDATE_CHANNEL_URL = "https://t.me/Zentrix_Update"
UPDATE_CHANNEL_ID = "@Zentrix_Update"

OTP_GROUP_URL = "https://t.me/+pBpZWtQC4qswODI1"
SUPPORT_ADMIN = "@ranaXvou"
DEFAULT_OTP_RATE = 0.60

ADMIN_UPLOAD_STATE = {}
USER_SEARCH_STATE = {}

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
        [KeyboardButton("💰 BALANCE"), KeyboardButton("🆘 SUPPORT")]
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
    if user.id in USER_SEARCH_STATE:
        del USER_SEARCH_STATE[user.id]

    await users_col.update_one(
        {"user_id": user.id},
        {"$set": {"username": user.username}, "$setOnInsert": {"balance": 0.0, "total_earned": 0.0}},
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

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == "check_join":
        is_joined = await check_force_join(user_id, context)
        if is_joined:
            await query.answer("✅ ধন্যবাদ! সফলভাবে ভেরিফাই করা হয়েছে।", show_alert=False)
            try:
                await query.message.delete()
            except Exception:
                pass
                
            user = query.from_user
            await users_col.update_one(
                {"user_id": user.id},
                {"$set": {"username": user.username}, "$setOnInsert": {"balance": 0.0, "total_earned": 0.0}},
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

    elif query.data in ["get_stock_click", "get_number_menu"]:
        await query.answer()
        services = await numbers_col.distinct("service_name", {"status": "Available"})
        
        if services:
            keyboard = [[InlineKeyboardButton(f"📱 {serv}", callback_data=f"sel_serv:{serv}")] for serv in services]
            reply_markup = InlineKeyboardMarkup(keyboard)
            text_msg = "📱 **Select a Service:**"
        else:
            reply_markup = None
            text_msg = "📱 **Get Number Menu**\n\n⚠️ বর্তমানে কোনো নাম্বার স্টক এ নেই!"
        
        try:
            await query.message.edit_text(text_msg, parse_mode="Markdown", reply_markup=reply_markup)
        except Exception:
            await query.message.reply_text(text_msg, parse_mode="Markdown", reply_markup=reply_markup)

    elif query.data.startswith("sel_serv:"):
        await query.answer()
        service_name = query.data.split(":", 1)[1].strip()
        countries = await numbers_col.distinct("country", {"service_name": service_name, "status": "Available"})
        
        if countries:
            keyboard = [[InlineKeyboardButton(f"🌍 {country}", callback_data=f"sel_count:{service_name}:{country}")] for country in countries]
            keyboard.append([InlineKeyboardButton("🔙 Back to Services", callback_data="get_number_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            text_msg = f"🌍 **Select Country for `{service_name}`:**"
        else:
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Services", callback_data="get_number_menu")]])
            text_msg = f"⚠️ `{service_name}` সার্ভিসে বর্তমানে কোনো কান্ট্রি এভেইলেবল নেই!"
        
        try:
            await query.message.edit_text(text_msg, parse_mode="Markdown", reply_markup=reply_markup)
        except Exception:
            await query.message.reply_text(text_msg, parse_mode="Markdown", reply_markup=reply_markup)

    elif query.data.startswith("sel_count:") or query.data.startswith("change_num:"):
        await query.answer()
        parts = query.data.split(":", 2)
        service_name = parts[1].strip() if len(parts) >= 2 else "Unknown"
        country = parts[2].strip() if len(parts) >= 3 else "Unknown"
        
        cursor = numbers_col.find({
            "service_name": {"$regex": f"^{service_name}$", "$options": "i"},
            "country": {"$regex": f"^{country}$", "$options": "i"},
            "status": "Available"
        }).limit(2)
        
        numbers = await cursor.to_list(length=2)
        
        if numbers:
            num_ids = [doc["_id"] for doc in numbers]
            await numbers_col.update_many({"_id": {"$in": num_ids}}, {"$set": {"status": "Assigned"}})
            
            for doc in numbers:
                await assigned_col.insert_one({
                    "user_id": user_id,
                    "phone_number": doc['phone_number'],
                    "service_name": service_name,
                    "country": country
                })
            
            text_msg = (
                f"🇲🇱 {country} Allocated 💬 {service_name}\n"
                f"🔗 Otp Rate : {DEFAULT_OTP_RATE}৳\n"
                f"⏳ Waiting for OTP...... ⬇️"
            )
            
            keyboard = []
            for doc in numbers:
                num = doc['phone_number']
                keyboard.append([InlineKeyboardButton(f"🇲🇱 📋 {num}", copy_text=CopyTextButton(text=num))])
            
            keyboard.append([InlineKeyboardButton("🔄 Change Number", callback_data=f"change_num:{service_name}:{country}")])
            keyboard.append([
                InlineKeyboardButton("🌍 Other Countries", callback_data=f"sel_serv:{service_name}"),
                InlineKeyboardButton("🌐 OTP", url=OTP_GROUP_URL)
            ])
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            text_msg = f"⚠️ দুঃখিত! `{service_name}` ({country}) এ বর্তমানে নতুন কোনো নাম্বার এভেইলেবল নেই।"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 Other Countries", callback_data=f"sel_serv:{service_name}")]])
        
        try:
            await query.message.edit_text(text_msg, parse_mode="Markdown", reply_markup=reply_markup)
        except Exception:
            await query.message.reply_text(text_msg, parse_mode="Markdown", reply_markup=reply_markup)

    elif query.data.startswith("search_next:"):
        await query.answer()
        prefix = query.data.split(":", 1)[1].strip()
        
        cursor = numbers_col.find({
            "phone_number": {"$regex": f"^\\+?{prefix}", "$options": "i"},
            "status": "Available"
        }).limit(2)
        
        numbers = await cursor.to_list(length=2)
        
        if numbers:
            num_ids = [doc["_id"] for doc in numbers]
            await numbers_col.update_many({"_id": {"$in": num_ids}}, {"$set": {"status": "Assigned"}})
            
            for doc in numbers:
                await assigned_col.insert_one({
                    "user_id": user_id,
                    "phone_number": doc['phone_number'],
                    "service_name": "Search",
                    "country": "Custom"
                })
            
            text_msg = f"🔎 **SEARCH RESULTS** (Prefix: `{prefix}`)"
            
            keyboard = []
            for doc in numbers:
                num = doc['phone_number']
                keyboard.append([InlineKeyboardButton(f"📲 📋 {num}", copy_text=CopyTextButton(text=num))])
            
            keyboard.append([InlineKeyboardButton("🔄 Change Number", callback_data=f"search_next:{prefix}")])
            keyboard.append([
                InlineKeyboardButton("🌍 Other Countries", callback_data="get_number_menu"),
                InlineKeyboardButton("🌐 OTP Group", url=OTP_GROUP_URL)
            ])
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.message.edit_text(text_msg, parse_mode="Markdown", reply_markup=reply_markup)
            except Exception:
                await query.message.reply_text(text_msg, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await query.message.edit_text(
                f"❌ এই সিরিয়াল বা প্রফিক্সের (`{prefix}`) আর কোনো নাম্বার এভেইলেবল নেই!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌍 Other Countries", callback_data="get_number_menu")],
                    [InlineKeyboardButton("🌐 OTP Group", url=OTP_GROUP_URL)]
                ])
            )

async def otp_group_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    
    text = message.text
    async for assigned_doc in assigned_col.find({}):
        phone = assigned_doc["phone_number"]
        if phone in text:
            user_id = assigned_doc["user_id"]
            service = assigned_doc["service_name"]
            
            await users_col.update_one(
                {"user_id": user_id},
                {"$inc": {"balance": DEFAULT_OTP_RATE, "total_earned": DEFAULT_OTP_RATE}}
            )
            
            user_msg = (
                f"🇲🇱 #ML `{phone}` English\n"
                f"📥 **OTP Received!**\n\n"
                f"💬 `{text}`\n\n"
                f"💵 Added to Balance: `+{DEFAULT_OTP_RATE}৳`"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"📱 {service}", callback_data="get_number_menu")]
            ])
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=user_msg,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception as e:
                logging.info(f"Failed to send OTP to user {user_id}: {e}")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text if update.message.text else ""

    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"username": update.effective_user.username}, "$setOnInsert": {"balance": 0.0, "total_earned": 0.0}},
        upsert=True
    )

    if text == "🔙 Back":
        if user_id in ADMIN_UPLOAD_STATE:
            del ADMIN_UPLOAD_STATE[user_id]
            if user_id == OWNER_ID:
                await update.message.reply_text("👑 **Admin Control Panel**", parse_mode="Markdown", reply_markup=admin_panel_keyboard())
                return
        if user_id in USER_SEARCH_STATE:
            del USER_SEARCH_STATE[user_id]
        
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

    if user_id in USER_SEARCH_STATE:
        prefix = text.strip()
        del USER_SEARCH_STATE[user_id]
        
        if not prefix:
            await update.message.reply_text("❌ কান্ট্রি কোড বা সিরিয়াল খালি রাখা যাবে না। আবার চেষ্টা করুন:", reply_markup=main_menu_keyboard(user_id))
            return
            
        cursor = numbers_col.find({
            "phone_number": {"$regex": f"^\\+?{prefix}", "$options": "i"},
            "status": "Available"
        }).limit(2)
        
        numbers = await cursor.to_list(length=2)
        
        if numbers:
            num_ids = [doc["_id"] for doc in numbers]
            await numbers_col.update_many({"_id": {"$in": num_ids}}, {"$set": {"status": "Assigned"}})
            
            for doc in numbers:
                await assigned_col.insert_one({
                    "user_id": user_id,
                    "phone_number": doc['phone_number'],
                    "service_name": "Search",
                    "country": "Custom"
                })
            
            text_msg = f"🔎 **SEARCH RESULTS** (Prefix: `{prefix}`)"
            
            keyboard = []
            for doc in numbers:
                num = doc['phone_number']
                keyboard.append([InlineKeyboardButton(f"📲 📋 {num}", copy_text=CopyTextButton(text=num))])
            
            keyboard.append([InlineKeyboardButton("🔄 Change Number", callback_data=f"search_next:{prefix}")])
            keyboard.append([
                InlineKeyboardButton("🌍 Other Countries", callback_data="get_number_menu"),
                InlineKeyboardButton("🌐 OTP Group", url=OTP_GROUP_URL)
            ])
            
            await update.message.reply_text(text_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(
                f"❌ এই সিরিয়াল বা প্রফিক্স (`{prefix}`) দিয়ে কোনো নাম্বার খুঁজে পাওয়া যাচ্ছে না!",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(user_id)
            )
        return

    if user_id == OWNER_ID and user_id in ADMIN_UPLOAD_STATE:
        state_data = ADMIN_UPLOAD_STATE[user_id]
        current_step = state_data.get("step")

        if current_step == "GET_SERVICE":
            service_name = text.strip()
            ADMIN_UPLOAD_STATE[user_id] = {"step": "GET_COUNTRY", "service": service_name}
            await update.message.reply_text(f"✅ সার্ভিস: `{service_name}`\n\n🌍 এখন কান্ট্রির নাম লিখে পাঠান:", parse_mode="Markdown", reply_markup=back_keyboard())
            return

        elif current_step == "GET_COUNTRY":
            country = text.strip()
            service_name = state_data["service"]
            ADMIN_UPLOAD_STATE[user_id] = {"step": "GET_NUMBERS", "service": service_name, "country": country}
            await update.message.reply_text("📂 এখন `.txt` ফাইল আপলোড করুন অথবা নাম্বারগুলো পেস্ট করুন:", parse_mode="Markdown", reply_markup=back_keyboard())
            return

        elif current_step == "GET_NUMBERS" and text:
            service_name = state_data["service"]
            country = state_data["country"]
            numbers_list = [line.strip() for line in text.split("\n") if line.strip()]
            
            docs = [{"service_name": service_name, "country": country, "phone_number": num, "status": "Available"} for num in numbers_list]
            if docs:
                await numbers_col.insert_many(docs)
            del ADMIN_UPLOAD_STATE[user_id]
            
            await update.message.reply_text(f"🎉 সফলভাবে {len(numbers_list)}টি নাম্বার যুক্ত হয়েছে!", reply_markup=admin_panel_keyboard())
            return

    if user_id == OWNER_ID and update.message.document and user_id in ADMIN_UPLOAD_STATE:
        state_data = ADMIN_UPLOAD_STATE[user_id]
        if state_data.get("step") == "GET_NUMBERS":
            doc = update.message.document
            file = await context.bot.get_file(doc.file_id)
            file_path = f"temp_{user_id}.txt"
            await file.download_to_drive(file_path)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            numbers_list = [line.strip() for line in content.split("\n") if line.strip()]
            docs = [{"service_name": state_data["service"], "country": state_data["country"], "phone_number": num, "status": "Available"} for num in numbers_list]
            if docs:
                await numbers_col.insert_many(docs)
            del ADMIN_UPLOAD_STATE[user_id]
            
            await update.message.reply_text(f"🎉 ফাইল থেকে সফলভাবে {len(numbers_list)}টি নাম্বার যুক্ত হয়েছে!", reply_markup=admin_panel_keyboard())
            return

    if text == "/start":
        await start(update, context)
        
    elif text == "📱 GET NUMBER":
        services = await numbers_col.distinct("service_name", {"status": "Available"})
        if services:
            keyboard = [[InlineKeyboardButton(f"📱 {serv}", callback_data=f"sel_serv:{serv}")] for serv in services]
            await update.message.reply_text("📱 **Select a Service:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("⚠️ বর্তমানে কোনো নাম্বার স্টক এ নেই!", parse_mode="Markdown")
        
    elif text == "🔎 SEARCH NUMBER":
        USER_SEARCH_STATE[user_id] = True
        await update.message.reply_text("🔎 **Search Number**\n\nদয়া করে কান্ট্রি কোড বা সিরিয়াল নাম্বার লিখে পাঠান (যেমন: `223` বা `22357`):", parse_mode="Markdown", reply_markup=back_keyword())
        
    elif text == "🚦 TRAFFIC":
        await update.message.reply_text(f"🚦 সিস্টেমের বর্তমান ট্রাফিক স্বাভাবিক আছে。\n\nঅফিশিয়াল আপডেট: {UPDATE_CHANNEL_URL}", parse_mode="Markdown", reply_markup=main_menu_keyboard(user_id))
        
    elif text == "👥 REFERRAL":
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        await update.message.reply_text(f"👥 **Referral System**\n\nআপনার রেফাল লিংক:\n`{ref_link}`", parse_mode="Markdown", reply_markup=main_menu_keyboard(user_id))
        
    elif text == "💰 BALANCE":
        user_data = await users_col.find_one({"user_id": user_id})
        balance = user_data.get("balance", 0.0) if user_data else 0.0
        total_earned = user_data.get("total_earned", 0.0) if user_data else 0.0
        
        balance_text = (
            f"👤 **User Account Dashboard**\n\n"
            f"💰 Current Balance : `{balance:.2f}৳`\n"
            f"📈 Total Earned : `{total_earned:.2f}৳`\n"
            f"💸 Withdrawal Status : `Active`\n\n"
            f"⚡ Earn per OTP: `{DEFAULT_OTP_RATE}৳`"
        )
        await update.message.reply_text(balance_text, parse_mode="Markdown", reply_markup=main_menu_keyboard(user_id))
        
    elif text == "🆘 SUPPORT":
        await update.message.reply_text(f"🆘 যোগাযোগ করুন:\n👤 Admin: {SUPPORT_ADMIN}\n💬 Group: {OTP_GROUP_URL}", parse_mode="Markdown", reply_markup=main_menu_keyboard(user_id))
        
    elif text == "👑 ADMIN PANEL" and user_id == OWNER_ID:
        await update.message.reply_text("👑 **Admin Control Panel**", parse_mode="Markdown", reply_markup=admin_panel_keyboard())
        
    elif text == "📊 Overview" and user_id == OWNER_ID:
        total_users = await users_col.count_documents({})
        total_nums = await numbers_col.count_documents({"status": "Available"})
        await update.message.reply_text(f"📊 **Overview**\n👥 Users: `{total_users}`\n📱 Stock: `{total_nums}`", parse_mode="Markdown", reply_markup=admin_panel_keyboard())
        
    elif text == "⚙️ Number Management" and user_id == OWNER_ID:
        ADMIN_UPLOAD_STATE[user_id] = {"step": "GET_SERVICE"}
        await update.message.reply_text("⚙️ কোন সার্ভিসের নাম্বার আপলোড করবেন নাম লিখুন:", parse_mode="Markdown", reply_markup=back_keyboard())
        
    else:
        if not update.message.document and user_id not in ADMIN_UPLOAD_STATE and user_id not in USER_SEARCH_STATE:
            await update.message.reply_text("দয়া করে নিচের বাটনগুলো ব্যবহার করুন অথবা /start দিন।", reply_markup=main_menu_keyboard(user_id))

async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    await application.bot.set_my_commands([BotCommand("start", "Start the bot")])

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, message_handler))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, otp_group_listener))

    print("Zentrix Bot is running successfully...")
    
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

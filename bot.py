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
traffic_col = db.traffic
settings_col = db.settings
withdrawals_col = db.withdrawals

# --- Permanent Links & Info ---
MAIN_CHANNEL_URL = "https://t.me/Zentrix_Officiall"
MAIN_CHANNEL_ID = "@Zentrix_Officiall"

UPDATE_CHANNEL_URL = "https://t.me/Zentrix_Update"
UPDATE_CHANNEL_ID = "@Zentrix_Update"

OTP_GROUP_URL = "https://t.me/+pBpZWtQC4qswODI1"
SUPPORT_URL = "https://t.me/ranaXvou"

ADMIN_UPLOAD_STATE = {}
USER_SEARCH_STATE = {}
ADMIN_SETTINGS_STATE = {}
USER_WITHDRAW_STATE = {}

# --- Dynamic Settings Getter/Setter ---
async def get_setting(key, default_val):
    res = await settings_col.find_one({"_id": key})
    if res and "value" in res:
        return res["value"]
    return default_val

async def set_setting(key, val):
    await settings_col.update_one({"_id": key}, {"$set": {"value": val}}, upsert=True)

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

# --- Reply Keyboards (Normal Users) ---
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

# --- Admin Inline Panel Keyboard ---
async def get_admin_panel_markup():
    total_users = await users_col.count_documents({})
    total_numbers = await numbers_col.count_documents({})
    available_numbers = await numbers_col.count_documents({"status": "Available"})
    assigned_numbers = await numbers_col.count_documents({"status": "Assigned"})
    used_numbers = await numbers_col.count_documents({"status": "Used"})
    
    pipeline = [{"$group": {"_id": {"service": "$service_name", "country": "$country"}}}]
    files_cursor = numbers_col.aggregate(pipeline)
    files_list = await files_cursor.to_list(length=1000)
    total_files = len(files_list)

    panel_text = (
        f"👑 **Admin Control Panel**\n\n"
        f"📊 **Database Overview:**\n"
        f"👥 Total Users: `{total_users}`\n"
        f"📂 Total Files/Batches: `{total_files}`\n"
        f"📱 Total Numbers: `{total_numbers}`\n"
        f"🟢 Available: `{available_numbers}` | 🔄 Assigned: `{assigned_numbers}`\n"
        f"🔴 Used Numbers: `{used_numbers}`\n\n"
        f"নিচের অপশনগুলো থেকে সিলেক্ট করুন:"
    )

    keyboard = [
        [InlineKeyboardButton("🏆 Leaderboard System", callback_data="adm_leaderboard")],
        [InlineKeyboardButton("⚙️ System", callback_data="adm_system_menu")],
        [InlineKeyboardButton("📤 Upload Number", callback_data="adm_upload"), InlineKeyboardButton("🗑️ Delete Files", callback_data="adm_delete")],
        [InlineKeyboardButton("📢 Broadcast System", callback_data="adm_broadcast")],
        [InlineKeyboardButton("📱 Used Numbers", callback_data="adm_used"), InlineKeyboardButton("📲 Unused Numbers", callback_data="adm_unused")],
        [InlineKeyboardButton("❌ Close Panel", callback_data="adm_close")]
    ]
    return panel_text, InlineKeyboardMarkup(keyboard)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    for state_dict in [ADMIN_UPLOAD_STATE, USER_SEARCH_STATE, ADMIN_SETTINGS_STATE, USER_WITHDRAW_STATE]:
        if user.id in state_dict:
            del state_dict[user.id]

    args = context.args
    referrer_id = None
    if args and args[0].isdigit():
        ref_id = int(args[0])
        if ref_id != user.id:
            referrer_id = ref_id

    existing_user = await users_col.find_one({"user_id": user.id})
    if not existing_user:
        ref_bonus = float(await get_setting("ref_bonus", 0.01))
        await users_col.insert_one({
            "user_id": user.id,
            "username": user.username,
            "balance": 0.0,
            "total_earned": 0.0,
            "referred_by": referrer_id
        })
        if referrer_id:
            await users_col.update_one(
                {"user_id": referrer_id},
                {"$inc": {"balance": ref_bonus, "total_earned": ref_bonus}}
            )
            try:
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 **New Referral!**\n\nআপনার লিংকের মাধ্যমে একজন নতুন ইউজার জয়েন করেছে এবং আপনি বোনাস পেয়েছেন: `+{ref_bonus}৳`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
    else:
        await users_col.update_one(
            {"user_id": user.id},
            {"$set": {"username": user.username}}
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
            "দয়া করে নিচের লিংকগুলোতে জয়েন করুন এবং তারপর চেক করুন।",
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
            welcome_text = (
                f"🌐 **NUMBER PANEL**\n\n"
                f"👋 Welcome, **{user.first_name}**\n"
                f"🚀 Premium Number Management System\n\n"
                f"⚡ Fast • Simple • Secure"
            )
            await context.bot.send_message(chat_id=user_id, text=welcome_text, parse_mode="Markdown", reply_markup=main_menu_keyboard(user_id))
        else:
            await query.answer("❌ আপনি এখনো সবকটি চ্যানেল বা গ্রুপে জয়েন করেননি! দয়া করে আগে জয়েন করুন।", show_alert=True)

    # --- Admin Inline Panel Actions ---
    elif query.data == "adm_leaderboard" and user_id == OWNER_ID:
        await query.answer()
        text = "🏆 **Leaderboard System**\n\n(এই ফিচারটির কার্যকারিতা শীঘ্রই যুক্ত করা হবে।)"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif query.data == "adm_system_menu" and user_id == OWNER_ID:
        await query.answer()
        sys_text = "⚙️ **System Control Hub**\n\nনিচের অপশনগুলো থেকে ম্যানেজ করুন:"
        sys_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("StexSMS Control", callback_data="sys_stex"), InlineKeyboardButton("Voltx Control", callback_data="sys_voltx")],
            [InlineKeyboardButton("Zenex Control", callback_data="sys_zenex"), InlineKeyboardButton("YE SMS Control", callback_data="sys_ye")],
            [InlineKeyboardButton("Force Join System", callback_data="sys_forcejoin"), InlineKeyboardButton("Admin Management", callback_data="sys_admin_mgmt")],
            [InlineKeyboardButton("OTP Group", callback_data="sys_otpgroup"), InlineKeyboardButton("User Management", callback_data="sys_usermgmt")],
            [InlineKeyboardButton("RanaX Control", callback_data="sys_ranax"), InlineKeyboardButton("Premium Emoji", callback_data="sys_emoji")],
            [InlineKeyboardButton("Menu Design", callback_data="sys_menudesign"), InlineKeyboardButton("Test", callback_data="sys_test")],
            [InlineKeyboardButton("🔙 Back", callback_data="adm_back")]
        ])
        await query.message.edit_text(sys_text, parse_mode="Markdown", reply_markup=sys_keyboard)

    elif query.data.startswith("sys_") and user_id == OWNER_ID:
        await query.answer("এই মডিউলটির কাজ পরবর্তীতে যুক্ত করা হবে।", show_alert=True)

    elif query.data == "adm_upload" and user_id == OWNER_ID:
        await query.answer()
        ADMIN_UPLOAD_STATE[user_id] = {"step": "GET_SERVICE"}
        await query.message.edit_text("⚙️ কোন সার্ভিসের নাম্বার আপলোড করবেন সেই নাম লিখে পাঠান (যেমন: Facebook):", parse_mode="Markdown")

    elif query.data == "adm_delete" and user_id == OWNER_ID:
        await query.answer()
        text = "🗑️ **Delete Files / Numbers**\n\n(এই অপশনের কাজ পরবর্তীতে সেটআপ করে দেওয়া হবে।)"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif query.data == "adm_broadcast" and user_id == OWNER_ID:
        await query.answer()
        text = "📢 **Broadcast System**\n\n(ব্রডকাস্ট সিস্টেমের কাজ পরবর্তীতে সেটআপ করা হবে।)"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif query.data == "adm_used" and user_id == OWNER_ID:
        await query.answer()
        count = await numbers_col.count_documents({"status": "Used"})
        text = f"📱 **Used Numbers Summary**\n\nমোট ব্যবহৃত (Used) নাম্বারের সংখ্যা: `{count}`"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif query.data == "adm_unused" and user_id == OWNER_ID:
        await query.answer()
        count = await numbers_col.count_documents({"status": "Available"})
        text = f"📲 **Unused/Available Numbers Summary**\n\nমোট অব্যবহৃত (Unused/Available) নাম্বারের সংখ্যা: `{count}`"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif query.data == "adm_close" and user_id == OWNER_ID:
        await query.answer("প্যানেল বন্ধ করা হয়েছে।")
        try:
            await query.message.delete()
        except Exception:
            pass

    elif query.data == "adm_back" and user_id == OWNER_ID:
        await query.answer()
        text, markup = await get_admin_panel_markup()
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=markup)

    elif query.data == "refresh_traffic":
        await query.answer("🔄 ট্রাফিক রিফ্রেশ করা হয়েছে!")
        traffic_list = await traffic_col.find({}).to_list(length=100)
        
        if not traffic_list:
            text = "📊 বর্তমানে কোনো ট্রাফিক আপডেট নেই।"
        else:
            text = "🚦 **1 HOUR LIVE TRAFFIC**\n\n"
            for item in traffic_list:
                text += f"🌍 **{item['service']}**\n{item['country']} : {item['status']} {item['icon']}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_traffic")]]
        try:
            await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            pass

    elif query.data == "withdraw_menu":
        await query.answer()
        user_data = await users_col.find_one({"user_id": user_id})
        balance = user_data.get("balance", 0.0) if user_data else 0.0
        
        if balance < 100.0:
            await query.message.reply_text(
                f"❌ দুঃখিত! উইথড্র করার জন্য আপনার অন্তত `100.0৳` ব্যালেন্স থাকতে হবে।\n"
                f"আপনার বর্তমান ব্যালেন্স: `{balance:.2f}৳`\n\n"
                f"💡 আরও নাম্বার ভেরিফাই করে বা রেফার করে ব্যালেন্স বাড়ান!",
                parse_mode="Markdown"
            )
            return
        
        USER_WITHDRAW_STATE[user_id] = {"step": "SELECT_METHOD"}
        keyboard = [
            [InlineKeyboardButton("📱 বিকাশ (Bkash)", callback_data="wd_meth:Bkash")],
            [InlineKeyboardButton("📱 নগদ (Nagad)", callback_data="wd_meth:Nagad")],
            [InlineKeyboardButton("🌐 Binance (BEP20)", callback_data="wd_meth:Binance")],
            [InlineKeyboardButton("🔙 Back to Balance", callback_data="back_to_balance")]
        ]
        await query.message.edit_text(
            f"💸 **Withdrawal Portal**\n\n"
            f"আপনার বর্তমান ব্যালেন্স: `{balance:.2f}৳`\n"
            f"দয়া করে আপনার পেমেন্ট মেথড সিলেক্ট করুন:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("wd_meth:"):
        await query.answer()
        method = query.data.split(":", 1)[1]
        USER_WITHDRAW_STATE[user_id] = {"step": "GET_ACCOUNT", "method": method}
        
        acc_prompt = "বিকাশ নাম্বার" if method == "Bkash" else ("নগদ নাম্বার" if method == "Nagad" else "Binance BEP20 Address")
        await query.message.edit_text(
            f"💳 Selected Method: **{method}**\n\n"
            f"দয়া করে আপনার সঠিক **{acc_prompt}** লিখে পাঠান:",
            parse_mode="Markdown"
        )

    elif query.data.startswith("wd_conf:"):
        await query.answer()
        parts = query.data.split(":")
        action = parts[1]
        target_user_id = int(parts[2])
        amount = float(parts[3])
        
        if action == "yes":
            await query.message.edit_text(f"{query.message.text}\n\n✅ **Status: Confirmed & Completed by Admin**", parse_mode="Markdown")
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"🎉 **অভিনন্দন!** আপনার উইথড্র রিকোয়েস্টটি সফলভাবে সম্পূর্ণ হয়েছে এবং পেমেন্ট পাঠিয়ে দেওয়া হয়েছে। ✅",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        elif action == "no":
            await users_col.update_one({"user_id": target_user_id}, {"$inc": {"balance": amount}})
            await query.message.edit_text(f"{query.message.text}\n\n❌ **Status: Cancelled & Refunded**", parse_mode="Markdown")
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"❌ আপনার উইথড্র রিকোয়েস্টটি বাতিল করা হয়েছে এবং `{amount}৳` আপনার ব্যালেন্সে ফিরিয়ে দেওয়া হয়েছে।",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    elif query.data.startswith("wd_user_conf:"):
        await query.answer()
        action = query.data.split(":", 1)[1]
        if action == "yes":
            data = USER_WITHDRAW_STATE.get(user_id)
            if not data:
                await query.message.edit_text("⚠️ সেশন মেয়াদোত্তীর্ণ হয়ে গেছে। দয়া করে আবার ব্যালেন্স থেকে উইথড্র করুন।")
                return
            
            method = data["method"]
            account = data["account"]
            amount = data["amount"]
            
            await users_col.update_one({"user_id": user_id}, {"$inc": {"balance": -amount}})
            if user_id in USER_WITHDRAW_STATE:
                del USER_WITHDRAW_STATE[user_id]
                
            await query.message.edit_text(
                f"🎉 **উইথড্র রিকোয়েস্ট সফলভাবে জমা হয়েছে!**\n\n"
                f"💳 Method: `{method}`\n"
                f"📥 Account: `{account}`\n"
                f"💰 Amount: `{amount:.2f}৳`\n\n"
                f"⏳ রিকোয়েস্টটি রিভিউ করে আগামী **২৪ ঘণ্টার মধ্যে** পেমেন্ট সম্পন্ন করা হবে। ধন্যবাদ!",
                parse_mode="Markdown"
            )
            
            username_str = f"@{query.from_user.username}" if query.from_user.username else "No Username"
            admin_msg = (
                f"🚨 **New Withdrawal Request!**\n\n"
                f"👤 User ID: `{user_id}`\n"
                f"🔗 Username: {username_str}\n"
                f"💳 Method: `{method}`\n"
                f"📥 Account/Address: `{account}`\n"
                f"💵 Amount: `{amount:.2f}৳`"
            )
            admin_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Confirm", callback_data=f"wd_conf:yes:{user_id}:{amount}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"wd_conf:no:{user_id}:{amount}")
                ]
            ])
            try:
                await context.bot.send_message(
                    chat_id=OTP_GROUP_URL,
                    text=admin_msg,
                    parse_mode="Markdown",
                    reply_markup=admin_keyboard
                )
            except Exception as e:
                logging.info(f"Failed to send withdraw request to admin group: {e}")
                
        else:
            if user_id in USER_WITHDRAW_STATE:
                del USER_WITHDRAW_STATE[user_id]
            await query.message.edit_text("❌ উইথড্র রিকোয়েস্ট বাতিল করা হয়েছে। মেনুতে ফিরে যান।")

    elif query.data == "back_to_balance":
        await query.answer()
        if user_id in USER_WITHDRAW_STATE:
            del USER_WITHDRAW_STATE[user_id]
        user_data = await users_col.find_one({"user_id": user_id})
        balance = user_data.get("balance", 0.0) if user_data else 0.0
        total_earned = user_data.get("total_earned", 0.0) if user_data else 0.0
        current_otp_rate = await get_setting("otp_rate", 0.60)
        
        balance_text = (
            f"👤 **User Account Dashboard**\n\n"
            f"💰 Current Balance : `{balance:.2f}৳`\n"
            f"📈 Total Earned : `{total_earned:.2f}৳`\n"
            f"💸 Withdrawal Status : `Active`\n\n"
            f"⚡ Earn per OTP: `{current_otp_rate}৳`"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💸 Withdraw Balance", callback_data="withdraw_menu")]
        ])
        await query.message.edit_text(balance_text, parse_mode="Markdown", reply_markup=keyboard)

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
        current_otp_rate = float(await get_setting("otp_rate", 0.60))
        
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
                f"🔗 Otp Rate : {current_otp_rate}৳\n"
                f"⏳ Waiting for OTP...... ⬇️"
            )
            
            keyboard = []
            for doc in numbers:
                num = doc['phone_number']
                keyboard.append([InlineKeyboardButton(f"🇲🇱 📋 {num}", copy_text=CopyTextButton(text=num))])
            
            keyboard.append([InlineKeyboardButton("🔄 Change Number", callback_data=f"change_num:{service_name}:{country}")])
            keyboard.append([
                InlineKeyboardButton("🌍 Other Countries", callback_data=f"sel_serv:{service_name}"),
                InlineKeyboardButton("🌐 OTP Group", url=OTP_GROUP_URL)
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
    current_otp_rate = float(await get_setting("otp_rate", 0.60))

    async for assigned_doc in assigned_col.find({}):
        phone = assigned_doc["phone_number"]
        if phone in text:
            user_id = assigned_doc["user_id"]
            service = assigned_doc["service_name"]
            
            await numbers_col.update_one({"phone_number": phone}, {"$set": {"status": "Used"}})
            
            await users_col.update_one(
                {"user_id": user_id},
                {"$inc": {"balance": current_otp_rate, "total_earned": current_otp_rate}}
            )
            
            user_msg = (
                f"🇲🇱 #ML `{phone}` English\n"
                f"📥 **OTP Received!**\n\n"
                f"💬 `{text}`\n\n"
                f"💵 Added to Balance: `+{current_otp_rate}৳`"
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
        for state_dict in [ADMIN_UPLOAD_STATE, USER_SEARCH_STATE, ADMIN_SETTINGS_STATE, USER_WITHDRAW_STATE]:
            if user_id in state_dict:
                del state_dict[user_id]
            
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
            "⚠️ আপনি চ্যানেল বা গ্রুপ থেকে লিভ নিয়েছেন!\nবট ব্যবহার করতে হলে আবার জয়েন করে চেক করুন:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if user_id in USER_WITHDRAW_STATE:
        state = USER_WITHDRAW_STATE[user_id]
        step = state.get("step")
        
        if step == "GET_ACCOUNT":
            state["account"] = text.strip()
            state["step"] = "GET_AMOUNT"
            USER_WITHDRAW_STATE[user_id] = state
            await update.message.reply_text(
                "💰 আপনি কত টাকা উইথড্র করতে চান সেই অ্যামাউন্ট লিখে পাঠান (যেমন: `100` বা `500`):",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
            return
            
        elif step == "GET_AMOUNT":
            try:
                amount = float(text.strip())
                user_data = await users_col.find_one({"user_id": user_id})
                balance = user_data.get("balance", 0.0) if user_data else 0.0
                
                if amount <= 0:
                    await update.message.reply_text("❌ অ্যামাউন্ট সঠিক নয়। আবার চেষ্টা করুন:", reply_markup=back_keyboard())
                    return
                if amount > balance:
                    await update.message.reply_text(f"❌ আপনার পর্যাপ্ত ব্যালেন্স নেই! আপনার বর্তমান ব্যালেন্স: `{balance:.2f}৳`", parse_mode="Markdown", reply_markup=back_keyboard())
                    return
                if amount < 100.0:
                    await update.message.reply_text("❌ সর্বনিম্ন ১০০ টাকা উইথড্র করতে হবে। সঠিক অ্যামাউন্ট দিন:", reply_markup=back_keyboard())
                    return
                
                state["amount"] = amount
                method = state["method"]
                account = state["account"]
                
                confirm_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Confirm", callback_data="wd_user_conf:yes"),
                        InlineKeyboardButton("❌ Cancel", callback_data="wd_user_conf:no")
                    ]
                ])
                await update.message.reply_text(
                    f"📋 **Withdrawal Summary**\n\n"
                    f"💳 Method: `{method}`\n"
                    f"📥 Account: `{account}`\n"
                    f"💵 Amount: `{amount:.2f}৳`\n\n"
                    f"দয়া করে তথ্যগুলো যাচাই করুন এবং কনফার্ম করুন:",
                    parse_mode="Markdown",
                    reply_markup=confirm_keyboard
                )
                return
            except ValueError:
                await update.message.reply_text("❌ দয়া করে সঠিক সংখ্যা লিখুন:", reply_markup=back_keyboard())
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
                await traffic_col.update_one(
                    {"country": country, "service": service_name},
                    {"$setOnInsert": {"status": "MEDIUM", "icon": "🟡"}},
                    upsert=True
                )
            del ADMIN_UPLOAD_STATE[user_id]
            
            await update.message.reply_text(f"🎉 সফলভাবে {len(numbers_list)}টি নাম্বার যুক্ত হয়েছে!", reply_markup=main_menu_keyboard(user_id))
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
            service_name = state_data["service"]
            country = state_data["country"]
            
            docs = [{"service_name": service_name, "country": country, "phone_number": num, "status": "Available"} for num in numbers_list]
            if docs:
                await numbers_col.insert_many(docs)
                await traffic_col.update_one(
                    {"country": country, "service": service_name},
                    {"$setOnInsert": {"status": "MEDIUM", "icon": "🟡"}},
                    upsert=True
                )
            del ADMIN_UPLOAD_STATE[user_id]
            
            await update.message.reply_text(f"🎉 ফাইল থেকে সফলভাবে {len(numbers_list)}টি নাম্বার যুক্ত হয়েছে!", reply_markup=main_menu_keyboard(user_id))
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
        await update.message.reply_text("🔎 **Search Number**\n\nদয়া করে কান্ট্রি কোড বা সিরিয়াল নাম্বার লিখে পাঠান (যেমন: `223` বা `22357`):", parse_mode="Markdown", reply_markup=back_keyboard())
        
    elif text == "🚦 TRAFFIC":
        traffic_list = await traffic_col.find({}).to_list(length=100)
        if not traffic_list:
            traffic_text = "📊 বর্তমানে কোনো লাইভ ট্রাফিক ডাটা নেই।"
        else:
            traffic_text = "🚦 **1 HOUR LIVE TRAFFIC**\n\n"
            for item in traffic_list:
                traffic_text += f"🌍 **{item['service']}**\n{item['country']} : {item['status']} {item['icon']}\n\n"
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_traffic")]])
        await update.message.reply_text(traffic_text, parse_mode="Markdown", reply_markup=keyboard)
        
    elif text == "👥 REFERRAL":
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        ref_bonus = await get_setting("ref_bonus", 0.01)
        ref_text = (
            f"👥 **Referral & Earn Program**\n\n"
            f"আপনার বন্ধুদের আমাদের বটে ইনভাইট করুন এবং আকর্ষণীয় ক্যাশ বোনাস আর্ন করুন!\n\n"
            f"🎁 **Per Referral Bonus:** `{ref_bonus}৳`\n\n"
            f"🔗 **আপনার রেফাল লিংক:**\n`{ref_link}`\n\n"
            f"💡 *লিংকটি কপি করে শেয়ার করুন এবং আপনার ব্যালেন্স বাড়ান!*"
        )
        await update.message.reply_text(ref_text, parse_mode="Markdown", reply_markup=main_menu_keyboard(user_id))
        
    elif text == "💰 BALANCE":
        user_data = await users_col.find_one({"user_id": user_id})
        balance = user_data.get("balance", 0.0) if user_data else 0.0
        total_earned = user_data.get("total_earned", 0.0) if user_data else 0.0
        current_otp_rate = await get_setting("otp_rate", 0.60)
        
        balance_text = (
            f"👤 **User Account Dashboard**\n\n"
            f"💰 Current Balance : `{balance:.2f}৳`\n"
            f"📈 Total Earned : `{total_earned:.2f}৳`\n"
            f"💸 Withdrawal Status : `Active`\n\n"
            f"⚡ Earn per OTP: `{current_otp_rate}৳`"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💸 Withdraw Balance", callback_data="withdraw_menu")]
        ])
        await update.message.reply_text(balance_text, parse_mode="Markdown", reply_markup=keyboard)
        
    elif text == "🆘 SUPPORT":
        support_text = (
            f"🆘 **SUPPORT & HELP DESK**\n\n"
            f"যেকোনো প্রয়োজনে সরাসরি আমাদের অফিসিয়াল অ্যাডমিনের সাথে যোগাযোগ করুন অথবা চ্যানেল ও গ্রুপে যুক্ত থাকুন।\n\n"
            f"👑 **Admin Support:** [Click Here to Message]({SUPPORT_URL})"
        )
        keyboard = [
            [InlineKeyboardButton("📢 Main Channel", url=MAIN_CHANNEL_URL), InlineKeyboardButton("📢 Update Channel", url=UPDATE_CHANNEL_URL)],
            [InlineKeyboardButton("💬 OTP Group", url=OTP_GROUP_URL)]
        ]
        await update.message.reply_text(support_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)
        
    elif text == "👑 ADMIN PANEL" and user_id == OWNER_ID:
        text_msg, markup = await get_admin_panel_markup()
        await update.message.reply_text(text_msg, parse_mode="Markdown", reply_markup=markup)
        
    else:
        if user_id == OWNER_ID and text == "":
            pass
        elif not update.message.document and not any(user_id in d for d in [ADMIN_UPLOAD_STATE, USER_SEARCH_STATE, ADMIN_SETTINGS_STATE, USER_WITHDRAW_STATE]):
            await update.message.reply_text("দয়া করে নিচের বাটনগুলো ব্যবহার করুন অথবা /start দিন।", reply_markup=main_menu_keyboard(user_id))

async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    await application.bot.set_my_commands([BotCommand("start", "Start the bot")])

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, message_handler))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, otp_group_listener))

    print("Zentrix Bot is running successfully with System Menu added...")
    
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

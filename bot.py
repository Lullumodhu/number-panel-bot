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
admins_col = db.admins
channels_col = db.channels
forward_groups_col = db.forward_groups
ranax_groups_col = db.ranax_groups  # RanaX সোর্স গ্রুপগুলো সংরক্ষণের জন্য কালেকশন

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
ADMIN_BROADCAST_STATE = {}
ADMIN_ADD_STATE = {}
CHANNEL_ADD_STATE = {}
FORWARD_GROUP_ADD_STATE = {}
USER_MANAGE_STATE = {}
RANAX_ADD_STATE = {}
MENU_EDIT_STATE = {}  # মেনু টেক্সট বা বাটন কাস্টমাইজেশনের জন্য স্টেট
TEST_FLOW_STATE = {}  # টেস্ট ফ্লো ডেটা সংরক্ষণের জন্য স্টেট

# --- Dynamic Settings Getter/Setter ---
async def get_setting(key, default_val):
    res = await settings_col.find_one({"_id": key})
    if res and "value" in res:
        return res["value"]
    return default_val

async def set_setting(key, val):
    await settings_col.update_one({"_id": key}, {"$set": {"value": val}}, upsert=True)

# --- Admin Check Function ---
async def is_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    admin_doc = await admins_col.find_one({"user_id": user_id})
    return bool(admin_doc)

# --- Force Join Check Function ---
async def check_force_join(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    fj_status = await get_setting("force_join_status", "ON")
    if fj_status != "ON":
        return True

    custom_channels = await channels_col.find({}).to_list(length=50)
    channels_to_check = []
    
    if custom_channels:
        for ch in custom_channels:
            channels_to_check.append((ch.get("name", "Channel"), ch.get("chat_id")))
    else:
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

# --- Reply Keyboards (Normal Users - Dynamic Support) ---
async def main_menu_keyboard(user_id: int):
    btn_get_num = await get_setting("btn_get_number", "📱 GET NUMBER")
    btn_search_num = await get_setting("btn_search_number", "🔎 SEARCH NUMBER")
    btn_traffic = await get_setting("btn_traffic", "🚦 TRAFFIC")
    btn_refer = await get_setting("btn_refer", "👥 REFERRAL")
    btn_balance = await get_setting("btn_balance", "💰 BALANCE")
    btn_support = await get_setting("btn_support", "🆘 SUPPORT")

    keyboard = [
        [KeyboardButton(btn_get_num), KeyboardButton(btn_search_num)],
        [KeyboardButton(btn_traffic), KeyboardButton(btn_refer)],
        [KeyboardButton(btn_balance), KeyboardButton(btn_support)]
    ]
    return keyboard

async def build_main_menu(user_id: int):
    kb = await main_menu_keyboard(user_id)
    if await is_admin(user_id):
        kb.append([KeyboardButton("👑 ADMIN PANEL")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def back_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("🔙 Back")]], resize_keyboard=True)

# --- Admin Main Control Panel Markup ---
async def get_admin_panel_markup(user_id: int):
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
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="adm_leaderboard"), InlineKeyboardButton("⚙️ System Hub", callback_data="adm_system_menu")],
        [InlineKeyboardButton("📤 Upload", callback_data="adm_upload"), InlineKeyboardButton("🗑️ Delete", callback_data="adm_delete")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"), InlineKeyboardButton("❌ Close", callback_data="adm_close")]
    ]
    return panel_text, InlineKeyboardMarkup(keyboard)

# --- OTP/Test Helpers ---
COUNTRY_ISO_BY_PREFIX = {
    "880": "BD", "60": "MY", "62": "ID", "33": "FR", "44": "GB",
    "1": "US", "7": "RU", "81": "JP", "82": "KR", "86": "CN",
    "91": "IN", "92": "PK", "93": "AF", "94": "LK", "95": "MM",
    "98": "IR", "20": "EG", "27": "ZA", "30": "GR", "31": "NL",
    "32": "BE", "34": "ES", "39": "IT", "40": "RO", "41": "CH",
    "43": "AT", "45": "DK", "46": "SE", "47": "NO", "48": "PL",
    "49": "DE", "51": "PE", "52": "MX", "53": "CU", "54": "AR",
    "55": "BR", "56": "CL", "57": "CO", "58": "VE", "63": "PH",
    "64": "NZ", "65": "SG", "66": "TH", "84": "VN", "90": "TR",
    "212": "MA", "213": "DZ", "216": "TN", "218": "LY", "234": "NG",
    "254": "KE", "255": "TZ", "256": "UG", "971": "AE", "972": "IL",
    "973": "BH", "974": "QA", "966": "SA", "968": "OM", "965": "KW",
}


def normalize_phone(phone: str) -> str:
    return ''.join(ch for ch in str(phone) if ch.isdigit() or ch == '+')


def detect_country_iso(phone: str) -> str:
    clean = normalize_phone(phone).lstrip('+')
    # Longest prefix first so 971/972 etc. are checked before shorter prefixes.
    for prefix in sorted(COUNTRY_ISO_BY_PREFIX, key=len, reverse=True):
        if clean.startswith(prefix):
            return COUNTRY_ISO_BY_PREFIX[prefix]
    return "UN"


def build_otp_display(service: str, phone: str, otp_text: str, language: str, country_iso: str, test=False, rate=None) -> str:
    """Single display format used by real OTP notifications and Test Flow."""
    title = "🧪 **[TEST OTP - OTP HUB]**" if test else "📥 **OTP Received!**"
    body = (
        f"💬 #OTP_Received `{phone}`\n"
        f"{title}\n\n"
        f"📱 **Service:** `{service}`\n"
        f"💬 `{otp_text}`\n"
        f"🌍 **Country:** `{country_iso}`\n"
        f"🌐 **Language:** `{language}`"
    )
    if rate is not None and not test:
        body += f"\n\n💵 Added to Balance: `+{rate}৳`"
    if test:
        body += "\n\n✅ _Test only — no balance/reward was added._"
    return body


async def get_otp_target_groups():
    groups = await forward_groups_col.find({}).to_list(length=50)
    ids = [g.get("group_id") for g in groups if g.get("group_id")]
    return ids or [OTP_GROUP_URL]

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    for state_dict in [ADMIN_UPLOAD_STATE, USER_SEARCH_STATE, ADMIN_SETTINGS_STATE, USER_WITHDRAW_STATE, ADMIN_BROADCAST_STATE, ADMIN_ADD_STATE, CHANNEL_ADD_STATE, FORWARD_GROUP_ADD_STATE, USER_MANAGE_STATE, RANAX_ADD_STATE, MENU_EDIT_STATE, TEST_FLOW_STATE]:
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
            "referred_by": referrer_id,
            "banned": False
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

    user_doc = await users_col.find_one({"user_id": user.id})
    if user_doc and user_doc.get("banned", False):
        await update.message.reply_text("❌ আপনি এই বট থেকে ব্যান হয়েছেন。", parse_mode="Markdown")
        return

    is_joined = await check_force_join(user.id, context)
    if not is_joined:
        channels_list = await channels_col.find({}).to_list(length=50)
        inline_kb = []
        if channels_list:
            for ch in channels_list:
                inline_kb.append([InlineKeyboardButton(f"📢 Join {ch.get('name')}", url=ch.get('url'))])
        else:
            inline_kb.append([InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_URL)])
            inline_kb.append([InlineKeyboardButton("📢 Join Update Channel", url=UPDATE_CHANNEL_URL)])
            
        inline_kb.append([InlineKeyboardButton("💬 Join OTP Group", url=OTP_GROUP_URL)])
        inline_kb.append([InlineKeyboardButton("✅ Joined / Check", callback_data="check_join")])

        await update.message.reply_text(
            "⚠️ **বটটি ব্যবহার করতে হলে অবশ্যই আমাদের চ্যানেল এবং গ্রুপগুলোতে জয়েন থাকতে হবে!**\n\n"
            "দয়া করে নিচের লিংকগুলোতে জয়েন করুন এবং তারপর চেক করুন।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_kb)
        )
        return

    custom_welcome = await get_setting("start_menu_text", None)
    if not custom_welcome:
        welcome_text = (
            f"🌐 **NUMBER PANEL**\n\n"
            f"👋 Welcome, **{user.first_name}**\n"
            f"🚀 Premium Number Management System\n\n"
            f"📱 Manage your available numbers\n"
            f"🌍 Browse services & countries\n"
            f"💰 Balance & referral management\n\n"
            f"⚡ Fast • Simple • Secure"
        )
    else:
        welcome_text = custom_welcome.format(first_name=user.first_name, username=user.username or "N/A", user_id=user.id)

    reply_markup = await build_main_menu(user.id)
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

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
            custom_welcome = await get_setting("start_menu_text", None)
            if not custom_welcome:
                welcome_text = (
                    f"🌐 **NUMBER PANEL**\n\n"
                    f"👋 Welcome, **{user.first_name}**\n"
                    f"🚀 Premium Number Management System\n\n"
                    f"⚡ Fast • Simple • Secure"
                )
            else:
                welcome_text = custom_welcome.format(first_name=user.first_name, username=user.username or "N/A", user_id=user.id)

            reply_markup = await build_main_menu(user_id)
            await context.bot.send_message(chat_id=user_id, text=welcome_text, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await query.answer("❌ আপনি এখনো সবকটি চ্যানেল বা গ্রুপে জয়েন করেননি! দয়া করে আগে জয়েন করুন.", show_alert=True)

    # --- System Control Hub Menu ---
    elif query.data == "adm_system_menu" and await is_admin(user_id):
        await query.answer()
        sys_text = "⚙️ **System Control Hub**\n\nনিচের অপশনগুলো থেকে ম্যানেজ করুন:"
        sys_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("StexSMS", callback_data="stex_control"), InlineKeyboardButton("Voltx", callback_data="voltx_control")],
            [InlineKeyboardButton("Zenex", callback_data="zenex_control"), InlineKeyboardButton("YE SMS", callback_data="ye_control")],
            [InlineKeyboardButton("RanaX", callback_data="ranax_control"), InlineKeyboardButton("Emoji", callback_data="premium_emoji")],
            [InlineKeyboardButton("Menu Design", callback_data="menu_design"), InlineKeyboardButton("Test", callback_data="test_flow_start")],
            [InlineKeyboardButton("👑 Admin Mgmt", callback_data="adm_mgmt_menu"), InlineKeyboardButton("⚙️ Force Join", callback_data="adm_fj_menu")],
            [InlineKeyboardButton("👥 User Mgmt", callback_data="adm_usermgmt_menu"), InlineKeyboardButton("💬 OTP Groups", callback_data="adm_otpgroup_menu")],
            [InlineKeyboardButton("🚀 X-Rony Panel", callback_data="adm_xrony_menu")],
            [InlineKeyboardButton("🔙 Back", callback_data="adm_back")]
        ])
        await query.message.edit_text(sys_text, parse_mode="Markdown", reply_markup=sys_keyboard)

    # --- Test Flow Handler Start ---
    elif query.data == "test_flow_start" and await is_admin(user_id):
        await query.answer()
        TEST_FLOW_STATE[user_id] = {"step": "WAITING_FOR_SERVICE"}
        await query.message.edit_text(
            "🧪 **Test Flow (GET_SERVICE)**\n\nদয়া করে টেস্ট করার জন্য সার্ভিসের নামটি লিখে পাঠান:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")]])
        )

    elif query.data.startswith("test_lang_") and await is_admin(user_id):
        state = TEST_FLOW_STATE.get(user_id)
        if not state:
            await query.answer("⚠️ সেশন মেয়াদোত্তীর্ণ হয়ে গেছে। আবার চেষ্টা করুন।", show_alert=True)
            return

        selected_lang = query.data.replace("test_lang_", "").upper()
        phone = state.get("phoneNumber", "")
        country_iso = state.get("countryISO") or detect_country_iso(phone)
        service = state.get("serviceName", "Unknown")
        otp = state.get("otpCode", "")

        # Test uses the same central display formatter as real OTP notifications.
        test_message = build_otp_display(
            service=service,
            phone=phone,
            otp_text=otp,
            language=selected_lang,
            country_iso=country_iso,
            test=True,
        )

        target_groups = await get_otp_target_groups()
        success = 0
        for target_group in target_groups:
            try:
                await context.bot.send_message(
                    chat_id=target_group,
                    text=test_message,
                    parse_mode="Markdown",
                )
                success += 1
            except Exception as e:
                logging.warning("Test OTP send failed for %s: %s", target_group, e)

        if success:
            await query.answer(f"✅ Test OTP {success}টি OTP Group-এ পাঠানো হয়েছে!", show_alert=True)
        else:
            await query.answer("❌ কোনো OTP Group-এ টেস্ট মেসেজ পাঠানো যায়নি। Group ID/permission চেক করুন।", show_alert=True)

        TEST_FLOW_STATE.pop(user_id, None)

        sys_text = "⚙️ **System Control Hub**\n\nনিচের অপশনগুলো থেকে ম্যানেজ করুন:"
        sys_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("StexSMS", callback_data="stex_control"), InlineKeyboardButton("Voltx", callback_data="voltx_control")],
            [InlineKeyboardButton("Zenex", callback_data="zenex_control"), InlineKeyboardButton("YE SMS", callback_data="ye_control")],
            [InlineKeyboardButton("RanaX", callback_data="ranax_control"), InlineKeyboardButton("Emoji", callback_data="premium_emoji")],
            [InlineKeyboardButton("Menu Design", callback_data="menu_design"), InlineKeyboardButton("Test", callback_data="test_flow_start")],
            [InlineKeyboardButton("👑 Admin Mgmt", callback_data="adm_mgmt_menu"), InlineKeyboardButton("⚙️ Force Join", callback_data="adm_fj_menu")],
            [InlineKeyboardButton("👥 User Mgmt", callback_data="adm_usermgmt_menu"), InlineKeyboardButton("💬 OTP Groups", callback_data="adm_otpgroup_menu")],
            [InlineKeyboardButton("🚀 X-Rony Panel", callback_data="adm_xrony_menu")],
            [InlineKeyboardButton("🔙 Back", callback_data="adm_back")]
        ])
        await query.message.edit_text(sys_text, parse_mode="Markdown", reply_markup=sys_keyboard)

    # --- Menu Design Control Hub ---
    elif query.data == "menu_design" and await is_admin(user_id):
        await query.answer()
        menu_text = (
            f"🎨 **Menu & Button Customization Hub**\n\n"
            f"বটের স্টার্ট মেসেজ এবং রিপ্লাই বাটনগুলোর নাম এখান থেকে আপনার পছন্দমতো পরিবর্তন করতে পারবেন।"
        )
        menu_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Edit Start Menu", callback_data="m_edit_start"), InlineKeyboardButton("✏️ Edit GET NUMBER", callback_data="m_edit_get")],
            [InlineKeyboardButton("✏️ Edit Search Number", callback_data="m_edit_search"), InlineKeyboardButton("✏️ Edit Select Country", callback_data="m_edit_country")],
            [InlineKeyboardButton("✏️ Edit TRAFFIC", callback_data="m_edit_traffic"), InlineKeyboardButton("✏️ Edit Refer", callback_data="m_edit_refer")],
            [InlineKeyboardButton("✏️ Edit WITHDRAWAL", callback_data="m_edit_withdraw"), InlineKeyboardButton("✏️ Edit SUPPORT", callback_data="m_edit_support")],
            [InlineKeyboardButton("🔄 Reset Defaults", callback_data="m_reset_defaults")],
            [InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")]
        ])
        await query.message.edit_text(menu_text, parse_mode="Markdown", reply_markup=menu_keyboard)

    elif query.data.startswith("m_edit_") and await is_admin(user_id):
        await query.answer()
        action = query.data.replace("m_edit_", "")
        MENU_EDIT_STATE[user_id] = {"action": action}
        
        prompts = {
            "start": "✏️ নতুন স্টার্ট মেনু টেক্সট লিখে পাঠান (Variables ব্যবহার করতে পারেন যেমন: `{first_name}`):",
            "get": "✏️ 'GET NUMBER' বাটনটির জন্য নতুন নাম লিখে পাঠান:",
            "search": "✏️ 'SEARCH NUMBER' বাটনটির জন্য নতুন নাম লিখে পাঠান:",
            "country": "✏️ সিলেক্ট কান্ট্রি সংক্রান্ত মেসেজ বা লেবেল পরিবর্তনের জন্য নতুন টেক্সট পাঠান:",
            "traffic": "✏️ 'TRAFFIC' বাটনটির জন্য নতুন নাম লিখে পাঠান:",
            "refer": "✏️ 'REFERRAL' বাটনটির জন্য নতুন নাম লিখে পাঠান:",
            "withdraw": "✏️ উইথড্রয়াল সেকশনের হেডার বা বাটন নাম পরিবর্তন করতে নতুন টেক্সট পাঠান:",
            "support": "✏️ 'SUPPORT' বাটনটির জন্য নতুন নাম লিখে পাঠান:"
        }
        await query.message.edit_text(
            prompts.get(action, "✏️ নতুন নাম বা টেক্সট লিখে পাঠান:"),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu_design")]])
        )

    elif query.data == "m_reset_defaults" and await is_admin(user_id):
        await settings_col.delete_many({"_id": {"$in": [
            "start_menu_text", "btn_get_number", "btn_search_number", 
            "btn_traffic", "btn_refer", "btn_balance", "btn_support"
        ]}})
        await query.answer("✅ সকল মেনু এবং বাটন ডিফল্ট সেটিংয়ে ফিরিয়ে আনা হয়েছে!", show_alert=True)
        
        menu_text = f"🎨 **Menu & Button Customization Hub**\n\nবটের স্টার্ট মেসেজ এবং রিপ্লাই বাটনগুলোর নাম এখান থেকে আপনার পছন্দমতো পরিবর্তন করতে পারবেন।"
        menu_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Edit Start Menu", callback_data="m_edit_start"), InlineKeyboardButton("✏️ Edit GET NUMBER", callback_data="m_edit_get")],
            [InlineKeyboardButton("✏️ Edit Search Number", callback_data="m_edit_search"), InlineKeyboardButton("✏️ Edit Select Country", callback_data="m_edit_country")],
            [InlineKeyboardButton("✏️ Edit TRAFFIC", callback_data="m_edit_traffic"), InlineKeyboardButton("✏️ Edit Refer", callback_data="m_edit_refer")],
            [InlineKeyboardButton("✏️ Edit WITHDRAWAL", callback_data="m_edit_withdraw"), InlineKeyboardButton("✏️ Edit SUPPORT", callback_data="m_edit_support")],
            [InlineKeyboardButton("🔄 Reset Defaults", callback_data="m_reset_defaults")],
            [InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")]
        ])
        await query.message.edit_text(menu_text, parse_mode="Markdown", reply_markup=menu_keyboard)

    # --- RanaX Custom OTP Source & ON/OFF Control Menu ---
    elif query.data == "ranax_control" and await is_admin(user_id):
        await query.answer()
        ranax_status = await get_setting("ranax_status", "ON")
        sources = await ranax_groups_col.find({}).to_list(length=50)

        text = (
            f"🛡️ **RanaX Auto-OTP Forwarder Panel**\n\n"
            f"⚡ System Status: `{ranax_status}`\n"
            f"📌 সোর্স চ্যাট আইডি বা গ্রুপ লিস্ট নিচে দেওয়া হলো:"
        )

        keyboard = []
        if sources:
            for s in sources:
                g_id = s.get("chat_id")
                g_name = s.get("name", "Source Group")
                keyboard.append([
                    InlineKeyboardButton(f"📁 {g_name} (`{g_id}`)", callback_data=f"noop_rx_{g_id}"),
                    InlineKeyboardButton("❌ ডিলিট", callback_data=f"rx_del:{g_id}")
                ])
        else:
            text += "\n\n⚠️ কোনো সোর্স চ্যাট আইডি যুক্ত করা হয়নি।"

        status_btn_text = "🔴 Turn OFF" if ranax_status == "ON" else "🟢 Turn ON"
        status_toggle_val = "OFF" if ranax_status == "ON" else "ON"

        keyboard.append([InlineKeyboardButton(status_btn_text, callback_data=f"rx_toggle:{status_toggle_val}")])
        keyboard.append([InlineKeyboardButton("➕ Add Source Chat ID", callback_data="rx_add_start")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")])

        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("rx_toggle:") and await is_admin(user_id):
        val = query.data.split(":", 1)[1]
        await set_setting("ranax_status", val)
        await query.answer(f"RanaX System status updated to {val}!", show_alert=True)
        
        ranax_status = val
        sources = await ranax_groups_col.find({}).to_list(length=50)
        text = f"🛡️ **RanaX Auto-OTP Forwarder Panel**\n\n⚡ System Status: `{ranax_status}`\n📌 সোর্স চ্যাট আইডি বা গ্রুপ লিস্ট নিচে দেওয়া হলো:"
        keyboard = []
        for s in sources:
            g_id = s.get("chat_id")
            g_name = s.get("name", "Source Group")
            keyboard.append([
                InlineKeyboardButton(f"📁 {g_name} (`{g_id}`)", callback_data=f"noop_rx_{g_id}"),
                InlineKeyboardButton("❌ ডিলিট", callback_data=f"rx_del:{g_id}")
            ])
        status_btn_text = "🔴 Turn OFF" if ranax_status == "ON" else "🟢 Turn ON"
        status_toggle_val = "OFF" if ranax_status == "ON" else "ON"
        keyboard.append([InlineKeyboardButton(status_btn_text, callback_data=f"rx_toggle:{status_toggle_val}")])
        keyboard.append([InlineKeyboardButton("➕ Add Source Chat ID", callback_data="rx_add_start")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "rx_add_start" and await is_admin(user_id):
        await query.answer()
        RANAX_ADD_STATE[user_id] = {"step": "GET_NAME"}
        await query.message.edit_text(
            "➕ **Add RanaX Source Chat**\n\nদয়া করে গ্রুপ বা চ্যানেলের নাম (Name) লিখে পাঠান:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="ranax_control")]])
        )

    elif query.data.startswith("rx_del:") and await is_admin(user_id):
        del_id = query.data.split(":", 1)[1]
        await ranax_groups_col.delete_one({"chat_id": del_id})
        await query.answer("✅ Source Chat ID successfully removed!", show_alert=True)
        
        ranax_status = await get_setting("ranax_status", "ON")
        sources = await ranax_groups_col.find({}).to_list(length=50)
        text = f"🛡️ **RanaX Auto-OTP Forwarder Panel**\n\n⚡ System Status: `{ranax_status}`\n📌 সোর্স চ্যাট আইডি বা গ্রুপ লিস্ট নিচে দেওয়া হলো:"
        keyboard = []
        for s in sources:
            g_id = s.get("chat_id")
            g_name = s.get("name", "Source Group")
            keyboard.append([
                InlineKeyboardButton(f"📁 {g_name} (`{g_id}`)", callback_data=f"noop_rx_{g_id}"),
                InlineKeyboardButton("❌ ডিলিট", callback_data=f"rx_del:{g_id}")
            ])
        status_btn_text = "🔴 Turn OFF" if ranax_status == "ON" else "🟢 Turn ON"
        status_toggle_val = "OFF" if ranax_status == "ON" else "ON"
        keyboard.append([InlineKeyboardButton(status_btn_text, callback_data=f"rx_toggle:{status_toggle_val}")])
        keyboard.append([InlineKeyboardButton("➕ Add Source Chat ID", callback_data="rx_add_start")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # --- 1. Admin Management System ---
    elif query.data == "adm_mgmt_menu" and await is_admin(user_id):
        await query.answer()
        admins = await admins_col.find({}).to_list(length=100)
        text = f"👑 **Admin Management System**\n\nPrimary Owner ID: `{OWNER_ID}`\n\n**Current Admins:**"
        
        keyboard = []
        if not admins:
            keyboard.append([InlineKeyboardButton("⚠️ কোনো সাব-এডমিন নেই", callback_data="noop")])
        else:
            for adm in admins:
                adm_id = adm['user_id']
                adm_name = adm.get('username', 'Admin')
                keyboard.append([
                    InlineKeyboardButton(f"👤 {adm_name} (`{adm_id}`)", callback_data=f"noop_{adm_id}"),
                    InlineKeyboardButton("❌ রিমুভ", callback_data=f"adm_do_rem:{adm_id}")
                ])

        keyboard.append([InlineKeyboardButton("➕ Add Admin", callback_data="adm_add_start")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")])
        
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "adm_add_start" and user_id == OWNER_ID:
        await query.answer()
        ADMIN_ADD_STATE[user_id] = True
        await query.message.edit_text(
            "➕ **Add New Admin**\n\nদয়া করে নতুন এডমিনের **Telegram Chat ID** বা ইউজারনেম লিখে পাঠান:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_mgmt_menu")]])
        )

    elif query.data.startswith("adm_do_rem:") and user_id == OWNER_ID:
        rem_id = int(query.data.split(":", 1)[1])
        await admins_col.delete_one({"user_id": rem_id})
        await query.answer(f"✅ Admin {rem_id} successfully removed!", show_alert=True)
        
        admins = await admins_col.find({}).to_list(length=100)
        text = f"👑 **Admin Management System**\n\nPrimary Owner ID: `{OWNER_ID}`\n\n**Current Admins:**"
        keyboard = []
        for adm in admins:
            adm_id = adm['user_id']
            adm_name = adm.get('username', 'Admin')
            keyboard.append([
                InlineKeyboardButton(f"👤 {adm_name} (`{adm_id}`)", callback_data=f"noop_{adm_id}"),
                InlineKeyboardButton("❌ রিমুভ", callback_data=f"adm_do_rem:{adm_id}")
            ])
        keyboard.append([InlineKeyboardButton("➕ Add Admin", callback_data="adm_add_start")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # --- 2. Force Join System ---
    elif query.data == "adm_fj_menu" and await is_admin(user_id):
        await query.answer()
        fj_status = await get_setting("force_join_status", "ON")
        channels = await channels_col.find({}).to_list(length=50)
        
        text = f"📢 **Force Join System Control**\n\nSTATUS: `{fj_status}`\n\n**Managed Channels:**"
        
        keyboard = []
        if channels:
            for c in channels:
                c_name = c.get('name', 'Channel')
                c_id = c.get('chat_id')
                keyboard.append([
                    InlineKeyboardButton(f"📢 {c_name} (`{c_id}`)", callback_data=f"noop_chan_{c_id}"),
                    InlineKeyboardButton("🗑️ রিমুভ", callback_data=f"fj_do_del:{c_id}")
                ])
        else:
            text += "\n⚠️ কোনো কাস্টম চ্যানেল যুক্ত করা হয়নি।"

        status_toggle_btn = "🔴 Turn OFF" if fj_status == "ON" else "🟢 Turn ON"
        toggle_val = "OFF" if fj_status == "ON" else "ON"

        keyboard.append([InlineKeyboardButton(status_toggle_btn, callback_data=f"set_fj:{toggle_val}")])
        keyboard.append([InlineKeyboardButton("➕ Add Channel", callback_data="fj_add_ch")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")])
        
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("set_fj:") and await is_admin(user_id):
        val = query.data.split(":", 1)[1]
        await set_setting("force_join_status", val)
        await query.answer(f"Force Join Status set to {val}!", show_alert=True)
        
        fj_status = val
        channels = await channels_col.find({}).to_list(length=50)
        text = f"📢 **Force Join System Control**\n\nSTATUS: `{fj_status}`\n\n**Managed Channels:**"
        keyboard = []
        for c in channels:
            keyboard.append([
                InlineKeyboardButton(f"📢 {c.get('name')} (`{c.get('chat_id')}`)", callback_data=f"noop"),
                InlineKeyboardButton("🗑️ রিমুভ", callback_data=f"fj_do_del:{c.get('chat_id')}")
            ])
        status_toggle_btn = "🔴 Turn OFF" if fj_status == "ON" else "🟢 Turn ON"
        toggle_val = "OFF" if fj_status == "ON" else "ON"
        keyboard.append([InlineKeyboardButton(status_toggle_btn, callback_data=f"set_fj:{toggle_val}")])
        keyboard.append([InlineKeyboardButton("➕ Add Channel", callback_data="fj_add_ch")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "fj_add_ch" and await is_admin(user_id):
        await query.answer()
        CHANNEL_ADD_STATE[user_id] = {"step": "GET_NAME"}
        await query.message.edit_text(
            "📢 **Add Force Join Channel**\n\nদয়া করে চ্যানেলের নাম (Name) লিখে পাঠান:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_fj_menu")]])
        )

    elif query.data.startswith("fj_do_del:") and await is_admin(user_id):
        chat_id_to_del = query.data.split(":", 1)[1]
        await channels_col.delete_one({"chat_id": chat_id_to_del})
        await query.answer("✅ Channel successfully deleted!", show_alert=True)
        
        fj_status = await get_setting("force_join_status", "ON")
        channels = await channels_col.find({}).to_list(length=50)
        text = f"📢 **Force Join System Control**\n\nSTATUS: `{fj_status}`\n\n**Managed Channels:**"
        keyboard = []
        for c in channels:
            keyboard.append([
                InlineKeyboardButton(f"📢 {c.get('name')} (`{c.get('chat_id')}`)", callback_data="noop"),
                InlineKeyboardButton("🗑️ রিমুভ", callback_data=f"fj_do_del:{c.get('chat_id')}")
            ])
        status_toggle_btn = "🔴 Turn OFF" if fj_status == "ON" else "🟢 Turn ON"
        toggle_val = "OFF" if fj_status == "ON" else "ON"
        keyboard.append([InlineKeyboardButton(status_toggle_btn, callback_data=f"set_fj:{toggle_val}")])
        keyboard.append([InlineKeyboardButton("➕ Add Channel", callback_data="fj_add_ch")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # --- 3. User Management & Analytics ---
    elif query.data == "adm_usermgmt_menu" and await is_admin(user_id):
        await query.answer()
        total_u = await users_col.count_documents({})
        verified_u = await users_col.count_documents({"balance": {"$gt": 0.0}})
        banned_u = await users_col.count_documents({"banned": True})

        text = (
            f"👥 **User Management & Analytics**\n\n"
            f"📊 **Live Statistics:**\n"
            f"👥 Total Users: `{total_u}`\n"
            f"🟢 Verified Users: `{verified_u}`\n"
            f"🔴 Banned Users: `{banned_u}`\n\n"
            f"নিচের অপশনগুলো থেকে ম্যানেজ করুন:"
        )
        keyboard = [
            [InlineKeyboardButton("💰 Balance", callback_data="us_m_balance"), InlineKeyboardButton("🚫 Ban/Unban", callback_data="us_m_ban")],
            [InlineKeyboardButton("👤 Profile", callback_data="us_m_profile"), InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")]
        ]
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "us_m_balance" and await is_admin(user_id):
        await query.answer()
        USER_MANAGE_STATE[user_id] = {"action": "balance"}
        await query.message.edit_text("💰 ব্যালেন্স ম্যানেজ করতে ইউজারের **Chat ID** বা **Username** লিখে পাঠান:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_usermgmt_menu")]]))

    elif query.data == "us_m_ban" and await is_admin(user_id):
        await query.answer()
        USER_MANAGE_STATE[user_id] = {"action": "ban"}
        await query.message.edit_text("🚫 ব্যান বা আনব্যান করতে ইউজারের **Chat ID** বা **Username** লিখে পাঠান:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_usermgmt_menu")]]))

    elif query.data == "us_m_profile" and await is_admin(user_id):
        await query.answer()
        USER_MANAGE_STATE[user_id] = {"action": "profile"}
        await query.message.edit_text("👤 ইউজারের ফুল ডিটেইলস দেখতে তার **Chat ID** বা **Username** লিখে পাঠান:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_usermgmt_menu")]]))

    # --- 4. OTP Group Management ---
    elif query.data == "adm_otpgroup_menu" and await is_admin(user_id):
        await query.answer()
        groups = await forward_groups_col.find({}).to_list(length=50)
        text = f"💬 **OTP Group Management**\n\n**Configured Forward Groups:**"
        
        keyboard = []
        if groups:
            for g in groups:
                g_id = g.get('group_id')
                g_name = g.get('name', 'OTP Group')
                keyboard.append([
                    InlineKeyboardButton(f"🛡️ {g_name} (`{g_id}`)", callback_data=f"noop_group_{g_id}"),
                    InlineKeyboardButton("❌ রিমুভ", callback_data=f"ot_do_del:{g_id}")
                ])
        else:
            text += "\n⚠️ কোনো ফরওয়ার্ড গ্রুপ সেট করা হয়নি।"

        keyboard.append([InlineKeyboardButton("✏️ Edit OTP Button Link", callback_data="ot_edit_link")])
        keyboard.append([InlineKeyboardButton("➕ Add Forward Group", callback_data="ot_add_group")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")])
        
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "ot_edit_link" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "edit_otp_link"}
        await query.message.edit_text("✏️ নতুন বট লিংক বা চ্যানেল লিংক লিখে পাঠান যা ওটিপি গ্রুপের বাটনে সেট হবে:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_otpgroup_menu")]]))

    elif query.data == "ot_add_group" and await is_admin(user_id):
        await query.answer()
        FORWARD_GROUP_ADD_STATE[user_id] = {"step": "GET_ID"}
        await query.message.edit_text("➕ নতুন ফরওয়ার্ড গ্রুপের **Chat ID** লিখে পাঠান:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_otpgroup_menu")]]))

    elif query.data.startswith("ot_do_del:") and await is_admin(user_id):
        gid = query.data.split(":", 1)[1]
        await forward_groups_col.delete_one({"group_id": gid})
        await query.answer("✅ Group successfully deleted!", show_alert=True)
        
        groups = await forward_groups_col.find({}).to_list(length=50)
        text = f"💬 **OTP Group Management**\n\n**Configured Forward Groups:**"
        keyboard = []
        for g in groups:
            keyboard.append([
                InlineKeyboardButton(f"🛡️ {g.get('name', 'Group')} (`{g.get('group_id')}`)", callback_data="noop"),
                InlineKeyboardButton("❌ রিমুভ", callback_data=f"ot_do_del:{g.get('group_id')}")
            ])
        keyboard.append([InlineKeyboardButton("✏️ Edit OTP Button Link", callback_data="ot_edit_link")])
        keyboard.append([InlineKeyboardButton("➕ Add Forward Group", callback_data="ot_add_group")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # --- 5. X-Rony Control Panel ---
    elif query.data == "adm_xrony_menu" and await is_admin(user_id):
        await query.answer()
        wd_status = await get_setting("withdraw_global_status", "ON")
        min_wd = await get_setting("min_withdraw", 100.0)
        ref_bonus = await get_setting("ref_bonus", 0.01)
        otp_rate = await get_setting("otp_rate", 0.60)
        num_req = await get_setting("num_request_count", 2)
        cooldown = await get_setting("cooldown_timer", 5)

        text = (
            f"🚀 **X-Rony Advanced Control Panel**\n\n"
            f"💸 Withdrawal Status: `{wd_status}`\n"
            f"💵 Min Withdraw: `{min_wd}৳`\n"
            f"👥 Referral Bonus: `{ref_bonus}৳`\n"
            f"⚡ OTP Reward Rate: `{otp_rate}৳`\n"
            f"📦 Numbers per Request: `{num_req}`\n"
            f"⏱️ Cooldown Timer: `{cooldown}s`\n\n"
            f"নিচের অপশনগুলো থেকে মান পরিবর্তন করুন:"
        )
        keyboard = [
            [InlineKeyboardButton("💸 Toggle Withdraw", callback_data="xr_toggle_wd")],
            [InlineKeyboardButton("💵 Min Withdraw", callback_data="xr_set_minwd"), InlineKeyboardButton("👥 Refer Bonus", callback_data="xr_set_ref")],
            [InlineKeyboardButton("⚡ OTP Rate", callback_data="xr_set_otprate"), InlineKeyboardButton("📦 Num/Req", callback_data="xr_set_numreq")],
            [InlineKeyboardButton("⏱️ Cooldown", callback_data="xr_set_cooldown"), InlineKeyboardButton("💳 Pay Methods", callback_data="xr_pay_methods")],
            [InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")]
        ]
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "xr_toggle_wd" and await is_admin(user_id):
        current = await get_setting("withdraw_global_status", "ON")
        new_val = "OFF" if current == "ON" else "ON"
        await set_setting("withdraw_global_status", new_val)
        await query.answer(f"Withdrawal status changed to {new_val}", show_alert=True)
        
        wd_status = new_val
        min_wd = await get_setting("min_withdraw", 100.0)
        ref_bonus = await get_setting("ref_bonus", 0.01)
        otp_rate = await get_setting("otp_rate", 0.60)
        num_req = await get_setting("num_request_count", 2)
        cooldown = await get_setting("cooldown_timer", 5)
        text = (
            f"🚀 **X-Rony Advanced Control Panel**\n\n"
            f"💸 Withdrawal Status: `{wd_status}`\n"
            f"💵 Min Withdraw: `{min_wd}৳`\n"
            f"👥 Referral Bonus: `{ref_bonus}৳`\n"
            f"⚡ OTP Reward Rate: `{otp_rate}৳`\n"
            f"📦 Numbers per Request: `{num_req}`\n"
            f"⏱️ Cooldown Timer: `{cooldown}s`\n"
        )
        keyboard = [
            [InlineKeyboardButton("💸 Toggle Withdraw", callback_data="xr_toggle_wd")],
            [InlineKeyboardButton("💵 Min Withdraw", callback_data="xr_set_minwd"), InlineKeyboardButton("👥 Refer Bonus", callback_data="xr_set_ref")],
            [InlineKeyboardButton("⚡ OTP Rate", callback_data="xr_set_otprate"), InlineKeyboardButton("📦 Num/Req", callback_data="xr_set_numreq")],
            [InlineKeyboardButton("⏱️ Cooldown", callback_data="xr_set_cooldown"), InlineKeyboardButton("💳 Pay Methods", callback_data="xr_pay_methods")],
            [InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")]
        ]
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "xr_set_minwd" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "set_min_withdraw"}
        await query.message.edit_text("💵 নতুন মিনিমাম উইথড্র অ্যামাউন্ট লিখে পাঠান (যেমন: `150`):", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_xrony_menu")]]))

    elif query.data == "xr_set_ref" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "set_ref_bonus"}
        await query.message.edit_text("👥 নতুন রেফার বোনাস অ্যামাউন্ট লিখে পাঠান (যেমন: `0.05`):", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_xrony_menu")]]))

    elif query.data == "xr_set_otprate" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "set_otp_rate"}
        await query.message.edit_text("⚡ প্রতি ওটিপি রেট লিখে পাঠান (যেমন: `0.80`):", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_xrony_menu")]]))

    elif query.data == "xr_set_numreq" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "set_num_req"}
        await query.message.edit_text("📦 এক সাথে ইউজারকে কয়টি করে নাম্বার দেওয়া হবে তা লিখুন (যেমন: `5`):", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_xrony_menu")]]))

    elif query.data == "xr_set_cooldown" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "set_cooldown"}
        await query.message.edit_text("⏱️ কোডাউন সেকেন্ড সেট করুন (যেমন: `10`):", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_xrony_menu")]]))

    elif query.data == "xr_pay_methods" and await is_admin(user_id):
        await query.answer()
        methods = await get_setting("payment_methods", ["Bkash", "Nagad", "Binance"])
        text = f"💳 **Payment Methods Control**\n\nCurrent Methods: `{', '.join(methods)}`\n\nনতুন মেথড যোগ করতে বা রিমুভ করতে নিচের অপশন ব্যবহার করুন:"
        keyboard = [
            [InlineKeyboardButton("➕ Add Method", callback_data="xr_add_pay"), InlineKeyboardButton("🗑️ Remove Method", callback_data="xr_rem_pay")],
            [InlineKeyboardButton("🔙 Back", callback_data="adm_xrony_menu")]
        ]
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "xr_add_pay" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "add_pay_method"}
        await query.message.edit_text("➕ নতুন পেমেন্ট মেথডের নাম লিখে পাঠান (যেমন: `Rocket`):", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="xr_pay_methods")]]))

    elif query.data == "xr_rem_pay" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "rem_pay_method"}
        await query.message.edit_text("🗑️ যে পেমেন্ট মেথডটি ডিলিট করতে চান তার নাম লিখে পাঠান:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="xr_pay_methods")]]))

    elif query.data == "adm_leaderboard" and await is_admin(user_id):
        await query.answer()
        cursor = users_col.find({}).sort("total_earned", -1).limit(10)
        top_users = await cursor.to_list(length=10)
        text = "🏆 **OTP Hunter Leaderboard** 🏆\n\n"
        rank_emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        if not top_users:
            text += "⚠️ বর্তমানে কোনো লিডারবোর্ড ডাটা নেই。"
        else:
            for index, u in enumerate(top_users):
                emoji = rank_emojis[index] if index < 10 else "👤"
                uname = f"@{u['username']}" if u.get('username') else f"User `{u['user_id']}`"
                earned = u.get('total_earned', 0.0)
                text += f"{emoji} {uname} — `💰 {earned:.2f}৳`\n"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif query.data == "adm_upload" and await is_admin(user_id):
        await query.answer()
        ADMIN_UPLOAD_STATE[user_id] = {"step": "GET_SERVICE"}
        await query.message.edit_text("⚙️ কোন সার্ভিসের নাম্বার আপলোড করবেন সেই নাম লিখে পাঠান (যেমন: Facebook):", parse_mode="Markdown")

    elif query.data == "adm_delete" and await is_admin(user_id):
        await query.answer()
        pipeline = [{"$group": {"_id": {"service": "$service_name", "country": "$country"}, "count": {"$sum": 1}}}]
        cursor = numbers_col.aggregate(pipeline)
        batches = await cursor.to_list(length=100)
        if not batches:
            text = "🗑️ **Delete Files**\n\nবর্তমানে সিস্টেমে কোনো ফাইল বা ব্যাচ এভেইলেবল নেই।"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])
        else:
            text = "🗑️ **Delete Files / Batches**\n\nনিচের তালিকা থেকে যে ফাইলটি মুছে ফেলতে চান সেটিতে ক্লিক করুন:"
            keyboard_buttons = []
            for b in batches:
                serv = b["_id"]["service"]
                count = b["count"]
                keyboard_buttons.append([InlineKeyboardButton(f"❌ {serv} ({count} Nos)", callback_data=f"adm_delfile:{serv}")])
            keyboard_buttons.append([InlineKeyboardButton("🔙 Back", callback_data="adm_back")])
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif query.data.startswith("adm_delfile:") and await is_admin(user_id):
        service_to_del = query.data.split(":", 1)[1]
        await numbers_col.delete_many({"service_name": service_to_del})
        await traffic_col.delete_many({"service": service_to_del})
        await query.answer(f"✅ সফলভাবে {service_to_del} এর সব নাম্বার ডিলিট করা হয়েছে!", show_alert=True)
        
        pipeline = [{"$group": {"_id": {"service": "$service_name", "country": "$country"}, "count": {"$sum": 1}}}]
        cursor = numbers_col.aggregate(pipeline)
        batches = await cursor.to_list(length=100)
        if not batches:
            text = "🗑️ **Delete Files**\n\nবর্তমানে সিস্টেমে কোনো ফাইল বা ব্যাচ এভেইলেবল নেই।"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])
        else:
            text = "🗑️ **Delete Files / Batches**\n\nনিচের তালিকা থেকে যে ফাইলটি মুছে ফেলতে চান সেটিতে ক্লিক করুন:"
            keyboard_buttons = []
            for b in batches:
                serv = b["_id"]["service"]
                count = b["count"]
                keyboard_buttons.append([InlineKeyboardButton(f"❌ {serv} ({count} Nos)", callback_data=f"adm_delfile:{serv}")])
            keyboard_buttons.append([InlineKeyboardButton("🔙 Back", callback_data="adm_back")])
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif query.data == "adm_broadcast" and await is_admin(user_id):
        await query.answer()
        ADMIN_BROADCAST_STATE[user_id] = True
        await query.message.edit_text(
            "📢 **Broadcast System**\n\nদয়া করে যে মেসেজটি সকল ইউজারের কাছে পাঠাতে চান সেটি লিখে পাঠান:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])
        )

    elif query.data == "adm_close" and await is_admin(user_id):
        await query.answer("প্যানেল বন্ধ করা হয়েছে।")
        try:
            await query.message.delete()
        except Exception:
            pass

    elif query.data == "adm_back" and await is_admin(user_id):
        await query.answer()
        if user_id in ADMIN_BROADCAST_STATE:
            del ADMIN_BROADCAST_STATE[user_id]
        text, markup = await get_admin_panel_markup(user_id)
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
        wd_status = await get_setting("withdraw_global_status", "ON")
        if wd_status != "ON":
            await query.message.reply_text("❌ বর্তমানে উইথড্র সিস্টেম গ্লোবালি বন্ধ রাখা হয়েছে।", parse_mode="Markdown")
            return

        user_data = await users_col.find_one({"user_id": user_id})
        balance = user_data.get("balance", 0.0) if user_data else 0.0
        min_wd = float(await get_setting("min_withdraw", 100.0))
        
        if balance < min_wd:
            await query.message.reply_text(
                f"❌ দুঃখিত! উইথড্র করার জন্য আপনার অন্তত `{min_wd}৳` ব্যালেন্স থাকতে হবে。\n"
                f"আপনার বর্তমান ব্যালেন্স: `{balance:.2f}৳`",
                parse_mode="Markdown"
            )
            return
        
        USER_WITHDRAW_STATE[user_id] = {"step": "SELECT_METHOD"}
        methods = await get_setting("payment_methods", ["Bkash", "Nagad", "Binance"])
        keyboard = []
        for m in methods:
            keyboard.append([InlineKeyboardButton(f"📱 {m}", callback_data=f"wd_meth:{m}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Balance", callback_data="back_to_balance")])
        
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
        await query.message.edit_text(
            f"💳 Selected Method: **{method}**\n\n"
            f"দয়া করে আপনার সঠিক অ্যাকাউন্ট নাম্বার বা অ্যাড্রেস লিখে পাঠান:",
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
                await query.message.edit_text("⚠️ সেশন মেয়াদোত্তীর্ণ হয়ে গেছে।")
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
                f"⏳ রিকোয়েস্টটি রিভিউ করে পেমেন্ট সম্পন্ন করা হবে। ধন্যবাদ!",
                parse_mode="Markdown"
            )
            
            username_str = f"@{query.from_user.username}" if query.from_user.username else "No Username"
            admin_msg = (
                f"🚨 **New Withdrawal Request!**\n\n"
                f"👤 User ID: `{user_id}`\n"
                f"🔗 Username: {username_str}\n"
                f"💳 Method: `{method}`\n"
                f"📥 Account: `{account}`\n"
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
            except Exception:
                pass
        else:
            if user_id in USER_WITHDRAW_STATE:
                del USER_WITHDRAW_STATE[user_id]
            await query.message.edit_text("❌ উইথড্র রিকোয়েস্ট বাতিল করা হয়েছে।")

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

    elif query.data == "get_number_menu":
        await query.answer()
        services = await numbers_col.distinct("service_name", {"status": "Available"})
        if services:
            keyboard = [[InlineKeyboardButton(f"📱 {s}", callback_data=f"sel_serv:{s}")] for s in services]
            keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_main_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            text_msg = "📱 **Select a Service:**"
        else:
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_main_menu")]])
            text_msg = "📱 **Get Number Menu**\n\n⚠️ বর্তমানে কোনো নাম্বার স্টক এ নেই!"
        try:
            await query.message.edit_text(text_msg, parse_mode="Markdown", reply_markup=reply_markup)
        except Exception:
            await query.message.reply_text(text_msg, parse_mode="Markdown", reply_markup=reply_markup)

    elif query.data == "back_to_main_menu":
        await query.answer()
        user = query.from_user
        custom_welcome = await get_setting("start_menu_text", None)
        if not custom_welcome:
            welcome_text = (
                f"🌐 **NUMBER PANEL**\n\n"
                f"👋 Welcome, **{user.first_name}**\n"
                f"🚀 Premium Number Management System\n\n"
                f"⚡ Fast • Simple • Secure"
            )
        else:
            welcome_text = custom_welcome.format(first_name=user.first_name, username=user.username or "N/A", user_id=user.id)

        reply_markup = await build_main_menu(user_id)
        try:
            await query.message.edit_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)
        except Exception:
            await query.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

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
        
        num_req = int(await get_setting("num_request_count", 2))
        cursor = numbers_col.find({
            "service_name": {"$regex": f"^{service_name}$", "$options": "i"},
            "country": {"$regex": f"^{country}$", "$options": "i"},
            "status": "Available"
        }).limit(num_req)
        
        numbers = await cursor.to_list(length=num_req)
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
                f"🌍 {country} Allocated 💬 {service_name}\n"
                f"🔗 Otp Rate : {current_otp_rate}৳\n"
                f"⏳ Waiting for OTP...... ⬇️"
            )
            
            keyboard = []
            for doc in numbers:
                num = doc['phone_number']
                keyboard.append([InlineKeyboardButton(f"📲 📋 {num}", copy_text=CopyTextButton(text=num))])
            
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
        num_req = int(await get_setting("num_request_count", 2))
        
        cursor = numbers_col.find({
            "phone_number": {"$regex": f"^\\+?{prefix}", "$options": "i"},
            "status": "Available"
        }).limit(num_req)
        
        numbers = await cursor.to_list(length=num_req)
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
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌍 Other Countries", callback_data="get_number_menu")]] )
            )

# --- General Group Listener for OTP and RanaX Auto-Forwarding ---
async def otp_group_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    
    chat_id = str(message.chat_id)
    text = message.text

    # --- 1. RanaX External Source Forwarding System ---
    ranax_status = await get_setting("ranax_status", "ON")
    if ranax_status == "ON":
        source_doc = await ranax_groups_col.find_one({"chat_id": chat_id})
        if source_doc:
            forward_groups = await forward_groups_col.find({}).to_list(length=50)
            target_ids = [fg.get("group_id") for fg in forward_groups]
            if not target_ids:
                target_ids = [OTP_GROUP_URL]

            for tid in target_ids:
                try:
                    await context.bot.send_message(
                        chat_id=tid,
                        text=f"🔄 **RanaX Auto-Forwarded OTP:**\n\n{text}",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

    # --- 2. Main Bot User Number Matcher System ---
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
            
            country_iso = detect_country_iso(phone)
            user_msg = build_otp_display(
                service=service,
                phone=phone,
                otp_text=text,
                language="EN",
                country_iso=country_iso,
                test=False,
                rate=current_otp_rate,
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
            except Exception:
                pass

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text if update.message.text else ""

    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"username": update.effective_user.username}, "$setOnInsert": {"balance": 0.0, "total_earned": 0.0, "banned": False}},
        upsert=True
    )

    user_doc = await users_col.find_one({"user_id": user_id})
    if user_doc and user_doc.get("banned", False):
        await update.message.reply_text("❌ আপনি এই বট থেকে ব্যান হয়েছেন।")
        return

    if text == "🔙 Back":
        for state_dict in [ADMIN_UPLOAD_STATE, USER_SEARCH_STATE, ADMIN_SETTINGS_STATE, USER_WITHDRAW_STATE, ADMIN_BROADCAST_STATE, ADMIN_ADD_STATE, CHANNEL_ADD_STATE, FORWARD_GROUP_ADD_STATE, USER_MANAGE_STATE, RANAX_ADD_STATE, MENU_EDIT_STATE, TEST_FLOW_STATE]:
            if user_id in state_dict:
                del state_dict[user_id]
            
        reply_markup = await build_main_menu(user_id)
        await update.message.reply_text("👇 Main Menu:", reply_markup=reply_markup)
        return

    is_joined = await check_force_join(user_id, context)
    if not is_joined and text != "/start":
        channels_list = await channels_col.find({}).to_list(length=50)
        inline_kb = []
        if channels_list:
            for ch in channels_list:
                inline_kb.append([InlineKeyboardButton(f"📢 Join {ch.get('name')}", url=ch.get('url'))])
        else:
            inline_kb.append([InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_URL)])
            inline_kb.append([InlineKeyboardButton("📢 Join Update Channel", url=UPDATE_CHANNEL_URL)])
            
        inline_kb.append([InlineKeyboardButton("💬 Join OTP Group", url=OTP_GROUP_URL)])
        inline_kb.append([InlineKeyboardButton("✅ Joined / Check", callback_data="check_join")])

        await update.message.reply_text(
            "⚠️ আপনি চ্যানেল বা গ্রুপ থেকে লিভ নিয়েছেন!\nবট ব্যবহার করতে হলে আবার জয়েন করে চেক করুন:",
            reply_markup=InlineKeyboardMarkup(inline_kb)
        )
        return

    # --- Test Flow State Handler ---
    if await is_admin(user_id) and user_id in TEST_FLOW_STATE:
        state = TEST_FLOW_STATE[user_id]
        step = state.get("step")

        if step == "WAITING_FOR_SERVICE":
            state["serviceName"] = text.strip()
            state["step"] = "WAITING_FOR_PHONE"
            TEST_FLOW_STATE[user_id] = state
            await update.message.reply_text("📱 এবার ফোন নম্বরটি লিখে পাঠান:")
            return
        elif step == "WAITING_FOR_PHONE":
            phone = normalize_phone(text.strip())
            if not phone or not any(ch.isdigit() for ch in phone):
                await update.message.reply_text("❌ সঠিক ফোন নম্বর দিন। উদাহরণ: `+601862810138`", parse_mode="Markdown")
                return
            state["phoneNumber"] = phone
            state["countryISO"] = detect_country_iso(phone)
            state["step"] = "WAITING_FOR_OTP"
            TEST_FLOW_STATE[user_id] = state
            await update.message.reply_text(
                f"🔑 এবার ওটিপি (OTP) কোডটি লিখে পাঠান:\n\n🌍 Detected Country: `{state['countryISO']}`",
                parse_mode="Markdown"
            )
            return
        elif step == "WAITING_FOR_OTP":
            state["otpCode"] = text.strip()
            state["step"] = "WAITING_FOR_LANG"
            TEST_FLOW_STATE[user_id] = state
            
            lang_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("EN", callback_data="test_lang_en"),
                    InlineKeyboardButton("FR", callback_data="test_lang_fr")
                ],
                [
                    InlineKeyboardButton("ID", callback_data="test_lang_id"),
                    InlineKeyboardButton("BN", callback_data="test_lang_bn")
                ]
            ])
            country_iso = state.get("countryISO", "UN")
            await update.message.reply_text(
                f"🌐 মেসেজের ভাষা সিলেক্ট করুন:\n\n🌍 Country: `{country_iso}`\n💡 Language code 2 অক্ষরের হবে (EN, FR, ID, BN ইত্যাদি)।",
                parse_mode="Markdown",
                reply_markup=lang_keyboard
            )
            return

    # --- Menu Customization State Handler ---
    if await is_admin(user_id) and user_id in MENU_EDIT_STATE:
        state = MENU_EDIT_STATE[user_id]
        action = state.get("action")
        del MENU_EDIT_STATE[user_id]
        new_val = text.strip()

        key_mapping = {
            "start": "start_menu_text",
            "get": "btn_get_number",
            "search": "btn_search_number",
            "traffic": "btn_traffic",
            "refer": "btn_refer",
            "withdraw": "withdraw_header_text",
            "support": "btn_support"
        }
        
        db_key = key_mapping.get(action)
        if db_key:
            await set_setting(db_key, new_val)
            await update.message.reply_text(f"✅ সফলভাবে আপডেট করা হয়েছে!\n\nনতুন মান: `{new_val}`", parse_mode="Markdown")
        return

    # --- RanaX Source Chat ID Add State Handler ---
    if await is_admin(user_id) and user_id in RANAX_ADD_STATE:
        state = RANAX_ADD_STATE[user_id]
        step = state.get("step")
        if step == "GET_NAME":
            state["name"] = text.strip()
            state["step"] = "GET_CHAT_ID"
            RANAX_ADD_STATE[user_id] = state
            await update.message.reply_text("🔗 এখন ওই সোর্স গ্রুপ বা চ্যানেলের **Chat ID** (যেমন: `-100xxxxxxxxxx`) লিখে পাঠান:")
            return
        elif step == "GET_CHAT_ID":
            chat_id_val = text.strip()
            await ranax_groups_col.update_one(
                {"chat_id": chat_id_val},
                {"$set": {"name": state["name"], "chat_id": chat_id_val}},
                upsert=True
            )
            del RANAX_ADD_STATE[user_id]
            await update.message.reply_text("✅ RanaX Source Chat ID সফলভাবে যুক্ত করা হয়েছে! এখন থেকে ঐ গ্রুপ থেকে ওটিপি ফরোয়ার্ড হয়ে আসবে।")
            return

    if user_id == OWNER_ID and user_id in ADMIN_ADD_STATE:
        del ADMIN_ADD_STATE[user_id]
        target_val = text.strip()
        target_id = None
        if target_val.isdigit():
            target_id = int(target_val)
        else:
            usr = await users_col.find_one({"username": target_val.lstrip("@")})
            if usr:
                target_id = usr["user_id"]
        
        if target_id:
            await admins_col.update_one({"user_id": target_id}, {"$set": {"user_id": target_id, "username": target_val}}, upsert=True)
            await update.message.reply_text(f"✅ সফলভাবে ইউজার `{target_id}` কে এডমিন হিসেবে যুক্ত করা হয়েছে!", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ ইউজার খুঁজে পাওয়া যায়নি। সঠিক আইডি বা ইউজারনেম দিন।")
        return

    if await is_admin(user_id) and user_id in CHANNEL_ADD_STATE:
        state = CHANNEL_ADD_STATE[user_id]
        step = state.get("step")
        if step == "GET_NAME":
            state["name"] = text.strip()
            state["step"] = "GET_ID"
            CHANNEL_ADD_STATE[user_id] = state
            await update.message.reply_text("🔗 এখন চ্যানেলের চ্যাট আইডি (যেমন: `@mychannel` বা `-100...`) লিখে পাঠান:")
            return
        elif step == "GET_ID":
            state["chat_id"] = text.strip()
            state["step"] = "GET_URL"
            CHANNEL_ADD_STATE[user_id] = state
            await update.message.reply_text("🌐 এখন চ্যানেলের ইনভাইট লিংক লিখে পাঠান:")
            return
        elif step == "GET_URL":
            state["url"] = text.strip()
            await channels_col.update_one(
                {"chat_id": state["chat_id"]},
                {"$set": {"name": state["name"], "url": state["url"]}},
                upsert=True
            )
            del CHANNEL_ADD_STATE[user_id]
            await update.message.reply_text("✅ ফোর্স জয়েন চ্যানেল সফলভাবে যুক্ত করা হয়েছে!")
            return

    if await is_admin(user_id) and user_id in FORWARD_GROUP_ADD_STATE:
        state = FORWARD_GROUP_ADD_STATE[user_id]
        step = state.get("step")
        if step == "GET_ID":
            gid = text.strip()
            await forward_groups_col.update_one({"group_id": gid}, {"$set": {"group_id": gid}}, upsert=True)
            del FORWARD_GROUP_ADD_STATE[user_id]
            await update.message.reply_text(f"✅ ফরওয়ার্ড গ্রুপ `{gid}` সফলভাবে যুক্ত করা হয়েছে!")
            return

    if await is_admin(user_id) and user_id in USER_MANAGE_STATE:
        action = USER_MANAGE_STATE[user_id].get("action")
        del USER_MANAGE_STATE[user_id]
        target_val = text.strip()
        
        target_user = None
        if target_val.isdigit():
            target_user = await users_col.find_one({"user_id": int(target_val)})
        else:
            target_user = await users_col.find_one({"username": target_val.lstrip("@")})

        if not target_user:
            await update.message.reply_text("❌ ইউজার ডাটাবেজে পাওয়া যায়নি।")
            return

        u_id = target_user["user_id"]
        if action == "balance":
            USER_MANAGE_STATE[user_id] = {"action": "do_balance", "target_id": u_id}
            await update.message.reply_text(f"👤 User: `{u_id}`\n বর্তমান ব্যালেন্স: `{target_user.get('balance', 0.0)}৳`\n\nনতুন ব্যালেন্স অ্যামাউন্ট বা পরিবর্তন করার পরিমাণ (যেমন `+50` বা `200`) লিখে পাঠান:")
            return
        elif action == "ban":
            current_ban = target_user.get("banned", False)
            new_ban = not current_ban
            await users_col.update_one({"user_id": u_id}, {"$set": {"banned": new_ban}})
            status_str = "ব্যান করা হয়েছে" if new_ban else "আনব্যান করা হয়েছে"
            await update.message.reply_text(f"✅ ইউজার `{u_id}` সফলভাবে {status_str}।")
            return
        elif action == "profile":
            total_nums = await assigned_col.count_documents({"user_id": u_id})
            profile_text = (
                f"👤 **User Profile Details**\n\n"
                f"🆔 ID: `{u_id}`\n"
                f"🔗 Username: @{target_user.get('username', 'N/A')}\n"
                f"💰 Balance: `{target_user.get('balance', 0.0):.2f}৳`\n"
                f"📈 Total Earned: `{target_user.get('total_earned', 0.0):.2f}৳`\n"
                f"📱 Total Used/Assigned Numbers: `{total_nums}`\n"
                f"🚫 Banned Status: `{target_user.get('banned', False)}`"
            )
            await update.message.reply_text(profile_text, parse_mode="Markdown")
            return

    if await is_admin(user_id) and USER_MANAGE_STATE.get(user_id, {}).get("action") == "do_balance":
        state_data = USER_MANAGE_STATE[user_id]
        target_id = state_data["target_id"]
        del USER_MANAGE_STATE[user_id]
        try:
            val = float(text.strip())
            await users_col.update_one({"user_id": target_id}, {"$set": {"balance": val}})
            await update.message.reply_text(f"✅ ইউজার `{target_id}` এর নতুন ব্যালেন্স সেট করা হয়েছে: `{val}৳`")
        except ValueError:
            await update.message.reply_text("❌ সঠিক সংখ্যা দিন।")
        return

    if await is_admin(user_id) and user_id in ADMIN_SETTINGS_STATE:
        setting_type = ADMIN_SETTINGS_STATE[user_id].get("setting")
        del ADMIN_SETTINGS_STATE[user_id]
        val = text.strip()

        if setting_type == "edit_otp_link":
            await set_setting("otp_button_link", val)
            await update.message.reply_text(f"✅ OTP Button Link updated to: `{val}`", parse_mode="Markdown")
            return
        elif setting_type == "set_min_withdraw":
            try:
                num = float(val)
                await set_setting("min_withdraw", num)
                await update.message.reply_text(f"✅ Min Withdraw updated to: `{num}৳`")
            except ValueError:
                await update.message.reply_text("❌ সঠিক সংখ্যা দিন।")
            return
        elif setting_type == "set_ref_bonus":
            try:
                num = float(val)
                await set_setting("ref_bonus", num)
                await update.message.reply_text(f"✅ Referral Bonus updated to: `{num}৳`")
            except ValueError:
                await update.message.reply_text("❌ সঠিক সংখ্যা দিন।")
            return
        elif setting_type == "set_otp_rate":
            try:
                num = float(val)
                await set_setting("otp_rate", num)
                await update.message.reply_text(f"✅ OTP Rate updated to: `{num}৳`")
            except ValueError:
                await update.message.reply_text("❌ সঠিক সংখ্যা দিন।")
            return
        elif setting_type == "set_num_req":
            try:
                num = int(val)
                await set_setting("num_request_count", num)
                await update.message.reply_text(f"✅ Numbers per request updated to: `{num}`")
            except ValueError:
                await update.message.reply_text("❌ সঠিক পূর্ণসংখ্যা দিন।")
            return
        elif setting_type == "set_cooldown":
            try:
                num = int(val)
                await set_setting("cooldown_timer", num)
                await update.message.reply_text(f"✅ Cooldown timer updated to: `{num}s`")
            except ValueError:
                await update.message.reply_text("❌ সঠিক সংখ্যা দিন।")
            return
        elif setting_type == "add_pay_method":
            methods = await get_setting("payment_methods", ["Bkash", "Nagad", "Binance"])
            if val not in methods:
                methods.append(val)
                await set_setting("payment_methods", methods)
            await update.message.reply_text(f"✅ Payment method `{val}` added successfully!")
            return
        elif setting_type == "rem_pay_method":
            methods = await get_setting("payment_methods", ["Bkash", "Nagad", "Binance"])
            if val in methods:
                methods.remove(val)
                await set_setting("payment_methods", methods)
            await update.message.reply_text(f"✅ Payment method `{val}` removed successfully!")
            return

    if await is_admin(user_id) and user_id in ADMIN_BROADCAST_STATE:
        del ADMIN_BROADCAST_STATE[user_id]
        broadcast_text = text.strip()
        
        processing_msg = await update.message.reply_text("⏳ ব্রডকাস্ট মেসেজ পাঠানো হচ্ছে, দয়া করে অপেক্ষা করুন...")
        
        all_users_cursor = users_col.find({})
        success_count = 0
        async for u in all_users_cursor:
            try:
                await context.bot.send_message(
                    chat_id=u["user_id"],
                    text=f"📢 **Announcement:**\n\n{broadcast_text}",
                    parse_mode="Markdown"
                )
                success_count += 1
            except Exception:
                pass
                
        await processing_msg.edit_text(f"✅ **ব্রডকাস্ট সফলভাবে সম্পন্ন হয়েছে!**\n📬 মোট ডেলিভারি হয়েছে: `{success_count}` জন ইউজারের কাছে।", parse_mode="Markdown")
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
                min_wd = float(await get_setting("min_withdraw", 100.0))
                
                if amount <= 0:
                    await update.message.reply_text("❌ অ্যামাউন্ট সঠিক নয়। আবার চেষ্টা করুন:", reply_markup=back_keyboard())
                    return
                if amount > balance:
                    await update.message.reply_text(f"❌ আপনার পর্যাপ্ত ব্যালেন্স নেই! আপনার বর্তমান ব্যালেন্স: `{balance:.2f}৳`", parse_mode="Markdown", reply_markup=back_keyboard())
                    return
                if amount < min_wd:
                    await update.message.reply_text(f"❌ সর্বনিম্ন `{min_wd}৳` উইথড্র করতে হবে। সঠিক অ্যামাউন্ট দিন:", reply_markup=back_keyboard())
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
            reply_markup = await build_main_menu(user_id)
            await update.message.reply_text("❌ কান্ট্রি কোড বা সিরিয়াল খালি রাখা যাবে না।", reply_markup=reply_markup)
            return
            
        num_req = int(await get_setting("num_request_count", 2))
        cursor = numbers_col.find({
            "phone_number": {"$regex": f"^\\+?{prefix}", "$options": "i"},
            "status": "Available"
        }).limit(num_req)
        
        numbers = await cursor.to_list(length=num_req)
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
            reply_markup = await build_main_menu(user_id)
            await update.message.reply_text(
                f"❌ এই সিরিয়াল বা প্রফিক্স (`{prefix}`) দিয়ে কোনো নাম্বার খুঁজে পাওয়া যাচ্ছে না!",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        return

    if await is_admin(user_id) and user_id in ADMIN_UPLOAD_STATE:
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
            await update.message.reply_text(f"✅ সার্ভিস: `{service_name}` | কান্ট্রি: `{country}`\n\n📂 এখন নাম্বার ফাইল (`.txt`) সেন্ড করুন অথবা নাম্বারগুলো পেস্ট করে দিন:", parse_mode="Markdown", reply_markup=back_keyboard())
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
            
            asyncio.create_task(broadcast_new_numbers_alert(context, service_name, len(numbers_list)))
            
            success_text = (
                f"🎉 **সফলভাবে নাম্বার আপলোড সম্পন্ন হয়েছে!**\n\n"
                f"💬 সার্ভিস নাম: `{service_name}`\n"
                f"🌍 কান্ট্রি নাম: `{country}`\n"
                f"📱 মোট নাম্বার: `{len(numbers_list)} টি`\n\n"
                f"✅ এখন ইউজাররা গেট নাম্বার থেকে কাজ করতে পারবে।"
            )
            success_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Get Number", callback_data=f"sel_serv:{service_name}")]
            ])
            await update.message.reply_text(success_text, parse_mode="Markdown", reply_markup=success_keyboard)
            return

    if await is_admin(user_id) and update.message.document and user_id in ADMIN_UPLOAD_STATE:
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
            
            asyncio.create_task(broadcast_new_numbers_alert(context, service_name, len(numbers_list)))
            
            success_text = (
                f"🎉 **ফাইল থেকে সফলভাবে নাম্বার আপলোড সম্পন্ন হয়েছে!**\n\n"
                f"💬 সার্ভিস নাম: `{service_name}`\n"
                f"🌍 কান্ট্রি নাম: `{country}`\n"
                f"📱 মোট নাম্বার: `{len(numbers_list)} টি`\n\n"
                f"✅ এখন ইউজাররা গেট নাম্বার থেকে কাজ করতে পারবে।"
            )
            success_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Get Number", callback_data=f"sel_serv:{service_name}")]
            ])
            await update.message.reply_text(success_text, parse_mode="Markdown", reply_markup=success_keyboard)
            return

    # ডায়নামিক বাটন লেবেলের চেক
    btn_get_num = await get_setting("btn_get_number", "📱 GET NUMBER")
    btn_search_num = await get_setting("btn_search_number", "🔎 SEARCH NUMBER")
    btn_traffic = await get_setting("btn_traffic", "🚦 TRAFFIC")
    btn_refer = await get_setting("btn_refer", "👥 REFERRAL")
    btn_balance = await get_setting("btn_balance", "💰 BALANCE")
    btn_support = await get_setting("btn_support", "🆘 SUPPORT")

    if text == "/start":
        await start(update, context)
        
    elif text == btn_get_num:
        services = await numbers_col.distinct("service_name", {"status": "Available"})
        if services:
            keyboard = [[InlineKeyboardButton(f"📱 {s}", callback_data=f"sel_serv:{s}")] for s in services]
            keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_main_menu")])
            await update.message.reply_text("📱 **Select a Service:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("⚠️ বর্তমানে কোনো নাম্বার স্টক এ নেই!", parse_mode="Markdown")
        
    elif text == btn_search_num:
        USER_SEARCH_STATE[user_id] = True
        await update.message.reply_text("🔎 **Search Number**\n\nদয়া করে কান্ট্রি কোড বা সিরিয়াল নাম্বার লিখে পাঠান (যেমন: `223`):", parse_mode="Markdown", reply_markup=back_keyboard())
        
    elif text == btn_traffic:
        traffic_list = await traffic_col.find({}).to_list(length=100)
        if not traffic_list:
            traffic_text = "📊 বর্তমানে কোনো লাইভ ট্রাফিক ডাটা নেই।"
        else:
            traffic_text = "🚦 **1 HOUR LIVE TRAFFIC**\n\n"
            for item in traffic_list:
                traffic_text += f"🌍 **{item['service']}**\n{item['country']} : {item['status']} {item['icon']}\n\n"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_traffic")]])
        await update.message.reply_text(traffic_text, parse_mode="Markdown", reply_markup=keyboard)
        
    elif text == btn_refer:
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
        reply_markup = await build_main_menu(user_id)
        await update.message.reply_text(ref_text, parse_mode="Markdown", reply_markup=reply_markup)
        
    elif text == btn_balance:
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
        
    elif text == btn_support:
        support_text = (
            f"🆘 **SUPPORT & HELP DESK**\n\n"
            f"যেকোনো প্রয়োজনে সরাসরি আমাদের অফিসিয়াল অ্যাডমিনের সাথে যোগাযোগ করুন অথবা চ্যানেল ও গ্রুপে যুক্ত থাকুন。\n\n"
            f"👑 **Admin Support:** [Click Here to Message]({SUPPORT_URL})"
        )
        keyboard = [
            [InlineKeyboardButton("📢 Main Channel", url=MAIN_CHANNEL_URL), InlineKeyboardButton("📢 Update Channel", url=UPDATE_CHANNEL_URL)],
            [InlineKeyboardButton("💬 OTP Group", url=OTP_GROUP_URL)]
        ]
        await update.message.reply_text(support_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)
        
    elif text == "👑 ADMIN PANEL" and await is_admin(user_id):
        text_msg, markup = await get_admin_panel_markup(user_id)
        await update.message.reply_text(text_msg, parse_mode="Markdown", reply_markup=markup)
        
    else:
        if await is_admin(user_id) and text == "":
            pass
        elif not update.message.document and not any(user_id in d for d in [ADMIN_UPLOAD_STATE, USER_SEARCH_STATE, ADMIN_SETTINGS_STATE, USER_WITHDRAW_STATE, ADMIN_BROADCAST_STATE, ADMIN_ADD_STATE, CHANNEL_ADD_STATE, FORWARD_GROUP_ADD_STATE, USER_MANAGE_STATE, RANAX_ADD_STATE, MENU_EDIT_STATE, TEST_FLOW_STATE]):
            reply_markup = await build_main_menu(user_id)
            await update.message.reply_text("দয়া করে নিচের বাটনগুলো ব্যবহার করুন অথবা /start দিন।", reply_markup=reply_markup)

async def broadcast_new_numbers_alert(context: ContextTypes.DEFAULT_TYPE, service_name: str, count: int):
    alert_text = (
        f"🚨 **New Numbers Added!** 🚨\n\n"
        f"📱 **Service:** `{service_name}`\n"
        f"📦 **Quantity:** `{count} Pcs` Added Successfully!\n\n"
        f"⚡ দ্রুত **GET NUMBER** এ গিয়ে নাম্বার নিয়ে নিন!"
    )
    all_users = users_col.find({})
    async for u in all_users:
        try:
            await context.bot.send_message(
                chat_id=u["user_id"],
                text=alert_text,
                parse_mode="Markdown"
            )
        except Exception:
            pass

async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    await application.bot.set_my_commands([BotCommand("start", "Start the bot")])

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, message_handler))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, otp_group_listener))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.SUPERGROUP, otp_group_listener))

    print("Zentrix Bot with RanaX Auto-Forwarder and Menu Customizer is running successfully...")
    
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


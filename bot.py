import os
import logging
import asyncio
import re
from urllib.parse import quote, unquote
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import motor.motor_asyncio

# Optional country detection. If unavailable, a calling-code fallback is used.
try:
    import phonenumbers
    from phonenumbers import geocoder
except ImportError:
    phonenumbers = None
    geocoder = None

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
ranax_groups_col = db.ranax_groups  # RanaX à¦¸à§‹à¦°à§à¦¸ à¦—à§à¦°à§à¦ªà¦—à§à¦²à§‹ à¦¸à¦‚à¦°à¦•à§à¦·à¦£à§‡à¦° à¦œà¦¨à§à¦¯ à¦•à¦¾à¦²à§‡à¦•à¦¶à¦¨
provider_panels_col = db.provider_panels  # Safe provider/panel configuration + inventory metadata

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
PANEL_STATE = {}
MENU_EDIT_STATE = {}  # à¦®à§‡à¦¨à§ à¦Ÿà§‡à¦•à§à¦¸à¦Ÿ à¦¬à¦¾ à¦¬à¦¾à¦Ÿà¦¨ à¦•à¦¾à¦¸à§à¦Ÿà¦®à¦¾à¦‡à¦œà§‡à¦¶à¦¨à§‡à¦° à¦œà¦¨à§à¦¯ à¦¸à§à¦Ÿà§‡à¦Ÿ
TEST_STATE = {}  # Admin-only OTP Group Test wizard

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
    # à¦¡à¦¾à§Ÿà¦¨à¦¾à¦®à¦¿à¦• à¦¨à¦¾à¦®à¦—à§à¦²à§‹ à¦¡à¦¾à¦Ÿà¦¾à¦¬à§‡à¦œ à¦¥à§‡à¦•à§‡ à¦²à§‹à¦¡ à¦•à¦°à¦¾ à¦¹à¦šà§à¦›à§‡, à¦¨à¦¾ à¦¥à¦¾à¦•à¦²à§‡ à¦¡à¦¿à¦«à¦²à§à¦Ÿ à¦¨à¦¾à¦® à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦¹à¦¬à§‡
    btn_get_num = await get_setting("btn_get_number", "ðŸ“± GET NUMBER")
    btn_search_num = await get_setting("btn_search_number", "ðŸ”Ž SEARCH NUMBER")
    btn_traffic = await get_setting("btn_traffic", "ðŸš¦ TRAFFIC")
    btn_refer = await get_setting("btn_refer", "ðŸ‘¥ REFERRAL")
    btn_balance = await get_setting("btn_balance", "ðŸ’° BALANCE")
    btn_support = await get_setting("btn_support", "ðŸ†˜ SUPPORT")

    keyboard = [
        [KeyboardButton(btn_get_num), KeyboardButton(btn_search_num)],
        [KeyboardButton(btn_traffic), KeyboardButton(btn_refer)],
        [KeyboardButton(btn_balance), KeyboardButton(btn_support)]
    ]
    return keyboard

async def build_main_menu(user_id: int):
    kb = await main_menu_keyboard(user_id)
    if await is_admin(user_id):
        kb.append([KeyboardButton("ðŸ‘‘ ADMIN PANEL")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def back_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("ðŸ”™ Back")]], resize_keyboard=True)

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
        f"ðŸ‘‘ **Admin Control Panel**\n\n"
        f"ðŸ“Š **Database Overview:**\n"
        f"ðŸ‘¥ Total Users: `{total_users}`\n"
        f"ðŸ“‚ Total Files/Batches: `{total_files}`\n"
        f"ðŸ“± Total Numbers: `{total_numbers}`\n"
        f"ðŸŸ¢ Available: `{available_numbers}` | ðŸ”„ Assigned: `{assigned_numbers}`\n"
        f"ðŸ”´ Used Numbers: `{used_numbers}`\n\n"
        f"à¦¨à¦¿à¦šà§‡à¦° à¦…à¦ªà¦¶à¦¨à¦—à§à¦²à§‹ à¦¥à§‡à¦•à§‡ à¦¸à¦¿à¦²à§‡à¦•à§à¦Ÿ à¦•à¦°à§à¦¨:"
    )

    keyboard = [
        [InlineKeyboardButton("ðŸ† Leaderboard", callback_data="adm_leaderboard"), InlineKeyboardButton("âš™ï¸ System Hub", callback_data="adm_system_menu")],
        [InlineKeyboardButton("ðŸ“¤ Upload", callback_data="adm_upload"), InlineKeyboardButton("ðŸ—‘ï¸ Delete", callback_data="adm_delete")],
        [InlineKeyboardButton("ðŸ“¢ Broadcast", callback_data="adm_broadcast"), InlineKeyboardButton("âŒ Close", callback_data="adm_close")]
    ]
    return panel_text, InlineKeyboardMarkup(keyboard)


# --- Safe Multi-Provider Panel Manager ---
# This layer manages provider credentials and catalog metadata only.
# It intentionally does NOT fetch/relay OTPs or intercept third-party verification codes.
PANEL_NAMES = ["StexSMS", "Voltx", "Zenex", "YE SMS"]
PANEL_CODES = {"StexSMS": "S", "Voltx": "V", "Zenex": "Z", "YE SMS": "Y"}

def panel_cb_value(value: str) -> str:
    return quote(str(value), safe="")

def panel_cb_decode(value: str) -> str:
    return unquote(value)

async def get_panel_doc(panel_name: str):
    return await provider_panels_col.find_one({"_id": panel_name})

async def panel_menu_markup(panel_name: str):
    code = PANEL_CODES[panel_name]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"âž• Add {panel_name} Key", callback_data=f"p_addkey:{panel_cb_value(panel_name)}"),
         InlineKeyboardButton("ðŸ—ï¸ View/Del Keys", callback_data=f"p_keys:{panel_cb_value(panel_name)}")],
        [InlineKeyboardButton(f"ðŸ§© Manage {panel_name} Services", callback_data=f"p_services:{panel_cb_value(panel_name)}")],
        [InlineKeyboardButton("ðŸŒ Search Country", callback_data=f"p_search_country:{panel_cb_value(panel_name)}")],
        [InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")]
    ])

async def render_panel_menu(query, panel_name: str):
    doc = await get_panel_doc(panel_name)
    keys = doc.get("api_keys", []) if doc else []
    services = doc.get("services", []) if doc else []
    key_count = len(keys)
    service_count = len(services)
    code = PANEL_CODES[panel_name]
    text = (
        f"âš¡ **{panel_name} Control Panel**\n\n"
        f"ðŸ”¤ Panel Code: `{code}`\n"
        f"ðŸ”‘ API Keys: `{key_count}`\n"
        f"ðŸ§© Services: `{service_count}`\n\n"
        f"à¦¨à¦¿à¦šà§‡à¦° à¦…à¦ªà¦¶à¦¨ à¦¥à§‡à¦•à§‡ {panel_name} à¦•à¦¨à¦«à¦¿à¦—à¦¾à¦° à¦•à¦°à§à¦¨:"
    )
    await query.message.edit_text(text, parse_mode="Markdown", reply_markup=await panel_menu_markup(panel_name))

async def render_panel_services(query, panel_name: str):
    doc = await get_panel_doc(panel_name)
    services = doc.get("services", []) if doc else []
    keyboard = []
    for service in services:
        name = service.get("name", "Unnamed")
        keyboard.append([InlineKeyboardButton(
            f"ðŸ“¦ {name}",
            callback_data=f"p_service:{panel_cb_value(panel_name)}:{panel_cb_value(name)}"
        )])
    keyboard.append([InlineKeyboardButton("âž• Add New Service", callback_data=f"p_addservice:{panel_cb_value(panel_name)}")])
    keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data=f"p_panel:{panel_cb_value(panel_name)}")])
    text = (
        f"ðŸ§© **{panel_name} Services Manager**\n\n"
        "Manage your API-backed service catalog below:\n"
    )
    if not services:
        text += "\nâš ï¸ à¦•à§‹à¦¨à§‹ service à¦à¦–à¦¨à§‹ à¦¯à§‹à¦— à¦•à¦°à¦¾ à¦¹à§Ÿà¦¨à¦¿à¥¤"
    await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def render_panel_service(query, panel_name: str, service_name: str):
    doc = await get_panel_doc(panel_name)
    services = doc.get("services", []) if doc else []
    service = next((s for s in services if s.get("name") == service_name), None)
    countries = service.get("countries", []) if service else []
    keyboard = []
    for country in countries:
        cname = country.get("name", "Unknown")
        ranges = country.get("ranges", [])
        keyboard.append([InlineKeyboardButton(
            f"ðŸŒ {cname} ({len(ranges)} ranges)",
            callback_data=f"p_country:{panel_cb_value(panel_name)}:{panel_cb_value(service_name)}:{panel_cb_value(cname)}"
        )])
    keyboard.append([InlineKeyboardButton("âž• Add Country", callback_data=f"p_addcountry:{panel_cb_value(panel_name)}:{panel_cb_value(service_name)}")])
    keyboard.append([InlineKeyboardButton("ðŸ—‘ï¸ Delete Service", callback_data=f"p_delservice:{panel_cb_value(panel_name)}:{panel_cb_value(service_name)}")])
    keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data=f"p_services:{panel_cb_value(panel_name)}")])
    text = (
        f"ðŸ“¦ **Service: {service_name}**\n\n"
        f"Manage countries for this service:"
    )
    if not countries:
        text += "\n\nâš ï¸ à¦•à§‹à¦¨à§‹ country à¦à¦–à¦¨à§‹ à¦¯à§‹à¦— à¦•à¦°à¦¾ à¦¹à§Ÿà¦¨à¦¿à¥¤"
    await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def render_panel_country(query, panel_name: str, service_name: str, country_name: str):
    doc = await get_panel_doc(panel_name)
    services = doc.get("services", []) if doc else []
    service = next((s for s in services if s.get("name") == service_name), None)
    countries = service.get("countries", []) if service else []
    country = next((c for c in countries if c.get("name") == country_name), None)
    ranges = country.get("ranges", []) if country else []
    range_lines = "\n".join([f"â€¢ `{r}`" for r in ranges]) if ranges else "âš ï¸ à¦•à§‹à¦¨à§‹ range à¦¯à§‹à¦— à¦•à¦°à¦¾ à¦¹à§Ÿà¦¨à¦¿à¥¤"
    keyboard = [
        [InlineKeyboardButton("âž• Add Range", callback_data=f"p_addrange:{panel_cb_value(panel_name)}:{panel_cb_value(service_name)}:{panel_cb_value(country_name)}")],
        [InlineKeyboardButton("ðŸ—‘ï¸ Delete Entire Country", callback_data=f"p_delcountry:{panel_cb_value(panel_name)}:{panel_cb_value(service_name)}:{panel_cb_value(country_name)}")],
        [InlineKeyboardButton("ðŸ”™ Back", callback_data=f"p_service:{panel_cb_value(panel_name)}:{panel_cb_value(service_name)}")]
    ]
    text = (
        f"ðŸŒ **Country: {country_name}**\n\n"
        f"ðŸ“Œ Configured Ranges:\n{range_lines}\n\n"
        "â„¹ï¸ Range metadata is stored for provider integration/inventory routing."
    )
    await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def render_panel_search_country(query, panel_name: str, term: str):
    doc = await get_panel_doc(panel_name)
    services = doc.get("services", []) if doc else []
    matches = []
    for service in services:
        for country in service.get("countries", []):
            if term.lower() in country.get("name", "").lower():
                matches.append((service.get("name", "Unnamed"), country.get("name", "Unknown"), len(country.get("ranges", []))))
    keyboard = []
    for service_name, country_name, count in matches:
        keyboard.append([InlineKeyboardButton(
            f"ðŸŒ {country_name} â€¢ {service_name} ({count})",
            callback_data=f"p_country:{panel_cb_value(panel_name)}:{panel_cb_value(service_name)}:{panel_cb_value(country_name)}"
        )])
    keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data=f"p_panel:{panel_cb_value(panel_name)}")])
    text = f"ðŸ”Ž **Search Country â€” {panel_name}**\n\n"
    text += "à¦•à§‹à¦¨à§‹ country à¦ªà¦¾à¦“à§Ÿà¦¾ à¦¯à¦¾à§Ÿà¦¨à¦¿à¥¤" if not matches else "à¦¨à¦¿à¦šà§‡ matching country à¦—à§à¦²à§‹:"
    await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def provider_inventory_services(panel_name: str):
    # Only numbers explicitly tagged with provider are exposed through provider menus.
    return await numbers_col.distinct(
        "service_name",
        {"provider": panel_name, "status": "Available"}
    )

async def provider_inventory_countries(panel_name: str, service_name: str):
    return await numbers_col.distinct(
        "country",
        {"provider": panel_name, "service_name": service_name, "status": "Available"}
    )

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    for state_dict in [ADMIN_UPLOAD_STATE, USER_SEARCH_STATE, ADMIN_SETTINGS_STATE, USER_WITHDRAW_STATE, ADMIN_BROADCAST_STATE, ADMIN_ADD_STATE, CHANNEL_ADD_STATE, FORWARD_GROUP_ADD_STATE, USER_MANAGE_STATE, RANAX_ADD_STATE, MENU_EDIT_STATE, TEST_STATE, PANEL_STATE]:
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
                    text=f"ðŸŽ‰ **New Referral!**\n\nà¦†à¦ªà¦¨à¦¾à¦° à¦²à¦¿à¦‚à¦•à§‡à¦° à¦®à¦¾à¦§à§à¦¯à¦®à§‡ à¦à¦•à¦œà¦¨ à¦¨à¦¤à§à¦¨ à¦‡à¦‰à¦œà¦¾à¦° à¦œà§Ÿà§‡à¦¨ à¦•à¦°à§‡à¦›à§‡ à¦à¦¬à¦‚ à¦†à¦ªà¦¨à¦¿ à¦¬à§‹à¦¨à¦¾à¦¸ à¦ªà§‡à§Ÿà§‡à¦›à§‡à¦¨: `+{ref_bonus}à§³`",
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
        await update.message.reply_text("âŒ à¦†à¦ªà¦¨à¦¿ à¦à¦‡ à¦¬à¦Ÿ à¦¥à§‡à¦•à§‡ à¦¬à§à¦¯à¦¾à¦¨ à¦¹à§Ÿà§‡à¦›à§‡à¦¨ã€‚", parse_mode="Markdown")
        return

    is_joined = await check_force_join(user.id, context)
    if not is_joined:
        channels_list = await channels_col.find({}).to_list(length=50)
        inline_kb = []
        if channels_list:
            for ch in channels_list:
                inline_kb.append([InlineKeyboardButton(f"ðŸ“¢ Join {ch.get('name')}", url=ch.get('url'))])
        else:
            inline_kb.append([InlineKeyboardButton("ðŸ“¢ Join Main Channel", url=MAIN_CHANNEL_URL)])
            inline_kb.append([InlineKeyboardButton("ðŸ“¢ Join Update Channel", url=UPDATE_CHANNEL_URL)])
            
        inline_kb.append([InlineKeyboardButton("ðŸ’¬ Join OTP Group", url=OTP_GROUP_URL)])
        inline_kb.append([InlineKeyboardButton("âœ… Joined / Check", callback_data="check_join")])

        await update.message.reply_text(
            "âš ï¸ **à¦¬à¦Ÿà¦Ÿà¦¿ à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦•à¦°à¦¤à§‡ à¦¹à¦²à§‡ à¦…à¦¬à¦¶à§à¦¯à¦‡ à¦†à¦®à¦¾à¦¦à§‡à¦° à¦šà§à¦¯à¦¾à¦¨à§‡à¦² à¦à¦¬à¦‚ à¦—à§à¦°à§à¦ªà¦—à§à¦²à§‹à¦¤à§‡ à¦œà§Ÿà§‡à¦¨ à¦¥à¦¾à¦•à¦¤à§‡ à¦¹à¦¬à§‡!**\n\n"
            "à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦¨à¦¿à¦šà§‡à¦° à¦²à¦¿à¦‚à¦•à¦—à§à¦²à§‹à¦¤à§‡ à¦œà§Ÿà§‡à¦¨ à¦•à¦°à§à¦¨ à¦à¦¬à¦‚ à¦¤à¦¾à¦°à¦ªà¦° à¦šà§‡à¦• à¦•à¦°à§à¦¨à¥¤",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_kb)
        )
        return

    custom_welcome = await get_setting("start_menu_text", None)
    if not custom_welcome:
        welcome_text = (
            f"ðŸŒ **NUMBER PANEL**\n\n"
            f"ðŸ‘‹ Welcome, **{user.first_name}**\n"
            f"ðŸš€ Premium Number Management System\n\n"
            f"ðŸ“± Manage your available numbers\n"
            f"ðŸŒ Browse services & countries\n"
            f"ðŸ’° Balance & referral management\n\n"
            f"âš¡ Fast â€¢ Simple â€¢ Secure"
        )
    else:
        welcome_text = custom_welcome.format(first_name=user.first_name, username=user.username or "N/A", user_id=user.id)

    reply_markup = await build_main_menu(user.id)
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)


# --- Admin OTP Group Test Helpers ---
FALLBACK_COUNTRY_CODES = {
    "880": "BD", "60": "MY", "62": "ID", "65": "SG", "66": "TH",
    "84": "VN", "63": "PH", "91": "IN", "92": "PK", "93": "AF",
    "94": "LK", "95": "MM", "98": "IR", "81": "JP", "82": "KR",
    "86": "CN", "7": "RU", "90": "TR", "1": "US/CA", "44": "GB",
    "33": "FR", "49": "DE", "39": "IT", "34": "ES", "31": "NL",
    "32": "BE", "41": "CH", "43": "AT", "45": "DK", "46": "SE",
    "47": "NO", "48": "PL", "30": "GR", "351": "PT", "353": "IE",
    "358": "FI", "380": "UA", "420": "CZ", "36": "HU", "40": "RO",
    "972": "IL", "971": "AE", "966": "SA", "974": "QA", "973": "BH",
    "965": "KW", "968": "OM", "967": "YE", "962": "JO", "961": "LB",
    "963": "SY", "964": "IQ", "20": "EG", "212": "MA", "213": "DZ",
    "216": "TN", "218": "LY", "234": "NG", "254": "KE", "255": "TZ",
    "256": "UG", "27": "ZA", "61": "AU", "64": "NZ",
}

def detect_test_country(phone: str) -> str:
    raw = re.sub(r"[^\d+]", "", phone.strip())
    if not raw.startswith("+"):
        raw = "+" + raw

    if phonenumbers is not None:
        try:
            parsed = phonenumbers.parse(raw, None)
            region = geocoder.region_code_for_number(parsed)
            if region:
                return region.upper()
        except Exception:
            pass

    digits = raw.lstrip("+")
    for length in (3, 2, 1):
        prefix = digits[:length]
        if prefix in FALLBACK_COUNTRY_CODES:
            return FALLBACK_COUNTRY_CODES[prefix]
    return "UN"

def country_flag(country: str) -> str:
    country = (country or "UN").upper()
    if len(country) != 2 or not country.isalpha():
        return "ðŸŒ"
    return "".join(chr(127397 + ord(c)) for c in country)

def service_icon(service: str) -> str:
    s = service.lower().replace("'", "").replace(" ", "")
    icons = {
        "whatsapp": "ðŸŸ¢", "facebook": "ðŸ”µ", "telegram": "ðŸ”·",
        "instagram": "ðŸŸ£", "discord": "ðŸŸª", "imo": "ðŸ”µ",
        "google": "ðŸ”´", "tiktok": "âš«", "twitter": "ðŸ¦",
    }
    return icons.get(s, "ðŸ“±")

def mask_test_phone(phone: str) -> str:
    # Keep the same compact visual style as the reference OTP group.
    if len(phone) <= 8:
        return phone
    return f"{phone[:5]}â€¢â€¢{phone[-4:]}"

async def build_test_otp_keyboard(context: ContextTypes.DEFAULT_TYPE, otp: str):
    # Channel URL can be changed from OTP Group Management; fallback is the main channel.
    channel_url = await get_setting("otp_button_link", MAIN_CHANNEL_URL)
    if not isinstance(channel_url, str) or not channel_url.startswith(("http://", "https://", "tg://")):
        channel_url = MAIN_CHANNEL_URL

    me = await context.bot.get_me()
    bot_username = me.username or ""
    get_number_url = f"https://t.me/{bot_username}?start=get_number" if bot_username else MAIN_CHANNEL_URL

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("ðŸ”” Channel", url=channel_url),
            InlineKeyboardButton(f"ðŸ›¡ï¸ ðŸ“‹ {otp}", copy_text=CopyTextButton(text=otp)),
        ],
        [InlineKeyboardButton("ðŸ“ž Get Number â†—", url=get_number_url)]
    ])

def build_test_otp_text(service: str, phone: str, otp: str, language: str, country: str) -> str:
    # Keep the visual layout close to the normal OTP feed, but retain a clear
    # synthetic-test marker so a test OTP is not mistaken for a real OTP.
    return (
        f"ðŸ§ª **TEST**  {country_flag(country)} **{country}** | "
        f"{service_icon(service)} **{service}** `{mask_test_phone(phone)}` | "
        f"ðŸ”Š **{language}**\n\n"
        f"ðŸ›¡ï¸ **OTP:** `{otp}`"
    )

async def send_test_otp_to_configured_groups(context: ContextTypes.DEFAULT_TYPE,
                                             service: str, phone: str,
                                             otp: str, language: str,
                                             country: str):
    groups = await forward_groups_col.find({}).to_list(length=50)
    target_ids = [str(g.get("group_id")).strip() for g in groups if g.get("group_id")]
    if not target_ids:
        target_ids = [OTP_GROUP_URL]

    payload = build_test_otp_text(service, phone, otp, language, country)
    reply_markup = await build_test_otp_keyboard(context, otp)
    success = 0
    failed = 0

    for target_id in target_ids:
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=payload,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            success += 1
        except Exception:
            failed += 1

    return success, failed, len(target_ids)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == "check_join":
        is_joined = await check_force_join(user_id, context)
        if is_joined:
            await query.answer("âœ… à¦§à¦¨à§à¦¯à¦¬à¦¾à¦¦! à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦­à§‡à¦°à¦¿à¦«à¦¾à¦‡ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡à¥¤", show_alert=False)
            try:
                await query.message.delete()
            except Exception:
                pass
                
            user = query.from_user
            custom_welcome = await get_setting("start_menu_text", None)
            if not custom_welcome:
                welcome_text = (
                    f"ðŸŒ **NUMBER PANEL**\n\n"
                    f"ðŸ‘‹ Welcome, **{user.first_name}**\n"
                    f"ðŸš€ Premium Number Management System\n\n"
                    f"âš¡ Fast â€¢ Simple â€¢ Secure"
                )
            else:
                welcome_text = custom_welcome.format(first_name=user.first_name, username=user.username or "N/A", user_id=user.id)

            reply_markup = await build_main_menu(user_id)
            await context.bot.send_message(chat_id=user_id, text=welcome_text, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await query.answer("âŒ à¦†à¦ªà¦¨à¦¿ à¦à¦–à¦¨à§‹ à¦¸à¦¬à¦•à¦Ÿà¦¿ à¦šà§à¦¯à¦¾à¦¨à§‡à¦² à¦¬à¦¾ à¦—à§à¦°à§à¦ªà§‡ à¦œà§Ÿà§‡à¦¨ à¦•à¦°à§‡à¦¨à¦¨à¦¿! à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦†à¦—à§‡ à¦œà§Ÿà§‡à¦¨ à¦•à¦°à§à¦¨.", show_alert=True)

    # --- System Control Hub Menu ---
    elif query.data == "adm_system_menu" and await is_admin(user_id):
        await query.answer()
        sys_text = "âš™ï¸ **System Control Hub**\n\nà¦¨à¦¿à¦šà§‡à¦° à¦…à¦ªà¦¶à¦¨à¦—à§à¦²à§‹ à¦¥à§‡à¦•à§‡ à¦®à§à¦¯à¦¾à¦¨à§‡à¦œ à¦•à¦°à§à¦¨:"
        sys_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("StexSMS", callback_data="stex_control"), InlineKeyboardButton("Voltx", callback_data="voltx_control")],
            [InlineKeyboardButton("Zenex", callback_data="zenex_control"), InlineKeyboardButton("YE SMS", callback_data="ye_control")],
            [InlineKeyboardButton("RanaX", callback_data="ranax_control"), InlineKeyboardButton("Emoji", callback_data="premium_emoji")],
            [InlineKeyboardButton("Menu Design", callback_data="menu_design"), InlineKeyboardButton("Test", callback_data="test")],
            [InlineKeyboardButton("ðŸ‘‘ Admin Mgmt", callback_data="adm_mgmt_menu"), InlineKeyboardButton("âš™ï¸ Force Join", callback_data="adm_fj_menu")],
            [InlineKeyboardButton("ðŸ‘¥ User Mgmt", callback_data="adm_usermgmt_menu"), InlineKeyboardButton("ðŸ’¬ OTP Groups", callback_data="adm_otpgroup_menu")],
            [InlineKeyboardButton("ðŸš€ X-Rony Panel", callback_data="adm_xrony_menu")],
            [InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_back")]
        ])
        await query.message.edit_text(sys_text, parse_mode="Markdown", reply_markup=sys_keyboard)


    # --- Safe Multi-Provider Panel Manager ---
    elif query.data in {"stex_control", "voltx_control", "zenex_control", "ye_control"} and await is_admin(user_id):
        await query.answer()
        panel_name = {
            "stex_control": "StexSMS",
            "voltx_control": "Voltx",
            "zenex_control": "Zenex",
            "ye_control": "YE SMS"
        }[query.data]
        await render_panel_menu(query, panel_name)

    elif query.data.startswith("p_panel:") and await is_admin(user_id):
        await query.answer()
        panel_name = panel_cb_decode(query.data.split(":", 1)[1])
        if panel_name not in PANEL_NAMES:
            await query.message.edit_text("âŒ Invalid panel.")
            return
        await render_panel_menu(query, panel_name)

    elif query.data.startswith("p_addkey:") and await is_admin(user_id):
        await query.answer()
        panel_name = panel_cb_decode(query.data.split(":", 1)[1])
        PANEL_STATE[user_id] = {"step": "API_KEY", "panel": panel_name}
        await query.message.edit_text(
            f"ðŸ” **{panel_name} API Key**\n\n"
            "API key à¦ªà¦¾à¦ à¦¾à¦¨à¥¤ à¦‰à¦¦à¦¾à¦¹à¦°à¦£: `MIUOAJ8WTEJ` à¦¬à¦¾ `MURAD_43122558F7FE7B6C79B419C2`\n\n"
            "âš ï¸ Key à¦¶à§à¦§à§à¦®à¦¾à¦¤à§à¦° admin configuration à¦¹à¦¿à¦¸à§‡à¦¬à§‡ à¦¸à¦‚à¦°à¦•à§à¦·à¦£ à¦•à¦°à¦¾ à¦¹à¦¬à§‡à¥¤",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data=f"p_panel:{panel_cb_value(panel_name)}")]])
        )

    elif query.data.startswith("p_keys:") and await is_admin(user_id):
        await query.answer()
        panel_name = panel_cb_decode(query.data.split(":", 1)[1])
        doc = await get_panel_doc(panel_name)
        keys = doc.get("api_keys", []) if doc else []
        keyboard = []
        for idx, key in enumerate(keys):
            masked = key[:4] + "â€¦" + key[-4:] if len(key) > 10 else "â€¢â€¢â€¢â€¢â€¢â€¢"
            keyboard.append([InlineKeyboardButton(
                f"ðŸ”‘ {masked}  #{idx+1}",
                callback_data=f"p_delkey:{panel_cb_value(panel_name)}:{idx}"
            )])
        keyboard.append([InlineKeyboardButton("âž• Add Key", callback_data=f"p_addkey:{panel_cb_value(panel_name)}")])
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data=f"p_panel:{panel_cb_value(panel_name)}")])
        text = f"ðŸ—ï¸ **{panel_name} API Keys**\n\n"
        text += "à¦•à§‹à¦¨à§‹ key à¦¨à§‡à¦‡à¥¤" if not keys else "à¦à¦•à¦Ÿà¦¿ key-à¦¤à§‡ à¦•à§à¦²à¦¿à¦• à¦•à¦°à¦²à§‡ à¦¸à§‡à¦Ÿà¦¿ delete à¦¹à¦¬à§‡à¥¤"
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("p_delkey:") and await is_admin(user_id):
        await query.answer()
        _, panel_enc, idx_s = query.data.split(":", 2)
        panel_name = panel_cb_decode(panel_enc)
        idx = int(idx_s)
        doc = await get_panel_doc(panel_name)
        keys = doc.get("api_keys", []) if doc else []
        if 0 <= idx < len(keys):
            keys.pop(idx)
            await provider_panels_col.update_one({"_id": panel_name}, {"$set": {"api_keys": keys}}, upsert=True)
        await query.answer("âœ… API key deleted.", show_alert=True)
        # Render keys again.
        doc = await get_panel_doc(panel_name)
        keys = doc.get("api_keys", []) if doc else []
        keyboard = []
        for i, key in enumerate(keys):
            masked = key[:4] + "â€¦" + key[-4:] if len(key) > 10 else "â€¢â€¢â€¢â€¢â€¢â€¢"
            keyboard.append([InlineKeyboardButton(f"ðŸ”‘ {masked} #{i+1}", callback_data=f"p_delkey:{panel_cb_value(panel_name)}:{i}")])
        keyboard.append([InlineKeyboardButton("âž• Add Key", callback_data=f"p_addkey:{panel_cb_value(panel_name)}")])
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data=f"p_panel:{panel_cb_value(panel_name)}")])
        await query.message.edit_text(
            f"ðŸ—ï¸ **{panel_name} API Keys**\n\n" + ("à¦•à§‹à¦¨à§‹ key à¦¨à§‡à¦‡à¥¤" if not keys else "à¦à¦•à¦Ÿà¦¿ key-à¦¤à§‡ à¦•à§à¦²à¦¿à¦• à¦•à¦°à¦²à§‡ à¦¸à§‡à¦Ÿà¦¿ delete à¦¹à¦¬à§‡."),
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("p_services:") and await is_admin(user_id):
        await query.answer()
        panel_name = panel_cb_decode(query.data.split(":", 1)[1])
        await render_panel_services(query, panel_name)

    elif query.data.startswith("p_addservice:") and await is_admin(user_id):
        await query.answer()
        panel_name = panel_cb_decode(query.data.split(":", 1)[1])
        PANEL_STATE[user_id] = {"step": "SERVICE_NAME", "panel": panel_name}
        await query.message.edit_text(
            f"ðŸ“¦ **{panel_name} â€” Add New Service**\n\n"
            "Service name à¦²à¦¿à¦–à§à¦¨à¥¤ à¦¯à§‡à¦®à¦¨: Facebook, Telegram, WhatsApp, imo",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data=f"p_services:{panel_cb_value(panel_name)}")]])
        )

    elif query.data.startswith("p_service:") and await is_admin(user_id):
        await query.answer()
        _, panel_enc, service_enc = query.data.split(":", 2)
        await render_panel_service(query, panel_cb_decode(panel_enc), panel_cb_decode(service_enc))

    elif query.data.startswith("p_delservice:") and await is_admin(user_id):
        await query.answer()
        _, panel_enc, service_enc = query.data.split(":", 2)
        panel_name = panel_cb_decode(panel_enc)
        service_name = panel_cb_decode(service_enc)
        await provider_panels_col.update_one(
            {"_id": panel_name},
            {"$pull": {"services": {"name": service_name}}}
        )
        await query.answer("âœ… Service deleted.", show_alert=True)
        await render_panel_services(query, panel_name)

    elif query.data.startswith("p_addcountry:") and await is_admin(user_id):
        await query.answer()
        _, panel_enc, service_enc = query.data.split(":", 2)
        panel_name = panel_cb_decode(panel_enc)
        service_name = panel_cb_decode(service_enc)
        PANEL_STATE[user_id] = {"step": "COUNTRY_NAME", "panel": panel_name, "service": service_name}
        await query.message.edit_text(
            f"ðŸŒ **{service_name} â€” Add Country**\n\nCountry name à¦²à¦¿à¦–à§à¦¨à¥¤ à¦¯à§‡à¦®à¦¨: Guinea, Bangladesh, Malaysia",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data=f"p_service:{panel_cb_value(panel_name)}:{panel_cb_value(service_name)}")]])
        )

    elif query.data.startswith("p_country:") and await is_admin(user_id):
        await query.answer()
        _, panel_enc, service_enc, country_enc = query.data.split(":", 3)
        await render_panel_country(
            query,
            panel_cb_decode(panel_enc),
            panel_cb_decode(service_enc),
            panel_cb_decode(country_enc)
        )

    elif query.data.startswith("p_delcountry:") and await is_admin(user_id):
        await query.answer()
        _, panel_enc, service_enc, country_enc = query.data.split(":", 3)
        panel_name = panel_cb_decode(panel_enc)
        service_name = panel_cb_decode(service_enc)
        country_name = panel_cb_decode(country_enc)
        await provider_panels_col.update_one(
            {"_id": panel_name, "services.name": service_name},
            {"$pull": {"services.$.countries": {"name": country_name}}}
        )
        await query.answer("âœ… Country deleted.", show_alert=True)
        await render_panel_service(query, panel_name, service_name)

    elif query.data.startswith("p_addrange:") and await is_admin(user_id):
        await query.answer()
        _, panel_enc, service_enc, country_enc = query.data.split(":", 3)
        panel_name = panel_cb_decode(panel_enc)
        service_name = panel_cb_decode(service_enc)
        country_name = panel_cb_decode(country_enc)
        PANEL_STATE[user_id] = {
            "step": "RANGE",
            "panel": panel_name,
            "service": service_name,
            "country": country_name
        }
        await query.message.edit_text(
            f"ðŸ§® **{country_name} â€” Add Range**\n\n"
            "à¦à¦‡ panel-à¦à¦° provider range à¦²à¦¿à¦–à§à¦¨à¥¤ à¦‰à¦¦à¦¾à¦¹à¦°à¦£: `26134`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "ðŸ”™ Back",
                    callback_data=f"p_country:{panel_cb_value(panel_name)}:{panel_cb_value(service_name)}:{panel_cb_value(country_name)}"
                )
            ]])
        )

    elif query.data.startswith("p_search_country:") and await is_admin(user_id):
        await query.answer()
        panel_name = panel_cb_decode(query.data.split(":", 1)[1])
        PANEL_STATE[user_id] = {"step": "SEARCH_COUNTRY", "panel": panel_name}
        await query.message.edit_text(
            f"ðŸ”Ž **Search Country â€” {panel_name}**\n\nCountry name à¦²à¦¿à¦–à§à¦¨:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data=f"p_panel:{panel_cb_value(panel_name)}")]])
        )

    # --- Admin OTP Group Test Wizard ---
    elif query.data == "test" and await is_admin(user_id):
        await query.answer()
        TEST_STATE[user_id] = {"step": "GET_SERVICE"}
        await query.message.edit_text(
            "ðŸ§ª **OTP Group Test**\n\n"
            "à¦ªà§à¦°à¦¥à¦®à§‡ à¦¯à§‡ **Service** à¦Ÿà§‡à¦¸à§à¦Ÿ à¦•à¦°à¦¤à§‡ à¦šà¦¾à¦¨ à¦¤à¦¾à¦° à¦¨à¦¾à¦® à¦²à¦¿à¦–à§à¦¨à¥¤\n"
            "à¦‰à¦¦à¦¾à¦¹à¦°à¦£: `Facebook` / `WhatsApp`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")]
            ])
        )

    # --- Menu Design Control Hub ---
    elif query.data == "menu_design" and await is_admin(user_id):
        await query.answer()
        menu_text = (
            f"ðŸŽ¨ **Menu & Button Customization Hub**\n\n"
            f"à¦¬à¦Ÿà§‡à¦° à¦¸à§à¦Ÿà¦¾à¦°à§à¦Ÿ à¦®à§‡à¦¸à§‡à¦œ à¦à¦¬à¦‚ à¦°à¦¿à¦ªà§à¦²à¦¾à¦‡ à¦¬à¦¾à¦Ÿà¦¨à¦—à§à¦²à§‹à¦° à¦¨à¦¾à¦® à¦à¦–à¦¾à¦¨ à¦¥à§‡à¦•à§‡ à¦†à¦ªà¦¨à¦¾à¦° à¦ªà¦›à¦¨à§à¦¦à¦®à¦¤à§‹ à¦ªà¦°à¦¿à¦¬à¦°à§à¦¤à¦¨ à¦•à¦°à¦¤à§‡ à¦ªà¦¾à¦°à¦¬à§‡à¦¨à¥¤"
        )
        menu_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("âœï¸ Edit Start Menu", callback_data="m_edit_start"), InlineKeyboardButton("âœï¸ Edit GET NUMBER", callback_data="m_edit_get")],
            [InlineKeyboardButton("âœï¸ Edit Search Number", callback_data="m_edit_search"), InlineKeyboardButton("âœï¸ Edit Select Country", callback_data="m_edit_country")],
            [InlineKeyboardButton("âœï¸ Edit TRAFFIC", callback_data="m_edit_traffic"), InlineKeyboardButton("âœï¸ Edit Refer", callback_data="m_edit_refer")],
            [InlineKeyboardButton("âœï¸ Edit WITHDRAWAL", callback_data="m_edit_withdraw"), InlineKeyboardButton("âœï¸ Edit SUPPORT", callback_data="m_edit_support")],
            [InlineKeyboardButton("ðŸ”„ Reset Defaults", callback_data="m_reset_defaults")],
            [InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")]
        ])
        await query.message.edit_text(menu_text, parse_mode="Markdown", reply_markup=menu_keyboard)

    elif query.data.startswith("m_edit_") and await is_admin(user_id):
        await query.answer()
        action = query.data.replace("m_edit_", "")
        MENU_EDIT_STATE[user_id] = {"action": action}
        
        prompts = {
            "start": "âœï¸ à¦¨à¦¤à§à¦¨ à¦¸à§à¦Ÿà¦¾à¦°à§à¦Ÿ à¦®à§‡à¦¨à§ à¦Ÿà§‡à¦•à§à¦¸à¦Ÿ à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨ (Variables à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦•à¦°à¦¤à§‡ à¦ªà¦¾à¦°à§‡à¦¨ à¦¯à§‡à¦®à¦¨: `{first_name}`):",
            "get": "âœï¸ 'GET NUMBER' à¦¬à¦¾à¦Ÿà¦¨à¦Ÿà¦¿à¦° à¦œà¦¨à§à¦¯ à¦¨à¦¤à§à¦¨ à¦¨à¦¾à¦® à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:",
            "search": "âœï¸ 'SEARCH NUMBER' à¦¬à¦¾à¦Ÿà¦¨à¦Ÿà¦¿à¦° à¦œà¦¨à§à¦¯ à¦¨à¦¤à§à¦¨ à¦¨à¦¾à¦® à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:",
            "country": "âœï¸ à¦¸à¦¿à¦²à§‡à¦•à§à¦Ÿ à¦•à¦¾à¦¨à§à¦Ÿà§à¦°à¦¿ à¦¸à¦‚à¦•à§à¦°à¦¾à¦¨à§à¦¤ à¦®à§‡à¦¸à§‡à¦œ à¦¬à¦¾ à¦²à§‡à¦¬à§‡à¦² à¦ªà¦°à¦¿à¦¬à¦°à§à¦¤à¦¨à§‡à¦° à¦œà¦¨à§à¦¯ à¦¨à¦¤à§à¦¨ à¦Ÿà§‡à¦•à§à¦¸à¦Ÿ à¦ªà¦¾à¦ à¦¾à¦¨:",
            "traffic": "âœï¸ 'TRAFFIC' à¦¬à¦¾à¦Ÿà¦¨à¦Ÿà¦¿à¦° à¦œà¦¨à§à¦¯ à¦¨à¦¤à§à¦¨ à¦¨à¦¾à¦® à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:",
            "refer": "âœï¸ 'REFERRAL' à¦¬à¦¾à¦Ÿà¦¨à¦Ÿà¦¿à¦° à¦œà¦¨à§à¦¯ à¦¨à¦¤à§à¦¨ à¦¨à¦¾à¦® à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:",
            "withdraw": "âœï¸ à¦‰à¦‡à¦¥à¦¡à§à¦°à§Ÿà¦¾à¦² à¦¸à§‡à¦•à¦¶à¦¨à§‡à¦° à¦¹à§‡à¦¡à¦¾à¦° à¦¬à¦¾ à¦¬à¦¾à¦Ÿà¦¨ à¦¨à¦¾à¦® à¦ªà¦°à¦¿à¦¬à¦°à§à¦¤à¦¨ à¦•à¦°à¦¤à§‡ à¦¨à¦¤à§à¦¨ à¦Ÿà§‡à¦•à§à¦¸à¦Ÿ à¦ªà¦¾à¦ à¦¾à¦¨:",
            "support": "âœï¸ 'SUPPORT' à¦¬à¦¾à¦Ÿà¦¨à¦Ÿà¦¿à¦° à¦œà¦¨à§à¦¯ à¦¨à¦¤à§à¦¨ à¦¨à¦¾à¦® à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:"
        }
        await query.message.edit_text(
            prompts.get(action, "âœï¸ à¦¨à¦¤à§à¦¨ à¦¨à¦¾à¦® à¦¬à¦¾ à¦Ÿà§‡à¦•à§à¦¸à¦Ÿ à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:"),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="menu_design")]])
        )

    elif query.data == "m_reset_defaults" and await is_admin(user_id):
        await settings_col.delete_many({"_id": {"$in": [
            "start_menu_text", "btn_get_number", "btn_search_number", 
            "btn_traffic", "btn_refer", "btn_balance", "btn_support"
        ]}})
        await query.answer("âœ… à¦¸à¦•à¦² à¦®à§‡à¦¨à§ à¦à¦¬à¦‚ à¦¬à¦¾à¦Ÿà¦¨ à¦¡à¦¿à¦«à¦²à§à¦Ÿ à¦¸à§‡à¦Ÿà¦¿à¦‚à§Ÿà§‡ à¦«à¦¿à¦°à¦¿à§Ÿà§‡ à¦†à¦¨à¦¾ à¦¹à§Ÿà§‡à¦›à§‡!", show_alert=True)
        
        # à¦°à¦¿à¦«à§à¦°à§‡à¦¶ à¦®à§‡à¦¨à§ à¦¡à¦¿à¦œà¦¾à¦‡à¦¨ à¦ªà§à¦¯à¦¾à¦¨à§‡à¦²
        menu_text = f"ðŸŽ¨ **Menu & Button Customization Hub**\n\nà¦¬à¦Ÿà§‡à¦° à¦¸à§à¦Ÿà¦¾à¦°à§à¦Ÿ à¦®à§‡à¦¸à§‡à¦œ à¦à¦¬à¦‚ à¦°à¦¿à¦ªà§à¦²à¦¾à¦‡ à¦¬à¦¾à¦Ÿà¦¨à¦—à§à¦²à§‹à¦° à¦¨à¦¾à¦® à¦à¦–à¦¾à¦¨ à¦¥à§‡à¦•à§‡ à¦†à¦ªà¦¨à¦¾à¦° à¦ªà¦›à¦¨à§à¦¦à¦®à¦¤à§‹ à¦ªà¦°à¦¿à¦¬à¦°à§à¦¤à¦¨ à¦•à¦°à¦¤à§‡ à¦ªà¦¾à¦°à¦¬à§‡à¦¨à¥¤"
        menu_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("âœï¸ Edit Start Menu", callback_data="m_edit_start"), InlineKeyboardButton("âœï¸ Edit GET NUMBER", callback_data="m_edit_get")],
            [InlineKeyboardButton("âœï¸ Edit Search Number", callback_data="m_edit_search"), InlineKeyboardButton("âœï¸ Edit Select Country", callback_data="m_edit_country")],
            [InlineKeyboardButton("âœï¸ Edit TRAFFIC", callback_data="m_edit_traffic"), InlineKeyboardButton("âœï¸ Edit Refer", callback_data="m_edit_refer")],
            [InlineKeyboardButton("âœï¸ Edit WITHDRAWAL", callback_data="m_edit_withdraw"), InlineKeyboardButton("âœï¸ Edit SUPPORT", callback_data="m_edit_support")],
            [InlineKeyboardButton("ðŸ”„ Reset Defaults", callback_data="m_reset_defaults")],
            [InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")]
        ])
        await query.message.edit_text(menu_text, parse_mode="Markdown", reply_markup=menu_keyboard)

    # --- RanaX Custom OTP Source & ON/OFF Control Menu ---
    elif query.data == "ranax_control" and await is_admin(user_id):
        await query.answer()
        ranax_status = await get_setting("ranax_status", "ON")
        sources = await ranax_groups_col.find({}).to_list(length=50)

        text = (
            f"ðŸ›¡ï¸ **RanaX Auto-OTP Forwarder Panel**\n\n"
            f"âš¡ System Status: `{ranax_status}`\n"
            f"ðŸ“Œ à¦¸à§‹à¦°à§à¦¸ à¦šà§à¦¯à¦¾à¦Ÿ à¦†à¦‡à¦¡à¦¿ à¦¬à¦¾ à¦—à§à¦°à§à¦ª à¦²à¦¿à¦¸à§à¦Ÿ à¦¨à¦¿à¦šà§‡ à¦¦à§‡à¦“à§Ÿà¦¾ à¦¹à¦²à§‹:"
        )

        keyboard = []
        if sources:
            for s in sources:
                g_id = s.get("chat_id")
                g_name = s.get("name", "Source Group")
                keyboard.append([
                    InlineKeyboardButton(f"ðŸ“ {g_name} (`{g_id}`)", callback_data=f"noop_rx_{g_id}"),
                    InlineKeyboardButton("âŒ à¦¡à¦¿à¦²à¦¿à¦Ÿ", callback_data=f"rx_del:{g_id}")
                ])
        else:
            text += "\n\nâš ï¸ à¦•à§‹à¦¨à§‹ à¦¸à§‹à¦°à§à¦¸ à¦šà§à¦¯à¦¾à¦Ÿ à¦†à¦‡à¦¡à¦¿ à¦¯à§à¦•à§à¦¤ à¦•à¦°à¦¾ à¦¹à§Ÿà¦¨à¦¿à¥¤"

        status_btn_text = "ðŸ”´ Turn OFF" if ranax_status == "ON" else "ðŸŸ¢ Turn ON"
        status_toggle_val = "OFF" if ranax_status == "ON" else "ON"

        keyboard.append([InlineKeyboardButton(status_btn_text, callback_data=f"rx_toggle:{status_toggle_val}")])
        keyboard.append([InlineKeyboardButton("âž• Add Source Chat ID", callback_data="rx_add_start")])
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")])

        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("rx_toggle:") and await is_admin(user_id):
        val = query.data.split(":", 1)[1]
        await set_setting("ranax_status", val)
        await query.answer(f"RanaX System status updated to {val}!", show_alert=True)
        
        ranax_status = val
        sources = await ranax_groups_col.find({}).to_list(length=50)
        text = f"ðŸ›¡ï¸ **RanaX Auto-OTP Forwarder Panel**\n\nâš¡ System Status: `{ranax_status}`\nðŸ“Œ à¦¸à§‹à¦°à§à¦¸ à¦šà§à¦¯à¦¾à¦Ÿ à¦†à¦‡à¦¡à¦¿ à¦¬à¦¾ à¦—à§à¦°à§à¦ª à¦²à¦¿à¦¸à§à¦Ÿ à¦¨à¦¿à¦šà§‡ à¦¦à§‡à¦“à§Ÿà¦¾ à¦¹à¦²à§‹:"
        keyboard = []
        for s in sources:
            g_id = s.get("chat_id")
            g_name = s.get("name", "Source Group")
            keyboard.append([
                InlineKeyboardButton(f"ðŸ“ {g_name} (`{g_id}`)", callback_data=f"noop_rx_{g_id}"),
                InlineKeyboardButton("âŒ à¦¡à¦¿à¦²à¦¿à¦Ÿ", callback_data=f"rx_del:{g_id}")
            ])
        status_btn_text = "ðŸ”´ Turn OFF" if ranax_status == "ON" else "ðŸŸ¢ Turn ON"
        status_toggle_val = "OFF" if ranax_status == "ON" else "ON"
        keyboard.append([InlineKeyboardButton(status_btn_text, callback_data=f"rx_toggle:{status_toggle_val}")])
        keyboard.append([InlineKeyboardButton("âž• Add Source Chat ID", callback_data="rx_add_start")])
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "rx_add_start" and await is_admin(user_id):
        await query.answer()
        RANAX_ADD_STATE[user_id] = {"step": "GET_NAME"}
        await query.message.edit_text(
            "âž• **Add RanaX Source Chat**\n\nà¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦—à§à¦°à§à¦ª à¦¬à¦¾ à¦šà§à¦¯à¦¾à¦¨à§‡à¦²à§‡à¦° à¦¨à¦¾à¦® (Name) à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="ranax_control")]])
        )

    elif query.data.startswith("rx_del:") and await is_admin(user_id):
        del_id = query.data.split(":", 1)[1]
        await ranax_groups_col.delete_one({"chat_id": del_id})
        await query.answer("âœ… Source Chat ID successfully removed!", show_alert=True)
        
        ranax_status = await get_setting("ranax_status", "ON")
        sources = await ranax_groups_col.find({}).to_list(length=50)
        text = f"ðŸ›¡ï¸ **RanaX Auto-OTP Forwarder Panel**\n\nâš¡ System Status: `{ranax_status}`\nðŸ“Œ à¦¸à§‹à¦°à§à¦¸ à¦šà§à¦¯à¦¾à¦Ÿ à¦†à¦‡à¦¡à¦¿ à¦¬à¦¾ à¦—à§à¦°à§à¦ª à¦²à¦¿à¦¸à§à¦Ÿ à¦¨à¦¿à¦šà§‡ à¦¦à§‡à¦“à§Ÿà¦¾ à¦¹à¦²à§‹:"
        keyboard = []
        for s in sources:
            g_id = s.get("chat_id")
            g_name = s.get("name", "Source Group")
            keyboard.append([
                InlineKeyboardButton(f"ðŸ“ {g_name} (`{g_id}`)", callback_data=f"noop_rx_{g_id}"),
                InlineKeyboardButton("âŒ à¦¡à¦¿à¦²à¦¿à¦Ÿ", callback_data=f"rx_del:{g_id}")
            ])
        status_btn_text = "ðŸ”´ Turn OFF" if ranax_status == "ON" else "ðŸŸ¢ Turn ON"
        status_toggle_val = "OFF" if ranax_status == "ON" else "ON"
        keyboard.append([InlineKeyboardButton(status_btn_text, callback_data=f"rx_toggle:{status_toggle_val}")])
        keyboard.append([InlineKeyboardButton("âž• Add Source Chat ID", callback_data="rx_add_start")])
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # --- 1. Admin Management System ---
    elif query.data == "adm_mgmt_menu" and await is_admin(user_id):
        await query.answer()
        admins = await admins_col.find({}).to_list(length=100)
        text = f"ðŸ‘‘ **Admin Management System**\n\nPrimary Owner ID: `{OWNER_ID}`\n\n**Current Admins:**"
        
        keyboard = []
        if not admins:
            keyboard.append([InlineKeyboardButton("âš ï¸ à¦•à§‹à¦¨à§‹ à¦¸à¦¾à¦¬-à¦à¦¡à¦®à¦¿à¦¨ à¦¨à§‡à¦‡", callback_data="noop")])
        else:
            for adm in admins:
                adm_id = adm['user_id']
                adm_name = adm.get('username', 'Admin')
                keyboard.append([
                    InlineKeyboardButton(f"ðŸ‘¤ {adm_name} (`{adm_id}`)", callback_data=f"noop_{adm_id}"),
                    InlineKeyboardButton("âŒ à¦°à¦¿à¦®à§à¦­", callback_data=f"adm_do_rem:{adm_id}")
                ])

        keyboard.append([InlineKeyboardButton("âž• Add Admin", callback_data="adm_add_start")])
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")])
        
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "adm_add_start" and user_id == OWNER_ID:
        await query.answer()
        ADMIN_ADD_STATE[user_id] = True
        await query.message.edit_text(
            "âž• **Add New Admin**\n\nà¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦¨à¦¤à§à¦¨ à¦à¦¡à¦®à¦¿à¦¨à§‡à¦° **Telegram Chat ID** à¦¬à¦¾ à¦‡à¦‰à¦œà¦¾à¦°à¦¨à§‡à¦® à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_mgmt_menu")]])
        )

    elif query.data.startswith("adm_do_rem:") and user_id == OWNER_ID:
        rem_id = int(query.data.split(":", 1)[1])
        await admins_col.delete_one({"user_id": rem_id})
        await query.answer(f"âœ… Admin {rem_id} successfully removed!", show_alert=True)
        
        admins = await admins_col.find({}).to_list(length=100)
        text = f"ðŸ‘‘ **Admin Management System**\n\nPrimary Owner ID: `{OWNER_ID}`\n\n**Current Admins:**"
        keyboard = []
        for adm in admins:
            adm_id = adm['user_id']
            adm_name = adm.get('username', 'Admin')
            keyboard.append([
                InlineKeyboardButton(f"ðŸ‘¤ {adm_name} (`{adm_id}`)", callback_data=f"noop_{adm_id}"),
                InlineKeyboardButton("âŒ à¦°à¦¿à¦®à§à¦­", callback_data=f"adm_do_rem:{adm_id}")
            ])
        keyboard.append([InlineKeyboardButton("âž• Add Admin", callback_data="adm_add_start")])
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # --- 2. Force Join System ---
    elif query.data == "adm_fj_menu" and await is_admin(user_id):
        await query.answer()
        fj_status = await get_setting("force_join_status", "ON")
        channels = await channels_col.find({}).to_list(length=50)
        
        text = f"ðŸ“¢ **Force Join System Control**\n\nSTATUS: `{fj_status}`\n\n**Managed Channels:**"
        
        keyboard = []
        if channels:
            for c in channels:
                c_name = c.get('name', 'Channel')
                c_id = c.get('chat_id')
                keyboard.append([
                    InlineKeyboardButton(f"ðŸ“¢ {c_name} (`{c_id}`)", callback_data=f"noop_chan_{c_id}"),
                    InlineKeyboardButton("ðŸ—‘ï¸ à¦°à¦¿à¦®à§à¦­", callback_data=f"fj_do_del:{c_id}")
                ])
        else:
            text += "\nâš ï¸ à¦•à§‹à¦¨à§‹ à¦•à¦¾à¦¸à§à¦Ÿà¦® à¦šà§à¦¯à¦¾à¦¨à§‡à¦² à¦¯à§à¦•à§à¦¤ à¦•à¦°à¦¾ à¦¹à§Ÿà¦¨à¦¿à¥¤"

        status_toggle_btn = "ðŸ”´ Turn OFF" if fj_status == "ON" else "ðŸŸ¢ Turn ON"
        toggle_val = "OFF" if fj_status == "ON" else "ON"

        keyboard.append([InlineKeyboardButton(status_toggle_btn, callback_data=f"set_fj:{toggle_val}")])
        keyboard.append([InlineKeyboardButton("âž• Add Channel", callback_data="fj_add_ch")])
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")])
        
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("set_fj:") and await is_admin(user_id):
        val = query.data.split(":", 1)[1]
        await set_setting("force_join_status", val)
        await query.answer(f"Force Join Status set to {val}!", show_alert=True)
        
        fj_status = val
        channels = await channels_col.find({}).to_list(length=50)
        text = f"ðŸ“¢ **Force Join System Control**\n\nSTATUS: `{fj_status}`\n\n**Managed Channels:**"
        keyboard = []
        for c in channels:
            keyboard.append([
                InlineKeyboardButton(f"ðŸ“¢ {c.get('name')} (`{c.get('chat_id')}`)", callback_data=f"noop"),
                InlineKeyboardButton("ðŸ—‘ï¸ à¦°à¦¿à¦®à§à¦­", callback_data=f"fj_do_del:{c.get('chat_id')}")
            ])
        status_toggle_btn = "ðŸ”´ Turn OFF" if fj_status == "ON" else "ðŸŸ¢ Turn ON"
        toggle_val = "OFF" if fj_status == "ON" else "ON"
        keyboard.append([InlineKeyboardButton(status_toggle_btn, callback_data=f"set_fj:{toggle_val}")])
        keyboard.append([InlineKeyboardButton("âž• Add Channel", callback_data="fj_add_ch")])
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "fj_add_ch" and await is_admin(user_id):
        await query.answer()
        CHANNEL_ADD_STATE[user_id] = {"step": "GET_NAME"}
        await query.message.edit_text(
            "ðŸ“¢ **Add Force Join Channel**\n\nà¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦šà§à¦¯à¦¾à¦¨à§‡à¦²à§‡à¦° à¦¨à¦¾à¦® (Name) à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_fj_menu")]])
        )

    elif query.data.startswith("fj_do_del:") and await is_admin(user_id):
        chat_id_to_del = query.data.split(":", 1)[1]
        await channels_col.delete_one({"chat_id": chat_id_to_del})
        await query.answer("âœ… Channel successfully deleted!", show_alert=True)
        
        fj_status = await get_setting("force_join_status", "ON")
        channels = await channels_col.find({}).to_list(length=50)
        text = f"ðŸ“¢ **Force Join System Control**\n\nSTATUS: `{fj_status}`\n\n**Managed Channels:**"
        keyboard = []
        for c in channels:
            keyboard.append([
                InlineKeyboardButton(f"ðŸ“¢ {c.get('name')} (`{c.get('chat_id')}`)", callback_data="noop"),
                InlineKeyboardButton("ðŸ—‘ï¸ à¦°à¦¿à¦®à§à¦­", callback_data=f"fj_do_del:{c.get('chat_id')}")
            ])
        status_toggle_btn = "ðŸ”´ Turn OFF" if fj_status == "ON" else "ðŸŸ¢ Turn ON"
        toggle_val = "OFF" if fj_status == "ON" else "ON"
        keyboard.append([InlineKeyboardButton(status_toggle_btn, callback_data=f"set_fj:{toggle_val}")])
        keyboard.append([InlineKeyboardButton("âž• Add Channel", callback_data="fj_add_ch")])
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # --- 3. User Management & Analytics ---
    elif query.data == "adm_usermgmt_menu" and await is_admin(user_id):
        await query.answer()
        total_u = await users_col.count_documents({})
        verified_u = await users_col.count_documents({"balance": {"$gt": 0.0}})
        banned_u = await users_col.count_documents({"banned": True})

        text = (
            f"ðŸ‘¥ **User Management & Analytics**\n\n"
            f"ðŸ“Š **Live Statistics:**\n"
            f"ðŸ‘¥ Total Users: `{total_u}`\n"
            f"ðŸŸ¢ Verified Users: `{verified_u}`\n"
            f"ðŸ”´ Banned Users: `{banned_u}`\n\n"
            f"à¦¨à¦¿à¦šà§‡à¦° à¦…à¦ªà¦¶à¦¨à¦—à§à¦²à§‹ à¦¥à§‡à¦•à§‡ à¦®à§à¦¯à¦¾à¦¨à§‡à¦œ à¦•à¦°à§à¦¨:"
        )
        keyboard = [
            [InlineKeyboardButton("ðŸ’° Balance", callback_data="us_m_balance"), InlineKeyboardButton("ðŸš« Ban/Unban", callback_data="us_m_ban")],
            [InlineKeyboardButton("ðŸ‘¤ Profile", callback_data="us_m_profile"), InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")]
        ]
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "us_m_balance" and await is_admin(user_id):
        await query.answer()
        USER_MANAGE_STATE[user_id] = {"action": "balance"}
        await query.message.edit_text("ðŸ’° à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦®à§à¦¯à¦¾à¦¨à§‡à¦œ à¦•à¦°à¦¤à§‡ à¦‡à¦‰à¦œà¦¾à¦°à§‡à¦° **Chat ID** à¦¬à¦¾ **Username** à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_usermgmt_menu")]]))

    elif query.data == "us_m_ban" and await is_admin(user_id):
        await query.answer()
        USER_MANAGE_STATE[user_id] = {"action": "ban"}
        await query.message.edit_text("ðŸš« à¦¬à§à¦¯à¦¾à¦¨ à¦¬à¦¾ à¦†à¦¨à¦¬à§à¦¯à¦¾à¦¨ à¦•à¦°à¦¤à§‡ à¦‡à¦‰à¦œà¦¾à¦°à§‡à¦° **Chat ID** à¦¬à¦¾ **Username** à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_usermgmt_menu")]]))

    elif query.data == "us_m_profile" and await is_admin(user_id):
        await query.answer()
        USER_MANAGE_STATE[user_id] = {"action": "profile"}
        await query.message.edit_text("ðŸ‘¤ à¦‡à¦‰à¦œà¦¾à¦°à§‡à¦° à¦«à§à¦² à¦¡à¦¿à¦Ÿà§‡à¦‡à¦²à¦¸ à¦¦à§‡à¦–à¦¤à§‡ à¦¤à¦¾à¦° **Chat ID** à¦¬à¦¾ **Username** à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_usermgmt_menu")]]))

    # --- 4. OTP Group Management ---
    elif query.data == "adm_otpgroup_menu" and await is_admin(user_id):
        await query.answer()
        groups = await forward_groups_col.find({}).to_list(length=50)
        text = f"ðŸ’¬ **OTP Group Management**\n\n**Configured Forward Groups:**"
        
        keyboard = []
        if groups:
            for g in groups:
                g_id = g.get('group_id')
                g_name = g.get('name', 'OTP Group')
                keyboard.append([
                    InlineKeyboardButton(f"ðŸ›¡ï¸ {g_name} (`{g_id}`)", callback_data=f"noop_group_{g_id}"),
                    InlineKeyboardButton("âŒ à¦°à¦¿à¦®à§à¦­", callback_data=f"ot_do_del:{g_id}")
                ])
        else:
            text += "\nâš ï¸ à¦•à§‹à¦¨à§‹ à¦«à¦°à¦“à§Ÿà¦¾à¦°à§à¦¡ à¦—à§à¦°à§à¦ª à¦¸à§‡à¦Ÿ à¦•à¦°à¦¾ à¦¹à§Ÿà¦¨à¦¿à¥¤"

        keyboard.append([InlineKeyboardButton("âœï¸ Edit OTP Button Link", callback_data="ot_edit_link")])
        keyboard.append([InlineKeyboardButton("âž• Add Forward Group", callback_data="ot_add_group")])
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")])
        
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "ot_edit_link" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "edit_otp_link"}
        await query.message.edit_text("âœï¸ à¦¨à¦¤à§à¦¨ à¦¬à¦Ÿ à¦²à¦¿à¦‚à¦• à¦¬à¦¾ à¦šà§à¦¯à¦¾à¦¨à§‡à¦² à¦²à¦¿à¦‚à¦• à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨ à¦¯à¦¾ à¦“à¦Ÿà¦¿à¦ªà¦¿ à¦—à§à¦°à§à¦ªà§‡à¦° à¦¬à¦¾à¦Ÿà¦¨à§‡ à¦¸à§‡à¦Ÿ à¦¹à¦¬à§‡:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_otpgroup_menu")]]))

    elif query.data == "ot_add_group" and await is_admin(user_id):
        await query.answer()
        FORWARD_GROUP_ADD_STATE[user_id] = {"step": "GET_ID"}
        await query.message.edit_text("âž• à¦¨à¦¤à§à¦¨ à¦«à¦°à¦“à§Ÿà¦¾à¦°à§à¦¡ à¦—à§à¦°à§à¦ªà§‡à¦° **Chat ID** à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_otpgroup_menu")]]))

    elif query.data.startswith("ot_do_del:") and await is_admin(user_id):
        gid = query.data.split(":", 1)[1]
        await forward_groups_col.delete_one({"group_id": gid})
        await query.answer("âœ… Group successfully deleted!", show_alert=True)
        
        groups = await forward_groups_col.find({}).to_list(length=50)
        text = f"ðŸ’¬ **OTP Group Management**\n\n**Configured Forward Groups:**"
        keyboard = []
        for g in groups:
            keyboard.append([
                InlineKeyboardButton(f"ðŸ›¡ï¸ {g.get('name', 'Group')} (`{g.get('group_id')}`)", callback_data="noop"),
                InlineKeyboardButton("âŒ à¦°à¦¿à¦®à§à¦­", callback_data=f"ot_do_del:{g.get('group_id')}")
            ])
        keyboard.append([InlineKeyboardButton("âœï¸ Edit OTP Button Link", callback_data="ot_edit_link")])
        keyboard.append([InlineKeyboardButton("âž• Add Forward Group", callback_data="ot_add_group")])
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")])
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
            f"ðŸš€ **X-Rony Advanced Control Panel**\n\n"
            f"ðŸ’¸ Withdrawal Status: `{wd_status}`\n"
            f"ðŸ’µ Min Withdraw: `{min_wd}à§³`\n"
            f"ðŸ‘¥ Referral Bonus: `{ref_bonus}à§³`\n"
            f"âš¡ OTP Reward Rate: `{otp_rate}à§³`\n"
            f"ðŸ“¦ Numbers per Request: `{num_req}`\n"
            f"â±ï¸ Cooldown Timer: `{cooldown}s`\n\n"
            f"à¦¨à¦¿à¦šà§‡à¦° à¦…à¦ªà¦¶à¦¨à¦—à§à¦²à§‹ à¦¥à§‡à¦•à§‡ à¦®à¦¾à¦¨ à¦ªà¦°à¦¿à¦¬à¦°à§à¦¤à¦¨ à¦•à¦°à§à¦¨:"
        )
        keyboard = [
            [InlineKeyboardButton("ðŸ’¸ Toggle Withdraw", callback_data="xr_toggle_wd")],
            [InlineKeyboardButton("ðŸ’µ Min Withdraw", callback_data="xr_set_minwd"), InlineKeyboardButton("ðŸ‘¥ Refer Bonus", callback_data="xr_set_ref")],
            [InlineKeyboardButton("âš¡ OTP Rate", callback_data="xr_set_otprate"), InlineKeyboardButton("ðŸ“¦ Num/Req", callback_data="xr_set_numreq")],
            [InlineKeyboardButton("â±ï¸ Cooldown", callback_data="xr_set_cooldown"), InlineKeyboardButton("ðŸ’³ Pay Methods", callback_data="xr_pay_methods")],
            [InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")]
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
            f"ðŸš€ **X-Rony Advanced Control Panel**\n\n"
            f"ðŸ’¸ Withdrawal Status: `{wd_status}`\n"
            f"ðŸ’µ Min Withdraw: `{min_wd}à§³`\n"
            f"ðŸ‘¥ Referral Bonus: `{ref_bonus}à§³`\n"
            f"âš¡ OTP Reward Rate: `{otp_rate}à§³`\n"
            f"ðŸ“¦ Numbers per Request: `{num_req}`\n"
            f"â±ï¸ Cooldown Timer: `{cooldown}s`\n"
        )
        keyboard = [
            [InlineKeyboardButton("ðŸ’¸ Toggle Withdraw", callback_data="xr_toggle_wd")],
            [InlineKeyboardButton("ðŸ’µ Min Withdraw", callback_data="xr_set_minwd"), InlineKeyboardButton("ðŸ‘¥ Refer Bonus", callback_data="xr_set_ref")],
            [InlineKeyboardButton("âš¡ OTP Rate", callback_data="xr_set_otprate"), InlineKeyboardButton("ðŸ“¦ Num/Req", callback_data="xr_set_numreq")],
            [InlineKeyboardButton("â±ï¸ Cooldown", callback_data="xr_set_cooldown"), InlineKeyboardButton("ðŸ’³ Pay Methods", callback_data="xr_pay_methods")],
            [InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_system_menu")]
        ]
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "xr_set_minwd" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "set_min_withdraw"}
        await query.message.edit_text("ðŸ’µ à¦¨à¦¤à§à¦¨ à¦®à¦¿à¦¨à¦¿à¦®à¦¾à¦® à¦‰à¦‡à¦¥à¦¡à§à¦° à¦…à§à¦¯à¦¾à¦®à¦¾à¦‰à¦¨à§à¦Ÿ à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨ (à¦¯à§‡à¦®à¦¨: `150`):", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_xrony_menu")]]))

    elif query.data == "xr_set_ref" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "set_ref_bonus"}
        await query.message.edit_text("ðŸ‘¥ à¦¨à¦¤à§à¦¨ à¦°à§‡à¦«à¦¾à¦° à¦¬à§‹à¦¨à¦¾à¦¸ à¦…à§à¦¯à¦¾à¦®à¦¾à¦‰à¦¨à§à¦Ÿ à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨ (à¦¯à§‡à¦®à¦¨: `0.05`):", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_xrony_menu")]]))

    elif query.data == "xr_set_otprate" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "set_otp_rate"}
        await query.message.edit_text("âš¡ à¦ªà§à¦°à¦¤à¦¿ à¦“à¦Ÿà¦¿à¦ªà¦¿ à¦°à§‡à¦Ÿ à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨ (à¦¯à§‡à¦®à¦¨: `0.80`):", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_xrony_menu")]]))

    elif query.data == "xr_set_numreq" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "set_num_req"}
        await query.message.edit_text("ðŸ“¦ à¦à¦• à¦¸à¦¾à¦¥à§‡ à¦‡à¦‰à¦œà¦¾à¦°à¦•à§‡ à¦•à§Ÿà¦Ÿà¦¿ à¦•à¦°à§‡ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦¦à§‡à¦“à§Ÿà¦¾ à¦¹à¦¬à§‡ à¦¤à¦¾ à¦²à¦¿à¦–à§à¦¨ (à¦¯à§‡à¦®à¦¨: `5`):", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_xrony_menu")]]))

    elif query.data == "xr_set_cooldown" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "set_cooldown"}
        await query.message.edit_text("â±ï¸ à¦•à§‹à¦¡à¦¾à¦‰à¦¨ à¦¸à§‡à¦•à§‡à¦¨à§à¦¡ à¦¸à§‡à¦Ÿ à¦•à¦°à§à¦¨ (à¦¯à§‡à¦®à¦¨: `10`):", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_xrony_menu")]]))

    elif query.data == "xr_pay_methods" and await is_admin(user_id):
        await query.answer()
        methods = await get_setting("payment_methods", ["Bkash", "Nagad", "Binance"])
        text = f"ðŸ’³ **Payment Methods Control**\n\nCurrent Methods: `{', '.join(methods)}`\n\nà¦¨à¦¤à§à¦¨ à¦®à§‡à¦¥à¦¡ à¦¯à§‹à¦— à¦•à¦°à¦¤à§‡ à¦¬à¦¾ à¦°à¦¿à¦®à§à¦­ à¦•à¦°à¦¤à§‡ à¦¨à¦¿à¦šà§‡à¦° à¦…à¦ªà¦¶à¦¨ à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦•à¦°à§à¦¨:"
        keyboard = [
            [InlineKeyboardButton("âž• Add Method", callback_data="xr_add_pay"), InlineKeyboardButton("ðŸ—‘ï¸ Remove Method", callback_data="xr_rem_pay")],
            [InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_xrony_menu")]
        ]
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "xr_add_pay" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "add_pay_method"}
        await query.message.edit_text("âž• à¦¨à¦¤à§à¦¨ à¦ªà§‡à¦®à§‡à¦¨à§à¦Ÿ à¦®à§‡à¦¥à¦¡à§‡à¦° à¦¨à¦¾à¦® à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨ (à¦¯à§‡à¦®à¦¨: `Rocket`):", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="xr_pay_methods")]]))

    elif query.data == "xr_rem_pay" and await is_admin(user_id):
        await query.answer()
        ADMIN_SETTINGS_STATE[user_id] = {"setting": "rem_pay_method"}
        await query.message.edit_text("ðŸ—‘ï¸ à¦¯à§‡ à¦ªà§‡à¦®à§‡à¦¨à§à¦Ÿ à¦®à§‡à¦¥à¦¡à¦Ÿà¦¿ à¦¡à¦¿à¦²à¦¿à¦Ÿ à¦•à¦°à¦¤à§‡ à¦šà¦¾à¦¨ à¦¤à¦¾à¦° à¦¨à¦¾à¦® à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="xr_pay_methods")]]))

    elif query.data == "adm_leaderboard" and await is_admin(user_id):
        await query.answer()
        cursor = users_col.find({}).sort("total_earned", -1).limit(10)
        top_users = await cursor.to_list(length=10)
        text = "ðŸ† **OTP Hunter Leaderboard** ðŸ†\n\n"
        rank_emojis = ["ðŸ¥‡", "ðŸ¥ˆ", "ðŸ¥‰", "4ï¸âƒ£", "5ï¸âƒ£", "6ï¸âƒ£", "7ï¸âƒ£", "8ï¸âƒ£", "9ï¸âƒ£", "ðŸ”Ÿ"]
        if not top_users:
            text += "âš ï¸ à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨à§‡ à¦•à§‹à¦¨à§‹ à¦²à¦¿à¦¡à¦¾à¦°à¦¬à§‹à¦°à§à¦¡ à¦¡à¦¾à¦Ÿà¦¾ à¦¨à§‡à¦‡ã€‚"
        else:
            for index, u in enumerate(top_users):
                emoji = rank_emojis[index] if index < 10 else "ðŸ‘¤"
                uname = f"@{u['username']}" if u.get('username') else f"User `{u['user_id']}`"
                earned = u.get('total_earned', 0.0)
                text += f"{emoji} {uname} â€” `ðŸ’° {earned:.2f}à§³`\n"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_back")]])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif query.data == "adm_upload" and await is_admin(user_id):
        await query.answer()
        ADMIN_UPLOAD_STATE[user_id] = {"step": "GET_SERVICE"}
        await query.message.edit_text("âš™ï¸ à¦•à§‹à¦¨ à¦¸à¦¾à¦°à§à¦­à¦¿à¦¸à§‡à¦° à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦†à¦ªà¦²à§‹à¦¡ à¦•à¦°à¦¬à§‡à¦¨ à¦¸à§‡à¦‡ à¦¨à¦¾à¦® à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨ (à¦¯à§‡à¦®à¦¨: Facebook):", parse_mode="Markdown")

    elif query.data == "adm_delete" and await is_admin(user_id):
        await query.answer()
        pipeline = [{"$group": {"_id": {"service": "$service_name", "country": "$country"}, "count": {"$sum": 1}}}]
        cursor = numbers_col.aggregate(pipeline)
        batches = await cursor.to_list(length=100)
        if not batches:
            text = "ðŸ—‘ï¸ **Delete Files**\n\nà¦¬à¦°à§à¦¤à¦®à¦¾à¦¨à§‡ à¦¸à¦¿à¦¸à§à¦Ÿà§‡à¦®à§‡ à¦•à§‹à¦¨à§‹ à¦«à¦¾à¦‡à¦² à¦¬à¦¾ à¦¬à§à¦¯à¦¾à¦š à¦à¦­à§‡à¦‡à¦²à§‡à¦¬à¦² à¦¨à§‡à¦‡à¥¤"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_back")]])
        else:
            text = "ðŸ—‘ï¸ **Delete Files / Batches**\n\nà¦¨à¦¿à¦šà§‡à¦° à¦¤à¦¾à¦²à¦¿à¦•à¦¾ à¦¥à§‡à¦•à§‡ à¦¯à§‡ à¦«à¦¾à¦‡à¦²à¦Ÿà¦¿ à¦®à§à¦›à§‡ à¦«à§‡à¦²à¦¤à§‡ à¦šà¦¾à¦¨ à¦¸à§‡à¦Ÿà¦¿à¦¤à§‡ à¦•à§à¦²à¦¿à¦• à¦•à¦°à§à¦¨:"
            keyboard_buttons = []
            for b in batches:
                serv = b["_id"]["service"]
                count = b["count"]
                keyboard_buttons.append([InlineKeyboardButton(f"âŒ {serv} ({count} Nos)", callback_data=f"adm_delfile:{serv}")])
            keyboard_buttons.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_back")])
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif query.data.startswith("adm_delfile:") and await is_admin(user_id):
        service_to_del = query.data.split(":", 1)[1]
        await numbers_col.delete_many({"service_name": service_to_del})
        await traffic_col.delete_many({"service": service_to_del})
        await query.answer(f"âœ… à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ {service_to_del} à¦à¦° à¦¸à¦¬ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦¡à¦¿à¦²à¦¿à¦Ÿ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡!", show_alert=True)
        
        pipeline = [{"$group": {"_id": {"service": "$service_name", "country": "$country"}, "count": {"$sum": 1}}}]
        cursor = numbers_col.aggregate(pipeline)
        batches = await cursor.to_list(length=100)
        if not batches:
            text = "ðŸ—‘ï¸ **Delete Files**\n\nà¦¬à¦°à§à¦¤à¦®à¦¾à¦¨à§‡ à¦¸à¦¿à¦¸à§à¦Ÿà§‡à¦®à§‡ à¦•à§‹à¦¨à§‹ à¦«à¦¾à¦‡à¦² à¦¬à¦¾ à¦¬à§à¦¯à¦¾à¦š à¦à¦­à§‡à¦‡à¦²à§‡à¦¬à¦² à¦¨à§‡à¦‡à¥¤"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_back")]])
        else:
            text = "ðŸ—‘ï¸ **Delete Files / Batches**\n\nà¦¨à¦¿à¦šà§‡à¦° à¦¤à¦¾à¦²à¦¿à¦•à¦¾ à¦¥à§‡à¦•à§‡ à¦¯à§‡ à¦«à¦¾à¦‡à¦²à¦Ÿà¦¿ à¦®à§à¦›à§‡ à¦«à§‡à¦²à¦¤à§‡ à¦šà¦¾à¦¨ à¦¸à§‡à¦Ÿà¦¿à¦¤à§‡ à¦•à§à¦²à¦¿à¦• à¦•à¦°à§à¦¨:"
            keyboard_buttons = []
            for b in batches:
                serv = b["_id"]["service"]
                count = b["count"]
                keyboard_buttons.append([InlineKeyboardButton(f"âŒ {serv} ({count} Nos)", callback_data=f"adm_delfile:{serv}")])
            keyboard_buttons.append([InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_back")])
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif query.data == "adm_broadcast" and await is_admin(user_id):
        await query.answer()
        ADMIN_BROADCAST_STATE[user_id] = True
        await query.message.edit_text(
            "ðŸ“¢ **Broadcast System**\n\nà¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦¯à§‡ à¦®à§‡à¦¸à§‡à¦œà¦Ÿà¦¿ à¦¸à¦•à¦² à¦‡à¦‰à¦œà¦¾à¦°à§‡à¦° à¦•à¦¾à¦›à§‡ à¦ªà¦¾à¦ à¦¾à¦¤à§‡ à¦šà¦¾à¦¨ à¦¸à§‡à¦Ÿà¦¿ à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data="adm_back")]])
        )

    elif query.data == "adm_close" and await is_admin(user_id):
        await query.answer("à¦ªà§à¦¯à¦¾à¦¨à§‡à¦² à¦¬à¦¨à§à¦§ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡à¥¤")
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
        await query.answer("ðŸ”„ à¦Ÿà§à¦°à¦¾à¦«à¦¿à¦• à¦°à¦¿à¦«à§à¦°à§‡à¦¶ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡!")
        traffic_list = await traffic_col.find({}).to_list(length=100)
        if not traffic_list:
            text = "ðŸ“Š à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨à§‡ à¦•à§‹à¦¨à§‹ à¦Ÿà§à¦°à¦¾à¦«à¦¿à¦• à¦†à¦ªà¦¡à§‡à¦Ÿ à¦¨à§‡à¦‡à¥¤"
        else:
            text = "ðŸš¦ **1 HOUR LIVE TRAFFIC**\n\n"
            for item in traffic_list:
                text += f"ðŸŒ **{item['service']}**\n{item['country']} : {item['status']} {item['icon']}\n\n"
        keyboard = [[InlineKeyboardButton("ðŸ”„ Refresh", callback_data="refresh_traffic")]]
        try:
            await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            pass

    elif query.data == "withdraw_menu":
        await query.answer()
        wd_status = await get_setting("withdraw_global_status", "ON")
        if wd_status != "ON":
            await query.message.reply_text("âŒ à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨à§‡ à¦‰à¦‡à¦¥à¦¡à§à¦° à¦¸à¦¿à¦¸à§à¦Ÿà§‡à¦® à¦—à§à¦²à§‹à¦¬à¦¾à¦²à¦¿ à¦¬à¦¨à§à¦§ à¦°à¦¾à¦–à¦¾ à¦¹à§Ÿà§‡à¦›à§‡à¥¤", parse_mode="Markdown")
            return

        user_data = await users_col.find_one({"user_id": user_id})
        balance = user_data.get("balance", 0.0) if user_data else 0.0
        min_wd = float(await get_setting("min_withdraw", 100.0))
        
        if balance < min_wd:
            await query.message.reply_text(
                f"âŒ à¦¦à§à¦ƒà¦–à¦¿à¦¤! à¦‰à¦‡à¦¥à¦¡à§à¦° à¦•à¦°à¦¾à¦° à¦œà¦¨à§à¦¯ à¦†à¦ªà¦¨à¦¾à¦° à¦…à¦¨à§à¦¤à¦¤ `{min_wd}à§³` à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦¥à¦¾à¦•à¦¤à§‡ à¦¹à¦¬à§‡ã€‚\n"
                f"à¦†à¦ªà¦¨à¦¾à¦° à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸: `{balance:.2f}à§³`",
                parse_mode="Markdown"
            )
            return
        
        USER_WITHDRAW_STATE[user_id] = {"step": "SELECT_METHOD"}
        methods = await get_setting("payment_methods", ["Bkash", "Nagad", "Binance"])
        keyboard = []
        for m in methods:
            keyboard.append([InlineKeyboardButton(f"ðŸ“± {m}", callback_data=f"wd_meth:{m}")])
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back to Balance", callback_data="back_to_balance")])
        
        await query.message.edit_text(
            f"ðŸ’¸ **Withdrawal Portal**\n\n"
            f"à¦†à¦ªà¦¨à¦¾à¦° à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸: `{balance:.2f}à§³`\n"
            f"à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦†à¦ªà¦¨à¦¾à¦° à¦ªà§‡à¦®à§‡à¦¨à§à¦Ÿ à¦®à§‡à¦¥à¦¡ à¦¸à¦¿à¦²à§‡à¦•à§à¦Ÿ à¦•à¦°à§à¦¨:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("wd_meth:"):
        await query.answer()
        method = query.data.split(":", 1)[1]
        USER_WITHDRAW_STATE[user_id] = {"step": "GET_ACCOUNT", "method": method}
        await query.message.edit_text(
            f"ðŸ’³ Selected Method: **{method}**\n\n"
            f"à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦†à¦ªà¦¨à¦¾à¦° à¦¸à¦ à¦¿à¦• à¦…à§à¦¯à¦¾à¦•à¦¾à¦‰à¦¨à§à¦Ÿ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦¬à¦¾ à¦…à§à¦¯à¦¾à¦¡à§à¦°à§‡à¦¸ à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:",
            parse_mode="Markdown"
        )

    elif query.data.startswith("wd_conf:"):
        await query.answer()
        parts = query.data.split(":")
        action = parts[1]
        target_user_id = int(parts[2])
        amount = float(parts[3])
        
        if action == "yes":
            await query.message.edit_text(f"{query.message.text}\n\nâœ… **Status: Confirmed & Completed by Admin**", parse_mode="Markdown")
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"ðŸŽ‰ **à¦…à¦­à¦¿à¦¨à¦¨à§à¦¦à¦¨!** à¦†à¦ªà¦¨à¦¾à¦° à¦‰à¦‡à¦¥à¦¡à§à¦° à¦°à¦¿à¦•à§‹à§Ÿà§‡à¦¸à§à¦Ÿà¦Ÿà¦¿ à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦¸à¦®à§à¦ªà§‚à¦°à§à¦£ à¦¹à§Ÿà§‡à¦›à§‡ à¦à¦¬à¦‚ à¦ªà§‡à¦®à§‡à¦¨à§à¦Ÿ à¦ªà¦¾à¦ à¦¿à§Ÿà§‡ à¦¦à§‡à¦“à§Ÿà¦¾ à¦¹à§Ÿà§‡à¦›à§‡à¥¤ âœ…",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        elif action == "no":
            await users_col.update_one({"user_id": target_user_id}, {"$inc": {"balance": amount}})
            await query.message.edit_text(f"{query.message.text}\n\nâŒ **Status: Cancelled & Refunded**", parse_mode="Markdown")
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"âŒ à¦†à¦ªà¦¨à¦¾à¦° à¦‰à¦‡à¦¥à¦¡à§à¦° à¦°à¦¿à¦•à§‹à§Ÿà§‡à¦¸à§à¦Ÿà¦Ÿà¦¿ à¦¬à¦¾à¦¤à¦¿à¦² à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡ à¦à¦¬à¦‚ `{amount}à§³` à¦†à¦ªà¦¨à¦¾à¦° à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸à§‡ à¦«à¦¿à¦°à¦¿à§Ÿà§‡ à¦¦à§‡à¦“à§Ÿà¦¾ à¦¹à§Ÿà§‡à¦›à§‡à¥¤",
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
                await query.message.edit_text("âš ï¸ à¦¸à§‡à¦¶à¦¨ à¦®à§‡à§Ÿà¦¾à¦¦à§‹à¦¤à§à¦¤à§€à¦°à§à¦£ à¦¹à§Ÿà§‡ à¦—à§‡à¦›à§‡à¥¤")
                return
            
            method = data["method"]
            account = data["account"]
            amount = data["amount"]
            
            await users_col.update_one({"user_id": user_id}, {"$inc": {"balance": -amount}})
            if user_id in USER_WITHDRAW_STATE:
                del USER_WITHDRAW_STATE[user_id]
                
            await query.message.edit_text(
                f"ðŸŽ‰ **à¦‰à¦‡à¦¥à¦¡à§à¦° à¦°à¦¿à¦•à§‹à§Ÿà§‡à¦¸à§à¦Ÿ à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦œà¦®à¦¾ à¦¹à§Ÿà§‡à¦›à§‡!**\n\n"
                f"ðŸ’³ Method: `{method}`\n"
                f"ðŸ“¥ Account: `{account}`\n"
                f"ðŸ’° Amount: `{amount:.2f}à§³`\n\n"
                f"â³ à¦°à¦¿à¦•à§‹à§Ÿà§‡à¦¸à§à¦Ÿà¦Ÿà¦¿ à¦°à¦¿à¦­à¦¿à¦‰ à¦•à¦°à§‡ à¦ªà§‡à¦®à§‡à¦¨à§à¦Ÿ à¦¸à¦®à§à¦ªà¦¨à§à¦¨ à¦•à¦°à¦¾ à¦¹à¦¬à§‡à¥¤ à¦§à¦¨à§à¦¯à¦¬à¦¾à¦¦!",
                parse_mode="Markdown"
            )
            
            username_str = f"@{query.from_user.username}" if query.from_user.username else "No Username"
            admin_msg = (
                f"ðŸš¨ **New Withdrawal Request!**\n\n"
                f"ðŸ‘¤ User ID: `{user_id}`\n"
                f"ðŸ”— Username: {username_str}\n"
                f"ðŸ’³ Method: `{method}`\n"
                f"ðŸ“¥ Account: `{account}`\n"
                f"ðŸ’µ Amount: `{amount:.2f}à§³`"
            )
            admin_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("âœ… Confirm", callback_data=f"wd_conf:yes:{user_id}:{amount}"),
                    InlineKeyboardButton("âŒ Cancel", callback_data=f"wd_conf:no:{user_id}:{amount}")
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
            await query.message.edit_text("âŒ à¦‰à¦‡à¦¥à¦¡à§à¦° à¦°à¦¿à¦•à§‹à§Ÿà§‡à¦¸à§à¦Ÿ à¦¬à¦¾à¦¤à¦¿à¦² à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡à¥¤")

    elif query.data == "back_to_balance":
        await query.answer()
        if user_id in USER_WITHDRAW_STATE:
            del USER_WITHDRAW_STATE[user_id]
        user_data = await users_col.find_one({"user_id": user_id})
        balance = user_data.get("balance", 0.0) if user_data else 0.0
        total_earned = user_data.get("total_earned", 0.0) if user_data else 0.0
        current_otp_rate = await get_setting("otp_rate", 0.60)
        
        balance_text = (
            f"ðŸ‘¤ **User Account Dashboard**\n\n"
            f"ðŸ’° Current Balance : `{balance:.2f}à§³`\n"
            f"ðŸ“ˆ Total Earned : `{total_earned:.2f}à§³`\n"
            f"ðŸ’¸ Withdrawal Status : `Active`\n\n"
            f"âš¡ Earn per OTP: `{current_otp_rate}à§³`"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("ðŸ’¸ Withdraw Balance", callback_data="withdraw_menu")]
        ])
        await query.message.edit_text(balance_text, parse_mode="Markdown", reply_markup=keyboard)

    elif query.data == "get_number_menu":
        await query.answer()
        configured = []
        for panel_name in PANEL_NAMES:
            doc = await get_panel_doc(panel_name)
            if doc:
                configured.append(panel_name)

        if configured:
            keyboard = []
            for panel_name in configured:
                code = PANEL_CODES[panel_name]
                keyboard.append([InlineKeyboardButton(
                    f"ðŸ”¹ {code}",
                    callback_data=f"get_provider:{panel_cb_value(panel_name)}"
                )])
            keyboard.append([InlineKeyboardButton("ðŸ”™ Back to Menu", callback_data="back_to_main_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            text_msg = "ðŸ“± **Select Number Panel:**\n\n" + " â€¢ ".join(f"{PANEL_CODES[p]} = {p}" for p in configured)
        else:
            services = await numbers_col.distinct("service_name", {"status": "Available"})
            if services:
                keyboard = [[InlineKeyboardButton(f"ðŸ“± {s}", callback_data=f"sel_serv:{s}")] for s in services]
                keyboard.append([InlineKeyboardButton("ðŸ”™ Back to Menu", callback_data="back_to_main_menu")])
                reply_markup = InlineKeyboardMarkup(keyboard)
                text_msg = "ðŸ“± **Select a Service:**"
            else:
                reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back to Menu", callback_data="back_to_main_menu")]])
                text_msg = "ðŸ“± **Get Number Menu**\n\nâš ï¸ à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨à§‡ à¦•à§‹à¦¨à§‹ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦¸à§à¦Ÿà¦• à¦ à¦¨à§‡à¦‡!"
        try:
            await query.message.edit_text(text_msg, parse_mode="Markdown", reply_markup=reply_markup)
        except Exception:
            await query.message.reply_text(text_msg, parse_mode="Markdown", reply_markup=reply_markup)

    elif query.data.startswith("get_provider:"):
        await query.answer()
        panel_name = panel_cb_decode(query.data.split(":", 1)[1])
        services = await provider_inventory_services(panel_name)
        # If provider-tagged inventory is not present, show the configured catalog as a safe preview.
        if not services:
            doc = await get_panel_doc(panel_name)
            services = [s.get("name") for s in (doc.get("services", []) if doc else []) if s.get("name")]
        keyboard = [[InlineKeyboardButton(f"ðŸ“¦ {s}", callback_data=f"sel_provider_service:{panel_cb_value(panel_name)}:{panel_cb_value(s)}")] for s in services]
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back to Panels", callback_data="get_number_menu")])
        text_msg = f"ðŸ“± **{panel_name}**\n\nSelect a service:"
        if not services:
            text_msg += "\n\nâš ï¸ à¦à¦‡ panel-à¦ à¦•à§‹à¦¨à§‹ service configure à¦•à¦°à¦¾ à¦¹à§Ÿà¦¨à¦¿à¥¤"
        await query.message.edit_text(text_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("sel_provider_service:"):
        await query.answer()
        _, panel_enc, service_enc = query.data.split(":", 2)
        panel_name = panel_cb_decode(panel_enc)
        service_name = panel_cb_decode(service_enc)
        countries = await provider_inventory_countries(panel_name, service_name)
        if not countries:
            doc = await get_panel_doc(panel_name)
            service = next((s for s in (doc.get("services", []) if doc else []) if s.get("name") == service_name), None)
            countries = [c.get("name") for c in (service.get("countries", []) if service else []) if c.get("name")]
        keyboard = [[InlineKeyboardButton(f"ðŸŒ {c}", callback_data=f"sel_provider_count:{panel_cb_value(panel_name)}:{panel_cb_value(service_name)}:{panel_cb_value(c)}")] for c in countries]
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back to Panel", callback_data=f"get_provider:{panel_cb_value(panel_name)}")])
        text_msg = f"ðŸŒ **{panel_name} / {service_name}**\n\nSelect a country:"
        if not countries:
            text_msg += "\n\nâš ï¸ à¦•à§‹à¦¨à§‹ country configure à¦•à¦°à¦¾ à¦¹à§Ÿà¦¨à¦¿à¥¤"
        await query.message.edit_text(text_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("sel_provider_count:"):
        await query.answer()
        _, panel_enc, service_enc, country_enc = query.data.split(":", 3)
        panel_name = panel_cb_decode(panel_enc)
        service_name = panel_cb_decode(service_enc)
        country = panel_cb_decode(country_enc)
        num_req = int(await get_setting("num_request_count", 2))
        cursor = numbers_col.find({
            "provider": panel_name,
            "service_name": {"$regex": f"^{re.escape(service_name)}$", "$options": "i"},
            "country": {"$regex": f"^{re.escape(country)}$", "$options": "i"},
            "status": "Available"
        }).limit(num_req)
        numbers = await cursor.to_list(length=num_req)
        if not numbers:
            await query.message.edit_text(
                f"âš ï¸ `{panel_name}` â†’ `{service_name}` â†’ `{country}` à¦ provider-tagged inventory à¦¨à§‡à¦‡à¥¤\n\n"
                "Admin-à¦•à§‡ provider-tagged inventory à¦¯à§‹à¦— à¦•à¦°à¦¤à§‡ à¦¹à¦¬à§‡à¥¤",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back", callback_data=f"sel_provider_service:{panel_cb_value(panel_name)}:{panel_cb_value(service_name)}")]])
            )
            return
        num_ids=[doc["_id"] for doc in numbers]
        await numbers_col.update_many({"_id":{"$in":num_ids}}, {"$set":{"status":"Assigned"}})
        for doc in numbers:
            await assigned_col.insert_one({
                "user_id": user_id, "phone_number": doc["phone_number"],
                "service_name": service_name, "country": country, "provider": panel_name
            })
        keyboard=[[InlineKeyboardButton(f"ðŸ“² ðŸ“‹ {doc['phone_number']}", copy_text=CopyTextButton(text=doc["phone_number"]))] for doc in numbers]
        keyboard.append([InlineKeyboardButton("ðŸ”™ Back to Country", callback_data=f"sel_provider_service:{panel_cb_value(panel_name)}:{panel_cb_value(service_name)}")])
        await query.message.edit_text(
            f"ðŸŒ `{country}` â€¢ `{service_name}` â€¢ `{panel_name}`\n\n"
            f"ðŸ“± {len(numbers)} number(s) allocated.\n"
            "â„¹ï¸ OTP handling is not included in this safe configuration build.",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "back_to_main_menu":
        await query.answer()
        user = query.from_user
        custom_welcome = await get_setting("start_menu_text", None)
        if not custom_welcome:
            welcome_text = (
                f"ðŸŒ **NUMBER PANEL**\n\n"
                f"ðŸ‘‹ Welcome, **{user.first_name}**\n"
                f"ðŸš€ Premium Number Management System\n\n"
                f"âš¡ Fast â€¢ Simple â€¢ Secure"
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
            keyboard = [[InlineKeyboardButton(f"ðŸŒ {country}", callback_data=f"sel_count:{service_name}:{country}")] for country in countries]
            keyboard.append([InlineKeyboardButton("ðŸ”™ Back to Services", callback_data="get_number_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            text_msg = f"ðŸŒ **Select Country for `{service_name}`:**"
        else:
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”™ Back to Services", callback_data="get_number_menu")]])
            text_msg = f"âš ï¸ `{service_name}` à¦¸à¦¾à¦°à§à¦­à¦¿à¦¸à§‡ à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨à§‡ à¦•à§‹à¦¨à§‹ à¦•à¦¾à¦¨à§à¦Ÿà§à¦°à¦¿ à¦à¦­à§‡à¦‡à¦²à§‡à¦¬à¦² à¦¨à§‡à¦‡!"
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
                f"ðŸŒ {country} Allocated ðŸ’¬ {service_name}\n"
                f"ðŸ”— Otp Rate : {current_otp_rate}à§³\n"
                f"â³ Waiting for OTP...... â¬‡ï¸"
            )
            
            keyboard = []
            for doc in numbers:
                num = doc['phone_number']
                keyboard.append([InlineKeyboardButton(f"ðŸ“² ðŸ“‹ {num}", copy_text=CopyTextButton(text=num))])
            
            keyboard.append([InlineKeyboardButton("ðŸ”„ Change Number", callback_data=f"change_num:{service_name}:{country}")])
            keyboard.append([
                InlineKeyboardButton("ðŸŒ Other Countries", callback_data=f"sel_serv:{service_name}"),
                InlineKeyboardButton("ðŸŒ OTP Group", url=OTP_GROUP_URL)
            ])
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            text_msg = f"âš ï¸ à¦¦à§à¦ƒà¦–à¦¿à¦¤! `{service_name}` ({country}) à¦ à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨à§‡ à¦¨à¦¤à§à¦¨ à¦•à§‹à¦¨à§‹ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦à¦­à§‡à¦‡à¦²à§‡à¦¬à¦² à¦¨à§‡à¦‡à¥¤"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("ðŸŒ Other Countries", callback_data=f"sel_serv:{service_name}")]])
        
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
            
            text_msg = f"ðŸ”Ž **SEARCH RESULTS** (Prefix: `{prefix}`)"
            keyboard = []
            for doc in numbers:
                num = doc['phone_number']
                keyboard.append([InlineKeyboardButton(f"ðŸ“² ðŸ“‹ {num}", copy_text=CopyTextButton(text=num))])
            
            keyboard.append([InlineKeyboardButton("ðŸ”„ Change Number", callback_data=f"search_next:{prefix}")])
            keyboard.append([
                InlineKeyboardButton("ðŸŒ Other Countries", callback_data="get_number_menu"),
                InlineKeyboardButton("ðŸŒ OTP Group", url=OTP_GROUP_URL)
            ])
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.message.edit_text(text_msg, parse_mode="Markdown", reply_markup=reply_markup)
            except Exception:
                await query.message.reply_text(text_msg, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await query.message.edit_text(
                f"âŒ à¦à¦‡ à¦¸à¦¿à¦°à¦¿à§Ÿà¦¾à¦² à¦¬à¦¾ à¦ªà§à¦°à¦«à¦¿à¦•à§à¦¸à§‡à¦° (`{prefix}`) à¦†à¦° à¦•à§‹à¦¨à§‹ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦à¦­à§‡à¦‡à¦²à§‡à¦¬à¦² à¦¨à§‡à¦‡!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ðŸŒ Other Countries", callback_data="get_number_menu")]] )
            )

# --- Live OTP group forwarding intentionally disabled in this safe build ---
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
        await update.message.reply_text("âŒ à¦†à¦ªà¦¨à¦¿ à¦à¦‡ à¦¬à¦Ÿ à¦¥à§‡à¦•à§‡ à¦¬à§à¦¯à¦¾à¦¨ à¦¹à§Ÿà§‡à¦›à§‡à¦¨à¥¤")
        return

    if text == "ðŸ”™ Back":
        for state_dict in [ADMIN_UPLOAD_STATE, USER_SEARCH_STATE, ADMIN_SETTINGS_STATE, USER_WITHDRAW_STATE, ADMIN_BROADCAST_STATE, ADMIN_ADD_STATE, CHANNEL_ADD_STATE, FORWARD_GROUP_ADD_STATE, USER_MANAGE_STATE, RANAX_ADD_STATE, MENU_EDIT_STATE, TEST_STATE, PANEL_STATE]:
            if user_id in state_dict:
                del state_dict[user_id]
            
        reply_markup = await build_main_menu(user_id)
        await update.message.reply_text("ðŸ‘‡ Main Menu:", reply_markup=reply_markup)
        return

    is_joined = await check_force_join(user_id, context)
    if not is_joined and text != "/start":
        channels_list = await channels_col.find({}).to_list(length=50)
        inline_kb = []
        if channels_list:
            for ch in channels_list:
                inline_kb.append([InlineKeyboardButton(f"ðŸ“¢ Join {ch.get('name')}", url=ch.get('url'))])
        else:
            inline_kb.append([InlineKeyboardButton("ðŸ“¢ Join Main Channel", url=MAIN_CHANNEL_URL)])
            inline_kb.append([InlineKeyboardButton("ðŸ“¢ Join Update Channel", url=UPDATE_CHANNEL_URL)])
            
        inline_kb.append([InlineKeyboardButton("ðŸ’¬ Join OTP Group", url=OTP_GROUP_URL)])
        inline_kb.append([InlineKeyboardButton("âœ… Joined / Check", callback_data="check_join")])

        await update.message.reply_text(
            "âš ï¸ à¦†à¦ªà¦¨à¦¿ à¦šà§à¦¯à¦¾à¦¨à§‡à¦² à¦¬à¦¾ à¦—à§à¦°à§à¦ª à¦¥à§‡à¦•à§‡ à¦²à¦¿à¦­ à¦¨à¦¿à§Ÿà§‡à¦›à§‡à¦¨!\nà¦¬à¦Ÿ à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦•à¦°à¦¤à§‡ à¦¹à¦²à§‡ à¦†à¦¬à¦¾à¦° à¦œà§Ÿà§‡à¦¨ à¦•à¦°à§‡ à¦šà§‡à¦• à¦•à¦°à§à¦¨:",
            reply_markup=InlineKeyboardMarkup(inline_kb)
        )
        return


    # --- Multi-Provider Panel Manager State Handler ---
    if await is_admin(user_id) and user_id in PANEL_STATE:
        state = PANEL_STATE[user_id]
        step = state.get("step")

        if step == "API_KEY":
            key = text.strip()
            if not key or len(key) > 256:
                await update.message.reply_text("âŒ API key à¦–à¦¾à¦²à¦¿/à¦…à¦¸à§à¦¬à¦¾à¦­à¦¾à¦¬à¦¿à¦• à¦¦à§€à¦°à§à¦˜à¥¤ à¦†à¦¬à¦¾à¦° à¦ªà¦¾à¦ à¦¾à¦¨:", reply_markup=back_keyboard())
                return
            panel_name = state["panel"]
            await provider_panels_col.update_one(
                {"_id": panel_name},
                {"$addToSet": {"api_keys": key}, "$setOnInsert": {"services": []}},
                upsert=True
            )
            del PANEL_STATE[user_id]
            await update.message.reply_text(
                f"âœ… **{panel_name} API key saved.**\n\n"
                "à¦¨à¦¿à¦°à¦¾à¦ªà¦¤à§à¦¤à¦¾à¦° à¦œà¦¨à§à¦¯ UI-à¦¤à§‡ key masked à¦…à¦¬à¦¸à§à¦¥à¦¾à§Ÿ à¦¦à§‡à¦–à¦¾à¦¨à§‹ à¦¹à¦¬à§‡à¥¤",
                parse_mode="Markdown"
            )
            return

        if step == "SERVICE_NAME":
            panel_name = state["panel"]
            service_name = text.strip()
            if not service_name or len(service_name) > 80:
                await update.message.reply_text("âŒ Service name 1â€“80 à¦…à¦•à§à¦·à¦°à§‡à¦° à¦®à¦§à§à¦¯à§‡ à¦¦à¦¿à¦¨:", reply_markup=back_keyboard())
                return
            doc = await get_panel_doc(panel_name)
            services = doc.get("services", []) if doc else []
            if any(s.get("name", "").lower() == service_name.lower() for s in services):
                await update.message.reply_text("âŒ à¦à¦‡ service à¦†à¦—à§‡ à¦¥à§‡à¦•à§‡à¦‡ à¦†à¦›à§‡à¥¤ à¦…à¦¨à§à¦¯ à¦¨à¦¾à¦® à¦¦à¦¿à¦¨:", reply_markup=back_keyboard())
                return
            services.append({"name": service_name, "countries": []})
            await provider_panels_col.update_one(
                {"_id": panel_name},
                {"$set": {"services": services}, "$setOnInsert": {"api_keys": []}},
                upsert=True
            )
            del PANEL_STATE[user_id]
            await update.message.reply_text(f"âœ… `{service_name}` service added to **{panel_name}**.", parse_mode="Markdown")
            return

        if step == "COUNTRY_NAME":
            panel_name = state["panel"]
            service_name = state["service"]
            country_name = text.strip()
            if not country_name or len(country_name) > 80:
                await update.message.reply_text("âŒ Country name 1â€“80 à¦…à¦•à§à¦·à¦°à§‡à¦° à¦®à¦§à§à¦¯à§‡ à¦¦à¦¿à¦¨:", reply_markup=back_keyboard())
                return
            doc = await get_panel_doc(panel_name)
            services = doc.get("services", []) if doc else []
            found = False
            for service in services:
                if service.get("name") == service_name:
                    found = True
                    countries = service.setdefault("countries", [])
                    if any(c.get("name", "").lower() == country_name.lower() for c in countries):
                        await update.message.reply_text("âŒ à¦à¦‡ country à¦†à¦—à§‡ à¦¥à§‡à¦•à§‡à¦‡ à¦†à¦›à§‡à¥¤", reply_markup=back_keyboard())
                        return
                    countries.append({"name": country_name, "ranges": []})
            if not found:
                await update.message.reply_text("âŒ Service à¦ªà¦¾à¦“à§Ÿà¦¾ à¦¯à¦¾à§Ÿà¦¨à¦¿à¥¤", reply_markup=back_keyboard())
                del PANEL_STATE[user_id]
                return
            await provider_panels_col.update_one({"_id": panel_name}, {"$set": {"services": services}}, upsert=True)
            del PANEL_STATE[user_id]
            await update.message.reply_text(f"âœ… `{country_name}` added under `{service_name}`.", parse_mode="Markdown")
            return

        if step == "RANGE":
            panel_name = state["panel"]
            service_name = state["service"]
            country_name = state["country"]
            range_value = text.strip()
            if not re.fullmatch(r"[A-Za-z0-9_+\\-./]{2,64}", range_value):
                await update.message.reply_text(
                    "âŒ Range-à¦ à¦¶à§à¦§à§ letters/numbers à¦à¦¬à¦‚ `_ + - . /` à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦•à¦°à§à¦¨à¥¤",
                    reply_markup=back_keyboard()
                )
                return
            doc = await get_panel_doc(panel_name)
            services = doc.get("services", []) if doc else []
            found = False
            for service in services:
                if service.get("name") == service_name:
                    for country in service.setdefault("countries", []):
                        if country.get("name") == country_name:
                            found = True
                            ranges = country.setdefault("ranges", [])
                            if range_value not in ranges:
                                ranges.append(range_value)
            if not found:
                await update.message.reply_text("âŒ Service/Country à¦ªà¦¾à¦“à§Ÿà¦¾ à¦¯à¦¾à§Ÿà¦¨à¦¿à¥¤", reply_markup=back_keyboard())
                del PANEL_STATE[user_id]
                return
            await provider_panels_col.update_one({"_id": panel_name}, {"$set": {"services": services}}, upsert=True)
            del PANEL_STATE[user_id]
            await update.message.reply_text(
                f"âœ… Range `{range_value}` saved under `{panel_name} / {service_name} / {country_name}`.",
                parse_mode="Markdown"
            )
            return

        if step == "SEARCH_COUNTRY":
            panel_name = state["panel"]
            term = text.strip()
            if not term:
                await update.message.reply_text("âŒ Country name à¦²à¦¿à¦–à§à¦¨:", reply_markup=back_keyboard())
                return
            del PANEL_STATE[user_id]
            # Re-use the callback renderer by sending a small result directly.
            doc = await get_panel_doc(panel_name)
            services = doc.get("services", []) if doc else []
            matches = []
            for service in services:
                for country in service.get("countries", []):
                    if term.lower() in country.get("name", "").lower():
                        matches.append((service.get("name", "Unnamed"), country.get("name", "Unknown"), len(country.get("ranges", []))))
            keyboard = [[InlineKeyboardButton(
                f"ðŸŒ {c} â€¢ {s} ({n})",
                callback_data=f"p_country:{panel_cb_value(panel_name)}:{panel_cb_value(s)}:{panel_cb_value(c)}"
            )] for s, c, n in matches]
            keyboard.append([InlineKeyboardButton("ðŸ”™ Back", callback_data=f"p_panel:{panel_cb_value(panel_name)}")])
            msg = f"ðŸ”Ž **Search Country â€” {panel_name}**\n\n"
            msg += "à¦•à§‹à¦¨à§‹ country à¦ªà¦¾à¦“à§Ÿà¦¾ à¦¯à¦¾à§Ÿà¦¨à¦¿à¥¤" if not matches else "à¦¨à¦¿à¦šà§‡ matching country à¦—à§à¦²à§‹:"
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            return

    # --- Admin OTP Group Test State Handler ---
    if await is_admin(user_id) and user_id in TEST_STATE:
        state = TEST_STATE[user_id]
        step = state.get("step")

        if step == "GET_SERVICE":
            service = text.strip()
            if not service:
                await update.message.reply_text(
                    "âŒ Service à¦¨à¦¾à¦® à¦–à¦¾à¦²à¦¿ à¦°à¦¾à¦–à¦¾ à¦¯à¦¾à¦¬à§‡ à¦¨à¦¾à¥¤ à¦†à¦¬à¦¾à¦° à¦²à¦¿à¦–à§à¦¨:",
                    reply_markup=back_keyboard()
                )
                return
            state["service"] = service
            state["step"] = "GET_NUMBER"
            TEST_STATE[user_id] = state
            await update.message.reply_text(
                "ðŸ“ž à¦à¦¬à¦¾à¦° **Phone Number** à¦²à¦¿à¦–à§à¦¨à¥¤\n\n"
                "à¦‰à¦¦à¦¾à¦¹à¦°à¦£: `+601862810138`",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
            return

        elif step == "GET_NUMBER":
            phone = text.strip()
            normalized = re.sub(r"[^\d+]", "", phone)
            if not re.fullmatch(r"\+\d{7,15}", normalized):
                await update.message.reply_text(
                    "âŒ à¦¸à¦ à¦¿à¦• à¦†à¦¨à§à¦¤à¦°à§à¦œà¦¾à¦¤à¦¿à¦• Phone Number à¦¦à¦¿à¦¨à¥¤\n"
                    "à¦‰à¦¦à¦¾à¦¹à¦°à¦£: `+601862810138`",
                    parse_mode="Markdown",
                    reply_markup=back_keyboard()
                )
                return

            state["phone"] = normalized
            state["step"] = "GET_COUNTRY"
            TEST_STATE[user_id] = state
            await update.message.reply_text(
                "ðŸŒ à¦à¦¬à¦¾à¦° **Country Short Code** à¦²à¦¿à¦–à§à¦¨à¥¤\n\n"
                "à¦¶à§à¦§à§ 2à¦Ÿà¦¿ à¦…à¦•à§à¦·à¦° à¦¦à¦¿à¦¨ â€” à¦¯à§‡à¦®à¦¨: `MY`, `BD`, `ID`, `FR`, `US`\n"
                "à¦à¦‡ code-à¦Ÿà¦¾à¦‡ OTP à¦—à§à¦°à§à¦ªà§‡ country à¦¹à¦¿à¦¸à§‡à¦¬à§‡ à¦¦à§‡à¦–à¦¾à¦¬à§‡à¥¤",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
            return

        elif step == "GET_COUNTRY":
            country = text.strip().upper()
            if not re.fullmatch(r"[A-Z]{2}", country):
                await update.message.reply_text(
                    "âŒ Country Short Code à¦…à¦¬à¦¶à§à¦¯à¦‡ 2à¦Ÿà¦¿ à¦‡à¦‚à¦°à§‡à¦œà¦¿ à¦…à¦•à§à¦·à¦° à¦¹à¦¤à§‡ à¦¹à¦¬à§‡à¥¤\n"
                    "à¦‰à¦¦à¦¾à¦¹à¦°à¦£: `MY` / `BD` / `ID`",
                    parse_mode="Markdown",
                    reply_markup=back_keyboard()
                )
                return

            state["country"] = country
            state["step"] = "GET_OTP"
            TEST_STATE[user_id] = state
            await update.message.reply_text(
                f"ðŸŒ Country: `{country}`\n\n"
                "ðŸ” à¦à¦¬à¦¾à¦° **OTP Code** à¦²à¦¿à¦–à§à¦¨à¥¤\n"
                "à¦‰à¦¦à¦¾à¦¹à¦°à¦£: `054627`",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
            return

        elif step == "GET_OTP":
            otp = text.strip()
            if not re.fullmatch(r"\d{4,8}", otp):
                await update.message.reply_text(
                    "âŒ OTP à¦…à¦¬à¦¶à§à¦¯à¦‡ 4â€“8 à¦¸à¦‚à¦–à§à¦¯à¦¾à¦° à¦¹à¦¤à§‡ à¦¹à¦¬à§‡à¥¤\n"
                    "à¦‰à¦¦à¦¾à¦¹à¦°à¦£: `054627`",
                    parse_mode="Markdown",
                    reply_markup=back_keyboard()
                )
                return

            state["otp"] = otp
            state["step"] = "GET_LANGUAGE"
            TEST_STATE[user_id] = state
            await update.message.reply_text(
                "ðŸŒ à¦à¦¬à¦¾à¦° **Language Code** à¦²à¦¿à¦–à§à¦¨à¥¤\n\n"
                "à¦¶à§à¦§à§ 2à¦Ÿà¦¿ à¦…à¦•à§à¦·à¦° à¦¦à¦¿à¦¨, à¦¯à§‡à¦®à¦¨: `EN`, `FR`, `ID`",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
            return

        elif step == "GET_LANGUAGE":
            language = text.strip().upper()
            if not re.fullmatch(r"[A-Z]{2}", language):
                await update.message.reply_text(
                    "âŒ Language Code à¦…à¦¬à¦¶à§à¦¯à¦‡ 2à¦Ÿà¦¿ à¦…à¦•à§à¦·à¦°à§‡à¦° à¦¹à¦¤à§‡ à¦¹à¦¬à§‡à¥¤\n"
                    "à¦‰à¦¦à¦¾à¦¹à¦°à¦£: `EN` / `FR` / `ID`",
                    parse_mode="Markdown",
                    reply_markup=back_keyboard()
                )
                return

            service = state["service"]
            phone = state["phone"]
            otp = state["otp"]
            country = state["country"]
            del TEST_STATE[user_id]

            processing = await update.message.reply_text(
                "â³ Test OTP configured OTP group-à¦ à¦ªà¦¾à¦ à¦¾à¦¨à§‹ à¦¹à¦šà§à¦›à§‡..."
            )

            success, failed, total = await send_test_otp_to_configured_groups(
                context, service, phone, otp, language, country
            )

            # Show the exact same test rendering in the admin chat as well.
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=build_test_otp_text(service, phone, otp, language, country),
                    parse_mode="Markdown",
                    reply_markup=await build_test_otp_keyboard(context, otp)
                )
            except Exception:
                pass

            result_text = (
                "ðŸ§ª **OTP Group Test Complete**\n\n"
                f"ðŸ“± Service: `{service}`\n"
                f"ðŸ“ž Number: `{phone}`\n"
                f"ðŸŒ Country: `{country}`\n"
                f"ðŸ” OTP: `{otp}`\n"
                f"ðŸŒ Language: `{language}`\n\n"
                f"ðŸ“¤ Groups Found: `{total}`\n"
                f"âœ… Sent: `{success}`\n"
                f"âŒ Failed: `{failed}`"
            )
            try:
                await processing.edit_text(result_text, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(result_text, parse_mode="Markdown")
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
            await update.message.reply_text(f"âœ… à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦†à¦ªà¦¡à§‡à¦Ÿ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡!\n\nà¦¨à¦¤à§à¦¨ à¦®à¦¾à¦¨: `{new_val}`", parse_mode="Markdown")
        return

    # --- RanaX Source Chat ID Add State Handler ---
    if await is_admin(user_id) and user_id in RANAX_ADD_STATE:
        state = RANAX_ADD_STATE[user_id]
        step = state.get("step")
        if step == "GET_NAME":
            state["name"] = text.strip()
            state["step"] = "GET_CHAT_ID"
            RANAX_ADD_STATE[user_id] = state
            await update.message.reply_text("ðŸ”— à¦à¦–à¦¨ à¦“à¦‡ à¦¸à§‹à¦°à§à¦¸ à¦—à§à¦°à§à¦ª à¦¬à¦¾ à¦šà§à¦¯à¦¾à¦¨à§‡à¦²à§‡à¦° **Chat ID** (à¦¯à§‡à¦®à¦¨: `-100xxxxxxxxxx`) à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:")
            return
        elif step == "GET_CHAT_ID":
            chat_id_val = text.strip()
            await ranax_groups_col.update_one(
                {"chat_id": chat_id_val},
                {"$set": {"name": state["name"], "chat_id": chat_id_val}},
                upsert=True
            )
            del RANAX_ADD_STATE[user_id]
            await update.message.reply_text("âœ… RanaX Source Chat ID à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦¯à§à¦•à§à¦¤ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡! à¦à¦–à¦¨ à¦¥à§‡à¦•à§‡ à¦ à¦—à§à¦°à§à¦ª à¦¥à§‡à¦•à§‡ à¦“à¦Ÿà¦¿à¦ªà¦¿ à¦«à¦°à§‹à§Ÿà¦¾à¦°à§à¦¡ à¦¹à§Ÿà§‡ à¦†à¦¸à¦¬à§‡à¥¤")
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
            await update.message.reply_text(f"âœ… à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦‡à¦‰à¦œà¦¾à¦° `{target_id}` à¦•à§‡ à¦à¦¡à¦®à¦¿à¦¨ à¦¹à¦¿à¦¸à§‡à¦¬à§‡ à¦¯à§à¦•à§à¦¤ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡!", parse_mode="Markdown")
        else:
            await update.message.reply_text("âŒ à¦‡à¦‰à¦œà¦¾à¦° à¦–à§à¦à¦œà§‡ à¦ªà¦¾à¦“à§Ÿà¦¾ à¦¯à¦¾à§Ÿà¦¨à¦¿à¥¤ à¦¸à¦ à¦¿à¦• à¦†à¦‡à¦¡à¦¿ à¦¬à¦¾ à¦‡à¦‰à¦œà¦¾à¦°à¦¨à§‡à¦® à¦¦à¦¿à¦¨à¥¤")
        return

    if await is_admin(user_id) and user_id in CHANNEL_ADD_STATE:
        state = CHANNEL_ADD_STATE[user_id]
        step = state.get("step")
        if step == "GET_NAME":
            state["name"] = text.strip()
            state["step"] = "GET_ID"
            CHANNEL_ADD_STATE[user_id] = state
            await update.message.reply_text("ðŸ”— à¦à¦–à¦¨ à¦šà§à¦¯à¦¾à¦¨à§‡à¦²à§‡à¦° à¦šà§à¦¯à¦¾à¦Ÿ à¦†à¦‡à¦¡à¦¿ (à¦¯à§‡à¦®à¦¨: `@mychannel` à¦¬à¦¾ `-100...`) à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:")
            return
        elif step == "GET_ID":
            state["chat_id"] = text.strip()
            state["step"] = "GET_URL"
            CHANNEL_ADD_STATE[user_id] = state
            await update.message.reply_text("ðŸŒ à¦à¦–à¦¨ à¦šà§à¦¯à¦¾à¦¨à§‡à¦²à§‡à¦° à¦‡à¦¨à¦­à¦¾à¦‡à¦Ÿ à¦²à¦¿à¦‚à¦• à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:")
            return
        elif step == "GET_URL":
            state["url"] = text.strip()
            await channels_col.update_one(
                {"chat_id": state["chat_id"]},
                {"$set": {"name": state["name"], "url": state["url"]}},
                upsert=True
            )
            del CHANNEL_ADD_STATE[user_id]
            await update.message.reply_text("âœ… à¦«à§‹à¦°à§à¦¸ à¦œà§Ÿà§‡à¦¨ à¦šà§à¦¯à¦¾à¦¨à§‡à¦² à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦¯à§à¦•à§à¦¤ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡!")
            return

    if await is_admin(user_id) and user_id in FORWARD_GROUP_ADD_STATE:
        state = FORWARD_GROUP_ADD_STATE[user_id]
        step = state.get("step")
        if step == "GET_ID":
            gid = text.strip()
            await forward_groups_col.update_one({"group_id": gid}, {"$set": {"group_id": gid}}, upsert=True)
            del FORWARD_GROUP_ADD_STATE[user_id]
            await update.message.reply_text(f"âœ… à¦«à¦°à¦“à§Ÿà¦¾à¦°à§à¦¡ à¦—à§à¦°à§à¦ª `{gid}` à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦¯à§à¦•à§à¦¤ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡!")
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
            await update.message.reply_text("âŒ à¦‡à¦‰à¦œà¦¾à¦° à¦¡à¦¾à¦Ÿà¦¾à¦¬à§‡à¦œà§‡ à¦ªà¦¾à¦“à§Ÿà¦¾ à¦¯à¦¾à§Ÿà¦¨à¦¿à¥¤")
            return

        u_id = target_user["user_id"]
        if action == "balance":
            USER_MANAGE_STATE[user_id] = {"action": "do_balance", "target_id": u_id}
            await update.message.reply_text(f"ðŸ‘¤ User: `{u_id}`\n à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸: `{target_user.get('balance', 0.0)}à§³`\n\nà¦¨à¦¤à§à¦¨ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦…à§à¦¯à¦¾à¦®à¦¾à¦‰à¦¨à§à¦Ÿ à¦¬à¦¾ à¦ªà¦°à¦¿à¦¬à¦°à§à¦¤à¦¨ à¦•à¦°à¦¾à¦° à¦ªà¦°à¦¿à¦®à¦¾à¦£ (à¦¯à§‡à¦®à¦¨ `+50` à¦¬à¦¾ `200`) à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:")
            return
        elif action == "ban":
            current_ban = target_user.get("banned", False)
            new_ban = not current_ban
            await users_col.update_one({"user_id": u_id}, {"$set": {"banned": new_ban}})
            status_str = "à¦¬à§à¦¯à¦¾à¦¨ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡" if new_ban else "à¦†à¦¨à¦¬à§à¦¯à¦¾à¦¨ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡"
            await update.message.reply_text(f"âœ… à¦‡à¦‰à¦œà¦¾à¦° `{u_id}` à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ {status_str}à¥¤")
            return
        elif action == "profile":
            total_nums = await assigned_col.count_documents({"user_id": u_id})
            profile_text = (
                f"ðŸ‘¤ **User Profile Details**\n\n"
                f"ðŸ†” ID: `{u_id}`\n"
                f"ðŸ”— Username: @{target_user.get('username', 'N/A')}\n"
                f"ðŸ’° Balance: `{target_user.get('balance', 0.0):.2f}à§³`\n"
                f"ðŸ“ˆ Total Earned: `{target_user.get('total_earned', 0.0):.2f}à§³`\n"
                f"ðŸ“± Total Used/Assigned Numbers: `{total_nums}`\n"
                f"ðŸš« Banned Status: `{target_user.get('banned', False)}`"
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
            await update.message.reply_text(f"âœ… à¦‡à¦‰à¦œà¦¾à¦° `{target_id}` à¦à¦° à¦¨à¦¤à§à¦¨ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦¸à§‡à¦Ÿ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡: `{val}à§³`")
        except ValueError:
            await update.message.reply_text("âŒ à¦¸à¦ à¦¿à¦• à¦¸à¦‚à¦–à§à¦¯à¦¾ à¦¦à¦¿à¦¨à¥¤")
        return

    if await is_admin(user_id) and user_id in ADMIN_SETTINGS_STATE:
        setting_type = ADMIN_SETTINGS_STATE[user_id].get("setting")
        del ADMIN_SETTINGS_STATE[user_id]
        val = text.strip()

        if setting_type == "edit_otp_link":
            await set_setting("otp_button_link", val)
            await update.message.reply_text(f"âœ… OTP Button Link updated to: `{val}`", parse_mode="Markdown")
            return
        elif setting_type == "set_min_withdraw":
            try:
                num = float(val)
                await set_setting("min_withdraw", num)
                await update.message.reply_text(f"âœ… Min Withdraw updated to: `{num}à§³`")
            except ValueError:
                await update.message.reply_text("âŒ à¦¸à¦ à¦¿à¦• à¦¸à¦‚à¦–à§à¦¯à¦¾ à¦¦à¦¿à¦¨à¥¤")
            return
        elif setting_type == "set_ref_bonus":
            try:
                num = float(val)
                await set_setting("ref_bonus", num)
                await update.message.reply_text(f"âœ… Referral Bonus updated to: `{num}à§³`")
            except ValueError:
                await update.message.reply_text("âŒ à¦¸à¦ à¦¿à¦• à¦¸à¦‚à¦–à§à¦¯à¦¾ à¦¦à¦¿à¦¨à¥¤")
            return
        elif setting_type == "set_otp_rate":
            try:
                num = float(val)
                await set_setting("otp_rate", num)
                await update.message.reply_text(f"âœ… OTP Rate updated to: `{num}à§³`")
            except ValueError:
                await update.message.reply_text("âŒ à¦¸à¦ à¦¿à¦• à¦¸à¦‚à¦–à§à¦¯à¦¾ à¦¦à¦¿à¦¨à¥¤")
            return
        elif setting_type == "set_num_req":
            try:
                num = int(val)
                await set_setting("num_request_count", num)
                await update.message.reply_text(f"âœ… Numbers per request updated to: `{num}`")
            except ValueError:
                await update.message.reply_text("âŒ à¦¸à¦ à¦¿à¦• à¦ªà§‚à¦°à§à¦£à¦¸à¦‚à¦–à§à¦¯à¦¾ à¦¦à¦¿à¦¨à¥¤")
            return
        elif setting_type == "set_cooldown":
            try:
                num = int(val)
                await set_setting("cooldown_timer", num)
                await update.message.reply_text(f"âœ… Cooldown timer updated to: `{num}s`")
            except ValueError:
                await update.message.reply_text("âŒ à¦¸à¦ à¦¿à¦• à¦¸à¦‚à¦–à§à¦¯à¦¾ à¦¦à¦¿à¦¨à¥¤")
            return
        elif setting_type == "add_pay_method":
            methods = await get_setting("payment_methods", ["Bkash", "Nagad", "Binance"])
            if val not in methods:
                methods.append(val)
                await set_setting("payment_methods", methods)
            await update.message.reply_text(f"âœ… Payment method `{val}` added successfully!")
            return
        elif setting_type == "rem_pay_method":
            methods = await get_setting("payment_methods", ["Bkash", "Nagad", "Binance"])
            if val in methods:
                methods.remove(val)
                await set_setting("payment_methods", methods)
            await update.message.reply_text(f"âœ… Payment method `{val}` removed successfully!")
            return

    if await is_admin(user_id) and user_id in ADMIN_BROADCAST_STATE:
        del ADMIN_BROADCAST_STATE[user_id]
        broadcast_text = text.strip()
        
        processing_msg = await update.message.reply_text("â³ à¦¬à§à¦°à¦¡à¦•à¦¾à¦¸à§à¦Ÿ à¦®à§‡à¦¸à§‡à¦œ à¦ªà¦¾à¦ à¦¾à¦¨à§‹ à¦¹à¦šà§à¦›à§‡, à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦…à¦ªà§‡à¦•à§à¦·à¦¾ à¦•à¦°à§à¦¨...")
        
        all_users_cursor = users_col.find({})
        success_count = 0
        async for u in all_users_cursor:
            try:
                await context.bot.send_message(
                    chat_id=u["user_id"],
                    text=f"ðŸ“¢ **Announcement:**\n\n{broadcast_text}",
                    parse_mode="Markdown"
                )
                success_count += 1
            except Exception:
                pass
                
        await processing_msg.edit_text(f"âœ… **à¦¬à§à¦°à¦¡à¦•à¦¾à¦¸à§à¦Ÿ à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦¸à¦®à§à¦ªà¦¨à§à¦¨ à¦¹à§Ÿà§‡à¦›à§‡!**\nðŸ“¬ à¦®à§‹à¦Ÿ à¦¡à§‡à¦²à¦¿à¦­à¦¾à¦°à¦¿ à¦¹à§Ÿà§‡à¦›à§‡: `{success_count}` à¦œà¦¨ à¦‡à¦‰à¦œà¦¾à¦°à§‡à¦° à¦•à¦¾à¦›à§‡à¥¤", parse_mode="Markdown")
        return

    if user_id in USER_WITHDRAW_STATE:
        state = USER_WITHDRAW_STATE[user_id]
        step = state.get("step")
        
        if step == "GET_ACCOUNT":
            state["account"] = text.strip()
            state["step"] = "GET_AMOUNT"
            USER_WITHDRAW_STATE[user_id] = state
            await update.message.reply_text(
                "ðŸ’° à¦†à¦ªà¦¨à¦¿ à¦•à¦¤ à¦Ÿà¦¾à¦•à¦¾ à¦‰à¦‡à¦¥à¦¡à§à¦° à¦•à¦°à¦¤à§‡ à¦šà¦¾à¦¨ à¦¸à§‡à¦‡ à¦…à§à¦¯à¦¾à¦®à¦¾à¦‰à¦¨à§à¦Ÿ à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨ (à¦¯à§‡à¦®à¦¨: `100` à¦¬à¦¾ `500`):",
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
                    await update.message.reply_text("âŒ à¦…à§à¦¯à¦¾à¦®à¦¾à¦‰à¦¨à§à¦Ÿ à¦¸à¦ à¦¿à¦• à¦¨à§Ÿà¥¤ à¦†à¦¬à¦¾à¦° à¦šà§‡à¦·à§à¦Ÿà¦¾ à¦•à¦°à§à¦¨:", reply_markup=back_keyboard())
                    return
                if amount > balance:
                    await update.message.reply_text(f"âŒ à¦†à¦ªà¦¨à¦¾à¦° à¦ªà¦°à§à¦¯à¦¾à¦ªà§à¦¤ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦¨à§‡à¦‡! à¦†à¦ªà¦¨à¦¾à¦° à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸: `{balance:.2f}à§³`", parse_mode="Markdown", reply_markup=back_keyboard())
                    return
                if amount < min_wd:
                    await update.message.reply_text(f"âŒ à¦¸à¦°à§à¦¬à¦¨à¦¿à¦®à§à¦¨ `{min_wd}à§³` à¦‰à¦‡à¦¥à¦¡à§à¦° à¦•à¦°à¦¤à§‡ à¦¹à¦¬à§‡à¥¤ à¦¸à¦ à¦¿à¦• à¦…à§à¦¯à¦¾à¦®à¦¾à¦‰à¦¨à§à¦Ÿ à¦¦à¦¿à¦¨:", reply_markup=back_keyboard())
                    return
                
                state["amount"] = amount
                method = state["method"]
                account = state["account"]
                
                confirm_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("âœ… Confirm", callback_data="wd_user_conf:yes"),
                        InlineKeyboardButton("âŒ Cancel", callback_data="wd_user_conf:no")
                    ]
                ])
                await update.message.reply_text(
                    f"ðŸ“‹ **Withdrawal Summary**\n\n"
                    f"ðŸ’³ Method: `{method}`\n"
                    f"ðŸ“¥ Account: `{account}`\n"
                    f"ðŸ’µ Amount: `{amount:.2f}à§³`\n\n"
                    f"à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦¤à¦¥à§à¦¯à¦—à§à¦²à§‹ à¦¯à¦¾à¦šà¦¾à¦‡ à¦•à¦°à§à¦¨ à¦à¦¬à¦‚ à¦•à¦¨à¦«à¦¾à¦°à§à¦® à¦•à¦°à§à¦¨:",
                    parse_mode="Markdown",
                    reply_markup=confirm_keyboard
                )
                return
            except ValueError:
                await update.message.reply_text("âŒ à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦¸à¦ à¦¿à¦• à¦¸à¦‚à¦–à§à¦¯à¦¾ à¦²à¦¿à¦–à§à¦¨:", reply_markup=back_keyboard())
                return

    if user_id in USER_SEARCH_STATE:
        prefix = text.strip()
        del USER_SEARCH_STATE[user_id]
        
        if not prefix:
            reply_markup = await build_main_menu(user_id)
            await update.message.reply_text("âŒ à¦•à¦¾à¦¨à§à¦Ÿà§à¦°à¦¿ à¦•à§‹à¦¡ à¦¬à¦¾ à¦¸à¦¿à¦°à¦¿à§Ÿà¦¾à¦² à¦–à¦¾à¦²à¦¿ à¦°à¦¾à¦–à¦¾ à¦¯à¦¾à¦¬à§‡ à¦¨à¦¾à¥¤", reply_markup=reply_markup)
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
            
            text_msg = f"ðŸ”Ž **SEARCH RESULTS** (Prefix: `{prefix}`)"
            keyboard = []
            for doc in numbers:
                num = doc['phone_number']
                keyboard.append([InlineKeyboardButton(f"ðŸ“² ðŸ“‹ {num}", copy_text=CopyTextButton(text=num))])
            
            keyboard.append([InlineKeyboardButton("ðŸ”„ Change Number", callback_data=f"search_next:{prefix}")])
            keyboard.append([
                InlineKeyboardButton("ðŸŒ Other Countries", callback_data="get_number_menu"),
                InlineKeyboardButton("ðŸŒ OTP Group", url=OTP_GROUP_URL)
            ])
            await update.message.reply_text(text_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            reply_markup = await build_main_menu(user_id)
            await update.message.reply_text(
                f"âŒ à¦à¦‡ à¦¸à¦¿à¦°à¦¿à§Ÿà¦¾à¦² à¦¬à¦¾ à¦ªà§à¦°à¦«à¦¿à¦•à§à¦¸ (`{prefix}`) à¦¦à¦¿à§Ÿà§‡ à¦•à§‹à¦¨à§‹ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦–à§à¦à¦œà§‡ à¦ªà¦¾à¦“à§Ÿà¦¾ à¦¯à¦¾à¦šà§à¦›à§‡ à¦¨à¦¾!",
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
            await update.message.reply_text(f"âœ… à¦¸à¦¾à¦°à§à¦­à¦¿à¦¸: `{service_name}`\n\nðŸŒ à¦à¦–à¦¨ à¦•à¦¾à¦¨à§à¦Ÿà§à¦°à¦¿à¦° à¦¨à¦¾à¦® à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:", parse_mode="Markdown", reply_markup=back_keyboard())
            return

        elif current_step == "GET_COUNTRY":
            country = text.strip()
            service_name = state_data["service"]
            ADMIN_UPLOAD_STATE[user_id] = {"step": "GET_NUMBERS", "service": service_name, "country": country}
            await update.message.reply_text(f"âœ… à¦¸à¦¾à¦°à§à¦­à¦¿à¦¸: `{service_name}` | à¦•à¦¾à¦¨à§à¦Ÿà§à¦°à¦¿: `{country}`\n\nðŸ“‚ à¦à¦–à¦¨ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦«à¦¾à¦‡à¦² (`.txt`) à¦¸à§‡à¦¨à§à¦¡ à¦•à¦°à§à¦¨ à¦…à¦¥à¦¬à¦¾ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦°à¦—à§à¦²à§‹ à¦ªà§‡à¦¸à§à¦Ÿ à¦•à¦°à§‡ à¦¦à¦¿à¦¨:", parse_mode="Markdown", reply_markup=back_keyboard())
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
                    {"$setOnInsert": {"status": "MEDIUM", "icon": "ðŸŸ¡"}},
                    upsert=True
                )
            del ADMIN_UPLOAD_STATE[user_id]
            
            asyncio.create_task(broadcast_new_numbers_alert(context, service_name, len(numbers_list)))
            
            success_text = (
                f"ðŸŽ‰ **à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦†à¦ªà¦²à§‹à¦¡ à¦¸à¦®à§à¦ªà¦¨à§à¦¨ à¦¹à§Ÿà§‡à¦›à§‡!**\n\n"
                f"ðŸ’¬ à¦¸à¦¾à¦°à§à¦­à¦¿à¦¸ à¦¨à¦¾à¦®: `{service_name}`\n"
                f"ðŸŒ à¦•à¦¾à¦¨à§à¦Ÿà§à¦°à¦¿ à¦¨à¦¾à¦®: `{country}`\n"
                f"ðŸ“± à¦®à§‹à¦Ÿ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦°: `{len(numbers_list)} à¦Ÿà¦¿`\n\n"
                f"âœ… à¦à¦–à¦¨ à¦‡à¦‰à¦œà¦¾à¦°à¦°à¦¾ à¦—à§‡à¦Ÿ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦¥à§‡à¦•à§‡ à¦•à¦¾à¦œ à¦•à¦°à¦¤à§‡ à¦ªà¦¾à¦°à¦¬à§‡à¥¤"
            )
            success_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("ðŸš€ Get Number", callback_data=f"sel_serv:{service_name}")]
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
                    {"$setOnInsert": {"status": "MEDIUM", "icon": "ðŸŸ¡"}},
                    upsert=True
                )
            del ADMIN_UPLOAD_STATE[user_id]
            
            asyncio.create_task(broadcast_new_numbers_alert(context, service_name, len(numbers_list)))
            
            success_text = (
                f"ðŸŽ‰ **à¦«à¦¾à¦‡à¦² à¦¥à§‡à¦•à§‡ à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦†à¦ªà¦²à§‹à¦¡ à¦¸à¦®à§à¦ªà¦¨à§à¦¨ à¦¹à§Ÿà§‡à¦›à§‡!**\n\n"
                f"ðŸ’¬ à¦¸à¦¾à¦°à§à¦­à¦¿à¦¸ à¦¨à¦¾à¦®: `{service_name}`\n"
                f"ðŸŒ à¦•à¦¾à¦¨à§à¦Ÿà§à¦°à¦¿ à¦¨à¦¾à¦®: `{country}`\n"
                f"ðŸ“± à¦®à§‹à¦Ÿ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦°: `{len(numbers_list)} à¦Ÿà¦¿`\n\n"
                f"âœ… à¦à¦–à¦¨ à¦‡à¦‰à¦œà¦¾à¦°à¦°à¦¾ à¦—à§‡à¦Ÿ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦¥à§‡à¦•à§‡ à¦•à¦¾à¦œ à¦•à¦°à¦¤à§‡ à¦ªà¦¾à¦°à¦¬à§‡à¥¤"
            )
            success_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("ðŸš€ Get Number", callback_data=f"sel_serv:{service_name}")]
            ])
            await update.message.reply_text(success_text, parse_mode="Markdown", reply_markup=success_keyboard)
            return

    # à¦¡à¦¾à§Ÿà¦¨à¦¾à¦®à¦¿à¦• à¦¬à¦¾à¦Ÿà¦¨ à¦²à§‡à¦¬à§‡à¦²à§‡à¦° à¦šà§‡à¦•
    btn_get_num = await get_setting("btn_get_number", "ðŸ“± GET NUMBER")
    btn_search_num = await get_setting("btn_search_number", "ðŸ”Ž SEARCH NUMBER")
    btn_traffic = await get_setting("btn_traffic", "ðŸš¦ TRAFFIC")
    btn_refer = await get_setting("btn_refer", "ðŸ‘¥ REFERRAL")
    btn_balance = await get_setting("btn_balance", "ðŸ’° BALANCE")
    btn_support = await get_setting("btn_support", "ðŸ†˜ SUPPORT")

    if text == "/start":
        await start(update, context)
        
    elif text == btn_get_num:
        services = await numbers_col.distinct("service_name", {"status": "Available"})
        if services:
            keyboard = [[InlineKeyboardButton(f"ðŸ“± {s}", callback_data=f"sel_serv:{s}")] for s in services]
            keyboard.append([InlineKeyboardButton("ðŸ”™ Back to Menu", callback_data="back_to_main_menu")])
            await update.message.reply_text("ðŸ“± **Select a Service:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("âš ï¸ à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨à§‡ à¦•à§‹à¦¨à§‹ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦¸à§à¦Ÿà¦• à¦ à¦¨à§‡à¦‡!", parse_mode="Markdown")
        
    elif text == btn_search_num:
        USER_SEARCH_STATE[user_id] = True
        await update.message.reply_text("ðŸ”Ž **Search Number**\n\nà¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦•à¦¾à¦¨à§à¦Ÿà§à¦°à¦¿ à¦•à§‹à¦¡ à¦¬à¦¾ à¦¸à¦¿à¦°à¦¿à§Ÿà¦¾à¦² à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦²à¦¿à¦–à§‡ à¦ªà¦¾à¦ à¦¾à¦¨ (à¦¯à§‡à¦®à¦¨: `223`):", parse_mode="Markdown", reply_markup=back_keyboard())
        
    elif text == btn_traffic:
        traffic_list = await traffic_col.find({}).to_list(length=100)
        if not traffic_list:
            traffic_text = "ðŸ“Š à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨à§‡ à¦•à§‹à¦¨à§‹ à¦²à¦¾à¦‡à¦­ à¦Ÿà§à¦°à¦¾à¦«à¦¿à¦• à¦¡à¦¾à¦Ÿà¦¾ à¦¨à§‡à¦‡à¥¤"
        else:
            traffic_text = "ðŸš¦ **1 HOUR LIVE TRAFFIC**\n\n"
            for item in traffic_list:
                traffic_text += f"ðŸŒ **{item['service']}**\n{item['country']} : {item['status']} {item['icon']}\n\n"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ”„ Refresh", callback_data="refresh_traffic")]])
        await update.message.reply_text(traffic_text, parse_mode="Markdown", reply_markup=keyboard)
        
    elif text == btn_refer:
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        ref_bonus = await get_setting("ref_bonus", 0.01)
        ref_text = (
            f"ðŸ‘¥ **Referral & Earn Program**\n\n"
            f"à¦†à¦ªà¦¨à¦¾à¦° à¦¬à¦¨à§à¦§à§à¦¦à§‡à¦° à¦†à¦®à¦¾à¦¦à§‡à¦° à¦¬à¦Ÿà§‡ à¦‡à¦¨à¦­à¦¾à¦‡à¦Ÿ à¦•à¦°à§à¦¨ à¦à¦¬à¦‚ à¦†à¦•à¦°à§à¦·à¦£à§€à§Ÿ à¦•à§à¦¯à¦¾à¦¶ à¦¬à§‹à¦¨à¦¾à¦¸ à¦†à¦°à§à¦¨ à¦•à¦°à§à¦¨!\n\n"
            f"ðŸŽ **Per Referral Bonus:** `{ref_bonus}à§³`\n\n"
            f"ðŸ”— **à¦†à¦ªà¦¨à¦¾à¦° à¦°à§‡à¦«à¦¾à¦² à¦²à¦¿à¦‚à¦•:**\n`{ref_link}`\n\n"
            f"ðŸ’¡ *à¦²à¦¿à¦‚à¦•à¦Ÿà¦¿ à¦•à¦ªà¦¿ à¦•à¦°à§‡ à¦¶à§‡à§Ÿà¦¾à¦° à¦•à¦°à§à¦¨ à¦à¦¬à¦‚ à¦†à¦ªà¦¨à¦¾à¦° à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦¬à¦¾à§œà¦¾à¦¨!*"
        )
        reply_markup = await build_main_menu(user_id)
        await update.message.reply_text(ref_text, parse_mode="Markdown", reply_markup=reply_markup)
        
    elif text == btn_balance:
        user_data = await users_col.find_one({"user_id": user_id})
        balance = user_data.get("balance", 0.0) if user_data else 0.0
        total_earned = user_data.get("total_earned", 0.0) if user_data else 0.0
        current_otp_rate = await get_setting("otp_rate", 0.60)
        
        balance_text = (
            f"ðŸ‘¤ **User Account Dashboard**\n\n"
            f"ðŸ’° Current Balance : `{balance:.2f}à§³`\n"
            f"ðŸ“ˆ Total Earned : `{total_earned:.2f}à§³`\n"
            f"ðŸ’¸ Withdrawal Status : `Active`\n\n"
            f"âš¡ Earn per OTP: `{current_otp_rate}à§³`"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("ðŸ’¸ Withdraw Balance", callback_data="withdraw_menu")]
        ])
        await update.message.reply_text(balance_text, parse_mode="Markdown", reply_markup=keyboard)
        
    elif text == btn_support:
        support_text = (
            f"ðŸ†˜ **SUPPORT & HELP DESK**\n\n"
            f"à¦¯à§‡à¦•à§‹à¦¨à§‹ à¦ªà§à¦°à§Ÿà§‹à¦œà¦¨à§‡ à¦¸à¦°à¦¾à¦¸à¦°à¦¿ à¦†à¦®à¦¾à¦¦à§‡à¦° à¦…à¦«à¦¿à¦¸à¦¿à§Ÿà¦¾à¦² à¦…à§à¦¯à¦¾à¦¡à¦®à¦¿à¦¨à§‡à¦° à¦¸à¦¾à¦¥à§‡ à¦¯à§‹à¦—à¦¾à¦¯à§‹à¦— à¦•à¦°à§à¦¨ à¦…à¦¥à¦¬à¦¾ à¦šà§à¦¯à¦¾à¦¨à§‡à¦² à¦“ à¦—à§à¦°à§à¦ªà§‡ à¦¯à§à¦•à§à¦¤ à¦¥à¦¾à¦•à§à¦¨ã€‚\n\n"
            f"ðŸ‘‘ **Admin Support:** [Click Here to Message]({SUPPORT_URL})"
        )
        keyboard = [
            [InlineKeyboardButton("ðŸ“¢ Main Channel", url=MAIN_CHANNEL_URL), InlineKeyboardButton("ðŸ“¢ Update Channel", url=UPDATE_CHANNEL_URL)],
            [InlineKeyboardButton("ðŸ’¬ OTP Group", url=OTP_GROUP_URL)]
        ]
        await update.message.reply_text(support_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)
        
    elif text == "ðŸ‘‘ ADMIN PANEL" and await is_admin(user_id):
        text_msg, markup = await get_admin_panel_markup(user_id)
        await update.message.reply_text(text_msg, parse_mode="Markdown", reply_markup=markup)
        
    else:
        if await is_admin(user_id) and text == "":
            pass
        elif not update.message.document and not any(user_id in d for d in [ADMIN_UPLOAD_STATE, USER_SEARCH_STATE, ADMIN_SETTINGS_STATE, USER_WITHDRAW_STATE, ADMIN_BROADCAST_STATE, ADMIN_ADD_STATE, CHANNEL_ADD_STATE, FORWARD_GROUP_ADD_STATE, USER_MANAGE_STATE, RANAX_ADD_STATE, MENU_EDIT_STATE, TEST_STATE]):
            reply_markup = await build_main_menu(user_id)
            await update.message.reply_text("à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦¨à¦¿à¦šà§‡à¦° à¦¬à¦¾à¦Ÿà¦¨à¦—à§à¦²à§‹ à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦•à¦°à§à¦¨ à¦…à¦¥à¦¬à¦¾ /start à¦¦à¦¿à¦¨à¥¤", reply_markup=reply_markup)

async def broadcast_new_numbers_alert(context: ContextTypes.DEFAULT_TYPE, service_name: str, count: int):
    alert_text = (
        f"ðŸš¨ **New Numbers Added!** ðŸš¨\n\n"
        f"ðŸ“± **Service:** `{service_name}`\n"
        f"ðŸ“¦ **Quantity:** `{count} Pcs` Added Successfully!\n\n"
        f"âš¡ à¦¦à§à¦°à§à¦¤ **GET NUMBER** à¦ à¦—à¦¿à§Ÿà§‡ à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦¨à¦¿à§Ÿà§‡ à¦¨à¦¿à¦¨!"
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
    

    print("Zentrix Bot with safe multi-provider panel manager is running successfully...")
    
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

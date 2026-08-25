import os
import logging
import asyncio
import re
import json
import base64
import hashlib
import random
import threading
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from uuid import uuid4
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler
)
import motor.motor_asyncio

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet = None
    InvalidToken = Exception

try:
    import phonenumbers
    from phonenumbers import geocoder
except ImportError:
    phonenumbers = None
    geocoder = None

# --- Logging Setup ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("DATABASE_URL") or os.getenv("MONGO_URL") or "mongodb://localhost:27017"
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
ranax_groups_col = db.ranax_groups

# Provider Dynamic Collections
provider_keys_col = db.provider_keys
provider_services_col = db.provider_services
provider_countries_col = db.provider_countries
provider_ranges_col = db.provider_ranges
provider_orders_col = db.provider_orders
otp_events_col = db.otp_events
provider_settings_col = db.provider_settings

# --- Permanent Links ---
MAIN_CHANNEL_URL = "https://t.me/Zentrix_Officiall"
MAIN_CHANNEL_ID = "@Zentrix_Officiall"
UPDATE_CHANNEL_URL = "https://t.me/Zentrix_Update"
UPDATE_CHANNEL_ID = "@Zentrix_Update"
OTP_GROUP_URL = "https://t.me/+pBpZWtQC4qswODI1"
SUPPORT_URL = "https://t.me/ranaXvou"

# --- In-Memory State Handling ---
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
MENU_EDIT_STATE = {}
TEST_STATE = {}
PROVIDER_STATE = {}

EVENT_LOOP = None
WEBHOOK_SERVER = None

# ================================================================
# AUTHORIZED MULTI-PROVIDER SYSTEM (Voltx & Fast X Included)
# ================================================================
PROVIDERS = {
    "stex": {
        "label": "StexSMS",
        "env": "STEXSMS",
        "base_url_required": True,
        "default_get_path": "/api/getnum",
        "auth_header": "X-API-Key",
        "payload_mode": "service_country_range"
    },
    "voltx": {
        "label": "Voltx",
        "env": "VOLTX",
        "base_url_required": False,
        "default_base_url": "https://voltxsms.com/api",
        "default_get_path": "/get-number",
        "auth_header": "Authorization",
        "payload_mode": "service_country_range"
    },
    "zenex": {
        "label": "Zenex",
        "env": "ZENEX",
        "base_url_required": True,
        "default_get_path": "/api/getnum",
        "auth_header": "X-API-Key",
        "payload_mode": "service_country_range"
    },
    "yesms": {
        "label": "YE SMS",
        "env": "YESMS",
        "base_url_required": True,
        "default_get_path": "/api/getnum",
        "auth_header": "X-API-Key",
        "payload_mode": "service_country_range"
    },
    "fastx": {
        "label": "Fast X OTP",
        "env": "FASTX",
        "base_url_required": True,
        "default_base_url": "https://2eee7.com/@Access/@Bot/2eee7/@public",
        "default_get_path": "/api/getnum",
        "auth_header": "X-API-Key",
        "payload_mode": "range_only",
    },
}

def provider_label(provider: str) -> str:
    return PROVIDERS.get(provider, {}).get("label", provider.upper())

def provider_env_prefix(provider: str) -> str:
    return PROVIDERS.get(provider, {}).get("env", provider.upper())

def country_flag(country: str) -> str:
    country = (country or "UN").upper()
    if len(country) != 2 or not country.isalpha():
        return "🌍"
    return "".join(chr(127397 + ord(c)) for c in country)

def service_icon(service: str) -> str:
    s = str(service).lower().replace("'", "").replace(" ", "")
    icons = {
        "whatsapp": "🟢",
        "facebook": "🔵",
        "telegram": "🔷",
        "instagram": "🟣",
        "google": "🔴",
        "tiktok": "⚫",
        "imo": "🟡",
        "binance": "🔶",
        "bimo": "🟢"
    }
    return icons.get(s, "📱")

def mask_test_phone(phone: str) -> str:
    if len(phone) <= 8:
        return phone
    return f"{phone[:5]}••{phone[-4:]}"

def key_cipher():
    if Fernet is None:
        return None
    secret = os.getenv("API_KEY_ENCRYPTION_SECRET") or BOT_TOKEN or MONGO_URI or "zentrix-default-secret"
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))

def encrypt_api_key(value: str) -> str:
    if not value:
        return ""
    cipher = key_cipher()
    if cipher:
        return "fernet:" + cipher.encrypt(value.encode()).decode()
    return "plain:" + value

def decrypt_api_key(value: str) -> str:
    if not value:
        return ""
    if value.startswith("fernet:"):
        cipher = key_cipher()
        if not cipher:
            return ""
        try:
            return cipher.decrypt(value[7:].encode()).decode()
        except InvalidToken:
            return ""
    if value.startswith("plain:"):
        return value[6:]
    return value

async def get_setting(key, default_val):
    res = await settings_col.find_one({"_id": key})
    return res["value"] if res and "value" in res else default_val

async def set_setting(key, val):
    await settings_col.update_one({"_id": key}, {"$set": {"value": val}}, upsert=True)

async def is_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    return bool(await admins_col.find_one({"user_id": user_id}))

async def is_user_joined(bot, user_id: int) -> bool:
    channels = await channels_col.find({}).to_list(length=100)
    required = [MAIN_CHANNEL_ID, UPDATE_CHANNEL_ID]
    for c in channels:
        ch = c.get("channel_id")
        if ch and ch not in required:
            required.append(ch)
    
    for ch in required:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            pass
    return True

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

async def provider_api_config(provider: str) -> dict:
    prefix = provider_env_prefix(provider)
    meta = PROVIDERS.get(provider, {})
    stored = await provider_settings_col.find_one({"provider": provider}) or {}
    base_url = str(stored.get("base_url") or os.getenv(f"{prefix}_API_BASE_URL", meta.get("default_base_url", ""))).strip().rstrip("/")
    get_path = str(stored.get("get_path") or os.getenv(f"{prefix}_GET_NUMBER_PATH", meta.get("default_get_path", "/get-number"))).strip()
    return {
        "base_url": base_url,
        "get_path": get_path,
        "get_method": str(stored.get("get_method") or os.getenv(f"{prefix}_GET_NUMBER_METHOD", "POST")).upper(),
        "auth_header": os.getenv(f"{prefix}_API_KEY_HEADER", meta.get("auth_header", "X-API-Key")),
        "payload_mode": str(stored.get("payload_mode") or meta.get("payload_mode", "service_country_range")),
    }

def _extract_first(data, keys):
    if isinstance(data, dict):
        for key in keys:
            if key in data and data[key] not in (None, ""):
                return data[key]
        for value in data.values():
            found = _extract_first(value, keys)
            if found not in (None, ""):
                return found
    return None

def _request_number_sync(url, method, payload, api_key, auth_header):
    headers = {"Accept": "application/json"}
    if auth_header.lower() == "authorization" and not api_key.startswith("Bearer "):
        headers[auth_header] = f"Bearer {api_key}"
    else:
        headers[auth_header] = api_key
        headers["Authorization"] = f"Bearer {api_key}"

    body = None
    if method == "GET":
        from urllib.parse import urlencode
        url += ("&" if "?" in url else "?") + urlencode(payload)
    else:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as response:
        raw = response.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else {}

async def request_number_from_provider(provider: str, api_key: str, service: str, country: str, range_value: str):
    cfg = await provider_api_config(provider)
    if not cfg["base_url"]:
        return None, None, f"Provider {provider} API base URL is not configured."
    path = cfg["get_path"].format(service=service, country=country, range=range_value, provider=provider)
    url = cfg["base_url"] + "/" + path.lstrip("/")
    
    payload = {"range": range_value} if cfg.get("payload_mode") == "range_only" else {"service": service, "country": country, "range": range_value}
    
    try:
        data = await asyncio.to_thread(_request_number_sync, url, cfg["get_method"], payload, api_key, cfg["auth_header"])
    except urllib.error.HTTPError as http_err:
        err_msg = http_err.read().decode("utf-8", errors="replace")
        return None, None, f"HTTP {http_err.code}: {err_msg}"
    except Exception as exc:
        return None, None, str(exc)

    if provider == "fastx" and isinstance(data, dict):
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        if meta.get("code") and str(meta.get("code")) != "200":
            msg = _extract_first(data, ["message", "error", "detail"]) or f"Fast X API code {meta.get('code')}"
            return None, str(_extract_first(data, ["order_id", "orderId", "id"]) or ""), str(msg)

    phone_keys = ["full_number", "phone_number", "phoneNumber", "phone", "number"]
    phone = _extract_first(data, phone_keys)
    order_id = _extract_first(data, ["order_id", "orderId", "order", "id", "request_id"])
    
    if phone:
        return str(phone), str(order_id or uuid4()), None
    return None, str(order_id or ""), str(_extract_first(data, ["message", "error", "detail"]) or "No phone number received from provider.")

async def create_provider_order(user_id: int, provider: str, key_doc: dict, service_doc: dict, country_doc: dict, range_doc: dict, phone: str, external_order_id: str):
    order_id = str(external_order_id or uuid4())
    doc = {
        "order_id": order_id,
        "provider": provider,
        "api_key_id": key_doc.get("key_id"),
        "service_id": service_doc.get("service_id"),
        "service_name": service_doc.get("name"),
        "country_id": country_doc.get("country_id"),
        "country": country_doc.get("name"),
        "country_code": country_doc.get("code", "UN"),
        "range_id": range_doc.get("range_id"),
        "range": range_doc.get("range"),
        "phone_number": phone,
        "user_id": user_id,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await provider_orders_col.update_one({"order_id": order_id}, {"$set": doc}, upsert=True)
    return order_id

# --- Webhook & Delivery Handler ---
async def deliver_authorized_otp(bot, provider: str, event: dict):
    event_id = str(event.get("event_id") or event.get("id") or uuid4())
    phone = str(event.get("phone_number") or event.get("phone") or event.get("number") or "").strip()
    external_order_id = str(event.get("order_id") or event.get("orderId") or "").strip()
    otp = str(event.get("otp") or event.get("code") or "").strip()
    sms_text = str(event.get("message") or event.get("sms") or event.get("text") or otp).strip()
    
    query = {"provider": provider, "status": "active"}
    if external_order_id:
        query["order_id"] = external_order_id
    elif phone:
        query["phone_number"] = phone
    else:
        return False, "no_match_key"

    order = await provider_orders_col.find_one(query)
    if not order:
        return False, "unmatched"

    await provider_orders_col.update_one({"_id": order["_id"]}, {"$set": {"status": "completed", "otp_received_at": datetime.now(timezone.utc).isoformat()}})

    otp_text = otp or sms_text
    group_text = (
        "🔔 **NEW OTP RECEIVED**

"
        f"📱 Service: `{order.get('service_name', 'Unknown')}`
"
        f"🌍 Country: {country_flag(order.get('country_code', 'UN'))} `{order.get('country', 'Unknown')}`
"
        f"📞 Number: `{mask_test_phone(order.get('phone_number', phone))}`
"
        f"🔢 OTP: `{otp_text}`
"
        f"🆔 Order: `#{order['order_id']}`
"
        f"⚡ Provider: `{provider_label(provider)}`"
    )

    # Dispatch to OTP Groups
    groups = await forward_groups_col.find({}).to_list(length=50)
    target_ids = [str(g.get("group_id")).strip() for g in groups if g.get("group_id")]
    for target_id in target_ids:
        try:
            await bot.send_message(chat_id=target_id, text=group_text, parse_mode="Markdown")
        except Exception as err:
            logger.error(f"Error sending to group {target_id}: {err}")

    # Direct to User
    try:
        await bot.send_message(
            chat_id=order["user_id"],
            text=f"🔔 **YOUR OTP IS HERE:** `{otp_text}`

For Order `#{order['order_id']}`",
            parse_mode="Markdown"
        )
    except Exception as err:
        logger.error(f"Error sending OTP to user {order['user_id']}: {err}")
    return True, "processed"

# --- Webhook HTTP Listener ---
class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            data = json.loads(body)
        except Exception:
            data = {}
        
        path = self.path.strip('/')
        provider = path.split('/')[-1] if path else "voltx"
        if provider not in PROVIDERS:
            provider = "voltx"

        if EVENT_LOOP and BOT_INSTANCE:
            asyncio.run_coroutine_threadsafe(
                deliver_authorized_otp(BOT_INSTANCE, provider, data),
                EVENT_LOOP
            )
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))

BOT_INSTANCE = None

def start_webhook_server(port=8080):
    server = ThreadingHTTPServer(('0.0.0.0', port), WebhookHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    logger.info(f"Webhook server running on port {port}")

# --- Bot Command & Button Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Save or update user
    existing = await users_col.find_one({"user_id": user.id})
    if not existing:
        ref_id = None
        if context.args and context.args[0].isdigit():
            ref_id = int(context.args[0])
            if ref_id != user.id:
                await users_col.update_one({"user_id": ref_id}, {"$inc": {"balance": 1.0, "referrals": 1}})
        await users_col.insert_one({
            "user_id": user.id,
            "first_name": user.first_name,
            "username": user.username,
            "balance": 0.0,
            "referrals": 0,
            "referred_by": ref_id,
            "joined_at": datetime.now(timezone.utc).isoformat()
        })

    welcome_text = (
        f"🌐 **ZENTRIX NUMBER PANEL**

"
        f"👋 Welcome, **{user.first_name}**!
"
        f"⚡ Get Instant Virtual Numbers for Telegram, WhatsApp, IMO, Google & more.

"
        f"📢 Join our Update Channel: {UPDATE_CHANNEL_URL}
"
        f"👥 Main Group: {MAIN_CHANNEL_URL}"
    )
    reply_markup = await build_main_menu(user.id)
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def handle_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    buttons = [
        [InlineKeyboardButton("🟢 WhatsApp", callback_query_data="select_svc_whatsapp"), InlineKeyboardButton("🔷 Telegram", callback_data="select_svc_telegram")],
        [InlineKeyboardButton("🟣 Instagram", callback_data="select_svc_instagram"), InlineKeyboardButton("🔴 Google", callback_data="select_svc_google")],
        [InlineKeyboardButton("⚫ TikTok", callback_data="select_svc_tiktok"), InlineKeyboardButton("🟡 IMO", callback_data="select_svc_imo")],
        [InlineKeyboardButton("⚡ Choose Provider", callback_data="select_provider_menu")]
    ]
    await update.message.reply_text("📱 **Select Service to Get Number:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await users_col.find_one({"user_id": update.effective_user.id})
    bal = user.get("balance", 0.0) if user else 0.0
    refs = user.get("referrals", 0) if user else 0
    msg = f"💰 **YOUR ACCOUNT BALANCE**

💵 Current Balance: `${bal:.2f}`
👥 Total Referrals: `{refs}`"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    msg = (
        f"👥 **REFERRAL PROGRAM**

"
        f"Share your referral link with friends and earn rewards for every active user!

"
        f"🔗 **Your Referral Link:**
`{ref_link}`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = f"🆘 **SUPPORT & HELP**

For any inquiries, contact our official admin: {SUPPORT_URL}"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_traffic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active_orders = await provider_orders_col.count_documents({"status": "active"})
    completed = await provider_orders_col.count_documents({"status": "completed"})
    msg = f"🚦 **SYSTEM TRAFFIC STATS**

⚡ Active Number Requests: `{active_orders}`
✅ Completed OTPs: `{completed}`"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access.")
        return
    buttons = [
        [InlineKeyboardButton("🔑 Manage Provider Keys", callback_data="admin_keys"), InlineKeyboardButton("⚙️ Provider Config", callback_data="admin_config")],
        [InlineKeyboardButton("📊 User Statistics", callback_data="admin_stats"), InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")]
    ]
    await update.message.reply_text("👑 **ADMIN CONTROL PANEL**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def callback_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("select_svc_"):
        svc = data.replace("select_svc_", "")
        # Dummy range request to test provider flow
        providers_list = ["voltx", "fastx", "stex", "zenex", "yesms"]
        kb = [[InlineKeyboardButton(f"Provider: {provider_label(p)}", callback_data=f"buy_{svc}_{p}")] for p in providers_list]
        await query.edit_message_text(f"📱 Service Selected: **{svc.upper()}**
Choose Provider:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    
    elif data.startswith("buy_"):
        parts = data.split("_")
        svc = parts[1]
        p_name = parts[2]
        user_id = query.from_user.id
        
        # Simulated or database key retrieval
        key_doc = await provider_keys_col.find_one({"provider": p_name, "status": "active"})
        api_key = decrypt_api_key(key_doc.get("api_key")) if key_doc else os.getenv(f"{provider_env_prefix(p_name)}_API_KEY", "DEMO_KEY")
        
        phone, order_id, err = await request_number_from_provider(
            provider=p_name,
            api_key=api_key,
            service=svc,
            country="US",
            range_value="1"
        )
        
        if err:
            await query.edit_message_text(f"❌ Failed to get number from {provider_label(p_name)}: {err}")
        else:
            await create_provider_order(user_id, p_name, key_doc or {}, {"name": svc}, {"name": "USA", "code": "US"}, {"range": "1"}, phone, order_id)
            await query.edit_message_text(
                f"✅ **NUMBER PURCHASED!**

"
                f"📱 Service: `{svc.upper()}`
"
                f"📞 Number: `{phone}`
"
                f"🆔 Order ID: `{order_id}`
"
                f"⚡ Provider: `{provider_label(p_name)}`

"
                f"Waiting for OTP...",
                parse_mode="Markdown"
            )

async def message_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    btn_get_num = await get_setting("btn_get_number", "📱 GET NUMBER")
    btn_search_num = await get_setting("btn_search_number", "🔎 SEARCH NUMBER")
    btn_traffic = await get_setting("btn_traffic", "🚦 TRAFFIC")
    btn_refer = await get_setting("btn_refer", "👥 REFERRAL")
    btn_balance = await get_setting("btn_balance", "💰 BALANCE")
    btn_support = await get_setting("btn_support", "🆘 SUPPORT")

    if text in [btn_get_num, "/getnumber"]:
        await handle_get_number(update, context)
    elif text in [btn_balance, "/balance"]:
        await handle_balance(update, context)
    elif text in [btn_refer, "/referral"]:
        await handle_referral(update, context)
    elif text in [btn_support, "/support"]:
        await handle_support(update, context)
    elif text in [btn_traffic, "/traffic"]:
        await handle_traffic(update, context)
    elif text == "👑 ADMIN PANEL":
        await handle_admin_panel(update, context)
    else:
        await update.message.reply_text("❓ Unknown command. Please select an option from the menu.")

def main():
    global EVENT_LOOP, BOT_INSTANCE
    if not BOT_TOKEN:
        print("CRITICAL ERROR: BOT_TOKEN is missing in Environment Variables!")
        return

    EVENT_LOOP = asyncio.get_event_loop()
    app = Application.builder().token(BOT_TOKEN).build()
    BOT_INSTANCE = app.bot

    # Webhook Server Background Start
    port = int(os.getenv("PORT", "8080"))
    start_webhook_server(port)

    # Command Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getnumber", handle_get_number))
    app.add_handler(CommandHandler("balance", handle_balance))
    app.add_handler(CommandHandler("traffic", handle_traffic))
    app.add_handler(CommandHandler("admin", handle_admin_panel))

    # Callback & Message Dispatchers
    app.add_handler(CallbackQueryHandler(callback_dispatcher))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_dispatcher))

    print(f"✅ Zentrix Telegram Bot with Voltx & Fast X OTP loaded successfully! Running polling...")
    app.run_polling()

if __name__ == "__main__":
    main()

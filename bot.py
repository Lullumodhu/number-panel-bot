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
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import motor.motor_asyncio

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet = None
    InvalidToken = Exception

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
ranax_groups_col = db.ranax_groups

# --- Dynamic Authorized Provider System ---
provider_keys_col = db.provider_keys
provider_services_col = db.provider_services
provider_countries_col = db.provider_countries
provider_ranges_col = db.provider_ranges
provider_orders_col = db.provider_orders
otp_events_col = db.otp_events
provider_settings_col = db.provider_settings

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
MENU_EDIT_STATE = {}
TEST_STATE = {}
PROVIDER_STATE = {}
EVENT_LOOP = None
WEBHOOK_SERVER = None

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

# --- Reply Keyboards ---
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

# --- Test OTP Helpers (Without TEST Tag in Feed Display) ---
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
        return "🌍"
    return "".join(chr(127397 + ord(c)) for c in country)

def service_icon(service: str) -> str:
    s = service.lower().replace("'", "").replace(" ", "")
    icons = {
        "whatsapp": "🟢", "facebook": "🔵", "telegram": "🔷",
        "instagram": "🟣", "discord": "🟪", "imo": "🔵",
        "google": "🔴", "tiktok": "⚫", "twitter": "🐦",
    }
    return icons.get(s, "📱")

def mask_test_phone(phone: str) -> str:
    if len(phone) <= 8:
        return phone
    return f"{phone[:5]}••{phone[-4:]}"

async def build_test_otp_keyboard(context: ContextTypes.DEFAULT_TYPE, otp: str):
    channel_url = await get_setting("otp_button_link", MAIN_CHANNEL_URL)
    if not isinstance(channel_url, str) or not channel_url.startswith(("http://", "https://", "tg://")):
        channel_url = MAIN_CHANNEL_URL

    me = await context.bot.get_me()
    bot_username = me.username or ""
    get_number_url = f"https://t.me/{bot_username}?start=get_number" if bot_username else MAIN_CHANNEL_URL

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔔 Channel", url=channel_url),
            InlineKeyboardButton(f"🛡️ 📋 {otp}", copy_text=CopyTextButton(text=otp)),
        ],
        [InlineKeyboardButton("📞 Get Number ↗", url=get_number_url)]
    ])

def build_test_otp_text(service: str, phone: str, otp: str, language: str, country: str) -> str:
    # 'TEST' লেখাটি সম্পূর্ণ বাদ দিয়ে ফরম্যাট করা হয়েছে যাতে সাধারণ ব্যবহারকারীদের চোখে না পড়ে।
    return (
        f"{country_flag(country)} **{country}** | "
        f"{service_icon(service)} **{service}** `{mask_test_phone(phone)}` | "
        f"🔊 **{language}**\n\n"
        f"🛡️ **OTP:** `{otp}`"
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


# ================================================================
# AUTHORIZED MULTI-PROVIDER MANAGEMENT
# ================================================================
PROVIDERS = {
    # Providers whose documented get-number endpoint expects only {"range": "..."}.
    "stex": {
        "label": "StexSMS", "env": "STEXSMS", "base_url_required": True,
        "default_get_path": "/api/getnum", "request_body_mode": "range_only",
        "default_otp_path": "/api/success-otp-info",
    },
    # Voltx keeps the existing API-key-only behavior and payload format.
    "voltx": {
        "label": "Voltx", "env": "VOLTX", "base_url_required": False,
        "default_get_path": "/get-number", "request_body_mode": "full",
        "default_otp_path": "",
    },
    "zenex": {
        "label": "Zenex", "env": "ZENEX", "base_url_required": True,
        "default_get_path": "/api/getnum", "request_body_mode": "range_only",
        "default_otp_path": "/api/success-otp-info",
    },
    "yesms": {
        "label": "YE SMS", "env": "YESMS", "base_url_required": True,
        "default_get_path": "/api/getnum", "request_body_mode": "range_only",
        "default_otp_path": "/api/success-otp-info",
    },
}


def provider_label(provider: str) -> str:
    return PROVIDERS.get(provider, {}).get("label", provider.upper())


def provider_env_prefix(provider: str) -> str:
    return PROVIDERS.get(provider, {}).get("env", provider.upper())


def normalize_name(value: str, max_len: int = 64) -> str:
    value = re.sub(r"\s+", " ", (value or "").strip())
    return value[:max_len]


def normalize_service(value: str) -> str:
    return normalize_name(value).upper()


def normalize_country(value: str) -> str:
    return normalize_name(value).title()


def normalize_range(value: str) -> str:
    value = re.sub(r"[^0-9+*#A-Za-z_-]", "", (value or "").strip())
    return value[:32]


def service_emoji(service: str) -> str:
    s = (service or "").lower().replace(" ", "").replace("'", "")
    icons = {
        "facebook": "📘", "whatsapp": "💬", "telegram": "✈️",
        "instagram": "📸", "google": "🔎", "youtube": "▶️",
        "tiktok": "🎵", "twitter": "🐦", "x": "✖️", "discord": "🟣",
        "imo": "💙", "snapchat": "👻", "microsoft": "🪟", "outlook": "📧",
        "apple": "🍎", "uber": "🚕", "airbnb": "🏠", "linkedin": "💼",
    }
    return icons.get(s, "🔹")


def country_code_from_name(name: str) -> str:
    known = {
        "guinea": "GN", "bangladesh": "BD", "india": "IN", "united states": "US",
        "united kingdom": "GB", "malaysia": "MY", "indonesia": "ID", "singapore": "SG",
        "thailand": "TH", "vietnam": "VN", "philippines": "PH", "pakistan": "PK",
        "afghanistan": "AF", "sri lanka": "LK", "myanmar": "MM", "japan": "JP",
        "south korea": "KR", "china": "CN", "russia": "RU", "turkey": "TR",
        "france": "FR", "germany": "DE", "italy": "IT", "spain": "ES",
        "netherlands": "NL", "belgium": "BE", "switzerland": "CH", "austria": "AT",
        "denmark": "DK", "sweden": "SE", "norway": "NO", "poland": "PL",
        "greece": "GR", "portugal": "PT", "ireland": "IE", "finland": "FI",
        "ukraine": "UA", "czech republic": "CZ", "hungary": "HU", "romania": "RO",
        "israel": "IL", "united arab emirates": "AE", "saudi arabia": "SA",
        "qatar": "QA", "bahrain": "BH", "kuwait": "KW", "oman": "OM",
        "yemen": "YE", "jordan": "JO", "lebanon": "LB", "syria": "SY",
        "iraq": "IQ", "egypt": "EG", "morocco": "MA", "algeria": "DZ",
        "tunisia": "TN", "libya": "LY", "nigeria": "NG", "kenya": "KE",
        "tanzania": "TZ", "uganda": "UG", "south africa": "ZA", "australia": "AU",
        "new zealand": "NZ",
    }
    return known.get((name or "").strip().lower(), "UN")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def key_cipher():
    if Fernet is None:
        return None
    secret = os.getenv("API_KEY_ENCRYPTION_SECRET") or BOT_TOKEN or MONGO_URI or "zentrix-default-secret"
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_api_key(value: str) -> str:
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


def mask_secret(value: str) -> str:
    value = value or ""
    if len(value) <= 8:
        return "•" * len(value)
    return value[:4] + "••••" + value[-4:]


async def provider_key_count(provider: str) -> int:
    return await provider_keys_col.count_documents({"provider": provider})


async def provider_configured_services(provider: str):
    return await provider_services_col.find({"provider": provider}).sort("name", 1).to_list(length=200)


async def provider_api_config(provider: str) -> dict:
    prefix = provider_env_prefix(provider)
    meta = PROVIDERS.get(provider, {})
    stored = await provider_settings_col.find_one({"provider": provider}) or {}
    stored_base_url = str(stored.get("base_url") or "").strip().rstrip("/")
    env_base_url = os.getenv(f"{prefix}_API_BASE_URL", "").strip().rstrip("/")
    base_url = stored_base_url or env_base_url
    get_path = str(stored.get("get_path") or os.getenv(
        f"{prefix}_GET_NUMBER_PATH", meta.get("default_get_path", "/get-number")
    )).strip()

    stored_otp_url = str(stored.get("otp_api_url") or "").strip()
    env_otp_url = os.getenv(f"{prefix}_OTP_API_URL", "").strip()
    otp_api_url = stored_otp_url or env_otp_url
    if not otp_api_url and base_url and meta.get("default_otp_path"):
        otp_api_url = base_url + "/" + str(meta["default_otp_path"]).lstrip("/")

    return {
        "base_url": base_url,
        "get_path": get_path,
        "get_method": str(stored.get("get_method") or os.getenv(f"{prefix}_GET_NUMBER_METHOD", "POST")).upper(),
        "request_body_mode": str(stored.get("request_body_mode") or meta.get("request_body_mode", "full")).lower(),
        "validate_path": os.getenv(f"{prefix}_VALIDATE_KEY_PATH", ""),
        "otp_api_url": otp_api_url,
        "otp_method": str(stored.get("otp_method") or os.getenv(f"{prefix}_OTP_METHOD", "GET")).upper(),
        "otp_poll_interval": max(2, int(stored.get("otp_poll_interval") or os.getenv("OTP_POLL_INTERVAL", "4"))),
        "webhook_secret": os.getenv(f"{prefix}_WEBHOOK_SECRET", ""),
        "auth_header": os.getenv(f"{prefix}_API_KEY_HEADER", "X-API-Key"),
        "webhook_port": int(os.getenv("WEBHOOK_PORT", "8080")),
        "base_url_required": bool(meta.get("base_url_required", True)),
    }


def provider_requires_base_url(provider: str) -> bool:
    return bool(PROVIDERS.get(provider, {}).get("base_url_required", True))


async def validate_provider_key(provider: str, api_key: str) -> bool:
    """Validate only when a documented validation endpoint is configured.
    Without one, a non-empty key is accepted and stored; this avoids inventing
    undocumented provider API calls.
    """
    if not api_key or len(api_key) > 512:
        return False
    cfg = await provider_api_config(provider)
    if not cfg["validate_path"] or not cfg["base_url"]:
        return True
    url = cfg["base_url"] + "/" + cfg["validate_path"].lstrip("/")
    return await asyncio.to_thread(_provider_http_check, url, api_key, cfg["auth_header"])


def _provider_http_check(url: str, api_key: str, auth_header: str) -> bool:
    try:
        req = urllib.request.Request(url, method="GET", headers={auth_header: api_key, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def _extract_first(data, keys):
    if isinstance(data, dict):
        for key in keys:
            if key in data and data[key] not in (None, ""):
                return data[key]
        for value in data.values():
            found = _extract_first(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(data, list):
        for value in data:
            found = _extract_first(value, keys)
            if found not in (None, ""):
                return found
    return None


def _request_number_sync(url, method, payload, api_key, auth_header):
    headers = {"Accept": "application/json", auth_header: api_key}
    if auth_header.lower() != "authorization":
        headers.setdefault("Authorization", f"Bearer {api_key}")
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
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}


async def request_number_from_provider(provider: str, api_key: str, service: str, country: str, range_value: str):
    cfg = await provider_api_config(provider)
    if provider_requires_base_url(provider) and not cfg["base_url"]:
        return None, None, "Provider API Base URL is not configured."

    # A provider can be API-key-only (Voltx) or Base-URL + API-key.
    if cfg["base_url"]:
        path = cfg["get_path"].format(
            service=service, country=country, range=range_value, provider=provider
        )
        url = cfg["base_url"] + "/" + path.lstrip("/")
    else:
        # For API-key-only providers the configured path may itself be a full URL.
        url = cfg["get_path"]
        if not re.match(r"^https?://", url):
            return None, None, "Provider API endpoint is not configured."

    if cfg["request_body_mode"] == "range_only":
        # Zenex-style endpoint shown in the supplied API documentation:
        # POST /api/getnum with exactly {"range": "26134XXX"}.
        payload = {"range": range_value}
    else:
        payload = {"service": service, "country": country, "range": range_value}

    try:
        data = await asyncio.to_thread(
            _request_number_sync, url, cfg["get_method"], payload, api_key, cfg["auth_header"]
        )
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        detail = f"HTTP {exc.code}" + (f": {body[:300]}" if body else "")
        return None, None, detail
    except Exception as exc:
        return None, None, str(exc)

    phone = _extract_first(data, [
        "full_number", "phone_number", "phoneNumber", "phone",
        "number", "mobile", "national_number", "no_plus_number"
    ])
    order_id = _extract_first(data, ["order_id", "orderId", "order", "id", "request_id", "requestId"])
    if phone:
        return str(phone), str(order_id or uuid4()), None

    meta_code = _extract_first(data, ["code", "status_code"])
    message = _extract_first(data, ["message", "error", "detail"])
    detail = "Provider response did not contain a phone number."
    if meta_code not in (None, ""):
        detail += f" code={meta_code}"
    if message not in (None, ""):
        detail += f" | {message}"
    return None, str(order_id or ""), detail


async def create_provider_order(user_id: int, provider: str, key_doc: dict, service_doc: dict,
                                country_doc: dict, range_doc: dict, phone: str, external_order_id: str):
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
        "created_at": now_iso(),
        "last_otp_event_id": None,
    }
    await provider_orders_col.update_one({"order_id": order_id}, {"$set": doc}, upsert=True)
    return order_id


async def provider_targets():
    groups = await forward_groups_col.find({}).to_list(length=50)
    ids = [str(g.get("group_id")).strip() for g in groups if g.get("group_id")]
    fallback = os.getenv("OTP_GROUP_ID", "").strip()
    return ids or ([fallback] if fallback else [])


async def deliver_authorized_otp(bot, provider: str, event: dict):
    """Deliver only provider-supplied events matched to an active order."""
    event_id = str(event.get("event_id") or event.get("id") or uuid4())
    phone = str(event.get("phone_number") or event.get("phone") or event.get("number") or "").strip()
    external_order_id = str(event.get("order_id") or event.get("orderId") or "").strip()
    otp = str(event.get("otp") or event.get("code") or "").strip()
    sms_text = str(event.get("message") or event.get("sms") or event.get("text") or otp).strip()
    if not otp and not sms_text:
        return False, "missing_otp"

    existing = await otp_events_col.find_one({"provider": provider, "event_id": event_id})
    if existing:
        return False, "duplicate"

    query = {"provider": provider, "status": "active"}
    if external_order_id:
        query["order_id"] = external_order_id
    elif phone:
        query["phone_number"] = phone
    else:
        return False, "no_match_key"

    order = await provider_orders_col.find_one(query)
    if not order and phone and external_order_id:
        order = await provider_orders_col.find_one({"provider": provider, "status": "active", "phone_number": phone})
    if not order:
        await otp_events_col.insert_one({"provider": provider, "event_id": event_id, "status": "unmatched", "created_at": now_iso()})
        return False, "unmatched"

    await otp_events_col.insert_one({
        "provider": provider, "event_id": event_id, "order_id": order["order_id"],
        "user_id": order["user_id"], "phone_number": order.get("phone_number"),
        "created_at": now_iso(), "status": "processed",
    })

    await provider_orders_col.update_one(
        {"_id": order["_id"]},
        {"$set": {"status": "completed", "last_otp_event_id": event_id, "otp_received_at": now_iso()}}
    )

    service = order.get("service_name", "Unknown")
    country = order.get("country", "Unknown")
    country_code = order.get("country_code", "UN")
    masked_phone = mask_test_phone(order.get("phone_number", phone))
    provider_name = provider_label(provider)
    otp_text = otp or sms_text
    group_text = (
        "🔔 **NEW OTP RECEIVED**\n\n"
        f"📱 Service: `{service}`\n"
        f"🌍 Country: {country_flag(country_code)} `{country}`\n"
        f"📞 Number: `{masked_phone}`\n"
        f"🔢 OTP: `{otp_text}`\n"
        f"🆔 Order: `#{order['order_id']}`\n"
        f"⚡ Provider: `{provider_name}`"
    )
    user_text = (
        "🔔 **OTP RECEIVED**\n\n"
        f"📱 Service: `{service}`\n"
        f"🌍 Country: {country_flag(country_code)} `{country}`\n"
        f"🔢 OTP: `{otp_text}`\n"
        f"🆔 Order: `#{order['order_id']}`\n"
        f"⚡ Provider: `{provider_name}`"
    )

    for target_id in await provider_targets():
        try:
            await bot.send_message(chat_id=target_id, text=group_text, parse_mode="Markdown")
        except Exception:
            pass
    try:
        await bot.send_message(chat_id=order["user_id"], text=user_text, parse_mode="Markdown")
    except Exception:
        pass
    return True, "processed"


async def provider_panel_markup(provider: str):
    label = provider_label(provider)
    keys = await provider_key_count(provider)
    services = await provider_services_col.count_documents({"provider": provider})
    countries = await provider_countries_col.count_documents({"provider": provider})
    ranges = await provider_ranges_col.count_documents({"provider": provider})
    cfg = await provider_api_config(provider)
    base_status = "Configured" if cfg["base_url"] else "Not configured"
    text = (
        f"⚡ **{label} Control Panel**\n\n"
        f"🔑 Total API Keys: `{keys}`\n"
        f"📁 Services: `{services}`  •  🌍 Countries: `{countries}`  •  📍 Ranges: `{ranges}`\n"
    )
    if provider_requires_base_url(provider):
        text += f"🌐 Base URL: `{base_status}`\n"
    else:
        text += "🔗 Connection: `API Key only`\n"
    otp_status = "Configured" if cfg.get("otp_api_url") else "Not configured"
    text += f"📩 OTP API: `{otp_status}`\n\n"
    text += f"Manage your {label} API keys, services, countries, ranges and OTP API below."
    keyboard = [
        [InlineKeyboardButton(f"🟢 ➕ Add {label} Key", callback_data=f"p_add_key:{provider}")],
        [InlineKeyboardButton("🔴 🗑 View / Delete Keys", callback_data=f"p_keys:{provider}")],
        [InlineKeyboardButton(f"🟡 ⚙️ Manage {label} Services", callback_data=f"p_services:{provider}")],
    ]
    if provider_requires_base_url(provider):
        keyboard.append([InlineKeyboardButton("🔵 🌐 Set Base URL", callback_data=f"p_baseurl:{provider}")])
    keyboard.append([InlineKeyboardButton("🟣 📩 Set OTP API", callback_data=f"p_otpapi:{provider}")])
    keyboard.extend([
        [InlineKeyboardButton("🔵 🔎 Search Country", callback_data=f"p_search:{provider}")],
        [InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")],
    ])
    return text, InlineKeyboardMarkup(keyboard)

async def provider_services_markup(provider: str):
    services = await provider_configured_services(provider)
    text = f"⚡ **{provider_label(provider)} Services Manager**\n\nManage your API-based dynamic services below:"
    keyboard = []
    for svc in services:
        sid = svc["service_id"]
        keyboard.append([InlineKeyboardButton(f"{svc.get('emoji', service_emoji(svc['name']))} {svc['name']}", callback_data=f"p_service:{provider}:{sid}")])
    keyboard.append([InlineKeyboardButton("➕ Add New Service", callback_data=f"p_add_service:{provider}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"p_control:{provider}")])
    return text, InlineKeyboardMarkup(keyboard)


async def provider_service_screen(provider: str, service_id: str):
    svc = await provider_services_col.find_one({"provider": provider, "service_id": service_id})
    if not svc:
        return "❌ Service not found.", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"p_services:{provider}")]])
    countries = await provider_countries_col.find({"provider": provider, "service_id": service_id}).sort("name", 1).to_list(length=200)
    text = f"📁 **Service: {svc['name']}**\n\nManage countries for this service:"
    keyboard = []
    for country in countries:
        keyboard.append([InlineKeyboardButton(
            f"{country.get('flag', country_flag(country.get('code', 'UN')))} {country['name']}",
            callback_data=f"p_country:{provider}:{service_id}:{country['country_id']}"
        )])
    keyboard.append([InlineKeyboardButton("➕ Add Country", callback_data=f"p_add_country:{provider}:{service_id}")])
    keyboard.append([InlineKeyboardButton("🗑 Delete Service", callback_data=f"p_del_service:{provider}:{service_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"p_services:{provider}")])
    return text, InlineKeyboardMarkup(keyboard)


async def provider_country_screen(provider: str, service_id: str, country_id: str):
    svc = await provider_services_col.find_one({"provider": provider, "service_id": service_id})
    country = await provider_countries_col.find_one({"provider": provider, "country_id": country_id})
    if not svc or not country:
        return "❌ Country configuration not found.", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"p_services:{provider}")]])
    ranges = await provider_ranges_col.find({"provider": provider, "service_id": service_id, "country_id": country_id}).sort("range", 1).to_list(length=500)
    text = (
        f"📍 **Service: {svc['name']} | Country: {country['name']}**\n\n"
        f"Total Ranges: `{len(ranges)}`\n\n"
        "Click on a range below to delete it, or add a new one."
    )
    keyboard = []
    for r in ranges:
        keyboard.append([InlineKeyboardButton(f"📍 {r['range']}", callback_data=f"p_del_range:{provider}:{r['range_id']}")])
    keyboard.append([InlineKeyboardButton("➕ Add Range", callback_data=f"p_add_range:{provider}:{service_id}:{country_id}")])
    keyboard.append([InlineKeyboardButton("🗑 Delete Entire Country", callback_data=f"p_del_country:{provider}:{service_id}:{country_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"p_service:{provider}:{service_id}")])
    return text, InlineKeyboardMarkup(keyboard)


def _normalize_otp_events(payload):
    """Return a flat list from common success-OTP API response shapes."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, dict):
        otps = data.get("otps")
        if isinstance(otps, list):
            return otps
        if isinstance(otps, dict):
            return [otps]
        if any(k in data for k in ("otp", "code", "number", "phone", "phone_number")):
            return [data]
    otps = payload.get("otps")
    if isinstance(otps, list):
        return otps
    if isinstance(otps, dict):
        return [otps]
    if any(k in payload for k in ("otp", "code", "number", "phone", "phone_number")):
        return [payload]
    return []


def _otp_event_fingerprint(provider: str, event: dict) -> str:
    raw = "|".join(str(event.get(k, "")) for k in (
        "id", "event_id", "number", "phone", "phone_number", "otp", "code", "sms", "message", "time"
    ))
    return hashlib.sha256(f"{provider}|{raw}".encode("utf-8")).hexdigest()


def _poll_otp_api_sync(url: str, method: str, api_key: str, auth_header: str):
    headers = {"Accept": "application/json", auth_header: api_key}
    if auth_header.lower() != "authorization":
        headers.setdefault("Authorization", f"Bearer {api_key}")
    req = urllib.request.Request(url, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read().decode("utf-8", errors="replace")
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}


async def poll_provider_otp_apis(bot):
    """Poll configured provider OTP APIs and forward only OTPs matching active orders."""
    while True:
        intervals = []
        try:
            for provider in PROVIDERS:
                cfg = await provider_api_config(provider)
                intervals.append(cfg.get("otp_poll_interval", 4))
                otp_url = cfg.get("otp_api_url")
                if not otp_url:
                    continue
                keys = await provider_keys_col.find({"provider": provider}).limit(1).to_list(length=1)
                if not keys:
                    continue
                api_key = decrypt_api_key(keys[0].get("encrypted_key", ""))
                if not api_key:
                    continue
                try:
                    payload = await asyncio.to_thread(
                        _poll_otp_api_sync, otp_url, cfg.get("otp_method", "GET"),
                        api_key, cfg.get("auth_header", "X-API-Key")
                    )
                except Exception as exc:
                    logging.warning("OTP API poll failed for %s: %s", provider, exc)
                    continue

                for event in _normalize_otp_events(payload):
                    if not isinstance(event, dict):
                        continue
                    event = dict(event)
                    if not event.get("event_id") and not event.get("id"):
                        event["event_id"] = _otp_event_fingerprint(provider, event)
                    await deliver_authorized_otp(bot, provider, event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Provider OTP polling loop error")

        sleep_for = min(intervals) if intervals else 4
        await asyncio.sleep(max(2, sleep_for))


class ProviderWebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_POST(self):
        global EVENT_LOOP
        match = re.fullmatch(r"/webhook/(stex|voltx|zenex|yesms)", self.path.split("?", 1)[0])
        if not match or EVENT_LOOP is None:
            self.send_response(404)
            self.end_headers()
            return
        provider = match.group(1)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
            secret = self.headers.get("X-Webhook-Secret", "")
            expected = os.getenv(f"{provider_env_prefix(provider)}_WEBHOOK_SECRET", "")
            body_secret = str(payload.get("secret", "")) if isinstance(payload, dict) else ""
            if not expected:
                self.send_response(503)
                self.end_headers()
                return
            if secret != expected and body_secret != expected:
                self.send_response(401)
                self.end_headers()
                return
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            future = asyncio.run_coroutine_threadsafe(_handle_webhook_payload(provider, payload), EVENT_LOOP)
            future.result(timeout=20)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception:
            self.send_response(400)
            self.end_headers()


async def _handle_webhook_payload(provider: str, payload: dict):
    # Some providers wrap the event in data/event/result.
    event = payload.get("event") if isinstance(payload.get("event"), dict) else payload
    if isinstance(event.get("data"), dict):
        merged = dict(event)
        merged.update(event["data"])
        event = merged
    bot = _WEBHOOK_BOT
    if bot is not None:
        await deliver_authorized_otp(bot, provider, event)


_WEBHOOK_BOT = None


def start_provider_webhook_server(bot):
    global EVENT_LOOP, WEBHOOK_SERVER, _WEBHOOK_BOT
    EVENT_LOOP = asyncio.get_running_loop()
    _WEBHOOK_BOT = bot
    port = int(os.getenv("WEBHOOK_PORT", "8080"))
    try:
        WEBHOOK_SERVER = ThreadingHTTPServer(("0.0.0.0", port), ProviderWebhookHandler)
        thread = threading.Thread(target=WEBHOOK_SERVER.serve_forever, daemon=True)
        thread.start()
        logging.info("Authorized provider webhook server listening on port %s", port)
    except Exception as exc:
        logging.warning("Provider webhook server not started: %s", exc)


def stop_provider_webhook_server():
    global WEBHOOK_SERVER
    if WEBHOOK_SERVER:
        try:
            WEBHOOK_SERVER.shutdown()
            WEBHOOK_SERVER.server_close()
        except Exception:
            pass
        WEBHOOK_SERVER = None

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    for state_dict in [ADMIN_UPLOAD_STATE, USER_SEARCH_STATE, ADMIN_SETTINGS_STATE, USER_WITHDRAW_STATE, ADMIN_BROADCAST_STATE, ADMIN_ADD_STATE, CHANNEL_ADD_STATE, FORWARD_GROUP_ADD_STATE, USER_MANAGE_STATE, RANAX_ADD_STATE, MENU_EDIT_STATE, TEST_STATE, PROVIDER_STATE]:
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

    # Any provider navigation cancels a pending provider text-input state.
    # The specific add/search callbacks below create a fresh state again.
    if query.data.startswith("p_") or query.data in {
        "stex_control", "voltx_control", "zenex_control", "ye_control"
    }:
        PROVIDER_STATE.pop(user_id, None)

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
        sys_text = (
            "⚙️ **System Control Hub**\n\n"
            "Manage each authorized SMS provider independently.\n"
            "Provider keys, services, countries and ranges are kept separate."
        )
        sys_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ StexSMS", callback_data="p_control:stex"), InlineKeyboardButton("💠 Voltx", callback_data="p_control:voltx")],
            [InlineKeyboardButton("🔷 Zenex", callback_data="p_control:zenex"), InlineKeyboardButton("🟢 YE SMS", callback_data="p_control:yesms")],
            [InlineKeyboardButton("🛡️ Provider OTP", callback_data="provider_otp_info"), InlineKeyboardButton("✨ Premium UI", callback_data="premium_emoji")],
            [InlineKeyboardButton("Menu Design", callback_data="menu_design"), InlineKeyboardButton("Test", callback_data="test")],
            [InlineKeyboardButton("👑 Admin Mgmt", callback_data="adm_mgmt_menu"), InlineKeyboardButton("⚙️ Force Join", callback_data="adm_fj_menu")],
            [InlineKeyboardButton("👥 User Mgmt", callback_data="adm_usermgmt_menu"), InlineKeyboardButton("💬 OTP Groups", callback_data="adm_otpgroup_menu")],
            [InlineKeyboardButton("🚀 X-Rony Panel", callback_data="adm_xrony_menu")],
            [InlineKeyboardButton("🔙 Back", callback_data="adm_back")]
        ])
        await query.message.edit_text(sys_text, parse_mode="Markdown", reply_markup=sys_keyboard)

    elif query.data == "premium_emoji" and await is_admin(user_id):
        await query.answer()
        await query.message.edit_text(
            "✨ **Premium UI Emoji**\n\n"
            "The provider panels use polished Unicode emoji for a premium look.\n"
            "Telegram Premium custom/animated emoji require the actual custom-emoji IDs; they cannot be invented safely in source code."
            ,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")]])
        )

    # --- Admin OTP Group Test Wizard ---
    elif query.data == "test" and await is_admin(user_id):
        await query.answer()
        TEST_STATE[user_id] = {"step": "GET_SERVICE"}
        await query.message.edit_text(
            "🧪 **OTP Group Test**\n\n"
            "প্রথমে যে **Service** টেস্ট করতে চান তার নাম লিখুন。\n"
            "উদাহরণ: `Facebook` / `WhatsApp`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")]
            ])
        )

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
            text = "📊 বর্তমানে কোনো ট্রাফিক আপডেট নেই。"
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


    # --- Legacy provider button aliases (kept for already-sent keyboards) ---
    elif query.data in {"stex_control", "voltx_control", "zenex_control", "ye_control"} and await is_admin(user_id):
        provider = {
            "stex_control": "stex",
            "voltx_control": "voltx",
            "zenex_control": "zenex",
            "ye_control": "yesms",
        }[query.data]
        await query.answer()
        text, markup = await provider_panel_markup(provider)
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=markup)

    # --- Dynamic Provider Control Panels ---
    elif query.data == "provider_otp_info" and await is_admin(user_id):
        await query.answer()
        await query.message.edit_text(
            "🛡️ **Authorized Provider OTP**\n\n"
            "OTP delivery is accepted only from the configured provider webhook/API and is matched to an active order.\n\n"
            "The bot does not read, intercept, or forward OTPs from unrelated Telegram chats or devices.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_system_menu")]])
        )

    elif query.data.startswith("p_control:") and await is_admin(user_id):
        provider = query.data.split(":", 1)[1]
        if provider not in PROVIDERS:
            await query.answer("❌ Unknown provider", show_alert=True)
        else:
            await query.answer()
            text, markup = await provider_panel_markup(provider)
            await query.message.edit_text(text, parse_mode="Markdown", reply_markup=markup)

    elif query.data.startswith("p_baseurl:") and await is_admin(user_id):
        provider = query.data.split(":", 1)[1]
        if not provider_requires_base_url(provider):
            await query.answer("This provider uses API Key only.", show_alert=True)
        else:
            PROVIDER_STATE[user_id] = {"step": "BASE_URL", "provider": provider}
            await query.answer()
            current_cfg = await provider_api_config(provider)
            current = current_cfg.get("base_url") or "Not configured"
            await query.message.edit_text(
                f"🌐 **Set {provider_label(provider)} Base URL**\n\n"
                f"Current: `{current}`\n\n"
                "Send the provider Base URL.\n"
                "Example: `https://example.com/@public/`\n\n"
                "The number endpoint will use `/api/getnum` by default.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"p_control:{provider}")]])
            )

    elif query.data.startswith("p_otpapi:") and await is_admin(user_id):
        provider = query.data.split(":", 1)[1]
        PROVIDER_STATE[user_id] = {"step": "OTP_API", "provider": provider}
        await query.answer()
        current_cfg = await provider_api_config(provider)
        current = current_cfg.get("otp_api_url") or "Auto/default OTP API not available"
        await query.message.edit_text(
            f"🟣 **Set {provider_label(provider)} OTP API**\n\n"
            f"Current: `{current}`\n\n"
            "Send the complete OTP API URL.\n"
            "Example: `https://example.com/@public/api/success-otp-info`\n\n"
            "The bot will poll this endpoint using the saved API key and send matched OTPs to the configured OTP group.\n"
            "Send `OFF` to disable custom OTP polling and use the provider default, if available.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"p_control:{provider}")]])
        )

    elif query.data.startswith("p_keys:") and await is_admin(user_id):
        provider = query.data.split(":", 1)[1]
        keys = await provider_keys_col.find({"provider": provider}).sort("created_at", 1).to_list(length=100)
        text = f"🔑 **{provider_label(provider)} API Keys**\n\nTotal API Keys: `{len(keys)}`\n"
        keyboard = []
        for index, key in enumerate(keys, 1):
            keyboard.append([InlineKeyboardButton(
                f"🔑 Key #{index}: {key.get('masked', '••••')}", callback_data="noop"
            ), InlineKeyboardButton("🗑 Delete", callback_data=f"p_del_key:{provider}:{key['key_id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"p_control:{provider}")])
        await query.answer()
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("p_add_key:") and await is_admin(user_id):
        provider = query.data.split(":", 1)[1]
        PROVIDER_STATE[user_id] = {"step": "API_KEY", "provider": provider}
        await query.answer()
        await query.message.edit_text(
            f"🔑 **Send the new {provider_label(provider)} API Key:**\n\n"
            "The key will be masked in the admin UI.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"p_control:{provider}")]])
        )

    elif query.data.startswith("p_del_key:") and await is_admin(user_id):
        _, provider, key_id = query.data.split(":", 2)
        await query.answer()
        await query.message.edit_text(
            "⚠️ **Are you sure you want to delete this API key?**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm", callback_data=f"p_del_key_confirm:{provider}:{key_id}"), InlineKeyboardButton("❌ Cancel", callback_data=f"p_keys:{provider}")]
            ])
        )

    elif query.data.startswith("p_del_key_confirm:") and await is_admin(user_id):
        _, provider, key_id = query.data.split(":", 2)
        await provider_keys_col.delete_one({"provider": provider, "key_id": key_id})
        await query.answer("✅ API key deleted", show_alert=True)
        keys = await provider_keys_col.find({"provider": provider}).sort("created_at", 1).to_list(length=100)
        text = f"🔑 **{provider_label(provider)} API Keys**\n\nTotal API Keys: `{len(keys)}`\n"
        keyboard = []
        for index, key in enumerate(keys, 1):
            keyboard.append([InlineKeyboardButton(f"🔑 Key #{index}: {key.get('masked', '••••')}", callback_data="noop"), InlineKeyboardButton("🗑 Delete", callback_data=f"p_del_key:{provider}:{key['key_id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"p_control:{provider}")])
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("p_services:") and await is_admin(user_id):
        provider = query.data.split(":", 1)[1]
        await query.answer()
        text, markup = await provider_services_markup(provider)
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=markup)

    elif query.data.startswith("p_add_service:") and await is_admin(user_id):
        provider = query.data.split(":", 1)[1]
        PROVIDER_STATE[user_id] = {"step": "SERVICE_NAME", "provider": provider}
        await query.answer()
        await query.message.edit_text(
            "📝 **Enter Service Name (e.g. TELEGRAM):**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"p_services:{provider}")]])
        )

    elif query.data.startswith("p_service:") and await is_admin(user_id):
        _, provider, service_id = query.data.split(":", 2)
        await query.answer()
        text, markup = await provider_service_screen(provider, service_id)
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=markup)

    elif query.data.startswith("p_del_service:") and await is_admin(user_id):
        _, provider, service_id = query.data.split(":", 2)
        await query.answer()
        await query.message.edit_text(
            "⚠️ **Delete this service and all of its countries/ranges?**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Confirm", callback_data=f"p_del_service_confirm:{provider}:{service_id}"), InlineKeyboardButton("❌ Cancel", callback_data=f"p_service:{provider}:{service_id}")]])
        )

    elif query.data.startswith("p_del_service_confirm:") and await is_admin(user_id):
        _, provider, service_id = query.data.split(":", 2)
        await provider_ranges_col.delete_many({"provider": provider, "service_id": service_id})
        await provider_countries_col.delete_many({"provider": provider, "service_id": service_id})
        await provider_services_col.delete_one({"provider": provider, "service_id": service_id})
        await query.answer("✅ Service deleted", show_alert=True)
        text, markup = await provider_services_markup(provider)
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=markup)

    elif query.data.startswith("p_add_country:") and await is_admin(user_id):
        _, provider, service_id = query.data.split(":", 2)
        PROVIDER_STATE[user_id] = {"step": "COUNTRY_NAME", "provider": provider, "service_id": service_id}
        await query.answer()
        await query.message.edit_text(
            "🌍 **Enter Country Name:**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"p_service:{provider}:{service_id}")]])
        )

    elif query.data.startswith("p_country:") and await is_admin(user_id):
        _, provider, service_id, country_id = query.data.split(":", 3)
        await query.answer()
        text, markup = await provider_country_screen(provider, service_id, country_id)
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=markup)

    elif query.data.startswith("p_del_country:") and await is_admin(user_id):
        _, provider, service_id, country_id = query.data.split(":", 3)
        await query.answer()
        await query.message.edit_text(
            "⚠️ **Delete this country and all configured ranges?**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Confirm", callback_data=f"p_del_country_confirm:{provider}:{service_id}:{country_id}"), InlineKeyboardButton("❌ Cancel", callback_data=f"p_country:{provider}:{service_id}:{country_id}")]])
        )

    elif query.data.startswith("p_del_country_confirm:") and await is_admin(user_id):
        _, provider, service_id, country_id = query.data.split(":", 3)
        await provider_ranges_col.delete_many({"provider": provider, "service_id": service_id, "country_id": country_id})
        await provider_countries_col.delete_one({"provider": provider, "country_id": country_id})
        await query.answer("✅ Country deleted", show_alert=True)
        text, markup = await provider_service_screen(provider, service_id)
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=markup)

    elif query.data.startswith("p_add_range:") and await is_admin(user_id):
        _, provider, service_id, country_id = query.data.split(":", 3)
        country = await provider_countries_col.find_one({"provider": provider, "country_id": country_id})
        country_name = country.get("name", "the selected country") if country else "the selected country"
        PROVIDER_STATE[user_id] = {"step": "RANGE", "provider": provider, "service_id": service_id, "country_id": country_id}
        await query.answer()
        await query.message.edit_text(
            f"📝 **Send the new Range for {country_name} (e.g. 26134):**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"p_country:{provider}:{service_id}:{country_id}")]])
        )

    elif query.data.startswith("p_del_range:") and await is_admin(user_id):
        _, provider, range_id = query.data.split(":", 2)
        rng = await provider_ranges_col.find_one({"provider": provider, "range_id": range_id})
        if not rng:
            await query.answer("Range not found", show_alert=True)
        else:
            await provider_ranges_col.delete_one({"provider": provider, "range_id": range_id})
            await query.answer("✅ Range deleted", show_alert=True)
            text, markup = await provider_country_screen(provider, rng["service_id"], rng["country_id"])
            await query.message.edit_text(text, parse_mode="Markdown", reply_markup=markup)

    elif query.data.startswith("p_search:") and await is_admin(user_id):
        provider = query.data.split(":", 1)[1]
        PROVIDER_STATE[user_id] = {"step": "SEARCH_COUNTRY", "provider": provider}
        await query.answer()
        await query.message.edit_text(
            f"🌐 **Search {provider_label(provider)} Country**\n\nSend a country name or part of it:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"p_control:{provider}")]])
        )

    # --- Provider user-facing service/country/number flow ---
    elif query.data.startswith("psel_serv:"):
        _, provider, service_id = query.data.split(":", 2)
        svc = await provider_services_col.find_one({"provider": provider, "service_id": service_id})
        if not svc:
            await query.answer("Service unavailable", show_alert=True)
        else:
            countries = await provider_countries_col.find({"provider": provider, "service_id": service_id}).sort("name", 1).to_list(length=200)
            if not countries:
                await query.answer("No countries configured", show_alert=True)
            else:
                await query.answer()
                keyboard = [[InlineKeyboardButton(f"{c.get('flag', country_flag(c.get('code', 'UN')))} {c['name']}", callback_data=f"psel_country:{provider}:{service_id}:{c['country_id']}")] for c in countries]
                keyboard.append([InlineKeyboardButton("🔙 Back to Services", callback_data="get_number_menu")])
                await query.message.edit_text(f"🌍 **{svc['name']} — Select Country:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("psel_country:"):
        _, provider, service_id, country_id = query.data.split(":", 3)
        svc = await provider_services_col.find_one({"provider": provider, "service_id": service_id})
        country = await provider_countries_col.find_one({"provider": provider, "country_id": country_id})
        ranges = await provider_ranges_col.find({"provider": provider, "service_id": service_id, "country_id": country_id}).to_list(length=500)
        if not svc or not country or not ranges:
            await query.answer("No ranges are configured for this country.", show_alert=True)
        else:
            key_docs = await provider_keys_col.find({"provider": provider}).to_list(length=100)
            if not key_docs:
                await query.answer("No API key is configured for this provider.", show_alert=True)
            else:
                await query.answer()
                processing = await query.message.edit_text("⏳ Requesting an authorized number from the provider API...")
                key_doc = random.choice(key_docs)
                api_key = decrypt_api_key(key_doc.get("encrypted_key", ""))
                rng = random.choice(ranges)
                phone, external_order_id, err = await request_number_from_provider(provider, api_key, svc["name"], country["name"], rng["range"])
                if not phone:
                    await processing.edit_text(
                        "❌ **Provider is currently unavailable.**\n\n"
                        f"`{err or 'No number was returned.'}`",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Other Countries", callback_data=f"psel_serv:{provider}:{service_id}")]])
                    )
                else:
                    order_id = await create_provider_order(
                        user_id, provider,
                        {"key_id": key_doc["key_id"]}, svc,
                        {**country, "country_id": country["country_id"]}, rng, phone, external_order_id
                    )
                    await processing.edit_text(
                        f"🌍 **{country['name']}** allocated for **{svc['name']}**\n\n"
                        f"📞 Number: `{phone}`\n"
                        f"🆔 Order: `#{order_id}`\n\n"
                        "⏳ Waiting for an authorized provider OTP event...",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(f"📲 📋 {phone}", copy_text=CopyTextButton(text=phone))],
                            [InlineKeyboardButton("🌍 Other Countries", callback_data=f"psel_serv:{provider}:{service_id}")],
                            [InlineKeyboardButton("🌐 OTP Group", url=OTP_GROUP_URL)],
                        ])
                    )

    elif query.data == "get_number_menu":
        await query.answer()
        provider_service_docs = []
        for provider in PROVIDERS:
            svcs = await provider_services_col.find({"provider": provider}).sort("name", 1).to_list(length=200)
            provider_service_docs.extend([(provider, svc) for svc in svcs])
        services = await numbers_col.distinct("service_name", {"status": "Available"})
        keyboard = []
        for provider, svc in provider_service_docs:
            keyboard.append([InlineKeyboardButton(
                f"{svc.get('emoji', service_emoji(svc['name']))} {svc['name']} • {provider_label(provider)[:1].upper()}",
                callback_data=f"psel_serv:{provider}:{svc['service_id']}"
            )])
        for s in services:
            keyboard.append([InlineKeyboardButton(f"📱 {s}", callback_data=f"sel_serv:{s}")])
        if keyboard:
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

# --- Group listener intentionally does not inspect or forward OTPs. ---
# OTP delivery is handled only by the authorized provider webhook/API above.
async def otp_group_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return

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
        for state_dict in [ADMIN_UPLOAD_STATE, USER_SEARCH_STATE, ADMIN_SETTINGS_STATE, USER_WITHDRAW_STATE, ADMIN_BROADCAST_STATE, ADMIN_ADD_STATE, CHANNEL_ADD_STATE, FORWARD_GROUP_ADD_STATE, USER_MANAGE_STATE, RANAX_ADD_STATE, MENU_EDIT_STATE, TEST_STATE, PROVIDER_STATE]:
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

    # --- Dynamic Provider Management State Handler ---
    if await is_admin(user_id) and user_id in PROVIDER_STATE:
        state = PROVIDER_STATE[user_id]
        step = state.get("step")
        provider = state.get("provider")

        if step == "BASE_URL":
            base_url = text.strip().rstrip("/")
            if not re.match(r"^https?://[^\s]+$", base_url):
                await update.message.reply_text(
                    "❌ Invalid Base URL. Please send a complete http:// or https:// URL.",
                    reply_markup=back_keyboard()
                )
                return
            await provider_settings_col.update_one(
                {"provider": provider},
                {"$set": {
                    "provider": provider,
                    "base_url": base_url,
                    "get_path": PROVIDERS.get(provider, {}).get("default_get_path", "/api/getnum"),
                    "get_method": "POST",
                    "updated_at": now_iso(),
                }},
                upsert=True
            )
            del PROVIDER_STATE[user_id]
            await update.message.reply_text("✅ Base URL saved successfully.")
            text_panel, markup = await provider_panel_markup(provider)
            await update.message.reply_text(text_panel, parse_mode="Markdown", reply_markup=markup)
            return

        if step == "OTP_API":
            otp_api_url = text.strip()
            if otp_api_url.upper() == "OFF":
                otp_api_url = ""
            elif not re.match(r"^https?://[^\s]+$", otp_api_url):
                await update.message.reply_text(
                    "❌ Invalid OTP API URL. Send a complete http:// or https:// URL.",
                    reply_markup=back_keyboard()
                )
                return
            await provider_settings_col.update_one(
                {"provider": provider},
                {"$set": {
                    "provider": provider,
                    "otp_api_url": otp_api_url,
                    "otp_method": "GET",
                    "updated_at": now_iso(),
                }},
                upsert=True
            )
            del PROVIDER_STATE[user_id]
            await update.message.reply_text(
                "✅ OTP API saved successfully." if otp_api_url else "✅ Custom OTP API disabled.",
                reply_markup=back_keyboard()
            )
            text_panel, markup = await provider_panel_markup(provider)
            await update.message.reply_text(text_panel, parse_mode="Markdown", reply_markup=markup)
            return

        if step == "API_KEY":
            api_key = text.strip()
            if not api_key or len(api_key) > 512:
                await update.message.reply_text("❌ Invalid API Key", reply_markup=back_keyboard())
                return
            valid = await validate_provider_key(provider, api_key)
            if not valid:
                await update.message.reply_text("❌ Invalid API Key", reply_markup=back_keyboard())
                return
            key_id = uuid4().hex[:8]
            await provider_keys_col.insert_one({
                "provider": provider, "key_id": key_id,
                "encrypted_key": encrypt_api_key(api_key),
                "masked": mask_secret(api_key), "created_at": now_iso()
            })
            del PROVIDER_STATE[user_id]
            await update.message.reply_text("✅ API key saved successfully.")
            text_panel, markup = await provider_panel_markup(provider)
            await update.message.reply_text(text_panel, parse_mode="Markdown", reply_markup=markup)
            return

        if step == "SERVICE_NAME":
            service = normalize_service(text)
            if not service:
                await update.message.reply_text("❌ Service name cannot be empty.", reply_markup=back_keyboard())
                return
            exists = await provider_services_col.find_one({"provider": provider, "name": service})
            if exists:
                await update.message.reply_text("⚠️ This service already exists.", reply_markup=back_keyboard())
                return
            service_id = uuid4().hex[:8]
            await provider_services_col.insert_one({
                "provider": provider, "service_id": service_id,
                "name": service, "emoji": service_emoji(service), "created_at": now_iso()
            })
            del PROVIDER_STATE[user_id]
            text_panel, markup = await provider_services_markup(provider)
            await update.message.reply_text(text_panel, parse_mode="Markdown", reply_markup=markup)
            return

        if step == "COUNTRY_NAME":
            country = normalize_country(text)
            if not country:
                await update.message.reply_text("❌ Country name cannot be empty.", reply_markup=back_keyboard())
                return
            exists = await provider_countries_col.find_one({"provider": provider, "service_id": state["service_id"], "name": country})
            if exists:
                await update.message.reply_text("⚠️ This country already exists for this service.", reply_markup=back_keyboard())
                return
            code = country_code_from_name(country)
            country_id = uuid4().hex[:8]
            await provider_countries_col.insert_one({
                "provider": provider, "service_id": state["service_id"], "country_id": country_id,
                "name": country, "code": code, "flag": country_flag(code), "created_at": now_iso()
            })
            service_id = state["service_id"]
            del PROVIDER_STATE[user_id]
            text_panel, markup = await provider_service_screen(provider, service_id)
            await update.message.reply_text(text_panel, parse_mode="Markdown", reply_markup=markup)
            return

        if step == "RANGE":
            range_value = normalize_range(text)
            if not range_value or not re.search(r"\d", range_value):
                await update.message.reply_text("❌ Invalid range.", reply_markup=back_keyboard())
                return
            exists = await provider_ranges_col.find_one({
                "provider": provider, "service_id": state["service_id"],
                "country_id": state["country_id"], "range": range_value
            })
            if exists:
                await update.message.reply_text("⚠️ This range already exists.", reply_markup=back_keyboard())
                return
            range_id = uuid4().hex[:8]
            await provider_ranges_col.insert_one({
                "provider": provider, "service_id": state["service_id"],
                "country_id": state["country_id"], "range_id": range_id,
                "range": range_value, "created_at": now_iso()
            })
            service_id, country_id = state["service_id"], state["country_id"]
            del PROVIDER_STATE[user_id]
            text_panel, markup = await provider_country_screen(provider, service_id, country_id)
            await update.message.reply_text(text_panel, parse_mode="Markdown", reply_markup=markup)
            return

        if step == "SEARCH_COUNTRY":
            query_text = normalize_name(text).lower()
            del PROVIDER_STATE[user_id]
            matches = await provider_countries_col.find({
                "provider": provider,
                "name": {"$regex": re.escape(query_text), "$options": "i"}
            }).to_list(length=100)
            if not matches:
                await update.message.reply_text("⚠️ No configured countries matched your search.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"p_control:{provider}")]]))
                return
            keyboard = []
            for c in matches:
                keyboard.append([InlineKeyboardButton(
                    f"{c.get('flag', '🌍')} {c['name']}",
                    callback_data=f"p_country:{provider}:{c['service_id']}:{c['country_id']}"
                )])
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"p_control:{provider}")])
            await update.message.reply_text(
                f"🌐 **{provider_label(provider)} Country Search**\n\nResults for `{query_text}`:",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

    # --- Admin OTP Group Test State Handler (Without TEST indicator) ---
    if await is_admin(user_id) and user_id in TEST_STATE:
        state = TEST_STATE[user_id]
        step = state.get("step")

        if step == "GET_SERVICE":
            service = text.strip()
            if not service:
                await update.message.reply_text(
                    "❌ Service নাম খালি রাখা যাবে না। আবার লিখুন:",
                    reply_markup=back_keyboard()
                )
                return
            state["service"] = service
            state["step"] = "GET_NUMBER"
            TEST_STATE[user_id] = state
            await update.message.reply_text(
                "📞 এবার **Phone Number** লিখুন。\n\n"
                "উদাহরণ: `+601862810138`",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
            return

        elif step == "GET_NUMBER":
            phone = text.strip()
            normalized = re.sub(r"[^\d+]", "", phone)
            if not re.fullmatch(r"\+\d{7,15}", normalized):
                await update.message.reply_text(
                    "❌ সঠিক আন্তর্জাতিক Phone Number দিন।\n"
                    "উদাহরণ: `+601862810138`",
                    parse_mode="Markdown",
                    reply_markup=back_keyboard()
                )
                return

            state["phone"] = normalized
            state["step"] = "GET_COUNTRY"
            TEST_STATE[user_id] = state
            await update.message.reply_text(
                "🌍 এবার **Country Short Code** লিখুন।\n\n"
                "শুধু 2টি অক্ষর দিন — যেমন: `MY`, `BD`, `ID`, `FR`, `US`",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
            return

        elif step == "GET_COUNTRY":
            country = text.strip().upper()
            if not re.fullmatch(r"[A-Z]{2}", country):
                await update.message.reply_text(
                    "❌ Country Short Code অবশ্যই 2টি ইংরেজি অক্ষর হতে হবে।\n"
                    "উদাহরণ: `MY` / `BD` / `ID`",
                    parse_mode="Markdown",
                    reply_markup=back_keyboard()
                )
                return

            state["country"] = country
            state["step"] = "GET_OTP"
            TEST_STATE[user_id] = state
            await update.message.reply_text(
                f"🌍 Country: `{country}`\n\n"
                "🔐 এবার **OTP Code** লিখুন。\n"
                "উদাহরণ: `054627`",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
            return

        elif step == "GET_OTP":
            otp = text.strip()
            if not re.fullmatch(r"\d{4,8}", otp):
                await update.message.reply_text(
                    "❌ OTP অবশ্যই 4–8 সংখ্যার হতে হবে।\n"
                    "উদাহরণ: `054627`",
                    parse_mode="Markdown",
                    reply_markup=back_keyboard()
                )
                return

            state["otp"] = otp
            state["step"] = "GET_LANGUAGE"
            TEST_STATE[user_id] = state
            await update.message.reply_text(
                "🌐 এবার **Language Code** লিখুন。\n\n"
                "শুধু 2টি অক্ষর দিন, যেমন: `EN`, `FR`, `ID`",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
            return

        elif step == "GET_LANGUAGE":
            language = text.strip().upper()
            if not re.fullmatch(r"[A-Z]{2}", language):
                await update.message.reply_text(
                    "❌ Language Code অবশ্যই 2টি অক্ষরের হতে হবে।\n"
                    "উদাহরণ: `EN` / `FR` / `ID`",
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
                "⏳ Test OTP configured OTP group-এ পাঠানো হচ্ছে..."
            )

            success, failed, total = await send_test_otp_to_configured_groups(
                context, service, phone, otp, language, country
            )

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
                "🧪 **OTP Group Test Complete**\n\n"
                f"📱 Service: `{service}`\n"
                f"📞 Number: `{phone}`\n"
                f"🌍 Country: `{country}`\n"
                f"🔐 OTP: `{otp}`\n"
                f"🌐 Language: `{language}`\n\n"
                f"📤 Groups Found: `{total}`\n"
                f"✅ Sent: `{success}`\n"
                f"❌ Failed: `{failed}`"
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
            await update.message.reply_text(f"👤 User: `{u_id}`\n বর্তমান ব্যালেন্স: `{target_user.get('balance', 0.0)}৳`\n\nনতুন ব্যালেন্স অ্যামাউন্ট বা পরিবর্তন করার পরিমাণ লিখে পাঠান:")
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
                "💰 আপনি কত টাকা উইথড্র করতে চান সেই অ্যামাউন্ট লিখে পাঠান:",
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

    btn_get_num = await get_setting("btn_get_number", "📱 GET NUMBER")
    btn_search_num = await get_setting("btn_search_number", "🔎 SEARCH NUMBER")
    btn_traffic = await get_setting("btn_traffic", "🚦 TRAFFIC")
    btn_refer = await get_setting("btn_refer", "👥 REFERRAL")
    btn_balance = await get_setting("btn_balance", "💰 BALANCE")
    btn_support = await get_setting("btn_support", "🆘 SUPPORT")

    if text == "/start":
        await start(update, context)
        
    elif text == btn_get_num:
        provider_service_docs = []
        for provider in PROVIDERS:
            svcs = await provider_services_col.find({"provider": provider}).sort("name", 1).to_list(length=200)
            provider_service_docs.extend([(provider, svc) for svc in svcs])
        services = await numbers_col.distinct("service_name", {"status": "Available"})
        keyboard = []
        for provider, svc in provider_service_docs:
            keyboard.append([InlineKeyboardButton(
                f"{svc.get('emoji', service_emoji(svc['name']))} {svc['name']} • {provider_label(provider)}",
                callback_data=f"psel_serv:{provider}:{svc['service_id']}"
            )])
        for s in services:
            keyboard.append([InlineKeyboardButton(f"📱 {s}", callback_data=f"sel_serv:{s}")])
        if keyboard:
            keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_main_menu")])
            await update.message.reply_text("📱 **Select a Service:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("⚠️ No services are configured.", parse_mode="Markdown")
        
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
        elif not update.message.document and not any(user_id in d for d in [ADMIN_UPLOAD_STATE, USER_SEARCH_STATE, ADMIN_SETTINGS_STATE, USER_WITHDRAW_STATE, ADMIN_BROADCAST_STATE, ADMIN_ADD_STATE, CHANNEL_ADD_STATE, FORWARD_GROUP_ADD_STATE, USER_MANAGE_STATE, RANAX_ADD_STATE, MENU_EDIT_STATE, TEST_STATE, PROVIDER_STATE]):
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
    
    # OTP delivery is webhook/API driven and never reads arbitrary group messages.
    print("Zentrix Bot with authorized multi-provider management is starting...")
    
    async def main_runner():
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        start_provider_webhook_server(application.bot)
        otp_poll_task = asyncio.create_task(poll_provider_otp_apis(application.bot))
        stop_signal = asyncio.Event()
        try:
            await stop_signal.wait()
        finally:
            otp_poll_task.cancel()
            try:
                await otp_poll_task
            except asyncio.CancelledError:
                pass

    try:
        await main_runner()
    except (KeyboardInterrupt, RuntimeError):
        pass
    finally:
        stop_provider_webhook_server()

if __name__ == "__main__":
    asyncio.run(main())

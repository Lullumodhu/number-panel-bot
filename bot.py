import asyncio
import io
import re
import json
import html
import os
import httpx
import pyotp
import random
import string
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

# ==================== CONFIG SECTION ====================

BOT_TOKEN = "8821432916:AAGSCHCS1vjQi_UHeTSqWeuhjNazJVVNSCY"
API_KEY = "FASTXOTP_6F62B5EFBBD6E0392DADC775"
BASE_URL = "https://otpapi.miahhost.com/@Telegram/@Bot/3oo10/@public/"
USER_DATA_FILE = "users.json"
PAID_SMS_FILE = "paid_sms.json"
STATS_FILE = "user_stats.json"
REFERRAL_DATA_FILE = "referral_data.json"
BANNED_USERS_FILE = "banned_users.json"
WITHDRAW_DATA_FILE = "withdraw_requests.json"
ACTIVITY_LOGS_FILE = "activity_logs.json"
DATA_RANGE_FILE = "datarange.json"
SYS_CONFIG_FILE = "sys_config.json"


# ==================== CUSTOM PREMIUM EMOJI IDs CONFIG ====================
CUSTOM_EMOJIS = {
    "GET_NUMBER": "5330237710655306682",  
    "TRAFFIC": "5330237710655306682",     
    "2FA": "your_emoji_id_here",         
    "SUPPORT": "6168100351665773873",     
    "PROFILE": "6129812419028982717",     
    "REFER": "5843618080713874142",       
    "WITHDRAW": "your_emoji_id_here",     
    "LANG": "your_emoji_id_here",         # ল্যাঙ্গুয়েজ বাটনের জন্য ইমোজি কী

    "INSTAGRAM": "your_emoji_id_here",   
    "TELEGRAM": "5330237710655306682",    
    "WHATSAPP": "5334998226636390258",    
    "FACEBOOK": "5323261730283863478",    
    "TIKTOK": "your_emoji_id_here",      
    "CLOSE": "your_emoji_id_here",       

    "BKASH": "your_emoji_id_here",       
    "NAGAD": "your_emoji_id_here",       
    "ROCKET": "your_emoji_id_here",      
    "BINANCE": "your_emoji_id_here",     
}

# কাস্টমাইজার প্যানেলে এডমিনদের বোঝার সুবিধার জন্য লেবেল ম্যাপিং
CUSTOMIZER_HUMAN_NAMES = {
    "WELCOME": "💎 Welcome Message (/start)",
    "GET_NUMBER": "📱 GET NUMBER (Main Button & Page 1 Title)",
    "GET_NUMBER_PAGE2": "🌍 SELECT COUNTRY (Page 2 Title)",
    "ALLOCATION_PENDING": "⏳ SCANNING NODE (Page 3 Pending Title)",
    "DECRYPTION_SUCCESS": "🔑 NODE DECRYPTED (Page 4 Success Title)",
    "TRAFFIC": "📟 TRAFFIC (Main Button & Leaderboard Title)",
    "2FA": "🔐 2FA ONLINE (Main Button & Prompt Title)",
    "SUPPORT": "👤 SUPPORT (Main Button & Home Title)",
    "HELP_CENTER": "💬 Support: Help Center Channel Button",
    "DEV_SUPPORT": "👨‍💻 Support: Developer Support Button",
    "REFER": "🎁 REFERRAL (Main Button & Screen Title)",
    "PROFILE": "👤 PROFILE (Main Button & Screen Title)",
    "WITHDRAW": "💸 WITHDRAW (Profile Button & Gateway Title)",
    "BKASH": "🌸 WITHDRAW: bKash Gateway Button",
    "NAGAD": "🍊 WITHDRAW: Nagad Gateway Button",
    "LANG": "🌐 LANGUAGE (Main Button & Translation Screen)"
}

# পেজিনেটেড কান্ট্রি লিস্টের জন্য সাধারণ প্রিফিক্সসমূহ
COMMON_PREFIXES = [
    "237", "225", "261", "40", "27", "234", "254", "233", "212", "213", 
    "20", "880", "91", "7", "1", "44", "33", "49", "92", "90", "964", "966", "380"
]


# ==================== PERSISTENT CONFIGURATION LOADER ====================
def load_sys_config():
    default_config = {
        "official_channel_id": -1003941468281,
        "official_channel_link": "https://t.me/shiyam7449266",
        "active_services": {
            "INSTAGRAM": True,
            "TELEGRAM": True,
            "WHATSAPP": True,
            "FACEBOOK": True,
            "TIKTOK": True
        },
        "service_emojis": {},
        "country_overrides": {},
        "service_name_overrides": {},
        "custom_buttons": {
            "GET_NUMBER": {
                "labels": {"en": "💬 GET NUMBER", "bn": "💬 নম্বর নিন"},
                "messages": {
                    "en": "📲 <b>[ GET ACTIVE NODE ]</b>\n\nSelect your target service from the database:",
                    "bn": "📲 <b>[ নম্বর নোড কানেকশন ]</b>\n\nনিচের লিস্ট থেকে আপনার টার্গেট সার্ভিসটি সিলেক্ট করুন:"
                },
                "emoji_id": "5330237710655306682"
            },
            "GET_NUMBER_PAGE2": {
                "labels": {"en": "🌍 SELECT COUNTRY", "bn": "🌍 দেশ নির্বাচন"},
                "messages": {
                    "en": "📲 <b>[ GET ACTIVE NODE ]</b>\n\n🎯 Service: <b>{sid}</b>\n🌍 Select origin prefix:",
                    "bn": "📲 <b>[ নম্বর নোড কানেকশন ]</b>\n\n🎯 সার্ভিস: <b>{sid}</b>\n🌍 কান্ট্রি বা দেশ সিলেক্ট করুন:"
                },
                "emoji_id": ""
            },
            "TRAFFIC": {
                "labels": {"en": "📟 TRAFFIC", "bn": "📟 লিডারবোর্ড"},
                "messages": {
                    "en": "🏆 <b>TOP 10 OTP LEADERBOARD</b> 🏆\n━━━━━━━━━━━━━━━━━━━━━━\n\n",
                    "bn": "🏆 <b>টপ ১০ ওটিপি লিডারবোর্ড</b> 🏆\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                },
                "emoji_id": "5330237710655306682"
            },
            "2FA": {
                "labels": {"en": "🔐 2FA ONLINE", "bn": "🔐 2FA অনলাইন"},
                "messages": {
                    "en": "🔑 <b>Enter your 2FA Secret Key:</b>",
                    "bn": "🔑 <b>আপনার 2FA সিক্রেট কী-টি পাঠান:</b>"
                },
                "emoji_id": ""
            },
            "SUPPORT": {
                "labels": {"en": "👤 SUPPORT", "bn": "👤 সাপোর্ট"},
                "messages": {
                    "en": "💬 <b>SUPPORT TERMINAL</b> 🎧\n━━━━━━━━━━━━━━━━━━━━━━\n\nUse the buttons below to establish direct support channels.",
                    "bn": "💬 <b>সাপোর্ট সেন্টার</b> 🎧\n━━━━━━━━━━━━━━━━━━━━━━\n\nযেকোনো সমস্যায় নিচে দেওয়া বাটনগুলোতে ক্লিক করে আমাদের সাথে যোগাযোগ করুন।"
                },
                "emoji_id": "6168100351665773873"
            },
            "HELP_CENTER": {
                "labels": {"en": "💬 Help Center", "bn": "💬 হেল্প সেন্টার"},
                "messages": {"en": "", "bn": ""},
                "emoji_id": ""
            },
            "DEV_SUPPORT": {
                "labels": {"en": "👨‍💻 Developer Support", "bn": "👨‍💻 ডেভলপার সাপোর্ট"},
                "messages": {"en": "", "bn": ""},
                "emoji_id": ""
            },
            "REFER": {
                "labels": {"en": "🎁 Refer", "bn": "🎁 রেফার করুন"},
                "messages": {
                    "en": "🎁 <b>[ REFERRAL PORTAL ]</b> 🎁\n━━━━━━━━━━━━━━━━━━━━━━\n\n<blockquote>👥 Successful Invites: <code>{successful_refers}</code>\n🪙 Harvested Income: <code>{total_reward} BDT</code></blockquote>\n\n🔗 <b>YOUR REFERRAL LINK:</b>\n<blockquote><code>{referral_link}</code></blockquote>\n\n<i>Share and replicate system node access with friends to earn commission.</i>",
                    "bn": "🎁 <b>[ রেফারেল সেন্টার ]</b> 🎁\n━━━━━━━━━━━━━━━━━━━━━━\n\n<blockquote>👥 সফল রেফারেল: <code>{successful_refers}</code>\n🪙 অর্জিত রিওয়ার্ড: <code>{total_reward} BDT</code></blockquote>\n\n🔗 <b>আপনার রেফারেল লিংক:</b>\n<blockquote><code>{referral_link}</code></blockquote>\n\n<i>বন্ধুদের আমন্ত্রণ জানান এবং প্রতিটি আমন্ত্রণে এক্সট্রা রিওয়ার্ড লাভ করুন।</i>"
                },
                "emoji_id": "5843618080713874142"
            },
            "PROFILE": {
                "labels": {"en": "👤 PROFILE", "bn": "👤 প্রোফাইল"},
                "messages": {
                    "en": "👤 <b>USER PROFILE</b>\n━━━━━━━━━━━━━━━━━━━━━━\n🏷️ <b>Name:</b> <code>{full_name}</code>\n🆔 <b>Username:</b> @{username}\n🗝️ <b>User ID:</b> <code>{uid}</code>\n\n💵 <b>Wallet Balance:</b> <code>{balance} BDT</code>\n\n📊 <b>Today's Stats:</b>\n<blockquote>📱 Numbers taken: <code>{today_numbers}</code>\n🔑 OTPs received: <code>{today_otps}</code></blockquote>\n\n🌐 <b>All-time Stats:</b>\n<blockquote>📱 Numbers taken: <code>{total_numbers}</code>\n🔑 OTPs received: <code>{total_otps}</code></blockquote>",
                    "bn": "👤 <b>ইউজার প্রোফাইল</b>\n━━━━━━━━━━━━━━━━━━━━━━\n🏷️ <b>নাম:</b> <code>{full_name}</code>\n🆔 <b>ইউজারনেম:</b> @{username}\n🗝️ <b>ইউজার আইডি:</b> <code>{uid}</code>\n\n💵 <b>ওয়ালেট ব্যালেন্স:</b> <code>{balance} BDT</code>\n\n📊 <b>আজকের স্ট্যাটাস:</b>\n<blockquote>📱 নম্বর নিয়েছেন: <code>{today_numbers}</code>\n🔑 ওটিপি পেয়েছেন: <code>{today_otps}</code></blockquote>\n\n🌐 <b>সর্বমোট স্ট্যাটাস:</b>\n<blockquote>📱 নম্বর নিয়েছেন: <code>{total_numbers}</code>\n🔑 ওটিপি পেয়েছেন: <code>{total_otps}</code></blockquote>"
                },
                "emoji_id": "6129812419028982717"
            },
            "WELCOME": {
                "labels": {"en": "WELCOME MSG", "bn": "স্বাগতম মেসেজ"},
                "messages": {
                    "en": "💎 <b>[ ACCESS GRANTED ]</b> 💎\n━━━━━━━━━━━━━━━━━━━━━━\n🟢 Connection Status: <code>SECURE</code>\n⚙️ Decryption Protocol: <code>ACTIVE</code>",
                    "bn": "💎 <b>[ নোড অ্যাক্সেস সফল ]</b> 💎\n━━━━━━━━━━━━━━━━━━━━━━\n🟢 সংযোগ স্ট্যাটাস: <code>সক্রিয়</code>\n⚙️ ডিক্রিপশন প্রোটোকল: <code>চলমান</code>"
                },
                "emoji_id": ""
            },
            "WITHDRAW": {
                "labels": {"en": "💳 WITHDRAW", "bn": "💸 উইথড্র করুন"},
                "messages": {
                    "en": "💳 Select your destination payment gateway:",
                    "bn": "💳 পেমেন্ট গেটওয়ে সিলেক্ট করুন:"
                },
                "emoji_id": ""
            },
            "BKASH": {
                "labels": {"en": "📱 BKASH", "bn": "🌸 BKASH"},
                "messages": {"en": "", "bn": ""},
                "emoji_id": ""
            },
            "NAGAD": {
                "labels": {"en": "💵 NAGAD", "bn": "🍊 NAGAD"},
                "messages": {"en": "", "bn": ""},
                "emoji_id": ""
            },
            "LANG": {
                "labels": {"en": "🌐 LANGUAGE", "bn": "🌐 ভাষা পরিবর্তন"},
                "messages": {
                    "en": "🌐 <b>Select your preferred language:</b>",
                    "bn": "🌐 <b>আপনার পছন্দের ভাষাটি সিলেক্ট করুন:</b>"
                },
                "emoji_id": ""
            },
            "ALLOCATION_PENDING": {
                "labels": {"en": "NODE ALLOCATION MSG", "bn": "নম্বর অ্যালোকেশন মেসেজ"},
                "messages": {
                    "en": "🛰️ <b>[ CYBER-NODE ALLOCATION ]</b> 🛰️\n━━━━━━━━━━━━━━━━━━━━━━\n\n🌍 <b>ORIGIN:</b> <code>{country_info}</code>\n🛰️ <b>NODE:</b> <code>{range_text}</code>\n📱 <b>TARGET:</b> <code>{service_logo}</code>\n📟 <b>ADDR:</b> <code>+{clean_num}</code>\n\n📡 <b>SCAN STATUS: ⏳ SCANNING FOR DATA...</b>",
                    "bn": "🛰️ <b>[ নম্বর নোড কানেকশন ]</b> 🛰️\n━━━━━━━━━━━━━━━━━━━━━━\n\n🌍 <b>কান্ট্রি:</b> <code>{country_info}</code>\n🛰️ <b>নোড রেঞ্জ:</b> <code>{range_text}</code>\n📱 <b>সার্ভিস:</b> <code>{service_logo}</code>\n📟 <b>নম্বর:</b> <code>+{clean_num}</code>\n\n📡 <b>স্ট্যাটাস: ⏳ ওটিপি স্ক্যান করা হচ্ছে...</b>"
                },
                "emoji_id": ""
            },
            "DECRYPTION_SUCCESS": {
                "labels": {"en": "🔑 SUCCESS MSG", "bn": "🔑 ওটিপি সফল মেসেজ"},
                "messages": {
                    "en": "🛰️ <b>[ NODE DECRYPTED SUCCESSFULLY ]</b> 🛰️\n━━━━━━━━━━━━━━━━━━━━━━\n\n🌍 <b>ORIGIN:</b> <code>{country_info}</code>\n🛰️ <b>NODE:</b> <code>{range_text}</code>\n📱 <b>TARGET:</b> <code>{service_logo}</code>\n📟 <b>ADDR:</b> <code>+{clean_num}</code>\n🔑 <b>KEY:</b> <code>{otp_safe}</code>{packet_text}",
                    "bn": "🛰️ <b>[ নম্বর নোড কানেকশন সফল ]</b> 🛰️\n━━━━━━━━━━━━━━━━━━━━━━\n\n🌍 <b>কান্ট্রি:</b> <code>{country_info}</code>\n🛰️ <b>নোড রেঞ্জ:</b> <code>{range_text}</code>\n📱 <b>সার্ভিস:</b> <code>{service_logo}</code>\n📟 <b>নম্বর:</b> <code>+{clean_num}</code>\n🔑 <b>ওটিপি কোড:</b> <code>{otp_safe}</code>{packet_text}"
                },
                "emoji_id": ""
            }
        }
    }
    if not os.path.exists(SYS_CONFIG_FILE):
        try:
            with open(SYS_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Failed to write default sys config: {e}")
        return default_config
    try:
        with open(SYS_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            modified = False
            if "active_services" not in data:
                data["active_services"] = default_config["active_services"]
                modified = True
            if "service_emojis" not in data:
                data["service_emojis"] = {}
                modified = True
            if "country_overrides" not in data:
                data["country_overrides"] = {}
                modified = True
            if "service_name_overrides" not in data:
                data["service_name_overrides"] = {}
                modified = True
            if "custom_buttons" not in data:
                data["custom_buttons"] = default_config["custom_buttons"]
                modified = True
            else:
                for k, v in default_config["custom_buttons"].items():
                    if k not in data["custom_buttons"]:
                        data["custom_buttons"][k] = v
                        modified = True
            if modified:
                save_sys_config(data)
            return data
    except Exception as e:
        print(f"[ERROR] load_sys_config failed: {e}. Falling back to default config.")
        return default_config

def save_sys_config(cfg):
    try:
        with open(SYS_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Failed to save system configuration: {e}")

sys_cfg = load_sys_config()


# ==================== HELPER FUNCTIONS FOR PREMIUM EMOJI ====================

def strip_emoji(text):
    cleaned = text
    emojis_to_remove = [
        "💬", "📟", "🔐", "👤", "🎁", "📲", "🏆", "🔑", "🟢", "📸", 
        "✈️", "🔵", "🎵", "❌", "🛡️", "📱", "💵", "🚀", "🏦", "🛑", "🌐"
    ]
    for char in emojis_to_remove:
        cleaned = cleaned.replace(char, "")
    return cleaned.strip()

def get_dynamic_button_label(key, lang):
    sc = load_sys_config()
    btn_data = sc.get("custom_buttons", {}).get(key, {})
    labels = btn_data.get("labels", {})
    return labels.get(lang, labels.get("bn", key))

def get_dynamic_message_text(key, lang):
    sc = load_sys_config()
    btn_data = sc.get("custom_buttons", {}).get(key, {})
    messages = btn_data.get("messages", {})
    return messages.get(lang, messages.get("bn", ""))

def get_dynamic_emoji_id(key):
    sc = load_sys_config()
    
    # কান্ট্রি ওভাররাইড প্রিমিয়াম ইমোজি ডাইনামিক হ্যান্ডলার
    if key and key.startswith("COUNTRY_"):
        prefix_clean = key.replace("COUNTRY_", "")
        overrides = sc.get("country_overrides", {})
        if prefix_clean in overrides:
            return overrides[prefix_clean].get("emoji_id", "").strip()
        # Fallback parsing for partial matching
        sorted_override_prefixes = sorted(overrides.keys(), key=len, reverse=True)
        for p in sorted_override_prefixes:
            if prefix_clean.startswith(p):
                return overrides[p].get("emoji_id", "").strip()
        return ""

    btn_data = sc.get("custom_buttons", {}).get(key, {})
    emoji_id = btn_data.get("emoji_id", "")
    if emoji_id and emoji_id.strip() != "":
        return emoji_id.strip()
    
    dynamic_emojis = sc.get("service_emojis", {})
    if key in dynamic_emojis and dynamic_emojis[key].strip() != "" and dynamic_emojis[key] != "your_emoji_id_here":
        return dynamic_emojis[key].strip()
    return CUSTOM_EMOJIS.get(key)

def is_premium_emoji_set(emoji_key):
    if not emoji_key:
        return False
    emoji_id = get_dynamic_emoji_id(emoji_key)
    return bool(emoji_id and emoji_id.strip() != "" and emoji_id != "your_emoji_id_here")


# ==================== HIDDEN / SPONSOR CHANNEL CONFIG ====================
def _get_h_lnk():
    p1 = "ht" + "tp" + "s://"
    p2 = "t." + "me" + "/s"
    p3 = "hi" + "ya" + "m7" + "44"
    return p1 + p2 + p3

# ==================== MULTIPLE ADMINS CONFIGURATION ====================
ADMINS = [7808485930]
OTP_GROUP_ID = -1003941468281

# ==================== OTP RATE & VALUATION ====================
OTP_RATE = 0.20
REFERRAL_PRICE = 0
MIN_WITHDRAW = 50
MAX_WITHDRAW = 10000

# ==================== SUPPORT & DEVELOPER LINKS ====================
SUPPORT_LINK = "https://t.me/shiyam744"
DEVELOPER_LINK = "https://t.me/shiyam744"

# ==================== LANGUAGES TRANSLATIONS DATA ====================
LANG_TEXTS = {
    "en": {
        "welcome": "💎 <b>[ ACCESS GRANTED ]</b> 💎\n━━━━━━━━━━━━━━━━━━━━━━\n🟢 Connection Status: <code>SECURE</code>\n⚙️ Decryption Protocol: <code>ACTIVE</code>",
        "btn_get_num": " GET NUMBER",
        "btn_search_otp": "🔎 SEARCH OTP",
        "btn_2fa": "🔐 2FA ONLINE",
        "btn_balance": "🪙 BALANCE",
        "btn_refer": "🎁 Refer",
        "btn_profile": "👤 PROFILE",
        "btn_leaderboard": "📟 TRAFFIC",
        "btn_support": "👤 SUPPORT",
        "btn_lang": "🌐 LANGUAGE",
        "btn_admin": "⚙️ ADMIN PANEL ⚙️",
        "banned": "🛑 YOU ARE BANNED!",
        "join_prompt": "🔔 <b>Official Channel Subscription</b>\n━━━━━━━━━━━━━━━━━━━━━━\nPlease subscribe to our channels to proceed with utilizing bot services safely.",
        "btn_join": "🔔 Join Channel",
        "btn_continue": "❇️ Continue",
        "profile_title": "👑 <b>USER PROFILE METRICS</b>\n━━━━━━━━━━━━━━━━━━━━━━",
        "balance_title": "🪙 <b>CORE WALLET BALANCE</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n💵 Liquid Funds: <code>{bal} BDT</code>",
        "btn_withdraw": "💳 WITHDRAW",
        "withdraw_min_err": "<blockquote>🪙 Current balance: {bal} BDT\n📉 Minimum withdrawal boundary is {min_val} BDT</blockquote>",
        "withdraw_method_prompt": "💳 Select your destination payment gateway:",
        "withdraw_amount_prompt": "🪙 Please enter withdrawal valuation (Min: {min_val} BDT):",
        "withdraw_number_prompt": "📲 Send your receiving address (Format: 017XXXXXXXX):",
        "withdraw_proposed": "✨ <b>PROPOSED TRANSACTION DETAILS</b> ✨\n━━━━━━━━━━━━━━━━━━━━━━\n\n<blockquote>💳 GATEWAY: {method}\n📲 DESTINATION: {num}\n🪙 AMOUNT: {amount} BDT</blockquote>\n\nConfirm to proceed.",
        "search_otp_prompt": "🔎 <b>Enter the target number to decrypt OTP:</b>",
        "search_otp_searching": "🔎 Checking database logs, please wait...",
        "search_otp_not_found": "🛑 <b>NO OTP RECORDED</b>\n━━━━━━━━━━━━━━━━━━━━━━\n📟 Address: `+{num}`\n⏳ Status: No active packet found.",
        "get_2fa_prompt": "🔑 <b>Enter your 2FA Secret Key:</b>",
        "2fa_invalid": "🛑 <b>INVALID SECRET KEY</b>\n\nPlease check the parameters and try again.",
        "node_alloc_fail": "🛑 <b>NODE ALLOCATION FAILED</b>\n\nNo available numbers at this range right now.",
        "get_active_node": "📲 <b>[ GET ACTIVE NODE ]</b>\n\nSelect your target service from the database:",
        "pick_country": "📲 <b>[ GET ACTIVE NODE ]</b>\n\n🎯 Service: <b>{sid}</b>\n🌍 Select origin prefix:",
        "custom_range_prompt": "⚙️ <b>[ CUSTOM RANGE ]</b>\n\nType custom range parameter (e.g. 234XXX):",
        "invalid_range": "🛑 <b>INVALID RANGE PARAMETERS!</b>\nFormat example: <code>234XXX</code>"
    },
    "bn": {
        "welcome": "💎 <b>[ নোড অ্যাক্সেস সফল ]</b> 💎\n━━━━━━━━━━━━━━━━━━━━━━\n🟢 সংযোগ স্ট্যাটাস: <code>সক্রিয়</code>\n⚙️ ডিক্রিপশন প্রোটোকল: <code>চলমান</code>",
        "btn_get_num": "GET NUMBER",
        "btn_search_otp": "🔎 ওটিপি খুঁজুন",
        "btn_2fa": "🔐 2FA ONLINE",
        "btn_balance": "🪙 ব্যালেন্স",
        "btn_refer": "🎁 Refer",
        "btn_profile": "👤 PROFILE",
        "btn_leaderboard": "📟 TRAFFIC",
        "btn_support": "👤 SUPPORT",
        "btn_lang": "🌐 ভাষা পরিবর্তন",
        "btn_admin": "⚙️ অ্যাডমিন প্যানেল ⚙️",
        "banned": "🛑 আপনি ব্যান হয়েছেন!",
        "join_prompt": "🔔 <b>অফিশিয়াল চ্যানেলে জয়েন করুন</b>\n━━━━━━━━━━━━━━━━━━━━━━\nবটের সার্ভিসগুলো নিরাপদে ব্যবহার করতে আমাদের আপডেট চ্যানেলে যুক্ত হোন।",
        "btn_join": "🔔 চ্যানেলে জয়েন করুন",
        "btn_continue": "❇️ প্রবেশ করুন",
        "profile_title": "👑 <b>ইউজার প্রোফাইল</b>\n━━━━━━━━━━━━━━━━━━━━━━",
        "balance_title": "🪙 <b>ওয়ালেট ব্যালেন্স</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n💵 মোট ব্যালেন্স: <code>{bal} BDT</code>",
        "btn_withdraw": "💸 উইথড্র করুন",
        "withdraw_min_err": "<blockquote>🪙 বর্তমান ব্যালেন্স: {bal} BDT\n📉 সর্বনিম্ন উইথড্র হচ্ছে {min_val} BDT</blockquote>",
        "withdraw_method_prompt": "💳 পেমেন্ট গেটওয়ে সিলেক্ট করুন:",
        "withdraw_amount_prompt": "🪙 উইথড্র করার পরিমাণটি লিখুন (সর্বনিম্ন: {min_val} BDT):",
        "withdraw_number_prompt": "📲 পেমেন্ট নম্বরটি পাঠান (যেমন: 017XXXXXXXX):",
        "withdraw_proposed": "✨ <b>প্রস্তাবিত উইথড্র ডিটেইলস</b> ✨\n━━━━━━━━━━━━━━━━━━━━━━\n\n<blockquote>💳 গেটওয়ে: {method}\n📲 নম্বর: {num}\n🪙 পরিমাণ: {amount} BDT</blockquote>\n\nনিশ্চিত করতে কনফার্ম বাটনে ক্লিক করুন।",
        "search_otp_prompt": "🔎 <b>ওটিপি খুঁজতে নম্বরটি দিন:</b>",
        "search_otp_searching": "🔎 ডেটাবেজ চেক করা হচ্ছে, দয়া করে অপেক্ষা করুন...",
        "search_otp_not_found": "🛑 <b>কোনো ওটিপি পাওয়া যায়নি</b>\n━━━━━━━━━━━━━━━━━━━━━━\n📟 নম্বর: `+{num}`\n⏳ স্ট্যাটাস: কোনো সক্রিয় ওটিপি পাওয়া যায়নি।",
        "get_2fa_prompt": "🔑 <b>আপনার 2FA সিক্রেট কী-টি পাঠান:</b>",
        "2fa_invalid": "🛑 <b>ভুল সিক্রেট কী!</b>\n\nদয়া করে সঠিক কী-টি পুনরায় ট্রাই করুন।",
        "node_alloc_fail": "🛑 <b>নম্বর অ্যালোকেশন ব্যর্থ</b>\n\nএই রেঞ্জে বর্তমানে কোনো নম্বর খালি নেই।",
        "get_active_node": "📲 <b>[ নম্বর নোড কানেকশন ]</b>\n\nনিচের লিস্ট থেকে আপনার টার্গেট সার্ভিসটি সিলেক্ট করুন:",
        "pick_country": "📲 <b>[ নম্বর নোড কানেকশন ]</b>\n\n🎯 সার্ভিস: <b>{sid}</b>\n🌍 কান্ট্রি বা দেশ সিলেক্ট করুন:",
        "custom_range_prompt": "⚙️ <b>[ কাস্টম রেঞ্জ সেটআপ ]</b>\n\nম্যানুয়ালি রেঞ্জ ইনপুট করুন (যেমন: 234XXX বা 225XXX):",
        "invalid_range": "🛑 <b>ভুল রেঞ্জ ফরম্যাট!</b>\nসঠিক ফরম্যাটের উদাহরণ: <code>234XXX</code>"
    }
}

T_CANCEL = ["🛑 CANCEL", "🛑 বাতিল", "🛑 ABORT", "❌ Close"]

def normalize_input_text(text):
    cleaned = text.strip()
    for char in ["💬", "📟", "🔐", "👤", "🎁", "📲", "🏆", "🔑", "🟢", "📸", "✈️", "🔵", "🎵", "❌", "🛡️", "📱", "💵", "🚀", "🏦", "🛑", "🌐"]:
        cleaned = cleaned.replace(char, "")
    return cleaned.strip().upper()

def get_normalized_dynamic_labels(key):
    sc = load_sys_config()
    btn_data = sc.get("custom_buttons", {}).get(key, {})
    labels = btn_data.get("labels", {})
    return [normalize_input_text(val) for val in labels.values()]

M_GET_NUM = ["GET NUMBER", "নম্বর নিন"]
M_TRAFFIC = ["TRAFFIC", "LEADERBOARD", "লিডারবোর্ড"]
M_2FA = ["2FA ONLINE", "GET 2FA", "2FA কোড নিন"]
M_SUPPORT = ["SUPPORT", "সাপোর্ট"]
M_REFER = ["REFER", "রেফার করুন"]
M_PROFILE = ["PROFILE", "প্রোফাইল"]
M_CANCEL = ["CANCEL", "বাতিল", "ABORT", "CLOSE"]
M_LANG = ["LANGUAGE", "ভাষা পরিবর্তন"]

request_queue = asyncio.Queue()
MAX_WORKERS = 5000

client_async = httpx.AsyncClient(
    timeout=httpx.Timeout(connect=3.0, read=8.0, write=5.0, pool=3.0),
    headers={
        "X-API-Key": API_KEY,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    },
    limits=httpx.Limits(max_connections=1000, max_keepalive_connections=200)
)

active_numbers = {}
last_range = {}
last_sid = {} # SELECTED SERVICE CONTEXT PERSISTENCE
CHECK_INTERVAL = 1.5

_liveaccess_cache = {"services": []}
LIVEACCESS_REFRESH_INTERVAL = 25

async def _do_liveaccess_fetch():
    global _liveaccess_cache
    try:
        r = await client_async.get(f"{BASE_URL}/api/liveaccess")
        data = r.json()
        if data.get("status") == "ok":
            svcs = data.get("services", [])
            if svcs:
                _liveaccess_cache["services"] = svcs
                print(f"[liveaccess] cache updated — {len(svcs)} service(s)")
    except Exception as e:
        print(f"[liveaccess] fetch error: {e}")

async def liveaccess_refresh_loop():
    while True:
        await _do_liveaccess_fetch()
        await asyncio.sleep(LIVEACCESS_REFRESH_INTERVAL)

def get_cached_services():
    return _liveaccess_cache["services"]

def is_admin(user_id):
    return user_id in ADMINS

# ==================== DATA LOADER HELPER FUNCTIONS ====================

def load_data(filename=USER_DATA_FILE):
    if not os.path.exists(filename):
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Failed to init {filename}: {e}")
        return {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] load_data failed for {filename}: {e}")
        return {}

def save_data(data, filename=USER_DATA_FILE):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] save_data failed for {filename}: {e}")

def get_user(uid):
    uid = str(uid)
    data = load_data()
    if uid not in data:
        data[uid] = {
            "user_id": uid, "balance": 0.0, "total_numbers": 0, 
            "referral_count": 0, "lang": None, "verified": False
        }
        save_data(data)
    else:
        modified = False
        if "lang" not in data[uid]:
            data[uid]["lang"] = None
            modified = True
        if "verified" not in data[uid]:
            data[uid]["verified"] = False
            modified = True
        if modified:
            save_data(data)
    return data[uid]

def set_user_lang(uid, lang):
    uid = str(uid)
    data = load_data()
    if uid in data:
        data[uid]["lang"] = lang
        save_data(data)

def get_user_lang(uid):
    user = get_user(uid)
    return user.get("lang") or "bn"

def set_user_verified(uid, verified=True):
    uid = str(uid)
    data = load_data()
    if uid in data:
        data[uid]["verified"] = verified
        save_data(data)

def is_user_verified(uid):
    user = get_user(uid)
    return user.get("verified", False)

async def update_db_balance(uid, amount):
    uid = str(uid)
    data = load_data()
    if uid in data:
        data[uid]["balance"] = round(data[uid].get("balance", 0.0) + amount, 2)
        save_data(data)
        return data[uid]["balance"]
    return 0.0

def get_all_users():
    data = load_data(USER_DATA_FILE)
    return list(data.keys()) if data else []

def user_exists(uid):
    data = load_data(USER_DATA_FILE)
    return str(uid) in data

# ==================== WITHDRAW / BANNED / STATS DATABASE ====================

def load_withdraw_requests():
    return load_data(WITHDRAW_DATA_FILE)

def save_withdraw_requests(data):
    save_data(data, WITHDRAW_DATA_FILE)

def generate_payment_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))

def load_banned_users():
    if not os.path.exists(BANNED_USERS_FILE):
        try:
            with open(BANNED_USERS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Failed to init {BANNED_USERS_FILE}: {e}")
        return []
    try:
        with open(BANNED_USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] load_banned_users failed: {e}")
        return []

def save_banned_users(banned_list):
    save_data(banned_list, BANNED_USERS_FILE)

def is_user_banned(uid):
    banned_list = load_banned_users()
    return str(uid) in banned_list

def ban_user(uid):
    banned_list = load_banned_users()
    uid_str = str(uid)
    if uid_str not in banned_list:
        banned_list.append(uid_str)
        save_banned_users(banned_list)
        return True
    return False

def unban_user(uid):
    banned_list = load_banned_users()
    uid_str = str(uid)
    if uid_str in banned_list:
        banned_list.remove(uid_str)
        save_banned_users(banned_list)
        return True
    return False

def load_referral_data():
    return load_data(REFERRAL_DATA_FILE)

def save_referral_data(data):
    save_data(data, REFERRAL_DATA_FILE)

def update_referral_count(uid, count):
    referral_data = load_referral_data()
    uid_str = str(uid)
    if uid_str not in referral_data:
        referral_data[uid_str] = {"referral_count": 0}
    referral_data[uid_str]["referral_count"] = count
    save_referral_data(referral_data)

def get_referral_count(uid):
    referral_data = load_referral_data()
    uid_str = str(uid)
    return referral_data.get(uid_str, {}).get("referral_count", 0)

def load_range_db():
    return load_data(DATA_RANGE_FILE)

def save_range_db(data):
    save_data(data, DATA_RANGE_FILE)

def save_number_range_info(uid, number, range_text):
    db = load_range_db()
    flag, name = get_country_info(number)
    db[normalize_number(number)] = {
        "user_id": str(uid),
        "number": f"+{normalize_number(number)}",
        "range": range_text,
        "country": f"{flag} {name}"
    }
    save_range_db(db)

# ==================== COUNTRY MAPPING SECTION ====================

def get_country_info(number):
    number = str(number).strip()
    
    clean_num = str(number).replace('+', '').replace(' ', '').replace('-', '').strip()
    
    # DYNAMIC COUNTRY OVERRIDES CHECK
    try:
        sc = load_sys_config()
        overrides = sc.get("country_overrides", {})
        sorted_override_prefixes = sorted(overrides.keys(), key=len, reverse=True)
        for prefix in sorted_override_prefixes:
            if clean_num.startswith(prefix):
                override_data = overrides[prefix]
                return (override_data.get("flag", "🌍"), override_data.get("name", "Unknown"))
    except Exception as e:
        print(f"Error checking country overrides: {e}")

    country_map = {
        "2376": ("🇨🇲", "Cameroon"), "2250": ("🇨🇮", "Ivory Coast"), "2613": ("🇲🇬", "Madagascar"), "4077": ("🇷🇴", "Romania"),
        "237": ("🇨🇲", "Cameroon"), "225": ("🇨🇮", "Ivory Coast"), "261": ("🇲🇬", "Madagascar"), "20": ("🇪🇬", "Egypt"),
        "27": ("🇿🇦", "South Africa"), "234": ("🇳🇬", "Nigeria"), "254": ("🇰🇪", "Kenya"), "233": ("🇬🇭", "Ghana"),
        "212": ("🇲🇦", "Morocco"), "213": ("🇩🇿", "Algeria"), "216": ("🇹🇳", "Tunisia"), "218": ("🇱🇾", "Libya"),
        "249": ("🇸🇩", "Sudan"), "251": ("🇪🇹", "Ethiopia"), "252": ("🇸🇴", "Somalia"), "253": ("🇩يجي", "Djibouti"),
        "255": ("🇹🇿", "Tanzania"), "256": ("🇺🇬", "Uganda"), "257": ("🇧🇮", "Burundi"), "258": ("🇲🇿", "Mozambique"),
        "260": ("🇿🇲", "Zambia"), "263": ("🇿🇼", "Zimbabwe"), "264": ("🇳🇦", "Namibia"), "265": ("🇲🇼", "Malawi"),
        "266": ("🇱🇸", "Lesotho"), "267": ("🇧🇼", "Botswana"), "268": ("🇸🇿", "Swaziland"), "269": ("🇰🇲", "Comoros"),
        "220": ("🇬🇲", "Gambia"), "221": ("🇸🇳", "Senegal"), "222": ("🇲🇷", "Mauritania"), "223": ("🇲🇱", "Mali"),
        "224": ("🇬🇳", "Guinea"), "226": ("🇧🇫", "Burkina Faso"), "227": ("🇳🇪", "Niger"), "228": ("🇹🇬", "Togo"),
        "229": ("🇧জয়েন", "Benin"), "230": ("🇲🇺", "Mauritius"), "231": ("🇱🇷", "Liberia"), "232": ("🇸🇱", "Sierra Leone"),
        "235": ("🇹🇩", "Chad"), "236": ("🇨🇫", "Central African Republic"), "238": ("🇨🇻", "Cape Verde"),
        "239": ("🇸🇹", "Sao Tome and Principe"), "240": ("🇬🇶", "Equatorial Guinea"), "241": ("🇬🇦", "Gabon"),
        "242": ("🇨🇬", "Congo"), "243": ("🇨🇩", "DR Congo"), "244": ("🇦🇴", "Angola"), "245": ("🇬🇼", "Guinea-Bissau"),
        "247": ("🇸🇭", "Saint Helena"), "248": ("🇸🇨", "Seychelles"), "250": ("🇷🇼", "Rwanda"), "290": ("🇸🇭", "Saint Helena"),
        "291": ("🇪🇷", "Eritrea"), "40": ("🇷🇴", "Romania"), "44": ("🇬🇧", "United Kingdom"), "33": ("🇫🇷", "France"),
        "49": ("🇩🇪", "Germany"), "39": ("🇮🇹", "Italy"), "34": ("🇪🇸", "Spain"), "31": ("🇳🇱", "Netherlands"),
        "32": ("🇧🇪", "Belgium"), "41": ("🇨🇭", "Switzerland"), "43": ("🇦🇹", "Austria"), "46": ("🇸🇪", "Sweden"),
        "47": ("🇳🇴", "Norway"), "45": ("🇩👑", "Denmark"), "358": ("🇫ᛁ", "Finland"), "351": ("🇵🇹", "Portugal"),
        "353": ("🇮🇪", "Ireland"), "36": ("🇭🇺", "Hungary"), "48": ("🇵🇱", "Poland"), "380": ("🇺🇦", "Ukraine"),
        "370": ("🇱🇹", "Lithuania"), "371": ("🇱🇻", "Latvia"), "372": ("🇪🇪", "Estonia"), "373": ("🇲🇩", "Moldova"),
        "374": ("🇦🇲", "Armenia"), "375": ("🇧🇾", "Belarus"), "376": ("🇦🇩", "Andorra"), "377": ("🇲🇨", "Monaco"),
        "381": ("🇷🇸", "Serbia"), "382": ("🇲🇪", "Montenegro"), "385": ("🇭🇷", "Croatia"), "386": ("🇸🇮", "Slovenia"),
        "387": ("🇧🇦", "Bosnia and Herzegovina"), "389": ("🇲🇰", "North Macedonia"), "350": ("🇬🇮", "Gibraltar"),
        "352": ("🇱🇺", "Luxembourg"), "354": ("🇮🇸", "Iceland"), "355": ("🇦🇱", "Albania"), "356": ("🇲🇹", "Malta"),
        "357": ("🇨🇾", "Cyprus"), "359": ("🇧🇬", "Bulgaria"), "421": ("🇸🇰", "Slovakia"), "420": ("🇨🇿", "Czech Republic"),
        "298": ("🇫🇴", "Faroe Islands"), "299": ("🇬🇱", "Greenland"), "1": ("🇺🇸", "United States"), "7": ("🇷🇺", "Russia"),
        "91": ("🇮🇳", "India"), "92": ("🇵🇰", "Pakistan"), "880": ("🇧🇩", "Bangladesh"), "86": ("🇨🇳", "China"),
        "81": ("🇯🇵", "Japan"), "82": ("🇰🇷", "South Korea"), "84": ("🇻🇳", "Vietnam"), "66": ("🇹🇭", "Thailand"),
        "62": ("🇮🇩", "Indonesia"), "60": ("🇲🇾", "Malaysia"), "65": ("🇸🇬", "Singapore"), "63": ("🇵🇭", "Philippines"),
        "95": ("🇲🇲", "Myanmar"), "94": ("🇱👑", "Sri Lanka"), "977": ("🇳🇵", "Nepal"), "93": ("🇦🇫", "Afghanistan"),
        "98": ("🇮րան", "Iran"), "90": ("🇹🇷", "Turkey"), "964": ("🇮🇶", "Iraq"), "963": ("🇸🇾", "Syria"),
        "961": ("🇱🇧", "Lebanon"), "962": ("🇯🇴", "Jordan"), "965": ("🇰🇼", "Kuwait"), "966": ("🇸🇦", "Saudi Arabia"),
        "967": ("🇾🇲", "Yemen"), "968": ("🇴🇲", "Oman"), "971": ("🇦🇪", "United Arab Emirates"), "972": ("🇮🇱", "Israel"),
        "973": ("🇧🇭", "Bahrain"), "974": ("🇶🇦", "Qatar"), "994": ("🇦🇿", "Azerbaijan"), "995": ("🇬🇪", "Georgia"),
        "996": ("🇰🇬", "Kyrgyzstan"), "992": ("🇹🇯", "Tajikistan"), "993": ("🇹🇲", "Turkmenistan"), "998": ("🇺🇿", "Uzbekistan"),
        "855": ("🇰🇭", "Cambodia"), "856": ("🇱🇦", "Laos"), "976": ("🇲🇳", "Mongolia"), "850": ("🇰🇵", "North Korea"),
        "55": ("🇧🇷", "Brazil"), "52": ("🇲🇽", "Mexico"), "54": ("🇦링", "Argentina"), "57": ("🇨🇴", "Colombia"),
        "51": ("🇵🇪", "Peru"), "58": ("🇻🇪", "Venezuela"), "56": ("🇨🇱", "Chile"), "593": ("🇪🇨", "Ecuador"),
        "591": ("🇧🇴", "Bolivia"), "595": ("🇵🇾", "Paraguay"), "598": ("🇺🇾", "Uruguay"), "502": ("🇬🇹", "Guatemala"),
        "503": ("🇸🇻", "El Salvador"), "504": ("🇭🇳", "Honduras"), "506": ("🇨🇷", "Costa Rica"), "507": ("🇵🇦", "Panama"),
        "509": ("🇭🇹", "Haiti"), "501": ("🇧🇿", "Belize"), "61": ("🇦🇺", "Australia"), "64": ("🇳🇿", "New Zealand"),
        "675": ("🇵🇬", "Papua New Guinea"), "679": ("🇫🇯", "Fiji"), "1246": ("🇧🇧", "Barbados"), "1876": ("🇯🇲", "Jamaica"),
        "53": ("🇨🇺", "Cuba"), "592": ("🇬🇾", "Guyana"),
    }
    sorted_prefixes = sorted(country_map.keys(), key=len, reverse=True)
    for prefix in sorted_prefixes:
        if clean_num.startswith(prefix):
            return country_map[prefix]
    return ("🌍", "Unknown")

def detect_service(full_sms):
    if not full_sms:
        return "SMS SERVICE"
    sms_lower = full_sms.lower()
    service_keywords = {
        "facebook": "FACEBOOK", "fb": "FACEBOOK", "instagram": "INSTAGRAM", "insta": "INSTAGRAM",
        "tiktok": "TIKTOK", "twitter": "TWITTER", "x.com": "TWITTER", "snapchat": "SNAPCHAT", "snap": "SNAPCHAT",
        "whatsapp": "WHATSAPP", "telegram": "TELEGRAM", "discord": "DISCORD", "messenger": "MESSENGER",
        "linkedin": "LINKEDIN", "google": "GOOGLE", "gmail": "GOOGLE", "amazon": "AMAZON", "microsoft": "MICROSOFT",
        "outlook": "MICROSOFT", "yahoo": "YAHOO", "paypal": "PAYPAL", "binance": "BINANCE", "coinbase": "COINBASE",
        "spotify": "SPOTIFY", "netflix": "NETFLIX", "uber": "UBER", "apple": "APPLE", "icloud": "APPLE",
        "bkash": "BKASH", "nagad": "NAGAD", "stripe": "STRIPE", "line": "LINE", "wechat": "WECHAT",
        "viber": "VIBER", "signal": "SIGNAL", "pubg": "PUBG", "free fire": "FREE FIRE",
    }
    for keyword, service_name in sorted(service_keywords.items(), key=lambda x: len(x[0]), reverse=True):
        if keyword in sms_lower:
            return service_name
    return "SMS SERVICE"

def get_service_logo(service_name):
    service_upper = str(service_name).upper()
    
    # DYNAMIC SERVICE NAME OVERRIDES CHECK
    try:
        sc = load_sys_config()
        overrides = sc.get("service_name_overrides", {})
        if service_upper in overrides:
            return overrides[service_upper]
    except Exception as e:
        print(f"Error checking service name overrides: {e}")

    SERVICE_LOGOS = {
        "FACEBOOK": "🔵 FACEBOOK", "INSTAGRAM": "📸 INSTAGRAM", "TIKTOK": "🎵 TIKTOK", "TWITTER": "🐦 TWITTER",
        "SNAPCHAT": "👻 SNAPCHAT", "WHATSAPP": "🟢 WHATSAPP", "TELEGRAM": "✈️ TELEGRAM", "DISCORD": "👾 DISCORD",
        "MESSENGER": "💬 MESSENGER", "LINKEDIN": "💼 LINKEDIN", "GOOGLE": "📨 GOOGLE", "AMAZON": "🛒 AMAZON",
        "MICROSOFT": "💻 MICROSOFT", "YAHOO": "🟣 YAHOO", "PAYPAL": "💳 PAYPAL", "BINANCE": "🔶 BINANCE",
        "COINBASE": "🔵 COINBASE", "SPOTIFY": "🎧 SPOTIFY", "NETFLIX": "🎬 NETFLIX", "UBER": "🚗 UBER",
        "APPLE": "🍎 APPLE", "BKASH": "🌸 BKASH", "NAGAD": "🍊 NAGAD", "STRIPE": "💳 STRIPE",
        "LINE": "🟢 LINE", "WECHAT": "💬 WECHAT", "VIBER": "🟣 VIBER", "SIGNAL": "💬 SIGNAL",
        "PUBG": "🎮 PUBG", "FREE FIRE": "🔥 FREE FIRE",
    }
    return SERVICE_LOGOS.get(service_upper, f"📩 {service_upper}")

# ==================== ADVANCED BOT BUTTON BUILDERS ====================

def make_keyboard_button(text, style=None, emoji_key=None):
    custom_id = get_dynamic_emoji_id(emoji_key) if emoji_key else None
    if custom_id and custom_id != "your_emoji_id_here" and custom_id.strip() != "":
        btn_text = strip_emoji(text)
        return KeyboardButton(text=btn_text, style=style, icon_custom_emoji_id=custom_id)
    return KeyboardButton(text=text, style=style)

def make_inline_keyboard_button(text, callback_data=None, url=None, style=None, emoji_key=None):
    custom_id = get_dynamic_emoji_id(emoji_key) if emoji_key else None
    has_custom = custom_id and custom_id != "your_emoji_id_here" and custom_id.strip() != ""
    
    if has_custom:
        btn_text = strip_emoji(text)
        # প্রিমিয়াম ইমোজি দেওয়া থাকলে সাধারণ পতাকা ও রিজিওনাল ইন্ডিকেটর টেক্সট থেকে বাদ দেওয়া হয়
        btn_text = re.sub(r'[\U0001F1E6-\U0001F1FF]', '', btn_text).strip()
    else:
        btn_text = text
    
    if url:
        if has_custom:
            return InlineKeyboardButton(text=btn_text, url=url, style=style, icon_custom_emoji_id=custom_id)
        return InlineKeyboardButton(text=btn_text, url=url, style=style)
    else:
        if has_custom:
            return InlineKeyboardButton(text=btn_text, callback_data=callback_data, style=style, icon_custom_emoji_id=custom_id)
        return InlineKeyboardButton(text=btn_text, callback_data=callback_data, style=style)

# ==================== SYSTEM KEYBOARDS ====================

def main_keyboard(user_id):
    lang = get_user_lang(user_id)
    
    get_num_lbl = get_dynamic_button_label("GET_NUMBER", lang)
    traffic_lbl = get_dynamic_button_label("TRAFFIC", lang)
    twofa_lbl = get_dynamic_button_label("2FA", lang)
    support_lbl = get_dynamic_button_label("SUPPORT", lang)
    refer_lbl = get_dynamic_button_label("REFER", lang)
    profile_lbl = get_dynamic_button_label("PROFILE", lang)
    lang_lbl = get_dynamic_button_label("LANG", lang)
    
    keyboard = [
        [
            make_keyboard_button(text=get_num_lbl, style="primary", emoji_key="GET_NUMBER"), 
            make_keyboard_button(text=traffic_lbl, style="success", emoji_key="TRAFFIC")
        ],
        [
            make_keyboard_button(text=twofa_lbl, style="primary", emoji_key="2FA"), 
            make_keyboard_button(text=support_lbl, style="primary", emoji_key="SUPPORT")
        ],
        [
            make_keyboard_button(text=refer_lbl, style="success", emoji_key="REFER"), 
            make_keyboard_button(text=profile_lbl, style="primary", emoji_key="PROFILE")
        ],
        [
            make_keyboard_button(text=lang_lbl, style="primary", emoji_key="LANG") # ট্রান্সলেট ল্যাঙ্গুয়েজ বাটন
        ]
    ]
    if is_admin(user_id):
        keyboard.append([make_keyboard_button(text="⚙️ ADMIN PANEL ⚙️", style="danger")])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def cancel_keyboard(user_id):
    lang = get_user_lang(user_id)
    btn_lbl = "🛑 CANCEL" if lang == "en" else "🛑 বাতিল"
    return ReplyKeyboardMarkup([[make_keyboard_button(text=btn_lbl, style="danger", emoji_key="CLOSE")]], resize_keyboard=True)

def admin_main_keyboard():
    keyboard = [
        [make_keyboard_button("👥 USER MANAGEMENT", style="primary")],
        [make_keyboard_button("⚙️ SYSTEM CONFIGURATION", style="primary")],
        [make_keyboard_button("🔙 BACK TO MAIN", style="danger")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def user_management_keyboard():
    keyboard = [
        [make_keyboard_button("📢 SEND MESSAGE TO ALL USERS", style="success")],
        [make_keyboard_button("🆔 ALL USER ID", style="primary")],
        [make_keyboard_button("📜 BAN USER LIST", style="primary")],
        [make_keyboard_button("💰 ALL USER BALANCE", style="primary")],
        [make_keyboard_button("🔙 BACK TO ADMIN", style="danger")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def system_config_keyboard():
    keyboard = [
        [make_keyboard_button("📈 TODAY ALL STATUS", style="primary"), make_keyboard_button("👤 USER STATUS CHECK", style="primary")],
        [make_keyboard_button("📢 UPDATE JOINS", style="success"), make_keyboard_button("📡 LIVE SERVICES", style="primary")],
        [make_keyboard_button("📝 CUSTOMIZE TEXTS & BUTTONS", style="success")],
        [make_keyboard_button("🗺️ ALL COUNTRY MANAGER", style="success")],
        [make_keyboard_button("📢 SYNC SERVICES TO CHANNEL", style="success")],
        [make_keyboard_button("⛔ BAN USER", style="danger"), make_keyboard_button("🔓 UNBAN USER", style="success")],
        [make_keyboard_button("📜 BAN USER LIST", style="primary")],
        [make_keyboard_button("➖ REMOVE BALANCE", style="danger"), make_keyboard_button("➕ ADD BALANCE", style="success")],
        [make_keyboard_button("🔙 BACK TO ADMIN", style="danger")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def withdraw_method_keyboard(user_id):
    lang = get_user_lang(user_id)
    cancel_lbl = "🛑 CANCEL" if lang == "en" else "🛑 বাতিল"
    
    bkash_lbl = get_dynamic_button_label("BKASH", lang)
    nagad_lbl = get_dynamic_button_label("NAGAD", lang)
    
    keyboard = ReplyKeyboardMarkup([
        [make_keyboard_button(bkash_lbl, style="primary", emoji_key="BKASH"), make_keyboard_button(nagad_lbl, style="primary", emoji_key="NAGAD")],
        [make_keyboard_button(cancel_lbl, style="danger", emoji_key="CLOSE")]
    ], resize_keyboard=True)
    return keyboard

# ==================== EMOJI CAPTCHA VERIFICATION ====================

EMOJI_POOL = ['🍎', '🦊', '🚗', '🥑', '🍕', '⚽', '🎸', '🚀', '🐱', '🐼', '🍩', '🏀']

def generate_emoji_captcha():
    correct = random.sample(EMOJI_POOL, 3)
    correct_str = " ".join(correct)
    options = [correct_str]
    while len(options) < 4:
        wrong = random.sample(EMOJI_POOL, 3)
        wrong_str = " ".join(wrong)
        if wrong_str not in options:
            options.append(wrong_str)
    random.shuffle(options)
    return correct_str, options

async def send_verification_captcha(chat_id, context: ContextTypes.DEFAULT_TYPE, uid):
    correct_ans, options = generate_emoji_captcha()
    context.user_data["captcha_correct"] = correct_ans

    lang = get_user_lang(uid)
    if lang == "bn":
        text = (
            f"🛡️ <b>[ সিকিউরিটি ভেরিফিকেশন ]</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"নিচের ৩-ইমোজি সিকোয়েন্সটি হুবহু মিলিয়ে সঠিক বাটনে ক্লিক করুন:\n"
            f"👉 <code>{correct_ans}</code>"
        )
    else:
        text = (
            f"🛡️ <b>[ SECURITY VERIFICATION ]</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Please match the exact 3-emoji sequence below to proceed:\n"
            f"👉 <code>{correct_ans}</code>"
        )

    buttons = []
    for i, opt in enumerate(options):
        buttons.append([make_inline_keyboard_button(opt, callback_data=f"captcha_opt_{i}")])
    
    context.user_data["captcha_options"] = options
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))

# ==================== UTILITY & STATUS LOG FUNCTIONS ====================

def format_balance(balance):
    return f"{balance:.2f}"

def extract_otp(text):
    if not text or text == "No Content":
        return "N/A"
    spaced_otp = re.search(r'\b(\d{3}\s\d{3})\b', text)
    if spaced_otp:
        return spaced_otp.group(1).replace(" ", "")
    match = re.search(r'\b(\d{4,8})\b', text)
    return match.group(1) if match else "N/A"

def normalize_number(num):
    return re.sub(r'\D', '', str(num))

def mask_number(num):
    if len(num) > 6:
        return f"{num[:4]}****{num[-6:]}"
    return num

def get_date_reset_time():
    now = datetime.now()
    return datetime(now.year, now.month, now.day, 0, 0, 0)

def is_valid_bangladesh_number(number):
    number = re.sub(r'\D', '', str(number))
    return len(number) == 11 and number.startswith('01')

def is_range_request(param):
    return 'X' in param.upper()

def is_referral_request(param):
    return param.isdigit()

def load_stats():
    return load_data(STATS_FILE)

def save_stats(stats):
    save_data(stats, STATS_FILE)

def add_number_taken(uid, count=1):
    uid = str(uid)
    stats = load_stats()
    if uid not in stats:
        stats[uid] = {"numbers_taken": [], "otps_received": []}
    now = datetime.now().isoformat()
    for _ in range(count):
        stats[uid]["numbers_taken"].append(now)
    log_global_activity(uid, "NUMBER_TAKEN", {"count": count})
    save_stats(stats)

def add_otp_received(uid):
    uid = str(uid)
    stats = load_stats()
    if uid not in stats:
        stats[uid] = {"numbers_taken": [], "otps_received": []}
    stats[uid]["otps_received"].append(datetime.now().isoformat())
    save_stats(stats)

def get_user_stats(uid):
    uid = str(uid)
    stats = load_stats()
    user_stats = stats.get(uid, {"numbers_taken": [], "otps_received": []})
    now = datetime.now()
    today_midnight = get_date_reset_time()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    numbers_taken = user_stats.get("numbers_taken", [])
    otps_received = user_stats.get("otps_received", [])
    today_numbers = sum(1 for t in numbers_taken if datetime.fromisoformat(t) >= today_midnight)
    today_otps = sum(1 for t in otps_received if datetime.fromisoformat(t) >= today_midnight)
    last24h_numbers = sum(1 for t in numbers_taken if datetime.fromisoformat(t) > last_24h)
    last24h_otps = sum(1 for t in otps_received if datetime.fromisoformat(t) > last_24h)
    last7d_numbers = sum(1 for t in numbers_taken if datetime.fromisoformat(t) > last_7d)
    last7d_otps = sum(1 for t in otps_received if datetime.fromisoformat(t) > last_7d)
    return {
        "total_numbers": len(numbers_taken), "total_otps": len(otps_received),
        "today_numbers": today_numbers, "today_otps": today_otps,
        "last24h_numbers": last24h_numbers, "last24h_otps": last24h_otps,
        "last7d_numbers": last7d_numbers, "last7d_otps": last7d_otps
    }

def log_global_activity(uid, action, details):
    if not os.path.exists(ACTIVITY_LOGS_FILE):
        try:
            with open(ACTIVITY_LOGS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Failed to init {ACTIVITY_LOGS_FILE}: {e}")
    try:
        with open(ACTIVITY_LOGS_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except:
        logs = []
    now = datetime.now()
    logs.append({
        "uid": str(uid), "action": action, "details": details,
        "timestamp": now.isoformat(),
        "date": now.strftime("%d/%m/%Y"),
        "time": now.strftime("%H:%M:%S")
    })
    save_data(logs, ACTIVITY_LOGS_FILE)

def get_global_system_stats():
    stats = load_stats()
    now = datetime.now()
    today_midnight = datetime(now.year, now.month, now.day)
    last_7d = now - timedelta(days=7)
    total_n = total_o = today_n = today_o = seven_n = seven_o = 0
    for uid in stats:
        u = stats[uid]
        n_list = u.get("numbers_taken", [])
        o_list = u.get("otps_received", [])
        total_n += len(n_list)
        total_o += len(o_list)
        for t in n_list:
            dt = datetime.fromisoformat(t)
            if dt >= today_midnight: today_n += 1
            if dt >= last_7d: seven_n += 1
        for t in o_list:
            dt = datetime.fromisoformat(t)
            if dt >= today_midnight: today_o += 1
            if dt >= last_7d: seven_o += 1
    return today_n, today_o, seven_n, seven_o, total_n, total_o

# ==================== CHANNEL MEMBERSHIP CHECK ====================

async def check_channel_membership(bot, user_id, channel_id):
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Membership verification failed: {e}")
        return True

# ==================== LEADERBOARD SECTION ====================

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    if is_user_banned(uid):
        await update.message.reply_text(LANG_TEXTS[lang]["banned"], reply_markup=main_keyboard(uid))
        return
    stats_data = load_stats()
    today_midnight = get_date_reset_time()
    user_data_all = load_data(USER_DATA_FILE)
    user_today_counts = []
    for uid_str, user_stats in stats_data.items():
        otps_received = user_stats.get("otps_received", [])
        today_count = sum(1 for ts in otps_received if datetime.fromisoformat(ts) >= today_midnight)
        if today_count > 0:
            name = user_data_all.get(uid_str, {}).get("full_name") or user_data_all.get(uid_str, {}).get("username") or f"User {uid_str}"
            user_today_counts.append((uid_str, today_count, html.escape(name)))
    user_today_counts.sort(key=lambda x: x[1], reverse=True)
    top10 = user_today_counts[:10]

    traffic_title = get_dynamic_message_text("TRAFFIC", lang)
    if not traffic_title:
        title = "🏆 <b>TOP 10 OTP LEADERBOARD</b> 🏆\n━━━━━━━━━━━━━━━━━━━━━━\n\n" if lang == "en" else "🏆 <b>টপ ১০ ওটিপি লিডারবোর্ড</b> 🏆\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    else:
        title = traffic_title

    if not top10:
        msg = title + ("🛑 No decrypted OTP entries recorded today." if lang == "en" else "🛑 আজ এখনও কেউ ওটিপি পায়নি।")
    else:
        msg = title
        for idx, (uid_str, count, name) in enumerate(top10, 1):
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}️⃣"
            msg += f"{medal} <b>{name}</b> → 🔑 <code>{count}</code> OTPs\n"
        msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n" + ("📊 <i>Resets at midnight automatically.</i>" if lang == "en" else "📊 <i>প্রতিদিন রাত ১২ টায় স্বয়ংক্রিয়ভাবে রিসেট হয়।</i>")

    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=main_keyboard(uid))

# ==================== 2FA CODE GENERATOR SECTION ====================

def generate_2fa_code(secret_key):
    try:
        clean_secret = secret_key.replace(" ", "").strip()
        totp = pyotp.TOTP(clean_secret)
        return totp.now(), clean_secret
    except:
        return None, None

async def get_2fa_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    if is_user_banned(uid):
        await update.message.reply_text(LANG_TEXTS[lang]["banned"], reply_markup=main_keyboard(uid))
        return
    context.user_data["mode"] = "get_2fa"
    
    twofa_txt = get_dynamic_message_text("2FA", lang)
    if not twofa_txt:
        twofa_txt = LANG_TEXTS[lang]["get_2fa_prompt"]
        
    await update.message.reply_text(
        twofa_txt,
        parse_mode="HTML",
        reply_markup=cancel_keyboard(uid)
    )

async def process_2fa_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    secret_key = update.message.text.strip()
    context.user_data["mode"] = None
    otp_code, clean_key = generate_2fa_code(secret_key)
    if otp_code is None:
        await update.message.reply_text(
            LANG_TEXTS[lang]["2fa_invalid"],
            parse_mode="HTML",
            reply_markup=main_keyboard(uid)
        )
        return
    now = datetime.now()
    final_msg = (
        f"⏳ <b>[ 2FA DECRYPTION COMPLETE ]</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<blockquote>🔑 SECRET_KEY: <code>{clean_key}</code></blockquote>\n"
        f"<blockquote>🔢 PIN_CODE: <code>{otp_code}</code></blockquote>\n"
        f"<blockquote>⏳ EXPIRES_IN: 30 SECONDS</blockquote>\n\n"
        f"📅 {now.strftime('%d %B, %Y')} | {now.strftime('%I:%M %p')}"
    )
    await update.message.reply_text(final_msg, parse_mode="HTML", reply_markup=main_keyboard(uid))

# ==================== GET NUMBER INTERFACE ====================

def filter_important_services(services):
    filtered = []
    sc = load_sys_config()
    active_map = sc.get("active_services", {})

    for svc in services:
        sid = svc.get("sid", "").strip().upper()
        if not sid:
            continue
            
        if active_map.get(sid, True):
            svc_copy = dict(svc)
            logo_and_name = get_service_logo(sid)
            
            if logo_and_name == "📩 SMS SERVICE" or logo_and_name.startswith("📩"):
                logo_and_name = f"📱 {sid}"
                
            svc_copy["display_name"] = logo_and_name
            svc_copy["matched_key"] = sid  
            filtered.append(svc_copy)
            
    return filtered

def _build_services_keyboard(services, user_id):
    buttons = []
    for i, svc in enumerate(services):
        sid = svc.get("sid", "").strip()
        display_name = svc.get("display_name", sid)
        emoji_key = svc.get("matched_key")
        
        buttons.append([
            make_inline_keyboard_button(display_name, callback_data=f"svc_{i}", style="primary", emoji_key=emoji_key)
        ])
        
    buttons.append([
        make_inline_keyboard_button("❌ Close", callback_data="close_menu", style="danger", emoji_key="CLOSE")
    ])
    return InlineKeyboardMarkup(buttons)

def _build_countries_keyboard(ranges, sid, user_id):
    lang = get_user_lang(user_id)
    btns = []
    seen = {}
    for i, r in enumerate(ranges[:24]):
        prefix = re.sub(r'[xX]+$', '', str(r)).strip()
        prefix_clean = re.sub(r'\D', '', prefix)
        flag, cname = get_country_info(prefix_clean)
        label = f"{flag} {cname}"
        
        emoji_key = f"COUNTRY_{prefix_clean}"
        if label not in seen:
            seen[label] = i
            callback_data = f"rng_{i}"
            # কান্ট্রিতে ডাইনামিক প্রিমিয়াম ইমোজি সেট করা থাকলে তা পাঠানো হয়
            if is_premium_emoji_set(emoji_key):
                btns.append(make_inline_keyboard_button(label, callback_data=callback_data, style="primary", emoji_key=emoji_key))
            else:
                btns.append(make_inline_keyboard_button(label, callback_data=callback_data, style="primary"))
                
    rows = [btns[j:j+2] for j in range(0, len(btns), 2)]
    back_lbl = "◀️ BACK" if lang == "en" else "◀️ ফিরে যান"
    rows.append([make_inline_keyboard_button(back_lbl, callback_data="back_services", style="danger")])
    return InlineKeyboardMarkup(rows)

async def show_app_selection(update, context):
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    if is_user_banned(uid):
        await update.message.reply_text(LANG_TEXTS[lang]["banned"], reply_markup=main_keyboard(uid))
        return
    services = get_cached_services()
    if not services:
        await _do_liveaccess_fetch()
        services = get_cached_services()
    if not services:
        err_msg = (
            "⚠️ <b>[ ACCESS FAIL ]</b>\n\n⏳ Server modules are currently sleeping. Retry in a few seconds."
            if lang == "en" else "⚠️ <b>[ সংযোগ ব্যর্থ ]</b>\n\n⏳ সার্ভার মডিউল বর্তমানে অফলাইন রয়েছে। কিছু সেকেন্ড পর চেষ্টা করুন।"
        )
        await update.message.reply_text(err_msg, parse_mode="HTML", reply_markup=main_keyboard(uid))
        return
        
    filtered_services = filter_important_services(services)
    context.user_data["la_services"] = filtered_services
    keyboard = _build_services_keyboard(filtered_services, uid)
    
    get_num_txt = get_dynamic_message_text("GET_NUMBER", lang)
    if not get_num_txt:
        get_num_txt = LANG_TEXTS[lang]["get_active_node"]
        
    await update.message.reply_text(
        get_num_txt,
        parse_mode="HTML",
        reply_markup=keyboard
    )

# ==================== SYNC SERVICES TO CHANNEL ====================
async def sync_services_to_channel(bot, channel_id, lang="bn"):
    services = get_cached_services()
    if not services:
        await _do_liveaccess_fetch()
        services = get_cached_services()
    if not services:
        return "❌ No services cached in database to post."
    
    filtered = filter_important_services(services)
    if not filtered:
        return "❌ Active services filter returned empty."

    text = "📡 <b>[ LIVE SYSTEM NODES & COUNTRIES ]</b> 📡\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for svc in filtered:
        sid = svc.get("sid", "").strip().upper()
        display_name = get_service_logo(sid)
        ranges = svc.get("ranges", [])
        
        country_list = []
        for r in ranges[:12]:
            prefix = re.sub(r'[xX]+$', '', str(r)).strip()
            prefix_clean = re.sub(r'\D', '', prefix)
            flag, cname = get_country_info(prefix_clean)
            country_list.append(f"{flag} {cname} (<code>{prefix}XXX</code>)")
        
        countries_str = ", ".join(country_list) if country_list else "None"
        text += f"📱 <b>{display_name}</b>\n🌍 Range Nodes:\n   └─ {countries_str}\n\n"
        
    text += "━━━━━━━━━━━━━━━━━━━━━━\n📢 <i>Updated automatically via admin console.</i>"
    
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        try:
            await bot.send_message(chat_id=channel_id, text=chunk, parse_mode="HTML")
        except Exception as e:
            return f"❌ Failed to send block: {e}"
    return f"✅ Successfully synchronized {len(filtered)} services & nodes with the channel!"


# ==================== PAGINATED ALL COUNTRY LAYOUT GENERATOR ====================

def _build_all_countries_keyboard(page=0):
    items_per_page = 8
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    subset = COMMON_PREFIXES[start_idx:end_idx]
    
    btns = []
    for pref in subset:
        flag, name = get_country_info(pref)
        emoji_key = f"COUNTRY_{pref}"
        if is_premium_emoji_set(emoji_key):
            btns.append(make_inline_keyboard_button(f"{flag} {name} (+{pref})", callback_data=f"ac_edit_{pref}", emoji_key=emoji_key))
        else:
            btns.append(make_inline_keyboard_button(f"{flag} {name} (+{pref})", callback_data=f"ac_edit_{pref}"))
        
    rows = [btns[i:i+2] for i in range(0, len(btns), 2)]
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(make_inline_keyboard_button("◀️ Prev", callback_data=f"ac_all_list_{page-1}"))
    if end_idx < len(COMMON_PREFIXES):
        nav_buttons.append(make_inline_keyboard_button("Next ▶️", callback_data=f"ac_all_list_{page+1}"))
        
    if nav_buttons:
        rows.append(nav_buttons)
        
    rows.append([
        make_inline_keyboard_button("⌨️ Manual Prefix Input", callback_data="ac_custom_prefix_input"),
        make_inline_keyboard_button("◀️ Back", callback_data="ac_main")
    ])
    return InlineKeyboardMarkup(rows)


# ==================== AUTO MONITOR LOOP (DECRYPTER) ====================

async def monitor_loop(app):
    while True:
        try:
            r = await client_async.get(f"{BASE_URL}/api/success-otp-info")
            res = r.json()
            if "data" in res and "otps" in res["data"]:
                otps = res["data"]["otps"]
                paid_data = load_data(PAID_SMS_FILE)
                range_db = load_data(DATA_RANGE_FILE)
                paid_keys_set = set(paid_data.keys())
                processed_in_session = set()

                for otp in otps:
                    num = normalize_number(otp.get("number", ""))
                    full_sms = otp.get('message') or otp.get('otp') or otp.get('sms') or "No SMS Content"
                    otp_code = extract_otp(full_sms)
                    otp_id = str(otp.get("otp_id", ""))
                    sms_key = otp_id if otp_id else f"{num}_{full_sms}"

                    if (num in active_numbers and
                            sms_key not in paid_keys_set and
                            sms_key not in processed_in_session):

                        details = active_numbers[num]
                        paid_keys_set.add(sms_key)
                        processed_in_session.add(sms_key)
                        paid_data[sms_key] = {"uid": details["uid"], "otp": otp_code}

                        await update_db_balance(details["uid"], OTP_RATE)
                        add_otp_received(details["uid"])
                        log_global_activity(details["uid"], "OTP_RECEIVED", {"number": num, "otp": otp_code, "sms": full_sms})

                        num_range_info = range_db.get(num, {}).get("range", "")
                        if not num_range_info:
                            num_range_info = active_numbers.get(num, {}).get("range", "")
                        if not num_range_info and num:
                            _d = re.sub(r'\D', '', str(num))
                            num_range_info = (_d[:-3] + 'XXX') if len(_d) > 3 else (_d + 'XXX')

                        country_flag, country_name = get_country_info(num)
                        service_name = detect_service(full_sms)
                        service_logo = get_service_logo(service_name)
                        clean_num = num.replace('+', '').strip()
                        full_number = f"+{clean_num}"
                        masked_number = f"+{mask_number(clean_num)}"

                        safe_full_sms = html.escape(str(full_sms))
                        safe_otp_code = html.escape(str(otp_code))

                        # Page 4 OTP সফল রিসিভ মেসেজ কাস্টমাইজেশন লোড করা
                        lang = get_user_lang(details["uid"])
                        success_template = get_dynamic_message_text("DECRYPTION_SUCCESS", lang)
                        packet_text = f"\n\n<blockquote>📩 <b>FULL PACKET:</b>\n<code>{safe_full_sms}</code></blockquote>"
                        
                        if not success_template:
                            user_msg = (
                                f"🛰️ <b>[ INCOMING PACKET DECRYPTED ]</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                f"🛰️ <b>NODE:</b> <code>{num_range_info}</code>\n"
                                f"🌍 <b>ORIGIN:</b> <code>{country_flag} {country_name}</code>\n"
                                f"📲 <b>TARGET:</b> <code>{service_logo}</code>\n"
                                f"📟 <b>ADDR:</b> <code>{full_number}</code>\n"
                                f"🔑 <b>KEY:</b> <code>{safe_otp_code}</code>\n"
                                f"{packet_text}\n"
                                f"🪙 <b>Rewarded +{OTP_RATE:.2f} BDT to Wallet!</b>"
                            )
                        else:
                            try:
                                user_msg = success_template.format(
                                    country_info=f"{country_flag} {country_name}",
                                    range_text=num_range_info,
                                    service_logo=service_logo,
                                    clean_num=clean_num,
                                    otp_safe=safe_otp_code,
                                    packet_text=packet_text
                                ) + f"\n🪙 <b>Rewarded +{OTP_RATE:.2f} BDT to Wallet!</b>"
                            except Exception as e:
                                user_msg = f"🛰️ <b>[ DECRYPTED ]</b> <code>{full_number}</code> | OTP: <code>{safe_otp_code}</code>"

                        group_msg = (
                            f"🛰️ <b>[ INCOMING PACKET DECRYPTED ]</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"🛰️ <b>NODE:</b> <code>{num_range_info}</code>\n"
                            f"🌍 <b>ORIGIN:</b> <code>{country_flag} {country_name}</code>\n"
                            f"📲 <b>TARGET:</b> <code>{service_logo}</code>\n"
                            f"📟 <b>ADDR:</b> <code>{masked_number}</code>\n"
                            f"🔑 <b>KEY:</b> <code>{safe_otp_code}</code>\n\n"
                            f"<blockquote>📩 <b>FULL PACKET:</b>\n<code>{safe_full_sms}</code></blockquote>"
                        )

                        group_buttons = InlineKeyboardMarkup([
                            [
                                make_inline_keyboard_button("🤖 PANEL", url="https://t.me/Topotp3833767_bot", style="primary"),
                                make_inline_keyboard_button("📢 CHANNEL", url="https://t.me/wertyu34567", style="success")
                            ]
                        ])

                        try:
                            await app.bot.send_message(details["uid"], user_msg, parse_mode="HTML")
                        except Exception as e:
                            print(f"❌ User Message Send Fail: {e}")

                        try:
                            await app.bot.send_message(OTP_GROUP_ID, group_msg, parse_mode="HTML", reply_markup=group_buttons)
                        except Exception as e:
                            print(f"❌ Group Send Fail: {e}")

                        save_data(paid_data, PAID_SMS_FILE)

                current_time = datetime.now()
                for num_key in list(active_numbers.keys()):
                    entry = active_numbers[num_key]
                    if 'timestamp' not in entry:
                        entry['timestamp'] = current_time
                    elif (current_time - entry['timestamp']).total_seconds() > 3600:
                        del active_numbers[num_key]

        except Exception as e:
            print(f"Monitor Error: {e}")
        await asyncio.sleep(CHECK_INTERVAL)


# ==================== FETCH NODES WORKERS (DIP-LINK RECOVERY) ====================

async def fetch_number_async(range_str):
    try:
        r = await client_async.post(
            f"{BASE_URL}/api/getnum",
            json={"range": range_str, "is_national": False}
        )
        print(f"[getnum] Request Range: {range_str}")
        print(f"[getnum] HTTP Status: {r.status_code}")
        
        data = r.json()
        print(f"[getnum] Response Data: {data}")
        
        if "message" in data:
            print(f"[getnum] API Response Message: {data['message']}")
            
        d = data.get("data") if isinstance(data.get("data"), dict) else {}
        number = d.get("full_number") or d.get("number") or data.get("number") or data.get("full_number")
        
        if number:
            return {
                "number":  number,
                "otp_now": bool(d.get("otp_now") or data.get("otp_now", False)),
                "otp":     d.get("otp") or data.get("otp"),
                "sms":     d.get("sms") or data.get("sms"),
            }
    except Exception as e:
        print(f"Fetch number error: {e}")
    return None


async def fast_allocate_number(query, context, range_text, sid):
    uid = query.from_user.id
    lang = get_user_lang(uid)
    if is_user_banned(uid):
        await query.message.edit_text(LANG_TEXTS[lang]["banned"])
        return
    try:
        res = await fetch_number_async(range_text)
    except Exception as e:
        await query.message.edit_text(f"❌ Server error: {str(e)[:100]}")
        return
    if not res or not res.get("number"):
        await query.message.edit_text(
            LANG_TEXTS[lang]["node_alloc_fail"],
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                make_inline_keyboard_button("◀️ BACK", callback_data="back_services", style="danger")
            ]])
        )
        return

    clean_num = normalize_number(res["number"])
    add_number_taken(uid, 1)
    last_range[uid] = range_text
    last_sid[uid] = sid # PERSIST THE EXACT SERVICE ID CONTEXT
    active_numbers[clean_num] = {"uid": uid, "range": range_text, "timestamp": datetime.now()}
    save_number_range_info(uid, clean_num, range_text)

    country_flag, country_name = get_country_info(clean_num)
    service_logo = get_service_logo(sid if sid else "SMS SERVICE")

    # ওটিপি ইনস্ট্যান্টলি ডিক্রিপ্ট হলে (Page 4 Message)
    if res.get("otp_now") and res.get("otp"):
        otp_safe = html.escape(str(res["otp"]))
        sms_safe = html.escape(str(res.get("sms") or ""))
        add_otp_received(uid)
        
        success_template = get_dynamic_message_text("DECRYPTION_SUCCESS", lang)
        packet_text = f"\n\n<blockquote>📩 PACKET: <code>{sms_safe}</code></blockquote>" if sms_safe else ""
        if not success_template:
            text = (
                f"🛰️ <b>[ NODE DECRYPTED SUCCESSFULLY ]</b> 🛰️\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🌍 <b>ORIGIN:</b> <code>{country_flag} {html.escape(country_name)}</code>\n"
                f"🛰️ <b>NODE:</b> <code>{range_text}</code>\n"
                f"📱 <b>TARGET:</b> <code>{service_logo}</code>\n"
                f"📟 <b>ADDR:</b> <code>+{clean_num}</code>\n"
                f"🔑 <b>KEY:</b> <code>{otp_safe}</code>"
                + packet_text
            )
        else:
            try:
                text = success_template.format(
                    country_info=f"{country_flag} {html.escape(country_name)}",
                    range_text=range_text,
                    service_logo=service_logo,
                    clean_num=clean_num,
                    otp_safe=otp_safe,
                    packet_text=packet_text
                )
            except Exception as e:
                text = f"🛰️ <b>[ DECRYPTED ]</b> <code>+{clean_num}</code> | OTP: <code>{otp_safe}</code>"
    # ওটিপি এর জন্য অপেক্ষমাণ থাকলে (Page 3 Message)
    else:
        pending_template = get_dynamic_message_text("ALLOCATION_PENDING", lang)
        if not pending_template:
            text = (
                f"🛰️ <b>[ CYBER-NODE ALLOCATION ]</b> 🛰️\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🌍 <b>ORIGIN:</b> <code>{country_flag} {html.escape(country_name)}</code>\n"
                f"🛰️ <b>NODE:</b> <code>{range_text}</code>\n"
                f"📱 <b>TARGET:</b> <code>{service_logo}</code>\n"
                f"📟 <b>ADDR:</b> <code>+{clean_num}</code>\n\n"
                f"📡 <b>SCAN STATUS: ⏳ SCANNING FOR DATA...</b>"
            )
        else:
            try:
                text = pending_template.format(
                    country_info=f"{country_flag} {html.escape(country_name)}",
                    range_text=range_text,
                    service_logo=service_logo,
                    clean_num=clean_num
                )
            except Exception as e:
                text = f"🛰️ <b>[ SCANNING... ]</b> <code>+{clean_num}</code>"

    keyboard = InlineKeyboardMarkup([
        [make_inline_keyboard_button("🔄 SAME RANGE", callback_data="same_range", style="success")],
        [make_inline_keyboard_button("📢 OTP GROUP", url="https://t.me/topotp76", style="primary")]
    ])
    try:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        print(f"fast_allocate edit error: {e}")

async def worker():
    while True:
        task = await request_queue.get()
        try:
            if task['type'] == 'process_numbers':
                await process_numbers(task['update'], task['context'], task['range_text'], task['count'], task.get('sid'))
            elif task['type'] == 'search_otp':
                await perform_otp_search(task['update'], task['context'], task['target_num'])
            elif task['type'] == 'auto_number':
                await process_auto_number(task['update'], task['context'], task['range_text'])
        except Exception as e:
            print(f"Worker Error: {e}")
        finally:
            request_queue.task_done()

# ==================== DEEP LINK AUTO ALLOCATION ====================

async def process_auto_number(update, context, range_text):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    lang = get_user_lang(uid)
    if is_user_banned(uid):
        await context.bot.send_message(chat_id=chat_id, text=LANG_TEXTS[lang]["banned"], reply_markup=main_keyboard(uid))
        return
    status_msg = await context.bot.send_message(chat_id=chat_id, text="🔍 INJECTING NODE MODULES...")
    try:
        res = await fetch_number_async(range_text)
        if not res or not res.get("number"):
            await status_msg.edit_text(LANG_TEXTS[lang]["node_alloc_fail"])
            return
        generated_num = normalize_number(res["number"])
        add_number_taken(uid, 1)
        last_range[uid] = range_text
        active_numbers[generated_num] = {"uid": uid, "range": range_text, "timestamp": datetime.now()}
        save_number_range_info(uid, generated_num, range_text)

        country_flag, country_name = get_country_info(generated_num)
        service_logo = get_service_logo("SMS SERVICE")

        # Page 4 SUCCESS Message
        if res.get("otp_now") and res.get("otp"):
            instant_otp = html.escape(str(res["otp"]))
            instant_sms = html.escape(str(res.get("sms") or ""))
            add_otp_received(uid)
            
            success_template = get_dynamic_message_text("DECRYPTION_SUCCESS", lang)
            packet_text = f"\n\n<blockquote>📩 PACKET: <code>{instant_sms}</code></blockquote>" if instant_sms else ""
            if not success_template:
                final_text = (
                    f"🛰️ <b>[ NODE DECRYPTED SUCCESSFULLY ]</b> 🛰️\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🌍 <b>ORIGIN:</b> <code>{country_flag} {country_name}</code>\n"
                    f"🛰️ <b>NODE:</b> <code>{range_text}</code>\n"
                    f"📱 <b>TARGET:</b> <code>{service_logo}</code>\n"
                    f"📟 <b>ADDR:</b> <code>+{generated_num}</code>\n"
                    f"🔑 <b>KEY:</b> <code>{instant_otp}</code>"
                    + packet_text
                )
            else:
                try:
                    final_text = success_template.format(
                        country_info=f"{country_flag} {country_name}",
                        range_text=range_text,
                        service_logo=service_logo,
                        clean_num=generated_num,
                        otp_safe=instant_otp,
                        packet_text=packet_text
                    )
                except Exception as e:
                    final_text = f"🛰️ <b>[ DECRYPTED ]</b> <code>+{generated_num}</code> | OTP: <code>{instant_otp}</code>"
        # Page 3 PENDING Message
        else:
            pending_template = get_dynamic_message_text("ALLOCATION_PENDING", lang)
            if not pending_template:
                final_text = (
                    f"🛰️ <b>[ CYBER-NODE ALLOCATION ]</b> 🛰️\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🌍 <b>ORIGIN:</b> <code>{country_flag} {country_name}</code>\n"
                    f"🛰️ <b>NODE:</b> <code>{range_text}</code>\n"
                    f"📱 <b>TARGET:</b> <code>{service_logo}</code>\n"
                    f"📟 <b>ADDR:</b> <code>+{generated_num}</code>\n\n"
                    f"📡 <b>SCAN STATUS: ⏳ SCANNING FOR DATA...</b>"
                )
            else:
                try:
                    final_text = pending_template.format(
                        country_info=f"{country_flag} {country_name}",
                        range_text=range_text,
                        service_logo=service_logo,
                        clean_num=generated_num
                    )
                except Exception as e:
                    final_text = f"🛰️ <b>[ SCANNING... ]</b> <code>+{generated_num}</code>"

        keyboard = InlineKeyboardMarkup([
            [make_inline_keyboard_button("🔄 SAME RANGE", callback_data="same_range", style="success")],
            [make_inline_keyboard_button("📢 OTP GROUP", url="https://t.me/topotp76", style="primary")]
        ])
        await status_msg.edit_text(final_text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        print(f"Auto Number Error: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)}")

# ==================== MANUALLY TRIGGERED PROCESS ====================

async def process_numbers(update_or_query, context, range_text, count, sid=None):
    if isinstance(update_or_query, Update) and update_or_query.callback_query:
        uid = update_or_query.callback_query.from_user.id
        chat_id = update_or_query.callback_query.message.chat_id
    else:
        uid = update_or_query.effective_user.id
        chat_id = update_or_query.effective_chat.id
    lang = get_user_lang(uid)
    if is_user_banned(uid):
        await context.bot.send_message(chat_id=chat_id, text=LANG_TEXTS[lang]["banned"], reply_markup=main_keyboard(uid))
        return

    status_msg = await context.bot.send_message(chat_id=chat_id, text="🔍 INTRUDING SYSTEM PATHS...")
    try:
        add_number_taken(uid, count)
        last_range[uid] = range_text
        if sid:
            last_sid[uid] = sid
        tasks = [fetch_number_async(range_text) for _ in range(count)]
        results = await asyncio.gather(*tasks)
        valid_results = [r for r in results if r and r.get("number")]

        if not valid_results:
            await status_msg.edit_text("❌ NO NUMBERS FOUND. TRY A VALID RANGE.")
            return

        num_entries = []
        for r in valid_results:
            clean_num = normalize_number(r["number"])
            if clean_num:
                active_numbers[clean_num] = {"uid": uid, "range": range_text, "timestamp": datetime.now()}
                save_number_range_info(uid, clean_num, range_text)
                num_entries.append({
                    "num":     clean_num,
                    "otp_now": r.get("otp_now", False),
                    "otp":     r.get("otp"),
                    "sms":     r.get("sms"),
                })

        country_flag, country_name = get_country_info(num_entries[0]["num"])
        service_logo = get_service_logo(sid if sid else detect_service(range_text))
        num_lines = []
        for entry in num_entries:
            if entry["otp_now"] and entry["otp"]:
                otp_safe = html.escape(str(entry["otp"]))
                sms_safe = html.escape(str(entry.get("sms") or ""))
                add_otp_received(uid)
                line = (
                    f"<blockquote>📟 ADDR: <code>+{entry['num']}</code>\n"
                    f"🔑 KEY: <code>{otp_safe}</code>"
                    + (f"\n📩 PACKET: <code>{sms_safe}</code>" if sms_safe else "")
                    + "</blockquote>"
                )
            else:
                line = f"<blockquote>📟 ADDR: <code>+{entry['num']}</code></blockquote>"
            num_lines.append(line)

        num_list_text = "\n".join(num_lines)
        any_instant = any(e["otp_now"] and e["otp"] for e in num_entries)
        sms_status = "🟢 ACTIVE DECRYPT" if any_instant else "📡 SCAN STATUS: ⏳ SCANNING FOR DATA..."

        final_text = (
            f"🛰️ <b>[ CYBER-NODE ALLOCATION ]</b> 🛰️\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🌍 <b>ORIGIN:</b> <code>{country_flag} {country_name}</code>\n"
            f"🛰️ <b>NODE:</b> <code>{range_text}</code>\n"
            f"📱 <b>TARGET:</b> <code>{service_logo}</code>\n\n"
            f"📋 <b>DECRYPTED CHANNELS:</b>\n"
            f"{num_list_text}\n\n"
            f"<b>{sms_status}</b>"
        )
        keyboard = InlineKeyboardMarkup([
            [make_inline_keyboard_button("🔄 SAME RANGE", callback_data="same_range", style="success")],
            [make_inline_keyboard_button("📢 OTP GROUP", url="https://t.me/topotp76", style="primary")]
        ])
        await status_msg.edit_text(final_text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        print(f"Process Number Error: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)}")

# ==================== PERFORM DECRYPTED OTP SEARCH ====================

async def perform_otp_search(update, context, target_num):
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    if is_user_banned(uid):
        await update.message.reply_text(LANG_TEXTS[lang]["banned"], reply_markup=main_keyboard(uid))
        return
    status_msg = await update.message.reply_text(LANG_TEXTS[lang]["search_otp_searching"])
    try:
        r = await client_async.get(f"{BASE_URL}/api/success-otp-info")
        res = r.json()
        if "data" in res and "otps" in res["data"]:
            all_otps = res["data"]["otps"]
            found_otps = [o for o in all_otps if normalize_number(o.get("number", "")) == target_num]

            if not found_otps:
                await status_msg.delete()
                err_text = LANG_TEXTS[lang]["search_otp_not_found"].format(num=target_num)
                await update.message.reply_text(err_text, parse_mode="Markdown", reply_markup=main_keyboard(uid))
            else:
                await status_msg.delete()
                paid_data = load_data(PAID_SMS_FILE)
                for o in found_otps:
                    full_sms = o.get('message') or o.get('otp') or o.get('sms') or "No Content"
                    otp_code = extract_otp(full_sms)
                    otp_id = str(o.get("otp_id", ""))
                    sms_key = otp_id if otp_id else f"{target_num}_{full_sms}"

                    if sms_key in paid_data:
                        payment_status = "❌ CORE ALREADY HARVESTED" if lang == "en" else "❌ এটি ইতিমধ্যে রিওয়ার্ড করা হয়েছে"
                    else:
                        await update_db_balance(uid, OTP_RATE)
                        add_otp_received(uid)
                        paid_data[sms_key] = {"uid": str(uid), "otp": otp_code}
                        payment_status = f"💵 Reward +{OTP_RATE:.2f} BDT Added to Balance!"

                    save_data(paid_data, PAID_SMS_FILE)
                    country_flag, country_name = get_country_info(target_num)
                    service_name = detect_service(full_sms)
                    service_logo = get_service_logo(service_name)

                    msg = (
                        f"♻️ <b>[ ENCRYPTED DATA RECOVERED ]</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🌍 <b>ORIGIN:</b> <code>{country_flag} {country_name}</code>\n"
                        f"📱 <b>TARGET:</b> <code>{service_logo}</code>\n"
                        f"📟 <b>ADDR:</b> <code>+{target_num}</code>\n"
                        f"🔑 <b>KEY:</b> <code>{html.escape(otp_code)}</code>\n\n"
                        f"<blockquote>📩 <b>FULL SMS PACKET:</b>\n<code>{html.escape(str(full_sms))}</code></blockquote>\n"
                        f"<b>{payment_status}</b>"
                    )
                    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=main_keyboard(uid))
        else:
            await status_msg.edit_text("❌ Database connectivity failure.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

# ==================== REFER AND EARN SECTION ====================

async def refer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    if is_user_banned(uid):
        await update.message.reply_text(LANG_TEXTS[lang]["banned"], reply_markup=main_keyboard(uid))
        return
    bot_info = await context.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={uid}"
    successful_refers = get_referral_count(uid)
    total_reward = float(successful_refers) * REFERRAL_PRICE

    refer_msg = get_dynamic_message_text("REFER", lang)
    if not refer_msg:
        if lang == "bn":
            refer_msg = (
                f"🎁 <b>[ রেফারেল সেন্টার ]</b> 🎁\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<blockquote>👥 সফল রেফারেল: <code>{successful_refers}</code>\n"
                f"🪙 অর্জিত রিওয়ার্ড: <code>{format_balance(total_reward)} BDT</code></blockquote>\n\n"
                f"🔗 <b>আপনার রেফারেল লিংক:</b>\n"
                f"<blockquote><code>{referral_link}</code></blockquote>\n\n"
                f"<i>বন্ধুদের আমন্ত্রণ জানান এবং প্রতিটি আমন্ত্রণে এক্সট্রা রিওয়ার্ড লাভ করুন।</i>"
            )
        else:
            refer_msg = (
                f"🎁 <b>[ REFERRAL PORTAL ]</b> 🎁\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<blockquote>👥 Successful Invites: <code>{successful_refers}</code>\n"
                f"🪙 Harvested Income: <code>{format_balance(total_reward)} BDT</code></blockquote>\n\n"
                f"🔗 <b>YOUR REFERRAL LINK:</b>\n"
                f"<blockquote><code>{referral_link}</code></blockquote>\n\n"
                f"<i>Share and replicate system node access with friends to earn commission.</i>"
            )
    else:
        try:
            refer_msg = refer_msg.format(
                successful_refers=successful_refers,
                total_reward=format_balance(total_reward),
                referral_link=referral_link
            )
        except Exception as e:
            print(f"Format referral custom msg failed: {e}")

    await update.message.reply_text(
        refer_msg,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([[
            make_inline_keyboard_button("👥 INVITED USERS REPORT", callback_data=f"my_ref_{uid}", style="primary")
        ]])
    )

# ==================== WITHDRAWAL FLOW ====================

async def withdraw_method_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    
    normalized = normalize_input_text(text)
    if normalized in M_CANCEL:
        context.user_data["withdraw_mode"] = None
        await update.message.reply_text("❌ TRANSACTION ABORTED", reply_markup=main_keyboard(uid))
        return

    # বিকাশ এবং রকেট/নগদ এর ডাইনামিক লেবেল ভ্যালিডেশন
    bkash_variants = get_normalized_dynamic_labels("BKASH") + ["BKASH"]
    nagad_variants = get_normalized_dynamic_labels("NAGAD") + ["NAGAD"]
    
    if normalized in bkash_variants:
        context.user_data["withdraw_method"] = "BKASH"
        context.user_data["withdraw_mode"] = "amount"
        await update.message.reply_text(
            LANG_TEXTS[lang]["withdraw_amount_prompt"].format(min_val=MIN_WITHDRAW),
            parse_mode="HTML",
            reply_markup=cancel_keyboard(uid)
        )
    elif normalized in nagad_variants:
        context.user_data["withdraw_method"] = "NAGAD"
        context.user_data["withdraw_mode"] = "amount"
        await update.message.reply_text(
            LANG_TEXTS[lang]["withdraw_amount_prompt"].format(min_val=MIN_WITHDRAW),
            parse_mode="HTML",
            reply_markup=cancel_keyboard(uid)
        )
    else:
        await update.message.reply_text("⚠️ Gateway unrecognized!", reply_markup=withdraw_method_keyboard(uid))

async def withdraw_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    
    normalized = normalize_input_text(text)
    if normalized in M_CANCEL:
        context.user_data["withdraw_mode"] = None
        await update.message.reply_text("❌ TRANSACTION ABORTED", reply_markup=main_keyboard(uid))
        return
    try:
        amount = float(text)
    except:
        await update.message.reply_text("⚠️ Invalid numerical value!", reply_markup=cancel_keyboard(uid))
        return
    balance = get_user(uid)['balance']
    if amount < MIN_WITHDRAW or amount > MAX_WITHDRAW:
        await update.message.reply_text(f"📉 RANGE LIMITS: MIN: {MIN_WITHDRAW} BDT | MAX: {MAX_WITHDRAW} BDT", reply_markup=cancel_keyboard(uid))
        return
    if amount > balance:
        await update.message.reply_text("🚫 VALUATION INSUFFICIENT!", reply_markup=cancel_keyboard(uid))
        return
    context.user_data["withdraw_amount"] = amount
    context.user_data["withdraw_mode"] = "number"
    await update.message.reply_text(
        LANG_TEXTS[lang]["withdraw_number_prompt"],
        parse_mode="HTML",
        reply_markup=cancel_keyboard(uid)
    )

async def withdraw_number_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    
    normalized = normalize_input_text(text)
    if normalized in M_CANCEL:
        context.user_data["withdraw_mode"] = None
        await update.message.reply_text("❌ TRANSACTION ABORTED", reply_markup=main_keyboard(uid))
        return
    if not is_valid_bangladesh_number(text):
        await update.message.reply_text("⚠️ FORMAT CONFLICT! MUST BE 017XXXXXXXX", reply_markup=cancel_keyboard(uid))
        return

    method = context.user_data.get("withdraw_method")
    amount = context.user_data.get("withdraw_amount")
    payment_number = text
    payment_id = generate_payment_id()
    context.user_data["temp_withdraw"] = {
        "method": method, "amount": amount,
        "number": payment_number, "payment_id": payment_id
    }
    proposal_msg = LANG_TEXTS[lang]["withdraw_proposed"].format(method=method, num=payment_number, amount=amount)
    
    await update.message.reply_text(
        proposal_msg,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            make_inline_keyboard_button("❌ ABORT", callback_data="withdraw_cancel", style="danger"),
            make_inline_keyboard_button("✅ CONFIRM", callback_data="withdraw_confirm", style="success")
        ]])
    )

async def process_withdraw_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()
    temp_data = context.user_data.get("temp_withdraw")
    if not temp_data:
        await query.message.reply_text("⚠️ TRANSACTION PACKET EXPIRED.", reply_markup=main_keyboard(uid))
        return

    method = temp_data["method"]
    amount = temp_data["amount"]
    payment_number = temp_data["number"]
    payment_id = temp_data["payment_id"]

    await update_db_balance(uid, -amount)
    wr = load_withdraw_requests()
    wr[str(payment_id)] = {
        "user_id": uid, "method": method, "amount": amount,
        "number": payment_number, "payment_id": payment_id,
        "status": "pending", "timestamp": datetime.now().isoformat()
    }
    save_withdraw_requests(wr)

    await query.message.edit_text(
        f"`✅` <b>TRANSACTION FORWARDED TO CORES</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<blockquote>📝 GATEWAY: <code>{method}</code>\n"
        f"📞 TARGET_ADDR: <code>{payment_number}</code>\n"
        f"💰 VALUATION: <code>{format_balance(amount)} BDT</code>\n"
        f"🆔 HASH_ID: <code>{payment_id}</code></blockquote>",
        parse_mode="HTML"
    )
    await context.bot.send_message(uid, "🎉 REQUEST SUBMITTED SUCCESSFULLY!", reply_markup=main_keyboard(uid))

    admin_msg = (
        f"✅ <b>[ NEW WITHDRAW REQUEST ]</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 NODE_USER: <code>{uid}</code>\n"
        f"📝 GATEWAY: <code>{method}</code>\n"
        f"📞 TARGET_ADDR: <code>{payment_number}</code>\n"
        f"💰 VALUATION: <code>{format_balance(amount)} BDT</code>\n"
        f"🆔 HASH_ID: <code>{payment_id}</code>"
    )
    admin_kb = InlineKeyboardMarkup([[
        make_inline_keyboard_button("❌ REJECT", callback_data=f"admin_reject_{payment_id}", style="danger"),
        make_inline_keyboard_button("✅ APPROVE", callback_data=f"admin_approve_{payment_id}", style="success")
    ]])
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(admin_id, admin_msg, parse_mode="HTML", reply_markup=admin_kb)
        except Exception as e:
            print(f"Admin notify fail {admin_id}: {e}")

    context.user_data["temp_withdraw"] = None
    context.user_data["withdraw_mode"] = None

async def process_withdraw_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()
    context.user_data["temp_withdraw"] = None
    context.user_data["withdraw_mode"] = None
    await query.message.edit_text("❌ TRANSACTION TERMINATED")
    await context.bot.send_message(uid, "🔹 SECURE CONTROLS RE-ENGAGED:", reply_markup=main_keyboard(uid))

# ==================== ADMIN PANEL - BACKEND CONTROLS ====================

async def admin_approve_withdraw(update, context, payment_id):
    query = update.callback_query
    await query.answer()
    wr = load_withdraw_requests()
    if payment_id not in wr:
        await query.message.reply_text("⚠️ Request not found.")
        return
    rd = wr[payment_id]
    uid = rd["user_id"]
    method = rd["method"]
    amount = rd["amount"]
    payment_number = rd["number"]
    wr[payment_id]["status"] = "approved"
    save_withdraw_requests(wr)
    try:
        await context.bot.send_message(
            uid,
            f"🎉 <b>[ TRANSACTION DISPATCHED ]</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<blockquote>📝 GATEWAY: <code>{method}</code>\n"
            f"📞 TARGET: <code>{payment_number}</code>\n"
            f"💰 CREDITS: <code>{format_balance(amount)} BDT</code></blockquote>",
            parse_mode="HTML"
        )
    except:
        pass
        
    sc = load_sys_config()
    ch_id = sc.get("official_channel_id")
    if ch_id:
        masked_user = mask_number(str(uid))
        proof_msg = (
            f"💳 <b>[ WITHDRAW SUCCESSFUL ]</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>User Node:</b> <code>{masked_user}</code>\n"
            f"💳 <b>Method:</b> <code>{method}</code>\n"
            f"💰 <b>Amount:</b> <code>{format_balance(amount)} BDT</code>\n"
            f"✅ <b>Status:</b> <code>PAID (SUCCESS)</code>\n\n"
            f"🎉 Congratulations to the user!"
        )
        try:
            await context.bot.send_message(chat_id=ch_id, text=proof_msg, parse_mode="HTML")
        except Exception as e:
            print(f"Failed to post withdraw proof to channel {ch_id}: {e}")

    await query.message.edit_text(f"✅ APPROVED | Node User: {uid} | Val: {format_balance(amount)} BDT")

async def admin_reject_withdraw(update, context, payment_id):
    query = update.callback_query
    await query.answer()
    wr = load_withdraw_requests()
    if payment_id not in wr:
        await query.message.reply_text("⚠️ Request not found.")
        return
    rd = wr[payment_id]
    uid = rd["user_id"]
    amount = rd["amount"]
    wr[payment_id]["status"] = "rejected"
    save_withdraw_requests(wr)
    try:
        await context.bot.send_message(uid, "❌ **[ TRANSACTION DENIED ]**\n\nTransaction rejected by admin core.", parse_mode="Markdown")
    except:
        pass
    await query.message.edit_text(f"❌ REJECTED | Node User: {uid} | Val: {format_balance(amount)} BDT")

async def admin_add_balance_start(update, context):
    context.user_data["add_balance_mode"] = True
    context.user_data["remove_balance_mode"] = False
    await update.message.reply_text("💰 Send target user ID to force inject balance:")

async def admin_remove_balance_start(update, context):
    context.user_data["remove_balance_mode"] = True
    context.user_data["add_balance_mode"] = False
    await update.message.reply_text("💸 Send target user ID to retrieve balance:")

async def process_add_balance_user(update, context):
    uid_to_add = update.message.text.strip()
    if not uid_to_add.isdigit():
        await update.message.reply_text("❌ Invalid ID.")
        return
    uid_to_add_int = int(uid_to_add)
    if not user_exists(uid_to_add_int):
        await update.message.reply_text("❌ User not found.")
        context.user_data["add_balance_mode"] = False
        return
    context.user_data["pending_add_user"] = uid_to_add_int
    await update.message.reply_text("💵 Send amount to inject:")

async def process_remove_balance_user(update, context):
    uid_to_remove = update.message.text.strip()
    if not uid_to_remove.isdigit():
        await update.message.reply_text("❌ Invalid ID.")
        return
    uid_to_remove_int = int(uid_to_remove)
    if not user_exists(uid_to_remove_int):
        await update.message.reply_text("❌ User not found.")
        context.user_data["remove_balance_mode"] = False
        return
    context.user_data["pending_remove_user"] = uid_to_remove_int
    await update.message.reply_text("💸 Send amount to remove:")

async def process_add_balance_amount(update, context):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ Invalid amount.")
        return
    uid = context.user_data.get("pending_add_user")
    if not uid:
        context.user_data["add_balance_mode"] = False
        await update.message.reply_text("⚠️ Session expired.")
        return
    new_balance = await update_db_balance(uid, amount)
    await update.message.reply_text(
        f"✅ **[ BALANCE INJECTED ]**\n🆔 Target User: `{uid}`\n"
        f"💰 Transferred: `{format_balance(amount)} BDT`\n"
        f"📈 New Balance: `{format_balance(new_balance)} BDT`",
        parse_mode="Markdown"
    )
    try:
        await context.bot.send_message(uid, f"🎉 Admin injected `{format_balance(amount)} BDT` credits to your account!\n💵 Wallet Balance: `{format_balance(new_balance)} BDT`", parse_mode="Markdown")
    except:
        pass
    context.user_data["add_balance_mode"] = False
    context.user_data["pending_add_user"] = None

async def process_remove_balance_amount(update, context):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ Invalid amount.")
        return
    uid = context.user_data.get("pending_remove_user")
    if not uid:
        context.user_data["remove_balance_mode"] = False
        await update.message.reply_text("⚠️ Session expired.")
        return
    old_balance = get_user(uid).get("balance", 0)
    if amount > old_balance:
        await update.message.reply_text(f"❌ Target balance only has {format_balance(old_balance)} BDT.")
        context.user_data["remove_balance_mode"] = False
        context.user_data["pending_remove_user"] = None
        return
    new_balance = await update_db_balance(uid, -amount)
    await update.message.reply_text(
        f"✅ **[ BALANCE PURGED ]**\n🆔 Target User: `{uid}`\n"
        f"💸 Deducted: `{format_balance(amount)} BDT`\n"
        f"📈 New Balance: `{format_balance(new_balance)} BDT`",
        parse_mode="Markdown"
    )
    try:
        await context.bot.send_message(uid, f"⚠️ Admin extracted `{format_balance(amount)} BDT` from your account!\n💵 Wallet Balance: `{format_balance(new_balance)} BDT`", parse_mode="Markdown")
    except:
        pass
    context.user_data["remove_balance_mode"] = False
    context.user_data["pending_remove_user"] = None

async def admin_ban_user_start(update, context):
    context.user_data["admin_ban_mode"] = True
    context.user_data["admin_unban_mode"] = False
    await update.message.reply_text("🚫 Send target user ID to enforce BAN status:")

async def admin_unban_user_start(update, context):
    context.user_data["admin_unban_mode"] = True
    context.user_data["admin_ban_mode"] = False
    await update.message.reply_text("🔓 Send target user ID to clear BAN status:")

async def process_ban_user(update, context):
    uid_to_ban = update.message.text.strip()
    if not uid_to_ban.isdigit():
        await update.message.reply_text("❌ Invalid ID.")
        return
    uid_to_ban_int = int(uid_to_ban)
    if not user_exists(uid_to_ban_int):
        await update.message.reply_text("❌ User not found.")
        context.user_data["admin_ban_mode"] = False
        return
    if is_user_banned(uid_to_ban_int):
        await update.message.reply_text("⚠️ Node is already blocked.")
        context.user_data["admin_ban_mode"] = False
        return
    ban_user(uid_to_ban_int)
    try:
        await context.bot.send_message(uid_to_ban_int, "🚫 **Your access profile has been suspended.**", parse_mode="Markdown")
    except:
        pass
    await update.message.reply_text(f"✅ User `{uid_to_ban}` banned successfully!", parse_mode="Markdown", reply_markup=system_config_keyboard())
    context.user_data["admin_ban_mode"] = False

async def process_unban_user(update, context):
    uid_to_unban = update.message.text.strip()
    if not uid_to_unban.isdigit():
        await update.message.reply_text("❌ Invalid ID.")
        return
    uid_to_unban_int = int(uid_to_unban)
    if not is_user_banned(uid_to_unban_int):
        await update.message.reply_text("⚠️ User node is active.")
        context.user_data["admin_unban_mode"] = False
        return
    unban_user(uid_to_unban_int)
    try:
        await context.bot.send_message(uid_to_unban_int, "✅ **Your access profile suspension has been lifted!**", parse_mode="Markdown")
    except:
        pass
    await update.message.reply_text(f"✅ User `{uid_to_unban}` unbanned successfully!", parse_mode="Markdown", reply_markup=system_config_keyboard())
    context.user_data["admin_unban_mode"] = False

async def show_banned_users_list(update, context):
    banned_list = load_banned_users()
    if not banned_list:
        await update.message.reply_text("📜 No banned nodes detected.", reply_markup=system_config_keyboard())
        return
    text = "📜 **BLOCKED SYSTEM NODES**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, uid in enumerate(banned_list, 1):
        text += f"{i}. `{uid}`\n"
    text += f"\n📊 Total: {len(banned_list)}"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=system_config_keyboard())

# ==================== LIVE SERVICES CONTROLLER (ADMIN) ====================

async def show_admin_services_menu(update, context):
    services = get_cached_services()
    if not services:
        await _do_liveaccess_fetch()
        services = get_cached_services()
        
    sc = load_sys_config()
    active_map = sc.get("active_services", {})
    
    sids = sorted(list(set(svc.get("sid", "").strip().upper() for svc in services if svc.get("sid"))))
    
    if not sids:
        sids = ["INSTAGRAM", "TELEGRAM", "WHATSAPP", "FACEBOOK", "TIKTOK"]

    buttons = []
    for key in sids:
        is_active = active_map.get(key, True)  
        status_lbl = "🟢 ON" if is_active else "🔴 OFF"
        btn_txt = f"{key} [{status_lbl}]"
        
        emoji_id = sc.get("service_emojis", {}).get(key, "")
        emoji_indicator = "✨" if emoji_id else "✏️"
        
        buttons.append([
            make_inline_keyboard_button(btn_txt, callback_data=f"toggle_svc_{key}"),
            make_inline_keyboard_button(f"{emoji_indicator} Edit Emoji", callback_data=f"edit_emoji_{key}")
        ])
    
    buttons.append([make_inline_keyboard_button("❌ Close", callback_data="close_menu", style="danger")])
    
    msg_text = (
        "📡 <b>LIVE SERVICES MANAGER</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Click status to toggle, or click edit to set/modify custom Premium Emoji ID for each service:"
    )
    await update.message.reply_text(msg_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))

# ==================== CUSTOM ENGINE: TEXTS & KEYBOARDS SYSTEM ====================

async def show_admin_customizer_menu(update, context):
    sc = load_sys_config()
    custom_buttons = sc.get("custom_buttons", {})
    
    buttons = []
    # কাস্টমাইজার পেজে সব বাটন ও পেজের চমৎকার একক কলাম তালিকা
    for key in custom_buttons.keys():
        display_title = CUSTOMIZER_HUMAN_NAMES.get(key, f"✏️ {key}")
        buttons.append([
            make_inline_keyboard_button(display_title, callback_data=f"cust_select_{key}")
        ])
    buttons.append([make_inline_keyboard_button("❌ Close", callback_data="close_menu", style="danger")])
    
    msg_text = (
        "📝 <b>SYSTEM CUSTOMIZER ENGINE</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "নিচের যে বাটন বা টেক্সটটি এডিট করতে চান—তা সিলেক্ট করুন:"
    )
    await update.message.reply_text(msg_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))

# ==================== MAIN CORE MESSAGE HANDLER ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    uid = update.effective_user.id
    text = update.message.text.strip()
    lang = get_user_lang(uid)

    normalized_text = normalize_input_text(text)

    if normalized_text in M_CANCEL:
        context.user_data.clear()
        cancel_txt = "❌ OPERATION ABORTED" if lang == "en" else "❌ অপারেশন বাতিল করা হয়েছে"
        await update.message.reply_text(cancel_txt, reply_markup=main_keyboard(uid))
        return

    if not is_admin(uid) and is_user_banned(uid):
        await update.message.reply_text(LANG_TEXTS[lang]["banned"], reply_markup=main_keyboard(uid))
        return

    if not is_user_verified(uid) and not is_admin(uid):
        await send_verification_captcha(update.effective_chat.id, context, uid)
        return

    if context.user_data.get("admin_channel_update_mode") and is_admin(uid):
        context.user_data["admin_channel_update_mode"] = False
        parts = text.split("|")
        if len(parts) != 2:
            await update.message.reply_text("❌ invalid format. Format: `channel_id | invite_link`", parse_mode="Markdown")
            return
        try:
            ch_id = int(parts[0].strip())
            ch_lnk = parts[1].strip()
            
            sc = load_sys_config()
            sc["official_channel_id"] = ch_id
            sc["official_channel_link"] = ch_lnk
            save_sys_config(sc)
            
            await update.message.reply_text(
                f"QA **CHANNEL SYSTEM CONFIGURATIONS UPDATED!**\n\n"
                f"🆔 ID: ` {ch_id} `\n"
                f"🔗 URL: {ch_lnk}",
                parse_mode="Markdown",
                reply_markup=system_config_keyboard()
            )
        except Exception as e:
            await update.message.reply_text(f"❌ config failure: {e}")
        return

    # এডমিন কর্তৃক কাস্টম বাটন/মেসেজ/ইমোজি আপডেট করার লজিক
    if context.user_data.get("admin_customizer_target") and is_admin(uid):
        target = context.user_data["admin_customizer_target"]
        context.user_data["admin_customizer_target"] = None
        
        key = target["key"]
        field = target["field"]
        target_lang = target["lang"]
        
        sc = load_sys_config()
        if key not in sc.get("custom_buttons", {}):
            await update.message.reply_text("❌ Key mismatch error.")
            return
            
        new_val = text
        
        if field == "label":
            sc["custom_buttons"][key]["labels"][target_lang] = new_val
            save_sys_config(sc)
            await update.message.reply_text(
                f"✅ Label ({target_lang.upper()}) updated for <b>{key}</b> to:\n<code>{html.escape(new_val)}</code>",
                parse_mode="HTML",
                reply_markup=system_config_keyboard()
            )
        elif field == "msg":
            sc["custom_buttons"][key]["messages"][target_lang] = new_val
            save_sys_config(sc)
            await update.message.reply_text(
                f"✅ Message ({target_lang.upper()}) updated for <b>{key}</b> to:\n<blockquote>{html.escape(new_val)}</blockquote>",
                parse_mode="HTML",
                reply_markup=system_config_keyboard()
            )
        elif field == "emoji":
            if new_val.lower() == "clear":
                sc["custom_buttons"][key]["emoji_id"] = ""
                save_sys_config(sc)
                await update.message.reply_text(
                    f"✅ Premium Emoji ID cleared for <b>{key}</b>!",
                    parse_mode="HTML",
                    reply_markup=system_config_keyboard()
                )
            else:
                sc["custom_buttons"][key]["emoji_id"] = new_val
                save_sys_config(sc)
                await update.message.reply_text(
                    f"✅ Premium Emoji ID successfully set for <b>{key}</b> to:\n<code>{new_val}</code>",
                    parse_mode="HTML",
                    reply_markup=system_config_keyboard()
                )
        return

    if not is_admin(uid):
        cur_cfg = load_sys_config()
        is_member = await check_channel_membership(context.bot, uid, cur_cfg["official_channel_id"])
        if not is_member:
            await show_join_prompt(update, context, uid)
            return

    if context.user_data.get("withdraw_mode") == "select_method":
        await withdraw_method_selected(update, context)
        return
    if context.user_data.get("withdraw_mode") == "amount":
        await withdraw_amount_received(update, context)
        return
    if context.user_data.get("withdraw_mode") == "number":
        await withdraw_number_received(update, context)
        return

    if context.user_data.get("add_balance_mode") and is_admin(uid):
        if context.user_data.get("pending_add_user"):
            await process_add_balance_amount(update, context)
        else:
            await process_add_balance_user(update, context)
        return
    if context.user_data.get("remove_balance_mode") and is_admin(uid):
        if context.user_data.get("pending_remove_user"):
            await process_remove_balance_amount(update, context)
        else:
            await process_remove_balance_user(update, context)
        return

    if context.user_data.get("admin_ban_mode") and is_admin(uid):
        await process_ban_user(update, context)
        return
    if context.user_data.get("admin_unban_mode") and is_admin(uid):
        await process_unban_user(update, context)
        return

    # কান্ট্রি ওভাররাইড আপডেট করার লজিক (Admin Panel)
    if context.user_data.get("admin_country_override_mode") == "input_prefix" and is_admin(uid):
        prefix = text.replace('+', '').strip()
        if not prefix.isdigit():
            await update.message.reply_text("❌ Prefix must be numbers (e.g. 237). Try again:")
            return
        context.user_data["temp_override_prefix"] = prefix
        context.user_data["admin_country_override_mode"] = "input_flag_name"
        await update.message.reply_text(
            f"🌍 Prefix Selected: <code>{prefix}</code>\n\n"
            "Please send the new flag emoji, country name and optional Premium Emoji ID separated by `|`.\n"
            "Example: <code>🇨🇲 | Cameroon VIP | 5330237710655306682</code>\n\n"
            "<i>(Type <code>clear</code> to remove the override)</i>",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(uid)
        )
        return

    if context.user_data.get("admin_country_override_mode") == "input_flag_name" and is_admin(uid):
        prefix = context.user_data.get("temp_override_prefix")
        context.user_data["admin_country_override_mode"] = None
        
        sc = load_sys_config()
        if "country_overrides" not in sc:
            sc["country_overrides"] = {}
            
        if text.lower() == "clear":
            if prefix in sc["country_overrides"]:
                del sc["country_overrides"][prefix]
            save_sys_config(sc)
            await update.message.reply_text(f"✅ Override for prefix {prefix} cleared!", reply_markup=system_config_keyboard())
            return
            
        parts = text.split("|")
        if len(parts) < 2 or len(parts) > 3:
            await update.message.reply_text("❌ Invalid format. Please use: <code>Flag | Country Name</code> or <code>Flag | Country Name | Premium Emoji ID</code>", parse_mode="HTML")
            return
            
        flag = parts[0].strip()
        name = parts[1].strip()
        emoji_id = parts[2].strip() if len(parts) == 3 else ""
        
        sc["country_overrides"][prefix] = {"flag": flag, "name": name, "emoji_id": emoji_id}
        save_sys_config(sc)
        
        await update.message.reply_text(
            f"✅ <b>Country Override Updated!</b>\n\n"
            f"🌍 Prefix: <code>{prefix}</code>\n"
            f"🚩 Flag: {flag}\n"
            f"🏷️ Name: {name}\n"
            f"✨ Premium Emoji ID: <code>{emoji_id if emoji_id else 'None'}</code>",
            parse_mode="HTML",
            reply_markup=system_config_keyboard()
        )
        return

    # সার্ভিস নাম/লোগো ওভাররাইড আপডেট করার লজিক (Admin Panel)
    if context.user_data.get("admin_service_override_mode") == "input_svc_key" and is_admin(uid):
        svc_key = text.upper().strip()
        context.user_data["temp_override_svc_key"] = svc_key
        context.user_data["admin_service_override_mode"] = "input_logo_name"
        await update.message.reply_text(
            f"📱 Service Key: <code>{svc_key}</code>\n\n"
            "Now please send the new display name with emoji.\n"
            "Example: <code>✈️ TELEGRAM VIP</code>\n\n"
            "<i>(Type <code>clear</code> to remove the override)</i>",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(uid)
        )
        return

    if context.user_data.get("admin_service_override_mode") == "input_logo_name" and is_admin(uid):
        svc_key = context.user_data["temp_override_svc_key"]
        context.user_data["admin_service_override_mode"] = None
        
        sc = load_sys_config()
        if "service_name_overrides" not in sc:
            sc["service_name_overrides"] = {}
            
        if text.lower() == "clear":
            if svc_key in sc["service_name_overrides"]:
                del sc["service_name_overrides"][svc_key]
            save_sys_config(sc)
            await update.message.reply_text(f"✅ Override for service {svc_key} cleared!", reply_markup=system_config_keyboard())
            return
            
        new_logo = text.strip()
        sc["service_name_overrides"][svc_key] = new_logo
        save_sys_config(sc)
        
        await update.message.reply_text(
            f"✅ <b>Service Name/Logo Override Updated!</b>\n\n"
            f"🔑 Key: <code>{svc_key}</code>\n"
            f"🏷️ Display Name: {new_logo}",
            parse_mode="HTML",
            reply_markup=system_config_keyboard()
        )
        return

    if context.user_data.get("admin_edit_emoji_target") and is_admin(uid):
        svc_key = context.user_data["admin_edit_emoji_target"]
        context.user_data["admin_edit_emoji_target"] = None
        
        emoji_id = text.strip()
        sc = load_sys_config()
        if "service_emojis" not in sc:
            sc["service_emojis"] = {}
            
        if emoji_id.lower() == "clear":
            if svc_key in sc["service_emojis"]:
                del sc["service_emojis"][svc_key]
            save_sys_config(sc)
            await update.message.reply_text(
                f"✅ Premium Emoji ID cleared for <b>{svc_key}</b>!",
                parse_mode="HTML",
                reply_markup=system_config_keyboard()
            )
        else:
            sc["service_emojis"][svc_key] = emoji_id
            save_sys_config(sc)
            await update.message.reply_text(
                f"✅ Premium Emoji ID successfully set for <b>{svc_key}</b>!\n\nID: <code>{emoji_id}</code>",
                parse_mode="HTML",
                reply_markup=system_config_keyboard()
            )
        return

    if context.user_data.get("mode") == "custom_range":
        context.user_data["mode"] = None
        range_text = text.strip().upper()
        if not re.search(r'\d', range_text):
            await update.message.reply_text(
                LANG_TEXTS[lang]["invalid_range"],
                parse_mode="HTML",
                reply_markup=main_keyboard(uid)
            )
            return
        await request_queue.put({
            'type': 'process_numbers',
            'update': update,
            'context': context,
            'range_text': range_text,
            'count': 1
        })
        return

    # ==================== DYNAMIC ENGINE ROUTING ====================
    is_get_number = normalized_text in get_normalized_dynamic_labels("GET_NUMBER") or normalized_text in M_GET_NUM
    is_traffic = normalized_text in get_normalized_dynamic_labels("TRAFFIC") or normalized_text in M_TRAFFIC
    is_2fa = normalized_text in get_normalized_dynamic_labels("2FA") or normalized_text in M_2FA
    is_support = normalized_text in get_normalized_dynamic_labels("SUPPORT") or normalized_text in M_SUPPORT
    is_refer = normalized_text in get_normalized_dynamic_labels("REFER") or normalized_text in M_REFER
    is_profile = normalized_text in get_normalized_dynamic_labels("PROFILE") or normalized_text in M_PROFILE
    is_lang = normalized_text in get_normalized_dynamic_labels("LANG") or normalized_text in M_LANG

    # ভাষা পরিবর্তনের বাটন রুট
    if is_lang:
        keyboard = InlineKeyboardMarkup([
            [
                make_inline_keyboard_button("🇺🇸 English", callback_data="set_lang_en", style="primary"),
                make_inline_keyboard_button("🇧🇩 বাংলা", callback_data="set_lang_bn", style="success")
            ]
        ])
        lang_msg = get_dynamic_message_text("LANG", lang)
        if not lang_msg:
            lang_msg = "🌐 <b>Select your language / আপনার ভাষা সিলেক্ট করুন:</b>"
            
        await update.message.reply_text(
            lang_msg,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return

    if is_profile:
        user_data = get_user(uid)
        stats = get_user_stats(uid)
        user = update.effective_user
        full_name = html.escape(user.full_name)
        username = html.escape(user.username or "N/A")

        profile_text = get_dynamic_message_text("PROFILE", lang)
        if not profile_text:
            if lang == "bn":
                profile_text = (
                    f"👤 <b>ইউজার প্রোফাইল</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🏷️ <b>নাম:</b> <code>{full_name}</code>\n"
                    f"🆔 <b>ইউজারনেম:</b> @{username}\n"
                    f"🗝️ <b>ইউজার আইডি:</b> <code>{uid}</code>\n\n"
                    f"💵 <b>ওয়ালেট ব্যালেন্স:</b> <code>{format_balance(user_data.get('balance', 0))} BDT</code>\n\n"
                    f"📊 <b>আজকের স্ট্যাটাস:</b>\n"
                    f"<blockquote>📱 নম্বর নিয়েছেন: <code>{stats['today_numbers']}</code>\n"
                    f"🔑 ওটিপি পেয়েছেন: <code>{stats['today_otps']}</code></blockquote>\n\n"
                    f"🌐 <b>সর্বমোট স্ট্যাটাস:</b>\n"
                    f"<blockquote>📱 নম্বর নিয়েছেন: <code>{stats['total_numbers']}</code>\n"
                    f"🔑 ওটিপি পেয়েছেন: <code>{stats['total_otps']}</code></blockquote>"
                )
            else:
                profile_text = (
                    f"👤 <b>USER PROFILE</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🏷️ <b>Name:</b> <code>{full_name}</code>\n"
                    f"🆔 <b>Username:</b> @{username}\n"
                    f"🗝️ <b>User ID:</b> <code>{uid}</code>\n\n"
                    f"💵 <b>Wallet Balance:</b> <code>{format_balance(user_data.get('balance', 0))} BDT</code>\n\n"
                    f"📊 <b>Today's Stats:</b>\n"
                    f"<blockquote>📱 Numbers taken: <code>{stats['today_numbers']}</code>\n"
                    f"🔑 OTPs received: <code>{stats['today_otps']}</code></blockquote>\n\n"
                    f"🌐 <b>All-time Stats:</b>\n"
                    f"<blockquote>📱 Numbers taken: <code>{stats['total_numbers']}</code>\n"
                    f"🔑 OTPs received: <code>{stats['total_otps']}</code></blockquote>"
                )
        else:
            try:
                profile_text = profile_text.format(
                    full_name=full_name,
                    username=username,
                    uid=uid,
                    balance=format_balance(user_data.get('balance', 0)),
                    today_numbers=stats['today_numbers'],
                    today_otps=stats['today_otps'],
                    total_numbers=stats['total_numbers'],
                    total_otps=stats['total_otps']
                )
            except Exception as e:
                print(f"Format profile custom msg failed: {e}")

        btn_withdraw_lbl = get_dynamic_button_label("WITHDRAW", lang)
        
        withdraw_kb = InlineKeyboardMarkup([[
            make_inline_keyboard_button(btn_withdraw_lbl, callback_data="withdraw_start", style="success", emoji_key="WITHDRAW")
        ]])
        await update.message.reply_text(profile_text, parse_mode="HTML", reply_markup=withdraw_kb)
        return

    if is_refer:
        await refer_command(update, context)
        return

    if is_2fa:
        await get_2fa_code(update, context)
        return

    if is_get_number:
        await show_app_selection(update, context)
        return

    if context.user_data.get("mode") == "get_2fa":
        await process_2fa_key(update, context)
        return

    if is_traffic:
        await leaderboard_command(update, context)
        return

    if is_support:
        support_text = get_dynamic_message_text("SUPPORT", lang)
        if not support_text:
            if lang == "bn":
                support_text = "💬 <b>সাপোর্ট সেন্টার</b> 🎧\n━━━━━━━━━━━━━━━━━━━━━━\n\nযেকোনো সমস্যায় নিচে দেওয়া বাটনগুলোতে ক্লিক করে আমাদের সাথে যোগাযোগ করুন।"
            else:
                support_text = "💬 <b>SUPPORT TERMINAL</b> 🎧\n━━━━━━━━━━━━━━━━━━━━━━\n\nUse the buttons below to establish direct support channels."

        btn_hc = get_dynamic_button_label("HELP_CENTER", lang)
        btn_dev = get_dynamic_button_label("DEV_SUPPORT", lang)

        keyboard = InlineKeyboardMarkup([
            [make_inline_keyboard_button(btn_hc, url=SUPPORT_LINK, style="primary", emoji_key="HELP_CENTER")],
            [make_inline_keyboard_button(btn_dev, url=DEVELOPER_LINK, style="success", emoji_key="DEV_SUPPORT")]
        ])
        await update.message.reply_text(support_text, reply_markup=keyboard, parse_mode="HTML")
        return

    # ==================== ADMIN NAVIGATION MANAGEMENT ====================
    if ("ADMIN PANEL" in normalized_text or "অ্যাডমিন প্যানেল" in normalized_text) and is_admin(uid):
        context.user_data["admin_mode"] = "main"
        await update.message.reply_text(
            "⌬━━━━━━━━━━━━━━━━━━━━⌬\n   WELCOME ADMIN SYSTEM CENTRAL\n⌬━━━━━━━━━━━━━━━━━━━━⌬",
            reply_markup=admin_main_keyboard()
        )
        return

    if "BACK TO MAIN" in normalized_text and context.user_data.get("admin_mode"):
        context.user_data["admin_mode"] = None
        await update.message.reply_text("🔙 Terminated panel system context.", reply_markup=main_keyboard(uid))
        return

    if "BACK TO ADMIN" in normalized_text:
        context.user_data["user_management_mode"] = None
        context.user_data["system_config_mode"] = None
        context.user_data["admin_mode"] = "main"
        await update.message.reply_text("Returned to master gateway.", reply_markup=admin_main_keyboard())
        return

    if "USER MANAGEMENT" in normalized_text and context.user_data.get("admin_mode") == "main" and is_admin(uid):
        context.user_data["user_management_mode"] = "main"
        await update.message.reply_text("👥 User Management Interface:", reply_markup=user_management_keyboard())
        return

    if "SYSTEM CONFIGURATION" in normalized_text and context.user_data.get("admin_mode") == "main" and is_admin(uid):
        context.user_data["system_config_mode"] = "main"
        await update.message.reply_text("⚙️ Core Configurations Enabled:", reply_markup=system_config_keyboard())
        return

    if "TODAY ALL STATUS" in normalized_text and context.user_data.get("system_config_mode") == "main" and is_admin(uid):
        t_n, t_o, s_n, s_o, tot_n, tot_o = get_global_system_stats()
        msg = (
            f"📊 <b>CORE TELEMETRY LOGS</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✨ <b>TODAY LOGS</b>\n📱 NODES FETCHED: {t_n}\n🔑 DECRYPTED OTPS: {t_o}\n\n"
            f"🔥 <b>7D LOGS</b>\n📱 NODES FETCHED: {s_n}\n🔑 DECRYPTED OTPS: {s_o}\n\n"
            f"🌐 <b>CORE ALLTIME LOGS</b>\n📱 NODES FETCHED: {tot_n}\n🔑 DECRYPTED OTPS: {tot_o}"
        )
        await update.message.reply_text(msg, parse_mode="HTML")
        return

    if "UPDATE JOINS" in normalized_text and context.user_data.get("system_config_mode") == "main" and is_admin(uid):
        context.user_data["admin_channel_update_mode"] = True
        await update.message.reply_text(
            "📢 <b>Update Join Verification Configuration:</b>\n\n"
            "Please send Channel ID and Link separated by vertical bar `|`.\n\n"
            "Example:\n` -1001234567890 | https://t.me/example_channel `",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard(uid)
        )
        return

    if "LIVE SERVICES" in normalized_text and context.user_data.get("system_config_mode") == "main" and is_admin(uid):
        await show_admin_services_menu(update, context)
        return

    if "CUSTOMIZE TEXTS & BUTTONS" in normalized_text and context.user_data.get("system_config_mode") == "main" and is_admin(uid):
        await show_admin_customizer_menu(update, context)
        return

    if "EDIT COUNTRY OVERRIDES" in normalized_text and is_admin(uid):
        context.user_data["admin_country_override_mode"] = "input_prefix"
        await update.message.reply_text(
            "🌍 <b>[ COUNTRY OVERRIDES MANAGER ]</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Please send the prefix of the country flag/name you want to override (e.g. 237 or 880):",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(uid)
        )
        return

    if "EDIT SERVICE OVERRIDES" in normalized_text and is_admin(uid):
        context.user_data["admin_service_override_mode"] = "input_svc_key"
        await update.message.reply_text(
            "📱 <b>[ SERVICE OVERRIDES MANAGER ]</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Please send the target service code key (e.g. TELEGRAM, WHATSAPP, FACEBOOK, SMS SERVICE):",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(uid)
        )
        return

    # ALL COUNTRY MANAGER বাটন হ্যান্ডলিং (Admin Interface)
    if "ALL COUNTRY MANAGER" in normalized_text and is_admin(uid):
        buttons = [
            [
                make_inline_keyboard_button("📱 Service & Country", callback_data="ac_svc_list"),
                make_inline_keyboard_button("🌍 All Country List", callback_data="ac_all_list_0")
            ],
            [
                make_inline_keyboard_button("❌ Close Panel", callback_data="close_menu", style="danger")
            ]
        ]
        await update.message.reply_text(
            "🗺️ <b>ALL COUNTRY MANAGER SYSTEM</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select one of the configurations below to customize custom fonts, prefixes, or Premium Animated Emojis:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if "SYNC SERVICES TO CHANNEL" in normalized_text and is_admin(uid):
        sc = load_sys_config()
        ch_id = sc.get("official_channel_id")
        if not ch_id:
            await update.message.reply_text("❌ Official Channel ID not set in system config.")
            return
        status = await sync_services_to_channel(context.bot, ch_id, lang)
        await update.message.reply_text(status)
        return

    if "USER STATUS CHECK" in normalized_text and is_admin(uid):
        context.user_data["mode"] = "input_user_id"
        await update.message.reply_text("🔍 INPUT USER TELEGRAM ID PROTOCOL:", reply_markup=cancel_keyboard(uid))
        return

    if context.user_data.get("mode") == "input_user_id" and is_admin(uid):
        target_uid = text.strip()
        if not target_uid.isdigit():
            await update.message.reply_text("❌ INVALID NUMERIC FORMAT!")
            return
        context.user_data["mode"] = None
        stats = get_user_stats(target_uid)
        msg = (
            f"👤 <b>NODE TELEMETRY CHECK</b> — <code>{target_uid}</code>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✨ TODAY: 📱 {stats['today_numbers']} | 🔑 {stats['today_otps']}\n"
            f"🔥 7 DAYS: 📱 {stats['last7d_numbers']} | 🔑 {stats['last7d_otps']}\n"
            f"🌐 ALL TIME: 📱 {stats['total_numbers']} | 🔑 {stats['total_otps']}"
        )
        await update.message.reply_text(
            msg, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                make_inline_keyboard_button("📂 PARSE DUMPED DATA PACKETS", callback_data=f"full_logs_{target_uid}", style="primary")
            ]])
        )
        return

    if "ALL USER ID" in normalized_text and context.user_data.get("user_management_mode") == "main" and is_admin(uid):
        users = get_all_users()
        if users:
            content = "\n".join(f"{i}. {u}" for i, u in enumerate(users, 1))
            f = io.BytesIO(content.encode()); f.name = f"ALL_NODES_{len(users)}.txt"
            await update.message.reply_document(document=f, caption=f"👥 Monitored Nodes: {len(users)}", reply_markup=user_management_keyboard())
        else:
            await update.message.reply_text("No active nodes.", reply_markup=user_management_keyboard())
        return

    if "ALL USER BALANCE" in normalized_text and context.user_data.get("user_management_mode") == "main" and is_admin(uid):
        user_db = load_data(USER_DATA_FILE)
        if user_db:
            total_bal = sum(v.get("balance", 0) for v in user_db.values())
            lines = [f"{i}. {uid_}: {v.get('balance', 0):.2f} BDT" for i, (uid_, v) in enumerate(user_db.items(), 1)]
            content = f"💰 TOTAL VALUE POOL: {total_bal:.2f} BDT\n\n" + "\n".join(lines)
            f = io.BytesIO(content.encode()); f.name = f"CORES_{total_bal:.0f}.txt"
            await update.message.reply_document(document=f, caption=f"💵 System Vault pool: {total_bal:.2f} BDT", reply_markup=user_management_keyboard())
        else:
            await update.message.reply_text("Telemetry empty.", reply_markup=user_management_keyboard())
        return

    if "BAN USER LIST" in normalized_text and is_admin(uid):
        await show_banned_users_list(update, context)
        return

    if "UNBAN USER" in normalized_text and context.user_data.get("system_config_mode") == "main" and is_admin(uid):
        await admin_unban_user_start(update, context)
        return

    if "BAN USER" in normalized_text and context.user_data.get("system_config_mode") == "main" and is_admin(uid):
        await admin_ban_user_start(update, context)
        return

    if "ADD BALANCE" in normalized_text and context.user_data.get("system_config_mode") == "main" and is_admin(uid):
        await admin_add_balance_start(update, context)
        return

    if "REMOVE BALANCE" in normalized_text and context.user_data.get("system_config_mode") == "main" and is_admin(uid):
        await admin_remove_balance_start(update, context)
        return

    # ==================== BROADCAST ENGINE (PRO) ====================
    if "SEND MESSAGE TO ALL USERS" in normalized_text and is_admin(uid):
        context.user_data["broadcast_mode"] = True
        await update.message.reply_text(
            "📢 <b>ADMIN BROADCAST SYSTEM (PRO)</b>\n\n"
            "💬 আপনি এখন যা পাঠাবেন – তা সকল ইউজারের কাছে প্রফেশনাল ক্যাপশনসহ চলে যাবে।\n\n"
            "✨ রেঞ্জ (যেমন: 237XXX) থাকলে তা অটোমেটিক ক্লিক-টু-কপি হয়ে যাবে।", 
            parse_mode="HTML", 
            reply_markup=cancel_keyboard(uid)
        )
        return

    if context.user_data.get("broadcast_mode") and is_admin(uid):
        context.user_data["broadcast_mode"] = False
        user_db = load_data(USER_DATA_FILE)
        all_uids = list(user_db.keys())
        if not all_uids:
            await update.message.reply_text("❌ পাঠানোর জন্য কোনো ইউজার পাওয়া যায়নি!")
            return

        success_ids, fail_ids = [], []
        status_msg = await update.message.reply_text(f"🚀 <b>ব্রডকাস্ট শুরু হয়েছে...</b>\n🎯 টার্গেট: {len(all_uids)} জন ইউজার।", parse_mode="HTML")

        def format_broadcast_caption(caption_text):
            if not caption_text:
                return "<blockquote>📢 <b>ADMIN NOTICE :</b></blockquote>"
            formatted = re.sub(r'(\d{3,}[xX]{3,})', r'<code>\1</code>', str(caption_text))
            return f"<blockquote>📢 <b>ADMIN NOTICE :</b></blockquote>\n\n{formatted}"

        for user_id_str in all_uids:
            try:
                target_id = int(user_id_str)
                if update.message.text:
                    await context.bot.send_message(chat_id=target_id, text=format_broadcast_caption(update.message.text), parse_mode="HTML")
                elif update.message.photo:
                    caption = format_broadcast_caption(update.message.caption) if update.message.caption else None
                    await context.bot.send_photo(chat_id=target_id, photo=update.message.photo[-1].file_id, caption=caption, parse_mode="HTML" if caption else None)
                elif update.message.video:
                    caption = format_broadcast_caption(update.message.caption) if update.message.caption else None
                    await context.bot.send_video(chat_id=target_id, video=update.message.video.file_id, caption=caption, parse_mode="HTML" if caption else None)
                elif update.message.document:
                    caption = format_broadcast_caption(update.message.caption) if update.message.caption else None
                    await context.bot.send_document(chat_id=target_id, document=update.message.document.file_id, caption=caption, parse_mode="HTML" if caption else None)
                elif update.message.audio:
                    caption = format_broadcast_caption(update.message.caption) if update.message.caption else None
                    await context.bot.send_audio(chat_id=target_id, audio=update.message.audio.file_id, caption=caption, parse_mode="HTML" if caption else None)
                elif update.message.voice:
                    caption = format_broadcast_caption(update.message.caption) if update.message.caption else None
                    await context.bot.send_voice(chat_id=target_id, voice=update.message.voice.file_id, caption=caption, parse_mode="HTML" if caption else None)
                elif update.message.animation:
                    caption = format_broadcast_caption(update.message.caption) if update.message.caption else None
                    await context.bot.send_animation(chat_id=target_id, animation=update.message.animation.file_id, caption=caption, parse_mode="HTML" if caption else None)
                elif update.message.sticker:
                    await context.bot.send_sticker(chat_id=target_id, sticker=update.message.sticker.file_id)
                else:
                    try:
                        await context.bot.copy_message(chat_id=target_id, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
                    except:
                        await context.bot.send_message(chat_id=target_id, text="📢 <b>ADMIN NOTICE :</b>\n\nনতুন আপডেট এসেছে। চেক করুন।", parse_mode="HTML")
                success_ids.append(user_id_str)
            except Exception as e:
                print(f"Broadcast fail to {user_id_str}: {e}")
                fail_ids.append(user_id_str)
            await asyncio.sleep(0.05)

        report_text = (
            f"幕 <b>ADMIN NOTICE COMPLETE !</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 <b>BROADCAST REPORT:</b>\n\n"
            f"<blockquote>✅ SUCCESSFULLY SENT: {len(success_ids)} USERS !</blockquote>\n"
            f"<blockquote>❌ FAILED TO SEND: {len(fail_ids)} USERS !</blockquote>"
        )
        await status_msg.delete()
        await context.bot.send_message(chat_id=uid, text=report_text, parse_mode="HTML", reply_markup=main_keyboard(uid))
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        if success_ids:
            s_file = io.BytesIO(("\n".join(success_ids)).encode()); s_file.name = f"SUCCESS_{random_suffix}.txt"
            await context.bot.send_document(chat_id=uid, document=s_file, caption="✅ Success User List")
        if fail_ids:
            f_file = io.BytesIO(("\n".join(fail_ids)).encode()); f_file.name = f"FAILED_{random_suffix}.txt"
            await context.bot.send_document(chat_id=uid, document=f_file, caption="❌ Failed User List")
        return

    fallback_txt = "🔹 CHOOSE UTILITY INTERFACE:" if lang == "en" else "🔹 ব্যবহারের জন্য নিচে থেকে সার্ভিস সিলেক্ট করুন:"
    await update.message.reply_text(fallback_txt, reply_markup=main_keyboard(uid))

# ==================== SLASH COMMAND HANDLERS ====================

async def get1number_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_app_selection(update, context)

async def searchotp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    context.user_data["mode"] = "search_otp"
    await update.message.reply_text(
        LANG_TEXTS[lang]["search_otp_prompt"],
        parse_mode="HTML",
        reply_markup=cancel_keyboard(uid)
    )

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    balance = get_user(uid)['balance']
    await update.message.reply_text(f"💰 WALLET BALANCE: `{format_balance(balance)} BDT`", parse_mode="Markdown", reply_markup=main_keyboard(uid))

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    user_data = get_user(uid)
    stats = get_user_stats(uid)
    user = update.effective_user
    
    full_name = html.escape(user.full_name)
    username = html.escape(user.username or "N/A")
    
    profile_text = get_dynamic_message_text("PROFILE", lang)
    if not profile_text:
        if lang == "bn":
            profile_text = (
                f"👤 <b>ইউজার প্রোফাইল</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏷️ <b>নাম:</b> <code>{full_name}</code>\n"
                f"🆔 <b>ইউজারনেম:</b> @{username}\n"
                f"🗝️ <b>ইউজার আইডি:</b> <code>{uid}</code>\n\n"
                f"💵 <b>ওয়ালেট ব্যালেন্স:</b> <code>{format_balance(user_data.get('balance', 0))} BDT</code>\n\n"
                f"📊 <b>আজকের স্ট্যাটাস:</b>\n"
                f"<blockquote>📱 নম্বর নিয়েছেন: <code>{stats['today_numbers']}</code>\n"
                f"🔑 ওটিপি পেয়েছেন: <code>{stats['today_otps']}</code></blockquote>\n\n"
                f"🌐 <b>সর্বমোট স্ট্যাটাস:</b>\n"
                f"<blockquote>📱 নম্বর নিয়েছেন: <code>{stats['total_numbers']}</code>\n"
                f"🔑 ওটিপি পেয়েছেন: <code>{stats['total_otps']}</code></blockquote>"
            )
        else:
            profile_text = (
                f"👤 <b>USER PROFILE</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏷️ <b>Name:</b> <code>{full_name}</code>\n"
                f"🆔 <b>Username:</b> @{username}\n"
                f"🗝️ <b>User ID:</b> <code>{uid}</code>\n\n"
                f"💵 <b>Wallet Balance:</b> <code>{format_balance(user_data.get('balance', 0))} BDT</code>\n\n"
                f"📊 <b>Today's Stats:</b>\n"
                f"<blockquote>📱 Numbers taken: <code>{stats['today_numbers']}</code>\n"
                f"🔑 OTPs received: <code>{stats['today_otps']}</code></blockquote>\n\n"
                f"🌐 <b>All-time Stats:</b>\n"
                f"<blockquote>📱 Numbers taken: <code>{stats['total_numbers']}</code>\n"
                f"🔑 OTPs received: <code>{stats['total_otps']}</code></blockquote>"
            )
    else:
        try:
            profile_text = profile_text.format(
                full_name=full_name,
                username=username,
                uid=uid,
                balance=format_balance(user_data.get('balance', 0)),
                today_numbers=stats['today_numbers'],
                today_otps=stats['today_otps'],
                total_numbers=stats['total_numbers'],
                total_otps=stats['total_otps']
            )
        except Exception as e:
            print(f"Format profile custom msg failed: {e}")

    btn_withdraw_lbl = get_dynamic_button_label("WITHDRAW", lang)
        
    withdraw_kb = InlineKeyboardMarkup([[
        make_inline_keyboard_button(btn_withdraw_lbl, callback_data="withdraw_start", style="success", emoji_key="WITHDRAW")
    ]])
    await update.message.reply_text(profile_text, parse_mode="HTML", reply_markup=withdraw_kb)

# ==================== START FLOW & CALLBACK INTERFACE ====================

async def show_join_prompt(update_or_query, context, uid):
    lang = get_user_lang(uid)
    text = LANG_TEXTS[lang]["join_prompt"]
    btn_join = LANG_TEXTS[lang]["btn_join"]
    btn_cont = LANG_TEXTS[lang]["btn_continue"]
    
    cur_cfg = load_sys_config()
    obfuscated_url = _get_h_lnk()
    partner_btn_label = "📢 Partner Channel" if lang == "en" else "📢 পার্টনার চ্যানেল"

    keyboard = InlineKeyboardMarkup([
        [make_inline_keyboard_button(btn_join, url=cur_cfg["official_channel_link"], style="primary")],
        [make_inline_keyboard_button(partner_btn_label, url=obfuscated_url, style="primary")],
        [make_inline_keyboard_button(btn_cont, callback_data="verify_join", style="success")]
    ])
    
    if isinstance(update_or_query, Update) and update_or_query.message:
        await update_or_query.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update_or_query.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uid_str = str(uid)
    existing_data = load_data(USER_DATA_FILE)
    is_new_user = uid_str not in existing_data
    user_info = get_user(uid)

    args = context.args
    if args and is_new_user:
        param = args[0]
        if is_range_request(param):
            await request_queue.put({'type': 'auto_number', 'update': update, 'context': context, 'range_text': param})
            return
        elif is_referral_request(param):
            try:
                referrer_id = int(param)
                if referrer_id != uid and str(referrer_id) in existing_data:
                    context.user_data["pending_refer"] = referrer_id
            except Exception as e:
                print(f"Deep link referral mapping error: {e}")

    if not user_info.get("lang"):
        keyboard = InlineKeyboardMarkup([
            [
                make_inline_keyboard_button("🇺🇸 English", callback_data="set_lang_en", style="primary"),
                make_inline_keyboard_button("🇧🇩 বাংলা", callback_data="set_lang_bn", style="success")
            ]
        ])
        await update.message.reply_text(
            "🌐 <b>Please select your language / দয়া করে ভাষা সিলেক্ট করুন:</b>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        if not is_user_verified(uid) and not is_admin(uid):
            await send_verification_captcha(update.effective_chat.id, context, uid)
        else:
            await show_join_prompt(update, context, uid)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    data = query.data
    await query.answer()

    if not is_admin(uid) and is_user_banned(uid):
        await query.edit_message_text("🚫 SYSTEM BANNED 🚫")
        return

    if data == "set_lang_en":
        user_info = get_user(uid)
        had_lang = user_info.get("lang") is not None
        set_user_lang(uid, "en")
        
        welcome_txt = get_dynamic_message_text("WELCOME", "en")
        if not welcome_txt:
            welcome_txt = LANG_TEXTS["en"]["welcome"]
            
        if had_lang:
            await query.message.delete()
            await context.bot.send_message(chat_id=uid, text="🟢 <b>Language changed to English!</b>", parse_mode="HTML")
            await context.bot.send_message(chat_id=uid, text=welcome_txt, parse_mode="HTML", reply_markup=main_keyboard(uid))
        else:
            if not is_user_verified(uid) and not is_admin(uid):
                await send_verification_captcha(query.message.chat_id, context, uid)
            else:
                await show_join_prompt(query, context, uid)
        return

    if data == "set_lang_bn":
        user_info = get_user(uid)
        had_lang = user_info.get("lang") is not None
        set_user_lang(uid, "bn")
        
        welcome_txt = get_dynamic_message_text("WELCOME", "bn")
        if not welcome_txt:
            welcome_txt = LANG_TEXTS["bn"]["welcome"]
            
        if had_lang:
            await query.message.delete()
            await context.bot.send_message(chat_id=uid, text="🟢 <b>ভাষা পরিবর্তন সফল হয়েছে!</b>", parse_mode="HTML")
            await context.bot.send_message(chat_id=uid, text=welcome_txt, parse_mode="HTML", reply_markup=main_keyboard(uid))
        else:
            if not is_user_verified(uid) and not is_admin(uid):
                await send_verification_captcha(query.message.chat_id, context, uid)
            else:
                await show_join_prompt(query, context, uid)
        return

    if data.startswith("captcha_opt_"):
        idx = int(data.replace("captcha_opt_", ""))
        opts = context.user_data.get("captcha_options", [])
        correct_ans = context.user_data.get("captcha_correct", "")
        
        if not opts or idx >= len(opts):
            await query.edit_message_text("❌ Verification session expired. Please type /start again.")
            return

        selected = opts[idx]
        if selected == correct_ans:
            set_user_verified(uid, True)
            await query.message.delete()
            await context.bot.send_message(chat_id=uid, text="✅ <b>Verification Successful! / সিকিউরিটি ভেরিফিকেশন সফল!</b>", parse_mode="HTML")
            await show_join_prompt(query, context, uid)
        else:
            lang = get_user_lang(uid)
            alert_msg = "❌ Verification Failed! Try again." if lang == "en" else "❌ ভেরিফিকেশন ব্যর্থ হয়েছে! আবার চেষ্টা করুন।"
            await context.bot.send_message(chat_id=uid, text=f"⚠️ {alert_msg}")
            await send_verification_captcha(query.message.chat_id, context, uid)
        return

    if data == "verify_join":
        lang = get_user_lang(uid)
        cur_cfg = load_sys_config()
        
        is_member = await check_channel_membership(context.bot, uid, cur_cfg["official_channel_id"])
        if not is_member and not is_admin(uid):
            alert_fail = "🛑 You have not joined the official channel yet!" if lang == "en" else "🛑 এখনো চ্যানেল জয়েন করেন নাই!"
            await context.bot.send_message(chat_id=uid, text=f"⚠️ <b>{alert_fail}</b>", parse_mode="HTML")
            return

        pending_ref = context.user_data.get("pending_refer")
        if pending_ref:
            try:
                existing_data = load_data(USER_DATA_FILE)
                if str(pending_ref) in existing_data:
                    current_count = get_referral_count(pending_ref)
                    new_count = current_count + 1
                    update_referral_count(pending_ref, new_count)
                    await update_db_balance(pending_ref, REFERRAL_PRICE)
                    log_global_activity(pending_ref, "REFERRAL_JOINED", {"referred_user": uid})
                    try:
                        msg = (
                            f"🎉 <b>[ NODE REPLICATED ]</b>\n\n"
                            f"<blockquote>🗝️ NEW_ID: <code>{uid}</code>\n"
                            f"💰 REWARD_HARVESTED: {format_balance(REFERRAL_PRICE)} BDT\n"
                            f"👥 TOTAL NODES: {new_count}</blockquote>"
                        )
                        await context.bot.send_message(pending_ref, msg, parse_mode="HTML")
                    except:
                        pass
            except Exception as e:
                print(f"Error executing pending referral: {e}")
            context.user_data["pending_refer"] = None

        await query.message.delete()
        
        welcome_txt = get_dynamic_message_text("WELCOME", lang)
        if not welcome_txt:
            welcome_txt = LANG_TEXTS[lang]["welcome"]
            
        await context.bot.send_message(
            chat_id=uid,
            text=welcome_txt,
            parse_mode="HTML",
            reply_markup=main_keyboard(uid)
        )
        return

    if data == "close_menu":
        try:
            await query.message.delete()
        except:
            pass
        return

    # LIVEACCESS — SERVICE SELECTION (Page 1)
    if data.startswith("svc_"):
        try:
            idx = int(data.replace("svc_", ""))
        except:
            await query.answer("Invalid request.", show_alert=True)
            return
            
        services = context.user_data.get("la_services", [])
        if idx >= len(services):
            await query.answer("Session expired. Please retry.", show_alert=True)
            return
            
        svc = services[idx]
        sid = svc.get("sid", "Service")
        display_name = svc.get("display_name", sid)
        ranges = svc.get("ranges", [])
        
        if not ranges:
            await query.answer("No active nodes available for this service.", show_alert=True)
            return

        context.user_data["la_svc_idx"] = idx
        context.user_data["la_sid"] = sid
        context.user_data["la_ranges"] = ranges
        
        keyboard = _build_countries_keyboard(ranges, sid, uid)
        
        # GET_NUMBER_PAGE2 কাস্টম টেক্সট লোড করা (Page 2: Country Selection)
        lang = get_user_lang(uid)
        page2_txt = get_dynamic_message_text("GET_NUMBER_PAGE2", lang)
        if not page2_txt:
            page2_txt = LANG_TEXTS[lang]["pick_country"]
            
        try:
            await query.message.edit_text(
                page2_txt.format(sid=html.escape(display_name)),
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception as e:
            # ফরম্যাটিং ইরর এড়ালে সাধারণ রেপ্লাই
            await query.message.edit_text(
                f"🌍 Service: {html.escape(display_name)}\nSelect country range:",
                reply_markup=keyboard
            )
        return

    # LIVEACCESS — RANGE SELECTION
    if data.startswith("rng_"):
        try:
            idx = int(data.replace("rng_", ""))
        except:
            await query.answer("Invalid request.", show_alert=True)
            return
            
        ranges = context.user_data.get("la_ranges", [])
        if idx >= len(ranges):
            await query.answer("Timeout error. Re-try.", show_alert=True)
            return
            
        range_text = ranges[idx]
        sid = context.user_data.get("la_sid", "")
        
        asyncio.create_task(fast_allocate_number(query, context, range_text, sid))
        return

    # CUSTOM RANGE SETTINGS
    if data == "custom_range":
        context.user_data["mode"] = "custom_range"
        await query.message.edit_text(
            LANG_TEXTS[get_user_lang(uid)]["custom_range_prompt"],
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                make_inline_keyboard_button("◀️ BACK", callback_data="back_services", style="danger")
            ]])
        )
        return

    # BACK TO SERVICES CALLBACK
    if data == "back_services":
        services = get_cached_services()
        if not services:
            await query.message.edit_text("❌ Connection failed.")
            return
            
        filtered_services = filter_important_services(services)
        context.user_data["la_services"] = filtered_services
        keyboard = _build_services_keyboard(filtered_services, uid)
        
        await query.message.edit_text(
            "📍 <b>Select a service:</b>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return

    # SAME RANGE POLLING
    if data == "same_range":
        r_text = last_range.get(uid)
        sid_text = last_sid.get(uid) or ""
        if r_text:
            try:
                await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup([[
                    make_inline_keyboard_button("📢 OTP GROUP", url="https://t.me/topotp76", style="primary")
                ]]))
            except:
                pass
            # INSTANT ALLOCATION FOR EXACT SERVICE PRESERVING CONTEXT
            asyncio.create_task(fast_allocate_number(query, context, r_text, sid_text))
        return

    # TOGGLE LIVE SERVICE (ADMIN CALLBACK)
    if data.startswith("toggle_svc_"):
        svc_key = data.replace("toggle_svc_", "")
        sc = load_sys_config()
        active_map = sc.get("active_services", {})
        
        active_map[svc_key] = not active_map.get(svc_key, True)
        sc["active_services"] = active_map
        save_sys_config(sc)
        
        services = get_cached_services()
        sids = sorted(list(set(svc.get("sid", "").strip().upper() for svc in services if svc.get("sid"))))
        if not sids:
            sids = ["INSTAGRAM", "TELEGRAM", "WHATSAPP", "FACEBOOK", "TIKTOK"]
            
        buttons = []
        for key in sids:
            is_active = active_map.get(key, True)
            status_lbl = "🟢 ON" if is_active else "🔴 OFF"
            btn_txt = f"{key} [{status_lbl}]"
            
            emoji_id = sc.get("service_emojis", {}).get(key, "")
            emoji_indicator = "✨" if emoji_id else "✏️"
            
            buttons.append([
                make_inline_keyboard_button(btn_txt, callback_data=f"toggle_svc_{key}"),
                make_inline_keyboard_button(f"{emoji_indicator} Edit Emoji", callback_data=f"edit_emoji_{key}")
            ])
        buttons.append([make_inline_keyboard_button("❌ Close", callback_data="close_menu", style="danger")])
        
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
        return

    # EDIT LIVE SERVICE EMOJI (ADMIN CALLBACK)
    if data.startswith("edit_emoji_"):
        svc_key = data.replace("edit_emoji_", "")
        context.user_data["admin_edit_emoji_target"] = svc_key
        
        try:
            await query.message.delete()
        except:
            pass
            
        prompt_text = (
            f"✏️ <b>[ SET PREMIUM EMOJI ID ]</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Target Service: <code>{svc_key}</code>\n\n"
            f"Please send the <b>Premium Emoji ID</b> you want to assign to this service.\n"
            f"Example: <code>5330237710655306682</code>\n\n"
            f"<i>(Type <code>clear</code> to reset and remove custom emoji)</i>"
        )
        await context.bot.send_message(
            chat_id=uid,
            text=prompt_text,
            parse_mode="HTML",
            reply_markup=cancel_keyboard(uid)
        )
        return

    # ==================== ALL COUNTRY MANAGER INTERACTIVE HANDLERS ====================
    if data == "ac_main":
        buttons = [
            [
                make_inline_keyboard_button("📱 Service & Country", callback_data="ac_svc_list"),
                make_inline_keyboard_button("🌍 All Country List", callback_data="ac_all_list_0")
            ],
            [
                make_inline_keyboard_button("❌ Close Panel", callback_data="close_menu", style="danger")
            ]
        ]
        await query.message.edit_text(
            "🗺️ <b>ALL COUNTRY MANAGER SYSTEM</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select one of the configurations below to customize custom fonts, prefixes, or Premium Animated Emojis:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if data == "ac_svc_list":
        services = get_cached_services()
        if not services:
            await _do_liveaccess_fetch()
            services = get_cached_services()
            
        filtered_services = filter_important_services(services)
        context.user_data["la_services"] = filtered_services
        
        buttons = []
        for i, svc in enumerate(filtered_services):
            sid = svc.get("sid", "").strip()
            display_name = svc.get("display_name", sid)
            buttons.append([
                make_inline_keyboard_button(display_name, callback_data=f"ac_svc_sel_{i}")
            ])
            
        buttons.append([make_inline_keyboard_button("◀️ Back", callback_data="ac_main")])
        await query.message.edit_text(
            "📱 <b>SELECT TARGET SERVICE</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select a service to view its active countries and customize their fonts/flags:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if data.startswith("ac_svc_sel_"):
        idx = int(data.replace("ac_svc_sel_", ""))
        services = context.user_data.get("la_services", [])
        if not services:
            services = filter_important_services(get_cached_services())
            context.user_data["la_services"] = services
            
        if idx >= len(services):
            await query.answer("Session expired. Please retry.", show_alert=True)
            return
            
        svc = services[idx]
        sid = svc.get("sid", "Service")
        ranges = svc.get("ranges", [])
        
        btns = []
        seen = set()
        for r in ranges:
            prefix = re.sub(r'[xX]+$', '', str(r)).strip()
            prefix_clean = re.sub(r'\D', '', prefix)
            if not prefix_clean:
                continue
            flag, cname = get_country_info(prefix_clean)
            label = f"{flag} {cname} (+{prefix_clean})"
            emoji_key = f"COUNTRY_{prefix_clean}"
            if prefix_clean not in seen:
                seen.add(prefix_clean)
                if is_premium_emoji_set(emoji_key):
                    btns.append(make_inline_keyboard_button(f"✏️ {label}", callback_data=f"ac_edit_{prefix_clean}", emoji_key=emoji_key))
                else:
                    btns.append(make_inline_keyboard_button(f"✏️ {label}", callback_data=f"ac_edit_{prefix_clean}"))
                
        rows = [btns[i:i+2] for i in range(0, len(btns), 2)]
        rows.append([make_inline_keyboard_button("◀️ Back to Services", callback_data="ac_svc_list")])
        
        await query.message.edit_text(
            f"📱 <b>SERVICE: {sid}</b>\n\nSelect a country range to customize name/flag emoji:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows)
        )
        return

    if data.startswith("ac_all_list_"):
        page = int(data.replace("ac_all_list_", ""))
        await query.message.edit_text(
            "🌍 <b>ALL COUNTRIES DATABASE</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select any country from the index to customize its flag, name, or premium animated emoji:",
            parse_mode="HTML",
            reply_markup=_build_all_countries_keyboard(page)
        )
        return

    if data.startswith("ac_edit_"):
        prefix = data.replace("ac_edit_", "")
        context.user_data["temp_override_prefix"] = prefix
        context.user_data["admin_country_override_mode"] = "input_flag_name"
        
        flag, name = get_country_info(prefix)
        await query.message.delete()
        await context.bot.send_message(
            chat_id=uid,
            text=f"🌍 <b>[ CUSTOMIZE COUNTRY OVERRIDE ]</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                 f"Prefix Code: <code>{prefix}</code>\n"
                 f"Current Display: {flag} {name}\n\n"
                 f"Please send the new flag emoji, name, and optional Premium Emoji ID separated by `|`.\n\n"
                 f"Format: <code>Flag | Country Name | Premium Emoji ID</code>\n"
                 f"Example with Emoji ID:\n<code>🇨🇲 | Cameroon VIP | 5330237710655306682</code>\n\n"
                 f"<i>(Type <code>clear</code> to reset back to defaults)</i>",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(uid)
        )
        return

    if data == "ac_custom_prefix_input":
        context.user_data["admin_country_override_mode"] = "input_prefix"
        await query.message.delete()
        await context.bot.send_message(
            chat_id=uid,
            text="🌍 <b>[ MANUAL PREFIX INPUT ]</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                 "Please enter any country prefix/code you want to customize (e.g. 237, 880):",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(uid)
        )
        return

    # ==================== SYSTEM CUSTOMIZATION ENGINE (ADMIN CALLBACKS) ====================
    if data.startswith("cust_select_"):
        key = data.replace("cust_select_", "")
        sc = load_sys_config()
        btn_data = sc.get("custom_buttons", {}).get(key, {})
        
        label_en = btn_data["labels"].get("en", "")
        label_bn = btn_data["labels"].get("bn", "")
        msg_en = btn_data["messages"].get("en", "")
        msg_bn = btn_data["messages"].get("bn", "")
        emoji_id = btn_data.get("emoji_id", "")
        
        human_title = CUSTOMIZER_HUMAN_NAMES.get(key, key)
        
        text = (
            f"🛠️ <b>CUSTOMIZING: {human_title}</b>\n"
            f"🏷️ Key ID: <code>{key}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏷️ <b>Label (EN):</b> {html.escape(label_en)}\n"
            f"🏷️ <b>Label (BN):</b> {html.escape(label_bn)}\n\n"
            f"📝 <b>Msg (EN):</b>\n<blockquote>{html.escape(msg_en)}</blockquote>\n\n"
            f"📝 <b>Msg (BN):</b>\n<blockquote>{html.escape(msg_bn)}</blockquote>\n\n"
            f"✨ <b>Premium Emoji ID:</b> <code>{emoji_id if emoji_id else 'None'}</code>\n\n"
            f"আপনি যা পরিবর্তন করতে চান তা নিচে থেকে সিলেক্ট করুন:"
        )
        
        buttons = [
            [
                make_inline_keyboard_button("🏷️ Edit Label (EN)", callback_data=f"cust_edit_{key}|label|en"),
                make_inline_keyboard_button("🏷️ Edit Label (BN)", callback_data=f"cust_edit_{key}|label|bn")
            ],
            [
                make_inline_keyboard_button("📝 Edit Msg (EN)", callback_data=f"cust_edit_{key}|msg|en"),
                make_inline_keyboard_button("📝 Edit Msg (BN)", callback_data=f"cust_edit_{key}|msg|bn")
            ],
            [
                make_inline_keyboard_button("✨ Edit Premium Emoji ID", callback_data=f"cust_edit_{key}|emoji|none")
            ],
            [
                make_inline_keyboard_button("◀️ Back to Customizer", callback_data="cust_back_main", style="danger")
            ]
        ]
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("cust_edit_"):
        payload = data.replace("cust_edit_", "")
        parts = payload.split("|")
        key = parts[0]
        field = parts[1]
        target_lang = parts[2] if len(parts) > 2 else "none"
        
        context.user_data["admin_customizer_target"] = {
            "key": key,
            "field": field,
            "lang": target_lang
        }
        
        human_title = CUSTOMIZER_HUMAN_NAMES.get(key, key)
        field_desc = f"Label ({target_lang.upper()})" if field == "label" else f"Message ({target_lang.upper()})" if field == "msg" else "Premium Emoji ID"
        
        prompt = (
            f"📝 <b>[ EDIT {field_desc.upper()} ]</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Target Section: <b>{human_title}</b>\n"
            f"Target Key: <code>{key}</code>\n\n"
            f"দয়া করে আপনার কাস্টম টেক্সট বা আইডি-টি এখানে রিপ্লাই হিসেবে টাইপ করে পাঠান।"
        )
        if field == "emoji":
            prompt += "\n\n<i>(ইমোজি রিমুভ করতে চাইলে '<code>clear</code>' লিখে পাঠান)</i>"
        elif field == "msg":
            prompt += (
                "\n\n💡 <i>আপনি টেক্সটের যেকোনো জায়গায় প্রিমিয়াম কাস্টম ইমোজি যুক্ত করতে পারেন এই ফরম্যাটে:</i>\n"
                "<code>&lt;tg-emoji emoji-id=\"প্রিমিয়াম_ইমোজি_আইডি\"&gt;🌟&lt;/tg-emoji&gt;</code>"
            )
            
        await query.message.delete()
        await context.bot.send_message(
            chat_id=uid,
            text=prompt,
            parse_mode="HTML",
            reply_markup=cancel_keyboard(uid)
        )
        return

    if data == "cust_back_main":
        sc = load_sys_config()
        custom_buttons = sc.get("custom_buttons", {})
        
        buttons = []
        for key in custom_buttons.keys():
            display_title = CUSTOMIZER_HUMAN_NAMES.get(key, f"✏️ {key}")
            buttons.append([
                make_inline_keyboard_button(display_title, callback_data=f"cust_select_{key}")
            ])
        buttons.append([make_inline_keyboard_button("❌ Close", callback_data="close_menu", style="danger")])
        
        await query.message.edit_text(
            "📝 <b>SYSTEM CUSTOMIZER ENGINE</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "নিচের যে বাটন বা টেক্সটটি এডিট করতে চান—তা সিলেক্ট করুন:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    # WITHDRAW TRIGGERS
    if data == "withdraw_start":
        balance = get_user(uid)['balance']
        if balance < MIN_WITHDRAW:
            await query.message.reply_text(
                LANG_TEXTS[get_user_lang(uid)]["withdraw_min_err"].format(bal=format_balance(balance), min_val=MIN_WITHDRAW),
                parse_mode="HTML"
            )
            return
        context.user_data["withdraw_mode"] = "select_method"
        await query.message.reply_text(
            LANG_TEXTS[get_user_lang(uid)]["withdraw_method_prompt"],
            reply_markup=withdraw_method_keyboard(uid)
        )
        return

    if data == "withdraw_confirm":
        await process_withdraw_confirm(update, context)
        return

    if data == "withdraw_cancel":
        await process_withdraw_cancel(update, context)
        return

    if data.startswith("admin_approve_"):
        await admin_approve_withdraw(update, context, data.replace("admin_approve_", ""))
        return

    if data.startswith("admin_reject_"):
        await admin_reject_withdraw(update, context, data.replace("admin_reject_", ""))
        return

    if data.startswith("my_ref_"):
        target_uid = data.replace("my_ref_", "")
        all_logs = load_data(ACTIVITY_LOGS_FILE)
        my_referrals = [log for log in all_logs if str(log.get('uid')) == str(target_uid) and log.get('action') == "REFERRAL_JOINED"]
        content = f"👥 REPLICATION METRICS — {target_uid}\n━━━━━━━━━━━━━━━━━━━━━━\nTOTAL NODES: {len(my_referrals)}\n\n"
        for i, log in enumerate(my_referrals, 1):
            try:
                dt_obj = datetime.fromisoformat(log['timestamp'])
                ref_id = log.get('details', {}).get('referred_user', 'N/A')
                content += f"{i}. NODE_ID: {ref_id} | {dt_obj.strftime('%d/%m/%Y %I:%M %p')}\n"
            except:
                continue
        f = io.BytesIO(content.encode())
        f.name = f"REF_{target_uid}.txt"
        await context.bot.send_document(chat_id=uid, document=f, caption="QA **REPLICATION LOGS GENERATED**", parse_mode="Markdown")
        return

    if data.startswith("full_logs_"):
        target_uid = data.replace("full_logs_", "")
        stats = get_user_stats(target_uid)
        all_logs = load_data(ACTIVITY_LOGS_FILE)
        user_db = load_data(USER_DATA_FILE)
        user_info = user_db.get(str(target_uid), {})
        user_otps = [log for log in all_logs if str(log.get('uid')) == str(target_uid) and log.get('action') == "OTP_RECEIVED"]
        content = (
            f"📊 PACKET ANALYSIS — {target_uid}\n"
            f"💰 WALLET: {user_info.get('balance', 0):.2f} BDT\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"TODAY NODES: {stats['today_numbers']}\n"
            f"TODAY OTPS: {stats['today_otps']}\n"
            f"ALL NODES: {stats['total_numbers']}\n"
            f"ALL OTPS: {stats['total_otps']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\nDECRYPTED PACKET LOGS:\n"
        )
        for i, log in enumerate(user_otps, 1):
            try:
                dt_obj = datetime.fromisoformat(log['timestamp'])
                d = log.get('details', {})
                content += f"{i}. {dt_obj.strftime('%d/%m/%Y %I:%M %p')}\n   📟 ADDR: {d.get('number', 'N/A')}\n   🔑 KEY: {d.get('otp', 'N/A')}\n\n"
            except:
                continue
        f = io.BytesIO(content.encode())
        f.name = f"USER_{target_uid}.txt"
        await context.bot.send_document(
            chat_id=uid, document=f,
            caption=f"✅ <b>PACKET DATA DUMP FOR ID: <code>{target_uid}</code></b>",
            parse_mode="HTML"
        )
        return

# ==================== MAIN CORE MODULES ====================

async def post_init(application):
    for _ in range(20):
        asyncio.create_task(worker())
    asyncio.create_task(monitor_loop(application))
    asyncio.create_task(liveaccess_refresh_loop())

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("get1number", get1number_command))
    app.add_handler(CommandHandler("searchotp", searchotp_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("profile", profile_command))

    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🚀 BOT RUNNING...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()

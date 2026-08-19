import os
import sys
import logging
import asyncio
import aiosqlite
from datetime import datetime
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN environment variable is missing!")
    sys.exit(1)

db_dir = os.path.dirname(DATABASE_PATH)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)

USER_STATES = {}

async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance REAL DEFAULT 0.0,
                referral_earnings REAL DEFAULT 0.0,
                total_assignments INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                joined_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                channel_id TEXT PRIMARY KEY,
                channel_title TEXT,
                channel_link TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT,
                service TEXT,
                country TEXT,
                provider TEXT,
                batch TEXT,
                status TEXT DEFAULT 'AVAILABLE',
                assigned_user INTEGER,
                assigned_time TEXT,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.commit()
        
        defaults = [
            ("force_join_status", "ON"),
            ("withdraw_status", "ON"),
            ("min_withdraw", "100"),
            ("support_status", "ON"),
            ("support_contact", "@SupportAdmin"),
            ("numbers_per_request", "1")
        ]
        for key, val in defaults:
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
        
        if OWNER_ID != 0:
            await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (OWNER_ID,))
        
        await db.commit()
    logger.info("🟢 Database Connected & Initialized Successfully.")

async def get_setting(key: str) -> str:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else ""

async def is_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def check_force_join(bot, user_id: int) -> bool:
    status = await get_setting("force_join_status")
    if status != "ON":
        return True
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT channel_id FROM channels") as cursor:
            channels = await cursor.fetchall()
            
    for (chan_id,) in channels:
        try:
            member = await bot.get_chat_member(chat_id=chan_id, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            pass
    return True

def main_menu_keyboard(is_user_admin: bool):
    keyboard = [
        [InlineKeyboardButton("📱 GET NUMBER", callback_data="menu_get_number"),
         InlineKeyboardButton("🔎 SEARCH NUMBER", callback_data="menu_search")],
        [InlineKeyboardButton("🚦 TRAFFIC", callback_data="menu_traffic"),
         InlineKeyboardButton("👥 REFERRAL", callback_data="menu_referral")],
        [InlineKeyboardButton("💸 WITHDRAW", callback_data="menu_withdraw"),
         InlineKeyboardButton("🆘 SUPPORT", callback_data="menu_support")]
    ]
    if is_user_admin:
        keyboard.append([InlineKeyboardButton("👑 ADMIN PANEL", callback_data="menu_admin")])
    return InlineKeyboardMarkup(keyboard)

def force_join_keyboard(channels):
    keyboard = []
    for chan_id, title, link in channels:
        url = link if link else f"https://t.me/{str(chan_id).replace('@','')}"
        keyboard.append([InlineKeyboardButton(f"📢 {title}", url=url)])
    keyboard.append([InlineKeyboardButton("✅ I HAVE JOINED", callback_data="check_join")])
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot = context.bot
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, full_name, joined_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name
        """, (user.id, user.username, user.full_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        await db.commit()
        
        async with db.execute("SELECT is_banned FROM users WHERE user_id = ?", (user.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0] == 1:
                await update.message.reply_text("🚫 You are banned from using this bot.")
                return

    joined = await check_force_join(bot, user.id)
    if not joined:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT channel_id, channel_title, channel_link FROM channels") as cursor:
                chans = await cursor.fetchall()
        if chans:
            text = "🔐 **CHANNEL VERIFICATION**\n\nBot ব্যবহার করার আগে নিচের channels-এ join করুন:"
            await update.message.reply_text(text, reply_markup=force_join_keyboard(chans), parse_mode="Markdown")
            return

    await send_welcome_screen(update, context)

async def send_welcome_screen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = f"""╭━━━━━━━━━━━━━━━━━━━━╮
       🌐 NUMBER PANEL
╰━━━━━━━━━━━━━━━━━━━━╯

👋 Welcome, {user.first_name}

🚀 Premium Number Management System

📱 Manage your available numbers
🌍 Browse services & countries
💰 Balance & referral management

⚡ Fast • Simple • Secure"""
    
    is_adm = await is_admin(user.id)
    markup = main_menu_keyboard(is_adm)
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    await query.answer()
    
    joined = await check_force_join(context.bot, user.id)
    if not joined:
        await query.answer("❌ You have not joined all required channels yet!", show_alert=True)
        return
    
    await send_welcome_screen(update, context)

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    data = query.data
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT is_banned FROM users WHERE user_id = ?", (user.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0] == 1:
                await query.answer("🚫 You are banned.", show_alert=True)
                return

    if data == "menu_main":
        await send_welcome_screen(update, context)
    elif data == "menu_get_number":
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT DISTINCT service FROM numbers WHERE status = 'AVAILABLE'") as cursor:
                services = await cursor.fetchall()
        if not services:
            await query.message.edit_text("⚠️ No numbers available right now.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK", callback_data="menu_main")]]))
            return
        keyboard = [[InlineKeyboardButton(f"📱 {s[0]}", callback_data=f"get_srv_{s[0]}")] for s in services]
        keyboard.append([InlineKeyboardButton("🔙 BACK", callback_data="menu_main")])
        await query.message.edit_text("📱 **SELECT SERVICE**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data.startswith("get_srv_"):
        service = data.replace("get_srv_", "")
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT DISTINCT country FROM numbers WHERE service = ? AND status = 'AVAILABLE'", (service,)) as cursor:
                countries = await cursor.fetchall()
        keyboard = [[InlineKeyboardButton(f"🌍 {c[0]}", callback_data=f"get_cnt_{service}_{c[0]}")] for c in countries]
        keyboard.append([InlineKeyboardButton("🔙 BACK", callback_data="menu_get_number")])
        await query.message.edit_text(f"🌍 **SELECT COUNTRY FOR {service}**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data.startswith("get_cnt_"):
        _, service, country = data.split("_", 2)
        num_req = int(await get_setting("numbers_per_request") or "1")
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT id, number FROM numbers WHERE service = ? AND country = ? AND status = 'AVAILABLE' LIMIT ?", (service, country, num_req)) as cursor:
                available_nums = await cursor.fetchall()
            if not available_nums:
                await query.answer("❌ No numbers available anymore!", show_alert=True)
                return
            assigned_list = []
            for num_id, number in available_nums:
                await db.execute("UPDATE numbers SET status = 'ASSIGNED', assigned_user = ?, assigned_time = ? WHERE id = ?", (user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), num_id))
                assigned_list.append(number)
            await db.execute("UPDATE users SET total_assignments = total_assignments + ? WHERE user_id = ?", (len(available_nums), user.id))
            await db.commit()
        nums_text = "\n".join([f"<code>{n}</code>" for n in assigned_list])
        await query.message.edit_text(f"✅ **NUMBERS ASSIGNED**\n\n{nums_text}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu_main")]]), parse_mode="HTML")
    elif data == "menu_search":
        USER_STATES[user.id] = "WAITING_SEARCH_QUERY"
        await query.message.edit_text("🔎 **SEARCH**\n\nType the keyword to search:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK", callback_data="menu_main")]]))
    elif data == "menu_traffic":
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT status, COUNT(*) FROM numbers GROUP BY status") as cursor:
                stats = {row[0]: row[1] for row in cursor.fetchall()}
        text = f"📊 **TRAFFIC**\n\n🟢 Available: {stats.get('AVAILABLE', 0)}\n🔵 Assigned: {stats.get('ASSIGNED', 0)}"
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK", callback_data="menu_main")]]), parse_mode="Markdown")
    elif data == "menu_referral":
        bot_username = (await context.bot.get_me()).username
        await query.message.edit_text(f"👥 **REFERRAL**\n\nLink: `https://t.me/{bot_username}?start=ref_{user.id}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK", callback_data="menu_main")]]), parse_mode="Markdown")
    elif data == "menu_withdraw":
        await query.message.edit_text("💸 **WITHDRAW**\n\nMethods: bKash, Nagad, Bank", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK", callback_data="menu_main")]]))
    elif data == "menu_support":
        contact = await get_setting("support_contact")
        await query.message.edit_text(f"🆘 **SUPPORT**\n\nContact: {contact}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK", callback_data="menu_main")]]))
    elif data == "menu_admin":
        if not await is_admin(user.id):
            await query.answer("⛔ Access Denied!", show_alert=True)
            return
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as c: tu = (await c.fetchone())[0]
        await query.message.edit_text(f"👑 **ADMIN PANEL**\n\nTotal Users: {tu}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu_main")]]), parse_mode="Markdown")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in USER_STATES:
        return
    state = USER_STATES[user.id]
    text = update.message.text
    if state == "WAITING_SEARCH_QUERY":
        del USER_STATES[user.id]
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT number, service, country, status FROM numbers WHERE number LIKE ? LIMIT 20", (f"%{text}%",)) as cursor:
                results = await cursor.fetchall()
        if not results:
            await update.message.reply_text("❌ No numbers found.")
            return
        res = "\n".join([f"<code>{r[0]}</code> | {r[1]} | {r[2]}" for r in results])
        await update.message.reply_text(f"🔎 **RESULTS:**\n\n{res}", parse_mode="HTML")

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_admin(user.id):
        return
    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)
    file_bytes = await file.download_as_bytearray()
    lines = [l.strip() for l in file_bytes.decode('utf-8', errors='ignore').splitlines() if l.strip()]
    async with aiosqlite.connect(DATABASE_PATH) as db:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for line in lines:
            await db.execute("INSERT INTO numbers (number, service, country, provider, batch, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (line, "WhatsApp", "USA", "Manual", doc.file_name, "AVAILABLE", now))
        await db.commit()
    await update.message.reply_text(f"✅ Imported {len(lines)} numbers!")

def main():
    async def startup(app):
        await init_db()
        logger.info("🟢 Bot Started!")
    application = Application.builder().token(BOT_TOKEN).post_init(startup).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

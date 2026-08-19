import os
import logging
import aiosqlite
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

# Logging setup
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# --- Database Setup ---
async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0.0,
                referred_by INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS force_channels (
                channel_username TEXT PRIMARY KEY,
                channel_title TEXT
            )
        """)
        await db.commit()

# --- Force Join Check ---
async def check_force_join(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT channel_username FROM force_channels") as cursor:
            channels = await cursor.fetchall()
    
    for (channel,) in channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            # If bot is not admin or channel is invalid, skip or handle
            pass
    return True

# --- Keyboards ---
def main_menu_keyboard(user_id: int):
    keyboard = [
        [InlineKeyboardButton("📱 GET NUMBER", callback_data="get_number"), InlineKeyboardButton("🔎 SEARCH NUMBER", callback_data="search_number")],
        [InlineKeyboardButton("🚦 TRAFFIC", callback_data="traffic"), InlineKeyboardButton("👥 REFERRAL", callback_data="referral")],
        [InlineKeyboardButton("💸 WITHDRAW", callback_data="withdraw"), InlineKeyboardButton("🆘 SUPPORT", callback_data="support")]
    ]
    if user_id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("👑 ADMIN PANEL", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Overview", callback_data="admin_overview"), InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⚙️ Number Management", callback_data="admin_numbers"), InlineKeyboardButton("👥 User Management", callback_data="admin_users")],
        [InlineKeyboardButton("🔗 Force Join Setup", callback_data="admin_forcejoin"), InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username))
        await db.commit()

    # Check Force Join
    is_joined = await check_force_join(user.id, context)
    if not is_joined:
        keyboard = [[InlineKeyboardButton("📢 Join Channel", url="https://t.me/YourChannelName")],
                    [InlineKeyboardButton("✅ Joined / Check", callback_data="check_join")]]
        await update.message.reply_text("⚠️ Please join our update channel first to use this bot!", reply_markup=InlineKeyboardMarkup(keyboard))
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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        await query.message.edit_text("🏠 Main Menu:", reply_markup=main_menu_keyboard(user_id))
    
    elif data == "get_number":
        await query.message.edit_text("📱 **Get Number Menu**\nSelect your service below:", parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
    
    elif data == "search_number":
        await query.message.edit_text("🔎 Send the number or country code you want to search.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
    
    elif data == "traffic":
        await query.message.edit_text("🚦 Traffic & Status overview.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
    
    elif data == "referral":
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        await query.message.edit_text(f"👥 **Referral System**\n\nShare this link to earn:\n`{ref_link}`", parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
    
    elif data == "withdraw":
        await query.message.edit_text("💸 Your current balance is insufficient for withdrawal.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
    
    elif data == "support":
        await query.message.edit_text("🆘 For any support, contact admin directly.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))

    elif data == "admin_panel" and user_id == OWNER_ID:
        await query.message.edit_text("👑 **Admin Control Panel**", parse_mode="Markdown", reply_markup=admin_panel_keyboard())
    
    elif data == "admin_overview" and user_id == OWNER_ID:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                total_users = (await cursor.fetchone())[0]
        await query.message.edit_text(f"📊 **Database Overview**\n\nTotal Users: `{total_users}`", parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]))

    elif data == "check_join":
        is_joined = await check_force_join(user_id, context)
        if is_joined:
            await query.message.delete()
            await start(update, context)
        else:
            await query.answer("❌ You have not joined the channel yet!", show_alert=True)

async def main():
    await init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    print("Bot is running...")
    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    
    async def main_runner():
        await init_db()
        application = Application.builder().token(BOT_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))

        print("Bot is running...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        # Keep the bot running
        stop_signal = asyncio.Event()
        try:
            await stop_signal.wait()
        finally:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()

    try:
        asyncio.run(main_runner())
    except (KeyboardInterrupt, RuntimeError):
        pass


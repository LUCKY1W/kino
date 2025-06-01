import os
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, filters, ConversationHandler
)

# === ENV ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# === CONFIGURATION ===
SUPER_ADMINS = [1693559876]  # https://t.me/Ibodov_Umidjon
MOVIE_CHANNEL_ID = -1002243665653  # https://t.me/YangiTV_kino
TRAILER_CHANNEL_ID = -1002183645866  # https://t.me/YangiTV_Premium_Kino

# === DATABASE SETUP ===
conn = sqlite3.connect("db/bot_data.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    joined TIMESTAMP
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT,
    type TEXT,
    part INTEGER,
    file_id TEXT,
    caption TEXT,
    uploaded_at TIMESTAMP
)
""")

conn.commit()

# === STATES ===
CHOOSING_TYPE, AWAITING_VIDEO, AWAITING_TRAILER, AWAITING_CODE = range(4)

# === CONTEXT KEYS ===
UPLOAD_CONTEXT = {}

# === HELPER FUNCTIONS ===
def add_user(user_id):
    now = datetime.now()
    c.execute("INSERT OR IGNORE INTO users (user_id, joined) VALUES (?, ?)", (user_id, now))
    conn.commit()

def add_upload(code, media_type, file_id, caption, part=None):
    now = datetime.now()
    c.execute("INSERT INTO uploads (code, type, part, file_id, caption, uploaded_at) VALUES (?, ?, ?, ?, ?, ?)",
              (code, media_type, part, file_id, caption, now))
    conn.commit()

def get_stats():
    now = datetime.now()
    def count(query, args=()):
        c.execute(query, args)
        return c.fetchone()[0]

    def user_stats():
        return {
            "total": count("SELECT COUNT(*) FROM users"),
            "year": count("SELECT COUNT(*) FROM users WHERE joined >= ?", (now - timedelta(days=365),)),
            "month": count("SELECT COUNT(*) FROM users WHERE joined >= ?", (now - timedelta(days=30),)),
            "week": count("SELECT COUNT(*) FROM users WHERE joined >= ?", (now - timedelta(days=7),)),
            "day": count("SELECT COUNT(*) FROM users WHERE date(joined) = date(?)", (now,))
        }

    def upload_stats():
        return {
            "total": count("SELECT COUNT(*) FROM uploads"),
            "year": count("SELECT COUNT(*) FROM uploads WHERE uploaded_at >= ?", (now - timedelta(days=365),)),
            "month": count("SELECT COUNT(*) FROM uploads WHERE uploaded_at >= ?", (now - timedelta(days=30),)),
            "week": count("SELECT COUNT(*) FROM uploads WHERE uploaded_at >= ?", (now - timedelta(days=7),)),
            "day": count("SELECT COUNT(*) FROM uploads WHERE date(uploaded_at) = date(?)", (now,))
        }

    return user_stats(), upload_stats()

# === HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)
    await update.message.reply_text("👋 Xush kelibsiz! Bu yerda filmlar kod orqali qidiriladi.")

async def statistika_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in SUPER_ADMINS:
        await update.message.reply_text("❌ Sizda ruxsat yo'q.")
        return

    users, uploads = get_stats()
    text = f"""📊 <b>Statistika</b>

👥 <b>Foydalanuvchilar:</b>
├ Jami: <code>{users['total']}</code>
├ Yiliga: <code>{users['year']}</code>
├ Oylik: <code>{users['month']}</code>
├ Haftalik: <code>{users['week']}</code>
└ Kundalik: <code>{users['day']}</code>

🎞 <b>Kino/Serial yuklamalari:</b>
├ Jami: <code>{uploads['total']}</code>
├ Yiliga: <code>{uploads['year']}</code>
├ Oylik: <code>{uploads['month']}</code>
├ Haftalik: <code>{uploads['week']}</code>
└ Kundalik: <code>{uploads['day']}</code>
"""
    await update.message.reply_text(text, parse_mode="HTML")

async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in SUPER_ADMINS:
        await update.message.reply_text("❌ Siz admin emassiz.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton("🎬 Kino", callback_data="upload_movie"),
                 InlineKeyboardButton("📺 Serial", callback_data="upload_serial")]]
    await update.message.reply_text("Nima yuklaysiz?", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSING_TYPE

async def choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    UPLOAD_CONTEXT[user_id] = {"type": "serial" if query.data == "upload_serial" else "movie"}
    await query.message.reply_text("🎥 Videoni yuboring")
    return AWAITING_VIDEO

async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    file_id = update.message.video.file_id
    UPLOAD_CONTEXT[user_id]["file_id"] = file_id
    await update.message.reply_text("🖼 Triller rasm va caption yuboring")
    return AWAITING_TRAILER

async def receive_trailer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    UPLOAD_CONTEXT[user_id]["caption"] = update.message.caption or ""
    await update.message.reply_text("🔢 Kod kiriting")
    return AWAITING_CODE

async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text.strip()
    data = UPLOAD_CONTEXT[user_id]

    if data['type'] == "movie":
        c.execute("SELECT 1 FROM uploads WHERE code = ?", (code,))
        if c.fetchone():
            await update.message.reply_text("❗ Bu kod allaqachon ishlatilgan, boshqa kod kiriting")
            return AWAITING_CODE
        caption = data['caption'] + f"\n🎞 Kod: {code}"
        add_upload(code, data['type'], data['file_id'], caption)
        await update.message.reply_text("✅ Kino yuklandi!")
        UPLOAD_CONTEXT.pop(user_id, None)
        return ConversationHandler.END
    else:
        UPLOAD_CONTEXT[user_id]['code'] = code
        c.execute("SELECT MAX(part) FROM uploads WHERE code = ?", (code,))
        result = c.fetchone()[0]
        part = (result + 1) if result is not None else 1
        caption = data['caption'] + f"\n📺 Kod: {code}\nQism: {part}"
        add_upload(code, data['type'], data['file_id'], caption, part=part)
        await update.message.reply_text(f"✅ {part}-qism yuklandi. Yana qism yuboring yoki /cancel buyrug'i bilan tugating.")
        return AWAITING_VIDEO

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    UPLOAD_CONTEXT.pop(user_id, None)
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END

# === BOT RUNNING ===
app = ApplicationBuilder().token(BOT_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("upload", upload_start)],
    states={
        CHOOSING_TYPE: [CallbackQueryHandler(choose_type)],
        AWAITING_VIDEO: [MessageHandler(filters.VIDEO, receive_video)],
        AWAITING_TRAILER: [MessageHandler(filters.PHOTO, receive_trailer)],
        AWAITING_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=True
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stat", statistika_handler))
app.add_handler(conv_handler)

app.run_polling()

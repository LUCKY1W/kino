import os
import sqlite3
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)
from dotenv import load_dotenv

# === ENV SETUP ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MOVIE_CHANNEL_ID = int(os.getenv("MOVIE_CHANNEL_ID"))
TRAILER_CHANNEL_ID = int(os.getenv("TRAILER_CHANNEL_ID"))

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

# === KONTEXTLAR ===
UPLOAD_CONTEXT = {}

# === FOYDALANUVCHI QO‘SHISH ===
def add_user(user_id):
    now = datetime.now()
    c.execute("INSERT OR IGNORE INTO users (user_id, joined) VALUES (?, ?)", (user_id, now))
    conn.commit()

# === YUKLASH FUNKSIYASI ===
def add_upload(code, media_type, file_id, caption, part=None):
    now = datetime.now()
    c.execute("""
        INSERT INTO uploads (code, type, part, file_id, caption, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (code, media_type, part, file_id, caption, now))
    conn.commit()

# === STATISTIKA O‘QISH ===
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
# === Kino yoki Serial Yuklashni Boshlash ===
async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎬 Kino", callback_data="upload_movie"),
         InlineKeyboardButton("📺 Serial", callback_data="upload_serial")]
    ]
    await update.message.reply_text("Nima yuklamoqchisiz?", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSING_TYPE

# === Kino yoki Serial Tanlandi ===
async def choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    UPLOAD_CONTEXT[user_id] = {"type": "serial" if query.data == "upload_serial" else "movie"}
    await query.message.reply_text("🎥 Kinoni/seriyani yuklang (video sifatida)")
    return AWAITING_VIDEO

# === Video Qabul Qilindi ===
async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    file_id = update.message.video.file_id
    UPLOAD_CONTEXT[user_id]["file_id"] = file_id
    await update.message.reply_text("📸 Triller rasmi va caption (izoh) yuboring")
    return AWAITING_TRAILER

# === Triller qabul qilindi ===
async def receive_trailer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    caption = update.message.caption or ""
    UPLOAD_CONTEXT[user_id]["caption"] = caption
    await update.message.reply_text("🔢 Kodni kiriting (masalan: 49)")
    return AWAITING_CODE

# === Kod qabul qilindi ===
async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text.strip()
    data = UPLOAD_CONTEXT[user_id]

    # Kod takrorlanmasin
    c.execute("SELECT 1 FROM uploads WHERE code = ? AND (type='movie' OR part=1)", (code,))
    if c.fetchone():
        await update.message.reply_text("❗ Bu kod allaqachon ishlatilgan, boshqa kod kiriting")
        return AWAITING_CODE

    media_type = data['type']
    file_id = data['file_id']
    caption = data['caption']
    
    if media_type == "movie":
        caption_final = f"{caption}\n🎞 Kod: {code}"
        add_upload(code, media_type, file_id, caption_final)
        await context.bot.send_video(chat_id=TRAILER_CHANNEL_ID, video=file_id, caption=caption_final)
        await context.bot.send_video(chat_id=MOVIE_CHANNEL_ID, video=file_id)
        await update.message.reply_text("✅ Kino yuklandi!")
    else:
        part = 1
        caption_final = f"{caption}\n📺 Kod: {code}\nQism: {part}"
        add_upload(code, media_type, file_id, caption_final, part=part)
        await context.bot.send_video(chat_id=TRAILER_CHANNEL_ID, video=file_id, caption=caption_final)
        await context.bot.send_video(chat_id=MOVIE_CHANNEL_ID, video=file_id)
        await update.message.reply_text(f"✅ 1-qism yuklandi. Yana qism yuklamoqchi bo‘lsangiz shu kodni qayta kiriting.")
    
    UPLOAD_CONTEXT.pop(user_id, None)
    return ConversationHandler.END
# === Kod bo‘yicha kino/serial izlash ===
async def search_by_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    c.execute("SELECT * FROM uploads WHERE code = ? ORDER BY part ASC", (code,))
    results = c.fetchall()

    if not results:
        await update.message.reply_text("😕 Bunday kod topilmadi.")
        return

    first = results[0]
    if first[2] == "movie":
        await update.message.reply_video(video=first[4], caption=first[5])
    else:
        await update.message.reply_video(video=first[4], caption=first[5])
        await update.message.reply_text(
            "⬇️ Davomini ko‘rish uchun raqam yuboring (masalan: 5)\nKod: " + code
        )
        context.user_data["serial_code"] = code

# === Serial qism izlash ===
async def search_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "serial_code" not in context.user_data:
        await update.message.reply_text("❗ Avval serial kodi yuboring.")
        return
    code = context.user_data["serial_code"]
    try:
        part = int(update.message.text.strip())
    except:
        await update.message.reply_text("⚠️ Noto‘g‘ri raqam!")
        return

    c.execute("SELECT * FROM uploads WHERE code = ? AND part = ?", (code, part))
    row = c.fetchone()
    if not row:
        await update.message.reply_text("❌ Bu qism topilmadi.")
    else:
        await update.message.reply_video(video=row[4], caption=row[5])
TRAILER_CHANNEL_ID = -1002183645866
MOVIE_CHANNEL_ID = -1002243665653
ADMIN_ID = 1693559876

app = ApplicationBuilder().token("7375606355:AAFLqkiZ_MBAtWzSfAhhXIVOgPTFPNM2w94").build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("upload", upload_start)],
    states={
        CHOOSING_TYPE: [CallbackQueryHandler(choose_type)],
        AWAITING_VIDEO: [MessageHandler(filters.VIDEO, receive_video)],
        AWAITING_TRAILER: [MessageHandler(filters.PHOTO, receive_trailer)],
        AWAITING_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
    },
    fallbacks=[]
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stat", statistika_handler))
app.add_handler(conv_handler)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_by_code))
app.add_handler(MessageHandler(filters.Regex(r"^\d+$"), search_episode))

print("✅ Bot ishga tushdi")
app.run_polling()

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, filters, ConversationHandler
)

# === ENV ===
load_dotenv()
BOT_TOKEN = ("7375606355:AAFLqkiZ_MBAtWzSfAhhXIVOgPTFPNM2w94")

# === CONFIGURATION ===
SUPER_ADMINS = [1693559876]  # https://t.me/Ibodov_Umidjon
MOVIE_CHANNEL_ID = -1002243665653  # https://t.me/YangiTV_kino
TRAILER_CHANNEL_ID = -1002183645866  # https://t.me/YangiTV_Premium_Kino

# === DATABASE SETUP ===
# Custom adapter and converter for datetime
def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(s):
    return datetime.fromisoformat(s.decode('utf-8'))

# Register adapter and converter
sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter('TIMESTAMP', convert_datetime)

# Global variables for database connection and cursor
conn = None
c = None

try:
    os.makedirs("db", exist_ok=True)
    conn = sqlite3.connect("db/bot_data.db", check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES)
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
except sqlite3.Error as e:
    print(f"Database error: {e}")
    if conn is None:
        conn = sqlite3.connect(":memory:", check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        print("Warning: Using in-memory database due to connection failure.")

# === STATES ===
CHOOSING_TYPE, AWAITING_VIDEO, AWAITING_TRAILER, AWAITING_CODE, AWAITING_ADMIN, AWAITING_BROADCAST = range(6)

# === CONTEXT KEYS ===
UPLOAD_CONTEXT = {}

# === HELPER FUNCTIONS ===
def add_user(user_id):
    try:
        now = datetime.now(timezone(timedelta(hours=5)))  # UTC+05:00
        c.execute("INSERT OR IGNORE INTO users (user_id, joined) VALUES (?, ?)", (user_id, now))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error adding user: {e}")

def add_upload(code, media_type, file_id, caption, part=None):
    try:
        now = datetime.now(timezone(timedelta(hours=5)))  # UTC+05:00
        c.execute("INSERT INTO uploads (code, type, part, file_id, caption, uploaded_at) VALUES (?, ?, ?, ?, ?, ?)",
                  (code, media_type, part, file_id, caption, now))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error adding upload: {e}")

def get_stats():
    try:
        now = datetime.now(timezone(timedelta(hours=5)))  # UTC+05:00
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
    except sqlite3.Error as e:
        print(f"Error getting stats: {e}")
        return {"total": 0, "year": 0, "month": 0, "week": 0, "day": 0}, {"total": 0, "year": 0, "month": 0, "week": 0, "day": 0}

# === HANDLERS ===
ADMIN_ID = 1693559876  # Asosiy admin

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)

    if user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("🎬 Kino/Serial yuklash", callback_data="upload_start")],
            [InlineKeyboardButton("📊 Statistika", callback_data="stat")],
            [InlineKeyboardButton("➕ Admin qo‘shish", callback_data="add_admin")],
            [InlineKeyboardButton("📢 Xabar yuborish", callback_data="broadcast")]
        ]
        await update.message.reply_text("👋 Admin paneliga xush kelibsiz!", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("👋 Xush kelibsiz! Bu yerda filmlar kod orqali qidiriladi.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Tugma bosilganligini tasdiqlaydi
    user_id = query.from_user.id

    if user_id not in SUPER_ADMINS:
        await query.message.reply_text("❌ Sizda ruxsat yo'q.")
        return

    if query.data == "stat":
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
        await query.message.reply_text(text, parse_mode="HTML")
    elif query.data == "add_admin":
        await query.message.reply_text("➕ Yangi admin qo'shish uchun foydalanuvchi ID'sini yuboring:")
        return AWAITING_ADMIN
    elif query.data == "broadcast":
        await query.message.reply_text("📢 Barcha foydalanuvchilarga yuboriladigan xabarni yuboring:")
        return AWAITING_BROADCAST
    elif query.data == "upload_start":
        keyboard = [[InlineKeyboardButton("🎬 Kino", callback_data="upload_movie"),
                     InlineKeyboardButton("📺 Serial", callback_data="upload_serial")]]
        await query.message.reply_text("Nima yuklaysiz?", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_TYPE

async def choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in SUPER_ADMINS:
        await query.message.reply_text("❌ Siz admin emassiz.")
        return ConversationHandler.END

    UPLOAD_CONTEXT[user_id] = {"type": "serial" if query.data == "upload_serial" else "movie"}
    await query.message.reply_text("🎥 Videoni yuboring")
    return AWAITING_VIDEO

async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not update.message.video:
        await update.message.reply_text("❌ Iltimos, video yuboring!")
        return AWAITING_VIDEO
    file_id = update.message.video.file_id
    UPLOAD_CONTEXT[user_id]["file_id"] = file_id
    await update.message.reply_text("🖼 Triller rasm va caption yuboring")
    return AWAITING_TRAILER

async def receive_trailer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not update.message.photo:
        await update.message.reply_text("❌ Iltimos, rasm yuboring!")
        return AWAITING_TRAILER
    UPLOAD_CONTEXT[user_id]["photo_id"] = update.message.photo[-1].file_id  # Store highest resolution photo
    UPLOAD_CONTEXT[user_id]["caption"] = update.message.caption or ""
    await update.message.reply_text("🔢 Kod kiriting")
    return AWAITING_CODE

async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text.strip()
    data = UPLOAD_CONTEXT[user_id]

    try:
        if data['type'] == "movie":
            c.execute("SELECT 1 FROM uploads WHERE code = ?", (code,))
            if c.fetchone():
                await update.message.reply_text("❗ Bu kod allaqachon ishlatilgan, boshqa kod kiriting")
                return AWAITING_CODE
            caption = data['caption'] + f"\n🎞 Kod: {code}"
            add_upload(code, data['type'], data['file_id'], caption)
            await context.bot.send_video(chat_id=MOVIE_CHANNEL_ID, video=data['file_id'], caption=caption)
            await context.bot.send_photo(chat_id=TRAILER_CHANNEL_ID, photo=data['photo_id'], caption=caption)
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
            await context.bot.send_video(chat_id=MOVIE_CHANNEL_ID, video=data['file_id'], caption=caption)
            await context.bot.send_photo(chat_id=TRAILER_CHANNEL_ID, photo=data['photo_id'], caption=caption)
            await update.message.reply_text(f"✅ {part}-qism yuklandi. Yana qism yuboring yoki /cancel buyrug'i bilan tugating.")
            return AWAITING_VIDEO
    except Exception as e:
        await update.message.reply_text(f"❌ Xato yuz berdi: {str(e)}")
        return ConversationHandler.END

async def receive_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in SUPER_ADMINS:
        await update.message.reply_text("❌ Sizda ruxsat yo'q.")
        return ConversationHandler.END

    try:
        new_admin_id = int(update.message.text.strip())
        if new_admin_id not in SUPER_ADMINS:
            SUPER_ADMINS.append(new_admin_id)
            await update.message.reply_text(f"✅ Foydalanuvchi {new_admin_id} admin sifatida qo'shildi!")
        else:
            await update.message.reply_text("❗ Bu foydalanuvchi allaqachon admin.")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Iltimos, to'g'ri foydalanuvchi ID'sini kiriting (faqat raqamlar).")
        return AWAITING_ADMIN

async def receive_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in SUPER_ADMINS:
        await update.message.reply_text("❌ Sizda ruxsat yo'q.")
        return ConversationHandler.END

    message = update.message.text
    try:
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        for user in users:
            await context.bot.send_message(chat_id=user[0], text=message)
        await update.message.reply_text(f"✅ Xabar {len(users)} foydalanuvchiga yuborildi!")
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Xato yuz berdi: {str(e)}")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    UPLOAD_CONTEXT.pop(user_id, None)
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END

# === BOT RUNNING ===
app = ApplicationBuilder().token(BOT_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("upload", lambda update, context: button_handler(update, context)),
        CallbackQueryHandler(button_handler, pattern="^(upload_start|stat|add_admin|broadcast)$")
    ],
    states={
        CHOOSING_TYPE: [CallbackQueryHandler(choose_type, pattern="^(upload_movie|upload_serial)$")],
        AWAITING_VIDEO: [MessageHandler(filters.VIDEO, receive_video)],
        AWAITING_TRAILER: [MessageHandler(filters.PHOTO, receive_trailer)],
        AWAITING_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
        AWAITING_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_id)],
        AWAITING_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broadcast)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=True
)

app.add_handler(CommandHandler("start", start))
app.add_handler(conv_handler)

if __name__ == "__main__":
    try:
        app.run_polling()
    except Exception as e:
        print(f"Bot error: {e}")
    finally:
        if conn:
            conn.close()

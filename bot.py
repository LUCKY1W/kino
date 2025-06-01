import sqlite3
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaVideo, InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)

# === CONFIGURATION ===
BOT_TOKEN = "7375606355:AAEZVGE9YUIX7ubTDI7dYPAP8K7ojVwlabw"
ADMIN_ID = 1693559876
MOVIE_CHANNEL_ID = -1002243665653
TRAILER_CHANNEL_ID = -1002183645866

# === DATABASE SETUP ===
conn = sqlite3.connect("bot_data.db", check_same_thread=False)
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

c.execute("""
CREATE TABLE IF NOT EXISTS agents (
    user_id INTEGER PRIMARY KEY
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

# === ROLE CHECK ===
def is_admin(user_id):
    return user_id == ADMIN_ID

def is_agent(user_id):
    c.execute("SELECT 1 FROM agents WHERE user_id = ?", (user_id,))
    return c.fetchone() is not None

# === HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)
    if is_admin(user_id):
        keyboard = [
            [InlineKeyboardButton("🎬 Kino yoki Serial yuklash", callback_data="upload")],
            [InlineKeyboardButton("📢 Xabar yuborish", callback_data="broadcast")],
            [InlineKeyboardButton("➕ Admin qo'shish", callback_data="add_agent")],
            [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
        ]
    elif is_agent(user_id):
        keyboard = [
            [InlineKeyboardButton("🎬 Kino yoki Serial yuklash", callback_data="upload")],
            [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
        ]
    else:
        keyboard = []
        await update.message.reply_text("👋 Xush kelibsiz! Bu yerda filmlar kod orqali qidiriladi.")
        return

    await update.message.reply_text("Menyuni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

async def inline_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "upload":
        return await upload_start(update, context)
    elif data == "stats":
        return await statistika_handler(update, context)
    elif data == "add_agent":
        await query.message.reply_text("Agentning user ID sini yuboring")
        return 1000
    elif data == "broadcast":
        await query.message.reply_text("Yuboriladigan xabarni matn sifatida yozing")
        return 1001

async def handle_add_agent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text.strip())
        c.execute("INSERT OR IGNORE INTO agents (user_id) VALUES (?)", (user_id,))
        conn.commit()
        await update.message.reply_text("✅ Yordamchi admin qo‘shildi")
    except:
        await update.message.reply_text("❗ Xato ID")
    return ConversationHandler.END

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    c.execute("SELECT user_id FROM users")
    users = [row[0] for row in c.fetchall()]
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(uid, text)
            count += 1
        except:
            continue
    await update.message.reply_text(f"✅ {count} foydalanuvchiga yuborildi")
    return ConversationHandler.END

async def statistika_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text(text, parse_mode="HTML")

async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🎬 Kino", callback_data="upload_movie"),
                 InlineKeyboardButton("📺 Serial", callback_data="upload_serial")]]
    await update.callback_query.edit_message_text("Nima yuklaysiz?", reply_markup=InlineKeyboardMarkup(keyboard))
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
    await update.message.reply_text("🖼 Triller caption bilan yuboring")
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
    file_id = data['file_id']

    if data['type'] == "movie":
        c.execute("SELECT 1 FROM uploads WHERE code = ?", (code,))
        if c.fetchone():
            await update.message.reply_text("❗ Bu kod allaqachon ishlatilgan, boshqa kod kiriting")
            return AWAITING_CODE
        caption = data['caption'] + f"\n🎞 Kod: {code}"
        await context.bot.send_video(MOVIE_CHANNEL_ID, video=file_id, caption=caption)
        await context.bot.send_photo(TRAILER_CHANNEL_ID, photo=update.message.photo[-1].file_id, caption=caption)
        add_upload(code, "movie", file_id, caption)
        await update.message.reply_text("✅ Kino yuklandi!")
        UPLOAD_CONTEXT.pop(user_id, None)
        return ConversationHandler.END
    else:
        c.execute("SELECT MAX(part) FROM uploads WHERE code = ?", (code,))
        result = c.fetchone()[0]
        part = (result + 1) if result is not None else 1
        caption = data['caption'] + f"\n📺 Kod: {code}\nQism: {part}"
        await context.bot.send_video(MOVIE_CHANNEL_ID, video=file_id, caption=caption)
        add_upload(code, "serial", file_id, caption, part=part)
        UPLOAD_CONTEXT[user_id]['code'] = code
        await update.message.reply_text(f"✅ {part}-qism yuklandi. Keyingi qismini yuborish uchun yana video yuboring yoki /cancel buyrug‘ini bering.")
        return AWAITING_VIDEO

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    UPLOAD_CONTEXT.pop(user_id, None)
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END

# === BOT START ===
app = ApplicationBuilder().token(BOT_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        1000: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_agent)],
        1001: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast)],
        CHOOSING_TYPE: [CallbackQueryHandler(choose_type, pattern="^upload_.*")],
        AWAITING_VIDEO: [MessageHandler(filters.VIDEO, receive_video)],
        AWAITING_TRAILER: [MessageHandler(filters.PHOTO & filters.Caption(True), receive_trailer)],
        AWAITING_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

app.add_handler(conv_handler)
app.add_handler(CallbackQueryHandler(inline_menu_handler))
app.add_handler(CommandHandler("cancel", cancel))

app.run_polling()

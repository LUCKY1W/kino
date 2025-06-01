import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta

# Bot tokenini o'rnating
TOKEN = "7375606355:AAFLqkiZ_MBAtWzSfAhhXIVOgPTFPNM2w94"
bot = telebot.TeleBot(TOKEN)

# Kanal ID lari
TRAILER_CHANNEL_ID = "-1002183645866"
MOVIES_CHANNEL_ID = "-1002243665653"
SERIES_CHANNEL_ID = "-1001537456685"

# Ma'lumotlar bazasini yaratish
conn = sqlite3.connect('kino_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Kino jadvalini yaratish
cursor.execute('''CREATE TABLE IF NOT EXISTS kinolar
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
             kino_id TEXT UNIQUE,
             file_id TEXT,
             nomi TEXT,
             tavsif TEXT,
             type TEXT CHECK(type IN ('movie', 'series')),
             trailer_id TEXT,
             trailer_caption TEXT,
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

# Serial qismlari jadvali
cursor.execute('''CREATE TABLE IF NOT EXISTS serial_qismlari
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
             serial_id TEXT,
             qism_nomeri INTEGER,
             file_id TEXT,
             FOREIGN KEY(serial_id) REFERENCES kinolar(kino_id))''')

# Adminlar jadvali
cursor.execute('''CREATE TABLE IF NOT EXISTS adminlar
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
             user_id INTEGER UNIQUE,
             username TEXT,
             full_name TEXT,
             role TEXT CHECK(role IN ('main_admin', 'helper')),
             added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

# Foydalanuvchilar jadvali
cursor.execute('''CREATE TABLE IF NOT EXISTS foydalanuvchilar
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
             user_id INTEGER UNIQUE,
             username TEXT,
             full_name TEXT,
             joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

# Statistika jadvali
cursor.execute('''CREATE TABLE IF NOT EXISTS statistika
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
             date TEXT UNIQUE,
             new_users INTEGER DEFAULT 0,
             new_movies INTEGER DEFAULT 0)''')

conn.commit()

# Boshlang'ich admin (o'z IDingizni qo'shing)
MAIN_ADMIN_ID = 123456789

# Admin panel tugmalari
def admin_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    cursor.execute("SELECT role FROM adminlar WHERE user_id=?", (chat_id,))
    admin_data = cursor.fetchone()
    
    if admin_data and admin_data[0] == 'main_admin':
        markup.add(
            types.KeyboardButton("🎬 Kino yuklash"),
            types.KeyboardButton("📊 Statistika"),
            types.KeyboardButton("📢 Xabar yuborish"),
            types.KeyboardButton("👨‍💼 Admin qo'shish")
        )
    elif admin_data and admin_data[0] == 'helper':
        markup.add(
            types.KeyboardButton("🎬 Kino yuklash"),
            types.KeyboardButton("📊 Statistika")
        )
    
    markup.add(types.KeyboardButton("🔙 Bosh menyu"))
    return markup

# Foydalanuvchi menyusi
def user_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        types.KeyboardButton("🔍 Kino qidirish"),
        types.KeyboardButton("📺 Serial qidirish")
    )
    return markup

# Start komandasi
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    # Foydalanuvchini bazaga qo'shamiz
    try:
        cursor.execute("INSERT OR IGNORE INTO foydalanuvchilar (user_id, username, full_name) VALUES (?, ?, ?)",
                      (user_id, username, full_name))
        conn.commit()
        
        # Statistika yangilash
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("INSERT OR IGNORE INTO statistika (date) VALUES (?)", (today,))
        cursor.execute("UPDATE statistika SET new_users = new_users + 1 WHERE date=?", (today,))
        conn.commit()
    except Exception as e:
        print(f"Foydalanuvchi qo'shishda xato: {e}")
    
    # Admin yoki foydalanuvchi ekanligini tekshiramiz
    cursor.execute("SELECT role FROM adminlar WHERE user_id=?", (user_id,))
    admin_data = cursor.fetchone()
    
    if admin_data:
        bot.send_message(message.chat.id, "Admin panelga xush kelibsiz!", reply_markup=admin_main_menu(user_id))
    else:
        bot.send_message(message.chat.id, "Kino botiga xush kelibsiz! Quyidagi tugmalardan birini tanlang:", reply_markup=user_main_menu())

# Admin paneli
@bot.message_handler(func=lambda message: message.text == "🔙 Bosh menyu")
def back_to_main(message):
    user_id = message.from_user.id
    cursor.execute("SELECT role FROM adminlar WHERE user_id=?", (user_id,))
    admin_data = cursor.fetchone()
    
    if admin_data:
        bot.send_message(message.chat.id, "Admin panelga xush kelibsiz!", reply_markup=admin_main_menu(user_id))
    else:
        bot.send_message(message.chat.id, "Bosh menyu:", reply_markup=user_main_menu())

# Kino yuklash boshlanishi
@bot.message_handler(func=lambda message: message.text == "🎬 Kino yuklash")
def start_upload_movie(message):
    user_id = message.from_user.id
    cursor.execute("SELECT role FROM adminlar WHERE user_id=?", (user_id,))
    admin_data = cursor.fetchone()
    
    if not admin_data:
        bot.send_message(message.chat.id, "Sizda bunday buyruq uchun ruxsat yo'q.")
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🎥 Film yuklash"),
        types.KeyboardButton("📺 Serial yuklash"),
        types.KeyboardButton("🔙 Bosh menyu")
    )
    
    bot.send_message(message.chat.id, "Nima yuklamoqchisiz?", reply_markup=markup)

# Film yuklash
@bot.message_handler(func=lambda message: message.text == "🎥 Film yuklash")
def upload_movie(message):
    msg = bot.send_message(message.chat.id, "Iltimos, filmni yuboring (video yoki fayl shaklida):")
    bot.register_next_step_handler(msg, process_movie_file)

def process_movie_file(message):
    try:
        if message.video:
            file_id = message.video.file_id
        elif message.document:
            file_id = message.document.file_id
        else:
            bot.send_message(message.chat.id, "Iltimos, video yoki fayl shaklida yuboring!")
            return
        
        # Vaqtincha saqlaymiz
        cursor.execute("INSERT OR REPLACE INTO temp_files (chat_id, file_id, type) VALUES (?, ?, ?)", 
                      (message.chat.id, file_id, 'movie'))
        conn.commit()
        
        msg = bot.send_message(message.chat.id, "Endi film uchun triller rasmini yuboring (foto shaklida):")
        bot.register_next_step_handler(msg, process_movie_trailer, file_id)
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

def process_movie_trailer(message, movie_file_id):
    try:
        if not message.photo:
            bot.send_message(message.chat.id, "Iltimos, faqat rasm yuboring!")
            return
        
        trailer_photo_id = message.photo[-1].file_id
        
        # Vaqtincha saqlaymiz
        cursor.execute("UPDATE temp_files SET trailer_id=? WHERE chat_id=?", 
                      (trailer_photo_id, message.chat.id))
        conn.commit()
        
        msg = bot.send_message(message.chat.id, "Endi film uchun caption (tavsif) yuboring:")
        bot.register_next_step_handler(msg, process_movie_caption, movie_file_id, trailer_photo_id)
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

def process_movie_caption(message, movie_file_id, trailer_photo_id):
    try:
        caption = message.text
        
        # Vaqtincha saqlaymiz
        cursor.execute("UPDATE temp_files SET trailer_caption=? WHERE chat_id=?", 
                      (caption, message.chat.id))
        conn.commit()
        
        msg = bot.send_message(message.chat.id, "Endi film uchun maxsus kod yuboring (faqat raqamlardan iborat bo'lsin):")
        bot.register_next_step_handler(msg, process_movie_code, movie_file_id, trailer_photo_id, caption)
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

def process_movie_code(message, movie_file_id, trailer_photo_id, caption):
    try:
        kino_id = message.text
        
        if not kino_id.isdigit():
            bot.send_message(message.chat.id, "Kod faqat raqamlardan iborat bo'lishi kerak!")
            return
        
        # Kod bandligini tekshiramiz
        cursor.execute("SELECT id FROM kinolar WHERE kino_id=?", (kino_id,))
        if cursor.fetchone():
            bot.send_message(message.chat.id, "Bu kod band. Iltimos, boshqa kod kiriting:")
            bot.register_next_step_handler(message, process_movie_code, movie_file_id, trailer_photo_id, caption)
            return
        
        # Kanalga triller yuboramiz
        sent_message = bot.send_photo(TRAILER_CHANNEL_ID, trailer_photo_id, 
                                    caption=f"{caption}\n\nKino kodi: {kino_id}")
        
        # Kino kanaliga filmni yuboramiz
        try:
            bot.send_video(MOVIES_CHANNEL_ID, movie_file_id, caption=f"{caption}\nKino kodi: {kino_id}")
        except:
            bot.send_document(MOVIES_CHANNEL_ID, movie_file_id, caption=f"{caption}\nKino kodi: {kino_id}")
        
        # Bazaga saqlaymiz
        cursor.execute("INSERT INTO kinolar (kino_id, file_id, nomi, tavsif, type, trailer_id, trailer_caption) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (kino_id, movie_file_id, caption[:100], caption, 'movie', trailer_photo_id, caption))
        conn.commit()
        
        # Statistika yangilash
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("INSERT OR IGNORE INTO statistika (date) VALUES (?)", (today,))
        cursor.execute("UPDATE statistika SET new_movies = new_movies + 1 WHERE date=?", (today,))
        conn.commit()
        
        bot.send_message(message.chat.id, f"Film muvaffaqiyatli yuklandi!\nKod: {kino_id}", reply_markup=admin_main_menu(message.chat.id))
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

# Serial yuklash
@bot.message_handler(func=lambda message: message.text == "📺 Serial yuklash")
def upload_series(message):
    msg = bot.send_message(message.chat.id, "Iltimos, serialning birinchi qismini yuboring (video yoki fayl shaklida):")
    bot.register_next_step_handler(msg, process_series_file)

def process_series_file(message):
    try:
        if message.video:
            file_id = message.video.file_id
        elif message.document:
            file_id = message.document.file_id
        else:
            bot.send_message(message.chat.id, "Iltimos, video yoki fayl shaklida yuboring!")
            return
        
        # Vaqtincha saqlaymiz
        cursor.execute("INSERT OR REPLACE INTO temp_files (chat_id, file_id, type) VALUES (?, ?, ?)", 
                      (message.chat.id, file_id, 'series'))
        conn.commit()
        
        msg = bot.send_message(message.chat.id, "Endi serial uchun triller rasmini yuboring (foto shaklida):")
        bot.register_next_step_handler(msg, process_series_trailer, file_id)
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

def process_series_trailer(message, series_file_id):
    try:
        if not message.photo:
            bot.send_message(message.chat.id, "Iltimos, faqat rasm yuboring!")
            return
        
        trailer_photo_id = message.photo[-1].file_id
        
        # Vaqtincha saqlaymiz
        cursor.execute("UPDATE temp_files SET trailer_id=? WHERE chat_id=?", 
                      (trailer_photo_id, message.chat.id))
        conn.commit()
        
        msg = bot.send_message(message.chat.id, "Endi serial uchun caption (tavsif) yuboring:")
        bot.register_next_step_handler(msg, process_series_caption, series_file_id, trailer_photo_id)
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

def process_series_caption(message, series_file_id, trailer_photo_id):
    try:
        caption = message.text
        
        # Vaqtincha saqlaymiz
        cursor.execute("UPDATE temp_files SET trailer_caption=? WHERE chat_id=?", 
                      (caption, message.chat.id))
        conn.commit()
        
        msg = bot.send_message(message.chat.id, "Endi serial uchun maxsus kod yuboring (faqat raqamlardan iborat bo'lsin):")
        bot.register_next_step_handler(msg, process_series_code, series_file_id, trailer_photo_id, caption)
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

def process_series_code(message, series_file_id, trailer_photo_id, caption):
    try:
        kino_id = message.text
        
        if not kino_id.isdigit():
            bot.send_message(message.chat.id, "Kod faqat raqamlardan iborat bo'lishi kerak!")
            return
        
        # Kod bandligini tekshiramiz
        cursor.execute("SELECT id FROM kinolar WHERE kino_id=?", (kino_id,))
        if cursor.fetchone():
            bot.send_message(message.chat.id, "Bu kod band. Iltimos, boshqa kod kiriting:")
            bot.register_next_step_handler(message, process_series_code, series_file_id, trailer_photo_id, caption)
            return
        
        # Kanalga triller yuboramiz
        sent_message = bot.send_photo(TRAILER_CHANNEL_ID, trailer_photo_id, 
                                    caption=f"{caption}\n\nSerial kodi: {kino_id}")
        
        # Serial kanaliga birinchi qismni yuboramiz
        try:
            bot.send_video(SERIES_CHANNEL_ID, series_file_id, caption=f"{caption}\n1-qism\nSerial kodi: {kino_id}")
        except:
            bot.send_document(SERIES_CHANNEL_ID, series_file_id, caption=f"{caption}\n1-qism\nSerial kodi: {kino_id}")
        
        # Bazaga saqlaymiz
        cursor.execute("INSERT INTO kinolar (kino_id, file_id, nomi, tavsif, type, trailer_id, trailer_caption) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (kino_id, series_file_id, caption[:100], caption, 'series', trailer_photo_id, caption))
        conn.commit()
        
        # Birinchi qismni qismlar jadvaliga qo'shamiz
        cursor.execute("INSERT INTO serial_qismlari (serial_id, qism_nomeri, file_id) VALUES (?, ?, ?)",
                      (kino_id, 1, series_file_id))
        conn.commit()
        
        # Statistika yangilash
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("INSERT OR IGNORE INTO statistika (date) VALUES (?)", (today,))
        cursor.execute("UPDATE statistika SET new_movies = new_movies + 1 WHERE date=?", (today,))
        conn.commit()
        
        # Keyingi qismni yuklash uchun menyu
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton("⏭ Keyingi qismni yuklash"),
            types.KeyboardButton("🏁 Serialni tugatish")
        )
        
        bot.send_message(message.chat.id, f"Serialning 1-qismi muvaffaqiyatli yuklandi!\nKod: {kino_id}\n\nKeyingi qismni yuklashni davom ettirasizmi?", reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

# Serialning keyingi qismini yuklash
@bot.message_handler(func=lambda message: message.text == "⏭ Keyingi qismni yuklash")
def continue_series_upload(message):
    msg = bot.send_message(message.chat.id, "Iltimos, serialning keyingi qismini yuboring (video yoki fayl shaklida):")
    bot.register_next_step_handler(msg, process_next_series_part)

def process_next_series_part(message):
    try:
        if message.video:
            file_id = message.video.file_id
        elif message.document:
            file_id = message.document.file_id
        else:
            bot.send_message(message.chat.id, "Iltimos, video yoki fayl shaklida yuboring!")
            return
        
        # Oxirgi serial kodini olamiz
        cursor.execute("SELECT kino_id FROM temp_files WHERE chat_id=? AND type='series'", (message.chat.id,))
        serial_data = cursor.fetchone()
        
        if not serial_data:
            bot.send_message(message.chat.id, "Serial topilmadi. Iltimos, boshidan boshlang.")
            return
        
        serial_id = serial_data[0]
        
        # Qism sonini aniqlaymiz
        cursor.execute("SELECT MAX(qism_nomeri) FROM serial_qismlari WHERE serial_id=?", (serial_id,))
        last_part = cursor.fetchone()[0] or 0
        new_part = last_part + 1
        
        # Serial kanaliga qismni yuboramiz
        cursor.execute("SELECT nomi FROM kinolar WHERE kino_id=?", (serial_id,))
        serial_name = cursor.fetchone()[0]
        
        try:
            bot.send_video(SERIES_CHANNEL_ID, file_id, caption=f"{serial_name}\n{new_part}-qism\nSerial kodi: {serial_id}")
        except:
            bot.send_document(SERIES_CHANNEL_ID, file_id, caption=f"{serial_name}\n{new_part}-qism\nSerial kodi: {serial_id}")
        
        # Bazaga saqlaymiz
        cursor.execute("INSERT INTO serial_qismlari (serial_id, qism_nomeri, file_id) VALUES (?, ?, ?)",
                      (serial_id, new_part, file_id))
        conn.commit()
        
        # Statistika yangilash
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("INSERT OR IGNORE INTO statistika (date) VALUES (?)", (today,))
        cursor.execute("UPDATE statistika SET new_movies = new_movies + 1 WHERE date=?", (today,))
        conn.commit()
        
        # Keyingi qismni yuklash uchun menyu
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton("⏭ Keyingi qismni yuklash"),
            types.KeyboardButton("🏁 Serialni tugatish")
        )
        
        bot.send_message(message.chat.id, f"Serialning {new_part}-qismi muvaffaqiyatli yuklandi!\n\nYana qism qo'shasizmi?", reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

# Serial yuklashni tugatish
@bot.message_handler(func=lambda message: message.text == "🏁 Serialni tugatish")
def finish_series_upload(message):
    # Vaqtincha ma'lumotlarni o'chiramiz
    cursor.execute("DELETE FROM temp_files WHERE chat_id=?", (message.chat.id,))
    conn.commit()
    
    bot.send_message(message.chat.id, "Serial yuklash tugatildi!", reply_markup=admin_main_menu(message.chat.id))

# Admin qo'shish
@bot.message_handler(func=lambda message: message.text == "👨‍💼 Admin qo'shish")
def add_admin(message):
    user_id = message.from_user.id
    cursor.execute("SELECT role FROM adminlar WHERE user_id=?", (user_id,))
    admin_data = cursor.fetchone()
    
    if not admin_data or admin_data[0] != 'main_admin':
        bot.send_message(message.chat.id, "Sizda bunday buyruq uchun ruxsat yo'q.")
        return
    
    msg = bot.send_message(message.chat.id, "Yangi adminning Telegram ID sini yuboring:")
    bot.register_next_step_handler(msg, process_admin_id)

def process_admin_id(message):
    try:
        new_admin_id = int(message.text)
        
        # Foydalanuvchi borligini tekshiramiz
        try:
            user_info = bot.get_chat(new_admin_id)
        except:
            bot.send_message(message.chat.id, "Bunday foydalanuvchi topilmadi yoki botdan foydalanmagan.")
            return
        
        msg = bot.send_message(message.chat.id, "Admin huquqini tanlang:", reply_markup=admin_role_keyboard())
        bot.register_next_step_handler(msg, process_admin_role, new_admin_id, user_info)
    except ValueError:
        bot.send_message(message.chat.id, "Iltimos, faqat raqam yuboring!")
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

def admin_role_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("Asosiy admin"),
        types.KeyboardButton("Yordamchi admin")
    )
    return markup

def process_admin_role(message, new_admin_id, user_info):
    role = 'helper' if message.text == "Yordamchi admin" else 'main_admin'
    
    try:
        cursor.execute("INSERT INTO adminlar (user_id, username, full_name, role) VALUES (?, ?, ?, ?)",
                      (new_admin_id, user_info.username, user_info.first_name, role))
        conn.commit()
        
        bot.send_message(message.chat.id, f"Yangi admin muvaffaqiyatli qo'shildi!\nIsmi: {user_info.first_name}\nRoli: {role}")
        
        # Yangi adminga xabar yuboramiz
        try:
            bot.send_message(new_admin_id, f"Siz {message.from_user.first_name} tomonidan admin qilib tayinlandingiz!")
        except:
            pass
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")
    
    bot.send_message(message.chat.id, "Admin panel:", reply_markup=admin_main_menu(message.chat.id))

# Statistika
@bot.message_handler(func=lambda message: message.text == "📊 Statistika")
def show_stats(message):
    user_id = message.from_user.id
    cursor.execute("SELECT role FROM adminlar WHERE user_id=?", (user_id,))
    admin_data = cursor.fetchone()
    
    if not admin_data:
        bot.send_message(message.chat.id, "Sizda bunday buyruq uchun ruxsat yo'q.")
        return
    
    # Jami foydalanuvchilar
    cursor.execute("SELECT COUNT(*) FROM foydalanuvchilar")
    total_users = cursor.fetchone()[0]
    
    # Jami kinolar
    cursor.execute("SELECT COUNT(*) FROM kinolar")
    total_movies = cursor.fetchone()[0]
    
    # Bugungi statistika
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT new_users, new_movies FROM statistika WHERE date=?", (today,))
    today_stats = cursor.fetchone() or (0, 0)
    
    # Haftalik statistika
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    cursor.execute("SELECT SUM(new_users), SUM(new_movies) FROM statistika WHERE date >= ?", (week_ago,))
    week_stats = cursor.fetchone() or (0, 0)
    
    # Oylik statistika
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    cursor.execute("SELECT SUM(new_users), SUM(new_movies) FROM statistika WHERE date >= ?", (month_ago,))
    month_stats = cursor.fetchone() or (0, 0)
    
    # Yillik statistika
    year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    cursor.execute("SELECT SUM(new_users), SUM(new_movies) FROM statistika WHERE date >= ?", (year_ago,))
    year_stats = cursor.fetchone() or (0, 0)
    
    stats_text = f"""📊 Bot statistikasi:

👥 Foydalanuvchilar:
- Jami: {total_users}
- Bugun: {today_stats[0]}
- Haftada: {week_stats[0]}
- Oyida: {month_stats[0]}
- Yilda: {year_stats[0]}

🎬 Kinolar:
- Jami: {total_movies}
- Bugun: {today_stats[1]}
- Haftada: {week_stats[1]}
- Oyida: {month_stats[1]}
- Yilda: {year_stats[1]}
"""
    bot.send_message(message.chat.id, stats_text)

# Kino qidirish
@bot.message_handler(func=lambda message: message.text == "🔍 Kino qidirish")
def search_movie(message):
    msg = bot.send_message(message.chat.id, "Kino kodini yuboring:")
    bot.register_next_step_handler(msg, process_movie_search)

def process_movie_search(message):
    try:
        kino_id = message.text
        
        cursor.execute("SELECT file_id, nomi, tavsif, type FROM kinolar WHERE kino_id=?", (kino_id,))
        kino_data = cursor.fetchone()
        
        if not kino_data:
            bot.send_message(message.chat.id, "Ushbu kodga mos kino topilmadi.")
            return
        
        file_id, nomi, tavsif, kino_type = kino_data
        
        if kino_type == 'movie':
            # Filmni yuboramiz
            try:
                bot.send_video(message.chat.id, file_id, caption=f"{nomi}\n\n{tavsif}")
            except:
                bot.send_document(message.chat.id, file_id, caption=f"{nomi}\n\n{tavsif}")
        else:
            # Serialning birinchi qismini yuboramiz
            cursor.execute("SELECT file_id FROM serial_qismlari WHERE serial_id=? AND qism_nomeri=1", (kino_id,))
            first_part = cursor.fetchone()
            
            if first_part:
                try:
                    bot.send_video(message.chat.id, first_part[0], caption=f"{nomi}\n1-qism\n\n{tavsif}")
                except:
                    bot.send_document(message.chat.id, first_part[0], caption=f"{nomi}\n1-qism\n\n{tavsif}")
                
                # Qidirish uchun tugma
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("⏭ Keyingi qism", callback_data=f"next_{kino_id}_2"),
                    types.InlineKeyboardButton("🔍 Qismni topish", callback_data=f"find_{kino_id}")
                )
                
                bot.send_message(message.chat.id, "Serialning boshqa qismlarini ko'rish:", reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

# Serial qidirish
@bot.message_handler(func=lambda message: message.text == "📺 Serial qidirish")
def search_series(message):
    msg = bot.send_message(message.chat.id, "Serial kodini yuboring:")
    bot.register_next_step_handler(msg, process_series_search)

def process_series_search(message):
    try:
        kino_id = message.text
        
        cursor.execute("SELECT nomi, tavsif FROM kinolar WHERE kino_id=? AND type='series'", (kino_id,))
        serial_data = cursor.fetchone()
        
        if not serial_data:
            bot.send_message(message.chat.id, "Ushbu kodga mos serial topilmadi.")
            return
        
        nomi, tavsif = serial_data
        
        # Serialning birinchi qismini yuboramiz
        cursor.execute("SELECT file_id FROM serial_qismlari WHERE serial_id=? AND qism_nomeri=1", (kino_id,))
        first_part = cursor.fetchone()
        
        if first_part:
            try:
                bot.send_video(message.chat.id, first_part[0], caption=f"{nomi}\n1-qism\n\n{tavsif}")
            except:
                bot.send_document(message.chat.id, first_part[0], caption=f"{nomi}\n1-qism\n\n{tavsif}")
            
            # Qidirish uchun tugma
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("⏭ Keyingi qism", callback_data=f"next_{kino_id}_2"),
                types.InlineKeyboardButton("🔍 Qismni topish", callback_data=f"find_{kino_id}")
            )
            
            bot.send_message(message.chat.id, "Serialning boshqa qismlarini ko'rish:", reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

# Callback querylar
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    try:
        if call.data.startswith("next_"):
            # Keyingi qismni yuborish
            parts = call.data.split("_")
            kino_id = parts[1]
            qism_nomeri = int(parts[2])
            
            cursor.execute("SELECT file_id FROM serial_qismlari WHERE serial_id=? AND qism_nomeri=?", (kino_id, qism_nomeri))
            part_data = cursor.fetchone()
            
            if part_data:
                cursor.execute("SELECT nomi, tavsif FROM kinolar WHERE kino_id=?", (kino_id,))
                serial_info = cursor.fetchone()
                
                if serial_info:
                    nomi, tavsif = serial_info
                    try:
                        bot.send_video(call.message.chat.id, part_data[0], caption=f"{nomi}\n{qism_nomeri}-qism\n\n{tavsif}")
                    except:
                        bot.send_document(call.message.chat.id, part_data[0], caption=f"{nomi}\n{qism_nomeri}-qism\n\n{tavsif}")
                    
                    # Keyingi qism mavjudligini tekshiramiz
                    cursor.execute("SELECT file_id FROM serial_qismlari WHERE serial_id=? AND qism_nomeri=?", (kino_id, qism_nomeri+1))
                    next_part = cursor.fetchone()
                    
                    markup = types.InlineKeyboardMarkup()
                    if next_part:
                        markup.add(
                            types.InlineKeyboardButton("⏭ Keyingi qism", callback_data=f"next_{kino_id}_{qism_nomeri+1}"),
                            types.InlineKeyboardButton("🔍 Qismni topish", callback_data=f"find_{kino_id}")
                        )
                    else:
                        markup.add(
                            types.InlineKeyboardButton("🔍 Qismni topish", callback_data=f"find_{kino_id}")
                        )
                    
                    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
            else:
                bot.answer_callback_query(call.id, "Bu serialning oxirgi qismi!")
        
        elif call.data.startswith("find_"):
            # Qismni topish
            kino_id = call.data.split("_")[1]
            
            msg = bot.send_message(call.message.chat.id, "Qaysi qismini ko'rmoqchisiz? Qism raqamini yuboring:")
            bot.register_next_step_handler(msg, process_find_part, kino_id)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Xatolik yuz berdi: {e}")

def process_find_part(message, kino_id):
    try:
        qism_nomeri = int(message.text)
        
        cursor.execute("SELECT file_id FROM serial_qismlari WHERE serial_id=? AND qism_nomeri=?", (kino_id, qism_nomeri))
        part_data = cursor.fetchone()
        
        if part_data:
            cursor.execute("SELECT nomi, tavsif FROM kinolar WHERE kino_id=?", (kino_id,))
            serial_info = cursor.fetchone()
            
            if serial_info:
                nomi, tavsif = serial_info
                try:
                    bot.send_video(message.chat.id, part_data[0], caption=f"{nomi}\n{qism_nomeri}-qism\n\n{tavsif}")
                except:
                    bot.send_document(message.chat.id, part_data[0], caption=f"{nomi}\n{qism_nomeri}-qism\n\n{tavsif}")
                
                # Keyingi qism mavjudligini tekshiramiz
                cursor.execute("SELECT file_id FROM serial_qismlari WHERE serial_id=? AND qism_nomeri=?", (kino_id, qism_nomeri+1))
                next_part = cursor.fetchone()
                
                markup = types.InlineKeyboardMarkup()
                if next_part:
                    markup.add(
                        types.InlineKeyboardButton("⏭ Keyingi qism", callback_data=f"next_{kino_id}_{qism_nomeri+1}"),
                        types.InlineKeyboardButton("🔍 Qismni topish", callback_data=f"find_{kino_id}")
                    )
                else:
                    markup.add(
                        types.InlineKeyboardButton("🔍 Qismni topish", callback_data=f"find_{kino_id}")
                    )
                
                bot.send_message(message.chat.id, "Boshqa qismni ko'rish:", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, "Ushbu raqamda qism topilmadi.")
    except ValueError:
        bot.send_message(message.chat.id, "Iltimos, faqat raqam yuboring!")
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

# Xabar yuborish
@bot.message_handler(func=lambda message: message.text == "📢 Xabar yuborish")
def send_broadcast(message):
    user_id = message.from_user.id
    cursor.execute("SELECT role FROM adminlar WHERE user_id=?", (user_id,))
    admin_data = cursor.fetchone()
    
    if not admin_data or admin_data[0] != 'main_admin':
        bot.send_message(message.chat.id, "Sizda bunday buyruq uchun ruxsat yo'q.")
        return
    
    msg = bot.send_message(message.chat.id, "Barcha foydalanuvchilarga yuborish uchun xabarni kiriting:")
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    try:
        text = message.text
        users = cursor.execute("SELECT user_id FROM foydalanuvchilar").fetchall()
        
        success = 0
        fail = 0
        
        for user in users:
            try:
                bot.send_message(user[0], text)
                success += 1
            except:
                fail += 1
        
        bot.send_message(message.chat.id, f"Xabar yuborildi!\nMuvaffaqiyatli: {success}\nMuvaffaqiyatsiz: {fail}")
    except Exception as e:
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

# Botni ishga tushurish
if __name__ == '__main__':
    # Vaqtincha fayllar uchun jadval
    cursor.execute('''CREATE TABLE IF NOT EXISTS temp_files
                 (chat_id INTEGER PRIMARY KEY,
                 file_id TEXT,
                 type TEXT,
                 trailer_id TEXT,
                 trailer_caption TEXT)''')
    conn.commit()
    
    # Asosiy adminni qo'shamiz
    try:
        cursor.execute("INSERT OR IGNORE INTO adminlar (user_id, role) VALUES (?, ?)", 
                      (MAIN_ADMIN_ID, 'main_admin'))
        conn.commit()
    except:
        pass
    
    print("Bot ishga tushdi...")
    bot.polling()

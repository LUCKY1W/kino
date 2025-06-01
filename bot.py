# kino_bot.py

import json
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from datetime import datetime, timedelta
import os

# Token from .env
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# Super admin ID
SUPER_ADMIN_ID = 1693559876

# Fayl yo'llari
USERS_FILE = 'data/users.json'
ADMINS_FILE = 'data/admins.json'
MOVIES_FILE = 'data/movies.json'
SERIES_FILE = 'data/series.json'

# ========== HELPERS ==========
def load_json(file):
    if not os.path.exists(file): return [] if 'users' in file or 'movies' in file else {}
    with open(file, 'r') as f:
        return json.load(f)

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)

def load_users(): return load_json(USERS_FILE)
def save_users(data): save_json(USERS_FILE, data)
def load_admins(): return load_json(ADMINS_FILE)
def save_admins(data): save_json(ADMINS_FILE, data)
def load_movies(): return load_json(MOVIES_FILE)
def save_movies(data): save_json(MOVIES_FILE, data)
def load_series(): return load_json(SERIES_FILE)
def save_series(data): save_json(SERIES_FILE, data)

# ========== STATES ==========
class BroadcastStates(StatesGroup):
    waiting_for_broadcast_text = State()

# ========== START ==========
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    users = load_users()
    found = False
    for u in users:
        if u['user_id'] == user_id:
            u['last_active'] = str(datetime.now().date())
            found = True
            break
    if not found:
        users.append({
            "user_id": user_id,
            "role": "user",
            "joined_at": str(datetime.now().date()),
            "last_active": str(datetime.now().date())
        })
    save_users(users)
    await message.answer("👋 Botga xush kelibsiz!")

# ========== ADMIN MENU ==========
def admin_main_keyboard():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton("🎬 Kino yuklash", callback_data="upload_movie")],
        [types.InlineKeyboardButton("👤 Adminlarni boshqarish", callback_data="manage_admins")],
        [types.InlineKeyboardButton("📊 Statistika", callback_data="view_stats")],
        [types.InlineKeyboardButton("📡 Kanallar", callback_data="manage_channels")],
        [types.InlineKeyboardButton("📢 Xabar yuborish", callback_data="broadcast_message")]
    ])

@dp.message_handler(lambda m: m.from_user.id == SUPER_ADMIN_ID, commands=['admin'])
async def show_admin_panel(message: types.Message):
    await message.answer("🔧 Admin paneli:", reply_markup=admin_main_keyboard())

# ========== STATISTICS ==========
@dp.callback_query_handler(lambda c: c.data == "view_stats")
async def show_statistics(callback: types.CallbackQuery):
    users = load_users()
    movies = load_movies()
    series = load_series()
    admins = load_admins()

    today = datetime.now().date()
    first_day = today.replace(day=1)
    active_window = today - timedelta(days=7)

    total = len(users)
    today_count = sum(1 for u in users if u.get('joined_at') == str(today))
    month_count = sum(1 for u in users if datetime.fromisoformat(u.get('joined_at')) >= first_day)
    active = sum(1 for u in users if datetime.fromisoformat(u.get('last_active')) >= active_window)

    movie_count = len(movies)
    series_eps = len(series)
    series_codes = len(set(s['series_code'] for s in series))
    today_uploads = sum(1 for m in movies if m['date'] == str(today)) + sum(1 for s in series if s['date'] == str(today))

    admin_count = len(admins.get('admins', []))
    agent_count = sum(1 for u in users if u.get("role") == "agent")

    msg = (
        f"📊 Statistika:\n\n"
        f"🎬 Jami kinolar: {movie_count}\n"
        f"🎞 Jami serial epizodlari: {series_eps}\n"
        f"📁 Umumiy kodlar: {movie_count + series_codes}\n"
        f"📅 Bugun yuklangan: {today_uploads}\n\n"
        f"👥 Foydalanuvchilar: {total}\n"
        f"📆 Shu oyda: {month_count}\n"
        f"📅 Bugun: {today_count}\n"
        f"🟢 Aktiv (7 kun): {active}\n\n"
        f"👑 Adminlar: {admin_count}\n"
        f"🤝 Agentlar: {agent_count}"
    )
    await callback.message.answer(msg)
    await callback.answer()

# ========== BROADCAST ==========
@dp.callback_query_handler(lambda c: c.data == "broadcast_message")
async def ask_broadcast_text(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📢 Yuboriladigan xabar matnini yuboring:")
    await BroadcastStates.waiting_for_broadcast_text.set()
    await callback.answer()

@dp.message_handler(state=BroadcastStates.waiting_for_broadcast_text, content_types=types.ContentTypes.TEXT)
async def broadcast_text_to_users(message: types.Message, state: FSMContext):
    text = message.text
    users = load_users()

    sent, failed, failed_ids = 0, 0, []
    for u in users:
        try:
            await bot.send_message(u['user_id'], text)
            sent += 1
        except:
            failed += 1
            failed_ids.append(u['user_id'])

    await state.update_data(failed_ids=failed_ids, broadcast_text=text)

    msg = (
        f"📢 Xabar yuborildi!\n\n"
        f"👥 Jami: {len(users)}\n"
        f"✅ Yuborildi: {sent}\n"
        f"❌ Yuborilmadi: {failed}\n"
    )

    if failed:
        keyboard = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🔁 Qayta yuborish", callback_data="retry_failed")
        )
        await message.answer(msg, reply_markup=keyboard)
    else:
        await message.answer(msg)

    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "retry_failed")
async def retry_failed_broadcast(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    failed_ids = data.get('failed_ids', [])
    text = data.get('broadcast_text', '')

    sent, still_failed = 0, 0
    for uid in failed_ids:
        try:
            await bot.send_message(uid, text)
            sent += 1
        except:
            still_failed += 1

    msg = (
        f"🔁 Qayta yuborish natijasi:\n\n"
        f"✅ Yuborildi: {sent}\n"
        f"❌ Yuborilmadi: {still_failed}"
    )
    await callback.message.answer(msg)
    await callback.answer("Yuborish yakunlandi")

# ========== RUN ==========
if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    executor.start_polling(dp, skip_updates=True)

from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from config import TOKEN
import handlers  # handlers/__init__.py orqali import qilinadi

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

handlers.register_all_handlers(dp)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

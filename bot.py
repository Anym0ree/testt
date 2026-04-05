from database import db
from keyboards import get_main_menu
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Привет! Используй /note текст — чтобы добавить заметку", reply_markup=get_main_menu())

@dp.message_handler(commands=['note'])
async def add_note(message: types.Message):
    text = message.get_args()
    if not text:
        await message.answer("Напиши: /note текст заметки")
        return
    db.add_note(message.from_user.id, text)
    await message.answer(f"✅ Заметка добавлена: {text}")

@dp.message_handler(commands=['notes'])
async def list_notes(message: types.Message):
    notes = db.get_notes(message.from_user.id)
    if not notes:
        await message.answer("Нет заметок")
        return
    text = "📋 Твои заметки:\n\n"
    for i, note in enumerate(reversed(notes), 1):
        text += f"{i}. {note['text'][:100]}\n   📅 {note['date']}\n"
        text += f"   🗑 /del_{note['id']}\n\n"
    await message.answer(text)

@dp.message_handler(lambda m: m.text.startswith('/del_'))
async def delete_note(message: types.Message):
    note_id = int(message.text.split('_')[1])
    db.delete_note_by_id(message.from_user.id, note_id)
    await message.answer(f"✅ Заметка {note_id} удалена")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

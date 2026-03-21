import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import db
from keyboards import *

# Логирование (для отладки)
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========== СОСТОЯНИЯ ==========
class SleepStates(StatesGroup):
    bed_time = State()
    wake_time = State()
    quality = State()
    woke_night = State()
    note = State()

class CheckinStates(StatesGroup):
    energy = State()
    stress = State()
    emotion = State()
    note = State()

class DaySummaryStates(StatesGroup):
    score = State()
    best = State()
    worst = State()
    gratitude = State()
    note = State()

class FoodStates(StatesGroup):
    meal_type = State()
    food_text = State()

class DrinkStates(StatesGroup):
    drink_type = State()
    amount = State()

class ThoughtStates(StatesGroup):
    thought_text = State()
    thought_type = State()
    action = State()

# ========== КОМАНДЫ ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я твой личный дневник-трекер.\n\n"
        "Что я умею:\n"
        "• 🛌 Записывать сон\n"
        "• ⚡️ Делать чек-ины (энергия, стресс, эмоции)\n"
        "• 🍽 Записывать еду и напитки\n"
        "• 💭 Сохранять мысли\n"
        "• 📊 Показывать статистику\n"
        "• 📤 Экспортировать все данные\n\n"
        "Главное меню — /menu",
        reply_markup=get_main_menu()
    )

@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer("📱 Главное меню", reply_markup=get_main_menu())

@dp.message(Command("skip"))
async def cmd_skip(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("⏭ Текущий опрос пропущен", reply_markup=get_main_menu())

# ========== СОН ==========
# (все обработчики сна остаются как были, не меняем)

# ========== ЧЕК-ИН ==========
# (остаются без изменений)

# ========== ИТОГ ДНЯ ==========
# (остаются без изменений)

# ========== ЕДА ==========
# (остаются без изменений)

# ========== НАПИТКИ ==========
@dp.message(F.text == "🥤 Напитки")
async def drink_start(message: Message, state: FSMContext):
    await message.answer("Что выпил?", reply_markup=get_drink_type_buttons())
    await state.set_state(DrinkStates.drink_type)

@dp.message(DrinkStates.drink_type)
async def drink_type(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return

    drink = message.text
    await state.update_data(drink_type=drink)

    # Если выбрано "Другое" – запрашиваем ввод
    if drink == "🔄 Другое":
        await message.answer("Напиши, что именно и сколько (например: 'энергетик 0.5л')", reply_markup=get_main_menu())
        await state.set_state(DrinkStates.amount)
    else:
        await message.answer("Сколько?", reply_markup=get_drink_amount_buttons())
        await state.set_state(DrinkStates.amount)

@dp.message(DrinkStates.amount)
async def drink_amount(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return

    data = await state.get_data()
    drink_type = data["drink_type"]
    amount = message.text
    db.add_drink(message.from_user.id, drink_type, amount)
    await message.answer(f"✅ Добавлено: {drink_type} — {amount}", reply_markup=get_main_menu())
    await state.clear()

# ========== МЫСЛИ ==========
# (остаются без изменений)

# ========== СТАТИСТИКА ==========
@dp.message(F.text == "📊 Статистика")
async def stats(message: Message):
    text = db.get_stats(message.from_user.id)
    await message.answer(text, reply_markup=get_main_menu())

# ========== ЭКСПОРТ ==========
@dp.message(F.text == "📤 Экспорт")
async def export(message: Message):
    file_path = db.export_all(message.from_user.id)
    await message.answer_document(
        FSInputFile(file_path, filename="my_data.json"),
        caption="📁 Вот все твои данные"
    )

# ========== НАСТРОЙКИ ==========
@dp.message(F.text == "⚙️ Настройки")
async def settings(message: Message):
    await message.answer(
        "⚙️ Настройки\n\n"
        "Выбери действие:",
        reply_markup=get_settings_menu()
    )

@dp.message(F.text == "🔄 Сброс данных")
async def reset_request(message: Message):
    await message.answer(
        "⚠️ ВНИМАНИЕ! Это действие удалит ВСЕ твои данные (сон, чек-ины, еду, мысли и т.д.).\n\n"
        "Ты уверен?",
        reply_markup=get_reset_confirm_keyboard()
    )

@dp.message(F.text == "❌ Назад")
async def back_to_main(message: Message):
    await message.answer("Главное меню", reply_markup=get_main_menu())

# Обработчики подтверждения сброса
@dp.callback_query(lambda c: c.data == "reset_confirm")
async def reset_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    success = db.reset_user_data(user_id)
    if success:
        await callback.message.edit_text("✅ Все твои данные удалены.", reply_markup=None)
    else:
        await callback.message.edit_text("❌ Не удалось удалить данные (возможно, их и не было).", reply_markup=None)
    await callback.answer()
    # Возвращаем в главное меню (отправим новое сообщение)
    await callback.message.answer("Главное меню", reply_markup=get_main_menu())

@dp.callback_query(lambda c: c.data == "reset_cancel")
async def reset_cancel(callback: CallbackQuery):
    await callback.message.edit_text("❌ Сброс отменён.", reply_markup=None)
    await callback.answer()
    await callback.message.answer("Главное меню", reply_markup=get_main_menu())

# ========== ВЕБ-СЕРВЕР ДЛЯ RENDER ==========
# Импортируем веб-модуль (web.py) и запускаем в фоне
import web

async def main():
    # Запускаем веб-сервер в фоне
    asyncio.create_task(web.start_web())
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

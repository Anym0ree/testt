import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

from config import BOT_TOKEN
from database import db
from keyboards import *

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

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
    emotions = State()
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
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
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

@dp.message_handler(commands=['menu'])
async def cmd_menu(message: types.Message):
    await message.answer("📱 Главное меню", reply_markup=get_main_menu())

@dp.message_handler(commands=['skip'])
async def cmd_skip(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("⏭ Текущий опрос пропущен", reply_markup=get_main_menu())

@dp.message_handler(commands=['thoughts'])
async def cmd_thoughts(message: types.Message):
    thoughts = db.get_thoughts(message.from_user.id)
    if not thoughts:
        await message.answer("💭 У тебя пока нет записанных мыслей.", reply_markup=get_main_menu())
        return

    text = "💭 *Твои мысли (последние 10):*\n\n"
    for i, thought in enumerate(reversed(thoughts)):
        idx = len(thoughts) - 1 - i  # индекс в исходном списке
        text += f"{i+1}. *{thought['thought_type']}*: {thought['thought_text']}\n"
        text += f"   📅 {thought['date']} {thought['time']} | Действие: {thought['action']}\n\n"

    await message.answer(text, parse_mode="Markdown", reply_markup=get_thoughts_list_keyboard(thoughts))

# ========== СОН ==========
# ... (код сна остаётся как в предыдущей версии, без изменений)
# Я не буду повторять его полностью, чтобы не дублировать. Используй ту же логику, что была.
# Но для краткости в ответе я приведу только изменённые части.

# ========== НАПИТКИ (изменённые) ==========
@dp.message_handler(text="🥤 Напитки")
async def drink_start(message: types.Message):
    await DrinkStates.drink_type.set()
    await message.answer("Что выпил?", reply_markup=get_drink_type_buttons())

@dp.message_handler(state=DrinkStates.drink_type)
async def drink_type(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(drink_type=message.text)
    await DrinkStates.amount.set()
    await message.answer("Сколько?", reply_markup=get_drink_amount_buttons())

@dp.message_handler(state=DrinkStates.amount)
async def drink_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    if message.text == "Другое":
        await message.answer("Введи количество (например: 0.5 л, 2 стакана):", reply_markup=types.ReplyKeyboardRemove())
        return
    data = await state.get_data()
    drink_type = data["drink_type"]
    amount = message.text
    db.add_drink(message.from_user.id, drink_type, amount)
    await message.answer(f"✅ Добавлено: {drink_type} — {amount}", reply_markup=get_main_menu())
    await state.finish()

@dp.message_handler(state=DrinkStates.amount)
async def drink_amount_custom(message: types.Message, state: FSMContext):
    data = await state.get_data()
    drink_type = data["drink_type"]
    amount = message.text
    db.add_drink(message.from_user.id, drink_type, amount)
    await message.answer(f"✅ Добавлено: {drink_type} — {amount}", reply_markup=get_main_menu())
    await state.finish()

# ========== МЫСЛИ (с возможностью просмотра и удаления) ==========
# ... (оставляем старый код добавления мысли)
# Добавляем обработчики для инлайн-кнопок

@dp.callback_query_handler(lambda c: c.data.startswith("del_thought_"))
async def delete_thought_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    idx_str = callback_query.data.split("_")[-1]
    try:
        idx = int(idx_str)
    except ValueError:
        await callback_query.answer("Ошибка", show_alert=True)
        return

    thoughts = db.get_thoughts(user_id)
    if idx < 0 or idx >= len(thoughts):
        await callback_query.answer("Мысль не найдена", show_alert=True)
        return

    success = db.delete_thought_by_index(user_id, idx)
    if success:
        await callback_query.answer("Мысль удалена", show_alert=False)
        # Обновляем список мыслей
        new_thoughts = db.get_thoughts(user_id)
        if new_thoughts:
            text = "💭 *Твои мысли (последние 10):*\n\n"
            for i, thought in enumerate(reversed(new_thoughts)):
                new_idx = len(new_thoughts) - 1 - i
                text += f"{i+1}. *{thought['thought_type']}*: {thought['thought_text']}\n"
                text += f"   📅 {thought['date']} {thought['time']} | Действие: {thought['action']}\n\n"
            await callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=get_thoughts_list_keyboard(new_thoughts))
        else:
            await callback_query.message.edit_text("💭 У тебя больше нет сохранённых мыслей.", reply_markup=None)
    else:
        await callback_query.answer("Не удалось удалить", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "close_thoughts")
async def close_thoughts(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    await callback_query.answer()

# ========== НАСТРОЙКИ (исправленный сброс) ==========
@dp.message_handler(text="⚙️ Настройки")
async def settings(message: types.Message):
    await message.answer(
        "⚙️ Настройки\n\n"
        "Выбери действие:",
        reply_markup=get_settings_menu()
    )

@dp.message_handler(text="🔄 Сброс данных")
async def reset_request(message: types.Message):
    await message.answer(
        "⚠️ ВНИМАНИЕ! Это действие удалит ВСЕ твои данные (сон, чек-ины, еду, мысли и т.д.).\n\n"
        "Ты уверен?",
        reply_markup=get_reset_confirm_keyboard()
    )

@dp.message_handler(text="❌ Назад")
async def back_to_main(message: types.Message):
    await message.answer("Главное меню", reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data == "reset_confirm")
async def reset_confirm(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    success = db.reset_user_data(user_id)
    if success:
        await callback_query.message.edit_text("✅ Все твои данные удалены.")
    else:
        await callback_query.message.edit_text("❌ Не удалось удалить данные (возможно, их и не было).")
    await callback_query.answer()
    await callback_query.message.answer("Главное меню", reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data == "reset_cancel")
async def reset_cancel(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text("❌ Сброс отменён.")
    await callback_query.answer()
    await callback_query.message.answer("Главное меню", reply_markup=get_main_menu())

# ========== ЗАПУСК ==========
from web import start_web

async def on_startup(dp):
    start_web()
    print("🤖 Бот запущен!")

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)

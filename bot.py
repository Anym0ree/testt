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

# ========== СОН ==========
@dp.message_handler(text="🛌 Сон")
async def sleep_start(message: types.Message):
    await SleepStates.bed_time.set()
    await message.answer("🛌 Во сколько лег?", reply_markup=get_time_buttons())

@dp.message_handler(state=SleepStates.bed_time)
async def sleep_bed_time(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    if message.text == "Другое":
        await message.answer("Введи время в формате ЧЧ:ММ (например 23:45):", reply_markup=types.ReplyKeyboardRemove())
        return
    await state.update_data(bed_time=message.text)
    await SleepStates.next()
    await message.answer("Во сколько встал?", reply_markup=get_time_buttons())

@dp.message_handler(state=SleepStates.bed_time)
async def sleep_bed_time_custom(message: types.Message, state: FSMContext):
    await state.update_data(bed_time=message.text)
    await SleepStates.next()
    await message.answer("Во сколько встал?", reply_markup=get_time_buttons())

@dp.message_handler(state=SleepStates.wake_time)
async def sleep_wake_time(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    if message.text == "Другое":
        await message.answer("Введи время в формате ЧЧ:ММ (например 09:15):", reply_markup=types.ReplyKeyboardRemove())
        return
    await state.update_data(wake_time=message.text)
    await SleepStates.next()
    await message.answer("Качество сна? (1-10)", reply_markup=get_energy_stress_buttons())

@dp.message_handler(state=SleepStates.wake_time)
async def sleep_wake_time_custom(message: types.Message, state: FSMContext):
    await state.update_data(wake_time=message.text)
    await SleepStates.next()
    await message.answer("Качество сна? (1-10)", reply_markup=get_energy_stress_buttons())

@dp.message_handler(state=SleepStates.quality)
async def sleep_quality(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(quality=message.text)
    await SleepStates.next()
    await message.answer("Просыпался ночью?", reply_markup=get_yes_no_buttons())

@dp.message_handler(state=SleepStates.woke_night)
async def sleep_woke_night(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(woke_night=message.text)
    await SleepStates.next()
    await message.answer("Заметка? (можно пропустить)", reply_markup=get_skip_markup_text())

@dp.message_handler(state=SleepStates.note)
async def sleep_note(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    data = await state.get_data()
    note = message.text if message.text != "Пропустить" else ""
    db.add_sleep(
        message.from_user.id,
        data["bed_time"],
        data["wake_time"],
        data["quality"],
        data["woke_night"],
        note
    )
    await message.answer("✅ Сон сохранен!", reply_markup=get_main_menu())
    await state.finish()

# ========== ЧЕК-ИН ==========
@dp.message_handler(text="⚡️ Чек-ин")
async def checkin_start(message: types.Message):
    await CheckinStates.energy.set()
    await message.answer("⚡️ Энергия? (1-10)", reply_markup=get_energy_stress_buttons())

@dp.message_handler(state=CheckinStates.energy)
async def checkin_energy(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(energy=message.text)
    await CheckinStates.next()
    await message.answer("Стресс? (1-10)", reply_markup=get_energy_stress_buttons())

@dp.message_handler(state=CheckinStates.stress)
async def checkin_stress(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(stress=message.text)
    await CheckinStates.next()
    await state.update_data(emotions_list=[])
    await message.answer(
        "Выбери эмоции (можно несколько). Когда закончишь, нажми '✅ Готово':",
        reply_markup=get_emotion_buttons()
    )

@dp.message_handler(state=CheckinStates.emotions)
async def checkin_emotions(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    if message.text == "✅ Готово":
        data = await state.get_data()
        emotions = data.get("emotions_list", [])
        if not emotions:
            await message.answer("Выбери хотя бы одну эмоцию или нажми 'Отмена'", reply_markup=get_emotion_buttons())
            return
        await CheckinStates.next()
        await message.answer("Заметка? (можно пропустить)", reply_markup=get_skip_markup_text())
        return
    if message.text == "✍️ Своя":
        await message.answer("Напиши свою эмоцию:", reply_markup=types.ReplyKeyboardRemove())
        return
    
    data = await state.get_data()
    emotions_list = data.get("emotions_list", [])
    if message.text not in emotions_list:
        emotions_list.append(message.text)
        await state.update_data(emotions_list=emotions_list)
        await message.answer(f"✅ Добавлено: {message.text}\nВыбрано: {', '.join(emotions_list)}", reply_markup=get_emotion_buttons())
    else:
        await message.answer(f"⚠️ Эмоция '{message.text}' уже добавлена", reply_markup=get_emotion_buttons())

@dp.message_handler(state=CheckinStates.emotions)
async def checkin_emotions_custom(message: types.Message, state: FSMContext):
    data = await state.get_data()
    emotions_list = data.get("emotions_list", [])
    emotions_list.append(message.text)
    await state.update_data(emotions_list=emotions_list)
    await message.answer(f"✅ Добавлено: {message.text}\nВыбрано: {', '.join(emotions_list)}", reply_markup=get_emotion_buttons())

@dp.message_handler(state=CheckinStates.note)
async def checkin_note(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    data = await state.get_data()
    note = message.text if message.text != "Пропустить" else ""
    hour = datetime.now().hour
    if hour < 12:
        time_slot = "утро"
    elif hour < 18:
        time_slot = "день"
    else:
        time_slot = "вечер"
    db.add_checkin(
        message.from_user.id,
        time_slot,
        data["energy"],
        data["stress"],
        data.get("emotions_list", []),
        note
    )
    await message.answer("✅ Чек-ин сохранен!", reply_markup=get_main_menu())
    await state.finish()

# ========== ИТОГ ДНЯ ==========
@dp.message_handler(text="📝 Итог дня")
async def summary_start(message: types.Message):
    await DaySummaryStates.score.set()
    await message.answer("📝 Оценка дня? (1-10)", reply_markup=get_energy_stress_buttons())

@dp.message_handler(state=DaySummaryStates.score)
async def summary_score(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(score=message.text)
    await DaySummaryStates.next()
    await message.answer("Что было лучшим?", reply_markup=get_skip_markup_text())

@dp.message_handler(state=DaySummaryStates.best)
async def summary_best(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    best = message.text if message.text != "Пропустить" else ""
    await state.update_data(best=best)
    await DaySummaryStates.next()
    await message.answer("Что было худшим?", reply_markup=get_skip_markup_text())

@dp.message_handler(state=DaySummaryStates.worst)
async def summary_worst(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    worst = message.text if message.text != "Пропустить" else ""
    await state.update_data(worst=worst)
    await DaySummaryStates.next()
    await message.answer("За что благодарен?", reply_markup=get_skip_markup_text())

@dp.message_handler(state=DaySummaryStates.gratitude)
async def summary_gratitude(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    gratitude = message.text if message.text != "Пропустить" else ""
    await state.update_data(gratitude=gratitude)
    await DaySummaryStates.next()
    await message.answer("Заметка? (можно пропустить)", reply_markup=get_skip_markup_text())

@dp.message_handler(state=DaySummaryStates.note)
async def summary_note(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    data = await state.get_data()
    note = message.text if message.text != "Пропустить" else ""
    db.add_day_summary(message.from_user.id, data["score"], data["best"], data["worst"], data["gratitude"], note)
    await message.answer("✅ Итог дня сохранен!", reply_markup=get_main_menu())
    await state.finish()

# ========== ЕДА ==========
@dp.message_handler(text="🍽 Еда")
async def food_start(message: types.Message):
    await FoodStates.meal_type.set()
    await message.answer("Что это за прием?", reply_markup=get_meal_type_buttons())

@dp.message_handler(state=FoodStates.meal_type)
async def food_meal_type(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(meal_type=message.text)
    await FoodStates.next()
    await message.answer("Что съел?", reply_markup=get_main_menu())

@dp.message_handler(state=FoodStates.food_text)
async def food_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    db.add_food(message.from_user.id, data["meal_type"], message.text)
    await message.answer(f"✅ Добавлено: {data['meal_type']} — {message.text}", reply_markup=get_main_menu())
    await state.finish()

# ========== НАПИТКИ ==========
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
    drink = message.text
    await state.update_data(drink_type=drink)

    if drink == "🔄 Другое":
        await message.answer("Напиши, что именно и сколько (например: 'энергетик 0.5л')", reply_markup=types.ReplyKeyboardRemove())
        await DrinkStates.amount.set()
    else:
        await DrinkStates.amount.set()
        await message.answer("Сколько?", reply_markup=get_drink_amount_buttons())

@dp.message_handler(state=DrinkStates.amount)
async def drink_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    data = await state.get_data()
    drink_type = data["drink_type"]
    amount = message.text
    db.add_drink(message.from_user.id, drink_type, amount)
    await message.answer(f"✅ Добавлено: {drink_type} — {amount}", reply_markup=get_main_menu())
    await state.finish()

# ========== МЫСЛИ ==========
@dp.message_handler(text="💭 Мысли")
async def thought_start(message: types.Message):
    await ThoughtStates.thought_text.set()
    await message.answer("Какая мысль?", reply_markup=get_main_menu())

@dp.message_handler(state=ThoughtStates.thought_text)
async def thought_text(message: types.Message, state: FSMContext):
    await state.update_data(thought_text=message.text)
    await ThoughtStates.next()
    await message.answer("Тип мысли?", reply_markup=get_thought_type_buttons())

@dp.message_handler(state=ThoughtStates.thought_type)
async def thought_type(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(thought_type=message.text)
    await ThoughtStates.next()
    await message.answer("Что сделал с мыслью?", reply_markup=get_thought_action_buttons())

@dp.message_handler(state=ThoughtStates.action)
async def thought_action(message: types.Message, state: FSMContext):
    data = await state.get_data()
    db.add_thought(message.from_user.id, data["thought_text"], data["thought_type"], message.text)
    await message.answer("✅ Мысль сохранена", reply_markup=get_main_menu())
    await state.finish()

# ========== СТАТИСТИКА ==========
@dp.message_handler(text="📊 Статистика")
async def stats(message: types.Message):
    text = db.get_stats(message.from_user.id)
    await message.answer(text, reply_markup=get_main_menu())

# ========== ЭКСПОРТ ==========
@dp.message_handler(text="📤 Экспорт")
async def export(message: types.Message):
    file_path = db.export_all(message.from_user.id)
    with open(file_path, 'rb') as f:
        await message.answer_document(f, caption="📁 Вот все твои данные")
    await message.answer("Главное меню", reply_markup=get_main_menu())

# ========== НАСТРОЙКИ ==========
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

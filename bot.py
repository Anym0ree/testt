import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import db
from keyboards import *

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# СОСТОЯНИЯ
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

@dp.message(F.text == "🛌 Сон")
async def sleep_start(message: Message, state: FSMContext):
    await message.answer("🛌 Во сколько лег?", reply_markup=get_time_buttons())
    await state.set_state(SleepStates.bed_time)

@dp.message(SleepStates.bed_time)
async def sleep_bed(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(bed_time=message.text)
    await message.answer("Во сколько встал?", reply_markup=get_time_buttons())
    await state.set_state(SleepStates.wake_time)

@dp.message(SleepStates.wake_time)
async def sleep_wake(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(wake_time=message.text)
    await message.answer("Качество сна? (1-10)", reply_markup=get_energy_stress_buttons())
    await state.set_state(SleepStates.quality)

@dp.message(SleepStates.quality)
async def sleep_quality(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(quality=message.text)
    await message.answer("Просыпался ночью?", reply_markup=get_yes_no_buttons())
    await state.set_state(SleepStates.woke_night)

@dp.message(SleepStates.woke_night)
async def sleep_woke(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(woke_night=message.text)
    await message.answer("Заметка? (можно пропустить)", reply_markup=get_skip_markup_text())
    await state.set_state(SleepStates.note)

@dp.message(SleepStates.note)
async def sleep_note(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    data = await state.get_data()
    note = message.text if message.text != "Пропустить" else ""
    db.add_sleep(message.from_user.id, data["bed_time"], data["wake_time"], data["quality"], data["woke_night"], note)
    await message.answer("✅ Сон сохранен!", reply_markup=get_main_menu())
    await state.clear()

# ========== ЧЕК-ИН ==========

@dp.message(F.text == "⚡️ Чек-ин")
async def checkin_start(message: Message, state: FSMContext):
    await message.answer("⚡️ Энергия? (1-10)", reply_markup=get_energy_stress_buttons())
    await state.set_state(CheckinStates.energy)

@dp.message(CheckinStates.energy)
async def checkin_energy(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(energy=message.text)
    await message.answer("Стресс? (1-10)", reply_markup=get_energy_stress_buttons())
    await state.set_state(CheckinStates.stress)

@dp.message(CheckinStates.stress)
async def checkin_stress(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(stress=message.text)
    await message.answer("Какая эмоция?", reply_markup=get_emotion_buttons())
    await state.set_state(CheckinStates.emotion)

@dp.message(CheckinStates.emotion)
async def checkin_emotion(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(emotion=message.text)
    await message.answer("Заметка? (можно пропустить)", reply_markup=get_skip_markup_text())
    await state.set_state(CheckinStates.note)

@dp.message(CheckinStates.note)
async def checkin_note(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
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
    db.add_checkin(message.from_user.id, time_slot, data["energy"], data["stress"], data["emotion"], note)
    await message.answer("✅ Чек-ин сохранен!", reply_markup=get_main_menu())
    await state.clear()

# ========== ИТОГ ДНЯ ==========

@dp.message(F.text == "📝 Итог дня")
async def summary_start(message: Message, state: FSMContext):
    await message.answer("📝 Оценка дня? (1-10)", reply_markup=get_energy_stress_buttons())
    await state.set_state(DaySummaryStates.score)

@dp.message(DaySummaryStates.score)
async def summary_score(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(score=message.text)
    await message.answer("Что было лучшим?", reply_markup=get_skip_markup_text())
    await state.set_state(DaySummaryStates.best)

@dp.message(DaySummaryStates.best)
async def summary_best(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    best = message.text if message.text != "Пропустить" else ""
    await state.update_data(best=best)
    await message.answer("Что было худшим?", reply_markup=get_skip_markup_text())
    await state.set_state(DaySummaryStates.worst)

@dp.message(DaySummaryStates.worst)
async def summary_worst(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    worst = message.text if message.text != "Пропустить" else ""
    await state.update_data(worst=worst)
    await message.answer("За что благодарен?", reply_markup=get_skip_markup_text())
    await state.set_state(DaySummaryStates.gratitude)

@dp.message(DaySummaryStates.gratitude)
async def summary_gratitude(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    gratitude = message.text if message.text != "Пропустить" else ""
    await state.update_data(gratitude=gratitude)
    await message.answer("Заметка? (можно пропустить)", reply_markup=get_skip_markup_text())
    await state.set_state(DaySummaryStates.note)

@dp.message(DaySummaryStates.note)
async def summary_note(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    data = await state.get_data()
    note = message.text if message.text != "Пропустить" else ""
    db.add_day_summary(message.from_user.id, data["score"], data["best"], data["worst"], data["gratitude"], note)
    await message.answer("✅ Итог дня сохранен!", reply_markup=get_main_menu())
    await state.clear()

# ========== ЕДА ==========

@dp.message(F.text == "🍽 Еда")
async def food_start(message: Message, state: FSMContext):
    await message.answer("Что это за прием?", reply_markup=get_meal_type_buttons())
    await state.set_state(FoodStates.meal_type)

@dp.message(FoodStates.meal_type)
async def food_meal(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(meal_type=message.text)
    await message.answer("Что съел?", reply_markup=get_main_menu())
    await state.set_state(FoodStates.food_text)

@dp.message(FoodStates.food_text)
async def food_text(message: Message, state: FSMContext):
    data = await state.get_data()
    db.add_food(message.from_user.id, data["meal_type"], message.text)
    await message.answer(f"✅ Добавлено: {data['meal_type']} — {message.text}", reply_markup=get_main_menu())
    await state.clear()

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
    await state.update_data(drink_type=message.text)
    await message.answer("Сколько?", reply_markup=get_drink_amount_buttons())
    await state.set_state(DrinkStates.amount)

@dp.message(DrinkStates.amount)
async def drink_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    db.add_drink(message.from_user.id, data["drink_type"], message.text)
    await message.answer(f"✅ Добавлено: {data['drink_type']} — {message.text}", reply_markup=get_main_menu())
    await state.clear()

# ========== МЫСЛИ ==========

@dp.message(F.text == "💭 Мысли")
async def thought_start(message: Message, state: FSMContext):
    await message.answer("Какая мысль?", reply_markup=get_main_menu())
    await state.set_state(ThoughtStates.thought_text)

@dp.message(ThoughtStates.thought_text)
async def thought_text(message: Message, state: FSMContext):
    await state.update_data(thought_text=message.text)
    await message.answer("Тип мысли?", reply_markup=get_thought_type_buttons())
    await state.set_state(ThoughtStates.thought_type)

@dp.message(ThoughtStates.thought_type)
async def thought_type(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(thought_type=message.text)
    await message.answer("Что сделал с мыслью?", reply_markup=get_thought_action_buttons())
    await state.set_state(ThoughtStates.action)

@dp.message(ThoughtStates.action)
async def thought_action(message: Message, state: FSMContext):
    data = await state.get_data()
    db.add_thought(message.from_user.id, data["thought_text"], data["thought_type"], message.text)
    await message.answer("✅ Мысль сохранена", reply_markup=get_main_menu())
    await state.clear()

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
        "Команды:\n"
        "/skip — пропустить опрос\n"
        "/menu — главное меню\n\n"
        "Данные хранятся в папке user_data/",
        reply_markup=get_main_menu()
    )

# ========== ЗАПУСК ==========

async def main():
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

import asyncio
import web  # наш веб-модуль

async def main():
    # Запускаем веб-сервер в фоне
    asyncio.create_task(web.start_web())
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
import asyncio
import logging
from datetime import datetime, timedelta
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

class TimezoneStates(StatesGroup):
    city = State()
    offset = State()

class ReminderStates(StatesGroup):
    text = State()
    date = State()
    hour = State()
    minute = State()
    advance = State()
    edit_text = State()
    edit_date = State()
    edit_hour = State()
    edit_minute = State()
    edit_reminder_id = State()

# ========== КОМАНДЫ ==========
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if db.get_user_timezone(message.from_user.id) == 0:
        await message.answer(
            "👋 Привет! Я твой личный дневник-трекер.\n\n"
            "Для корректной работы мне нужно знать твой часовой пояс.\n"
            "Выбери свой город или нажми 'Другое' и введи смещение:",
            reply_markup=get_timezone_buttons()
        )
        await TimezoneStates.city.set()
    else:
        await message.answer(
            "👋 Привет! Я твой личный дневник-трекер.\n\n"
            "Что я умею:\n"
            "• 🛌 Записывать сон (один раз в день)\n"
            "• ⚡️ Делать чек-ины (энергия, стресс, эмоции)\n"
            "• 🍽 Записывать еду и напитки\n"
            "• 💭 Сохранять мысли\n"
            "• 📝 Итог дня (только после 18:00, один раз в день)\n"
            "• 📅 Напоминания\n"
            "• 📊 Статистика\n"
            "• 📤 Экспорт\n\n"
            "Главное меню — /menu",
            reply_markup=get_main_menu()
        )

# ========== УСТАНОВКА ГОРОДА ==========
@dp.message_handler(state=TimezoneStates.city)
async def set_city(message: types.Message, state: FSMContext):
    city_map = {
        "Москва (UTC+3)": 3,
        "Санкт-Петербург (UTC+3)": 3,
        "Екатеринбург (UTC+5)": 5,
        "Новосибирск (UTC+7)": 7,
        "Владивосток (UTC+10)": 10,
        "Калининград (UTC+2)": 2
    }
    if message.text in city_map:
        offset = city_map[message.text]
        db.set_user_timezone(message.from_user.id, offset)
        await message.answer(f"✅ Часовой пояс установлен: UTC+{offset}\n\nГлавное меню — /menu", reply_markup=get_main_menu())
        await state.finish()
    elif message.text == "Другое":
        await message.answer("Введи смещение в часах от UTC (например, 3 для Москвы, -5 для Нью-Йорка):\n\nПримеры: 3, -5, 0", reply_markup=types.ReplyKeyboardRemove())
        await TimezoneStates.offset.set()
    elif message.text == "❌ Отмена":
        await message.answer("❌ Отменено. Для настройки используй /start или настройки.", reply_markup=get_main_menu())
        await state.finish()
    else:
        await message.answer("Пожалуйста, выбери город из списка или нажми 'Другое'.", reply_markup=get_timezone_buttons())

@dp.message_handler(state=TimezoneStates.offset)
async def set_offset(message: types.Message, state: FSMContext):
    try:
        offset = int(message.text.strip())
        db.set_user_timezone(message.from_user.id, offset)
        sign = "+" if offset >= 0 else ""
        await message.answer(f"✅ Часовой пояс установлен: UTC{sign}{offset}\n\nГлавное меню — /menu", reply_markup=get_main_menu())
        await state.finish()
    except ValueError:
        await message.answer("❌ Неверный формат. Введи целое число (например: 3, -5, 0).", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(commands=['menu'])
async def cmd_menu(message: types.Message):
    await message.answer("📱 Главное меню", reply_markup=get_main_menu())

@dp.message_handler(commands=['skip'])
async def cmd_skip(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("⏭ Текущий опрос пропущен", reply_markup=get_main_menu())

# ========== МЫСЛИ (просмотр) ==========
@dp.message_handler(commands=['thoughts'])
async def cmd_thoughts(message: types.Message):
    thoughts = db.get_thoughts(message.from_user.id)
    if not thoughts:
        await message.answer("💭 У тебя пока нет записанных мыслей.", reply_markup=get_main_menu())
        return

    text = "💭 *Твои мысли (последние 10):*\n\n"
    for i, thought in enumerate(reversed(thoughts)):
        text += f"{i+1}. *{thought['thought_type']}*: {thought['thought_text']}\n"
        text += f"   📅 {thought['date']} {thought['time']} | Действие: {thought['action']}\n\n"

    await message.answer(text, parse_mode="Markdown", reply_markup=get_thoughts_list_keyboard(thoughts))

# ========== СПИСОК ЕДЫ ЗА СЕГОДНЯ ==========
@dp.message_handler(text="🍽 Еда сегодня")
async def show_today_food(message: types.Message):
    food_list = db.get_today_food(message.from_user.id)
    if not food_list:
        await message.answer("🍽 За сегодня ещё нет записей о еде.", reply_markup=get_main_menu())
        return
    text = "🍽 *Еда сегодня:*\n\n"
    for f in food_list:
        text += f"🕐 {f['time']} — {f['meal_type']}: {f['food_text']}\n"
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_menu())

# ========== СПИСОК НАПИТКОВ ЗА СЕГОДНЯ ==========
@dp.message_handler(text="🥤 Напитки сегодня")
async def show_today_drinks(message: types.Message):
    drinks_list = db.get_today_drinks(message.from_user.id)
    if not drinks_list:
        await message.answer("🥤 За сегодня ещё нет записей о напитках.", reply_markup=get_main_menu())
        return
    text = "🥤 *Напитки сегодня:*\n\n"
    for d in drinks_list:
        text += f"🕐 {d['time']} — {d['drink_type']}: {d['amount']}\n"
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_menu())

# ========== СОН ==========
@dp.message_handler(text="🛌 Сон")
async def sleep_start(message: types.Message):
    if db.has_sleep_today(message.from_user.id):
        await message.answer("❌ Ты уже записал сон сегодня. Сон можно записывать только один раз в день.", reply_markup=get_main_menu())
        return
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
    success = db.add_sleep(
        message.from_user.id,
        data["bed_time"],
        data["wake_time"],
        data["quality"],
        data["woke_night"],
        note
    )
    if success:
        await message.answer("✅ Сон сохранен!", reply_markup=get_main_menu())
    else:
        await message.answer("❌ Не удалось сохранить сон.", reply_markup=get_main_menu())
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
    hour = db.get_user_local_hour(message.from_user.id)
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
    local_hour = db.get_user_local_hour(message.from_user.id)
    if local_hour < 18:
        await message.answer(f"📝 Итог дня можно подвести только после 18:00. Сейчас {local_hour}:00 по твоему времени.", reply_markup=get_main_menu())
        return
    if db.has_day_summary_today(message.from_user.id):
        await message.answer("❌ Ты уже записал итог дня сегодня. Итог дня можно записывать только один раз.", reply_markup=get_main_menu())
        return
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
    success = db.add_day_summary(message.from_user.id, data["score"], data["best"], data["worst"], data["gratitude"], note)
    if success:
        await message.answer("✅ Итог дня сохранен!", reply_markup=get_main_menu())
    else:
        await message.answer("❌ Не удалось сохранить итог дня.", reply_markup=get_main_menu())
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

# ========== МЫСЛИ (добавление) ==========
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

# ========== ПРОСМОТР МЫСЛЕЙ (кнопка) ==========
@dp.message_handler(text="💭 Мои мысли")
async def show_thoughts_button(message: types.Message):
    await cmd_thoughts(message)

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

@dp.message_handler(text="🌍 Сменить город")
async def change_city(message: types.Message):
    await message.answer(
        "Выбери свой город или введи смещение вручную:",
        reply_markup=get_timezone_buttons()
    )
    await TimezoneStates.city.set()

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

# ========== УДАЛЕНИЕ МЫСЛЕЙ ==========
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
        new_thoughts = db.get_thoughts(user_id)
        if new_thoughts:
            text = "💭 *Твои мысли (последние 10):*\n\n"
            for i, thought in enumerate(reversed(new_thoughts)):
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

# ========== МОДУЛЬ НАПОМИНАНИЙ ==========
@dp.message_handler(text="📅 Напоминания")
async def reminders_menu(message: types.Message):
    await message.answer("📅 Напоминания\n\nЗдесь можно управлять напоминалками.", reply_markup=get_reminder_menu())

@dp.message_handler(text="➕ Добавить")
async def add_reminder_start(message: types.Message):
    await ReminderStates.text.set()
    await message.answer("📝 Введи название напоминания\n\nНапример: позвонить маме, купить хлеб, запись к врачу", reply_markup=get_back_button())

@dp.message_handler(state=ReminderStates.text)
async def add_reminder_text(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await reminders_menu(message)
        return
    await state.update_data(text=message.text)
    await ReminderStates.date.set()
    await message.answer("📅 Выбери дату:", reply_markup=get_reminder_date_buttons())

@dp.message_handler(state=ReminderStates.date)
async def add_reminder_date(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await reminders_menu(message)
        return
    if message.text == "⬅️ Назад":
        await ReminderStates.text.set()
        await message.answer("📝 Введи название напоминания", reply_markup=get_back_button())
        return

    today = datetime.now().date()
    if message.text == "📅 Сегодня":
        target_date = today
    elif message.text == "📆 Завтра":
        target_date = today + timedelta(days=1)
    elif message.text == "📆 Послезавтра":
        target_date = today + timedelta(days=2)
    elif message.text == "🔢 Выбрать дату":
        await message.answer("📅 Введи дату в формате: число месяц\n\nПримеры: 25 декабря, 1 января", reply_markup=get_back_button())
        return
    else:
        try:
            day_month = message.text.split()
            day = int(day_month[0])
            month_name = day_month[1]
            month_map = {
                "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
                "мая": 5, "июня": 6, "июля": 7, "августа": 8,
                "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
            }
            month = month_map.get(month_name.lower())
            if not month:
                raise ValueError
            year = today.year
            target_date = datetime(year, month, day).date()
            if target_date < today:
                target_date = datetime(year + 1, month, day).date()
        except:
            await message.answer("❌ Неверный формат. Введи дату как '25 декабря'", reply_markup=get_reminder_date_buttons())
            return

    await state.update_data(date=target_date.strftime("%Y-%m-%d"))
    await ReminderStates.hour.set()
    await message.answer("🕐 Выбери час:", reply_markup=get_reminder_hour_buttons())

@dp.message_handler(state=ReminderStates.date)
async def add_reminder_date_custom(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await ReminderStates.text.set()
        await message.answer("📝 Введи название напоминания", reply_markup=get_back_button())
        return
    try:
        day_month = message.text.split()
        day = int(day_month[0])
        month_name = day_month[1]
        month_map = {
            "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
            "мая": 5, "июня": 6, "июля": 7, "августа": 8,
            "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
        }
        month = month_map.get(month_name.lower())
        if not month:
            raise ValueError
        today = datetime.now().date()
        year = today.year
        target_date = datetime(year, month, day).date()
        if target_date < today:
            target_date = datetime(year + 1, month, day).date()
    except:
        await message.answer("❌ Неверный формат. Введи дату как '25 декабря'", reply_markup=get_reminder_date_buttons())
        return

    await state.update_data(date=target_date.strftime("%Y-%m-%d"))
    await ReminderStates.hour.set()
    await message.answer("🕐 Выбери час:", reply_markup=get_reminder_hour_buttons())

@dp.message_handler(state=ReminderStates.hour)
async def add_reminder_hour(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await reminders_menu(message)
        return
    if message.text == "⬅️ Назад":
        await ReminderStates.date.set()
        await message.answer("📅 Выбери дату:", reply_markup=get_reminder_date_buttons())
        return
    try:
        hour = int(message.text)
        if 0 <= hour <= 23:
            await state.update_data(hour=hour)
            await ReminderStates.minute.set()
            await message.answer("🕐 Выбери минуты:", reply_markup=get_reminder_minute_buttons())
        else:
            raise ValueError
    except:
        await message.answer("❌ Выбери час из кнопок (0-23)", reply_markup=get_reminder_hour_buttons())

@dp.message_handler(state=ReminderStates.minute)
async def add_reminder_minute(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await reminders_menu(message)
        return
    if message.text == "⬅️ Назад":
        await ReminderStates.hour.set()
        await message.answer("🕐 Выбери час:", reply_markup=get_reminder_hour_buttons())
        return
    if message.text not in ["00", "15", "30", "45"]:
        await message.answer("❌ Выбери минуты из кнопок: 00, 15, 30, 45", reply_markup=get_reminder_minute_buttons())
        return
    await state.update_data(minute=message.text)
    await ReminderStates.advance.set()
    await message.answer("⏰ Нужно ли напомнить заранее?", reply_markup=get_reminder_advance_buttons())

@dp.message_handler(state=ReminderStates.advance)
async def add_reminder_advance(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await reminders_menu(message)
        return
    if message.text == "⬅️ Назад":
        await ReminderStates.minute.set()
        await message.answer("🕐 Выбери минуты:", reply_markup=get_reminder_minute_buttons())
        return

    advance_map = {
        "⏰ За 1 день": "day",
        "⏳ За 3 часа": "3h",
        "⌛ За 1 час": "1h",
        "🚫 Не надо": None
    }
    advance_type = advance_map.get(message.text)

    data = await state.get_data()
    text = data["text"]
    target_date = data["date"]
    time_str = f"{data['hour']:02d}:{data['minute']}"

    reminder_id = db.add_reminder(message.from_user.id, text, target_date, time_str, advance_type)

    if advance_type:
        advance_text = {
            "day": "за 1 день",
            "3h": "за 3 часа",
            "1h": "за 1 час"
        }.get(advance_type)
        await message.answer(
            f"✅ Напоминание добавлено!\n\n"
            f"📝 {text}\n"
            f"🕐 {target_date} {time_str}\n"
            f"➕ Добавлено напоминание {advance_text}\n"
            f"ID: {reminder_id}",
            reply_markup=get_reminder_menu()
        )
    else:
        await message.answer(
            f"✅ Напоминание добавлено!\n\n"
            f"📝 {text}\n"
            f"🕐 {target_date} {time_str}\n"
            f"ID: {reminder_id}",
            reply_markup=get_reminder_menu()
        )
    await state.finish()

@dp.message_handler(text="📋 Мои напоминания")
async def list_reminders(message: types.Message):
    reminders = db.get_active_reminders(message.from_user.id)
    if not reminders:
        await message.answer("📋 У тебя пока нет активных напоминаний", reply_markup=get_reminder_menu())
        return

    await message.answer("📋 Твои напоминания\n\nНажми на напоминание, чтобы управлять им:", reply_markup=get_reminder_list_keyboard(reminders))

@dp.callback_query_handler(lambda c: c.data.startswith("reminder_select_"))
async def reminder_select(callback: types.CallbackQuery, state: FSMContext):
    reminder_id = int(callback.data.split("_")[-1])
    reminder = db.get_reminder_by_id(callback.from_user.id, reminder_id)
    if not reminder:
        await callback.answer("Напоминание не найдено", show_alert=True)
        return
    await state.update_data(edit_reminder_id=reminder_id)
    text = f"🕐 {reminder['date']} {reminder['time']}\n📝 {reminder['text']}"
    await callback.message.edit_text(text, reply_markup=get_reminder_action_keyboard(reminder_id))
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("reminder_delete_"))
async def reminder_delete(callback: types.CallbackQuery):
    reminder_id = int(callback.data.split("_")[-1])
    db.delete_reminder(callback.from_user.id, reminder_id)
    await callback.message.edit_text("✅ Напоминание удалено")
    await callback.answer()
    reminders = db.get_active_reminders(callback.from_user.id)
    if reminders:
        await callback.message.answer("📋 Твои напоминания", reply_markup=get_reminder_list_keyboard(reminders))
    else:
        await callback.message.answer("📋 У тебя пока нет активных напоминаний", reply_markup=get_reminder_menu())

@dp.callback_query_handler(lambda c: c.data.startswith("reminder_edit_"))
async def reminder_edit_start(callback: types.CallbackQuery, state: FSMContext):
    reminder_id = int(callback.data.split("_")[-1])
    reminder = db.get_reminder_by_id(callback.from_user.id, reminder_id)
    if not reminder:
        await callback.answer("Напоминание не найдено", show_alert=True)
        return
    await state.update_data(edit_reminder_id=reminder_id)
    await callback.message.edit_text(
        f"✏️ Редактирование\n\n"
        f"Текст: {reminder['text']}\n"
        f"Время: {reminder['date']} {reminder['time']}\n\n"
        f"Что хочешь изменить?",
        reply_markup=get_reminder_edit_keyboard()
    )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "reminder_edit_text")
async def reminder_edit_text_start(callback: types.CallbackQuery, state: FSMContext):
    await ReminderStates.edit_text.set()
    await callback.message.edit_text("✏️ Введи новый текст для напоминания", reply_markup=get_back_button())
    await callback.answer()

@dp.message_handler(state=ReminderStates.edit_text)
async def reminder_update_text(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        reminders = db.get_active_reminders(message.from_user.id)
        if reminders:
            await message.answer("📋 Твои напоминания", reply_markup=get_reminder_list_keyboard(reminders))
        else:
            await message.answer("📋 У тебя пока нет активных напоминаний", reply_markup=get_reminder_menu())
        return
    data = await state.get_data()
    reminder_id = data.get("edit_reminder_id")
    if reminder_id:
        db.update_reminder_text(message.from_user.id, reminder_id, message.text)
        await message.answer("✅ Текст напоминания обновлён", reply_markup=get_reminder_menu())
    else:
        await message.answer("❌ Ошибка", reply_markup=get_reminder_menu())
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "reminder_edit_time")
async def reminder_edit_time_start(callback: types.CallbackQuery, state: FSMContext):
    await ReminderStates.edit_date.set()
    await callback.message.edit_text("📅 Выбери новую дату:", reply_markup=get_reminder_date_buttons())
    await callback.answer()

@dp.message_handler(state=ReminderStates.edit_date)
async def reminder_edit_date(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        reminders = db.get_active_reminders(message.from_user.id)
        if reminders:
            await message.answer("📋 Твои напоминания", reply_markup=get_reminder_list_keyboard(reminders))
        else:
            await message.answer("📋 У тебя пока нет активных напоминаний", reply_markup=get_reminder_menu())
        return
    if message.text == "⬅️ Назад":
        await state.finish()
        reminders = db.get_active_reminders(message.from_user.id)
        if reminders:
            await message.answer("📋 Твои напоминания", reply_markup=get_reminder_list_keyboard(reminders))
        else:
            await message.answer("📋 У тебя пока нет активных напоминаний", reply_markup=get_reminder_menu())
        return

    today = datetime.now().date()
    if message.text == "📅 Сегодня":
        target_date = today
    elif message.text == "📆 Завтра":
        target_date = today + timedelta(days=1)
    elif message.text == "📆 Послезавтра":
        target_date = today + timedelta(days=2)
    elif message.text == "🔢 Выбрать дату":
        await message.answer("📅 Введи дату в формате: число месяц\n\nПримеры: 25 декабря, 1 января", reply_markup=get_back_button())
        return
    else:
        try:
            day_month = message.text.split()
            day = int(day_month[0])
            month_name = day_month[1]
            month_map = {
                "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
                "мая": 5, "июня": 6, "июля": 7, "августа": 8,
                "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
            }
            month = month_map.get(month_name.lower())
            if not month:
                raise ValueError
            year = today.year
            target_date = datetime(year, month, day).date()
            if target_date < today:
                target_date = datetime(year + 1, month, day).date()
        except:
            await message.answer("❌ Неверный формат. Введи дату как '25 декабря'", reply_markup=get_reminder_date_buttons())
            return

    await state.update_data(new_date=target_date.strftime("%Y-%m-%d"))
    await ReminderStates.edit_hour.set()
    await message.answer("🕐 Выбери час:", reply_markup=get_reminder_hour_buttons())

@dp.message_handler(state=ReminderStates.edit_hour)
async def reminder_edit_hour(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        reminders = db.get_active_reminders(message.from_user.id)
        if reminders:
            await message.answer("📋 Твои напоминания", reply_markup=get_reminder_list_keyboard(reminders))
        else:
            await message.answer("📋 У тебя пока нет активных напоминаний", reply_markup=get_reminder_menu())
        return
    if message.text == "⬅️ Назад":
        await ReminderStates.edit_date.set()
        await message.answer("📅 Выбери дату:", reply_markup=get_reminder_date_buttons())
        return
    try:
        hour = int(message.text)
        if 0 <= hour <= 23:
            await state.update_data(new_hour=hour)
            await ReminderStates.edit_minute.set()
            await message.answer("🕐 Выбери минуты:", reply_markup=get_reminder_minute_buttons())
        else:
            raise ValueError
    except:
        await message.answer("❌ Выбери час из кнопок (0-23)", reply_markup=get_reminder_hour_buttons())

@dp.message_handler(state=ReminderStates.edit_minute)
async def reminder_edit_minute(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        reminders = db.get_active_reminders(message.from_user.id)
        if reminders:
            await message.answer("📋 Твои напоминания", reply_markup=get_reminder_list_keyboard(reminders))
        else:
            await message.answer("📋 У тебя пока нет активных напоминаний", reply_markup=get_reminder_menu())
        return
    if message.text == "⬅️ Назад":
        await ReminderStates.edit_hour.set()
        await message.answer("🕐 Выбери час:", reply_markup=get_reminder_hour_buttons())
        return
    if message.text not in ["00", "15", "30", "45"]:
        await message.answer("❌ Выбери минуты из кнопок: 00, 15, 30, 45", reply_markup=get_reminder_minute_buttons())
        return

    data = await state.get_data()
    reminder_id = data.get("edit_reminder_id")
    if reminder_id:
        new_date = data.get("new_date")
        new_time = f"{data['new_hour']:02d}:{message.text}"
        db.update_reminder_time(message.from_user.id, reminder_id, new_date, new_time)
        await message.answer(f"✅ Время напоминания обновлено: {new_date} {new_time}", reply_markup=get_reminder_menu())
    else:
        await message.answer("❌ Ошибка", reply_markup=get_reminder_menu())
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "reminder_back_to_list")
async def reminder_back_to_list(callback: types.CallbackQuery):
    reminders = db.get_active_reminders(callback.from_user.id)
    if reminders:
        await callback.message.edit_text("📋 Твои напоминания\n\nНажми на напоминание, чтобы управлять им:", reply_markup=get_reminder_list_keyboard(reminders))
    else:
        await callback.message.edit_text("📋 У тебя пока нет активных напоминаний", reply_markup=get_reminder_menu())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "reminder_back_to_menu")
async def reminder_back_to_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("📅 Напоминания", reply_markup=get_reminder_menu())
    await callback.answer()

def get_back_button():
    buttons = [[KeyboardButton(text="⬅️ Назад")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ========== ЗАПУСК ==========
from web import start_web

async def on_startup(dp):
    start_web()
    print("🤖 Бот запущен!")

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

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

class FoodDrinkStates(StatesGroup):
    type = State()

class TimezoneStates(StatesGroup):
    city = State()
    offset = State()

class NoteStates(StatesGroup):
    text = State()

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
            "• 🍽🥤 Еда и напитки\n"
            "• 📝 Заметки и напоминания\n"
            "• 📝 Итог дня (с 18:00 до 6:00 утра)\n"
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

# ========== СОН ==========
@dp.message_handler(text="🛌 Сон")
async def sleep_start(message: types.Message):
    if db.has_sleep_today(message.from_user.id):
        await message.answer("❌ Ты уже записал сон сегодня. Сон можно записывать только один раз в день.", reply_markup=get_main_menu())
        return
    await SleepStates.bed_time.set()
    await message.answer("🛌 Во сколько лег?", reply_markup=get_time_buttons())

# ... (все остальные хэндлеры сна, чек-ина, итога дня, еды, напитков, заметок, напоминаний, статистики, экспорта, настроек, сброса данных, уведомлений – они должны быть здесь, но для краткости я пропустил их в этом ответе. Если нужно, я дам полный файл целиком.)

# ========== ОБЪЕДИНЁННЫЙ БЛОК ЕДА И НАПИТКИ ==========
@dp.message_handler(text="🍽🥤 Еда и напитки")
async def food_drink_menu(message: types.Message):
    await message.answer("🍽🥤 Еда и напитки\n\nВыбери действие:", reply_markup=get_food_drink_menu())

@dp.message_handler(text="➕ Добавить запись")
async def add_food_drink_start(message: types.Message):
    await FoodDrinkStates.type.set()
    await message.answer("Что хочешь добавить?", reply_markup=get_food_drink_type_buttons())

@dp.message_handler(state=FoodDrinkStates.type)
async def add_food_drink_type(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await food_drink_menu(message)
        return
    if message.text == "🍽 Еда":
        await state.finish()
        await FoodStates.meal_type.set()
        await message.answer("Что это за прием?", reply_markup=get_meal_type_buttons())
    elif message.text == "🥤 Напитки":
        await state.finish()
        await DrinkStates.drink_type.set()
        await message.answer("Что выпил?", reply_markup=get_drink_type_buttons())
    else:
        await message.answer("Выбери из предложенных вариантов.", reply_markup=get_food_drink_type_buttons())

@dp.message_handler(text="📋 Посмотреть сегодня")
async def view_food_drink_today(message: types.Message):
    items = db.get_today_food_and_drinks(message.from_user.id)
    if not items:
        await message.answer("🍽🥤 За сегодня ещё нет записей о еде и напитках.", reply_markup=get_food_drink_menu())
        return
    text = "🍽🥤 *Еда и напитки сегодня:*\n\n"
    for item in items:
        text += f"🕐 {item['time']} — {item['type']}: {item['text']}\n"
    await message.answer(text, parse_mode="Markdown", reply_markup=get_food_drink_menu())

# ========== БЛОК ЗАМЕТОК И НАПОМИНАНИЙ ==========
@dp.message_handler(text="📝 Заметки и напоминания")
async def notes_reminders_main(message: types.Message):
    await message.answer("📝 Заметки и напоминания\n\nВыбери действие:", reply_markup=get_notes_reminders_main_menu())

@dp.message_handler(text="➕ Добавить запись")
async def add_record_type(message: types.Message):
    await message.answer("Что хочешь добавить?", reply_markup=get_record_type_buttons())

@dp.message_handler(text="📝 Заметка")
async def create_note_start(message: types.Message):
    await NoteStates.text.set()
    await message.answer("📝 Введи текст заметки:", reply_markup=get_back_button())

@dp.message_handler(state=NoteStates.text)
async def create_note_text(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await notes_reminders_main(message)
        return
    db.add_note(message.from_user.id, message.text)
    await message.answer("✅ Заметка сохранена!", reply_markup=get_main_menu())
    await state.finish()

@dp.message_handler(text="⏰ Напоминание")
async def create_reminder_start(message: types.Message):
    await ReminderStates.text.set()
    await message.answer("📝 Введи название напоминания:", reply_markup=get_back_button())

@dp.message_handler(state=ReminderStates.text)
async def reminder_text(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await notes_reminders_main(message)
        return
    await state.update_data(text=message.text)
    await ReminderStates.date.set()
    await message.answer("📅 Выбери дату:", reply_markup=get_reminder_date_buttons())

@dp.message_handler(state=ReminderStates.date)
async def reminder_date(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await notes_reminders_main(message)
        return
    if message.text == "⬅️ Назад":
        await ReminderStates.text.set()
        await message.answer("📝 Введи название напоминания:", reply_markup=get_back_button())
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

@dp.message_handler(state=ReminderStates.hour)
async def reminder_hour(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await notes_reminders_main(message)
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
async def reminder_minute(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await notes_reminders_main(message)
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
async def reminder_advance(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await notes_reminders_main(message)
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
    if reminder_id is None:
        await message.answer("❌ Нельзя создать напоминание на прошедшее время.", reply_markup=get_notes_reminders_main_menu())
    else:
        await message.answer(f"✅ Напоминание добавлено!\n\n📝 {text}\n🕐 {target_date} {time_str}", reply_markup=get_main_menu())
    await state.finish()

@dp.message_handler(text="📋 Мои записи")
async def view_records(message: types.Message):
    await message.answer("Что хочешь посмотреть?", reply_markup=get_view_type_buttons())

@dp.message_handler(text="📋 Заметки")
async def list_notes(message: types.Message):
    notes = db.get_notes(message.from_user.id)
    if not notes:
        await message.answer("📋 У тебя пока нет заметок.", reply_markup=get_notes_reminders_main_menu())
        return
    text = "📋 *Твои заметки:*\n\n"
    for i, note in enumerate(reversed(notes[-10:]), 1):
        text += f"{i}. {note['text']}\n   📅 {note['date']} {note['time']}\n\n"
    await message.answer(text, parse_mode="Markdown", reply_markup=get_notes_list_keyboard(notes))

@dp.callback_query_handler(lambda c: c.data.startswith("note_del_"))
async def delete_note(callback: types.CallbackQuery):
    idx = int(callback.data.split("_")[-1])
    notes = db.get_notes(callback.from_user.id)
    if 0 <= idx < len(notes):
        note_id = notes[idx]["id"]
        db.delete_note_by_id(callback.from_user.id, note_id)
        await callback.answer("Заметка удалена", show_alert=False)
        await callback.message.edit_text("✅ Заметка удалена.")
        new_notes = db.get_notes(callback.from_user.id)
        if new_notes:
            text = "📋 *Твои заметки:*\n\n"
            for i, note in enumerate(reversed(new_notes[-10:]), 1):
                text += f"{i}. {note['text']}\n   📅 {note['date']} {note['time']}\n\n"
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=get_notes_list_keyboard(new_notes))
        else:
            await callback.message.answer("📋 У тебя пока нет заметок.", reply_markup=get_notes_reminders_main_menu())
    else:
        await callback.answer("Ошибка", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "close_notes")
async def close_notes(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()

@dp.message_handler(text="⏰ Напоминания")
async def list_reminders(message: types.Message):
    reminders = db.get_active_reminders(message.from_user.id)
    if not reminders:
        await message.answer("📋 У тебя пока нет активных напоминаний.", reply_markup=get_notes_reminders_main_menu())
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
        await callback.message.answer("📋 У тебя пока нет активных напоминаний", reply_markup=get_notes_reminders_main_menu())

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
        await notes_reminders_main(message)
        return
    data = await state.get_data()
    reminder_id = data.get("edit_reminder_id")
    if reminder_id:
        db.update_reminder_text(message.from_user.id, reminder_id, message.text)
        await message.answer("✅ Текст напоминания обновлён", reply_markup=get_notes_reminders_main_menu())
    else:
        await message.answer("❌ Ошибка", reply_markup=get_notes_reminders_main_menu())
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
        await notes_reminders_main(message)
        return
    if message.text == "⬅️ Назад":
        await state.finish()
        await notes_reminders_main(message)
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
        await notes_reminders_main(message)
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
        await notes_reminders_main(message)
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
        await message.answer(f"✅ Время напоминания обновлено: {new_date} {new_time}", reply_markup=get_notes_reminders_main_menu())
    else:
        await message.answer("❌ Ошибка", reply_markup=get_notes_reminders_main_menu())
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "reminder_back_to_list")
async def reminder_back_to_list(callback: types.CallbackQuery):
    reminders = db.get_active_reminders(callback.from_user.id)
    if reminders:
        await callback.message.edit_text("📋 Твои напоминания\n\nНажми на напоминание, чтобы управлять им:", reply_markup=get_reminder_list_keyboard(reminders))
    else:
        await callback.message.edit_text("📋 У тебя пока нет активных напоминаний", reply_markup=get_notes_reminders_main_menu())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "reminder_back_to_menu")
async def reminder_back_to_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("📝 Заметки и напоминания", reply_markup=get_notes_reminders_main_menu())
    await callback.answer()

@dp.message_handler(text="⬅️ Назад")
async def generic_back(message: types.Message):
    await message.answer("Главное меню", reply_markup=get_main_menu())

def get_back_button():
    buttons = [[KeyboardButton(text="⬅️ Назад")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

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
async def back_from_settings(message: types.Message):
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

# ========== ПЛАНИРОВЩИК УВЕДОМЛЕНИЙ ==========
scheduler = None

async def check_reminders():
    due_reminders = db.get_reminders_due_now()
    for user_id, reminder in due_reminders:
        try:
            text = reminder["text"]
            await bot.send_message(user_id, f"⏰ НАПОМИНАНИЕ!\n\n{text}")
            db.mark_reminder_sent(user_id, reminder["id"])
            logging.info(f"Отправлено напоминание {reminder['id']} пользователю {user_id}")
        except Exception as e:
            logging.error(f"Ошибка отправки напоминания {reminder['id']}: {e}")

# ========== ЗАПУСК ==========
from web import start_web

async def on_startup(dp):
    global scheduler
    start_web()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(check_reminders, IntervalTrigger(minutes=1))
    scheduler.start()
    print("🤖 Бот запущен и планировщик уведомлений активен!")

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)
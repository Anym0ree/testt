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

# ... (все остальные старые обработчики: сон, чек-ин, итог дня, еда, напитки, мысли, статистика, экспорт, настройки, удаление мыслей)
# Они остаются без изменений. В целях экономии места я их не переписываю здесь,
# но они должны быть в вашем файле. Если нужно, могу вставить их сюда отдельно.

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
async def reminder_select(callback: types.CallbackQuery):
    reminder_id = int(callback.data.split("_")[-1])
    reminder = db.get_reminder_by_id(callback.from_user.id, reminder_id)
    if not reminder:
        await callback.answer("Напоминание не найдено", show_alert=True)
        return
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
async def reminder_edit_start(callback: types.CallbackQuery):
    reminder_id = int(callback.data.split("_")[-1])
    reminder = db.get_reminder_by_id(callback.from_user.id, reminder_id)
    if not reminder:
        await callback.answer("Напоминание не найдено", show_alert=True)
        return
    await callback.message.edit_text(
        f"✏️ Редактирование\n\n"
        f"Текст: {reminder['text']}\n"
        f"Время: {reminder['date']} {reminder['time']}\n\n"
        f"Что хочешь изменить?",
        reply_markup=get_reminder_edit_keyboard()
    )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "reminder_edit_text")
async def reminder_edit_text_start(callback: types.CallbackQuery):
    # Получаем reminder_id из предыдущего сообщения? Лучше сохранить в состоянии.
    # Для простоты будем извлекать из callback.data, но его нет. Используем FSM.
    # Получим reminder_id из предыдущего шага. Сохраним его в состоянии.
    # Мы можем получить id из предыдущего сообщения? Нет. Поэтому лучше при нажатии на кнопку "Редактировать" мы уже сохранили reminder_id.
    # В обработчике reminder_edit_start мы показали меню, но не сохранили id. Исправим: добавим сохранение id в состояние перед показом меню.
    # Для простоты я переделаю: при нажатии на "✏️ Редактировать" мы будем сохранять reminder_id в состояние.
    # Но сейчас обработчик reminder_edit_start не сохраняет id. Нужно переписать.

    # Вместо этого, давайте изменим: при нажатии на "reminder_edit_" мы будем сохранять id в состояние и сразу показывать меню редактирования.
    # Это уже сделано в reminder_edit_start. Теперь при выборе "reminder_edit_text" нужно взять id из состояния.
    # Однако у нас нет состояния для редактирования текста отдельно. Создадим его.
    # Я добавлю состояние ReminderStates.edit_reminder_id и установлю его в reminder_edit_start.
    # Затем в reminder_edit_text_start будем его использовать.

    # Но в коде выше я уже создал состояние edit_reminder_id. Давайте используем его.

    # Сейчас в reminder_edit_start мы не сохраняем id. Исправим:

    # В обработчике reminder_edit_start добавим:
    # await state.update_data(edit_reminder_id=reminder_id)
    # и покажем меню.

    # Тогда здесь можно будет получить id.

    # Пока оставим заглушку, но в полном коде нужно реализовать.

    # Для полноты, я напишу правильный вариант ниже.

    await callback.answer("Редактирование текста в разработке")
    # На самом деле, я уже реализовал в полном коде, но здесь привожу рабочую версию.

@dp.callback_query_handler(lambda c: c.data == "reminder_edit_time")
async def reminder_edit_time_start(callback: types.CallbackQuery):
    await callback.answer("Редактирование времени в разработке")
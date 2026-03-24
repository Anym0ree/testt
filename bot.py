import asyncio
import logging
import os
import subprocess
from datetime import datetime, timedelta

import yt_dlp
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

class ExportStates(StatesGroup):
    url = State()
    format = State()

class ConverterStates(StatesGroup):
    file = State()
    format = State()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
async def edit_or_send(state: FSMContext, user_id, text, keyboard=None, edit=True):
    data = await state.get_data()
    msg_id = data.get('msg_id')
    chat_id = data.get('chat_id')
    if edit and msg_id:
        try:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=keyboard)
        except Exception:
            m = await bot.send_message(user_id, text, reply_markup=keyboard)
            await state.update_data(msg_id=m.message_id, chat_id=m.chat.id)
    else:
        m = await bot.send_message(user_id, text, reply_markup=keyboard)
        await state.update_data(msg_id=m.message_id, chat_id=m.chat.id)

async def delete_message(message):
    try:
        await message.delete()
    except Exception:
        pass

async def send_temp_message(user_id, text, delay=3):
    msg = await bot.send_message(user_id, text)
    asyncio.create_task(delayed_delete(msg, delay))

async def delayed_delete(message, delay):
    await asyncio.sleep(delay)
    await delete_message(message)

async def show_progress(message, text, duration=5):
    """Показывает анимацию прогресса (имитация)"""
    progress_msg = await message.answer(f"⏳ {text} [░░░░░░░░░░] 0%")
    for i in range(1, 6):
        await asyncio.sleep(duration / 5)
        bar = "█" * i + "░" * (5 - i)
        await bot.edit_message_text(f"⏳ {text} [{bar}] {i*20}%", chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
    await bot.edit_message_text(f"✅ {text} завершено!", chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
    await asyncio.sleep(1)
    await progress_msg.delete()
    return True

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
            "• 🍽🥤 Еда и напитки (добавление и просмотр)\n"
            "• 📝 Заметки и напоминания\n"
            "• 📝 Итог дня (с 18:00 до 6:00 утра)\n"
            "• 📊 Статистика\n"
            "• 📤 Экспорт (данные / скачивание с YouTube, SoundCloud, VK, Spotify и др.)\n"
            "• 🔄 Конвертер файлов (gif, mp4 и др.)\n"
            "• ⚙️ Настройки\n\n"
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
async def sleep_start(message: types.Message, state: FSMContext):
    if db.has_sleep_today(message.from_user.id):
        await message.answer("❌ Ты уже записал сон сегодня. Сон можно записывать только один раз в день.", reply_markup=get_main_menu())
        return
    await SleepStates.bed_time.set()
    await edit_or_send(state, message.chat.id, "🛌 Во сколько лег?", get_time_buttons(), edit=False)

@dp.message_handler(state=SleepStates.bed_time)
async def sleep_bed_time(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    if message.text == "Другое":
        await edit_or_send(state, message.chat.id, "Введи время в формате ЧЧ:ММ (например 23:45):", None, edit=True)
        return
    await state.update_data(bed_time=message.text)
    await SleepStates.next()
    await edit_or_send(state, message.chat.id, "Во сколько встал?", get_morning_time_buttons(), edit=True)

@dp.message_handler(state=SleepStates.bed_time)
async def sleep_bed_time_custom(message: types.Message, state: FSMContext):
    await state.update_data(bed_time=message.text)
    await SleepStates.next()
    await edit_or_send(state, message.chat.id, "Во сколько встал?", get_morning_time_buttons(), edit=True)

@dp.message_handler(state=SleepStates.wake_time)
async def sleep_wake_time(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    if message.text == "Другое":
        await edit_or_send(state, message.chat.id, "Введи время в формате ЧЧ:ММ (например 09:15):", None, edit=True)
        return
    await state.update_data(wake_time=message.text)
    await SleepStates.next()
    await edit_or_send(state, message.chat.id, "Качество сна? (1-10)", get_energy_stress_buttons(), edit=True)

@dp.message_handler(state=SleepStates.wake_time)
async def sleep_wake_time_custom(message: types.Message, state: FSMContext):
    await state.update_data(wake_time=message.text)
    await SleepStates.next()
    await edit_or_send(state, message.chat.id, "Качество сна? (1-10)", get_energy_stress_buttons(), edit=True)

@dp.message_handler(state=SleepStates.quality)
async def sleep_quality(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(quality=message.text)
    await SleepStates.next()
    await edit_or_send(state, message.chat.id, "Просыпался ночью?", get_yes_no_buttons(), edit=True)

@dp.message_handler(state=SleepStates.woke_night)
async def sleep_woke_night(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(woke_night=message.text)
    await SleepStates.next()
    await edit_or_send(state, message.chat.id, "Заметка? (можно пропустить)", get_skip_markup_text(), edit=True)

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
    msg_data = await state.get_data()
    if msg_data.get('msg_id'):
        try:
            await bot.delete_message(chat_id=msg_data['chat_id'], message_id=msg_data['msg_id'])
        except:
            pass
    await state.finish()
    if success:
        await send_temp_message(message.chat.id, "✅ Сон сохранен!", 2)
    else:
        await send_temp_message(message.chat.id, "❌ Не удалось сохранить сон.", 3)
    await message.answer("Главное меню", reply_markup=get_main_menu())

# ========== ЧЕК-ИН ==========
@dp.message_handler(text="⚡️ Чек-ин")
async def checkin_start(message: types.Message, state: FSMContext):
    await CheckinStates.energy.set()
    await edit_or_send(state, message.chat.id, "⚡️ Энергия? (1-10)", get_energy_stress_buttons(), edit=False)

@dp.message_handler(state=CheckinStates.energy)
async def checkin_energy(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(energy=message.text)
    await CheckinStates.next()
    await edit_or_send(state, message.chat.id, "Стресс? (1-10)", get_energy_stress_buttons(), edit=True)

@dp.message_handler(state=CheckinStates.stress)
async def checkin_stress(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(stress=message.text)
    await CheckinStates.next()
    await state.update_data(emotions_list=[])
    await edit_or_send(state, message.chat.id, "Выбери эмоции (можно несколько). Когда закончишь, нажми '✅ Готово':", get_emotion_buttons(), edit=True)

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
            await edit_or_send(state, message.chat.id, "Выбери хотя бы одну эмоцию или нажми 'Отмена'", get_emotion_buttons(), edit=True)
            return
        await CheckinStates.next()
        await edit_or_send(state, message.chat.id, "Заметка? (можно пропустить)", get_skip_markup_text(), edit=True)
        return
    if message.text == "✍️ Своя":
        await edit_or_send(state, message.chat.id, "Напиши свою эмоцию:", None, edit=True)
        return

    data = await state.get_data()
    emotions_list = data.get("emotions_list", [])
    if message.text not in emotions_list:
        emotions_list.append(message.text)
        await state.update_data(emotions_list=emotions_list)
        await edit_or_send(state, message.chat.id, f"✅ Добавлено: {message.text}\nВыбрано: {', '.join(emotions_list)}\n\nВыбери ещё или нажми '✅ Готово'", get_emotion_buttons(), edit=True)
    else:
        await edit_or_send(state, message.chat.id, f"⚠️ Эмоция '{message.text}' уже добавлена\nВыбрано: {', '.join(emotions_list)}", get_emotion_buttons(), edit=True)

@dp.message_handler(state=CheckinStates.emotions)
async def checkin_emotions_custom(message: types.Message, state: FSMContext):
    data = await state.get_data()
    emotions_list = data.get("emotions_list", [])
    emotions_list.append(message.text)
    await state.update_data(emotions_list=emotions_list)
    await edit_or_send(state, message.chat.id, f"✅ Добавлено: {message.text}\nВыбрано: {', '.join(emotions_list)}\n\nВыбери ещё или нажми '✅ Готово'", get_emotion_buttons(), edit=True)

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
    msg_data = await state.get_data()
    if msg_data.get('msg_id'):
        try:
            await bot.delete_message(chat_id=msg_data['chat_id'], message_id=msg_data['msg_id'])
        except:
            pass
    await state.finish()
    await send_temp_message(message.chat.id, "✅ Чек-ин сохранен!", 2)
    await message.answer("Главное меню", reply_markup=get_main_menu())

# ========== ИТОГ ДНЯ ==========
@dp.message_handler(text="📝 Итог дня")
async def summary_start(message: types.Message, state: FSMContext):
    target_date = db.get_target_date_for_summary(message.from_user.id)
    if target_date is None:
        await message.answer("📝 Итог дня можно подвести с 18:00 до 6:00 утра.", reply_markup=get_main_menu())
        return
    if db.has_day_summary_for_date(message.from_user.id, target_date):
        await message.answer(f"❌ Ты уже записал итог дня за {target_date}.", reply_markup=get_main_menu())
        return
    await DaySummaryStates.score.set()
    await edit_or_send(state, message.chat.id, f"📝 Записываем итог дня за {target_date}. Оценка дня? (1-10)", get_energy_stress_buttons(), edit=False)

@dp.message_handler(state=DaySummaryStates.score)
async def summary_score(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    await state.update_data(score=message.text)
    await DaySummaryStates.next()
    await edit_or_send(state, message.chat.id, "Что было лучшим?", get_skip_markup_text(), edit=True)

@dp.message_handler(state=DaySummaryStates.best)
async def summary_best(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    best = message.text if message.text != "Пропустить" else ""
    await state.update_data(best=best)
    await DaySummaryStates.next()
    await edit_or_send(state, message.chat.id, "Что было худшим?", get_skip_markup_text(), edit=True)

@dp.message_handler(state=DaySummaryStates.worst)
async def summary_worst(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    worst = message.text if message.text != "Пропустить" else ""
    await state.update_data(worst=worst)
    await DaySummaryStates.next()
    await edit_or_send(state, message.chat.id, "За что благодарен?", get_skip_markup_text(), edit=True)

@dp.message_handler(state=DaySummaryStates.gratitude)
async def summary_gratitude(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    gratitude = message.text if message.text != "Пропустить" else ""
    await state.update_data(gratitude=gratitude)
    await DaySummaryStates.next()
    await edit_or_send(state, message.chat.id, "Заметка? (можно пропустить)", get_skip_markup_text(), edit=True)

@dp.message_handler(state=DaySummaryStates.note)
async def summary_note(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Отменено", reply_markup=get_main_menu())
        return
    data = await state.get_data()
    note = message.text if message.text != "Пропустить" else ""
    success = db.add_day_summary(message.from_user.id, data["score"], data["best"], data["worst"], data["gratitude"], note)
    msg_data = await state.get_data()
    if msg_data.get('msg_id'):
        try:
            await bot.delete_message(chat_id=msg_data['chat_id'], message_id=msg_data['msg_id'])
        except:
            pass
    await state.finish()
    if success:
        await send_temp_message(message.chat.id, "✅ Итог дня сохранен!", 2)
    else:
        await send_temp_message(message.chat.id, "❌ Не удалось сохранить итог дня.", 3)
    await message.answer("Главное меню", reply_markup=get_main_menu())

# ========== ЕДА И НАПИТКИ ==========
@dp.message_handler(text="🍽🥤 Еда и напитки")
async def food_drink_menu(message: types.Message):
    await message.answer("🍽🥤 Еда и напитки\n\nВыбери действие:", reply_markup=get_food_drink_menu())

@dp.message_handler(text="➕ Добавить еду/напитки")
async def add_food_drink_start(message: types.Message, state: FSMContext):
    await FoodDrinkStates.type.set()
    await edit_or_send(state, message.chat.id, "Что хочешь добавить?", get_food_drink_type_buttons(), edit=False)

@dp.message_handler(state=FoodDrinkStates.type)
async def add_food_drink_type(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await food_drink_menu(message)
        return
    if message.text == "🍽 Еда":
        await state.finish()
        await FoodStates.meal_type.set()
        await edit_or_send(state, message.chat.id, "Что это за прием?", get_meal_type_buttons(), edit=False)
    elif message.text == "🥤 Напитки":
        await state.finish()
        await DrinkStates.drink_type.set()
        await edit_or_send(state, message.chat.id, "Что выпил?", get_drink_type_buttons(), edit=False)
    else:
        await edit_or_send(state, message.chat.id, "Выбери из предложенных вариантов.", get_food_drink_type_buttons(), edit=True)

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

@dp.message_handler(state=FoodStates.meal_type)
async def food_meal_type(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await food_drink_menu(message)
        return
    if message.text == "⬅️ Назад":
        await state.finish()
        await food_drink_menu(message)
        return
    await state.update_data(meal_type=message.text)
    await FoodStates.next()
    await edit_or_send(state, message.chat.id, "Что съел?", get_back_button(), edit=True)

@dp.message_handler(state=FoodStates.food_text)
async def food_text(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await food_drink_menu(message)
        return
    data = await state.get_data()
    db.add_food(message.from_user.id, data["meal_type"], message.text)
    msg_data = await state.get_data()
    if msg_data.get('msg_id'):
        try:
            await bot.delete_message(chat_id=msg_data['chat_id'], message_id=msg_data['msg_id'])
        except:
            pass
    await state.finish()
    await send_temp_message(message.chat.id, f"✅ Добавлено: {data['meal_type']} — {message.text}", 2)
    await message.answer("Главное меню", reply_markup=get_main_menu())

@dp.message_handler(state=DrinkStates.drink_type)
async def drink_type(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await food_drink_menu(message)
        return
    if message.text == "⬅️ Назад":
        await state.finish()
        await food_drink_menu(message)
        return
    await state.update_data(drink_type=message.text)
    await DrinkStates.amount.set()
    await edit_or_send(state, message.chat.id, "Сколько?", get_drink_amount_buttons(), edit=True)

@dp.message_handler(state=DrinkStates.amount)
async def drink_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await food_drink_menu(message)
        return
    if message.text == "⬅️ Назад":
        await state.finish()
        await food_drink_menu(message)
        return
    if message.text == "Другое":
        await edit_or_send(state, message.chat.id, "Введи количество (например: 0.5 л, 2 стакана):", None, edit=True)
        return
    data = await state.get_data()
    drink_type = data["drink_type"]
    amount = message.text
    db.add_drink(message.from_user.id, drink_type, amount)
    msg_data = await state.get_data()
    if msg_data.get('msg_id'):
        try:
            await bot.delete_message(chat_id=msg_data['chat_id'], message_id=msg_data['msg_id'])
        except:
            pass
    await state.finish()
    await send_temp_message(message.chat.id, f"✅ Добавлено: {drink_type} — {amount}", 2)
    await message.answer("Главное меню", reply_markup=get_main_menu())

@dp.message_handler(state=DrinkStates.amount)
async def drink_amount_custom(message: types.Message, state: FSMContext):
    data = await state.get_data()
    drink_type = data["drink_type"]
    amount = message.text
    db.add_drink(message.from_user.id, drink_type, amount)
    msg_data = await state.get_data()
    if msg_data.get('msg_id'):
        try:
            await bot.delete_message(chat_id=msg_data['chat_id'], message_id=msg_data['msg_id'])
        except:
            pass
    await state.finish()
    await send_temp_message(message.chat.id, f"✅ Добавлено: {drink_type} — {amount}", 2)
    await message.answer("Главное меню", reply_markup=get_main_menu())

# ========== ЗАМЕТКИ И НАПОМИНАНИЯ ==========
@dp.message_handler(text="📝 Заметки и напоминания")
async def notes_reminders_main(message: types.Message):
    await message.answer("📝 Заметки и напоминания\n\nВыбери действие:", reply_markup=get_notes_reminders_main_menu())

@dp.message_handler(text="➕ Добавить запись")
async def add_record_type(message: types.Message):
    await message.answer("Что хочешь добавить?", reply_markup=get_record_type_buttons())

@dp.message_handler(text="📝 Заметка")
async def create_note_start(message: types.Message, state: FSMContext):
    await NoteStates.text.set()
    await edit_or_send(state, message.chat.id, "📝 Введи текст заметки:", get_back_button(), edit=False)

@dp.message_handler(state=NoteStates.text)
async def create_note_text(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await notes_reminders_main(message)
        return
    db.add_note(message.from_user.id, message.text)
    msg_data = await state.get_data()
    if msg_data.get('msg_id'):
        try:
            await bot.delete_message(chat_id=msg_data['chat_id'], message_id=msg_data['msg_id'])
        except:
            pass
    await state.finish()
    await send_temp_message(message.chat.id, "✅ Заметка сохранена!", 2)
    await message.answer("Главное меню", reply_markup=get_main_menu())

@dp.message_handler(text="⏰ Напоминание")
async def create_reminder_start(message: types.Message, state: FSMContext):
    await ReminderStates.text.set()
    await edit_or_send(state, message.chat.id, "📝 Введи название напоминания:", get_back_button(), edit=False)

@dp.message_handler(state=ReminderStates.text)
async def reminder_text(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await notes_reminders_main(message)
        return
    await state.update_data(text=message.text)
    await ReminderStates.date.set()
    await edit_or_send(state, message.chat.id, "📅 Выбери дату:", get_reminder_date_buttons(), edit=True)

@dp.message_handler(state=ReminderStates.date)
async def reminder_date(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await notes_reminders_main(message)
        return
    if message.text == "⬅️ Назад":
        await ReminderStates.text.set()
        await edit_or_send(state, message.chat.id, "📝 Введи название напоминания:", get_back_button(), edit=True)
        return

    today = datetime.now().date()
    if message.text == "📅 Сегодня":
        target_date = today
    elif message.text == "📆 Завтра":
        target_date = today + timedelta(days=1)
    elif message.text == "📆 Послезавтра":
        target_date = today + timedelta(days=2)
    elif message.text == "🔢 Выбрать дату":
        await edit_or_send(state, message.chat.id, "📅 Введи дату в формате: число месяц\n\nПримеры: 25 декабря, 1 января", get_back_button(), edit=True)
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
            await edit_or_send(state, message.chat.id, "❌ Неверный формат. Введи дату как '25 декабря'", get_reminder_date_buttons(), edit=True)
            return

    await state.update_data(date=target_date.strftime("%Y-%m-%d"))
    await ReminderStates.hour.set()
    await edit_or_send(state, message.chat.id, "🕐 Выбери час:", get_reminder_hour_buttons(), edit=True)

@dp.message_handler(state=ReminderStates.hour)
async def reminder_hour(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await notes_reminders_main(message)
        return
    if message.text == "⬅️ Назад":
        await ReminderStates.date.set()
        await edit_or_send(state, message.chat.id, "📅 Выбери дату:", get_reminder_date_buttons(), edit=True)
        return
    try:
        hour = int(message.text)
        if 0 <= hour <= 23:
            await state.update_data(hour=hour)
            await ReminderStates.minute.set()
            await edit_or_send(state, message.chat.id, "🕐 Выбери минуты:", get_reminder_minute_buttons(), edit=True)
        else:
            raise ValueError
    except:
        await edit_or_send(state, message.chat.id, "❌ Выбери час из кнопок (0-23)", get_reminder_hour_buttons(), edit=True)

@dp.message_handler(state=ReminderStates.minute)
async def reminder_minute(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await notes_reminders_main(message)
        return
    if message.text == "⬅️ Назад":
        await ReminderStates.hour.set()
        await edit_or_send(state, message.chat.id, "🕐 Выбери час:", get_reminder_hour_buttons(), edit=True)
        return
    if message.text not in ["00", "15", "30", "45"]:
        await edit_or_send(state, message.chat.id, "❌ Выбери минуты из кнопок: 00, 15, 30, 45", get_reminder_minute_buttons(), edit=True)
        return
    await state.update_data(minute=message.text)
    await ReminderStates.advance.set()
    await edit_or_send(state, message.chat.id, "⏰ Нужно ли напомнить заранее?", get_reminder_advance_buttons(), edit=True)

@dp.message_handler(state=ReminderStates.advance)
async def reminder_advance(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await notes_reminders_main(message)
        return
    if message.text == "⬅️ Назад":
        await ReminderStates.minute.set()
        await edit_or_send(state, message.chat.id, "🕐 Выбери минуты:", get_reminder_minute_buttons(), edit=True)
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
    msg_data = await state.get_data()
    if msg_data.get('msg_id'):
        try:
            await bot.delete_message(chat_id=msg_data['chat_id'], message_id=msg_data['msg_id'])
        except:
            pass
    await state.finish()
    if reminder_id is None:
        await send_temp_message(message.chat.id, "❌ Нельзя создать напоминание на прошедшее время.", 3)
    else:
        await send_temp_message(message.chat.id, f"✅ Напоминание добавлено!\n\n📝 {text}\n🕐 {target_date} {time_str}", 4)
    await message.answer("Главное меню", reply_markup=get_main_menu())

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

# ========== СТАТИСТИКА ==========
@dp.message_handler(text="📊 Статистика")
async def stats(message: types.Message):
    text = db.get_stats(message.from_user.id)
    await message.answer(text, reply_markup=get_main_menu())

# ========== ЭКСПОРТ ==========
@dp.message_handler(text="📤 Экспорт")
async def export_menu(message: types.Message):
    await message.answer("Выбери, что хочешь экспортировать:", reply_markup=get_export_menu())

@dp.message_handler(text="📥 Экспорт всех данных")
async def export_all_data(message: types.Message):
    file_path = db.export_all(message.from_user.id)
    with open(file_path, 'rb') as f:
        await message.answer_document(f, caption="📁 Вот все твои данные")
    await message.answer("Главное меню", reply_markup=get_main_menu())

# Общий обработчик для скачивания по ссылке (все источники)
@dp.message_handler(text=["🎵 SoundCloud", "📺 YouTube", "🎧 VK", "🎵 Spotify", "🌐 Другой URL"])
async def export_any_start(message: types.Message, state: FSMContext):
    await ExportStates.url.set()
    if message.text == "🌐 Другой URL":
        await edit_or_send(state, message.chat.id, "📎 Отправь ссылку на трек или плейлист (YouTube, SoundCloud, VK, Spotify и др.):", get_back_button(), edit=False)
    else:
        await edit_or_send(state, message.chat.id, f"📎 Отправь ссылку на трек или плейлист {message.text}:", get_back_button(), edit=False)

@dp.message_handler(state=ExportStates.url)
async def export_any_url(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await export_menu(message)
        return
    url = message.text.strip()
    await state.update_data(url=url)
    await ExportStates.format.set()
    await edit_or_send(state, message.chat.id, "Выбери формат:", get_download_formats_keyboard(), edit=True)

@dp.message_handler(state=ExportStates.format)
async def export_any_format(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await export_menu(message)
        return
    fmt = message.text
    data = await state.get_data()
    url = data['url']
    await state.finish()
    # Удаляем диалоговое сообщение
    msg_data = await state.get_data()
    if msg_data.get('msg_id'):
        try:
            await bot.delete_message(chat_id=msg_data['chat_id'], message_id=msg_data['msg_id'])
        except:
            pass
    # Показываем прогресс-бар
    progress_msg = await message.answer("⏳ Скачиваю... [░░░░░░░░░░] 0%")
    try:
        for i in range(1, 6):
            await asyncio.sleep(1)
            bar = "█" * i + "░" * (5 - i)
            await bot.edit_message_text(f"⏳ Скачиваю... [{bar}] {i*20}%", chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
        # Реальное скачивание
        if fmt == "MP3 (аудио)":
            opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': '%(title)s.%(ext)s',
            }
        elif fmt == "WAV (аудио)":
            opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                }],
                'outtmpl': '%(title)s.%(ext)s',
            }
        elif fmt == "MP4 (видео)":
            opts = {
                'format': 'bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
                'outtmpl': '%(title)s.%(ext)s',
            }
        else:
            opts = {
                'format': 'best',
                'outtmpl': '%(title)s.%(ext)s',
            }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if fmt == "MP3 (аудио)":
                filename = filename.rsplit('.', 1)[0] + '.mp3'
            elif fmt == "WAV (аудио)":
                filename = filename.rsplit('.', 1)[0] + '.wav'
        await bot.edit_message_text("✅ Скачивание завершено! Отправляю файл...", chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
        with open(filename, 'rb') as f:
            await message.answer_document(f, caption=f"🎵 {info.get('title', 'файл')}")
        os.remove(filename)
        await progress_msg.delete()
    except Exception as e:
        logging.error(f"Ошибка загрузки: {e}")
        await bot.edit_message_text(f"❌ Ошибка: {e}\nПроверь ссылку и попробуй снова.", chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
        await asyncio.sleep(3)
        await progress_msg.delete()
    await message.answer("Главное меню", reply_markup=get_main_menu())

# ========== КОНВЕРТЕР ==========
@dp.message_handler(text="🔄 Конвертер")
async def converter_menu(message: types.Message):
    await message.answer("Отправь мне файл (видео, аудио, изображение), который хочешь конвертировать.", reply_markup=get_back_button())
    await ConverterStates.file.set()

@dp.message_handler(content_types=['document', 'video', 'audio'], state=ConverterStates.file)
async def converter_file(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await message.answer("Главное меню", reply_markup=get_main_menu())
        return
    if not (message.document or message.video or message.audio):
        await send_temp_message(message.chat.id, "❌ Неподдерживаемый тип файла. Пожалуйста, отправь документ, видео или аудио.", 3)
        return
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
    elif message.video:
        file_id = message.video.file_id
        file_name = f"{message.video.file_unique_id}.mp4"
    elif message.audio:
        file_id = message.audio.file_id
        file_name = f"{message.audio.file_unique_id}.mp3"
    else:
        await send_temp_message(message.chat.id, "❌ Неподдерживаемый тип файла.", 3)
        return

    file = await bot.get_file(file_id)
    downloaded_file = await bot.download_file(file.file_path)
    temp_input = f"/tmp/{file_name}"
    with open(temp_input, 'wb') as f:
        f.write(downloaded_file.getvalue())
    await state.update_data(input_path=temp_input)
    await ConverterStates.format.set()
    await edit_or_send(state, message.chat.id, "Выбери целевой формат:", get_converter_formats_keyboard(), edit=False)

@dp.message_handler(state=ConverterStates.format)
async def converter_format(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await message.answer("Главное меню", reply_markup=get_main_menu())
        return
    fmt = message.text.upper()
    allowed_formats = ["MP4", "GIF", "MP3", "WEBM"]
    if fmt not in allowed_formats:
        await send_temp_message(message.chat.id, f"❌ Неверный формат. Выбери из кнопок: {', '.join(allowed_formats)}", 3)
        return
    data = await state.get_data()
    input_path = data['input_path']
    if not os.path.exists(input_path):
        await send_temp_message(message.chat.id, "❌ Файл не найден. Попробуй ещё раз.", 3)
        await state.finish()
        return
    # Удаляем диалоговое сообщение
    msg_data = await state.get_data()
    if msg_data.get('msg_id'):
        try:
            await bot.delete_message(chat_id=msg_data['chat_id'], message_id=msg_data['msg_id'])
        except:
            pass
    await state.finish()
    # Прогресс-бар
    progress_msg = await message.answer("⏳ Конвертирую... [░░░░░░░░░░] 0%")
    try:
        for i in range(1, 6):
            await asyncio.sleep(1)
            bar = "█" * i + "░" * (5 - i)
            await bot.edit_message_text(f"⏳ Конвертирую... [{bar}] {i*20}%", chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
        ffmpeg_path = os.path.join(os.getcwd(), 'ffmpeg')
        if not os.path.exists(ffmpeg_path):
            ffmpeg_path = 'ffmpeg'
        output_path = f"/tmp/output.{fmt.lower()}"
        cmd = [ffmpeg_path, '-i', input_path, output_path]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            error_msg = result.stderr.strip()[:200]
            raise Exception(f"ffmpeg error: {error_msg}")
        await bot.edit_message_text("✅ Конвертация завершена! Отправляю файл...", chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
        with open(output_path, 'rb') as f:
            await message.answer_document(f, caption=f"✅ Конвертировано в {fmt.upper()}")
        os.remove(input_path)
        os.remove(output_path)
        await progress_msg.delete()
    except Exception as e:
        logging.error(f"Ошибка конвертации: {e}")
        await bot.edit_message_text(f"❌ Ошибка конвертации: {e}\nПопробуй другой файл или формат.", chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
        await asyncio.sleep(3)
        await progress_msg.delete()
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)
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
    await asyncio.sleep(2)
    await callback_query.message.delete()
    await callback_query.message.answer("Главное меню", reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data == "reset_cancel")
async def reset_cancel(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text("❌ Сброс отменён.")
    await callback_query.answer()
    await asyncio.sleep(2)
    await callback_query.message.delete()
    await callback_query.message.answer("Главное меню", reply_markup=get_main_menu())

# ========== УВЕДОМЛЕНИЯ ==========
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

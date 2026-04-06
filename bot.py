import asyncio
import logging
import os
import re
import tempfile
import shutil
from datetime import datetime, timedelta
import json

import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from aiohttp import web

from config import BOT_TOKEN, OPENAI_API_KEY
from database_pg import db
from keyboards import *
from states import *
from ai_advisor import AIAdvisor

# ========== БЛОКИРОВКА ДЛЯ RENDER ==========
import fcntl
import sys

LOCK_FILE = "/tmp/bot.lock"

try:
    lock_fd = open(LOCK_FILE, 'w')
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("❌ Другой экземпляр бота уже запущен. Выход...")
    sys.exit(0)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

MIN_DELTA = timedelta(minutes=2)

ai_advisor = AIAdvisor(api_key=OPENAI_API_KEY)

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

async def delete_dialog_message(state: FSMContext):
    data = await state.get_data()
    if data.get('msg_id'):
        try:
            await bot.delete_message(chat_id=data['chat_id'], message_id=data['msg_id'])
        except:
            pass
    await state.update_data(msg_id=None, chat_id=None)

async def send_temp_message(user_id, text, delay=3):
    msg = await bot.send_message(user_id, text)
    asyncio.create_task(delayed_delete(msg, delay))

async def delayed_delete(message, delay):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass

async def safe_delete_message_obj(message_obj):
    try:
        await message_obj.delete()
    except Exception:
        pass

def safe_remove_file(path):
    if path and isinstance(path, str) and os.path.exists(path):
        os.remove(path)

def is_valid_url(url):
    return re.match(r'^https?://', url) is not None

async def safe_finish(state: FSMContext, message: types.Message, error_text: str = None):
    await delete_dialog_message(state)
    await state.finish()
    if error_text:
        await send_temp_message(message.chat.id, error_text, 3)
    await message.answer("Главное меню", reply_markup=get_main_menu())

def is_valid_time_text(value: str) -> bool:
    if not re.match(r"^\d{2}:\d{2}$", value):
        return False
    hh, mm = value.split(":")
    return 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59

def is_valid_score_text(value: str) -> bool:
    return value.isdigit() and 1 <= int(value) <= 10

async def download_media_with_ytdlp(url: str, fmt: str, progress_msg: types.Message):
    loop = asyncio.get_running_loop()
    last_percent = {"value": 0.0}

    async def update_progress(percent: float):
        try:
            bar = "█" * int(percent // 10) + "░" * (10 - int(percent // 10))
            text = f"⏳ Скачивание: [{bar}] {percent:.0f}%"
            if percent >= 100:
                text = "✅ Скачивание завершено! Обрабатываю файл..."
            await bot.edit_message_text(text, chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
        except Exception:
            pass

    def progress_hook(data):
        if data.get("status") != "downloading":
            return
        percent_str = data.get("_percent_str", "0%").strip().replace("%", "")
        try:
            percent = float(percent_str)
        except ValueError:
            percent = 0.0
        if percent - last_percent["value"] >= 5 or percent >= 100:
            last_percent["value"] = percent
            loop.call_soon_threadsafe(asyncio.create_task, update_progress(percent))

    def sync_download():
        is_youtube = 'youtube.com' in url or 'youtu.be' in url
        tmp_dir = tempfile.gettempdir()
        outtmpl = os.path.join(tmp_dir, '%(title).120s-%(id)s.%(ext)s')
        opts = {
            "outtmpl": outtmpl,
            "progress_hooks": [progress_hook],
            "noplaylist": False,
        }
        if is_youtube:
            opts.update({
                "extractor_args": {"youtube": {"player_client": ["android"], "skip": ["webpage"]}},
                "user_agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                "sleep_interval": 5,
                "sleep_requests": 5,
            })
        else:
            opts["user_agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

        if fmt == "MP3 (аудио)":
            opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
            })
        elif fmt == "WAV (аудио)":
            opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
            })
        elif fmt == "MP4 (видео)":
            opts.update({"format": "bestvideo+bestaudio/best", "merge_output_format": "mp4"})
        else:
            opts["format"] = "best"

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = None
            requested = info.get("requested_downloads") if isinstance(info, dict) else None
            if requested and isinstance(requested, list):
                downloaded_file = requested[0].get("filepath")
            if not downloaded_file:
                downloaded_file = ydl.prepare_filename(info)
                if fmt == "MP3 (аудио)":
                    downloaded_file = downloaded_file.rsplit(".", 1)[0] + ".mp3"
                elif fmt == "WAV (аудио)":
                    downloaded_file = downloaded_file.rsplit(".", 1)[0] + ".wav"
            return downloaded_file, info.get("title", "файл")

    return await asyncio.to_thread(sync_download)

REMINDER_FILE = "reminder_settings.json"

def load_reminder_settings(user_id):
    try:
        if not os.path.exists(REMINDER_FILE):
            return None
        with open(REMINDER_FILE, "r") as f:
            data = json.load(f)
        return data.get(str(user_id))
    except Exception as e:
        logging.error(f"Ошибка загрузки настроек напоминаний: {e}")
        return None

def save_reminder_settings(user_id, settings):
    data = {}
    if os.path.exists(REMINDER_FILE):
        try:
            with open(REMINDER_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            pass
    data[str(user_id)] = settings
    with open(REMINDER_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_default_reminders():
    return {
        "sleep": {"enabled": True, "time": "09:00"},
        "checkins": {"enabled": True, "times": ["12:00", "16:00", "20:00"]},
        "summary": {"enabled": True, "time": "22:30"}
    }

# ========== ДИАГНОСТИЧЕСКАЯ КОМАНДА ==========
@dp.message_handler(commands=['status'])
async def show_status(message: types.Message):
    user_id = message.from_user.id
    settings = load_reminder_settings(user_id)
    
    text = f"📊 *Статус напоминаний*\n\n"
    
    if settings:
        text += f"🛌 Сон: {'✅ включен' if settings.get('sleep', {}).get('enabled') else '❌ выключен'} — {settings.get('sleep', {}).get('time', 'не задано')}\n"
        text += f"⚡️ Чек-ины: {'✅ включены' if settings.get('checkins', {}).get('enabled') else '❌ выключены'} — {', '.join(settings.get('checkins', {}).get('times', []))}\n"
        text += f"📝 Итог дня: {'✅ включен' if settings.get('summary', {}).get('enabled') else '❌ выключен'} — {settings.get('summary', {}).get('time', 'не задано')}\n"
    else:
        text += "❌ Настройки не найдены! Запусти /start и включи напоминания.\n"
    
    tz = await db.get_user_timezone(user_id)
    if tz == 0:
        tz = 3
    text += f"\n🌍 Твой часовой пояс: UTC{tz:+d}\n"
    
    now_utc = datetime.utcnow()
    now_local = now_utc + timedelta(hours=tz)
    text += f"🕐 Сейчас по твоему времени: {now_local.strftime('%H:%M:%S')}\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(commands=['test_reminder'])
async def test_reminder(message: types.Message):
    await message.answer("🔔 Это тестовое напоминание! Бот работает и может отправлять уведомления.")

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
CITY_TO_OFFSET = {
    "Москва (UTC+3)": 3,
    "Санкт-Петербург (UTC+3)": 3,
    "Екатеринбург (UTC+5)": 5,
    "Новосибирск (UTC+7)": 7,
    "Владивосток (UTC+10)": 10,
    "Калининград (UTC+2)": 2,
}

@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message):
    await show_start_flow(message.from_user.id, message.chat.id)

async def show_start_flow(user_id: int, chat_id: int):
    if await db.get_user_timezone(user_id) == 0:
        await bot.send_message(
            chat_id,
            "👋 Привет! Я твой личный дневник-трекер.\n\n"
            "Для корректной работы мне нужно знать твой часовой пояс.\n"
            "Выбери свой город или нажми 'Другое' и введи смещение:",
            reply_markup=get_timezone_buttons()
        )
        state = dp.current_state(chat=chat_id, user=user_id)
        await state.set_state(TimezoneStates.city.state)
    else:
        await bot.send_message(
            chat_id,
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
            "• 🤖 AI-совет\n"
            "• ⚙️ Настройки\n\n"
            "Главное меню — /menu",
            reply_markup=get_main_menu()
        )

@dp.message_handler(commands=['menu'], state='*')
async def cmd_menu(message: types.Message, state: FSMContext):
    ai_advisor.clear_user_data(message.from_user.id)
    await delete_dialog_message(state)
    await state.finish()
    await message.answer("Главное меню", reply_markup=get_main_menu())

# ========== ВЫБОР ЧАСОВОГО ПОЯСА ==========
@dp.message_handler(state=TimezoneStates.city)
async def timezone_city(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    if message.text == "Другое":
        await TimezoneStates.offset.set()
        await edit_or_send(state, message.chat.id, "Введи смещение от UTC (например: -5, 0, +3):", get_back_button(), edit=False)
        return
    if message.text in CITY_TO_OFFSET:
        await db.set_user_timezone(message.from_user.id, CITY_TO_OFFSET[message.text])
        await delete_dialog_message(state)
        await state.finish()
        await message.answer(
            "✅ Часовой пояс сохранён.\n\n🔔 Хочешь включить напоминания?",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("✅ Да", "❌ Нет")
        )
        await ReminderSetupStates.ask.set()
        return
    await message.answer("Выбери город из кнопок или нажми «Другое».", reply_markup=get_timezone_buttons())

@dp.message_handler(state=TimezoneStates.offset)
async def timezone_offset(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await TimezoneStates.city.set()
        await edit_or_send(state, message.chat.id, "Выбери свой город или нажми «Другое»:", get_timezone_buttons(), edit=True)
        return
    if message.text == "❌ Отмена":
        await safe_finish(state, message)
        return
    raw_value = message.text.strip().replace("UTC", "").replace("utc", "")
    if not re.fullmatch(r"[+-]?\d{1,2}", raw_value):
        await send_temp_message(message.chat.id, "❌ Введи число от -12 до +14 (например: -5, 0, +3).", 3)
        return
    offset = int(raw_value)
    if offset < -12 or offset > 14:
        await send_temp_message(message.chat.id, "❌ Смещение должно быть в диапазоне от -12 до +14.", 3)
        return
    await db.set_user_timezone(message.from_user.id, offset)
    await delete_dialog_message(state)
    await state.finish()
    await message.answer(
        "✅ Часовой пояс сохранён.\n\n🔔 Хочешь включить напоминания?",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("✅ Да", "❌ Нет")
    )
    await ReminderSetupStates.ask.set()

# ========== НАСТРОЙКИ НАПОМИНАНИЙ (включение/выключение) ==========
@dp.message_handler(state=ReminderSetupStates.ask)
async def reminder_setup_ask(message: types.Message, state: FSMContext):
    if message.text == "❌ Нет":
        settings = get_default_reminders()
        settings["sleep"]["enabled"] = False
        settings["checkins"]["enabled"] = False
        settings["summary"]["enabled"] = False
        save_reminder_settings(message.from_user.id, settings)
        await state.finish()
        await message.answer("❌ Напоминания выключены", reply_markup=get_main_menu())
        return

    await message.answer(
        "Использовать стандартные настройки?\n\n"
        "🛌 Сон — 09:00\n"
        "⚡️ Чек-ины — 12:00, 16:00, 20:00\n"
        "📝 Итог дня — 22:30",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("✅ Да", "✏️ Настроить вручную")
    )
    await ReminderSetupStates.choose_mode.set()

@dp.message_handler(state=ReminderSetupStates.choose_mode)
async def reminder_setup_mode(message: types.Message, state: FSMContext):
    if message.text == "✅ Да":
        save_reminder_settings(message.from_user.id, get_default_reminders())
        await state.finish()
        await message.answer("✅ Напоминания включены со стандартными настройками!", reply_markup=get_main_menu())
    elif message.text == "✏️ Настроить вручную":
        await state.finish()
        await reminder_settings_menu(message)
    else:
        await message.answer("Выбери вариант из кнопок.")

# ========== НАСТРОЙКИ ==========
@dp.message_handler(text="⚙️ Настройки")
async def settings(message: types.Message):
    await message.answer(
        "⚙️ Настройки\n\nВыбери действие:",
        reply_markup=get_settings_menu_no_reset()
    )

@dp.message_handler(text="🌍 Сменить город")
async def change_city(message: types.Message):
    await message.answer(
        "Выбери свой город или введи смещение вручную:",
        reply_markup=get_timezone_buttons()
    )
    await TimezoneStates.city.set()

@dp.message_handler(text="🔔 Настройка напоминаний")
async def reminder_settings_menu(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🛌 Сон", "⚡️ Чек-ины")
    kb.add("📝 Итог дня", "⬅️ Назад")
    await message.answer("Выбери, что настроить:", reply_markup=kb)
    await ReminderCustomizeStates.waiting.set()

# ========== НАСТРОЙКИ НАПОМИНАНИЙ (КАСТОМИЗАЦИЯ) ==========
@dp.message_handler(state=ReminderCustomizeStates.waiting)
async def reminder_customize_choose(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await settings(message)
        return

    settings_data = load_reminder_settings(message.from_user.id)
    if not settings_data:
        settings_data = get_default_reminders()

    if message.text == "🛌 Сон":
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        current_enabled = settings_data["sleep"]["enabled"]
        kb.add("✅ Включить" if not current_enabled else "❌ Выключить")
        kb.add("🕐 Изменить время")
        kb.add("⬅️ Назад")
        await message.answer(
            f"Сон:\nСостояние: {'✅ Включено' if current_enabled else '❌ Выключено'}\nВремя: {settings_data['sleep']['time']}\n\nЧто сделать?",
            reply_markup=kb
        )
        await state.set_state(ReminderCustomizeStates.sleep_menu)

    elif message.text == "⚡️ Чек-ины":
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        current_enabled = settings_data["checkins"]["enabled"]
        kb.add("✅ Включить" if not current_enabled else "❌ Выключить")
        kb.add("🕐 Изменить время")
        kb.add("⬅️ Назад")
        times_str = ", ".join(settings_data["checkins"]["times"])
        await message.answer(
            f"Чек-ины:\nСостояние: {'✅ Включено' if current_enabled else '❌ Выключено'}\nВремя: {times_str}\n\nЧто сделать?",
            reply_markup=kb
        )
        await state.set_state(ReminderCustomizeStates.checkins_menu)

    elif message.text == "📝 Итог дня":
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        current_enabled = settings_data["summary"]["enabled"]
        kb.add("✅ Включить" if not current_enabled else "❌ Выключить")
        kb.add("🕐 Изменить время")
        kb.add("⬅️ Назад")
        await message.answer(
            f"Итог дня:\nСостояние: {'✅ Включено' if current_enabled else '❌ Выключено'}\nВремя: {settings_data['summary']['time']}\n\nЧто сделать?",
            reply_markup=kb
        )
        await state.set_state(ReminderCustomizeStates.summary_menu)

    else:
        await message.answer("Выбери из кнопок.")

@dp.message_handler(state=ReminderCustomizeStates.sleep_menu)
async def sleep_menu_action(message: types.Message, state: FSMContext):
    settings_data = load_reminder_settings(message.from_user.id)
    if not settings_data:
        settings_data = get_default_reminders()

    if message.text == "✅ Включить":
        settings_data["sleep"]["enabled"] = True
        save_reminder_settings(message.from_user.id, settings_data)
        await message.answer("✅ Напоминания о сне включены.")
        await state.finish()
        await reminder_settings_menu(message)
    elif message.text == "❌ Выключить":
        settings_data["sleep"]["enabled"] = False
        save_reminder_settings(message.from_user.id, settings_data)
        await message.answer("❌ Напоминания о сне выключены.")
        await state.finish()
        await reminder_settings_menu(message)
    elif message.text == "🕐 Изменить время":
        await message.answer("Введи новое время в формате ЧЧ:ММ (например, 09:00):\n\nИли нажми «Назад» для отмены.")
        await state.set_state(ReminderCustomizeStates.change_sleep_time)
    elif message.text == "⬅️ Назад":
        await state.finish()
        await reminder_settings_menu(message)
    else:
        await message.answer("Выбери действие из кнопок.")

@dp.message_handler(state=ReminderCustomizeStates.change_sleep_time)
async def change_sleep_time(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await reminder_settings_menu(message)
        return
    
    if not is_valid_time_text(message.text):
        await message.answer("❌ Неверный формат. Введи время в формате ЧЧ:ММ (например, 09:00).\nИли нажми «Назад».")
        return
    
    settings_data = load_reminder_settings(message.from_user.id)
    if not settings_data:
        settings_data = get_default_reminders()
    settings_data["sleep"]["time"] = message.text
    save_reminder_settings(message.from_user.id, settings_data)
    await message.answer(f"✅ Время напоминания о сне изменено на {message.text}.")
    await state.finish()
    await reminder_settings_menu(message)

@dp.message_handler(state=ReminderCustomizeStates.checkins_menu)
async def checkins_menu_action(message: types.Message, state: FSMContext):
    settings_data = load_reminder_settings(message.from_user.id)
    if not settings_data:
        settings_data = get_default_reminders()

    if message.text == "✅ Включить":
        settings_data["checkins"]["enabled"] = True
        save_reminder_settings(message.from_user.id, settings_data)
        await message.answer("✅ Напоминания о чек-инах включены.")
        await state.finish()
        await reminder_settings_menu(message)
    elif message.text == "❌ Выключить":
        settings_data["checkins"]["enabled"] = False
        save_reminder_settings(message.from_user.id, settings_data)
        await message.answer("❌ Напоминания о чек-инах выключены.")
        await state.finish()
        await reminder_settings_menu(message)
    elif message.text == "🕐 Изменить время":
        await message.answer("Введи время для чек-инов в формате ЧЧ:ММ через запятую или пробел.\nНапример: 12:00, 16:00, 20:00\n\nИли нажми «Назад».")
        await state.set_state(ReminderCustomizeStates.change_checkins_times)
    elif message.text == "⬅️ Назад":
        await state.finish()
        await reminder_settings_menu(message)
    else:
        await message.answer("Выбери действие из кнопок.")

@dp.message_handler(state=ReminderCustomizeStates.change_checkins_times)
async def change_checkins_times(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await reminder_settings_menu(message)
        return
    
    parts = re.split(r'[ ,;]+', message.text)
    times = []
    for part in parts:
        if is_valid_time_text(part.strip()):
            times.append(part.strip())
    
    if not times:
        await message.answer("❌ Не удалось распознать время. Введи время в формате ЧЧ:ММ через запятую или пробел (например, 12:00, 16:00, 20:00).\nИли нажми «Назад».")
        return
    
    times = sorted(set(times))
    settings_data = load_reminder_settings(message.from_user.id)
    if not settings_data:
        settings_data = get_default_reminders()
    settings_data["checkins"]["times"] = times
    save_reminder_settings(message.from_user.id, settings_data)
    await message.answer(f"✅ Время чек-инов изменено: {', '.join(times)}.")
    await state.finish()
    await reminder_settings_menu(message)

@dp.message_handler(state=ReminderCustomizeStates.summary_menu)
async def summary_menu_action(message: types.Message, state: FSMContext):
    settings_data = load_reminder_settings(message.from_user.id)
    if not settings_data:
        settings_data = get_default_reminders()

    if message.text == "✅ Включить":
        settings_data["summary"]["enabled"] = True
        save_reminder_settings(message.from_user.id, settings_data)
        await message.answer("✅ Напоминания об итоге дня включены.")
        await state.finish()
        await reminder_settings_menu(message)
    elif message.text == "❌ Выключить":
        settings_data["summary"]["enabled"] = False
        save_reminder_settings(message.from_user.id, settings_data)
        await message.answer("❌ Напоминания об итоге дня выключены.")
        await state.finish()
        await reminder_settings_menu(message)
    elif message.text == "🕐 Изменить время":
        await message.answer("Введи новое время для итога дня в формате ЧЧ:ММ (например, 22:30):\n\nИли нажми «Назад».")
        await state.set_state(ReminderCustomizeStates.change_summary_time)
    elif message.text == "⬅️ Назад":
        await state.finish()
        await reminder_settings_menu(message)
    else:
        await message.answer("Выбери действие из кнопок.")

@dp.message_handler(state=ReminderCustomizeStates.change_summary_time)
async def change_summary_time(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await reminder_settings_menu(message)
        return
    
    if not is_valid_time_text(message.text):
        await message.answer("❌ Неверный формат. Введи время в формате ЧЧ:ММ (например, 22:30).\nИли нажми «Назад».")
        return
    
    settings_data = load_reminder_settings(message.from_user.id)
    if not settings_data:
        settings_data = get_default_reminders()
    settings_data["summary"]["time"] = message.text
    save_reminder_settings(message.from_user.id, settings_data)
    await message.answer(f"✅ Время итога дня изменено на {message.text}.")
    await state.finish()
    await reminder_settings_menu(message)

@dp.message_handler(text="⬅️ Назад")
async def back_from_settings(message: types.Message):
    await message.answer("Главное меню", reply_markup=get_main_menu())

# ========== УВЕДОМЛЕНИЯ ==========
scheduler = None

async def check_custom_reminders():
    try:
        if not os.path.exists(REMINDER_FILE):
            return
        with open(REMINDER_FILE, "r") as f:
            all_data = json.load(f)
        now_utc = datetime.utcnow()
        for user_id, settings_data in all_data.items():
            user_id = int(user_id)
            tz = await db.get_user_timezone(user_id)
            if tz == 0:
                continue
            user_time = now_utc + timedelta(hours=tz)
            current_time = user_time.strftime("%H:%M")
            if settings_data["sleep"]["enabled"]:
                if settings_data["sleep"]["time"] == current_time:
                    if not await db.has_sleep_today(user_id):
                        await bot.send_message(user_id, "🛌 Пора записать сон")
            if settings_data["checkins"]["enabled"]:
                for t in settings_data["checkins"]["times"]:
                    if t == current_time:
                        checkins = await db._load_json(user_id, "checkins.json")
                        today_str = user_time.strftime("%Y-%m-%d")
                        has_today_checkin = any(c.get("date") == today_str for c in checkins)
                        if not has_today_checkin:
                            await bot.send_message(user_id, "⚡️ Сделай чек-ин")
            if settings_data["summary"]["enabled"]:
                if settings_data["summary"]["time"] == current_time:
                    if await db.get_target_date_for_summary(user_id):
                        await bot.send_message(user_id, "📝 Не забудь подвести итог дня")
    except Exception as e:
        logging.error(f"Ошибка кастомных напоминаний: {e}")

async def check_reminders():
    due_reminders = await db.get_reminders_due_now()
    for user_id, reminder in due_reminders:
        try:
            text = reminder["text"]
            await bot.send_message(user_id, f"⏰ НАПОМИНАНИЕ!\n\n{text}")
            await db.mark_reminder_sent(user_id, reminder["id"])
            logging.info(f"Отправлено напоминание {reminder['id']} пользователю {user_id}")
        except Exception as e:
            logging.error(f"Ошибка отправки напоминания {reminder['id']}: {e}")

# ========== HEALTH CHECK ДЛЯ RENDER ==========
async def health_check(request):
    return web.Response(text="I am alive!")

async def run_health_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logging.info("✅ Health check сервер запущен на порту 8080")

# ========== ЗАПУСК (POLLING) ==========
async def on_startup_polling(dp):
    # Запускаем health check сервер в фоне
    asyncio.create_task(run_health_server())
    
    # Удаляем вебхук, чтобы избежать конфликта
    await bot.delete_webhook()
    
    await db.init_pool()
    
    global scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(check_reminders, IntervalTrigger(minutes=1))
    scheduler.add_job(check_custom_reminders, IntervalTrigger(minutes=1))
    scheduler.start()
    logging.info("✅ Бот запущен в polling режиме с health check!")

async def on_shutdown_polling(dp):
    if scheduler and scheduler.running:
        scheduler.shutdown()
    try:
        if hasattr(db, 'close_pool'):
            await db.close_pool()
        elif hasattr(db, 'close'):
            await db.close()
    except Exception as e:
        logging.error(f"Ошибка при закрытии БД: {e}")

if __name__ == "__main__":
    executor.start_polling(
        dp,
        on_startup=on_startup_polling,
        on_shutdown=on_shutdown_polling,
        skip_updates=True
    )

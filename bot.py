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
from database import db
from keyboards import *
from states import *
from ai_advisor import AIAdvisor

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

# ========== КОМАНДЫ ==========
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
    if db.get_user_timezone(user_id) == 0:
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
        db.set_user_timezone(message.from_user.id, CITY_TO_OFFSET[message.text])
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
    db.set_user_timezone(message.from_user.id, offset)
    await delete_dialog_message(state)
    await state.finish()
    await message.answer(
        "✅ Часовой пояс сохранён.\n\n🔔 Хочешь включить напоминания?",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("✅ Да", "❌ Нет")
    )
    await ReminderSetupStates.ask.set()

# ========== СОН ==========
@dp.message_handler(text="🛌 Сон")
async def sleep_start(message: types.Message, state: FSMContext):
    if db.has_sleep_today(message.from_user.id):
        await send_temp_message(message.chat.id, "🛌 Сон за сегодня уже записан.", 3)
        return
    await SleepStates.bed_time.set()
    await edit_or_send(state, message.chat.id, "Во сколько лёг спать?", get_time_buttons(), edit=False)

@dp.message_handler(state=SleepStates.bed_time)
async def sleep_bed_time(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    if message.text == "Другое":
        await send_temp_message(message.chat.id, "Введи время в формате ЧЧ:ММ, например 23:45", 3)
        return
    if not is_valid_time_text(message.text):
        await send_temp_message(message.chat.id, "❌ Укажи время в формате ЧЧ:ММ", 3)
        return
    await state.update_data(bed_time=message.text)
    await SleepStates.wake_time.set()
    await edit_or_send(state, message.chat.id, "Во сколько проснулся?", get_morning_time_buttons(), edit=True)

@dp.message_handler(state=SleepStates.wake_time)
async def sleep_wake_time(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    if message.text == "Другое":
        await send_temp_message(message.chat.id, "Введи время в формате ЧЧ:ММ, например 07:30", 3)
        return
    if not is_valid_time_text(message.text):
        await send_temp_message(message.chat.id, "❌ Укажи время в формате ЧЧ:ММ", 3)
        return
    await state.update_data(wake_time=message.text)
    await SleepStates.quality.set()
    await edit_or_send(state, message.chat.id, "Оцени качество сна (1–10):", get_energy_stress_buttons(), edit=True)

@dp.message_handler(state=SleepStates.quality)
async def sleep_quality(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    if not is_valid_score_text(message.text):
        await send_temp_message(message.chat.id, "❌ Оценка должна быть от 1 до 10", 3)
        return
    await state.update_data(quality=int(message.text))
    await SleepStates.woke_night.set()
    await edit_or_send(state, message.chat.id, "Просыпался ночью?", get_yes_no_buttons(), edit=True)

@dp.message_handler(state=SleepStates.woke_night)
async def sleep_woke_night(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    if message.text not in ("✅ Да", "❌ Нет"):
        await send_temp_message(message.chat.id, "❌ Выбери ответ кнопками", 3)
        return
    await state.update_data(woke_night=(message.text == "✅ Да"))
    await SleepStates.note.set()
    await edit_or_send(state, message.chat.id, "Заметка по сну? (можно пропустить)", get_skip_markup_text(), edit=True)

@dp.message_handler(state=SleepStates.note)
async def sleep_note(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    data = await state.get_data()
    note = "" if message.text == "Пропустить" else message.text
    saved = db.add_sleep(
        message.from_user.id,
        data.get("bed_time"),
        data.get("wake_time"),
        data.get("quality"),
        data.get("woke_night"),
        note
    )
    await delete_dialog_message(state)
    await state.finish()
    if saved:
        await send_temp_message(message.chat.id, "✅ Сон сохранён!", 2)
    else:
        await send_temp_message(message.chat.id, "🛌 Сон за сегодня уже записан.", 3)
    await message.answer("Главное меню", reply_markup=get_main_menu())

# ========== ЧЕК-ИН ==========
@dp.message_handler(text="⚡️ Чек-ин")
async def checkin_start(message: types.Message, state: FSMContext):
    await CheckinStates.energy.set()
    await edit_or_send(state, message.chat.id, "Оцени уровень энергии (1–10):", get_energy_stress_buttons(), edit=False)

@dp.message_handler(state=CheckinStates.energy)
async def checkin_energy(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    if not is_valid_score_text(message.text):
        await send_temp_message(message.chat.id, "❌ Оценка должна быть от 1 до 10", 3)
        return
    await state.update_data(energy=int(message.text))
    await CheckinStates.stress.set()
    await edit_or_send(state, message.chat.id, "Оцени уровень стресса (1–10):", get_energy_stress_buttons(), edit=True)

@dp.message_handler(state=CheckinStates.stress)
async def checkin_stress(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    if not is_valid_score_text(message.text):
        await send_temp_message(message.chat.id, "❌ Оценка должна быть от 1 до 10", 3)
        return
    await state.update_data(stress=int(message.text), emotions=[])
    await CheckinStates.emotions.set()
    await edit_or_send(state, message.chat.id, "Выбери эмоции (можно несколько), затем нажми «✅ Готово»", get_emotion_buttons(), edit=True)

@dp.message_handler(state=CheckinStates.emotions)
async def checkin_emotions(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await safe_finish(state, message)
        return
    data = await state.get_data()
    emotions = data.get("emotions", [])
    if message.text == "⬅️ Назад":
        await CheckinStates.stress.set()
        await edit_or_send(state, message.chat.id, "Оцени уровень стресса (1–10):", get_energy_stress_buttons(), edit=True)
        return
    if message.text == "✍️ Своя":
        await send_temp_message(message.chat.id, "Напиши свою эмоцию текстом, затем нажми «✅ Готово».", 4)
        return
    if message.text == "✅ Готово":
        await CheckinStates.note.set()
        await edit_or_send(state, message.chat.id, "Короткая заметка? (можно пропустить)", get_skip_markup_text(), edit=True)
        return
    if message.text not in emotions:
        emotions.append(message.text)
        await state.update_data(emotions=emotions)
    await send_temp_message(message.chat.id, f"Добавлено эмоций: {len(emotions)}", 2)

@dp.message_handler(state=CheckinStates.note)
async def checkin_note(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    data = await state.get_data()
    note = "" if message.text == "Пропустить" else message.text
    db.add_checkin(
        message.from_user.id,
        "manual",
        data.get("energy"),
        data.get("stress"),
        data.get("emotions", []),
        note
    )
    await delete_dialog_message(state)
    await state.finish()
    await send_temp_message(message.chat.id, "✅ Чек-ин сохранён!", 2)
    await message.answer("Главное меню", reply_markup=get_main_menu())

# ========== ИТОГ ДНЯ ==========
@dp.message_handler(text="📝 Итог дня")
async def day_summary_start(message: types.Message, state: FSMContext):
    target_date = db.get_target_date_for_summary(message.from_user.id)
    if target_date is None:
        await send_temp_message(message.chat.id, "🕕 Итог дня доступен с 18:00 до 06:00 по твоему часовому поясу.", 4)
        return
    if db.has_day_summary_for_date(message.from_user.id, target_date):
        await send_temp_message(message.chat.id, f"📝 Итог за {target_date} уже сохранён.", 4)
        return
    await DaySummaryStates.score.set()
    await edit_or_send(state, message.chat.id, "Как прошёл день? Оценка от 1 до 10:", get_energy_stress_buttons(), edit=False)

@dp.message_handler(state=DaySummaryStates.score)
async def summary_score(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    if not is_valid_score_text(message.text):
        await send_temp_message(message.chat.id, "❌ Оценка должна быть от 1 до 10", 3)
        return
    await state.update_data(score=int(message.text))
    await DaySummaryStates.best.set()
    await edit_or_send(state, message.chat.id, "Что было лучшим за день?", get_skip_markup_text(), edit=True)

@dp.message_handler(state=DaySummaryStates.best)
async def summary_best(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    best = message.text if message.text != "Пропустить" else ""
    await state.update_data(best=best)
    await DaySummaryStates.worst.set()
    await edit_or_send(state, message.chat.id, "Что было самым сложным?", get_skip_markup_text(), edit=True)

@dp.message_handler(state=DaySummaryStates.worst)
async def summary_worst(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    worst = message.text if message.text != "Пропустить" else ""
    await state.update_data(worst=worst)
    await DaySummaryStates.gratitude.set()
    await edit_or_send(state, message.chat.id, "За что благодарен?", get_skip_markup_text(), edit=True)

@dp.message_handler(state=DaySummaryStates.gratitude)
async def summary_gratitude(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    gratitude = message.text if message.text != "Пропустить" else ""
    await state.update_data(gratitude=gratitude)
    await DaySummaryStates.note.set()
    await edit_or_send(state, message.chat.id, "Заметка? (можно пропустить)", get_skip_markup_text(), edit=True)

@dp.message_handler(state=DaySummaryStates.note)
async def summary_note(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    data = await state.get_data()
    note = "" if message.text == "Пропустить" else message.text
    success = db.add_day_summary(
        message.from_user.id,
        data["score"],
        data["best"],
        data["worst"],
        data["gratitude"],
        note
    )
    await delete_dialog_message(state)
    await state.finish()
    if success:
        await send_temp_message(message.chat.id, "✅ Итог дня сохранён!", 2)
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
        await safe_finish(state, message)
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
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    await state.update_data(meal_type=message.text)
    await FoodStates.next()
    await edit_or_send(state, message.chat.id, "Что съел?", get_back_button(), edit=True)

@dp.message_handler(state=FoodStates.food_text)
async def food_text(message: types.Message, state: FSMContext):
    if message.text in ("⬅️ Назад", "❌ Отмена"):
        await safe_finish(state, message, "Добавление отменено")
        return
    data = await state.get_data()
    db.add_food(message.from_user.id, data["meal_type"], message.text)
    await delete_dialog_message(state)
    await state.finish()
    await send_temp_message(message.chat.id, f"✅ Добавлено: {data['meal_type']} — {message.text}", 2)
    await message.answer("Главное меню", reply_markup=get_main_menu())

@dp.message_handler(state=DrinkStates.drink_type)
async def drink_type(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    await state.update_data(drink_type=message.text)
    await DrinkStates.amount.set()
    await edit_or_send(state, message.chat.id, "Сколько?", get_drink_amount_buttons(), edit=True)

@dp.message_handler(state=DrinkStates.amount)
async def drink_amount(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return
    if message.text == "Другое":
        await state.update_data(awaiting_custom_drink_amount=True)
        await edit_or_send(state, message.chat.id, "Введи количество (например: 0.5 л, 2 стакана):", get_back_button(), edit=True)
        return
    data = await state.get_data()
    if data.get("awaiting_custom_drink_amount"):
        if not message.text.strip():
            await edit_or_send(state, message.chat.id, "❌ Введи количество напитка текстом.", get_back_button(), edit=True)
            return
        await state.update_data(awaiting_custom_drink_amount=False)
    drink_type = data["drink_type"]
    amount = message.text
    db.add_drink(message.from_user.id, drink_type, amount)
    await delete_dialog_message(state)
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

# ========== СОЗДАНИЕ ЗАМЕТКИ ==========
@dp.message_handler(text="📝 Заметка")
async def create_note_start(message: types.Message, state: FSMContext):
    await NoteStates.text.set()
    await edit_or_send(state, message.chat.id, "📝 Введи текст заметки:", get_back_button(), edit=False)

@dp.message_handler(state=NoteStates.text)
async def create_note_text(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await safe_finish(state, message)
        await notes_reminders_main(message)
        return
    db.add_note(message.from_user.id, message.text)
    await delete_dialog_message(state)
    await state.finish()
    await send_temp_message(message.chat.id, "✅ Заметка сохранена!", 2)
    await message.answer("Главное меню", reply_markup=get_main_menu())

# ========== СОЗДАНИЕ НАПОМИНАНИЯ ==========
@dp.message_handler(text="⏰ Напоминание")
async def create_reminder_start(message: types.Message, state: FSMContext):
    await ReminderStates.text.set()
    await edit_or_send(state, message.chat.id, "📝 Введи название напоминания:", get_back_button(), edit=False)

@dp.message_handler(state=ReminderStates.text)
async def reminder_text(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await safe_finish(state, message)
        await notes_reminders_main(message)
        return
    await state.update_data(text=message.text)
    await ReminderStates.date.set()
    await edit_or_send(state, message.chat.id, "📅 Выбери дату:", get_reminder_date_buttons(), edit=True)

@dp.message_handler(state=ReminderStates.date)
async def reminder_date(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await safe_finish(state, message)
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
        await safe_finish(state, message)
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
        await safe_finish(state, message)
        await notes_reminders_main(message)
        return
    if message.text == "⬅️ Назад":
        await ReminderStates.hour.set()
        await edit_or_send(state, message.chat.id, "🕐 Выбери час:", get_reminder_hour_buttons(), edit=True)
        return
    if message.text not in ["00", "15", "30", "45"]:
        await edit_or_send(state, message.chat.id, "❌ Выбери минуты из кнопок: 00, 15, 30, 45", get_reminder_minute_buttons(), edit=True)
        return

    data = await state.get_data()
    text = data["text"]
    target_date = data["date"]
    time_str = f"{data['hour']:02d}:{message.text}"

    try:
        target_dt = datetime.strptime(f"{target_date} {time_str}", "%Y-%m-%d %H:%M")
    except:
        await edit_or_send(state, message.chat.id, "❌ Ошибка в дате/времени. Попробуй снова.", get_notes_reminders_main_menu(), edit=False)
        await state.finish()
        return
    now = datetime.now()
    if target_dt < now + MIN_DELTA:
        await edit_or_send(state, message.chat.id, f"❌ Нельзя установить напоминание раньше, чем через {int(MIN_DELTA.total_seconds()//60)} минут.", get_reminder_minute_buttons(), edit=True)
        return

    await state.update_data(minute=message.text)
    await ReminderStates.advance.set()
    await edit_or_send(state, message.chat.id, "⏰ Нужно ли напомнить заранее?", get_reminder_advance_buttons(), edit=True)

@dp.message_handler(state=ReminderStates.advance)
async def reminder_advance(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await safe_finish(state, message)
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
        "🚫 Не надо": None,
        "✏️ Своё время": "custom"
    }
    if message.text not in advance_map:
        await edit_or_send(state, message.chat.id, "❌ Выбери вариант из кнопок.", get_reminder_advance_buttons(), edit=True)
        return
    advance_type = advance_map.get(message.text)

    if advance_type == "custom":
        await ReminderStates.custom_time.set()
        await edit_or_send(state, message.chat.id, "✏️ Введи время в формате ЧЧ:ММ (например, 10:30).\n\nДоп. напоминание сработает в этот час в день основного.", get_back_button(), edit=True)
        return

    data = await state.get_data()
    text = data["text"]
    target_date = data["date"]
    time_str = f"{data['hour']:02d}:{data['minute']}"

    try:
        main_dt = datetime.strptime(f"{target_date} {time_str}", "%Y-%m-%d %H:%M")
    except:
        await edit_or_send(state, message.chat.id, "❌ Ошибка в дате/времени.", get_notes_reminders_main_menu(), edit=False)
        await state.finish()
        return
    now = datetime.now()
    if main_dt < now + MIN_DELTA:
        await delete_dialog_message(state)
        await state.finish()
        await send_temp_message(message.chat.id, "❌ Нельзя создать напоминание на прошедшее или слишком близкое время.", 3)
        await message.answer("Главное меню", reply_markup=get_main_menu())
        return

    if advance_type:
        if advance_type == "day":
            adv_dt = main_dt - timedelta(days=1)
        elif advance_type == "3h":
            adv_dt = main_dt - timedelta(hours=3)
        elif advance_type == "1h":
            adv_dt = main_dt - timedelta(hours=1)
        else:
            adv_dt = None
        if adv_dt and adv_dt < now + MIN_DELTA:
            await edit_or_send(state, message.chat.id, "❌ Выбранное доп.напоминание попадает в прошлое или слишком близко — выбери другой вариант.", get_reminder_advance_buttons(), edit=True)
            return

    reminder_id = db.add_reminder(message.from_user.id, text, target_date, time_str, advance_type)
    await delete_dialog_message(state)
    await state.finish()
    if reminder_id is None:
        await send_temp_message(message.chat.id, "❌ Нельзя создать напоминание на прошедшее время.", 3)
    else:
        await send_temp_message(message.chat.id, f"✅ Напоминание добавлено!\n\n📝 {text}\n🕐 {target_date} {time_str}", 4)
    await message.answer("Главное меню", reply_markup=get_main_menu())

@dp.message_handler(state=ReminderStates.custom_time)
async def reminder_custom_time(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await ReminderStates.advance.set()
        await edit_or_send(state, message.chat.id, "⏰ Нужно ли напомнить заранее?", get_reminder_advance_buttons(), edit=True)
        return
    if message.text == "❌ Отмена":
        await safe_finish(state, message)
        await notes_reminders_main(message)
        return

    time_pattern = r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$'
    if not re.match(time_pattern, message.text):
        await send_temp_message(message.chat.id, "❌ Неверный формат. Введи время в формате ЧЧ:ММ (например, 10:30).", 3)
        await edit_or_send(state, message.chat.id, "✏️ Введи время в формате ЧЧ:ММ:", get_back_button(), edit=True)
        return

    data = await state.get_data()
    target_date = data['date']
    custom_time = message.text
    try:
        custom_dt = datetime.strptime(f"{target_date} {custom_time}", "%Y-%m-%d %H:%M")
    except:
        await send_temp_message(message.chat.id, "❌ Ошибка даты/времени.", 3)
        await ReminderStates.advance.set()
        await edit_or_send(state, message.chat.id, "⏰ Выбери вариант доп. напоминания:", get_reminder_advance_buttons(), edit=True)
        return

    now = datetime.now()
    if custom_dt < now + MIN_DELTA:
        await send_temp_message(message.chat.id, f"❌ Доп. напоминание не может быть раньше, чем через {int(MIN_DELTA.total_seconds()//60)} минут от текущего момента.", 3)
        await edit_or_send(state, message.chat.id, "✏️ Введи другое время:", get_back_button(), edit=True)
        return

    await state.update_data(custom_time=custom_time)

    text = data['text']
    target_date_str = data['date']
    time_str = f"{data['hour']:02d}:{data['minute']}"
    main_id = db.add_reminder(message.from_user.id, text, target_date_str, time_str, advance_type=None)

    if not main_id:
        await send_temp_message(message.chat.id, "❌ Не удалось создать напоминание.", 3)
        await safe_finish(state, message)
        return

    adv_text = f"🔔 Напоминание: {text}"
    db.add_reminder(message.from_user.id, adv_text, target_date_str, custom_time, advance_type=None, parent_id=main_id, is_custom=True)

    await delete_dialog_message(state)
    await state.finish()
    await send_temp_message(message.chat.id, f"✅ Напоминание добавлено!\n\n📝 {text}\n🕐 {target_date_str} {time_str}\n🔔 Доп. напоминание: {target_date_str} {custom_time}", 4)
    await message.answer("Главное меню", reply_markup=get_main_menu())

# ========== ПРОСМОТР ЗАПИСЕЙ ==========
@dp.message_handler(text="📋 Мои записи")
async def view_records(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Что хочешь посмотреть?", reply_markup=get_view_type_buttons())

# ========== ЗАМЕТКИ ==========
@dp.message_handler(text="📋 Заметки")
async def list_notes(message: types.Message, state: FSMContext):
    await state.finish()
    notes = db.get_notes(message.from_user.id)
    if not notes:
        await message.answer("📋 У тебя пока нет заметок.", reply_markup=get_notes_reminders_main_menu())
        return
    await state.update_data(last_section='notes')
    visible = list(reversed(notes))
    text = "📋 *Твои заметки:*\n\n"
    for i, note in enumerate(visible, 1):
        note_text = note['text'][:60] + "..." if len(note['text']) > 60 else note['text']
        text += f"{i}. {note_text}\n   📅 {note.get('date','-')} {note.get('time','')}\n\n"
    text += "\n✏️ *Команды:*\n`копировать 3` — скопировать текст заметки\n`редактировать 2` — изменить заметку\n`удалить 1` — удалить заметку"
    await message.answer(text, parse_mode="Markdown", reply_markup=get_notes_reminders_main_menu())

# ========== НАПОМИНАНИЯ ==========
@dp.message_handler(text="⏰ Напоминания")
async def list_reminders(message: types.Message, state: FSMContext):
    await state.finish()
    reminders = db.get_active_reminders(message.from_user.id)
    if not reminders:
        await message.answer("📋 У тебя пока нет активных напоминаний.", reply_markup=get_notes_reminders_main_menu())
        return
    await state.update_data(last_section='reminders')
    main_reminders = [r for r in reminders if not r.get('parent_id')]
    text = "📋 *Твои основные напоминания:*\n\n"
    for i, r in enumerate(main_reminders, 1):
        text += f"{i}. ⏰ {r['date']} {r['time']} — {r['text'][:50]}\n"
    text += "\n🗑 *Команды:*\n`редактировать 2` — изменить напоминание\n`удалить 1` — удалить напоминание (вместе с доп.)"
    await message.answer(text, parse_mode="Markdown", reply_markup=get_notes_reminders_main_menu())

# ========== ОБРАБОТЧИКИ КОМАНД ДЛЯ ЗАМЕТОК И НАПОМИНАНИЙ ==========
@dp.message_handler(regexp=r'^копировать (\d+)$', state='*')
async def copy_note(message: types.Message, state: FSMContext):
    data = await state.get_data()
    last_section = data.get('last_section')
    if last_section != 'notes':
        await send_temp_message(message.chat.id, "❌ Сначала открой список заметок.", 3)
        return
    match = re.match(r'^копировать (\d+)$', message.text)
    if not match:
        return
    index = int(match.group(1))
    notes = db.get_notes(message.from_user.id)
    if not notes:
        await send_temp_message(message.chat.id, "❌ Заметок нет.", 3)
        return
    visible = list(reversed(notes))
    if index < 1 or index > len(visible):
        await send_temp_message(message.chat.id, f"❌ Неверный номер. Доступно заметок: {len(visible)}", 3)
        return
    note = visible[index-1]
    await bot.send_message(message.from_user.id, f"📋 *Скопированная заметка:*\n\n{note['text']}", parse_mode="Markdown")
    await send_temp_message(message.chat.id, "✅ Заметка скопирована и отправлена тебе в чат!", 3)

@dp.message_handler(regexp=r'^редактировать (\d+)$', state='*')
async def edit_note_or_reminder(message: types.Message, state: FSMContext):
    data = await state.get_data()
    last_section = data.get('last_section')
    if not last_section:
        await send_temp_message(message.chat.id, "❌ Сначала открой список заметок или напоминаний.", 3)
        return
    match = re.match(r'^редактировать (\d+)$', message.text)
    if not match:
        return
    index = int(match.group(1))

    if last_section == 'notes':
        notes = db.get_notes(message.from_user.id)
        if not notes:
            await send_temp_message(message.chat.id, "❌ Заметок нет.", 3)
            return
        visible = list(reversed(notes))
        if index < 1 or index > len(visible):
            await send_temp_message(message.chat.id, f"❌ Неверный номер. Доступно заметок: {len(visible)}", 3)
            return
        note = visible[index-1]
        db.delete_note_by_id(message.from_user.id, note['id'])
        await NoteStates.text.set()
        await state.update_data(edit_note_text=note['text'])
        await edit_or_send(state, message.chat.id, f"✏️ *Редактирование заметки*\n\nТекущий текст:\n{note['text']}\n\nВведи новый текст заметки (или оставь как есть):", get_back_button(), edit=False)

    elif last_section == 'reminders':
        reminders = db.get_active_reminders(message.from_user.id)
        if not reminders:
            await send_temp_message(message.chat.id, "❌ Напоминаний нет.", 3)
            return
        main_reminders = [r for r in reminders if not r.get('parent_id')]
        if index < 1 or index > len(main_reminders):
            await send_temp_message(message.chat.id, f"❌ Неверный номер. Доступно основных напоминаний: {len(main_reminders)}", 3)
            return
        reminder = main_reminders[index-1]
        await state.update_data(edit_reminder_data=reminder)
        db.delete_reminder(message.from_user.id, reminder['id'])
        await ReminderStates.text.set()
        await state.update_data(edit_reminder_text=reminder['text'])
        await edit_or_send(state, message.chat.id, f"✏️ *Редактирование напоминания*\n\nТекущий текст:\n{reminder['text']}\n\nВведи новый текст (или оставь как есть):", get_back_button(), edit=False)
    else:
        await send_temp_message(message.chat.id, "❌ Неизвестный раздел.", 3)

@dp.message_handler(regexp=r'^удалить (\d+)$', state='*')
async def delete_item(message: types.Message, state: FSMContext):
    data = await state.get_data()
    last_section = data.get('last_section')
    if not last_section:
        await send_temp_message(message.chat.id, "❌ Сначала открой список заметок или напоминаний.", 3)
        return
    match = re.match(r'^удалить (\d+)$', message.text)
    if not match:
        return
    index = int(match.group(1))

    if last_section == 'notes':
        notes = db.get_notes(message.from_user.id)
        if not notes:
            await send_temp_message(message.chat.id, "❌ Заметок нет.", 3)
            return
        visible = list(reversed(notes))
        if index < 1 or index > len(visible):
            await send_temp_message(message.chat.id, f"❌ Неверный номер. Доступно заметок: {len(visible)}", 3)
            return
        note = visible[index-1]
        db.delete_note_by_id(message.from_user.id, note['id'])
        await send_temp_message(message.chat.id, f"✅ Заметка {index} удалена.", 3)

    elif last_section == 'reminders':
        reminders = db.get_active_reminders(message.from_user.id)
        if not reminders:
            await send_temp_message(message.chat.id, "❌ Напоминаний нет.", 3)
            return
        main_reminders = [r for r in reminders if not r.get('parent_id')]
        if index < 1 or index > len(main_reminders):
            await send_temp_message(message.chat.id, f"❌ Неверный номер. Доступно основных напоминаний: {len(main_reminders)}", 3)
            return
        reminder = main_reminders[index-1]
        db.delete_reminder(message.from_user.id, reminder['id'])
        await send_temp_message(message.chat.id, f"✅ Напоминание {index} и связанные с ним удалены.", 3)
    else:
        await send_temp_message(message.chat.id, "❌ Неизвестный раздел.", 3)

# ========== AI СОВЕТ (ДИАЛОГ) ==========
def escape_markdown(text: str) -> str:
    chars = r'_*[]()~`>#+-=|{}.!'
    for ch in chars:
        text = text.replace(ch, '\\' + ch)
    return text

@dp.message_handler(text="🤖 AI-совет")
async def ai_advice_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = {
        "sleep": db._load_json(user_id, "sleep.json"),
        "checkins": db._load_json(user_id, "checkins.json"),
        "day_summary": db._load_json(user_id, "day_summary.json"),
        "notes": db._load_json(user_id, "notes.json"),
        "reminders": db._load_json(user_id, "reminders.json"),
    }
    ai_advisor.set_user_data(user_id, user_data)

    await AIState.waiting_question.set()
    await message.answer("🤖 *Загружаю ваши данные для анализа...*", parse_mode="Markdown")
    advice = await ai_advisor.get_advice(user_id)
    advice = escape_markdown(advice)
    await message.answer(
        f"🤖 *Совет AI:*\n\n{advice}",
        parse_mode="Markdown",
        reply_markup=get_back_button()
    )
    await message.answer(
        "✏️ *Вы можете задать уточняющий вопрос* или написать /cancel для выхода.",
        parse_mode="Markdown"
    )

@dp.message_handler(state=AIState.waiting_question)
async def ai_question(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text == "/cancel":
        await state.finish()
        ai_advisor.clear_user_data(user_id)
        await message.answer("✅ Выход из AI-режима.", reply_markup=get_main_menu())
        return
    if message.text == "⬅️ Назад":
        await state.finish()
        ai_advisor.clear_user_data(user_id)
        await message.answer("✅ Выход из AI-режима.", reply_markup=get_main_menu())
        return

    if not ai_advisor.get_user_data(user_id):
        user_data = {
            "sleep": db._load_json(user_id, "sleep.json"),
            "checkins": db._load_json(user_id, "checkins.json"),
            "day_summary": db._load_json(user_id, "day_summary.json"),
            "notes": db._load_json(user_id, "notes.json"),
            "reminders": db._load_json(user_id, "reminders.json"),
        }
        ai_advisor.set_user_data(user_id, user_data)

    await bot.send_chat_action(message.chat.id, "typing")
    advice = await ai_advisor.get_advice(user_id, message.text)
    advice = escape_markdown(advice)
    await message.answer(
        f"🤖 *Ответ:*\n\n{advice}",
        parse_mode="Markdown",
        reply_markup=get_back_button()
    )

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

@dp.message_handler(text=["🎵 SoundCloud", "📌 Pinterest (видео)", "🌐 Другой URL"])
async def export_any_start(message: types.Message, state: FSMContext):
    await ExportStates.url.set()
    if message.text == "🌐 Другой URL":
        await edit_or_send(state, message.chat.id, "📎 Отправь ссылку на трек или плейлист (YouTube, SoundCloud, VK, Spotify и др.):", get_back_button(), edit=False)
    else:
        await edit_or_send(state, message.chat.id, f"📎 Отправь ссылку на трек или плейлист {message.text}:", get_back_button(), edit=False)

@dp.message_handler(state=ExportStates.url)
async def export_any_url(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await safe_finish(state, message)
        await export_menu(message)
        return
    url = message.text.strip()
    if not is_valid_url(url):
        await send_temp_message(message.chat.id, "❌ Это не похоже на ссылку. Пожалуйста, отправь корректный URL (начинающийся с http:// или https://).", 4)
        await edit_or_send(state, message.chat.id, "📎 Отправь ссылку на трек или плейлист:", get_back_button(), edit=True)
        return
    await state.update_data(url=url)
    await ExportStates.format.set()
    await edit_or_send(state, message.chat.id, "Выбери формат:", reply_markup=get_download_formats_keyboard(source="unknown"), edit=True)

@dp.message_handler(state=ExportStates.format)
async def export_any_format(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await safe_finish(state, message)
        await export_menu(message)
        return
    fmt = message.text
    allowed_formats = {"MP3 (аудио)", "WAV (аудио)", "MP4 (видео)", "Лучшее качество (оригинал)"}
    if fmt not in allowed_formats:
        await send_temp_message(message.chat.id, "❌ Выбери формат только кнопками.", 3)
        await edit_or_send(state, message.chat.id, "Выбери формат:", get_download_formats_keyboard(), edit=True)
        return
    data = await state.get_data()
    url = data.get('url')
    if not url:
        await safe_finish(state, message, "Ошибка: ссылка не найдена. Начни заново.")
        return
    await delete_dialog_message(state)
    await state.finish()

    progress_msg = await message.answer("⏳ Начинаю скачивание...")
    filename = None

    try:
        filename, title = await download_media_with_ytdlp(url, fmt, progress_msg)
        if not filename or not os.path.exists(filename):
            raise Exception("Скачанный файл не найден после завершения загрузки.")

        await bot.edit_message_text("✅ Скачивание завершено! Отправляю файл...", chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
        file_size = os.path.getsize(filename)
        if file_size > 50 * 1024 * 1024:
            raise Exception("Файл слишком большой для отправки в Telegram (более 50 MB).")
        with open(filename, 'rb') as f:
            await message.answer_document(f, caption=f"🎵 {title}")
    except Exception as e:
        logging.error(f"Ошибка загрузки: {e}")
        error_msg = str(e)
        if "Sign in to confirm you’re not a bot" in error_msg:
            await bot.edit_message_text(
                "❌ YouTube временно блокирует запросы. Попробуйте:\n"
                "• Подождать 10–15 минут\n"
                "• Использовать другой источник (SoundCloud, VK)\n"
                "• Скачать позже, когда нагрузка снизится",
                chat_id=progress_msg.chat.id, message_id=progress_msg.message_id
            )
        else:
            await bot.edit_message_text(f"❌ Ошибка: {error_msg[:200]}\nПроверь ссылку и попробуй снова.", chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
        await asyncio.sleep(3)
        await safe_delete_message_obj(progress_msg)
    finally:
        safe_remove_file(filename)
    await message.answer("Главное меню", reply_markup=get_main_menu())

# ========== КОНВЕРТЕР ==========
@dp.message_handler(text="🔄 Конвертер")
async def converter_menu(message: types.Message, state: FSMContext):
    await ConverterStates.file.set()
    m = await message.answer("Отправь мне файл (видео, аудио, изображение), который хочешь конвертировать.", reply_markup=get_back_button())
    await state.update_data(msg_id=m.message_id, chat_id=m.chat.id)

@dp.message_handler(state=ConverterStates.file, content_types=types.ContentTypes.TEXT)
async def converter_file_text(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await safe_finish(state, message)
        return
    await send_temp_message(message.chat.id, "❌ Отправь файл или нажми «Назад».", 3)

@dp.message_handler(content_types=['document', 'video', 'audio'], state=ConverterStates.file)
async def converter_file(message: types.Message, state: FSMContext):
    if not (message.document or message.video or message.audio):
        await send_temp_message(message.chat.id, "❌ Неподдерживаемый тип файла. Пожалуйста, отправь документ, видео или аудио.", 3)
        return
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or f"{message.document.file_unique_id}.bin"
    elif message.video:
        file_id = message.video.file_id
        file_name = f"{message.video.file_unique_id}.mp4"
    elif message.audio:
        file_id = message.audio.file_id
        file_name = f"{message.audio.file_unique_id}.mp3"
    else:
        await send_temp_message(message.chat.id, "❌ Неподдерживаемый тип файла.", 3)
        return

    try:
        file = await bot.get_file(file_id)
        downloaded_file = await bot.download_file(file.file_path)
        input_ext = os.path.splitext(file_name)[1] or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=input_ext, dir="/tmp") as tmp_file:
            tmp_file.write(downloaded_file.getvalue())
            temp_input = tmp_file.name
        await state.update_data(input_path=temp_input)
        await delete_dialog_message(state)
        m = await message.answer("Выбери целевой формат:", reply_markup=get_converter_formats_keyboard())
        await state.update_data(msg_id=m.message_id, chat_id=m.chat.id)
        await ConverterStates.format.set()
    except Exception as e:
        logging.error(f"Ошибка при получении файла: {e}")
        await send_temp_message(message.chat.id, "❌ Не удалось загрузить файл. Попробуй ещё раз.", 3)
        await safe_finish(state, message)

@dp.message_handler(state=ConverterStates.format)
async def converter_format(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await safe_finish(state, message)
        return
    fmt = message.text.upper()
    allowed_formats = ["MP4", "GIF", "MP3", "WEBM"]
    if fmt not in allowed_formats:
        await send_temp_message(message.chat.id, f"❌ Неверный формат. Выбери из кнопок: {', '.join(allowed_formats)}", 3)
        return
    data = await state.get_data()
    input_path = data.get('input_path')
    if not input_path or not os.path.exists(input_path):
        await send_temp_message(message.chat.id, "❌ Файл не найден. Попробуй ещё раз.", 3)
        await safe_finish(state, message)
        return
    await delete_dialog_message(state)
    await state.finish()

    spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    progress_msg = await message.answer(f"⏳ Конвертирую... {spinner[0]}")

    async def update_spinner():
        i = 0
        while True:
            await asyncio.sleep(0.3)
            i = (i + 1) % len(spinner)
            try:
                await bot.edit_message_text(f"⏳ Конвертирую... {spinner[i]}", chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
            except:
                break

    spinner_task = asyncio.create_task(update_spinner())
    output_path = None

    try:
        ffmpeg_path = shutil.which('ffmpeg')
        if not ffmpeg_path:
            ffmpeg_path = os.path.join(os.getcwd(), 'ffmpeg')
            if not os.path.exists(ffmpeg_path):
                raise Exception("ffmpeg не найден в системе. Установите ffmpeg или поместите его в папку с ботом.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{fmt.lower()}", dir="/tmp") as tmp_out:
            output_path = tmp_out.name
        cmd = [ffmpeg_path, '-i', input_path, output_path]
        if fmt == "GIF":
            cmd = [ffmpeg_path, '-i', input_path, '-vf', 'scale=640:-1:flags=lanczos,fps=15,split[s0][s1];[s0]palettegen=max_colors=256[p];[s1][p]paletteuse', '-loop', '0', output_path]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="ignore").strip()[:200]
            raise Exception(f"ffmpeg error: {error_msg}")

        file_size = os.path.getsize(output_path)
        max_size = 50 * 1024 * 1024
        if file_size > max_size:
            raise Exception(f"File too large: {file_size / (1024*1024):.1f} MB > 50 MB limit. Try a different format (MP4 or WEBM may be smaller) or reduce resolution manually.")

        spinner_task.cancel()
        try:
            await spinner_task
        except asyncio.CancelledError:
            pass
        await bot.edit_message_text("✅ Конвертация завершена! Отправляю файл...", chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
        with open(output_path, 'rb') as f:
            await message.answer_document(f, caption=f"✅ Конвертировано в {fmt.upper()}")
    except Exception as e:
        logging.error(f"Ошибка конвертации: {e}")
        spinner_task.cancel()
        try:
            await spinner_task
        except asyncio.CancelledError:
            pass
        error_msg = str(e)
        if "File too large" in error_msg:
            await bot.edit_message_text(f"❌ {error_msg}", chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
        else:
            await bot.edit_message_text(f"❌ Ошибка конвертации: {error_msg}\nПопробуй другой файл или формат.", chat_id=progress_msg.chat.id, message_id=progress_msg.message_id)
        await asyncio.sleep(3)
        await safe_delete_message_obj(progress_msg)
    finally:
        safe_remove_file(input_path)
        safe_remove_file(output_path)
    await message.answer("Главное меню", reply_markup=get_main_menu())

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
    save_reminder_settings(message.from_user.id, get_default_reminders())
    await state.finish()
    await message.answer("✅ Напоминания включены!", reply_markup=get_main_menu())

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
    """Меню для настройки напоминаний (включить/выключить каждый тип)"""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🛌 Сон", "⚡️ Чек-ины")
    kb.add("📝 Итог дня", "⬅️ Назад")
    await message.answer("Выбери, что настроить:", reply_markup=kb)
    await ReminderCustomizeStates.waiting.set()

# Состояния для настройки напоминаний
class ReminderCustomizeStates:
    waiting = 0
    change_sleep_time = 1
    change_checkins_times = 2
    change_summary_time = 3

@dp.message_handler(state=ReminderCustomizeStates.waiting)
async def reminder_customize_choose(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.finish()
        await settings(message)
        return

    settings = load_reminder_settings(message.from_user.id)
    if not settings:
        settings = get_default_reminders()

    if message.text == "🛌 Сон":
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        current_enabled = settings["sleep"]["enabled"]
        kb.add("✅ Включить" if not current_enabled else "❌ Выключить")
        kb.add("🕐 Изменить время")
        kb.add("⬅️ Назад")
        await message.answer(
            f"Сон:\nСостояние: {'✅ Включено' if current_enabled else '❌ Выключено'}\nВремя: {settings['sleep']['time']}\n\nЧто сделать?",
            reply_markup=kb
        )
        await state.update_data(current_type="sleep")
        await state.set_state("sleep_menu")

    elif message.text == "⚡️ Чек-ины":
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        current_enabled = settings["checkins"]["enabled"]
        kb.add("✅ Включить" if not current_enabled else "❌ Выключить")
        kb.add("🕐 Изменить время")
        kb.add("⬅️ Назад")
        times_str = ", ".join(settings["checkins"]["times"])
        await message.answer(
            f"Чек-ины:\nСостояние: {'✅ Включено' if current_enabled else '❌ Выключено'}\nВремя: {times_str}\n\nЧто сделать?",
            reply_markup=kb
        )
        await state.update_data(current_type="checkins")
        await state.set_state("checkins_menu")

    elif message.text == "📝 Итог дня":
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        current_enabled = settings["summary"]["enabled"]
        kb.add("✅ Включить" if not current_enabled else "❌ Выключить")
        kb.add("🕐 Изменить время")
        kb.add("⬅️ Назад")
        await message.answer(
            f"Итог дня:\nСостояние: {'✅ Включено' if current_enabled else '❌ Выключено'}\nВремя: {settings['summary']['time']}\n\nЧто сделать?",
            reply_markup=kb
        )
        await state.update_data(current_type="summary")
        await state.set_state("summary_menu")

    else:
        await message.answer("Выбери из кнопок.")

@dp.message_handler(state="sleep_menu")
async def sleep_menu_action(message: types.Message, state: FSMContext):
    settings = load_reminder_settings(message.from_user.id)
    if not settings:
        settings = get_default_reminders()

    if message.text == "✅ Включить":
        settings["sleep"]["enabled"] = True
        save_reminder_settings(message.from_user.id, settings)
        await message.answer("✅ Напоминания о сне включены.")
        await state.finish()
        await reminder_settings_menu(message)
    elif message.text == "❌ Выключить":
        settings["sleep"]["enabled"] = False
        save_reminder_settings(message.from_user.id, settings)
        await message.answer("❌ Напоминания о сне выключены.")
        await state.finish()
        await reminder_settings_menu(message)
    elif message.text == "🕐 Изменить время":
        await message.answer("Введи новое время в формате ЧЧ:ММ (например, 09:00):")
        await state.set_state("change_sleep_time")
    elif message.text == "⬅️ Назад":
        await state.finish()
        await reminder_settings_menu(message)
    else:
        await message.answer("Выбери действие из кнопок.")

@dp.message_handler(state="change_sleep_time")
async def change_sleep_time(message: types.Message, state: FSMContext):
    if not is_valid_time_text(message.text):
        await message.answer("❌ Неверный формат. Введи время в формате ЧЧ:ММ (например, 09:00).")
        return
    settings = load_reminder_settings(message.from_user.id)
    if not settings:
        settings = get_default_reminders()
    settings["sleep"]["time"] = message.text
    save_reminder_settings(message.from_user.id, settings)
    await message.answer(f"✅ Время напоминания о сне изменено на {message.text}.")
    await state.finish()
    await reminder_settings_menu(message)

@dp.message_handler(state="checkins_menu")
async def checkins_menu_action(message: types.Message, state: FSMContext):
    settings = load_reminder_settings(message.from_user.id)
    if not settings:
        settings = get_default_reminders()

    if message.text == "✅ Включить":
        settings["checkins"]["enabled"] = True
        save_reminder_settings(message.from_user.id, settings)
        await message.answer("✅ Напоминания о чек-инах включены.")
        await state.finish()
        await reminder_settings_menu(message)
    elif message.text == "❌ Выключить":
        settings["checkins"]["enabled"] = False
        save_reminder_settings(message.from_user.id, settings)
        await message.answer("❌ Напоминания о чек-инах выключены.")
        await state.finish()
        await reminder_settings_menu(message)
    elif message.text == "🕐 Изменить время":
        await message.answer("Введи время для чек-инов в формате ЧЧ:ММ через запятую или пробел.\nНапример: 12:00, 16:00, 20:00")
        await state.set_state("change_checkins_times")
    elif message.text == "⬅️ Назад":
        await state.finish()
        await reminder_settings_menu(message)
    else:
        await message.answer("Выбери действие из кнопок.")

@dp.message_handler(state="change_checkins_times")
async def change_checkins_times(message: types.Message, state: FSMContext):
    parts = re.split(r'[ ,;]+', message.text)
    times = []
    for part in parts:
        if is_valid_time_text(part.strip()):
            times.append(part.strip())
    if not times:
        await message.answer("❌ Не удалось распознать время. Введи время в формате ЧЧ:ММ через запятую или пробел (например, 12:00, 16:00, 20:00).")
        return
    times = sorted(set(times))
    settings = load_reminder_settings(message.from_user.id)
    if not settings:
        settings = get_default_reminders()
    settings["checkins"]["times"] = times
    save_reminder_settings(message.from_user.id, settings)
    await message.answer(f"✅ Время чек-инов изменено: {', '.join(times)}.")
    await state.finish()
    await reminder_settings_menu(message)

@dp.message_handler(state="summary_menu")
async def summary_menu_action(message: types.Message, state: FSMContext):
    settings = load_reminder_settings(message.from_user.id)
    if not settings:
        settings = get_default_reminders()

    if message.text == "✅ Включить":
        settings["summary"]["enabled"] = True
        save_reminder_settings(message.from_user.id, settings)
        await message.answer("✅ Напоминания об итоге дня включены.")
        await state.finish()
        await reminder_settings_menu(message)
    elif message.text == "❌ Выключить":
        settings["summary"]["enabled"] = False
        save_reminder_settings(message.from_user.id, settings)
        await message.answer("❌ Напоминания об итоге дня выключены.")
        await state.finish()
        await reminder_settings_menu(message)
    elif message.text == "🕐 Изменить время":
        await message.answer("Введи новое время для итога дня в формате ЧЧ:ММ (например, 22:30):")
        await state.set_state("change_summary_time")
    elif message.text == "⬅️ Назад":
        await state.finish()
        await reminder_settings_menu(message)
    else:
        await message.answer("Выбери действие из кнопок.")

@dp.message_handler(state="change_summary_time")
async def change_summary_time(message: types.Message, state: FSMContext):
    if not is_valid_time_text(message.text):
        await message.answer("❌ Неверный формат. Введи время в формате ЧЧ:ММ (например, 22:30).")
        return
    settings = load_reminder_settings(message.from_user.id)
    if not settings:
        settings = get_default_reminders()
    settings["summary"]["time"] = message.text
    save_reminder_settings(message.from_user.id, settings)
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
        for user_id, settings in all_data.items():
            user_id = int(user_id)
            tz = db.get_user_timezone(user_id)
            if tz == 0:
                continue
            user_time = now_utc + timedelta(hours=tz)
            current_time = user_time.strftime("%H:%M")
            # Сон
            if settings["sleep"]["enabled"]:
                if settings["sleep"]["time"] == current_time:
                    if not db.has_sleep_today(user_id):
                        await bot.send_message(user_id, "🛌 Пора записать сон")
            # Чек-ины
            if settings["checkins"]["enabled"]:
                for t in settings["checkins"]["times"]:
                    if t == current_time:
                        checkins = db._load_json(user_id, "checkins.json")
                        today_str = user_time.strftime("%Y-%m-%d")
                        has_today_checkin = any(c.get("date") == today_str for c in checkins)
                        if not has_today_checkin:
                            await bot.send_message(user_id, "⚡️ Сделай чек-ин")
            # Итог дня
            if settings["summary"]["enabled"]:
                if settings["summary"]["time"] == current_time:
                    if db.get_target_date_for_summary(user_id):
                        await bot.send_message(user_id, "📝 Не забудь подвести итог дня")
    except Exception as e:
        logging.error(f"Ошибка кастомных напоминаний: {e}")

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

# ========== ПРОСТОЙ HTTP-СЕРВЕР ДЛЯ HEALTHCHECK ==========
async def healthcheck(request):
    return web.Response(text="OK")

async def run_http_server():
    port = int(os.environ.get("PORT", 10000))
    app = web.Application()
    app.router.add_get("/", healthcheck)
    app.router.add_get("/health", healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Healthcheck сервер запущен на порту {port}")
    await asyncio.Event().wait()

async def on_startup(dp):
    global scheduler
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(1)
    asyncio.create_task(run_http_server())
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(check_reminders, IntervalTrigger(minutes=1))
    scheduler.add_job(check_custom_reminders, IntervalTrigger(minutes=1))
    scheduler.start()
    print("🤖 Бот запущен и планировщик уведомлений активен!")

async def on_shutdown(dp):
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown, skip_updates=True)
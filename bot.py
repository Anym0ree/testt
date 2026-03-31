import asyncio
import logging
import os
import re
import tempfile
from datetime import datetime, timedelta

import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

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

# ========== AI СОВЕТНИК ==========
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
        opts = {
            "outtmpl": "/tmp/%(title).120s-%(id)s.%(ext)s",
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
    # Очищаем кэш AI, если был активен
    ai_advisor.clear_user_data(message.from_user.id)
    await delete_dialog_message(state)
    await state.finish()
    await message.answer("Главное меню", reply_markup=get_main_menu())
@dp.message_handler(state=TimezoneStates.city)
async def timezone_city(message: types.Message, state: FSMContext):
    if message.text in ("❌ Отмена", "⬅️ Назад"):
        await safe_finish(state, message)
        return

    if message.text == "Другое":
        await TimezoneStates.offset.set()
        await edit_or_send(
            state,
            message.chat.id,
            "Введи смещение от UTC (например: -5, 0, +3):",
            get_back_button(),
            edit=False
        )
        return

    if message.text in CITY_TO_OFFSET:
        db.set_user_timezone(message.from_user.id, CITY_TO_OFFSET[message.text])
        await delete_dialog_message(state)
        await state.finish()
        await message.answer("✅ Часовой пояс сохранён.", reply_markup=get_main_menu())
        return

    await message.answer("Выбери город из кнопок или нажми «Другое».", reply_markup=get_timezone_buttons())

@dp.message_handler(state=TimezoneStates.offset)
async def timezone_offset(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await TimezoneStates.city.set()
        await edit_or_send(
            state,
            message.chat.id,
            "Выбери свой город или нажми «Другое»:",
            get_timezone_buttons(),
            edit=True
        )
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
    await message.answer("✅ Часовой пояс сохранён.", reply_markup=get_main_menu())

# ========== ОСТАЛЬНЫЕ ОБРАБОТЧИКИ (СОН, ЧЕК-ИН, ИТОГ ДНЯ, ЕДА/НАПИТКИ) ==========
# Они остаются без изменений (как в твоём исходном коде). 
# Я не буду их дублировать здесь, чтобы не перегружать ответ, 
# но в полном файле они должны быть. Если нужно, я могу дать полный файл со всем.

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
        "🚫 Не надо": None
    }
    if message.text not in advance_map:
        await edit_or_send(state, message.chat.id, "❌ Выбери вариант из кнопок.", get_reminder_advance_buttons(), edit=True)
        return
    advance_type = advance_map.get(message.text)

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
    visible_notes = list(reversed(notes[-20:]))
    text = "📋 *Твои заметки:*\n\n"
    for i, note in enumerate(visible_notes, 1):
        note_text = note['text'][:50] + "..." if len(note['text']) > 50 else note['text']
        text += f"{i}. {note_text}\n   📅 {note.get('date','-')} {note.get('time','')}\n\n"
    await message.answer(text, parse_mode="Markdown", reply_markup=get_notes_list_keyboard(visible_notes))

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("note_view_"), state='*')
async def note_view(callback: types.CallbackQuery):
    note_id = int(callback.data.split("_")[-1])
    notes = db.get_notes(callback.from_user.id)
    note = next((n for n in notes if n.get("id") == note_id), None)
    if not note:
        await callback.answer("Заметка не найдена", show_alert=True)
        return
    text = (
        "📝 *Заметка*\n\n"
        f"{note['text']}\n\n"
        f"📅 {note.get('date','-')} {note.get('time','')}"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_note_action_keyboard(note_id))
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("note_copy_"), state='*')
async def note_copy(callback: types.CallbackQuery):
    note_id = int(callback.data.split("_")[-1])
    notes = db.get_notes(callback.from_user.id)
    note = next((n for n in notes if n.get("id") == note_id), None)
    if not note:
        await callback.answer("Заметка не найдена", show_alert=True)
        return
    
    await bot.send_message(callback.from_user.id, f"📋 *Скопированная заметка:*\n\n{note['text']}", parse_mode="Markdown")
    await callback.answer("✅ Заметка скопирована и отправлена тебе в чат!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("note_del_"), state='*')
async def note_delete_confirm(callback: types.CallbackQuery):
    note_id = int(callback.data.split("_")[-1])
    await callback.message.edit_text(
        "⚠️ *Точно удалить эту заметку?*",
        parse_mode="Markdown",
        reply_markup=get_confirm_delete_keyboard("note", note_id)
    )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("note_confirm_del_"), state='*')
async def note_delete(callback: types.CallbackQuery):
    note_id = int(callback.data.split("_")[-1])
    db.delete_note_by_id(callback.from_user.id, note_id)
    await callback.answer("Заметка удалена", show_alert=False)
    notes = db.get_notes(callback.from_user.id)
    if notes:
        visible_notes = list(reversed(notes[-20:]))
        text = "📋 *Твои заметки:*\n\n"
        for i, note in enumerate(visible_notes, 1):
            note_text = note['text'][:50] + "..." if len(note['text']) > 50 else note['text']
            text += f"{i}. {note_text}\n   📅 {note.get('date','-')} {note.get('time','')}\n\n"
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_notes_list_keyboard(visible_notes))
    else:
        await callback.message.edit_text("📋 У тебя пока нет заметок.", reply_markup=get_notes_reminders_main_menu())
    await callback.message.answer("Главное меню", reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data == "note_cancel", state='*')
async def note_cancel(callback: types.CallbackQuery):
    notes = db.get_notes(callback.from_user.id)
    if notes:
        visible_notes = list(reversed(notes[-20:]))
        text = "📋 *Твои заметки:*\n\n"
        for i, note in enumerate(visible_notes, 1):
            note_text = note['text'][:50] + "..." if len(note['text']) > 50 else note['text']
            text += f"{i}. {note_text}\n   📅 {note.get('date','-')} {note.get('time','')}\n\n"
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_notes_list_keyboard(visible_notes))
    else:
        await callback.message.edit_text("📋 У тебя пока нет заметок.", reply_markup=get_notes_reminders_main_menu())
    await callback.answer()

# ========== НАПОМИНАНИЯ ==========
@dp.message_handler(text="⏰ Напоминания")
async def list_reminders(message: types.Message, state: FSMContext):
    await state.finish()
    reminders = db.get_active_reminders(message.from_user.id)
    if not reminders:
        await message.answer("📋 У тебя пока нет активных напоминаний.", reply_markup=get_notes_reminders_main_menu())
        return
    text = "📋 *Твои напоминания:*\n\n"
    for r in reminders:
        marker = "🔔" if r.get("parent_id") else "⏰"
        text += f"{marker} {r['date']} {r['time']} — {r['text'][:40]}\n"
    await message.answer(text, parse_mode="Markdown", reply_markup=get_reminder_list_keyboard(reminders))

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("reminder_view_"), state='*')
async def reminder_view(callback: types.CallbackQuery):
    reminder_id = int(callback.data.split("_")[-1])
    reminder = db.get_reminder_by_id(callback.from_user.id, reminder_id)
    if not reminder:
        await callback.answer("Напоминание не найдено", show_alert=True)
        return
    is_extra = bool(reminder.get("parent_id"))
    reminder_type = "🔔 Доп. напоминание" if is_extra else "⏰ Основное напоминание"
    text = (
        f"*{reminder_type}*\n\n"
        f"📝 {reminder['text']}\n\n"
        f"🕐 {reminder['date']} {reminder['time']}"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_reminder_action_keyboard(reminder_id))
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("reminder_del_"), state='*')
async def reminder_delete_confirm(callback: types.CallbackQuery):
    reminder_id = int(callback.data.split("_")[-1])
    await callback.message.edit_text(
        "⚠️ *Точно удалить это напоминание?*\n\n*Внимание:* при удалении основного напоминания удалится и дополнительное!",
        parse_mode="Markdown",
        reply_markup=get_confirm_delete_keyboard("reminder", reminder_id)
    )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("reminder_confirm_del_"), state='*')
async def reminder_delete(callback: types.CallbackQuery):
    reminder_id = int(callback.data.split("_")[-1])
    db.delete_reminder(callback.from_user.id, reminder_id)
    await callback.answer("Напоминание удалено", show_alert=False)
    reminders = db.get_active_reminders(callback.from_user.id)
    if reminders:
        text = "📋 *Твои напоминания:*\n\n"
        for r in reminders:
            marker = "🔔" if r.get("parent_id") else "⏰"
            text += f"{marker} {r['date']} {r['time']} — {r['text'][:40]}\n"
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_reminder_list_keyboard(reminders))
    else:
        await callback.message.edit_text("📋 У тебя пока нет активных напоминаний.", reply_markup=get_notes_reminders_main_menu())
    await callback.message.answer("Главное меню", reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data == "reminder_cancel", state='*')
async def reminder_cancel(callback: types.CallbackQuery):
    reminders = db.get_active_reminders(callback.from_user.id)
    if reminders:
        text = "📋 *Твои напоминания:*\n\n"
        for r in reminders:
            marker = "🔔" if r.get("parent_id") else "⏰"
            text += f"{marker} {r['date']} {r['time']} — {r['text'][:40]}\n"
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_reminder_list_keyboard(reminders))
    else:
        await callback.message.edit_text("📋 У тебя пока нет активных напоминаний.", reply_markup=get_notes_reminders_main_menu())
    await callback.answer()

# ========== AI СОВЕТ ==========
@dp.message_handler(text="🤖 AI-совет")
async def ai_advice_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    # Собираем данные пользователя
    user_data = {
        "sleep": db._load_json(user_id, "sleep.json"),
        "checkins": db._load_json(user_id, "checkins.json"),
        "day_summary": db._load_json(user_id, "day_summary.json"),
        "notes": db._load_json(user_id, "notes.json"),
        "reminders": db._load_json(user_id, "reminders.json"),
    }
    ai_advisor.set_user_data(user_id, user_data)

    await AIState.waiting_question.set()
    await message.answer(
        "🤖 *Загружаю ваши данные для анализа...*",
        parse_mode="Markdown"
    )
    advice = await ai_advisor.get_advice(user_id)
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

    if not ai_advisor.get_user_data(user_id):
        # Если нет в кэше, загружаем
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
    await message.answer(
        f"🤖 *Ответ:*\n\n{advice}",
        parse_mode="Markdown"
    )

# ========== ОСТАЛЬНЫЕ ОБРАБОТЧИКИ (СТАТИСТИКА, ЭКСПОРТ, КОНВЕРТЕР, НАСТРОЙКИ) ==========
# Они остаются как в твоём исходном коде. Я их здесь не дублирую, но в полном файле они должны быть.

# ========== УВЕДОМЛЕНИЯ И ЗАПУСК ==========
scheduler = None
web_task = None

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

from web import start_web, stop_web

async def on_startup(dp):
    global scheduler, web_task
    await bot.delete_webhook(drop_pending_updates=True)
    web_task = start_web()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(check_reminders, IntervalTrigger(minutes=1))
    scheduler.start()
    print("🤖 Бот запущен и планировщик уведомлений активен!")

async def on_shutdown(dp):
    global scheduler, web_task
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
    await stop_web(web_task)
    web_task = None

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)

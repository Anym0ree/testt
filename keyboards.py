from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu():
    buttons = [
        [KeyboardButton(text="🛌 Сон")],
        [KeyboardButton(text="⚡️ Чек-ин")],
        [KeyboardButton(text="📝 Итог дня")],
        [KeyboardButton(text="🍽 Еда")],
        [KeyboardButton(text="🥤 Напитки")],
        [KeyboardButton(text="💭 Мысли")],
        [KeyboardButton(text="💭 Мои мысли")],
        [KeyboardButton(text="🍽 Еда сегодня")],
        [KeyboardButton(text="🥤 Напитки сегодня")],
        [KeyboardButton(text="📅 Напоминания")],  # новая кнопка
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📤 Экспорт")],
        [KeyboardButton(text="⚙️ Настройки")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_reminder_menu():
    buttons = [
        [KeyboardButton(text="➕ Добавить")],
        [KeyboardButton(text="📋 Мои напоминания")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_reminder_action_keyboard(reminder_id):
    buttons = [
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"reminder_delete_{reminder_id}")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"reminder_edit_{reminder_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="reminder_back_to_list")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_reminder_date_buttons():
    buttons = [
        [KeyboardButton(text="📅 Сегодня")],
        [KeyboardButton(text="📆 Завтра")],
        [KeyboardButton(text="📆 Послезавтра")],
        [KeyboardButton(text="🔢 Выбрать дату")],
        [KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_reminder_hour_buttons():
    row1 = [KeyboardButton(text=str(i)) for i in range(0, 6)]
    row2 = [KeyboardButton(text=str(i)) for i in range(6, 12)]
    row3 = [KeyboardButton(text=str(i)) for i in range(12, 18)]
    row4 = [KeyboardButton(text=str(i)) for i in range(18, 24)]
    buttons = [row1, row2, row3, row4, [KeyboardButton(text="❌ Отмена")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_reminder_minute_buttons():
    buttons = [
        [KeyboardButton(text="00"), KeyboardButton(text="15")],
        [KeyboardButton(text="30"), KeyboardButton(text="45")],
        [KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_reminder_advance_buttons():
    buttons = [
        [KeyboardButton(text="⏰ За 1 день")],
        [KeyboardButton(text="⏳ За 3 часа")],
        [KeyboardButton(text="⌛ За 1 час")],
        [KeyboardButton(text="🚫 Не надо")],
        [KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_reminder_list_keyboard(reminders):
    buttons = []
    for r in reminders:
        text = f"🕐 {r['date']} {r['time']} — {r['text'][:30]}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"reminder_select_{r['id']}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="reminder_back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_reminder_edit_keyboard():
    buttons = [
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="reminder_edit_text")],
        [InlineKeyboardButton(text="🕐 Изменить время", callback_data="reminder_edit_time")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="reminder_back_to_action")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Остальные функции (get_settings_menu, get_reset_confirm_keyboard и т.д.) остаются без изменений
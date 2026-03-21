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
        [KeyboardButton(text="📅 Напоминания")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📤 Экспорт")],
        [KeyboardButton(text="⚙️ Настройки")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_settings_menu():
    buttons = [
        [KeyboardButton(text="🌍 Сменить город")],
        [KeyboardButton(text="🔄 Сброс данных")],
        [KeyboardButton(text="❌ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_reset_confirm_keyboard():
    buttons = [
        [InlineKeyboardButton(text="✅ Да, сбросить всё", callback_data="reset_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="reset_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_emotion_buttons():
    buttons = [
        [KeyboardButton(text="😊 Радость"), KeyboardButton(text="😠 Гнев")],
        [KeyboardButton(text="😰 Тревога"), KeyboardButton(text="😌 Спокойствие")],
        [KeyboardButton(text="😤 Раздражение"), KeyboardButton(text="😔 Грусть")],
        [KeyboardButton(text="😐 Апатия"), KeyboardButton(text="😨 Страх")],
        [KeyboardButton(text="😌 Облегчение"), KeyboardButton(text="😳 Стыд")],
        [KeyboardButton(text="✨ Вдохновение"), KeyboardButton(text="✍️ Своя")],
        [KeyboardButton(text="✅ Готово"), KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_yes_no_buttons():
    buttons = [
        [KeyboardButton(text="✅ Да"), KeyboardButton(text="❌ Нет")],
        [KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_meal_type_buttons():
    buttons = [
        [KeyboardButton(text="🍳 Завтрак"), KeyboardButton(text="🍱 Обед")],
        [KeyboardButton(text="🍲 Ужин"), KeyboardButton(text="🍎 Перекус")],
        [KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_drink_type_buttons():
    buttons = [
        [KeyboardButton(text="💧 Вода"), KeyboardButton(text="☕️ Кофе")],
        [KeyboardButton(text="🍵 Чай"), KeyboardButton(text="🧃 Сок")],
        [KeyboardButton(text="🍺 Алкоголь"), KeyboardButton(text="⚡️ Энергетик")],
        [KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_drink_amount_buttons():
    buttons = [
        [KeyboardButton(text="1 чашка"), KeyboardButton(text="2 чашки")],
        [KeyboardButton(text="3+ чашек"), KeyboardButton(text="200 мл")],
        [KeyboardButton(text="300 мл"), KeyboardButton(text="500 мл")],
        [KeyboardButton(text="1 л"), KeyboardButton(text="Другое")],
        [KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_thought_type_buttons():
    buttons = [
        [KeyboardButton(text="😰 Тревожная"), KeyboardButton(text="🤬 Критическая")],
        [KeyboardButton(text="🔄 Повторяющаяся"), KeyboardButton(text="💡 Инсайт")],
        [KeyboardButton(text="✨ Вдохновляющая"), KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_thought_action_buttons():
    buttons = [
        [KeyboardButton(text="🔄 Зациклился"), KeyboardButton(text="👋 Отпустил")],
        [KeyboardButton(text="📝 Записал"), KeyboardButton(text="🗣 Рассказал")],
        [KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_energy_stress_buttons():
    row = [KeyboardButton(text=str(i)) for i in range(1, 6)]
    row2 = [KeyboardButton(text=str(i)) for i in range(6, 11)]
    buttons = [row, row2, [KeyboardButton(text="❌ Отмена")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_time_buttons():
    buttons = [
        [KeyboardButton(text="22:00"), KeyboardButton(text="23:00")],
        [KeyboardButton(text="00:00"), KeyboardButton(text="01:00")],
        [KeyboardButton(text="02:00"), KeyboardButton(text="03:00")],
        [KeyboardButton(text="Другое"), KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_skip_markup_text():
    buttons = [
        [KeyboardButton(text="Пропустить"), KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_thoughts_list_keyboard(thoughts):
    buttons = []
    for i, thought in enumerate(thoughts):
        text = thought['thought_text'][:30] + "..." if len(thought['thought_text']) > 30 else thought['thought_text']
        buttons.append([InlineKeyboardButton(text=f"🗑 {text}", callback_data=f"del_thought_{i}")])
    buttons.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="close_thoughts")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_timezone_buttons():
    buttons = [
        [KeyboardButton(text="Москва (UTC+3)"), KeyboardButton(text="Санкт-Петербург (UTC+3)")],
        [KeyboardButton(text="Екатеринбург (UTC+5)"), KeyboardButton(text="Новосибирск (UTC+7)")],
        [KeyboardButton(text="Владивосток (UTC+10)"), KeyboardButton(text="Калининград (UTC+2)")],
        [KeyboardButton(text="Другое"), KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ========== КЛАВИАТУРЫ ДЛЯ НАПОМИНАНИЙ ==========
def get_reminder_menu():
    buttons = [
        [KeyboardButton(text="➕ Добавить")],
        [KeyboardButton(text="📋 Мои напоминания")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

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

def get_reminder_action_keyboard(reminder_id):
    buttons = [
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"reminder_delete_{reminder_id}")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"reminder_edit_{reminder_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="reminder_back_to_list")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_reminder_edit_keyboard():
    buttons = [
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="reminder_edit_text")],
        [InlineKeyboardButton(text="🕐 Изменить время", callback_data="reminder_edit_time")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="reminder_back_to_action")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_button():
    buttons = [[KeyboardButton(text="⬅️ Назад")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
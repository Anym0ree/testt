from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu():
    buttons = [
        [KeyboardButton(text="🛌 Сон")],
        [KeyboardButton(text="⚡️ Чек-ин")],
        [KeyboardButton(text="📝 Итог дня")],
        [KeyboardButton(text="🍽 Еда")],
        [KeyboardButton(text="🥤 Напитки")],
        [KeyboardButton(text="💭 Мысли")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📤 Экспорт")],
        [KeyboardButton(text="⚙️ Настройки")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_settings_menu():
    buttons = [
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
        [KeyboardButton(text="🔄 Другое"), KeyboardButton(text="❌ Отмена")]
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

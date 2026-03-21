from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🛌 Сон"))
    builder.add(KeyboardButton(text="⚡️ Чек-ин"))
    builder.add(KeyboardButton(text="📝 Итог дня"))
    builder.add(KeyboardButton(text="🍽 Еда"))
    builder.add(KeyboardButton(text="🥤 Напитки"))
    builder.add(KeyboardButton(text="💭 Мысли"))
    builder.add(KeyboardButton(text="📊 Статистика"))
    builder.add(KeyboardButton(text="📤 Экспорт"))
    builder.add(KeyboardButton(text="⚙️ Настройки"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_settings_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🔄 Сброс данных"))
    builder.add(KeyboardButton(text="❌ Назад"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def get_emotion_buttons():
    builder = ReplyKeyboardBuilder()
    emotions = ["😊 Радость", "😠 Гнев", "😰 Тревога", "😌 Спокойствие", 
                "😤 Раздражение", "😔 Грусть", "😐 Апатия", "✍️ Своя"]
    for e in emotions:
        builder.add(KeyboardButton(text=e))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_yes_no_buttons():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="✅ Да"))
    builder.add(KeyboardButton(text="❌ Нет"))
    return builder.as_markup(resize_keyboard=True)

def get_meal_type_buttons():
    builder = ReplyKeyboardBuilder()
    for meal in ["🍳 Завтрак", "🍱 Обед", "🍲 Ужин", "🍎 Перекус"]:
        builder.add(KeyboardButton(text=meal))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_drink_type_buttons():
    builder = ReplyKeyboardBuilder()
    drinks = ["💧 Вода", "☕️ Кофе", "🍵 Чай", "🧃 Сок", "🍺 Алкоголь", "⚡️ Энергетик", "🔄 Другое"]
    for d in drinks:
        builder.add(KeyboardButton(text=d))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_drink_amount_buttons():
    builder = ReplyKeyboardBuilder()
    for amount in ["1 чашка", "2 чашки", "3+ чашек", "200 мл", "300 мл", "500 мл", "1 л", "Другое"]:
        builder.add(KeyboardButton(text=amount))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_thought_type_buttons():
    builder = ReplyKeyboardBuilder()
    types = ["😰 Тревожная", "🤬 Критическая", "🔄 Повторяющаяся", "💡 Инсайт", "✨ Вдохновляющая"]
    for t in types:
        builder.add(KeyboardButton(text=t))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_thought_action_buttons():
    builder = ReplyKeyboardBuilder()
    actions = ["🔄 Зациклился", "👋 Отпустил", "📝 Записал", "🗣 Рассказал"]
    for a in actions:
        builder.add(KeyboardButton(text=a))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_energy_stress_buttons():
    builder = ReplyKeyboardBuilder()
    for i in range(1, 11):
        builder.add(KeyboardButton(text=str(i)))
    builder.adjust(5)
    return builder.as_markup(resize_keyboard=True)

def get_time_buttons():
    builder = ReplyKeyboardBuilder()
    for t in ["22:00", "23:00", "00:00", "01:00", "Другое"]:
        builder.add(KeyboardButton(text=t))
    builder.add(KeyboardButton(text="❌ Отмена"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_skip_markup_text():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Пропустить"))
    builder.add(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)

def get_reset_confirm_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Да, сбросить всё", callback_data="reset_confirm"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="reset_cancel"))
    return builder.as_markup()

import os

# СЮДА ВСТАВЬ ТОКЕН ОТ @BotFather
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Папка для хранения данных
DATA_FOLDER = "user_data"

# Создаем папку если нет
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

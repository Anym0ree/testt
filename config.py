import os

# Токен бота (получить у @BotFather)
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Папка для хранения данных (локально, внутри контейнера)
DATA_FOLDER = "user_data"

# Создаём папку, если её нет
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

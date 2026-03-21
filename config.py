import os

# СЮДА ВСТАВЬ ТОКЕН ОТ @BotFather
BOT_TOKEN = "8774658045:AAHvlvChRK1-JVcLpcmPqQ-89lkY--W4rE8"

# Папка для хранения данных
DATA_FOLDER = "user_data"

# Создаем папку если нет
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)
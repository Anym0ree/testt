import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DATA_FOLDER = "data"

# Проверка, что токены заданы (для отладки)
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY не задан в переменных окружения")

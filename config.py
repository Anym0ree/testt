import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Путь к папке с данными (создаётся автоматически)
DATA_FOLDER = os.path.join(os.path.dirname(__file__), "data")  # или просто "data", если папка в корне

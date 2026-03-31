import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATA_FOLDER = "user_data"

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Please export BOT_TOKEN before starting the bot.")
# AI (OpenAI)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")   # для AI-советника

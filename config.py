import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATA_FOLDER = "user_data"

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

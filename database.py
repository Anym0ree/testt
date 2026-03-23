import json
import os
import logging
from datetime import datetime, timedelta
from config import DATA_FOLDER

logging.basicConfig(level=logging.INFO)

class Database:
    def __init__(self):
        self.data_folder = DATA_FOLDER

    # ... все методы остаются без изменений (кроме get_today_food и get_today_drinks) ...

    # === СПИСОК ЕДЫ ЗА ДЕНЬ (с сортировкой) ===
    def get_today_food(self, user_id):
        food = self._load_json(user_id, "food.json")
        today = self.get_user_local_date(user_id)
        today_food = [f for f in food if f.get("date") == today]
        # сортировка по времени
        today_food.sort(key=lambda x: x.get('time', '00:00'))
        return today_food

    # === СПИСОК НАПИТКОВ ЗА ДЕНЬ (с сортировкой) ===
    def get_today_drinks(self, user_id):
        drinks = self._load_json(user_id, "drinks.json")
        today = self.get_user_local_date(user_id)
        today_drinks = [d for d in drinks if d.get("date") == today]
        today_drinks.sort(key=lambda x: x.get('time', '00:00'))
        return today_drinks

    # ... остальные методы без изменений ...
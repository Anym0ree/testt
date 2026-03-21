import json
import os
from datetime import datetime
from config import DATA_FOLDER

class Database:
    def __init__(self):
        self.data_folder = DATA_FOLDER

    def _get_user_folder(self, user_id):
        return os.path.join(self.data_folder, str(user_id))

    def _get_user_file(self, user_id, filename):
        user_folder = self._get_user_folder(user_id)
        if not os.path.exists(user_folder):
            os.makedirs(user_folder)
        return os.path.join(user_folder, filename)

    def _load_json(self, user_id, filename):
        file_path = self._get_user_file(user_id, filename)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def _save_json(self, user_id, filename, data):
        file_path = self._get_user_file(user_id, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # Сон
    def add_sleep(self, user_id, bed_time, wake_time, quality, woke_night, note=""):
        data = self._load_json(user_id, "sleep.json")
        record = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "bed_time": bed_time,
            "wake_time": wake_time,
            "quality": quality,
            "woke_night": woke_night,
            "note": note
        }
        data.append(record)
        self._save_json(user_id, "sleep.json", data)

    # Чек-ин
    def add_checkin(self, user_id, time_slot, energy, stress, emotion, note=""):
        data = self._load_json(user_id, "checkins.json")
        record = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "timestamp": datetime.now().isoformat(),
            "time_slot": time_slot,
            "energy": energy,
            "stress": stress,
            "emotion": emotion,
            "note": note
        }
        data.append(record)
        self._save_json(user_id, "checkins.json", data)

    # Итог дня
    def add_day_summary(self, user_id, score, best, worst, gratitude, note=""):
        data = self._load_json(user_id, "day_summary.json")
        record = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "score": score,
            "best": best,
            "worst": worst,
            "gratitude": gratitude,
            "note": note
        }
        data.append(record)
        self._save_json(user_id, "day_summary.json", data)

    # Еда
    def add_food(self, user_id, meal_type, food_text):
        data = self._load_json(user_id, "food.json")
        record = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "timestamp": datetime.now().isoformat(),
            "meal_type": meal_type,
            "food_text": food_text
        }
        data.append(record)
        self._save_json(user_id, "food.json", data)

    # Напитки
    def add_drink(self, user_id, drink_type, amount):
        data = self._load_json(user_id, "drinks.json")
        record = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "timestamp": datetime.now().isoformat(),
            "drink_type": drink_type,
            "amount": amount
        }
        data.append(record)
        self._save_json(user_id, "drinks.json", data)

    # Мысли
    def add_thought(self, user_id, thought_text, thought_type, action):
        data = self._load_json(user_id, "thoughts.json")
        record = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "timestamp": datetime.now().isoformat(),
            "thought_text": thought_text,
            "thought_type": thought_type,
            "action": action
        }
        data.append(record)
        self._save_json(user_id, "thoughts.json", data)

    # Статистика
    def get_stats(self, user_id):
        sleep = self._load_json(user_id, "sleep.json")
        checkins = self._load_json(user_id, "checkins.json")
        food = self._load_json(user_id, "food.json")
        drinks = self._load_json(user_id, "drinks.json")
        thoughts = self._load_json(user_id, "thoughts.json")

        text = "📊 ТВОЯ СТАТИСТИКА\n\n"
        text += f"😴 Сон: {len(sleep)} записей\n"
        text += f"⚡️ Чек-ины: {len(checkins)} записей\n"
        text += f"🍽 Еда: {len(food)} записей\n"
        text += f"🥤 Напитки: {len(drinks)} записей\n"
        text += f"💭 Мысли: {len(thoughts)} записей\n"

        if sleep:
            last = sleep[-1]
            text += f"\n😴 Последний сон:\n   Лег: {last.get('bed_time')}, встал: {last.get('wake_time')}\n   Качество: {last.get('quality')}/10"
        if checkins:
            last = checkins[-1]
            text += f"\n\n⚡️ Последний чек-ин:\n   Энергия: {last.get('energy')}/10, стресс: {last.get('stress')}/10\n   Эмоция: {last.get('emotion')}"

        return text

    # Экспорт всех данных
    def export_all(self, user_id):
        export_data = {
            "user_id": user_id,
            "export_date": datetime.now().isoformat(),
            "sleep": self._load_json(user_id, "sleep.json"),
            "checkins": self._load_json(user_id, "checkins.json"),
            "day_summary": self._load_json(user_id, "day_summary.json"),
            "food": self._load_json(user_id, "food.json"),
            "drinks": self._load_json(user_id, "drinks.json"),
            "thoughts": self._load_json(user_id, "thoughts.json")
        }

        file_path = os.path.join(self.data_folder, str(user_id), "export_all.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        return file_path

    # Сброс всех данных пользователя
    def reset_user_data(self, user_id):
        user_folder = self._get_user_folder(user_id)
        if os.path.exists(user_folder):
            for filename in os.listdir(user_folder):
                file_path = os.path.join(user_folder, filename)
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            try:
                os.rmdir(user_folder)
            except Exception:
                pass
            return True
        return False

db = Database()

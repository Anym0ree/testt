import json
import os
import logging
from datetime import datetime
from config import DATA_FOLDER

logging.basicConfig(level=logging.INFO)

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

    # === СОН ===
    def has_sleep_today(self, user_id):
        """Проверяет, есть ли запись сна за сегодня"""
        data = self._load_json(user_id, "sleep.json")
        today = datetime.now().strftime("%Y-%m-%d")
        for record in data:
            if record.get("date") == today:
                return True
        return False

    def add_sleep(self, user_id, bed_time, wake_time, quality, woke_night, note=""):
        if self.has_sleep_today(user_id):
            return False
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
        return True

    # === ИТОГ ДНЯ ===
    def has_day_summary_today(self, user_id):
        data = self._load_json(user_id, "day_summary.json")
        today = datetime.now().strftime("%Y-%m-%d")
        for record in data:
            if record.get("date") == today:
                return True
        return False

    def add_day_summary(self, user_id, score, best, worst, gratitude, note=""):
        if self.has_day_summary_today(user_id):
            return False
        # Проверка времени (после 18:00 по серверному времени)
        if datetime.now().hour < 18:
            return False
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
        return True

    # === ЧЕК-ИН ===
    def add_checkin(self, user_id, time_slot, energy, stress, emotions, note=""):
        data = self._load_json(user_id, "checkins.json")
        record = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M"),
            "timestamp": datetime.now().isoformat(),
            "time_slot": time_slot,
            "energy": energy,
            "stress": stress,
            "emotions": emotions,
            "note": note
        }
        data.append(record)
        self._save_json(user_id, "checkins.json", data)
        return True

    # === ЕДА ===
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
        return True

    # === НАПИТКИ ===
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
        return True

    # === МЫСЛИ ===
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
        return True

    def get_thoughts(self, user_id, limit=10):
        thoughts = self._load_json(user_id, "thoughts.json")
        return thoughts[-limit:] if thoughts else []

    def delete_thought_by_index(self, user_id, index):
        thoughts = self._load_json(user_id, "thoughts.json")
        if 0 <= index < len(thoughts):
            del thoughts[index]
            self._save_json(user_id, "thoughts.json", thoughts)
            return True
        return False

    # === СТАТИСТИКА ===
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
            emotions_str = ", ".join(last.get('emotions', []))
            text += f"\n\n⚡️ Последний чек-ин:\n   Энергия: {last.get('energy')}/10, стресс: {last.get('stress')}/10\n   Эмоции: {emotions_str}"

        return text

    # === ЭКСПОРТ ===
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

    # === СБРОС ===
    def reset_user_data(self, user_id):
        user_folder = self._get_user_folder(user_id)
        if not os.path.exists(user_folder):
            logging.info(f"Сброс данных: папка {user_folder} не существует")
            return False

        success = True
        try:
            for filename in os.listdir(user_folder):
                file_path = os.path.join(user_folder, filename)
                try:
                    os.remove(file_path)
                    logging.info(f"Удалён файл {file_path}")
                except Exception as e:
                    logging.error(f"Не удалось удалить {file_path}: {e}")
                    success = False
            try:
                os.rmdir(user_folder)
                logging.info(f"Удалена папка {user_folder}")
            except Exception as e:
                logging.warning(f"Не удалось удалить папку {user_folder}: {e}")
        except Exception as e:
            logging.error(f"Ошибка при сбросе данных: {e}")
            return False

        return success

db = Database()

import json
import os
import logging
from datetime import datetime, timedelta
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

    # === ЧАСОВОЙ ПОЯС ===
    def set_user_timezone(self, user_id, timezone_offset):
        user_folder = self._get_user_folder(user_id)
        if not os.path.exists(user_folder):
            os.makedirs(user_folder)
        file_path = os.path.join(user_folder, "user_settings.json")
        settings = {}
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        settings["timezone_offset"] = timezone_offset
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    def get_user_timezone(self, user_id):
        user_folder = self._get_user_folder(user_id)
        file_path = os.path.join(user_folder, "user_settings.json")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                return settings.get("timezone_offset", 0)
        return 0

    def get_user_local_hour(self, user_id):
        offset = self.get_user_timezone(user_id)
        utc_hour = datetime.utcnow().hour
        local_hour = (utc_hour + offset) % 24
        return local_hour

    def get_user_local_date(self, user_id):
        offset = self.get_user_timezone(user_id)
        utc_now = datetime.utcnow()
        local_now = utc_now + timedelta(hours=offset)
        return local_now.strftime("%Y-%m-%d")

    # === СОН ===
    def has_sleep_today(self, user_id):
        data = self._load_json(user_id, "sleep.json")
        today = self.get_user_local_date(user_id)
        for record in data:
            if record.get("date") == today:
                return True
        return False

    def add_sleep(self, user_id, bed_time, wake_time, quality, woke_night, note=""):
        if self.has_sleep_today(user_id):
            return False
        data = self._load_json(user_id, "sleep.json")
        record = {
            "date": self.get_user_local_date(user_id),
            "timestamp": datetime.utcnow().isoformat(),
            "bed_time": bed_time,
            "wake_time": wake_time,
            "quality": quality,
            "woke_night": woke_night,
            "note": note
        }
        data.append(record)
        self._save_json(user_id, "sleep.json", data)
        return True

    # === ИТОГ ДНЯ (НОВАЯ ЛОГИКА) ===
    def get_target_date_for_summary(self, user_id):
        """Возвращает дату, за которую нужно записать итог дня (вчера, если время до 6 утра)"""
        local_hour = self.get_user_local_hour(user_id)
        if local_hour >= 18:
            return self.get_user_local_date(user_id)
        elif local_hour < 6:
            offset = self.get_user_timezone(user_id)
            utc_now = datetime.utcnow()
            yesterday = utc_now - timedelta(days=1)
            local_yesterday = yesterday + timedelta(hours=offset)
            return local_yesterday.strftime("%Y-%m-%d")
        else:
            return None

    def has_day_summary_for_date(self, user_id, date_str):
        data = self._load_json(user_id, "day_summary.json")
        for record in data:
            if record.get("date") == date_str:
                return True
        return False

    def add_day_summary(self, user_id, score, best, worst, gratitude, note=""):
        target_date = self.get_target_date_for_summary(user_id)
        if target_date is None:
            return False
        if self.has_day_summary_for_date(user_id, target_date):
            return False
        data = self._load_json(user_id, "day_summary.json")
        record = {
            "date": target_date,
            "timestamp": datetime.utcnow().isoformat(),
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
            "date": self.get_user_local_date(user_id),
            "time": datetime.utcnow().strftime("%H:%M"),
            "timestamp": datetime.utcnow().isoformat(),
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
            "date": self.get_user_local_date(user_id),
            "time": datetime.utcnow().strftime("%H:%M"),
            "timestamp": datetime.utcnow().isoformat(),
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
            "date": self.get_user_local_date(user_id),
            "time": datetime.utcnow().strftime("%H:%M"),
            "timestamp": datetime.utcnow().isoformat(),
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
            "date": self.get_user_local_date(user_id),
            "time": datetime.utcnow().strftime("%H:%M"),
            "timestamp": datetime.utcnow().isoformat(),
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

    # === СПИСОК ЕДЫ ЗА ДЕНЬ ===
    def get_today_food(self, user_id):
        food = self._load_json(user_id, "food.json")
        today = self.get_user_local_date(user_id)
        return [f for f in food if f.get("date") == today]

    # === СПИСОК НАПИТКОВ ЗА ДЕНЬ ===
    def get_today_drinks(self, user_id):
        drinks = self._load_json(user_id, "drinks.json")
        today = self.get_user_local_date(user_id)
        return [d for d in drinks if d.get("date") == today]

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
            "export_date": datetime.utcnow().isoformat(),
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

    # === НАПОМИНАНИЯ ===
    def add_reminder(self, user_id, text, target_date, target_time, advance_type=None):
        reminders = self._load_json(user_id, "reminders.json")
        reminder_id = len(reminders) + 1
        reminder = {
            "id": reminder_id,
            "text": text,
            "date": target_date,
            "time": target_time,
            "advance_type": advance_type,
            "is_active": True,
            "created_at": datetime.utcnow().isoformat()
        }
        reminders.append(reminder)
        self._save_json(user_id, "reminders.json", reminders)

        if advance_type:
            advance_reminder = {
                "id": reminder_id + 1000,
                "text": f"⚠️ ЗА ДЕНЬ: {text}" if advance_type == "day" else f"⚠️ ЗА 3 ЧАСА: {text}" if advance_type == "3h" else f"⚠️ ЗА 1 ЧАС: {text}",
                "date": self._get_advance_date(target_date, advance_type),
                "time": target_time,
                "advance_type": None,
                "is_active": True,
                "parent_id": reminder_id,
                "created_at": datetime.utcnow().isoformat()
            }
            reminders.append(advance_reminder)
            self._save_json(user_id, "reminders.json", reminders)

        return reminder_id

    def _get_advance_date(self, target_date, advance_type):
        target = datetime.strptime(target_date, "%Y-%m-%d")
        if advance_type == "day":
            advance = target - timedelta(days=1)
        elif advance_type == "3h":
            advance = target - timedelta(hours=3)
        elif advance_type == "1h":
            advance = target - timedelta(hours=1)
        else:
            return target_date
        return advance.strftime("%Y-%m-%d")

    def get_active_reminders(self, user_id):
        reminders = self._load_json(user_id, "reminders.json")
        return [r for r in reminders if r.get("is_active", True)]

    def delete_reminder(self, user_id, reminder_id):
        reminders = self._load_json(user_id, "reminders.json")
        for r in reminders:
            if r.get("id") == reminder_id:
                r["is_active"] = False
                break
        self._save_json(user_id, "reminders.json", reminders)
        return True

    def update_reminder_text(self, user_id, reminder_id, new_text):
        reminders = self._load_json(user_id, "reminders.json")
        for r in reminders:
            if r.get("id") == reminder_id:
                r["text"] = new_text
                break
        self._save_json(user_id, "reminders.json", reminders)
        return True

    def update_reminder_time(self, user_id, reminder_id, new_date, new_time):
        reminders = self._load_json(user_id, "reminders.json")
        for r in reminders:
            if r.get("id") == reminder_id:
                r["date"] = new_date
                r["time"] = new_time
                break
        self._save_json(user_id, "reminders.json", reminders)
        return True

    def get_reminder_by_id(self, user_id, reminder_id):
        reminders = self._load_json(user_id, "reminders.json")
        for r in reminders:
            if r.get("id") == reminder_id:
                return r
        return None

db = Database()
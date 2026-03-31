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

    def _get_all_user_folders(self):
        if not os.path.exists(self.data_folder):
            return []
        return [int(folder) for folder in os.listdir(self.data_folder) if folder.isdigit()]

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

    def get_user_local_datetime(self, user_id):
        offset = self.get_user_timezone(user_id)
        utc_now = datetime.utcnow()
        local_now = utc_now + timedelta(hours=offset)
        return local_now

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

    # === ИТОГ ДНЯ ===
    def get_target_date_for_summary(self, user_id):
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

    # === ЗАМЕТКИ ===
    def add_note(self, user_id, text):
        data = self._load_json(user_id, "notes.json")
        note_id = max([n.get("id", 0) for n in data], default=0) + 1
        record = {
            "id": note_id,
            "text": text,
            "date": self.get_user_local_date(user_id),
            "time": datetime.utcnow().strftime("%H:%M"),
            "timestamp": datetime.utcnow().isoformat()
        }
        data.append(record)
        self._save_json(user_id, "notes.json", data)
        return note_id

    def get_notes(self, user_id):
        return self._load_json(user_id, "notes.json")

    def delete_note_by_id(self, user_id, note_id):
        notes = self._load_json(user_id, "notes.json")
        new_notes = [n for n in notes if n.get("id") != note_id]
        if len(new_notes) != len(notes):
            self._save_json(user_id, "notes.json", new_notes)
            return True
        return False

    def update_note_text(self, user_id, note_id, new_text):
        notes = self._load_json(user_id, "notes.json")
        for note in notes:
            if note.get("id") == note_id:
                note["text"] = new_text
                self._save_json(user_id, "notes.json", notes)
                return True
        return False

    # === НАПОМИНАНИЯ ===
    def add_reminder(self, user_id, text, target_date, target_time, advance_type=None, parent_id=None, is_custom=False):
        local_dt = self.get_user_local_datetime(user_id)
        target_dt = datetime.strptime(f"{target_date} {target_time}", "%Y-%m-%d %H:%M")
        if target_dt < local_dt:
            return None
    
        reminders = self._load_json(user_id, "reminders.json")
        reminder_id = max([r.get("id", 0) for r in reminders], default=0) + 1
        reminder = {
            "id": reminder_id,
            "text": text,
            "date": target_date,
            "time": target_time,
            "is_active": True,
            "created_at": datetime.utcnow().isoformat()
        }
        if parent_id:
            reminder["parent_id"] = parent_id
            if is_custom:
                reminder["is_custom"] = True
        else:
            reminder["advance_type"] = advance_type
    
        reminders.append(reminder)
        self._save_json(user_id, "reminders.json", reminders)
        return reminder_id
    
    def _get_advance_datetime(self, target_date, target_time, advance_type):
        target = datetime.strptime(f"{target_date} {target_time}", "%Y-%m-%d %H:%M")
        if advance_type == "day":
            advance = target - timedelta(days=1)
        elif advance_type == "3h":
            advance = target - timedelta(hours=3)
        elif advance_type == "1h":
            advance = target - timedelta(hours=1)
        else:
            return target
        return advance

    def get_active_reminders(self, user_id):
        reminders = self._load_json(user_id, "reminders.json")
        active = [r for r in reminders if r.get("is_active", True)]
        active.sort(key=lambda r: f"{r.get('date', '')} {r.get('time', '')}")
        return active

    def get_parent_reminder_id(self, reminders, reminder_id):
        selected = next((r for r in reminders if r.get("id") == reminder_id), None)
        if not selected:
            return None
        return selected.get("parent_id") or selected.get("id")

    def _get_related_reminder_ids(self, reminders, reminder_id):
        selected = next((r for r in reminders if r.get("id") == reminder_id), None)
        if not selected:
            return []
        if selected.get("parent_id"):
            parent_id = selected["parent_id"]
        else:
            parent_id = selected["id"]
        related_ids = [r["id"] for r in reminders if r.get("id") == parent_id or r.get("parent_id") == parent_id]
        return related_ids

    def delete_reminder(self, user_id, reminder_id):
        reminders = self._load_json(user_id, "reminders.json")
        selected = next((r for r in reminders if r.get("id") == reminder_id), None)
        if not selected:
            return False

        if selected.get("parent_id"):
            selected["is_active"] = False
        else:
            related_ids = self._get_related_reminder_ids(reminders, reminder_id)
            for r in reminders:
                if r.get("id") in related_ids:
                    r["is_active"] = False
        self._save_json(user_id, "reminders.json", reminders)
        return True

    def update_reminder_text(self, user_id, reminder_id, new_text):
        reminders = self._load_json(user_id, "reminders.json")
        related_ids = self._get_related_reminder_ids(reminders, reminder_id)
        target = next((r for r in reminders if r.get("id") == reminder_id), None)
        if not target:
            return False
        target["text"] = new_text
        if target.get("parent_id"):
            self._save_json(user_id, "reminders.json", reminders)
            return True

        for r in reminders:
            if r.get("id") in related_ids and r.get("id") != reminder_id:
                kind = r.get("advance_kind", "day")
                if kind == "day":
                    r["text"] = f"⚠️ ЗА ДЕНЬ: {new_text}"
                elif kind == "3h":
                    r["text"] = f"⚠️ ЗА 3 ЧАСА: {new_text}"
                elif kind == "1h":
                    r["text"] = f"⚠️ ЗА 1 ЧАС: {new_text}"
        self._save_json(user_id, "reminders.json", reminders)
        return True

    def update_reminder_time(self, user_id, reminder_id, new_date, new_time):
        reminders = self._load_json(user_id, "reminders.json")
        target = next((r for r in reminders if r.get("id") == reminder_id), None)
        if not target:
            return False
        target["date"] = new_date
        target["time"] = new_time
        if target.get("parent_id"):
            self._save_json(user_id, "reminders.json", reminders)
            return True

        related_ids = self._get_related_reminder_ids(reminders, reminder_id)
        for r in reminders:
            if r.get("id") in related_ids and r.get("id") != reminder_id:
                kind = r.get("advance_kind")
                if not kind:
                    continue
                adv_dt = self._get_advance_datetime(new_date, new_time, kind)
                r["date"] = adv_dt.strftime("%Y-%m-%d")
                r["time"] = adv_dt.strftime("%H:%M")
        self._save_json(user_id, "reminders.json", reminders)
        return True

    def update_reminder_advance(self, user_id, reminder_id, advance_type):
        reminders = self._load_json(user_id, "reminders.json")
        parent_id = self.get_parent_reminder_id(reminders, reminder_id)
        if not parent_id:
            return False

        parent = next((r for r in reminders if r.get("id") == parent_id), None)
        if not parent:
            return False

        if not advance_type:
            children = [r for r in reminders if r.get("parent_id") == parent_id and r.get("is_active", True)]
            for child in children:
                child["is_active"] = False
            parent["advance_type"] = None
            self._save_json(user_id, "reminders.json", reminders)
            return True

        adv_dt = self._get_advance_datetime(parent["date"], parent["time"], advance_type)
        local_dt = self.get_user_local_datetime(user_id)
        if adv_dt < local_dt:
            return False

        children = [r for r in reminders if r.get("parent_id") == parent_id and r.get("is_active", True)]
        for child in children:
            child["is_active"] = False

        parent["advance_type"] = advance_type
        next_id = max([r.get("id", 0) for r in reminders], default=0) + 1
        prefix = "⚠️ ЗА ДЕНЬ" if advance_type == "day" else "⚠️ ЗА 3 ЧАСА" if advance_type == "3h" else "⚠️ ЗА 1 ЧАС"
        reminders.append({
            "id": next_id,
            "text": f"{prefix}: {parent['text']}",
            "date": adv_dt.strftime("%Y-%m-%d"),
            "time": adv_dt.strftime("%H:%M"),
            "advance_type": None,
            "advance_kind": advance_type,
            "is_active": True,
            "parent_id": parent_id,
            "created_at": datetime.utcnow().isoformat()
        })
        self._save_json(user_id, "reminders.json", reminders)
        return True

    def get_reminder_by_id(self, user_id, reminder_id):
        reminders = self._load_json(user_id, "reminders.json")
        for r in reminders:
            if r.get("id") == reminder_id:
                return r
        return None

    # === УВЕДОМЛЕНИЯ ===
    def get_reminders_due_now(self):
        all_users = self._get_all_user_folders()
        due = []
        for user_id in all_users:
            reminders = self._load_json(user_id, "reminders.json")
            local_date = self.get_user_local_date(user_id)
            local_time = datetime.utcnow() + timedelta(hours=self.get_user_timezone(user_id))
            local_minute = local_time.strftime("%H:%M")
            for r in reminders:
                if r.get("is_active", True):
                    if r["date"] == local_date and r["time"] == local_minute:
                        due.append((user_id, r))
        return due

    def mark_reminder_sent(self, user_id, reminder_id):
        reminders = self._load_json(user_id, "reminders.json")
        for r in reminders:
            if r.get("id") == reminder_id:
                r["is_active"] = False
                break
        self._save_json(user_id, "reminders.json", reminders)

    # === ОБЪЕДИНЁННЫЙ СПИСОК ЕДЫ И НАПИТКОВ ===
    def get_today_food_and_drinks(self, user_id):
        food = self._load_json(user_id, "food.json")
        drinks = self._load_json(user_id, "drinks.json")
        today = self.get_user_local_date(user_id)
        combined = []
        for f in food:
            if f.get("date") == today:
                combined.append({
                    "type": "🍽 Еда",
                    "time": f.get("time", "00:00"),
                    "text": f"{f['meal_type']}: {f['food_text']}"
                })
        for d in drinks:
            if d.get("date") == today:
                combined.append({
                    "type": "🥤 Напитки",
                    "time": d.get("time", "00:00"),
                    "text": f"{d['drink_type']}: {d['amount']}"
                })
        combined.sort(key=lambda x: x["time"])
        return combined

    def get_today_food(self, user_id):
        food = self._load_json(user_id, "food.json")
        today = self.get_user_local_date(user_id)
        today_food = [f for f in food if f.get("date") == today]
        today_food.sort(key=lambda x: x.get('time', '00:00'))
        return today_food

    def get_today_drinks(self, user_id):
        drinks = self._load_json(user_id, "drinks.json")
        today = self.get_user_local_date(user_id)
        today_drinks = [d for d in drinks if d.get("date") == today]
        today_drinks.sort(key=lambda x: x.get('time', '00:00'))
        return today_drinks

    # === СТАТИСТИКА ===
    def get_stats(self, user_id):
        sleep = self._load_json(user_id, "sleep.json")
        checkins = self._load_json(user_id, "checkins.json")
        food = self._load_json(user_id, "food.json")
        drinks = self._load_json(user_id, "drinks.json")
        notes = self._load_json(user_id, "notes.json")
        reminders = self._load_json(user_id, "reminders.json")

        text = "📊 ТВОЯ СТАТИСТИКА\n\n"
        text += f"😴 Сон: {len(sleep)} записей\n"
        text += f"⚡️ Чек-ины: {len(checkins)} записей\n"
        text += f"🍽 Еда: {len(food)} записей\n"
        text += f"🥤 Напитки: {len(drinks)} записей\n"
        text += f"📝 Заметки: {len(notes)} записей\n"
        text += f"⏰ Напоминания: {len(reminders)} записей\n"

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
            "notes": self._load_json(user_id, "notes.json"),
            "reminders": self._load_json(user_id, "reminders.json")
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

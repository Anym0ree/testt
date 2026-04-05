import sqlite3
import json
import os
import logging
from datetime import datetime, timedelta
from config import DATA_FOLDER

logging.basicConfig(level=logging.INFO)

class Database:
    def __init__(self):
        self.data_folder = DATA_FOLDER
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
        self.db_path = os.path.join(self.data_folder, "bot.db")
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                timezone_offset INTEGER DEFAULT 0,
                created_at TEXT
            )
        ''')
        
        # Таблица сна
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sleep (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                timestamp TEXT,
                bed_time TEXT,
                wake_time TEXT,
                quality INTEGER,
                woke_night INTEGER,
                note TEXT
            )
        ''')
        
        # Таблица чек-инов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                time TEXT,
                timestamp TEXT,
                time_slot TEXT,
                energy INTEGER,
                stress INTEGER,
                emotions TEXT,
                note TEXT
            )
        ''')
        
        # Таблица итогов дня
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS day_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                timestamp TEXT,
                score INTEGER,
                best TEXT,
                worst TEXT,
                gratitude TEXT,
                note TEXT
            )
        ''')
        
        # Таблица еды
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS food (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                time TEXT,
                timestamp TEXT,
                meal_type TEXT,
                food_text TEXT
            )
        ''')
        
        # Таблица напитков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS drinks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                time TEXT,
                timestamp TEXT,
                drink_type TEXT,
                amount TEXT
            )
        ''')
        
        # Таблица заметок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                date TEXT,
                time TEXT,
                timestamp TEXT
            )
        ''')
        
        # Таблица напоминаний
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                date TEXT,
                time TEXT,
                advance_type TEXT,
                parent_id INTEGER,
                is_custom INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

    # === ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===
    def get_user_timezone(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT timezone_offset FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0

    def set_user_timezone(self, user_id, timezone_offset):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, timezone_offset, created_at)
            VALUES (?, ?, COALESCE((SELECT created_at FROM users WHERE user_id = ?), ?))
        ''', (user_id, timezone_offset, user_id, datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()

    def get_user_local_datetime(self, user_id):
        offset = self.get_user_timezone(user_id)
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=offset)

    def get_user_local_date(self, user_id):
        return self.get_user_local_datetime(user_id).strftime("%Y-%m-%d")

    def get_user_local_hour(self, user_id):
        return self.get_user_local_datetime(user_id).hour

    # === СОН ===
    def has_sleep_today(self, user_id):
        today = self.get_user_local_date(user_id)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM sleep WHERE user_id = ? AND date = ? LIMIT 1", (user_id, today))
        result = cursor.fetchone() is not None
        conn.close()
        return result

    def add_sleep(self, user_id, bed_time, wake_time, quality, woke_night, note=""):
        if self.has_sleep_today(user_id):
            return False
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sleep (user_id, date, timestamp, bed_time, wake_time, quality, woke_night, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, self.get_user_local_date(user_id), datetime.utcnow().isoformat(),
              bed_time, wake_time, quality, 1 if woke_night else 0, note))
        conn.commit()
        conn.close()
        return True

    # === ЧЕК-ИН ===
    def add_checkin(self, user_id, time_slot, energy, stress, emotions, note=""):
        conn = self._get_connection()
        cursor = conn.cursor()
        local_dt = self.get_user_local_datetime(user_id)
        cursor.execute('''
            INSERT INTO checkins (user_id, date, time, timestamp, time_slot, energy, stress, emotions, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, local_dt.strftime("%Y-%m-%d"), local_dt.strftime("%H:%M"),
              datetime.utcnow().isoformat(), time_slot, energy, stress, json.dumps(emotions, ensure_ascii=False), note))
        conn.commit()
        conn.close()
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
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM day_summary WHERE user_id = ? AND date = ? LIMIT 1", (user_id, date_str))
        result = cursor.fetchone() is not None
        conn.close()
        return result

    def add_day_summary(self, user_id, score, best, worst, gratitude, note=""):
        target_date = self.get_target_date_for_summary(user_id)
        if target_date is None or self.has_day_summary_for_date(user_id, target_date):
            return False
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO day_summary (user_id, date, timestamp, score, best, worst, gratitude, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, target_date, datetime.utcnow().isoformat(), score, best, worst, gratitude, note))
        conn.commit()
        conn.close()
        return True

    # === ЕДА ===
    def add_food(self, user_id, meal_type, food_text):
        conn = self._get_connection()
        cursor = conn.cursor()
        local_dt = self.get_user_local_datetime(user_id)
        cursor.execute('''
            INSERT INTO food (user_id, date, time, timestamp, meal_type, food_text)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, local_dt.strftime("%Y-%m-%d"), local_dt.strftime("%H:%M"),
              datetime.utcnow().isoformat(), meal_type, food_text))
        conn.commit()
        conn.close()
        return True

    # === НАПИТКИ ===
    def add_drink(self, user_id, drink_type, amount):
        conn = self._get_connection()
        cursor = conn.cursor()
        local_dt = self.get_user_local_datetime(user_id)
        cursor.execute('''
            INSERT INTO drinks (user_id, date, time, timestamp, drink_type, amount)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, local_dt.strftime("%Y-%m-%d"), local_dt.strftime("%H:%M"),
              datetime.utcnow().isoformat(), drink_type, amount))
        conn.commit()
        conn.close()
        return True

    # === ЗАМЕТКИ ===
    def add_note(self, user_id, text):
        conn = self._get_connection()
        cursor = conn.cursor()
        local_dt = self.get_user_local_datetime(user_id)
        cursor.execute('''
            INSERT INTO notes (user_id, text, date, time, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, text, local_dt.strftime("%Y-%m-%d"), local_dt.strftime("%H:%M"),
              datetime.utcnow().isoformat()))
        conn.commit()
        note_id = cursor.lastrowid
        conn.close()
        return note_id

    def get_notes(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, text, date, time, timestamp FROM notes WHERE user_id = ? ORDER BY id DESC", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{"id": r[0], "text": r[1], "date": r[2], "time": r[3], "timestamp": r[4]} for r in rows]

    def delete_note_by_id(self, user_id, note_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE user_id = ? AND id = ?", (user_id, note_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    # === НАПОМИНАНИЯ ===
    def add_reminder(self, user_id, text, target_date, target_time, advance_type=None, parent_id=None, is_custom=False):
        local_dt = self.get_user_local_datetime(user_id)
        target_dt = datetime.strptime(f"{target_date} {target_time}", "%Y-%m-%d %H:%M")
        if target_dt < local_dt:
            return None
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reminders (user_id, text, date, time, advance_type, parent_id, is_custom, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, text, target_date, target_time, advance_type, parent_id, 1 if is_custom else 0,
              datetime.utcnow().isoformat()))
        conn.commit()
        reminder_id = cursor.lastrowid
        conn.close()
        return reminder_id

    def get_active_reminders(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, text, date, time, advance_type, parent_id, is_custom
            FROM reminders WHERE user_id = ? AND is_active = 1
            ORDER BY date, time
        ''', (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{"id": r[0], "text": r[1], "date": r[2], "time": r[3],
                 "advance_type": r[4], "parent_id": r[5], "is_custom": r[6]} for r in rows]

    def delete_reminder(self, user_id, reminder_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE reminders SET is_active = 0 WHERE user_id = ? AND (id = ? OR parent_id = ?)",
                      (user_id, reminder_id, reminder_id))
        conn.commit()
        conn.close()
        return True

    def get_reminders_due_now(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        due = []
        # Получаем всех пользователей с активными напоминаниями
        cursor.execute("SELECT DISTINCT user_id FROM reminders WHERE is_active = 1")
        users = cursor.fetchall()
        for (user_id,) in users:
            local_dt = self.get_user_local_datetime(user_id)
            local_date = local_dt.strftime("%Y-%m-%d")
            local_minute = local_dt.strftime("%H:%M")
            cursor.execute('''
                SELECT id, text FROM reminders
                WHERE user_id = ? AND is_active = 1 AND date = ? AND time = ?
            ''', (user_id, local_date, local_minute))
            reminders = cursor.fetchall()
            for r in reminders:
                due.append((user_id, {"id": r[0], "text": r[1]}))
        conn.close()
        return due

    def mark_reminder_sent(self, user_id, reminder_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE reminders SET is_active = 0 WHERE user_id = ? AND id = ?", (user_id, reminder_id))
        conn.commit()
        conn.close()

    # === ОБЪЕДИНЁННЫЙ СПИСОК ЕДЫ И НАПИТКОВ ===
    def get_today_food_and_drinks(self, user_id):
        today = self.get_user_local_date(user_id)
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT time, meal_type, food_text FROM food WHERE user_id = ? AND date = ?", (user_id, today))
        food_rows = cursor.fetchall()
        
        cursor.execute("SELECT time, drink_type, amount FROM drinks WHERE user_id = ? AND date = ?", (user_id, today))
        drink_rows = cursor.fetchall()
        
        conn.close()
        
        combined = []
        for r in food_rows:
            combined.append({"type": "🍽 Еда", "time": r[0], "text": f"{r[1]}: {r[2]}"})
        for r in drink_rows:
            combined.append({"type": "🥤 Напитки", "time": r[0], "text": f"{r[1]}: {r[2]}"})
        combined.sort(key=lambda x: x["time"])
        return combined

    # === СТАТИСТИКА ===
    def get_stats(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM sleep WHERE user_id = ?", (user_id,))
        sleep_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM checkins WHERE user_id = ?", (user_id,))
        checkins_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM food WHERE user_id = ?", (user_id,))
        food_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM drinks WHERE user_id = ?", (user_id,))
        drinks_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM notes WHERE user_id = ?", (user_id,))
        notes_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reminders WHERE user_id = ? AND is_active = 1", (user_id,))
        reminders_count = cursor.fetchone()[0]
        
        # Последний сон
        cursor.execute('''
            SELECT bed_time, wake_time, quality FROM sleep
            WHERE user_id = ? ORDER BY id DESC LIMIT 1
        ''', (user_id,))
        last_sleep = cursor.fetchone()
        
        # Последний чек-ин
        cursor.execute('''
            SELECT energy, stress, emotions FROM checkins
            WHERE user_id = ? ORDER BY id DESC LIMIT 1
        ''', (user_id,))
        last_checkin = cursor.fetchone()
        
        conn.close()
        
        text = f"📊 ТВОЯ СТАТИСТИКА\n\n"
        text += f"😴 Сон: {sleep_count} записей\n"
        text += f"⚡️ Чек-ины: {checkins_count} записей\n"
        text += f"🍽 Еда: {food_count} записей\n"
        text += f"🥤 Напитки: {drinks_count} записей\n"
        text += f"📝 Заметки: {notes_count} записей\n"
        text += f"⏰ Активных напоминаний: {reminders_count}\n"
        
        if last_sleep:
            text += f"\n😴 Последний сон:\n   Лег: {last_sleep[0]}, встал: {last_sleep[1]}\n   Качество: {last_sleep[2]}/10"
        if last_checkin:
            emotions = json.loads(last_checkin[2]) if last_checkin[2] else []
            emotions_str = ", ".join(emotions) or "не указаны"
            text += f"\n\n⚡️ Последний чек-ин:\n   Энергия: {last_checkin[0]}/10, стресс: {last_checkin[1]}/10\n   Эмоции: {emotions_str}"
        
        return text

    # === ЭКСПОРТ ===
    def export_all(self, user_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        export_data = {
            "user_id": user_id,
            "export_date": datetime.utcnow().isoformat(),
            "sleep": [],
            "checkins": [],
            "day_summary": [],
            "food": [],
            "drinks": [],
            "notes": [],
            "reminders": []
        }
        
        cursor.execute("SELECT date, bed_time, wake_time, quality, woke_night, note FROM sleep WHERE user_id = ?", (user_id,))
        for row in cursor.fetchall():
            export_data["sleep"].append({"date": row[0], "bed_time": row[1], "wake_time": row[2],
                                         "quality": row[3], "woke_night": bool(row[4]), "note": row[5]})
        
        cursor.execute("SELECT date, time, time_slot, energy, stress, emotions, note FROM checkins WHERE user_id = ?", (user_id,))
        for row in cursor.fetchall():
            export_data["checkins"].append({"date": row[0], "time": row[1], "time_slot": row[2],
                                            "energy": row[3], "stress": row[4],
                                            "emotions": json.loads(row[5]) if row[5] else [], "note": row[6]})
        
        cursor.execute("SELECT date, score, best, worst, gratitude, note FROM day_summary WHERE user_id = ?", (user_id,))
        for row in cursor.fetchall():
            export_data["day_summary"].append({"date": row[0], "score": row[1], "best": row[2],
                                               "worst": row[3], "gratitude": row[4], "note": row[5]})
        
        cursor.execute("SELECT date, time, meal_type, food_text FROM food WHERE user_id = ?", (user_id,))
        for row in cursor.fetchall():
            export_data["food"].append({"date": row[0], "time": row[1], "meal_type": row[2], "food_text": row[3]})
        
        cursor.execute("SELECT date, time, drink_type, amount FROM drinks WHERE user_id = ?", (user_id,))
        for row in cursor.fetchall():
            export_data["drinks"].append({"date": row[0], "time": row[1], "drink_type": row[2], "amount": row[3]})
        
        cursor.execute("SELECT text, date, time, timestamp FROM notes WHERE user_id = ?", (user_id,))
        for row in cursor.fetchall():
            export_data["notes"].append({"text": row[0], "date": row[1], "time": row[2], "timestamp": row[3]})
        
        cursor.execute("SELECT text, date, time, advance_type, parent_id, is_custom FROM reminders WHERE user_id = ? AND is_active = 1", (user_id,))
        for row in cursor.fetchall():
            export_data["reminders"].append({"text": row[0], "date": row[1], "time": row[2],
                                             "advance_type": row[3], "parent_id": row[4], "is_custom": bool(row[5])})
        
        conn.close()
        
        file_path = os.path.join(self.data_folder, str(user_id), "export_all.json")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return file_path

    # === ДЛЯ AI СОВЕТА (загрузка всех данных) ===
    def _load_json(self, user_id, filename):
        """Совместимость со старым кодом AI"""
        # Этот метод нужен только для AIAdvisor, который ожидает JSON
        # Возвращаем данные из SQLite в том же формате
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if filename == "sleep.json":
            cursor.execute("SELECT date, bed_time, wake_time, quality, woke_night, note FROM sleep WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [{"date": r[0], "bed_time": r[1], "wake_time": r[2], "quality": r[3], "woke_night": bool(r[4]), "note": r[5]} for r in rows]
        
        elif filename == "checkins.json":
            cursor.execute("SELECT date, time, energy, stress, emotions, note FROM checkins WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [{"date": r[0], "time": r[1], "energy": r[2], "stress": r[3], "emotions": json.loads(r[4]) if r[4] else [], "note": r[5]} for r in rows]
        
        elif filename == "day_summary.json":
            cursor.execute("SELECT date, score, best, worst, gratitude, note FROM day_summary WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [{"date": r[0], "score": r[1], "best": r[2], "worst": r[3], "gratitude": r[4], "note": r[5]} for r in rows]
        
        elif filename == "notes.json":
            cursor.execute("SELECT id, text, date, time, timestamp FROM notes WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [{"id": r[0], "text": r[1], "date": r[2], "time": r[3], "timestamp": r[4]} for r in rows]
        
        elif filename == "reminders.json":
            cursor.execute("SELECT id, text, date, time, advance_type, parent_id, is_custom, is_active, created_at FROM reminders WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [{"id": r[0], "text": r[1], "date": r[2], "time": r[3], "advance_type": r[4],
                     "parent_id": r[5], "is_custom": bool(r[6]), "is_active": bool(r[7]), "created_at": r[8]} for r in rows]
        
        elif filename == "food.json":
            cursor.execute("SELECT date, time, meal_type, food_text FROM food WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [{"date": r[0], "time": r[1], "meal_type": r[2], "food_text": r[3]} for r in rows]
        
        elif filename == "drinks.json":
            cursor.execute("SELECT date, time, drink_type, amount FROM drinks WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [{"date": r[0], "time": r[1], "drink_type": r[2], "amount": r[3]} for r in rows]
        
        return []
    # === ДЛЯ НОВЫХ КНОПОК ===
    def get_note_by_id(self, user_id, note_id):
        """Получить заметку по ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, text, date, time FROM notes WHERE user_id = ? AND id = ?", (user_id, note_id))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"id": row[0], "text": row[1], "date": row[2], "time": row[3]}
        return None
    
    def get_reminder_by_id(self, user_id, reminder_id):
        """Получить напоминание по ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, text, date, time FROM reminders 
            WHERE user_id = ? AND id = ? AND is_active = 1
        ''', (user_id, reminder_id))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"id": row[0], "text": row[1], "date": row[2], "time": row[3]}
        return None
    
    def edit_note(self, user_id, note_id, new_text):
        """Редактировать заметку"""
        conn = self._get_connection()
        cursor = conn.cursor()
        local_dt = self.get_user_local_datetime(user_id)
        cursor.execute('''
            UPDATE notes 
            SET text = ?, date = ?, time = ?, timestamp = ?
            WHERE user_id = ? AND id = ?
        ''', (new_text, local_dt.strftime("%Y-%m-%d"), local_dt.strftime("%H:%M"),
              datetime.utcnow().isoformat(), user_id, note_id))
        conn.commit()
        conn.close()
        return True
db = Database()

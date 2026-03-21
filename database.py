# === НАПОМИНАНИЯ ===
def add_reminder(self, user_id, text, target_date, target_time, advance_type=None):
    """Добавляет напоминание. advance_type: 'day', '3h', '1h' или None"""
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

    # Если есть предварительное напоминание, создаём его
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
    """Вычисляет дату предварительного напоминания"""
    from datetime import datetime, timedelta
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
    """Возвращает активные напоминания"""
    reminders = self._load_json(user_id, "reminders.json")
    return [r for r in reminders if r.get("is_active", True)]

def delete_reminder(self, user_id, reminder_id):
    """Удаляет напоминание (мягкое удаление)"""
    reminders = self._load_json(user_id, "reminders.json")
    for r in reminders:
        if r.get("id") == reminder_id:
            r["is_active"] = False
            break
    self._save_json(user_id, "reminders.json", reminders)
    return True

def update_reminder_text(self, user_id, reminder_id, new_text):
    """Обновляет текст напоминания"""
    reminders = self._load_json(user_id, "reminders.json")
    for r in reminders:
        if r.get("id") == reminder_id:
            r["text"] = new_text
            break
    self._save_json(user_id, "reminders.json", reminders)
    return True

def get_reminder_by_id(self, user_id, reminder_id):
    """Возвращает напоминание по ID"""
    reminders = self._load_json(user_id, "reminders.json")
    for r in reminders:
        if r.get("id") == reminder_id:
            return r
    return None
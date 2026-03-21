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

    # ... все остальные методы (add_sleep, add_checkin и т.д.) остаются без изменений ...

    def reset_user_data(self, user_id):
        """Удаляет все данные пользователя"""
        user_folder = self._get_user_folder(user_id)
        if os.path.exists(user_folder):
            for filename in os.listdir(user_folder):
                file_path = os.path.join(user_folder, filename)
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            # удаляем саму папку (опционально)
            try:
                os.rmdir(user_folder)
            except Exception:
                pass
            return True
        return False

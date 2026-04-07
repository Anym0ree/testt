import loggingimport aiohttp
import logging
from typing import Dict, Optional, List
import json

class AIAdvisor:
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile", base_url: str = "https://api.groq.com/openai/v1/chat/completions"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.user_context = {}

    def set_user_data(self, user_id: int, data: Dict):
        self.user_context[user_id] = data

    def get_user_data(self, user_id: int) -> Optional[Dict]:
        return self.user_context.get(user_id)

    def clear_user_data(self, user_id: int):
        self.user_context.pop(user_id, None)

    async def get_advice(self, user_id: int, user_question: Optional[str] = None, history: Optional[List[Dict]] = None) -> str:
        if not self.api_key:
            return ("❌ AI-модуль не настроен.\n"
                    "Добавьте API-ключ Groq в config.py (переменная OPENAI_API_KEY).\n"
                    "Получить ключ можно бесплатно на https://console.groq.com/ после регистрации.")

        user_data = self.get_user_data(user_id)
        if not user_data:
            return "⚠️ Данные для анализа не найдены. Пожалуйста, сначала нажмите «🤖 AI-совет» из главного меню."

        # Новый системный промпт — живой, увлекательный, с фактами и предложением диалога
        system_prompt = (
            "Ты — заботливый, остроумный и вдохновляющий AI-коуч по саморазвитию. "
            "Твоя задача: анализировать данные пользователя (сон, чек-ины, итоги дня, заметки, еда, напитки) и выдавать "
            "не сухую статистику, а увлекательный, живой рассказ. Перечисляй ключевые аспекты плавно, с интригой. "
            "Обязательно добавь 1-2 интересных научных факта, связанных со сном, энергией, питанием или стрессом, "
            "чтобы пользователь узнал что-то новое. В конце всегда напоминай: «Можешь спросить меня о чём угодно — "
            "поговорим о твоих привычках, питании или просто поболтаем 😊». Предлагай конкретные темы для обсуждения. "
            "Отвечай на русском, тепло, с эмпатией, но без излишней слащавости. Старайся удивить полезным фактом."
        )

        user_summary = self._format_user_data(user_data)

        # Формируем сообщения с учётом истории и вопроса
        if history:
            # Восстанавливаем диалог, но системный промпт добавляем в начало
            messages = [{"role": "system", "content": system_prompt}]
            # Пропускаем, если в истории уже был system (чтобы избежать дублей)
            for msg in history:
                if msg.get("role") != "system":
                    messages.append(msg)
            if user_question:
                messages.append({"role": "user", "content": user_question})
            else:
                # Если вопрос не задан, но есть история — просто просим продолжить анализ
                messages.append({"role": "user", "content": "Продолжим анализ. Что скажешь ещё?"})
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Вот мои данные за последнее время:\n{user_summary}\n\nПожалуйста, дай интересный, живой обзор с фактами и советами, а в конце предложи поговорить подробнее."}
            ]
            if user_question:
                # Если есть вопрос и нет истории, просто добавляем вопрос
                messages.append({"role": "user", "content": user_question})

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.85,  # чуть выше креативность
                "max_tokens": 1200,
                "top_p": 0.95
            }
            try:
                async with session.post(self.base_url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result["choices"][0]["message"]["content"]
                    else:
                        error_text = await resp.text()
                        logging.error(f"AI API error {resp.status}: {error_text}")
                        return f"⚠️ Ошибка AI-сервиса (код {resp.status}). Попробуйте позже."
            except Exception as e:
                logging.error(f"AI request failed: {e}")
                return "⚠️ Не удалось связаться с AI-сервисом. Проверьте интернет и настройки."

    def _format_user_data(self, data: Dict) -> str:
        """Форматирует все данные пользователя в читаемый текст для AI."""
        lines = []

        # Сон
        sleep = data.get("sleep", [])
        if sleep:
            lines.append("📊 СОН (последние записи):")
            for s in sleep[-10:]:
                lines.append(f"  • {s.get('date')}: лёг в {s.get('bed_time')}, встал в {s.get('wake_time')}, качество {s.get('quality')}/10, ночные пробуждения: {'да' if s.get('woke_night') else 'нет'}")
                if s.get('note'):
                    lines.append(f"       заметка: {s['note'][:100]}")
        else:
            lines.append("📊 Данные о сне отсутствуют.")

        # Чек-ины (энергия, стресс, эмоции, заметки)
        checkins = data.get("checkins", [])
        if checkins:
            lines.append("\n⚡️ ЧЕК-ИНЫ (последние):")
            for c in checkins[-10:]:
                emotions = ', '.join(c.get('emotions', [])) or 'не указаны'
                lines.append(f"  • {c.get('date')} {c.get('time')}: энергия {c.get('energy')}/10, стресс {c.get('stress')}/10, эмоции: {emotions}")
                if c.get('note'):
                    lines.append(f"       заметка: {c['note'][:100]}")
        else:
            lines.append("\n⚡️ Чек-ины отсутствуют.")

        # Итоги дня
        summaries = data.get("day_summary", [])
        if summaries:
            lines.append("\n📝 ИТОГИ ДНЯ (последние):")
            for s in summaries[-10:]:
                lines.append(f"  • {s.get('date')}: оценка {s.get('score')}/10, лучшее: {s.get('best') or '—'}, сложное: {s.get('worst') or '—'}")
                if s.get('note'):
                    lines.append(f"       заметка: {s['note'][:100]}")
        else:
            lines.append("\n📝 Итоги дня отсутствуют.")

        # Заметки (общие)
        notes = data.get("notes", [])
        if notes:
            lines.append("\n📋 ОБЩИЕ ЗАМЕТКИ (последние):")
            for n in notes[-7:]:
                lines.append(f"  • {n.get('date')}: {n.get('text')[:120]}{'...' if len(n.get('text', '')) > 120 else ''}")

        # Еда
        food = data.get("food", [])
        if food:
            lines.append("\n🍽 ЕДА (последние записи):")
            for f in food[-10:]:
                lines.append(f"  • {f.get('date')} {f.get('time')}: {f.get('meal_type')} — {f.get('food_text')[:100]}")
        else:
            lines.append("\n🍽 Данные о еде отсутствуют.")

        # Напитки
        drinks = data.get("drinks", [])
        if drinks:
            lines.append("\n🥤 НАПИТКИ (последние записи):")
            for d in drinks[-10:]:
                lines.append(f"  • {d.get('date')} {d.get('time')}: {d.get('drink_type')} — {d.get('amount')}")
        else:
            lines.append("\n🥤 Данные о напитках отсутствуют.")

        # Активные напоминания
        reminders = data.get("reminders", [])
        active_reminders = [r for r in reminders if r.get('is_active')]
        if active_reminders:
            lines.append("\n⏰ АКТИВНЫЕ НАПОМИНАНИЯ:")
            for r in active_reminders[-5:]:
                lines.append(f"  • {r.get('date')} {r.get('time')}: {r.get('text')[:80]}")

        # Добавляем заметки из чек-инов и итогов дня уже включены выше, но для полноты можно вывести отдельно все заметки из разных источников
        # Собираем все заметки из всех опросов (сон, чек-ин, итог дня) в одном месте
        all_notes = []
        for s in sleep:
            if s.get('note'):
                all_notes.append(("сон", s.get('date'), s['note']))
        for c in checkins:
            if c.get('note'):
                all_notes.append(("чек-ин", c.get('date'), c['note']))
        for s in summaries:
            if s.get('note'):
                all_notes.append(("итог дня", s.get('date'), s['note']))
        if all_notes:
            lines.append("\n📌 ЗАМЕТКИ ИЗ ОПРОСОВ (сон, чек-ин, итог дня):")
            for src, date, note in all_notes[-10:]:
                lines.append(f"  • [{src}] {date}: {note[:120]}")

        return "\n".join(lines)
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)



class AIAdvisor:
    def __init__(self, api_key: str):
        """Инициализация Groq клиента."""
        # Указываем правильный адрес для Groq API
        self.client = AsyncOpenAI(
            base_url="https://api.groq.com/openai/v1",  # <-- Адрес Groq
            api_key=api_key,
        )
        self.model = "llama-3.1-8b-instant"  # <-- Модель Groq
    def set_user_data(self, user_id: int, data: Dict):
        self.user_context[user_id] = data

    def get_user_data(self, user_id: int) -> Optional[Dict]:
        return self.user_context.get(user_id)

    def clear_user_data(self, user_id: int):
        self.user_context.pop(user_id, None)

    async def get_advice(self, user_id: int, question: str = None, history: list = None) -> str:
        try:
            if question is None:
                user_data = self.get_user_data(user_id)
                prompt = f"Вот данные пользователя за последние дни:\n{user_data}\n\nНа основе этих данных дай общий совет по улучшению самочувствия и продуктивности."
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            else:
                if history is None:
                    user_data = self.get_user_data(user_id)
                    prompt = f"Вот данные пользователя за последние дни:\n{user_data}\n\nВопрос пользователя: {question}"
                    messages = [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ]
                else:
                    messages = history
                    messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Ошибка Groq API: {e}")
            return f"⚠️ Ошибка AI-сервиса ({e}). Попробуйте позже."

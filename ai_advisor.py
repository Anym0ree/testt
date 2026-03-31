import aiohttp
import logging
from typing import Dict, Optional

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

    async def get_advice(self, user_id: int, user_question: Optional[str] = None) -> str:
        if not self.api_key:
            return ("❌ AI-модуль не настроен.\n"
                    "Добавьте API-ключ DeepSeek в config.py (переменная OPENAI_API_KEY).\n"
                    "Получить ключ можно бесплатно на https://platform.deepseek.com/ после регистрации.")

        user_data = self.get_user_data(user_id)
        if not user_data:
            return "⚠️ Данные для анализа не найдены. Пожалуйста, сначала нажмите «🤖 AI-совет» из главного меню."

        system_prompt = (
            "Ты — дружелюбный и заботливый AI-коуч по саморазвитию. "
            "На основе предоставленных данных о сне, энергии, стрессе, эмоциях, итогах дня и заметках "
            "давай пользователю конкретные, полезные советы для улучшения самочувствия, продуктивности и настроения. "
            "Также можешь подмечать интересные факты из данных, задавать уточняющие вопросы, поддерживать диалог. "
            "Отвечай структурированно, но живо, без излишней воды. Если данных недостаточно, предложи вести записи регулярнее."
        )

        user_summary = self._format_user_data(user_data)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Вот мои данные за последнее время:\n{user_summary}"}
        ]
        if user_question:
            messages.append({"role": "user", "content": user_question})
        else:
            messages.append({"role": "user", "content": "Пожалуйста, дай общий анализ моего состояния и практические советы."})

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1000
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
        lines = []

        sleep = data.get("sleep", [])
        if sleep:
            lines.append("📊 СОН (последние записи):")
            for s in sleep[-10:]:
                lines.append(f"  • {s.get('date')}: лёг в {s.get('bed_time')}, встал в {s.get('wake_time')}, качество {s.get('quality')}/10, ночные пробуждения: {'да' if s.get('woke_night') else 'нет'}")
        else:
            lines.append("📊 Данные о сне отсутствуют.")

        checkins = data.get("checkins", [])
        if checkins:
            lines.append("\n⚡️ ЧЕК-ИНЫ (последние):")
            for c in checkins[-10:]:
                emotions = ', '.join(c.get('emotions', [])) or 'не указаны'
                lines.append(f"  • {c.get('date')} {c.get('time')}: энергия {c.get('energy')}/10, стресс {c.get('stress')}/10, эмоции: {emotions}")
                if c.get('note'):
                    lines.append(f"       заметка: {c['note'][:80]}")
        else:
            lines.append("\n⚡️ Чек-ины отсутствуют.")

        summaries = data.get("day_summary", [])
        if summaries:
            lines.append("\n📝 ИТОГИ ДНЯ (последние):")
            for s in summaries[-10:]:
                lines.append(f"  • {s.get('date')}: оценка {s.get('score')}/10, лучшее: {s.get('best') or '—'}, сложное: {s.get('worst') or '—'}")
                if s.get('note'):
                    lines.append(f"       заметка: {s['note'][:80]}")
        else:
            lines.append("\n📝 Итоги дня отсутствуют.")

        notes = data.get("notes", [])
        if notes:
            lines.append("\n📋 ЗАМЕТКИ (последние):")
            for n in notes[-7:]:
                lines.append(f"  • {n.get('date')}: {n.get('text')[:100]}{'...' if len(n.get('text', '')) > 100 else ''}")

        reminders = data.get("reminders", [])
        active_reminders = [r for r in reminders if r.get('is_active')]
        if active_reminders:
            lines.append("\n⏰ АКТИВНЫЕ НАПОМИНАНИЯ:")
            for r in active_reminders[-5:]:
                lines.append(f"  • {r.get('date')} {r.get('time')}: {r.get('text')[:70]}")

        return "\n".join(lines)

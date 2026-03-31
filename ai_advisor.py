import aiohttp
import logging
from typing import Dict, Optional

class AIAdvisor:
    """Класс для получения AI-советов через DeepSeek/Groq API (OpenAI-совместимый)."""

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

    async def get_advice(self, user_id: int, user_data: Dict, user_question: Optional[str] = None) -> str:
        if not self.api_key:
            return "❌ API-ключ не задан. Добавьте OPENAI_API_KEY в переменные окружения."

        user_data = self.get_user_data(user_id)
        if not user_data:
            return "⚠️ Данные для анализа не найдены. Нажмите «🤖 AI-совет» из главного меню."

        system_prompt = (
            "Ты — дружелюбный AI-коуч по саморазвитию. "
            "На основе данных о сне, энергии, стрессе, эмоциях, итогах дня и заметках "
            "давай пользователю конкретные, полезные советы для улучшения самочувствия, продуктивности и настроения. "
            "Подмечай интересные факты из данных, поддерживай диалог. Отвечай структурированно, живо, без воды."
        )

        user_summary = self._format_user_data(user_data)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Вот мои данные:\n{user_summary}"}
        ]
        if user_question:
            messages.append({"role": "user", "content": user_question})
        else:
            messages.append({"role": "user", "content": "Дай общий анализ моего состояния и практические советы."})

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
                        return f"⚠️ Ошибка API (код {resp.status}). Проверьте ключ и лимиты."
            except Exception as e:
                logging.error(f"AI request failed: {e}")
                return "⚠️ Не удалось связаться с AI-сервисом. Проверьте интернет."

    def _format_user_data(self, data: Dict) -> str:
        lines = []
        sleep = data.get("sleep", [])
        if sleep:
            lines.append("СОН (последние):")
            for s in sleep[-10:]:
                lines.append(f"  • {s.get('date')}: лёг {s.get('bed_time')}, встал {s.get('wake_time')}, качество {s.get('quality')}/10, ночные пробуждения: {'да' if s.get('woke_night') else 'нет'}")
        else:
            lines.append("Данные о сне отсутствуют.")

        checkins = data.get("checkins", [])
        if checkins:
            lines.append("\nЧЕК-ИНЫ (последние):")
            for c in checkins[-10:]:
                emotions = ', '.join(c.get('emotions', [])) or 'не указаны'
                lines.append(f"  • {c.get('date')} {c.get('time')}: энергия {c.get('energy')}/10, стресс {c.get('stress')}/10, эмоции: {emotions}")
                if c.get('note'):
                    lines.append(f"       заметка: {c['note'][:80]}")
        else:
            lines.append("\nЧек-ины отсутствуют.")

        summaries = data.get("day_summary", [])
        if summaries:
            lines.append("\nИТОГИ ДНЯ (последние):")
            for s in summaries[-10:]:
                lines.append(f"  • {s.get('date')}: оценка {s.get('score')}/10, лучшее: {s.get('best') or '—'}, сложное: {s.get('worst') or '—'}")
                if s.get('note'):
                    lines.append(f"       заметка: {s['note'][:80]}")

        notes = data.get("notes", [])
        if notes:
            lines.append("\nЗАМЕТКИ (последние):")
            for n in notes[-7:]:
                lines.append(f"  • {n.get('date')}: {n.get('text')[:100]}{'...' if len(n.get('text', '')) > 100 else ''}")

        return "\n".join(lines)

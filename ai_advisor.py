import logging
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

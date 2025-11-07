"""
Интеграция с YandexGPT API.
"""
import os
import logging
import requests
from typing import List, Optional
from dotenv import load_dotenv

from .base import BaseLLM, Message

load_dotenv()
logger = logging.getLogger(__name__)


class YandexGPT(BaseLLM):
    """Клиент для работы с YandexGPT API"""
    
    API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    
    def __init__(
        self, 
        api_key: str = None, 
        folder_id: str = None,
        model: str = "yandexgpt-lite"
    ):
        """
        Args:
            api_key: API ключ (или из .env)
            folder_id: ID каталога (или из .env)
            model: Модель ("yandexgpt-lite" или "yandexgpt")
        """
        self.api_key = api_key or os.getenv("YANDEX_API_KEY")
        self.folder_id = folder_id or os.getenv("YANDEX_FOLDER_ID")
        self.model = model
        
        if not self.api_key:
            raise ValueError("YANDEX_API_KEY не найден в .env!")
        if not self.folder_id:
            raise ValueError("YANDEX_FOLDER_ID не найден в .env!")
        
        self.model_uri = f"gpt://{self.folder_id}/{self.model}/latest"
        logger.info(f"✅ YandexGPT инициализирован. Модель: {self.model}")
    
    def generate(
        self, 
        messages: List[Message], 
        temperature: float = 0.6,
        max_tokens: int = 2000
    ) -> str:
        """
        Генерирует ответ на основе истории сообщений
        """
        # Формируем запрос
        yandex_messages = [
            {"role": msg.role, "text": msg.content}
            for msg in messages
        ]
        
        payload = {
            "modelUri": self.model_uri,
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": str(max_tokens)
            },
            "messages": yandex_messages
        }
        
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Отправка запроса к YandexGPT ({len(messages)} сообщений)...")
        
        try:
            response = requests.post(
                self.API_URL, 
                json=payload, 
                headers=headers,
                timeout=30
            )
            
            # Логирование ошибки
            if response.status_code != 200:
                logger.error(f"Ответ API (код {response.status_code}): {response.text}")
            
            response.raise_for_status()
            
            result = response.json()
            answer = result["result"]["alternatives"][0]["message"]["text"]
            
            logger.info(f"✅ Получен ответ от YandexGPT ({len(answer)} символов)")
            return answer
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Ошибка при запросе к YandexGPT: {e}")
            raise
    
    def generate_with_context(
        self,
        query: str,
        context: str,
        temperature: float = 0.6,
        max_tokens: int = 2000
    ) -> str:
        """
        Генерирует ответ с учётом контекста (для RAG)
        """
        # Создаём промпт для RAG
        system_prompt = (
            "Ты — умный помощник приёмной комиссии университета. "
            "Твоя задача — отвечать на вопросы о поступлении, используя предоставленные документы.\n\n"
            "ВАЖНО:\n"
            "1. Отвечай только на основе предоставленного контекста\n"
            "2. Если информации нет в контексте — так и скажи\n"
            "3. Указывай источники (название документа, страницу)\n"
            "4. Структурируй ответ (используй списки, заголовки)\n"
            "5. Будь конкретным и точным\n\n"
            f"КОНТЕКСТ ИЗ ДОКУМЕНТОВ:\n{context}\n\n"
            f"ВОПРОС ПОЛЬЗОВАТЕЛЯ:\n{query}"
        )
        
        messages = [
            Message(role="user", content=system_prompt)
        ]
        
        return self.generate(messages, temperature, max_tokens)


# === ТЕСТИРОВАНИЕ ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Простой тест
    llm = YandexGPT()
    
    # Тест 1: Простой диалог
    print("\n" + "="*50)
    print("ТЕСТ 1: Простой диалог")
    print("="*50)
    
    messages = [
        Message(role="user", content="Привет! Как дела?")
    ]
    
    response = llm.generate(messages)
    print(f"Ответ: {response}")
    
    # Тест 2: RAG
    print("\n" + "="*50)
    print("ТЕСТ 2: Ответ с контекстом")
    print("="*50)
    
    test_context = """
    Документ: Правила приёма 2025
    Страница: 15
    
    Для поступления необходимы следующие документы:
    1. Паспорт или иной документ, удостоверяющий личность
    2. Документ об образовании (аттестат или диплом)
    3. 4 фотографии размером 3x4
    4. Медицинская справка формы 086-У
    """
    
    query = "Какие документы нужны для поступления?"
    
    response = llm.generate_with_context(query, test_context)
    print(f"Ответ: {response}")
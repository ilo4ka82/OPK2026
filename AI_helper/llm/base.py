"""
Базовый абстрактный класс для LLM.
Позволяет легко менять модели (YandexGPT → OpenAI → Claude и т.д.)
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class Message:
    """Сообщение в диалоге"""
    role: str  # "user" или "assistant"
    content: str


class BaseLLM(ABC):
    """Базовый класс для всех LLM"""
    
    @abstractmethod
    def generate(
        self, 
        messages: List[Message], 
        temperature: float = 0.6,
        max_tokens: int = 2000
    ) -> str:
        """
        Генерирует ответ на основе истории сообщений
        
        Args:
            messages: История диалога
            temperature: Креативность (0.0 - детерминированно, 1.0 - креативно)
            max_tokens: Максимум токенов в ответе
            
        Returns:
            Текст ответа
        """
        pass
    
    @abstractmethod
    def generate_with_context(
        self,
        query: str,
        context: str,
        temperature: float = 0.6,
        max_tokens: int = 2000
    ) -> str:
        """
        Генерирует ответ с учётом контекста (для RAG)
        
        Args:
            query: Вопрос пользователя
            context: Найденные документы (контекст)
            temperature: Креативность
            max_tokens: Максимум токенов
            
        Returns:
            Текст ответа
        """
        pass
"""
Главный класс AI-помощника.
Объединяет векторный поиск (RAG) и генерацию ответов (LLM).
"""
import logging
from typing import List, Dict, Optional

from .vector_store import VectorStore
from .llm import YandexGPT, Message

logger = logging.getLogger(__name__)


class AIAssistant:
    """Умный помощник с RAG (Retrieval-Augmented Generation)"""
    
    def __init__(
        self,
        vector_store: VectorStore = None,
        llm: YandexGPT = None,
        top_k: int = 5
    ):
        """
        Args:
            vector_store: Векторное хранилище (или создаст новое)
            llm: LLM модель (или создаст YandexGPT)
            top_k: Количество документов для поиска
        """
        self.vector_store = vector_store or VectorStore()
        self.llm = llm or YandexGPT()
        self.top_k = top_k
        
        logger.info(f"✅ AI Assistant инициализирован (top_k={top_k})")
    
    def ask(
        self, 
        question: str, 
        conversation_history: List[Message] = None,
        temperature: float = 0.6
    ) -> Dict:
        """
        Отвечает на вопрос пользователя
        
        Args:
            question: Вопрос пользователя
            conversation_history: История диалога (опционально)
            temperature: Креативность ответа
            
        Returns:
            {
                'answer': str,          # Ответ
                'sources': List[Dict],  # Источники
                'context': str          # Использованный контекст
            }
        """
        logger.info(f"Получен вопрос: '{question}'")
        
        # 1. ПОИСК релевантных документов
        search_results = self.vector_store.search(question, top_k=self.top_k)
        
        if not search_results:
            logger.warning("Не найдено релевантных документов")
            return {
                'answer': "К сожалению, я не нашёл информации по вашему вопросу в документах.",
                'sources': [],
                'context': ""
            }
        
        # 2. ФОРМИРОВАНИЕ контекста
        context_parts = []
        sources = []
        
        for idx, result in enumerate(search_results, 1):
            # Текст документа
            context_parts.append(
                f"[ДОКУМЕНТ {idx}]\n"
                f"Источник: {result['file_name']}\n"
                f"Страница: {result.get('page', 'N/A')}\n"
                f"Релевантность: {result['score']:.2f}\n"
                f"Текст:\n{result['text']}\n"
            )
            
            # Источник для ответа
            sources.append({
                'file_name': result['file_name'],
                'page': result.get('page'),
                'score': result['score'],
                'text_preview': result['text'][:200] + "..."
            })
        
        context = "\n".join(context_parts)
        
        logger.info(f"Найдено {len(search_results)} релевантных документов")
        
        # 3. ГЕНЕРАЦИЯ ответа через LLM
        answer = self.llm.generate_with_context(
            query=question,
            context=context,
            temperature=temperature
        )
        
        logger.info(f"✅ Ответ сгенерирован ({len(answer)} символов)")
        
        return {
            'answer': answer,
            'sources': sources,
            'context': context
        }
    
    def ask_with_history(
        self,
        question: str,
        history: List[Dict[str, str]],
        temperature: float = 0.6
    ) -> Dict:
        """
        Отвечает с учётом истории диалога
        
        Args:
            question: Вопрос
            history: [{'role': 'user', 'content': '...'}, ...]
            temperature: Креативность
            
        Returns:
            То же что и ask()
        """
        # Пока просто вызываем ask без истории
        # TODO: Добавить логику учёта истории
        return self.ask(question, temperature=temperature)


# === ТЕСТИРОВАНИЕ ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*70)
    print("🤖 ТЕСТ AI ASSISTANT (ПОЛНЫЙ RAG)")
    print("="*70)
    
    # Создаём ассистента
    assistant = AIAssistant(top_k=3)
    
    # Проверяем что в векторном хранилище есть документы
    doc_count = assistant.vector_store.get_count()
    print(f"\n📚 Документов в базе: {doc_count}")
    
    if doc_count == 0:
        print("\n❌ База пустая! Сначала запусти:")
        print("   python -m AI_helper.vector_store")
        exit(1)
    
    # Тестовый вопрос
    print("\n" + "-"*70)
    question = "Какие документы нужны для поступления в бакалавриат?"
    print(f"❓ ВОПРОС: {question}")
    print("-"*70)
    
    # Получаем ответ
    result = assistant.ask(question)
    
    # Выводим результат
    print(f"\n💬 ОТВЕТ:\n{result['answer']}")
    
    print(f"\n📄 ИСТОЧНИКИ ({len(result['sources'])} шт.):")
    for i, source in enumerate(result['sources'], 1):
        print(f"\n{i}. {source['file_name']}")
        print(f"   Страница: {source['page']}")
        print(f"   Релевантность: {source['score']:.2f}")
        print(f"   Превью: {source['text_preview']}")
    
    print("\n" + "="*70)
    print("✅ ТЕСТ ЗАВЕРШЁН!")
    print("="*70)
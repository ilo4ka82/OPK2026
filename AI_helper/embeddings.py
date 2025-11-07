"""
Модуль для создания embeddings (векторных представлений) текста.
Использует sentence-transformers для русского языка.
"""
import logging
from typing import List
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """Класс для создания embeddings текста"""
    
    def __init__(self, model_name: str = "intfloat/multilingual-e5-large"):
        """
        Args:
            model_name: Название модели из HuggingFace
                       Варианты:
                       - "intfloat/multilingual-e5-large" (рекомендуется, 560MB)
                       - "sentence-transformers/paraphrase-multilingual-mpnet-base-v2" (легче, 278MB)
        """
        logger.info(f"Загрузка модели embeddings: {model_name}")
        self.model = SentenceTransformer(model_name)
        logger.info(f"✅ Модель загружена. Размерность: {self.model.get_sentence_embedding_dimension()}")
    
    def embed_text(self, text: str) -> List[float]:
        """
        Создаёт embedding для одного текста
        
        Args:
            text: Текст для векторизации
        
        Returns:
            Список float (вектор)
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_texts(self, texts: List[str], batch_size: int = 32, show_progress: bool = True) -> List[List[float]]:
        """
        Создаёт embeddings для списка текстов (батчами для скорости)
        
        Args:
            texts: Список текстов
            batch_size: Размер батча
            show_progress: Показывать прогресс-бар
        
        Returns:
            Список векторов
        """
        logger.info(f"Создание embeddings для {len(texts)} текстов...")
        
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )
        
        logger.info(f"✅ Создано {len(embeddings)} embeddings")
        return embeddings.tolist()
    
    def get_dimension(self) -> int:
        """Возвращает размерность вектора"""
        return self.model.get_sentence_embedding_dimension()


# === ТЕСТИРОВАНИЕ ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Создаём модель
    embedder = EmbeddingModel()
    
    # Тестовые тексты
    test_texts = [
        "Какие документы нужны для поступления?",
        "Правила приёма в университет 2025 года",
        "БВИ - без вступительных испытаний"
    ]
    
    # Создаём embeddings
    embeddings = embedder.embed_texts(test_texts)
    
    print(f"\n📊 Размерность векторов: {embedder.get_dimension()}")
    print(f"📝 Создано {len(embeddings)} embeddings")
    print(f"📄 Пример вектора (первые 10 чисел): {embeddings[0][:10]}")
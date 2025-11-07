"""
Векторное хранилище для поиска похожих документов.
Использует ChromaDB.
"""
import logging
from typing import List, Dict
from pathlib import Path
import chromadb
from chromadb.config import Settings

from .document_loader import DocumentChunk
from .embeddings import EmbeddingModel

logger = logging.getLogger(__name__)


class VectorStore:
    """Векторное хранилище на базе ChromaDB"""
    
    def __init__(self, collection_name: str = "ai_knowledge", persist_directory: str = None):
        """
        Args:
            collection_name: Название коллекции в ChromaDB
            persist_directory: Папка для хранения БД (по умолчанию ./data/chroma_db/)
        """
        if persist_directory is None:
            current_dir = Path(__file__).parent
            persist_directory = str(current_dir / "data" / "chroma_db")
        
        logger.info(f"Инициализация ChromaDB в {persist_directory}")
        
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Получаем или создаём коллекцию
        try:
            self.collection = self.client.get_collection(name=collection_name)
            logger.info(f"✅ Коллекция '{collection_name}' загружена ({self.collection.count()} документов)")
        except Exception:
            self.collection = self.client.create_collection(name=collection_name)
            logger.info(f"✅ Создана новая коллекция '{collection_name}'")
        
        # Модель embeddings
        self.embedder = EmbeddingModel()
    
    def add_documents(self, chunks: List[DocumentChunk], batch_size: int = 100) -> None:
        """
        Добавляет документы в векторное хранилище (батчами)
        
        Args:
            chunks: Список DocumentChunk
            batch_size: Размер батча (по умолчанию 100, ChromaDB лимит ~166)
        """
        if not chunks:
            logger.warning("Нет документов для добавления")
            return
        
        logger.info(f"Добавление {len(chunks)} чанков в ChromaDB...")
        
        # Создаём embeddings для ВСЕХ чанков сразу
        texts = [chunk.text for chunk in chunks]
        logger.info(f"Создание embeddings для {len(texts)} текстов...")
        all_embeddings = self.embedder.embed_texts(texts, batch_size=32)
        logger.info(f"✅ Embeddings созданы")
        
        # Добавляем в ChromaDB батчами
        total_batches = (len(chunks) + batch_size - 1) // batch_size
        
        for batch_idx in range(0, len(chunks), batch_size):
            batch_chunks = chunks[batch_idx:batch_idx + batch_size]
            batch_embeddings = all_embeddings[batch_idx:batch_idx + batch_size]
            
            batch_texts = []
            batch_metadatas = []
            batch_ids = []
            
            for i, chunk in enumerate(batch_chunks):
                global_idx = batch_idx + i
                
                # Создаём уникальный ID
                chunk_id = f"{Path(chunk.source).stem}_chunk_{global_idx}"
                batch_ids.append(chunk_id)
                
                # Текст
                batch_texts.append(chunk.text)
                
                # Метаданные
                metadata = {
                    "source": chunk.source,
                    "file_name": Path(chunk.source).name,
                }
                if chunk.page:
                    metadata["page"] = chunk.page
                if chunk.metadata:
                    metadata.update(chunk.metadata)
                
                batch_metadatas.append(metadata)
            
            # Добавляем батч в ChromaDB
            self.collection.add(
                embeddings=batch_embeddings,
                documents=batch_texts,
                metadatas=batch_metadatas,
                ids=batch_ids
            )
            
            current_batch = (batch_idx // batch_size) + 1
            logger.info(f"✅ Добавлен батч {current_batch}/{total_batches} ({len(batch_chunks)} документов)")
        
        logger.info(f"✅ Всего добавлено {len(chunks)} документов в ChromaDB")
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Ищет наиболее релевантные документы
        
        Args:
            query: Поисковый запрос
            top_k: Количество результатов
        
        Returns:
            Список словарей с полями: text, source, score, metadata
        """
        logger.info(f"Поиск по запросу: '{query}'")
        
        # Создаём embedding запроса
        query_embedding = self.embedder.embed_text(query)
        
        # Ищем в ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        # Форматируем результаты
        formatted_results = []
        
        for i in range(len(results["documents"][0])):
            formatted_results.append({
                "text": results["documents"][0][i],
                "source": results["metadatas"][0][i].get("source", "Unknown"),
                "file_name": results["metadatas"][0][i].get("file_name", "Unknown"),
                "page": results["metadatas"][0][i].get("page"),
                "score": 1 - results["distances"][0][i],
                "metadata": results["metadatas"][0][i]
            })
        
        logger.info(f"✅ Найдено {len(formatted_results)} результатов")
        return formatted_results
    
    def clear_collection(self) -> None:
        """Очищает всю коллекцию"""
        logger.warning(f"Очистка коллекции '{self.collection.name}'")
        self.client.delete_collection(name=self.collection.name)
        self.collection = self.client.create_collection(name=self.collection.name)
        logger.info("✅ Коллекция очищена")
    
    def get_count(self) -> int:
        """Возвращает количество документов в коллекции"""
        return self.collection.count()


# === ТЕСТИРОВАНИЕ ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    from AI_helper.document_loader import DocumentLoader
    
    # Загружаем документы
    loader = DocumentLoader()
    documents = loader.load_all_documents(chunk_size=500, chunk_overlap=50)
    
    if not documents:
        print("❌ Нет документов для индексации!")
        print("Положите PDF/DOCX/TXT файлы в AI_helper/data/ai_knowledge/")
        exit(1)
    
    # Создаём векторное хранилище
    vector_store = VectorStore()
    
    # Очищаем старые данные (если нужно)
    # vector_store.clear_collection()
    
    # Добавляем документы
    vector_store.add_documents(documents)
    
    # Тестовый поиск
    print("\n" + "="*50)
    print("🔍 ТЕСТОВЫЙ ПОИСК")
    print("="*50)
    
    query = "Какие документы нужны для поступления?"
    results = vector_store.search(query, top_k=3)
    
    for i, result in enumerate(results, 1):
        print(f"\n📄 Результат {i} (релевантность: {result['score']:.2f})")
        print(f"Источник: {result['file_name']}")
        if result['page']:
            print(f"Страница: {result['page']}")
        print(f"Текст: {result['text'][:200]}...")
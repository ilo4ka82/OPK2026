"""
Логирование запросов и ответов AI для аналитики.
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


class AILogger:
    """Логирование работы AI-помощника"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # БД рядом с ChromaDB
            current_dir = Path(__file__).parent
            data_dir = current_dir / "data"
            
            # ✅ СОЗДАЁМ ПАПКУ ЕСЛИ НЕТ
            data_dir.mkdir(parents=True, exist_ok=True)
            
            db_path = data_dir / "ai_logs.db"
    
        self.db_path = str(db_path)
        self._init_db()
    
    def _init_db(self):
        """Создание таблиц"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица запросов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                response_time_ms INTEGER,
                
                -- Метрики поиска
                documents_found INTEGER,
                avg_relevance REAL,
                max_relevance REAL,
                min_relevance REAL,
                
                -- Обратная связь
                feedback INTEGER,  -- 1 = 👍, -1 = 👎, NULL = нет оценки
                feedback_time DATETIME,
                
                -- Метаданные
                sources TEXT,  -- JSON со списком источников
                context_length INTEGER,
                tokens_used INTEGER
            )
        """)
        
        # Индексы для быстрого поиска
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON ai_requests(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON ai_requests(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback ON ai_requests(feedback)")
        
        conn.commit()
        conn.close()
    
    def log_request(
        self,
        user_id: int,
        username: str,
        question: str,
        answer: str,
        sources: List[Dict],
        response_time_ms: int,
        context_length: int = 0
    ) -> int:
        """
        Логирует запрос
        
        Returns:
            request_id для последующего обновления
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Вычисляем метрики релевантности
        relevances = [s['score'] for s in sources if 'score' in s]
        avg_relevance = sum(relevances) / len(relevances) if relevances else 0
        max_relevance = max(relevances) if relevances else 0
        min_relevance = min(relevances) if relevances else 0
        
        cursor.execute("""
            INSERT INTO ai_requests (
                user_id, username, question, answer,
                response_time_ms, documents_found,
                avg_relevance, max_relevance, min_relevance,
                sources, context_length
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, username, question, answer,
            response_time_ms, len(sources),
            avg_relevance, max_relevance, min_relevance,
            json.dumps(sources, ensure_ascii=False), context_length
        ))
        
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return request_id
    
    def log_feedback(self, request_id: int, feedback: int):
        """
        Логирует обратную связь пользователя
        
        Args:
            request_id: ID запроса
            feedback: 1 (👍) или -1 (👎)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE ai_requests 
            SET feedback = ?, feedback_time = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (feedback, request_id))
        
        conn.commit()
        conn.close()
    
    def get_stats(self, days: int = 7) -> Dict:
        """Статистика за последние N дней"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_requests,
                AVG(response_time_ms) as avg_response_time,
                AVG(avg_relevance) as avg_relevance,
                SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) as positive_feedback,
                SUM(CASE WHEN feedback = -1 THEN 1 ELSE 0 END) as negative_feedback,
                SUM(CASE WHEN feedback IS NOT NULL THEN 1 ELSE 0 END) as total_feedback
            FROM ai_requests
            WHERE timestamp >= datetime('now', '-{days} days')
        """)
        
        row = cursor.fetchone()
        
        stats = {
            'total_requests': row[0] or 0,
            'avg_response_time_ms': round(row[1] or 0, 2),
            'avg_relevance': round(row[2] or 0, 3),
            'positive_feedback': row[3] or 0,
            'negative_feedback': row[4] or 0,
            'total_feedback': row[5] or 0,
            'feedback_rate': round((row[5] or 0) / (row[0] or 1) * 100, 1)
        }
        
        conn.close()
        return stats
    
    def get_popular_questions(self, limit: int = 10) -> List[Dict]:
        """Самые частые вопросы"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT question, COUNT(*) as count
            FROM ai_requests
            WHERE timestamp >= datetime('now', '-30 days')
            GROUP BY LOWER(question)
            ORDER BY count DESC
            LIMIT ?
        """, (limit,))
        
        questions = [
            {'question': row[0], 'count': row[1]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return questions
    
    def get_low_relevance_requests(self, threshold: float = 0.6, limit: int = 20) -> List[Dict]:
        """Запросы с низкой релевантностью (проблемные)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, question, avg_relevance, answer
            FROM ai_requests
            WHERE max_relevance < ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (threshold, limit))
        
        requests = [
            {
                'id': row[0],
                'question': row[1],
                'relevance': row[2],
                'answer': row[3][:100] + '...'
            }
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return requests


# === ТЕСТИРОВАНИЕ ===
if __name__ == "__main__":
    logger = AILogger()
    
    # Тестовый запрос
    request_id = logger.log_request(
        user_id=123456,
        username="test_user",
        question="Какие документы нужны?",
        answer="Для поступления нужны: паспорт, аттестат...",
        sources=[
            {'file_name': 'rules.pdf', 'page': 19, 'score': 0.85},
            {'file_name': 'rules.pdf', 'page': 20, 'score': 0.78}
        ],
        response_time_ms=2500,
        context_length=1500
    )
    
    print(f"✅ Логирован запрос #{request_id}")
    
    # Добавляем фидбек
    logger.log_feedback(request_id, feedback=1)
    print("✅ Добавлен фидбек")
    
    # Статистика
    stats = logger.get_stats(days=7)
    print(f"\n📊 Статистика:\n{json.dumps(stats, indent=2, ensure_ascii=False)}")
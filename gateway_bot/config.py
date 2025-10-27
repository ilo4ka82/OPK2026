"""Конфигурация Gateway Bot."""
import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()


class Config:
    """Конфигурация бота"""
    
    # === TELEGRAM ===
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не найден в .env файле!")
    
    # === DATABASE (для табеля) ===
    DATABASE_PATH = os.getenv("DATABASE_PATH", "D:/БотикСакает/tabel_database.db")  # ← ДОБАВИЛИ!
    
    # === REDIS (пока не используем) ===
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    
    # === АВТОРИЗАЦИЯ ===
    ALLOWED_USERS_STR = os.getenv("ALLOWED_USERS", "")
    ALLOWED_USERS = [
        int(user_id.strip()) 
        for user_id in ALLOWED_USERS_STR.split(",") 
        if user_id.strip()
    ]
    
    # Если список пустой - разрешаем всем (для разработки)
    ALLOW_ALL = len(ALLOWED_USERS) == 0
    
    # === АДМИНЫ ===
    ADMIN_USERS_STR = os.getenv("ADMIN_USERS", "")
    ADMIN_USERS = [
        int(user_id.strip()) 
        for user_id in ADMIN_USERS_STR.split(",") 
        if user_id.strip()
    ]
    
    # Для обратной совместимости с Tabel_service
    ADMIN_TELEGRAM_IDS = ADMIN_USERS  # ← ДОБАВИЛИ!
    
    # === ПУТИ ===
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DOCUMENTS_DIR = os.path.join(BASE_DIR, "gateway_bot", "data", "documents")
    
    # Создаем папку если не существует
    os.makedirs(DOCUMENTS_DIR, exist_ok=True)
    
    # === КАТЕГОРИИ ДОКУМЕНТОВ ===
    DOCUMENT_CATEGORIES = {
        "pravila": "📄 Правила приема",
        "metodichki": "📖 Методички",
        "other": "📁 Прочее"
    }
    
    def get_categories(self):  # ← ДОБАВИЛИ МЕТОД!
        """Получить категории документов"""
        return self.DOCUMENT_CATEGORIES
    
    def get_files_in_category(self, category: str):  # ← ДОБАВИЛИ МЕТОД!
        """Получить список файлов в категории"""
        category_path = os.path.join(self.DOCUMENTS_DIR, category)
        
        if not os.path.exists(category_path):
            return []
        
        files = [
            f for f in os.listdir(category_path)
            if os.path.isfile(os.path.join(category_path, f))
        ]
        
        return sorted(files)


# Создаем глобальный экземпляр
config = Config()
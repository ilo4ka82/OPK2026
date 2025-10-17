import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

class Config:
    """Конфигурация бота"""
    
    # Telegram Bot Token
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не найден в .env файле!")
    
    # Redis (пока не используем)
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    
    # Авторизация
    ALLOWED_USERS_STR = os.getenv("ALLOWED_USERS", "")
    ALLOWED_USERS = [
        int(user_id.strip()) 
        for user_id in ALLOWED_USERS_STR.split(",") 
        if user_id.strip()
    ]
    
    # Если список пустой - разрешаем всем (для разработки)
    ALLOW_ALL = len(ALLOWED_USERS) == 0
    
    # Админы (для загрузки документов)
    ADMIN_USERS_STR = os.getenv("ADMIN_USERS", "")
    ADMIN_USERS = [
        int(user_id.strip()) 
        for user_id in ADMIN_USERS_STR.split(",") 
        if user_id.strip()
    ]
    
    # Пути
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DOCUMENTS_DIR = os.path.join(BASE_DIR, "gateway_bot", "data", "documents")
    
    # Категории документов (для структуры)
    DOCUMENT_CATEGORIES = {
        "pravila": "📄 Правила приема",
        "metodichki": "📖 Методички",
        "other": "📁 Прочее"
    }

config = Config()
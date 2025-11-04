"""
Конфигурация табеля.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class TimesheetConfig:
    """Конфигурация табеля."""
    
    # === TELEGRAM ===
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")  
    if not TELEGRAM_BOT_TOKEN:  
        raise ValueError("Критическая ошибка: TELEGRAM_BOT_TOKEN или BOT_TOKEN не найден в .env файле!")
    
    # Парсинг списка ID администраторов
    admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS") or os.getenv("ADMIN_USERS", "")  
    cleaned_ids_str = admin_ids_str.strip().strip('[]')
    ADMIN_TELEGRAM_IDS = [
        int(admin_id.strip()) 
        for admin_id in cleaned_ids_str.split(',') 
        if admin_id.strip()
    ]
    
    # === DATABASE ===
    DATABASE_PATH = os.getenv("DATABASE_PATH")
    if not DATABASE_PATH:
        raise ValueError("Критическая ошибка: DATABASE_PATH не найден в .env файле!")
    
    # === PATHS ===
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        """
        Проверяет, является ли пользователь администратором.
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            True если пользователь - админ, False иначе
        """
        return user_id in cls.ADMIN_TELEGRAM_IDS
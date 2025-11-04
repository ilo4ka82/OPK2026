"""
Главный файл запуска Gateway Bot.
"""
import logging
import sys
import os
from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Добавляем РОДИТЕЛЬСКУЮ папку в sys.path (D:\БотикСакает)
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Импортируем из Tabel_service как из полноценного пакета
from Tabel_service.database import init_db as init_tabel_db

from config import config
from handlers.start import register_handlers as register_start_handlers
from handlers.handbook import register_handlers as register_handbook_handlers
from handlers.timesheet import register_handlers as register_timesheet_handlers

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("gateway_bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def on_startup(dp: Dispatcher):
    """Действия при запуске бота."""
    # Инициализируем БД табеля
    try:
        init_tabel_db()
        logger.info("✅ База данных табеля инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД табеля: {e}")
    
    logger.info("✅ Gateway Bot запущен!")


async def on_shutdown(dp: Dispatcher):
    """Действия при остановке бота."""
    logger.info("🛑 Gateway Bot остановлен!")


def main():
    """Главная функция запуска бота."""
    try:
        # Создание бота и диспетчера
        bot = Bot(token=config.BOT_TOKEN)
        storage = MemoryStorage()
        dp = Dispatcher(bot, storage=storage)
        
        # Регистрация обработчиков
        register_start_handlers(dp)
        register_handbook_handlers(dp)
        register_timesheet_handlers(dp)
        
        logger.info("✅ Все обработчики зарегистрированы")
        logger.info("🚀 Запуск Gateway Bot...")
        
        # Запуск бота
        executor.start_polling(
            dp,
            skip_updates=True,
            on_startup=on_startup,
            on_shutdown=on_shutdown
        )
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
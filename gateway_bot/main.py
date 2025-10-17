"""
Главный файл запуска Gateway Bot.
"""
import logging
import sys
from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from config import config
from handlers.start import register_handlers as register_start_handlers  # ✅
from handlers.handbook import register_handlers as register_handbook_handlers  # если есть

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
        
        # Если есть обработчики для справочника
        try:
            register_handbook_handlers(dp)
        except ImportError:
            logger.warning("Обработчики handbook не найдены, пропускаем...")
        
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
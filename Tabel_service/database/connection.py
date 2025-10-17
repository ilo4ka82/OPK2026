"""
Подключение к базе данных.
"""
import sqlite3
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_db_connection() -> sqlite3.Connection:
    """
    Создает подключение к базе данных SQLite.
    
    Returns:
        Объект подключения с row_factory для работы со словарями
    """
    from ..config import TimesheetConfig
    
    conn = sqlite3.connect(TimesheetConfig.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Инициализирует базу данных: создает таблицы, если их нет.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # --- Таблица users ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                application_full_name TEXT,
                application_department TEXT,
                is_authorized BOOLEAN DEFAULT FALSE,
                is_admin BOOLEAN DEFAULT FALSE,
                registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                application_status TEXT DEFAULT 'none'
            )
        ''')
        logger.info("Таблица 'users' проверена/создана.")

        # --- Таблица work_sessions ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS work_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                check_in_time DATETIME NOT NULL,
                check_out_time DATETIME,
                duration_minutes INTEGER,
                latitude REAL,
                longitude REAL,
                checkin_type TEXT NOT NULL DEFAULT 'geo',
                sector_id TEXT,
                FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
            )
        ''')
        logger.info("Таблица 'work_sessions' проверена/создана.")

        # Добавление столбца checkin_type (для старых БД)
        cursor.execute("PRAGMA table_info(work_sessions)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'checkin_type' not in columns:
            try:
                cursor.execute(
                    "ALTER TABLE work_sessions ADD COLUMN checkin_type TEXT NOT NULL DEFAULT 'geo'"
                )
                logger.info("Столбец 'checkin_type' добавлен в 'work_sessions'.")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise

        # Добавление столбца sector_id (для старых БД)
        cursor.execute("PRAGMA table_info(work_sessions)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'sector_id' not in columns:
            try:
                cursor.execute("ALTER TABLE work_sessions ADD COLUMN sector_id TEXT")
                logger.info("Столбец 'sector_id' добавлен в 'work_sessions'.")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise
        
        # --- Таблица manual_checkin_requests ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS manual_checkin_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                requested_checkin_time TEXT NOT NULL,
                request_timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'pending',
                admin_id_processed INTEGER,
                processed_timestamp TEXT,
                final_checkin_time TEXT,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id),
                FOREIGN KEY (admin_id_processed) REFERENCES users(telegram_id)
            )
        ''')
        logger.info("Таблица 'manual_checkin_requests' проверена/создана.")
        
        conn.commit()
        logger.info("✅ База данных успешно инициализирована.")
        
    except sqlite3.Error as e:
        logger.error(f"Ошибка при инициализации БД: {e}", exc_info=True)
        raise
    finally:
        if conn:
            conn.close()
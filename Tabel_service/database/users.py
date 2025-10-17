"""
Операции с пользователями в базе данных.
"""
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Tuple
import pytz

from .connection import get_db_connection

logger = logging.getLogger(__name__)
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def add_or_update_user(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None
) -> bool:
    """
    Добавляет нового пользователя или обновляет существующего.
    
    Args:
        telegram_id: Telegram ID пользователя
        username: Username пользователя
        first_name: Имя
        last_name: Фамилия
        
    Returns:
        True если успешно, False при ошибке
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        registration_time_msk = datetime.now(MOSCOW_TZ)

        cursor.execute('''
            INSERT INTO users (telegram_id, username, first_name, last_name, registration_date)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = COALESCE(excluded.username, users.username),
                first_name = COALESCE(excluded.first_name, users.first_name),
                last_name = COALESCE(excluded.last_name, users.last_name)
        ''', (telegram_id, username, first_name, last_name, registration_time_msk))
        
        conn.commit()
        logger.info(f"Пользователь {telegram_id} ({first_name}) добавлен/обновлен в БД.")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении/обновлении пользователя {telegram_id}: {e}", exc_info=True)
        return False
    finally:
        if conn:
            conn.close()


def get_user(telegram_id: int) -> Optional[dict]:
    """
    Получает пользователя по ID.
    
    Args:
        telegram_id: Telegram ID пользователя
        
    Returns:
        Словарь с данными пользователя или None если не найден
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user_row = cursor.fetchone()
        
        if user_row:
            return dict(user_row)
        return None
        
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении пользователя {telegram_id}: {e}", exc_info=True)
        return None
    finally:
        if conn:
            conn.close()


def is_user_authorized(telegram_id: int) -> bool:
    """
    Проверяет, авторизован ли пользователь.
    
    Args:
        telegram_id: Telegram ID пользователя
        
    Returns:
        True если авторизован, False иначе
    """
    user_data = get_user(telegram_id)
    if user_data and user_data['is_authorized']:
        return True
    return False


def authorize_user(telegram_id_to_authorize: int, authorizing_admin_id: int) -> Tuple[bool, str]:
    """
    Авторизует пользователя (одобряет заявку).
    
    Args:
        telegram_id_to_authorize: ID пользователя для авторизации
        authorizing_admin_id: ID администратора
        
    Returns:
        (успех, сообщение)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        user_exists = get_user(telegram_id_to_authorize)
        if not user_exists:
            logger.warning(
                f"Попытка авторизации несуществующего пользователя {telegram_id_to_authorize} "
                f"администратором {authorizing_admin_id}."
            )
            return False, f"Пользователь с ID {telegram_id_to_authorize} не найден в базе."
        
        cursor.execute('''
            UPDATE users SET is_authorized = TRUE, application_status = 'approved'
            WHERE telegram_id = ?
        ''', (telegram_id_to_authorize,))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            logger.info(
                f"Пользователь {telegram_id_to_authorize} авторизован администратором "
                f"{authorizing_admin_id} (статус 'approved')."
            )
            return True, f"Пользователь ID {telegram_id_to_authorize} успешно авторизован."
        else:
            if user_exists['is_authorized'] and user_exists['application_status'] == 'approved':
                return True, f"Пользователь ID {telegram_id_to_authorize} уже был авторизован ранее."
            
            logger.warning(
                f"Не удалось авторизовать пользователя {telegram_id_to_authorize} "
                f"(rowcount=0)."
            )
            return False, f"Не удалось авторизовать пользователя ID {telegram_id_to_authorize}."
            
    except sqlite3.Error as e:
        logger.error(
            f"Ошибка SQLite при авторизации пользователя {telegram_id_to_authorize}: {e}",
            exc_info=True
        )
        return False, f"Произошла ошибка базы данных при авторизации."
    finally:
        if conn:
            conn.close()


def list_pending_users() -> List[dict]:
    """
    Возвращает список пользователей с ожидающими заявками.
    
    Returns:
        Список словарей с данными пользователей
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT telegram_id, username, first_name, last_name, registration_date, 
                   application_full_name, application_department 
            FROM users 
            WHERE application_status = 'pending' AND is_authorized = FALSE
            ORDER BY registration_date ASC
        """)
        users = [dict(row) for row in cursor.fetchall()]
        return users
        
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении списка ожидающих пользователей: {e}", exc_info=True)
        return []
    finally:
        if conn:
            conn.close()


def submit_application(telegram_id: int, full_name: str, department: str) -> Tuple[bool, str]:
    """
    Подает заявку на доступ к боту.
    
    Args:
        telegram_id: Telegram ID пользователя
        full_name: ФИО пользователя
        department: Департамент/сектор
        
    Returns:
        (успех, сообщение)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        user = get_user(telegram_id)
        if not user:
            logger.error(f"Попытка подать заявку от незарегистрированного пользователя {telegram_id}")
            return False, "Произошла ошибка. Пожалуйста, попробуйте сначала /start."
        
        if user['application_status'] == 'pending':
            return False, "Вы уже подали заявку. Ожидайте подтверждения администратором."
        
        if user['application_status'] == 'approved' or user['is_authorized']:
            return False, "Ваша заявка уже одобрена, и вы авторизованы."
        
        cursor.execute('''
            UPDATE users 
            SET application_status = 'pending', 
                application_full_name = ?, 
                application_department = ?
            WHERE telegram_id = ?
        ''', (full_name, department, telegram_id))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            logger.info(
                f"Пользователь {telegram_id} подал заявку на доступ (статус 'pending') "
                f"с ФИО: {full_name}, Отдел: {department}."
            )
            return True, "✅ Ваша заявка на доступ успешно подана! Администратор рассмотрит ее в ближайшее время."
        else:
            logger.warning(f"Не удалось обновить статус заявки для {telegram_id} (rowcount=0).")
            return False, "Не удалось подать заявку. Попробуйте еще раз."
            
    except sqlite3.Error as e:
        logger.error(f"Ошибка SQLite при подаче заявки пользователем {telegram_id}: {e}", exc_info=True)
        return False, "Произошла ошибка базы данных при подаче заявки."
    finally:
        if conn:
            conn.close()


def reject_application(
    telegram_id_to_reject: int,
    rejecting_admin_id: int,
    reason: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Отклоняет заявку пользователя.
    
    Args:
        telegram_id_to_reject: ID пользователя
        rejecting_admin_id: ID администратора
        reason: Причина отклонения (опционально)
        
    Returns:
        (успех, сообщение)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        user_to_reject = get_user(telegram_id_to_reject)

        if not user_to_reject:
            logger.warning(
                f"Попытка отклонить заявку несуществующего пользователя {telegram_id_to_reject} "
                f"администратором {rejecting_admin_id}."
            )
            return False, f"Пользователь с ID {telegram_id_to_reject} не найден в базе."

        if user_to_reject['is_authorized']:
            logger.info(f"Попытка отклонить заявку уже авторизованного пользователя {telegram_id_to_reject}.")
            return False, f"Пользователь ID {telegram_id_to_reject} уже авторизован. Отклонение заявки невозможно."
        
        if user_to_reject['application_status'] == 'rejected':
            logger.info(f"Заявка пользователя {telegram_id_to_reject} уже была отклонена ранее.")
            return True, f"Заявка пользователя ID {telegram_id_to_reject} уже была отклонена ранее."

        if user_to_reject['application_status'] != 'pending':
            logger.warning(
                f"Попытка отклонить заявку пользователя {telegram_id_to_reject} "
                f"со статусом '{user_to_reject['application_status']}' (ожидался 'pending')."
            )
            return False, f"Заявка пользователя ID {telegram_id_to_reject} не находится в статусе 'pending'."

        cursor.execute("""
            UPDATE users 
            SET application_status = 'rejected', 
                is_authorized = FALSE,
                application_full_name = NULL,
                application_department = NULL
            WHERE telegram_id = ? AND application_status = 'pending'
        """, (telegram_id_to_reject,))
        
        conn.commit()

        if cursor.rowcount > 0:
            logger.info(
                f"Заявка пользователя {telegram_id_to_reject} отклонена администратором "
                f"{rejecting_admin_id}. Данные заявки очищены."
            )
            return True, f"Заявка пользователя ID {telegram_id_to_reject} успешно отклонена."
        else:
            logger.warning(
                f"Не удалось отклонить заявку пользователя {telegram_id_to_reject} "
                f"(rowcount=0 при UPDATE)."
            )
            return False, f"Не удалось отклонить заявку пользователя ID {telegram_id_to_reject}."

    except sqlite3.Error as e:
        logger.error(
            f"Ошибка SQLite при отклонении заявки пользователя {telegram_id_to_reject}: {e}",
            exc_info=True
        )
        return False, f"Произошла ошибка базы данных при отклонении заявки."
    finally:
        if conn:
            conn.close()


def find_users_by_name(name_part: str) -> List[dict]:
    """
    Ищет пользователей по части имени.
    
    Args:
        name_part: Часть имени для поиска
        
    Returns:
        Список словарей с данными пользователей
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql_query = """
            SELECT telegram_id, application_full_name
            FROM users
            WHERE LOWER(application_full_name) LIKE LOWER(?)
            AND is_authorized = 1
            ORDER BY application_full_name
        """
        
        search_term = f"%{name_part}%"
        cursor.execute(sql_query, (search_term,))
        users = [dict(row) for row in cursor.fetchall()]
        
        logger.info(f"Поиск по имени '{name_part}' нашел {len(users)} пользователей.")
        return users

    except sqlite3.Error as e:
        logger.error(f"Ошибка при поиске пользователей по имени '{name_part}': {e}", exc_info=True)
        return []
    finally:
        if conn:
            conn.close()


def get_unique_user_departments() -> List[str]:
    """
    Возвращает список уникальных департаментов из таблицы users.
    
    Returns:
        Список названий департаментов
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT application_department 
            FROM users 
            WHERE application_department IS NOT NULL AND application_department != '' 
            ORDER BY application_department ASC
        """)
        
        departments = [row[0] for row in cursor.fetchall() if row[0]]
        
        if departments:
            logger.info(f"Получены уникальные департаменты: {departments}")
        else:
            logger.info("Уникальные департаменты не найдены.")
            
        return departments
        
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении уникальных департаментов: {e}", exc_info=True)
        return []
    finally:
        if conn:
            conn.close()
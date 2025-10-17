"""
Операции с ручными заявками на отметку прихода.
"""
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Tuple
import pytz
from telegram.error import Forbidden

from .connection import get_db_connection
from ..utils import datetime_to_db_string

logger = logging.getLogger(__name__)
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def add_manual_checkin_request(user_id: int, requested_checkin_time: datetime) -> bool:
    """
    Добавляет новую заявку на ручную отметку прихода.
    
    Args:
        user_id: Telegram ID пользователя
        requested_checkin_time: Запрошенное время прихода (datetime в МСК)
        
    Returns:
        True если успешно, False при ошибке
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Конвертируем datetime в строку для БД
        requested_time_str = datetime_to_db_string(requested_checkin_time)
        
        cursor.execute("""
            INSERT INTO manual_checkin_requests 
            (user_id, requested_checkin_time, request_timestamp, status)
            VALUES (?, ?, datetime('now', 'localtime'), 'pending')
        """, (user_id, requested_time_str))
        
        conn.commit()
        
        logger.info(
            f"Новая заявка на ручную отметку прихода добавлена для user_id={user_id}, "
            f"время={requested_time_str} (МСК)"
        )
        return True
        
    except sqlite3.Error as e:
        logger.error(
            f"Ошибка при добавлении заявки на ручную отметку для user_id={user_id}: {e}",
            exc_info=True
        )
        return False
    finally:
        if conn:
            conn.close()


def get_pending_manual_checkin_requests() -> List[dict]:
    """
    Возвращает список ожидающих заявок на ручную отметку.
    
    Returns:
        Список словарей с данными заявок
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql_query = """
            SELECT
                req.request_id,
                req.user_id,
                req.requested_checkin_time,
                req.request_timestamp,
                u.application_full_name,
                u.username
            FROM manual_checkin_requests req
            LEFT JOIN users u ON req.user_id = u.telegram_id
            WHERE req.status = 'pending'
            ORDER BY req.request_timestamp ASC
        """
        
        cursor.execute(sql_query)
        requests_rows = cursor.fetchall()
        requests_dicts = [dict(row) for row in requests_rows]

        logger.info(f"Найдено {len(requests_dicts)} ожидающих заявок на ручную отметку.")
        return requests_dicts
        
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении списка ручных заявок: {e}", exc_info=True)
        return []
    finally:
        if conn:
            conn.close()


def get_manual_checkin_request_by_id(request_id: int) -> Optional[dict]:
    """
    Получает детали конкретной заявки по ID.
    
    Args:
        request_id: ID заявки
        
    Returns:
        Словарь с данными заявки или None
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                mcr.request_id, 
                mcr.user_id, 
                mcr.requested_checkin_time,
                mcr.status,
                u.application_full_name,
                u.username,
                u.application_department
            FROM manual_checkin_requests mcr
            LEFT JOIN users u ON mcr.user_id = u.telegram_id
            WHERE mcr.request_id = ?
        """, (request_id,))
        
        request_data_row = cursor.fetchone()
        
        if request_data_row:
            logger.info(f"Получена заявка на ручную отметку с ID={request_id}.")
            return dict(request_data_row)
        else:
            logger.warning(f"Заявка на ручную отметку с ID={request_id} не найдена.")
            return None

    except sqlite3.Error as e:
        logger.error(
            f"Ошибка при получении ручной заявки по ID={request_id}: {e}",
            exc_info=True
        )
        return None
    finally:
        if conn:
            conn.close()


def approve_manual_checkin_request(
    request_id: int,
    admin_id: int,
    final_checkin_time: datetime,
    user_id: int,
    user_sector_key: str
) -> bool:
    """
    Одобряет заявку на ручную отметку и создает рабочую сессию.
    
    Args:
        request_id: ID заявки
        admin_id: ID администратора
        final_checkin_time: Финальное время прихода (datetime в МСК)
        user_id: ID пользователя
        user_sector_key: Ключ сектора пользователя
        
    Returns:
        True если успешно, False при ошибке
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Конвертируем время в строки для БД
        checkin_time_str = datetime_to_db_string(final_checkin_time)
        processed_time_str = datetime_to_db_string(datetime.now(MOSCOW_TZ))

        # Обновляем заявку
        cursor.execute("""
            UPDATE manual_checkin_requests
            SET status = 'approved',
                admin_id_processed = ?, 
                processed_timestamp = ?,
                final_checkin_time = ?
            WHERE request_id = ? AND status = 'pending'
        """, (admin_id, processed_time_str, checkin_time_str, request_id))
        
        if cursor.rowcount == 0:
            logger.warning(
                f"Не удалось обновить заявку {request_id} для одобрения (возможно, уже обработана)."
            )
            conn.rollback()
            return False

        # Создаем рабочую сессию
        cursor.execute("""
            INSERT INTO work_sessions (telegram_id, check_in_time, checkin_type, sector_id)
            VALUES (?, ?, 'manual_admin', ?)
        """, (user_id, checkin_time_str, user_sector_key))
        
        conn.commit()
        
        logger.info(
            f"Заявка {request_id} одобрена. Создана сессия для user_id={user_id}, "
            f"сектор='{user_sector_key}', время='{checkin_time_str}' (МСК)."
        )
        return True

    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Ошибка при одобрении ручной заявки {request_id}: {e}", exc_info=True)
        return False
    finally:
        if conn:
            conn.close()


def approve_all_pending_manual_checkins(admin_id: int) -> Tuple[List[dict], int]:
    """
    Одобряет все ожидающие заявки на ручную отметку.
    
    Args:
        admin_id: ID администратора
        
    Returns:
        (список одобренных заявок для уведомлений, количество ошибок)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Получаем все ожидающие заявки
        cursor.execute("SELECT * FROM manual_checkin_requests WHERE status = 'pending'")
        pending_requests = [dict(row) for row in cursor.fetchall()]

        if not pending_requests:
            return [], 0

        approved_requests_data = []
        failed_count = 0
        
        processed_time_str = datetime_to_db_string(datetime.now(MOSCOW_TZ))

        for req in pending_requests:
            try:
                request_id = req['request_id']
                user_id = req['user_id']
                checkin_time_str = req['requested_checkin_time']
                
                # Обновляем заявку
                cursor.execute("""
                    UPDATE manual_checkin_requests
                    SET status = 'approved', admin_id_processed = ?, 
                        processed_timestamp = ?, final_checkin_time = ?
                    WHERE request_id = ?
                """, (admin_id, processed_time_str, checkin_time_str, request_id))

                # Получаем сектор пользователя
                cursor.execute(
                    "SELECT application_department FROM users WHERE telegram_id = ?",
                    (user_id,)
                )
                user_data = cursor.fetchone()
                user_sector_key = user_data['application_department'] if user_data else 'unknown'

                # Создаем рабочую сессию
                cursor.execute("""
                    INSERT INTO work_sessions (telegram_id, check_in_time, checkin_type, sector_id)
                    VALUES (?, ?, 'manual_admin', ?)
                """, (user_id, checkin_time_str, user_sector_key))

                # Добавляем в список для уведомлений
                approved_requests_data.append({
                    'user_id': user_id,
                    'checkin_time_str': checkin_time_str
                })
                
                logger.info(
                    f"Массовое одобрение: Заявка {request_id} для user_id={user_id} успешно обработана."
                )

            except sqlite3.Error as e:
                logger.error(f"Массовое одобрение: Ошибка при обработке заявки {req.get('request_id')}: {e}")
                failed_count += 1
        
        conn.commit()
        return approved_requests_data, failed_count

    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Критическая ошибка при массовом одобрении заявок: {e}", exc_info=True)
        return [], len(pending_requests) if 'pending_requests' in locals() else 0
    finally:
        if conn:
            conn.close()


def reject_manual_checkin_request(request_id: int, admin_id: int) -> bool:
    """
    Отклоняет заявку на ручную отметку.
    
    Args:
        request_id: ID заявки
        admin_id: ID администратора
        
    Returns:
        True если успешно, False при ошибке
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        processed_time_str = datetime_to_db_string(datetime.now(MOSCOW_TZ))

        cursor.execute("""
            UPDATE manual_checkin_requests
            SET status = 'rejected',
                admin_id_processed = ?,
                processed_timestamp = ?
            WHERE request_id = ? AND status = 'pending'
        """, (admin_id, processed_time_str, request_id))
        
        if cursor.rowcount == 0:
            logger.warning(
                f"Не удалось отклонить заявку {request_id} (возможно, уже обработана или не найдена)."
            )
            return False
            
        conn.commit()
        logger.info(f"Заявка {request_id} отклонена админом {admin_id}.")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Ошибка при отклонении ручной заявки {request_id}: {e}", exc_info=True)
        return False
    finally:
        if conn:
            conn.close()


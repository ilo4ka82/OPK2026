"""
Операции с рабочими сессиями в базе данных.
"""
import sqlite3
import logging
from datetime import datetime, timedelta, date
from typing import Optional, List, Tuple
import pytz

from .connection import get_db_connection
from ..utils import datetime_to_db_string, parse_datetime_from_db, format_duration

logger = logging.getLogger(__name__)
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def record_check_in(user_id: int, latitude: float, longitude: float) -> Tuple[bool, str]:
    """
    Записывает время прихода по геолокации.
    
    Args:
        user_id: Telegram ID пользователя
        latitude: Широта
        longitude: Долгота
        
    Returns:
        (успех, сообщение)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Проверка на активную сессию
        cursor.execute(
            "SELECT session_id FROM work_sessions WHERE telegram_id = ? AND check_out_time IS NULL",
            (user_id,)
        )
        existing_session = cursor.fetchone()
        
        if existing_session:
            logger.warning(f"Пользователь {user_id} попытался отметиться на приходе, уже имея активную сессию.")
            return (False, "❌ Вы уже отметились на приходе. Сначала нужно отметить уход.")

        # Получение департамента пользователя
        cursor.execute("SELECT application_department FROM users WHERE telegram_id = ?", (user_id,))
        user_record = cursor.fetchone()
        user_department = user_record['application_department'] if user_record else None

        # Получаем текущее московское время
        moscow_time_now = datetime.now(MOSCOW_TZ)
        checkin_time_str_for_db = datetime_to_db_string(moscow_time_now)

        # Записываем сессию
        cursor.execute("""
            INSERT INTO work_sessions (telegram_id, check_in_time, checkin_type, latitude, longitude, sector_id)
            VALUES (?, ?, 'geo', ?, ?, ?)
        """, (user_id, checkin_time_str_for_db, latitude, longitude, user_department))
        
        conn.commit()
        
        time_str_for_message = moscow_time_now.strftime('%H:%M:%S')
        logger.info(
            f"Пользователь {user_id} успешно отметил приход по гео в {time_str_for_message} (МСК) "
            f"в департаменте '{user_department}'."
        )
        return (True, f"✅ Вы успешно отметили приход в {time_str_for_message}!")

    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Ошибка при записи прихода для {user_id}: {e}", exc_info=True)
        return (False, "❌ Произошла ошибка базы данных при попытке отметить приход.")
    finally:
        if conn:
            conn.close()


def record_check_out(user_id: int) -> Tuple[bool, str]:
    """
    Записывает время ухода и вычисляет длительность сессии.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        (успех, сообщение)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Находим активную сессию
        cursor.execute("""
            SELECT session_id, check_in_time FROM work_sessions
            WHERE telegram_id = ? AND check_out_time IS NULL
            ORDER BY check_in_time DESC
            LIMIT 1
        """, (user_id,))
        
        row = cursor.fetchone()
        if not row:
            logger.warning(f"Пользователь {user_id} попытался уйти, не имея активных сессий.")
            return (False, "❌ Вы не были отмечены на приходе. Невозможно отметить уход.")
        
        last_session = dict(row)
        session_to_close_id = last_session['session_id']
        check_in_time_msk_str = last_session['check_in_time']
        
        # Парсим время прихода
        check_in_moscow_dt = parse_datetime_from_db(check_in_time_msk_str)
        
        # Получаем текущее время ухода
        checkout_moscow_dt = datetime.now(MOSCOW_TZ)
        
        # Вычисляем длительность
        duration_str = format_duration(check_in_moscow_dt, checkout_moscow_dt)
        
        # Обновляем сессию
        checkout_time_str_for_db = datetime_to_db_string(checkout_moscow_dt)
        cursor.execute(
            "UPDATE work_sessions SET check_out_time = ? WHERE session_id = ?",
            (checkout_time_str_for_db, session_to_close_id)
        )
        conn.commit()
        
        checkout_time_display = checkout_moscow_dt.strftime('%H:%M:%S')
        message = (
            f"✅ Вы успешно отметили уход в {checkout_time_display}.\n\n"
            f"⏱️ **Продолжительность сессии:** {duration_str}\n\n"
            f"Хорошего вечера!"
        )
        
        logger.info(
            f"Пользователь {user_id} успешно отметил уход для сессии {session_to_close_id}. "
            f"Длительность: {duration_str}."
        )
        return (True, message)

    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Ошибка при записи ухода для {user_id}: {e}", exc_info=True)
        return (False, "❌ Произошла ошибка базы данных при попытке отметить уход.")
    finally:
        if conn:
            conn.close()


def get_active_users_by_department(department: str) -> List[dict]:
    """
    Возвращает список пользователей на смене (с открытой сессией после 5 утра).
    
    Args:
        department: Название департамента или 'ALL' для всех
        
    Returns:
        Список словарей с данными пользователей
    """
    conn = None
    try:
        # Вычисляем точку отсечки (5 утра текущего рабочего дня)
        now_moscow = datetime.now(MOSCOW_TZ)
        cutoff_time_moscow = now_moscow.replace(hour=5, minute=0, second=0, microsecond=0)
        
        # Если сейчас раньше 5 утра, то рабочий день еще вчерашний
        if now_moscow < cutoff_time_moscow:
            cutoff_time_moscow -= timedelta(days=1)
            
        cutoff_time_str = datetime_to_db_string(cutoff_time_moscow)

        conn = get_db_connection()
        cursor = conn.cursor()

        sql_query = """
            SELECT
                u.application_full_name,
                u.username,
                u.application_department,
                t.max_check_in_time AS check_in_time
            FROM (
                SELECT
                    telegram_id,
                    MAX(check_in_time) AS max_check_in_time
                FROM work_sessions
                WHERE 
                    check_out_time IS NULL 
                    AND check_in_time >= ?
                GROUP BY telegram_id
            ) AS t
            JOIN users u ON t.telegram_id = u.telegram_id
            WHERE
                (? = 'ALL' OR u.application_department = ?)
            ORDER BY
                u.application_department, u.application_full_name ASC
        """
        
        cursor.execute(sql_query, (cutoff_time_str, department, department))
        results = [dict(row) for row in cursor.fetchall()]
        
        logger.info(
            f"Запрос для /on_shift (отсечка: {cutoff_time_str}) вернул {len(results)} строк."
        )
        return results

    except sqlite3.Error as e:
        logger.error(
            f"Ошибка при получении активных пользователей для департамента '{department}': {e}",
            exc_info=True
        )
        return []
    finally:
        if conn:
            conn.close()


def get_completed_sessions_for_user(user_id: int, period: str) -> List[dict]:
    """
    Получает завершенные сессии пользователя за период.
    
    Args:
        user_id: Telegram ID пользователя
        period: 'last5', 'week', 'month'
        
    Returns:
        Список словарей с данными сессий
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        sql_query = """
            SELECT session_id, check_in_time, check_out_time
            FROM work_sessions
            WHERE telegram_id = ? AND check_out_time IS NOT NULL
            ORDER BY check_in_time DESC
        """
        
        cursor.execute(sql_query, (user_id,))
        all_sessions = [dict(row) for row in cursor.fetchall()]

        if period == 'last5':
            return all_sessions[:5]

        # Вычисляем дату отсечки для фильтрации
        if period == 'week':
            cutoff_date = datetime.now(MOSCOW_TZ) - timedelta(days=7)
        elif period == 'month':
            cutoff_date = datetime.now(MOSCOW_TZ) - timedelta(days=30)
        else:
            return []
            
        filtered_sessions = []
        for session in all_sessions:
            try:
                session_dt = parse_datetime_from_db(session['check_in_time'])
                
                if session_dt >= cutoff_date:
                    filtered_sessions.append(session)
            except Exception as e:
                logger.error(f"Ошибка при обработке сессии ID {session['session_id']}: {e}")
                continue
        
        return filtered_sessions

    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении сессий для {user_id}: {e}", exc_info=True)
        return []
    finally:
        if conn:
            conn.close()


def update_session_checkout_time(session_id: int, new_checkout_time_str: str) -> bool:
    """
    Обновляет время ухода для конкретной сессии.
    
    Args:
        session_id: ID сессии
        new_checkout_time_str: Новое время в формате 'YYYY-MM-DD HH:MM:SS'
        
    Returns:
        True если успешно, False при ошибке
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем время прихода для вычисления новой длительности
        cursor.execute("SELECT check_in_time FROM work_sessions WHERE session_id = ?", (session_id,))
        result = cursor.fetchone()
        if not result:
            logger.error(f"Не удалось найти сессию {session_id} для обновления.")
            return False
            
        check_in_time_str = result['check_in_time']
        
        # Считаем новую длительность
        check_in_dt = datetime.strptime(check_in_time_str, '%Y-%m-%d %H:%M:%S')
        new_checkout_dt = datetime.strptime(new_checkout_time_str, '%Y-%m-%d %H:%M:%S')
        new_duration = (new_checkout_dt - check_in_dt).total_seconds() / 60
        new_duration_minutes = int(new_duration)

        # Обновляем оба поля
        sql_query = """
            UPDATE work_sessions 
            SET 
                check_out_time = ?, 
                duration_minutes = ? 
            WHERE 
                session_id = ?
        """
        cursor.execute(sql_query, (new_checkout_time_str, new_duration_minutes, session_id))
        conn.commit()
        
        if cursor.rowcount > 0:
            logger.info(
                f"Сессия {session_id} успешно обновлена. "
                f"Новое время ухода: {new_checkout_time_str}, новая длительность: {new_duration_minutes} мин."
            )
            return True
        else:
            logger.warning(f"Не удалось обновить сессию {session_id} (rowcount = 0).")
            return False

    except (sqlite3.Error, ValueError, TypeError) as e:
        logger.error(f"Ошибка при обновлении сессии {session_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def get_attendance_data_for_period(
    start_date: datetime,
    end_date: datetime,
    sector_key: Optional[str] = None
) -> List[dict]:
    """
    Получает данные о посещаемости за период для экспорта.
    
    Args:
        start_date: Начальная дата
        end_date: Конечная дата
        sector_key: Ключ сектора или None для всех
        
    Returns:
        Список словарей с данными сессий
    """
    conn = None
    attendance_data = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                u.application_full_name,
                u.username,
                u.application_department,
                ws.check_in_time AS session_start_time, 
                ws.check_out_time AS session_end_time
            FROM work_sessions ws
            JOIN users u ON ws.telegram_id = u.telegram_id
            WHERE ws.check_in_time BETWEEN ? AND ? 
        """
        
        params = [start_date, end_date]
        
        if sector_key and sector_key.upper() != 'ALL':
            query += " AND UPPER(u.application_department) = ? "
            params.append(sector_key.upper())
        
        query += " ORDER BY u.application_full_name ASC, ws.check_in_time ASC"
        
        cursor.execute(query, tuple(params))
        
        columns = [desc[0] for desc in cursor.description]
        for row in cursor.fetchall():
            attendance_data.append(dict(zip(columns, row)))
        
        logger.info(f"Получено {len(attendance_data)} записей о посещаемости для отчета.")
    
    except sqlite3.Error as e:
        logger.error(f"Ошибка SQLite при получении данных о посещаемости: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
    
    return attendance_data
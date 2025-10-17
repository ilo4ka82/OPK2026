"""
Функции форматирования данных для табеля.
"""
from datetime import datetime, timedelta
from typing import Union
import pytz

MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def format_seconds_to_hhmmss(seconds_val: Union[int, float, None]) -> str:
    """
    Форматирует количество секунд в строку ЧЧ:ММ:СС.
    
    Args:
        seconds_val: Количество секунд (int/float) или None
        
    Returns:
        Строка формата "ЧЧ:ММ:СС" или "Активна" если данные некорректны
    """
    if seconds_val is None or not isinstance(seconds_val, (int, float)) or seconds_val < 0:
        return "Активна"
    
    seconds_val = int(seconds_val)
    hours = seconds_val // 3600
    minutes = (seconds_val % 3600) // 60
    secs = seconds_val % 60
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_duration(start_time: datetime, end_time: datetime) -> str:
    """
    Вычисляет и форматирует длительность между двумя временными точками.
    
    Args:
        start_time: Начальное время
        end_time: Конечное время
        
    Returns:
        Строка формата "X ч YY мин"
    """
    duration = end_time - start_time
    total_seconds = int(duration.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    return f"{hours} ч {minutes:02d} мин"


def format_time_for_display(dt: datetime, format_str: str = '%H:%M:%S') -> str:
    """
    Форматирует datetime объект для отображения пользователю.
    
    Args:
        dt: Datetime объект
        format_str: Строка формата (по умолчанию '%H:%M:%S')
        
    Returns:
        Отформатированная строка
    """
    if not isinstance(dt, datetime):
        return "Неизвестно"
    
    return dt.strftime(format_str)


def escape_markdown_v2(text: str) -> str:
    """
    Экранирует специальные символы для Telegram MarkdownV2.
    
    Args:
        text: Исходный текст
        
    Returns:
        Экранированный текст
    """
    if not isinstance(text, str):
        text = str(text)
    
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return "".join(f'\\{char}' if char in escape_chars else char for char in text)


def parse_datetime_from_db(dt_string: str) -> datetime:
    """
    Парсит строку времени из БД в datetime объект с московским часовым поясом.
    
    Args:
        dt_string: Строка формата 'YYYY-MM-DD HH:MM:SS'
        
    Returns:
        Datetime объект с timezone=MOSCOW_TZ
        
    Raises:
        ValueError: Если формат строки неверный
    """
    naive_dt = datetime.strptime(dt_string, '%Y-%m-%d %H:%M:%S')
    return MOSCOW_TZ.localize(naive_dt)


def datetime_to_db_string(dt: datetime) -> str:
    """
    Конвертирует datetime объект в строку для записи в БД.
    
    Args:
        dt: Datetime объект (желательно с timezone)
        
    Returns:
        Строка формата 'YYYY-MM-DD HH:MM:SS'
    """
    if dt.tzinfo is None:
        # Если timezone не указан, считаем что это московское время
        dt = MOSCOW_TZ.localize(dt)
    elif dt.tzinfo != MOSCOW_TZ:
        # Конвертируем в московское время
        dt = dt.astimezone(MOSCOW_TZ)
    
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def format_user_for_display(user_data: dict) -> str:
    """
    Форматирует данные пользователя для отображения.
    
    Args:
        user_data: Словарь с данными пользователя из БД
        
    Returns:
        Отформатированная строка с именем пользователя
    """
    # Приоритет: application_full_name > username > "Без имени"
    display_name = (
        user_data.get('application_full_name') or 
        f"@{user_data.get('username', 'unknown')}" if user_data.get('username') else
        'Без имени'
    )
    return display_name
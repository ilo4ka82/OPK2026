"""
Функции валидации данных для табеля.
"""
from datetime import datetime
from typing import Tuple
from .constants import THE_OFFICE_ZONE


def is_within_office_zone(latitude: float, longitude: float) -> bool:
    """
    Проверяет, находятся ли координаты внутри разрешенной геозоны офиса.
    
    Args:
        latitude: Широта
        longitude: Долгота
        
    Returns:
        True если внутри зоны, False если снаружи
    """
    min_lat = THE_OFFICE_ZONE["min_latitude"]
    max_lat = THE_OFFICE_ZONE["max_latitude"]
    min_lon = THE_OFFICE_ZONE["min_longitude"]
    max_lon = THE_OFFICE_ZONE["max_longitude"]
    
    return (min_lat <= latitude <= max_lat and 
            min_lon <= longitude <= max_lon)


def validate_full_name(name: str) -> Tuple[bool, str]:
    """
    Валидирует ФИО пользователя.
    
    Args:
        name: Введенное ФИО
        
    Returns:
        (валидно, сообщение об ошибке)
    """
    if not name or len(name.strip()) < 5:
        return False, "Пожалуйста, введите корректное полное имя (не менее 5 символов)."
    
    return True, ""


def validate_department(department: str) -> Tuple[bool, str]:
    """
    Валидирует название департамента.
    
    Args:
        department: Введенный департамент
        
    Returns:
        (валидно, сообщение об ошибке)
    """
    if not department or len(department.strip()) < 2:
        return False, "Пожалуйста, введите корректное название сектора (не менее 2 символов)."
    
    return True, ""


def validate_datetime_format(dt_string: str, format_str: str = '%d.%m.%Y %H:%M') -> Tuple[bool, datetime, str]:
    """
    Валидирует строку даты-времени.
    
    Args:
        dt_string: Строка с датой/временем
        format_str: Ожидаемый формат
        
    Returns:
        (валидно, datetime объект или None, сообщение об ошибке)
    """
    try:
        dt = datetime.strptime(dt_string, format_str)
        return True, dt, ""
    except ValueError:
        error_msg = f"Неверный формат. Пожалуйста, введите время в формате ДД.ММ.ГГГГ ЧЧ:ММ"
        return False, None, error_msg


def validate_location_age(message_date: datetime, max_age_seconds: int = 300) -> Tuple[bool, int]:
    """
    Проверяет возраст геолокации.
    
    Args:
        message_date: Время сообщения с геолокацией
        max_age_seconds: Максимально допустимый возраст (секунд)
        
    Returns:
        (валидно, возраст в секундах)
    """
    from datetime import timezone
    current_date = datetime.now(timezone.utc)
    age = current_date - message_date
    age_seconds = int(age.total_seconds())
    
    return age_seconds <= max_age_seconds, age_seconds
"""
Утилиты для работы табеля.
"""
import pytz

from .constants import *
from .formatters import (
    format_seconds_to_hhmmss,
    format_duration,
    format_time_for_display,
    escape_markdown_v2,
    parse_datetime_from_db,
    datetime_to_db_string,
    format_user_for_display,
)
from .validators import (
    is_within_office_zone,
    validate_full_name,
    validate_department,
    validate_datetime_format,
    validate_location_age,
)
# НЕ ИМПОРТИРУЕМ decorators! Они используют telegram
# from .decorators import admin_required, log_errors  # ← ЗАКОММЕНТИРОВАЛИ
from .messages import TimesheetMessages, AdminMessages

MOSCOW_TZ = pytz.timezone('Europe/Moscow')

__all__ = [
    # Constants
    'THE_OFFICE_ZONE',
    'SECTOR_WEEKLY_NORMS',
    'SECTOR_SCHEDULES',
    'PREDEFINED_SECTORS',
    'ITEMS_PER_PAGE',
    'SESSIONS_PER_PAGE',
    'MAX_LOCATION_AGE_SECONDS',
    'MOSCOW_TIMEZONE',
    'MOSCOW_TZ',
    
    # Formatters
    'format_seconds_to_hhmmss',
    'format_duration',
    'format_time_for_display',
    'escape_markdown_v2',
    'parse_datetime_from_db',
    'datetime_to_db_string',
    'format_user_for_display',
    
    # Validators
    'is_within_office_zone',
    'validate_full_name',
    'validate_department',
    'validate_datetime_format',
    'validate_location_age',
    
    # Decorators - УБРАЛИ ИЗ ЭКСПОРТА
    # 'admin_required',
    # 'log_errors',
    
    # Messages
    'TimesheetMessages',
    'AdminMessages',
]
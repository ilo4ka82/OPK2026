"""
Модуль работы с базой данных табеля.
"""
from .connection import get_db_connection, init_db
from .users import (
    add_or_update_user,
    get_user,
    is_user_authorized,
    authorize_user,
    list_pending_users,
    submit_application,
    reject_application,
    find_users_by_name,
    get_unique_user_departments,
)
from .sessions import (
    record_check_in,
    record_check_out,
    get_active_users_by_department,
    get_completed_sessions_for_user,
    update_session_checkout_time,
    get_attendance_data_for_period,
)
from .manual_requests import (
    add_manual_checkin_request,
    get_pending_manual_checkin_requests,
    get_manual_checkin_request_by_id,
    approve_manual_checkin_request,
    approve_all_pending_manual_checkins,
    reject_manual_checkin_request,
)

__all__ = [
    # Connection
    'get_db_connection',
    'init_db',
    
    # Users
    'add_or_update_user',
    'get_user',
    'is_user_authorized',
    'authorize_user',
    'list_pending_users',
    'submit_application',
    'reject_application',
    'find_users_by_name',
    'get_unique_user_departments',
    
    # Sessions
    'record_check_in',
    'record_check_out',
    'get_active_users_by_department',
    'get_completed_sessions_for_user',
    'update_session_checkout_time',
    'get_attendance_data_for_period',
    
    # Manual Requests
    'add_manual_checkin_request',
    'get_pending_manual_checkin_requests',
    'get_manual_checkin_request_by_id',
    'approve_manual_checkin_request',
    'approve_all_pending_manual_checkins',
    'reject_manual_checkin_request',
]
# backend/__init__.py
from .queries_db import (
    check_nickname, check_password,
    create_user, verify_user, get_user_by_id,
    create_group, join_group, get_user_groups,
    add_expense, delete_expense, get_expenses,
    get_group_stats, get_personal_total, get_categories,
    add_debt, delete_debt, get_group_debts, get_group_members_for_select,
    # Добавляем функции уведомлений
    add_notification,
    get_notifications,
    get_unread_count,
    mark_notification_read,
    mark_all_notifications_read
)
from .init_db import init_db   # экспортируем init_db
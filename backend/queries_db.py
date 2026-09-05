from typing import Optional, List, Dict
from decimal import Decimal
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

from .models.db_user import User
from .models.db_group import Group
from .models.db_group_member import GroupMember
from .models.db_expense import Expense
from .models.db_debt import Debt
from .database import get_connection

# ---------- Валидация (можно вынести в отдельный модуль) ----------
def check_nickname(nickname: str):
    import re
    if not nickname or not nickname.strip():
        return "Никнейм не может быть пустым."
    if len(nickname) < 3:
        return "Никнейм должен быть не короче 3 символов."
    if len(nickname) > 20:
        return "Никнейм должен быть не длиннее 20 символов."
    if not re.match(r'^[a-zA-Z]+$', nickname):
        return "Никнейм может содержать только латинские буквы."
    return None

def check_password(password: str):
    import re
    if not password:
        return "Пароль не может быть пустым."
    if len(password) < 8:
        return "Пароль должен быть не короче 8 символов."
    if len(password) > 15:
        return "Пароль должен быть не длиннее 15 символов."
    if not re.search(r'[A-Z]', password):
        return "Пароль должен содержать хотя бы одну заглавную латинскую букву."
    if not re.search(r'[0-9]', password):
        return "Пароль должен содержать хотя бы одну цифру."
    if not re.search(r'[^a-zA-Z0-9]', password):
        return "Пароль должен содержать хотя бы один специальный символ."
    if not re.match(r'^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{}|;:\'",.<>\/?~`]+$', password):
        return "Пароль содержит недопустимые символы."
    return None

# ---------- User ----------
def create_user(nickname: str, real_name: str, password: str) -> int:
    hashed = generate_password_hash(password)
    user = User.create(nickname, real_name, hashed)
    return user.id

def verify_user(nickname: str, password: str) -> Optional[Dict]:
    user = User.get_by_nickname(nickname)
    if user and check_password_hash(user.password_hash, password):
        return {"id": user.id, "nickname": user.nickname, "real_name": user.real_name}
    return None

def get_user_by_id(user_id: int) -> Optional[Dict]:
    user = User.get_by_id(user_id)
    if user:
        return {"id": user.id, "nickname": user.nickname, "real_name": user.real_name}
    return None

# ---------- Groups ----------
def create_group(name: str) -> Dict:
    import uuid
    code = uuid.uuid4().hex[:6].upper()
    group = Group.create(name, code)
    return {"id": group.id, "name": group.name, "code": group.code}

def join_group(code: str, user_id: int) -> Optional[Dict]:
    group = Group.get_by_code(code)
    if not group:
        return None
    GroupMember.create(user_id, group.id)
    return {"id": group.id, "name": group.name, "code": group.code}

def get_user_groups(user_id: int) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT g.* FROM groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.user_id = ?
        ORDER BY g.created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "code": r[2], "created_at": r[3]} for r in rows]

# ---------- Expenses ----------
def add_expense(amount: float, category: str, description: str, date: str,
                user_id: int, group_id: int = None):
    exp = Expense.create(user_id, group_id, amount, category, description, date)
    return exp.id

def delete_expense(expense_id: int):
    Expense.delete(expense_id)

def get_expenses(month: str = None, category: str = None,
                 group_id: int = None, user_id: int = None) -> List[Dict]:
    return Expense.get_filtered(month, category, group_id, user_id)

def get_group_stats(group_id: int, month: str) -> Dict:
    expenses = get_expenses(month=month, group_id=group_id)
    total = sum(e["amount"] for e in expenses)
    user_totals = {}
    for e in expenses:
        uid = e["user_id"]
        uname = e.get("user_name") or "Unknown"
        user_totals.setdefault(uid, {"user_id": uid, "user_name": uname, "total": 0})
        user_totals[uid]["total"] += e["amount"]
    stats = []
    for item in user_totals.values():
        perc = (item["total"] / total * 100) if total > 0 else 0
        stats.append({"user_id": item["user_id"], "user_name": item["user_name"],
                      "total": item["total"], "percentage": perc})
    stats.sort(key=lambda x: x["total"], reverse=True)
    return {"total": total, "users": stats}

def get_personal_total(user_id: int, month: str) -> float:
    expenses = get_expenses(month=month, user_id=user_id)
    return sum(e["amount"] for e in expenses)

def get_categories() -> List[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM expenses ORDER BY category")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

# ---------- Debts ----------
def init_debts_table():
    # таблица создаётся в init_db, эта функция может быть пустой или проверять существование
    pass

def add_debt(group_id: int, debtor_id: int, creditor_id: int, amount: float, description: str = None):
    Debt.create(group_id, debtor_id, creditor_id, amount, description)

def delete_debt(debt_id: int):
    Debt.delete(debt_id)

def get_group_debts(group_id: int) -> List[Dict]:
    return Debt.get_by_group(group_id)

def get_group_members_for_select(group_id: int) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.real_name
        FROM users u
        JOIN group_members gm ON u.id = gm.user_id
        WHERE gm.group_id = ?
        ORDER BY u.real_name
    """, (group_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "real_name": r[1]} for r in rows]
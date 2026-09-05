import sqlite3
import uuid
import re
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = "expenses.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nickname TEXT UNIQUE NOT NULL,
                real_name TEXT NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS group_members (
                group_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (group_id, user_id),
                FOREIGN KEY (group_id) REFERENCES groups(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                date TEXT NOT NULL,
                user_id INTEGER,
                group_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (group_id) REFERENCES groups(id)
            )
        """)


def init_debts_table():
    """Создаёт таблицу долгов (вызывается один раз при запуске)"""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS debts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                debtor_id INTEGER NOT NULL,
                creditor_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups(id),
                FOREIGN KEY (debtor_id) REFERENCES users(id),
                FOREIGN KEY (creditor_id) REFERENCES users(id)
            )
        """)


# ==================== ПРОВЕРКИ ====================

def check_nickname(nickname: str):
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


# ==================== АВТОРИЗАЦИЯ ====================

def create_user(nickname: str, real_name: str, password: str) -> int:
    hashed = generate_password_hash(password)
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (nickname, real_name, password_hash) VALUES (?, ?, ?)",
            (nickname, real_name, hashed)
        )
        return cursor.lastrowid


def verify_user(nickname: str, password: str):
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE nickname = ?", (nickname,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            return dict(user)
        return None


def get_user_by_id(user_id: int):
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(user) if user else None


# ==================== ГРУППЫ ====================

def create_group(name: str):
    code = uuid.uuid4().hex[:6].upper()
    with get_db() as conn:
        cursor = conn.execute("INSERT INTO groups (name, code) VALUES (?, ?)", (name, code))
        return {"id": cursor.lastrowid, "name": name, "code": code}


def join_group(code: str, user_id: int):
    with get_db() as conn:
        group = conn.execute("SELECT * FROM groups WHERE code = ?", (code,)).fetchone()
        if not group:
            return None
        conn.execute(
            "INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)",
            (group["id"], user_id)
        )
        return dict(group)


def get_user_groups(user_id: int):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT g.* FROM groups g
            JOIN group_members gm ON g.id = gm.group_id
            WHERE gm.user_id = ?
            ORDER BY g.created_at DESC
        """, (user_id,)).fetchall()
        return [dict(r) for r in rows]


# ==================== РАСХОДЫ ====================

def add_expense(amount: float, category: str, description: str, date: str,
                user_id: int, group_id: int = None):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO expenses
               (amount, category, description, date, user_id, group_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (amount, category, description or None, date, user_id, group_id)
        )


def delete_expense(expense_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))


def get_expenses(month: str = None, category: str = None,
                 group_id: int = None, user_id: int = None):
    query = """SELECT e.*, u.real_name as user_name
               FROM expenses e
               LEFT JOIN users u ON e.user_id = u.id
               WHERE 1=1"""
    params = []

    if group_id:
        query += " AND e.group_id = ?"
        params.append(group_id)
    elif user_id:
        query += " AND e.group_id IS NULL AND e.user_id = ?"
        params.append(user_id)

    if month:
        query += " AND strftime('%Y-%m', e.date) = ?"
        params.append(month)
    if category:
        query += " AND e.category = ?"
        params.append(category)

    query += " ORDER BY e.date DESC, e.id DESC"

    with get_db() as conn:
        return conn.execute(query, params).fetchall()


def get_group_stats(group_id: int, month: str):
    with get_db() as conn:
        total_row = conn.execute(
            """SELECT COALESCE(SUM(amount), 0) as total
               FROM expenses
               WHERE group_id = ? AND strftime('%Y-%m', date) = ?""",
            (group_id, month)
        ).fetchone()
        total = total_row["total"]

        user_stats = conn.execute(
            """SELECT e.user_id, u.real_name as user_name, SUM(e.amount) as user_total
               FROM expenses e
               LEFT JOIN users u ON e.user_id = u.id
               WHERE e.group_id = ? AND strftime('%Y-%m', e.date) = ?
               GROUP BY e.user_id, u.real_name
               ORDER BY user_total DESC""",
            (group_id, month)
        ).fetchall()

        stats = []
        for row in user_stats:
            percentage = (row["user_total"] / total * 100) if total > 0 else 0
            stats.append({
                "user_id": row["user_id"],
                "user_name": row["user_name"],
                "total": row["user_total"],
                "percentage": percentage
            })

        return {"total": total, "users": stats}


def get_personal_total(user_id: int, month: str):
    with get_db() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(amount), 0) as total
               FROM expenses
               WHERE user_id = ? AND group_id IS NULL
               AND strftime('%Y-%m', date) = ?""",
            (user_id, month)
        ).fetchone()
        return row["total"]


def get_categories():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM expenses ORDER BY category"
        ).fetchall()
        return [r[0] for r in rows]


# ==================== ДОЛГИ ====================

def add_debt(group_id: int, debtor_id: int, creditor_id: int, amount: float, description: str = None):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO debts (group_id, debtor_id, creditor_id, amount, description)
               VALUES (?, ?, ?, ?, ?)""",
            (group_id, debtor_id, creditor_id, amount, description)
        )


def delete_debt(debt_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM debts WHERE id = ?", (debt_id,))


def get_group_debts(group_id: int):
    with get_db() as conn:
        return conn.execute("""
            SELECT d.*, 
                   u1.real_name as debtor_name,
                   u2.real_name as creditor_name
            FROM debts d
            LEFT JOIN users u1 ON d.debtor_id = u1.id
            LEFT JOIN users u2 ON d.creditor_id = u2.id
            WHERE d.group_id = ?
            ORDER BY d.created_at DESC
        """, (group_id,)).fetchall()


def get_group_members_for_select(group_id: int):
    """Возвращает список участников группы для выпадающего списка"""
    with get_db() as conn:
        return conn.execute("""
            SELECT u.id, u.real_name
            FROM users u
            JOIN group_members gm ON u.id = gm.user_id
            WHERE gm.group_id = ?
            ORDER BY u.real_name
        """, (group_id,)).fetchall()
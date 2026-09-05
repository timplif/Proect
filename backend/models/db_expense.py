from ..database import get_connection
from datetime import datetime

class Expense:
    def __init__(self, id=None, user_id=None, group_id=None, amount=None,
                 category=None, description=None, date=None):
        self.id = id
        self.user_id = user_id
        self.group_id = group_id
        self.amount = amount          # Decimal или float
        self.category = category
        self.description = description
        self.date = date              # строка YYYY-MM-DD

    @classmethod
    def create(cls, user_id, group_id, amount, category, description=None, date=None):
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO expenses (user_id, group_id, amount, category, description, date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, group_id, float(amount), category, description, date)
        )
        conn.commit()
        exp_id = cursor.lastrowid
        conn.close()
        return cls(id=exp_id, user_id=user_id, group_id=group_id, amount=amount,
                   category=category, description=description, date=date)

    @classmethod
    def delete(cls, expense_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
        conn.close()

    @classmethod
    def get_filtered(cls, month=None, category=None, group_id=None, user_id=None):
        query = """SELECT e.*, u.real_name as user_name
                   FROM expenses e
                   LEFT JOIN users u ON e.user_id = u.id
                   WHERE 1=1"""
        params = []
        if group_id is not None:
            query += " AND e.group_id = ?"
            params.append(group_id)
        elif user_id is not None:
            query += " AND e.group_id IS NULL AND e.user_id = ?"
            params.append(user_id)
        if month:
            query += " AND strftime('%Y-%m', e.date) = ?"
            params.append(month)
        if category:
            query += " AND e.category = ?"
            params.append(category)
        query += " ORDER BY e.date DESC, e.id DESC"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        # возвращаем список словарей (как в старом database.py)
        result = []
        for row in rows:
            result.append({
                "id": row[0],
                "amount": row[1],
                "category": row[2],
                "description": row[3],
                "date": row[4],
                "user_id": row[5],
                "group_id": row[6],
                "user_name": row[7] if len(row) > 7 else None
            })
        return result
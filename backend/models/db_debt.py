from ..database import get_connection

class Debt:
    def __init__(self, id=None, group_id=None, debtor_id=None, creditor_id=None,
                 amount=None, description=None, created_at=None):
        self.id = id
        self.group_id = group_id
        self.debtor_id = debtor_id
        self.creditor_id = creditor_id
        self.amount = amount
        self.description = description
        self.created_at = created_at

    @classmethod
    def create(cls, group_id, debtor_id, creditor_id, amount, description=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO debts (group_id, debtor_id, creditor_id, amount, description)
               VALUES (?, ?, ?, ?, ?)""",
            (group_id, debtor_id, creditor_id, float(amount), description)
        )
        conn.commit()
        debt_id = cursor.lastrowid
        conn.close()
        return cls(id=debt_id, group_id=group_id, debtor_id=debtor_id,
                   creditor_id=creditor_id, amount=amount, description=description)

    @classmethod
    def delete(cls, debt_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM debts WHERE id = ?", (debt_id,))
        conn.commit()
        conn.close()

    @classmethod
    def get_by_group(cls, group_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT d.*, u1.real_name as debtor_name, u2.real_name as creditor_name
               FROM debts d
               LEFT JOIN users u1 ON d.debtor_id = u1.id
               LEFT JOIN users u2 ON d.creditor_id = u2.id
               WHERE d.group_id = ?
               ORDER BY d.created_at DESC""",
            (group_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        result = []
        for row in rows:
            result.append({
                "id": row[0],
                "group_id": row[1],
                "debtor_id": row[2],
                "creditor_id": row[3],
                "amount": row[4],
                "description": row[5],
                "created_at": row[6],
                "debtor_name": row[7],
                "creditor_name": row[8]
            })
        return result
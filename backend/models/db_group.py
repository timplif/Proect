from ..database import get_connection

class Group:
    def __init__(self, id=None, name=None, code=None, created_at=None):
        self.id = id
        self.name = name
        self.code = code          # ваше поле code (вместо invite_code)
        self.created_at = created_at

    @classmethod
    def create(cls, name, code):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO groups (name, code) VALUES (?, ?)",
            (name, code)
        )
        conn.commit()
        group_id = cursor.lastrowid
        conn.close()
        return cls(id=group_id, name=name, code=code)

    @classmethod
    def get_by_code(cls, code):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, code, created_at FROM groups WHERE code = ?", (code,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return cls(id=row[0], name=row[1], code=row[2], created_at=row[3])
        return None

    @classmethod
    def get_by_id(cls, group_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, code, created_at FROM groups WHERE id = ?", (group_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return cls(id=row[0], name=row[1], code=row[2], created_at=row[3])
        return None
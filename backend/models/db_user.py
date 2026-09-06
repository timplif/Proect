from ..database import get_connection

class User:
    def __init__(self, id=None, nickname=None, real_name=None, password_hash=None):
        self.id = id
        self.nickname = nickname
        self.real_name = real_name
        self.password_hash = password_hash

    @classmethod
    def create(cls, nickname, real_name, password_hash):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (nickname, real_name, password_hash) VALUES (?, ?, ?)",
            (nickname, real_name, password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return cls(id=user_id, nickname=nickname, real_name=real_name, password_hash=password_hash)

    @classmethod
    def get_by_nickname(cls, nickname):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nickname, real_name, password_hash FROM users WHERE nickname = ?", (nickname,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return cls(id=row[0], nickname=row[1], real_name=row[2], password_hash=row[3])
        return None

    @classmethod
    def get_by_id(cls, user_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nickname, real_name, password_hash FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return cls(id=row[0], nickname=row[1], real_name=row[2], password_hash=row[3])
        return None
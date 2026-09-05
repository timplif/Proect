from ..database import get_connection

class GroupMember:
    def __init__(self, group_id=None, user_id=None):
        self.group_id = group_id
        self.user_id = user_id

    @classmethod
    def create(cls, user_id, group_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)",
            (group_id, user_id)
        )
        conn.commit()
        conn.close()
        return cls(group_id=group_id, user_id=user_id)

    @classmethod
    def get_by_user_and_group(cls, user_id, group_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT group_id, user_id FROM group_members WHERE user_id = ? AND group_id = ?",
            (user_id, group_id)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return cls(group_id=row[0], user_id=row[1])
        return None

    @classmethod
    def get_members_by_group(cls, group_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM group_members WHERE group_id = ?",
            (group_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]
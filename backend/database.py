# backend/database.py
import sqlite3
from config import DB_PATH   # импортируем единый путь

def get_connection():
    """Возвращает новое соединение с SQLite."""
    return sqlite3.connect(DB_PATH)

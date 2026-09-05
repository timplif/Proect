import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database.sqlite3')

def get_connection():
    """Возвращает новое соединение с SQLite."""
    return sqlite3.connect(DB_PATH)

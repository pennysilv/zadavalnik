import sqlite3

def create_sessions_table(conn):
    """
    Создает таблицу sessions для хранения сессий пользователей.
    """
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER PRIMARY KEY,
            session_start DATETIME NOT NULL
        )
    """)
    conn.commit()
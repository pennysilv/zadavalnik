import sqlite3
from zadavalnik.config.settings import Settings
from zadavalnik.database.models import create_sessions_table
# from zadavalnik.utils.helpers import get_current_time

from datetime import datetime



def init_db():
    """
    Инициализирует базу данных и создает таблицы.
    """
    with sqlite3.connect(Settings.DB_PATH) as conn:
        create_sessions_table(conn)

def add_session(user_id):
    """
    Добавляет новую сессию для пользователя с текущей временной меткой.
    """
    try:
        with sqlite3.connect(Settings.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO sessions (user_id, session_start)
                VALUES (?, ?)
                """,
                (user_id, datetime.now().isoformat())
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"Ошибка при добавлении сессии: {e}")
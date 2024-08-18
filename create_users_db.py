import sqlite3

def create_db():
    conn = sqlite3.connect('book_catalog.db')
    cursor = conn.cursor()

    # Создание таблицы для хранения книг
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            chat_id INTEGER NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

create_db()
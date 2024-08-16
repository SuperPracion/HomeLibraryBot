import sqlite3

def create_db():
    conn = sqlite3.connect('book_catalog.db')
    cursor = conn.cursor()

    # Создание таблицы для хранения книг
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY NOT NULL,
            name TEXT NOT NULL,
            holder TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

create_db()
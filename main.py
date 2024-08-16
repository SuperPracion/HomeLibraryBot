import sqlite3
from telegram import Update
from telegram.ext import Application, CallbackContext, CommandHandler

# Функция для подключения к БД
def get_db_connection():
    conn = sqlite3.connect("book_catalog.db")
    return conn


# Команда /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Привет! Это книжный каталог. Вы можете добавлять книги с помощью команды /add, "
        "просматривать каталог с помощью команды /catalog, брать книги через команду /take и "
        "редактировать/удалять свои книги с помощью команд /edit и /delete."
    )


# Вспомогательная функция для получения идентификатора следующей книги
def get_next_id():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM books ORDER BY id ASC")
    ids = cursor.fetchall()
    conn.close()

    # Ищем минимально пропущенный ID
    expected_id = 1
    for (id,) in ids:
        if id == expected_id:
            expected_id += 1
        else:
            break

    return expected_id


# Добавление книги
async def add_book(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        await update.message.reply_text("Используйте /add <название книги> для добавления книги.")
        return

    book_name = " ".join(context.args)
    user = update.message.from_user.username

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO books (id, name, holder) VALUES (?, ?, ?)",(get_next_id(), book_name, user),)
    conn.commit()
    conn.close()

    await update.message.reply_text(f"Книга '{book_name}' была добавлена в каталог под вашим именем!")


# Просмотр каталога
async def catalog(update: Update, context: CallbackContext):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, holder FROM books")
    books = cursor.fetchall()
    conn.close()

    if len(books) == 0:
        await update.message.reply_text("Каталог пуст.")
    else:
        catalog_list = "\n".join(
            [f"{book[0]}. {book[1]} (Держатель: @{book[2]})" for book in books]
        )
        await update.message.reply_text(f"Книги в каталоге:\n{catalog_list}")


# Взять книгу
async def take_book(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        await update.message.reply_text("Используйте /take <ID книги> для того, чтобы стать держателем.")
        return

    book_id = context.args[0]
    user = update.message.from_user.username

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT holder FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()

    if book is None:
        await update.message.reply_text("Книга с таким ID не найдена.")
    elif book[0] == user:
        await update.message.reply_text("Вы уже являетесь держателем этой книги.")
    else:
        cursor.execute("UPDATE books SET holder = ? WHERE id = ?",(user, book_id))
        conn.commit()
        await update.message.reply_text(f"Вы теперь держатель книги с ID {book_id}.")

    conn.close()


# Редактирование книги
async def edit_book(update: Update, context: CallbackContext):
    if len(context.args) < 2:
        await update.message.reply_text("Используйте /edit <ID книги> <новое название книги> для редактирования.")
        return

    book_id = context.args[0]
    new_name = " ".join(context.args[1:])
    user = update.message.from_user.username

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT holder, name FROM books WHERE id = ?",(book_id,))
    book = cursor.fetchone()

    # Если книги нет в бд
    if book is None:
        await update.message.reply_text("Книга с таким ID не найдена.")

    # Если текущий пользоваель не тот, кто редактирует
    if book[0] != user:
        await update.message.reply_text("Вы не являетесь держателем этой книги и не можете её редактировать.")
    elif book[0] == user:
        if book[1] == new_name:
            await update.message.reply_text("Изменений не обнаружено. Книга уже имеет это название.")
        else:
            cursor.execute("UPDATE books SET name = ? WHERE id = ?",(new_name, book_id))
            conn.commit()
            await update.message.reply_text(f"Книга с ID {book_id} была обновлена.")

    conn.close()


# Удаление книги
async def delete_book(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        await update.message.reply_text("Используйте /delete <ID книги> для удаления книги.")
        return

    book_id = context.args[0]
    user = update.message.from_user.username

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT holder FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()

    if book is None:
        await update.message.reply_text("Книга с таким ID не найдена.")
    elif book[0] == user:
        cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
        conn.commit()
        await update.message.reply_text(f"Книга с ID {book_id} была удалена из каталога.")
    else:
        await update.message.reply_text("Вы не являетесь держателем этой книги и не можете её удалить.")

    conn.close()


# Основная функция
application = (Application.builder().token("").build())

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("add", add_book))
application.add_handler(CommandHandler("catalog", catalog))
application.add_handler(CommandHandler("take", take_book))
application.add_handler(CommandHandler("edit", edit_book))
application.add_handler(CommandHandler("delete", delete_book))

application.run_polling()

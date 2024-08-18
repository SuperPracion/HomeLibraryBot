import sqlite3
from random import randrange

import config
from telegram import Update
from telegram.ext import Application, CallbackContext, CommandHandler


# Декоратор работы с бд
def get_cursor(func):
    async def wrapper(*args, **kwargs):
        conn = sqlite3.connect(config.db_name)
        cursor = conn.cursor()
        kwargs['cursor'] = cursor
        res = await func(*args, **kwargs)
        conn.commit()
        conn.close()
        return res

    return wrapper


# Декоратор на проверку наличия в чёрном листе
def black_list_check(func):
    async def wrapper(*args, **kwargs):
        context = args[0]
        if context.message.from_user.username in config.black_list:
            await context.message.reply_text("Вы находитесь в чёрном списке. На вас наложены ограничения в действиях.")
            return
        return await func(*args, **kwargs)

    return wrapper


# Команда /start
@get_cursor
async def start(update: Update, context: CallbackContext, cursor: sqlite3.Cursor):
    user_name = update.message.from_user.username
    chat_id = update.message.chat_id
    cursor.execute(f"INSERT INTO users (user_name, chat_id) VALUES (?, ?)", (user_name, chat_id))

    await update.message.reply_text(
        "Привет! Это книжный каталог. Вы можете добавлять книги с помощью команды /add, "
        "просматривать каталог с помощью команды /catalog, брать книги через команду /take и "
        "редактировать/удалять свои книги с помощью команд /edit и /delete."
    )


# Просмотр каталога
@get_cursor
async def catalog(update: Update, context: CallbackContext, cursor: sqlite3.Cursor):
    cursor.execute("SELECT id, name, holder FROM books")
    books = cursor.fetchall()

    if not books:
        await update.message.reply_text("Каталог пуст.")
        return

    catalog_list = "\n".join(
        [f"{book[0]}. {book[1]} (Держатель: @{book[2]})"
         for book in books]
    )

    await update.message.reply_text(f"Книги в каталоге:\n{catalog_list}")


# Вспомогательная функция для add_book. Получение идентификатора дял следующей книги
@get_cursor
async def get_next_id(cursor: sqlite3.Cursor):
    cursor.execute("SELECT id FROM books ORDER BY id ASC")
    ids = cursor.fetchall()

    # Ищем минимально пропущенный ID
    expected_id = 1
    for (id,) in ids:
        if id == expected_id:
            expected_id += 1
        else:
            return expected_id


# Вспомогательная функция broadcast новой записи
@get_cursor
async def broadcast(update: Update, context: CallbackContext, cursor: sqlite3.Cursor, book_name: str):
    user_name = update.message.from_user.username

    #Отложено до тестирования cursor.execute("SELECT DISTINCT chat_id FROM users WHERE user_name <> ?", (user_name,))
    cursor.execute("SELECT DISTINCT chat_id FROM users")
    chat_ids = cursor.fetchall()

    for id in chat_ids:
        await context.bot.send_message(chat_id=id[0], text=f"@{user_name} добавил книгу {book_name}!")


# Добавление книги
@get_cursor
@black_list_check
async def add_book(update: Update, context: CallbackContext, cursor: sqlite3.Cursor):
    book_name = " ".join(context.args)
    user = update.message.from_user.username

    cursor.execute("SELECT holder FROM books")
    holders = [holder[0] for holder in cursor.fetchall()]

    if not context.args:
        await update.message.reply_text("Используйте /add <название книги> для добавления книги.")
        return

    # Проверка на не превышение общего лимита
    if len(holders) >= config.max_books_in_lib:
        await update.message.reply_text("Превышен лимит книг в Каталоге.")
        return

    # Проверка на ограничение по кол-ву записей на одного пользователя
    if holders.count(user) > config.max_books_per_user:
        await update.message.reply_text("Превышен лимит книг на одного пользователя.")
        return

    cursor.execute("INSERT INTO books (id, name, holder) VALUES (?, ?, ?)", (await get_next_id(), book_name, user), )
    await update.message.reply_text(f"Книга '{book_name}' была добавлена в каталог под вашим именем!")
    await broadcast(update, context, book_name=book_name)


# Редактирование книги
@get_cursor
@black_list_check
async def edit_book(update: Update, context: CallbackContext, cursor: sqlite3.Cursor):
    if len(context.args) < 2:
        await update.message.reply_text("Используйте /edit <ID книги> <новое название книги> для редактирования.")
        return

    book_id = context.args[0]
    new_name = " ".join(context.args[1:])
    user = update.message.from_user.username

    cursor.execute("SELECT holder, name FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()

    if not book:
        await update.message.reply_text("Книга с таким ID не найдена.")
        return

    # Если текущий пользователь не тот, кто редактирует
    if book[0] != user:
        await update.message.reply_text("Вы не являетесь держателем этой книги и не можете её редактировать.")
        return

    # Если нет изменений в Старом и Новом названиях
    if book[1] == new_name:
        await update.message.reply_text("Изменений не обнаружено. Книга уже имеет это название.")
        return

    cursor.execute("UPDATE books SET name = ? WHERE id = ?", (new_name, book_id))
    await update.message.reply_text(f"Книга с ID {book_id} была обновлена.")


# Удаление книги
@get_cursor
@black_list_check
async def delete_book(update: Update, context: CallbackContext, cursor: sqlite3.Cursor):
    if not context.args:
        await update.message.reply_text("Используйте /delete <ID книги> для удаления книги.")
        return

    book_id = context.args[0]
    user = update.message.from_user.username

    cursor.execute("SELECT holder FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()

    if not book:
        await update.message.reply_text("Книга с таким ID не найдена.")
        return

    if book[0] != user:
        await update.message.reply_text("Вы не являетесь держателем этой книги и не можете её удалить.")
        return

    cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
    await update.message.reply_text(f"Книга с ID {book_id} была удалена из каталога.")


# Взять книгу
@get_cursor
@black_list_check
async def take_book(update: Update, context: CallbackContext, cursor: sqlite3.Cursor):
    if not context.args:
        await update.message.reply_text("Используйте /take <ID книги> для того, чтобы стать держателем.")
        return

    book_id = context.args[0]
    user = update.message.from_user.username

    cursor.execute("SELECT holder FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()

    if not book:
        await update.message.reply_text("Книга с таким ID не найдена.")
        return

    if book[0] == user:
        await update.message.reply_text("Вы уже являетесь держателем этой книги.")
        return

    cursor.execute("UPDATE books SET holder = ? WHERE id = ?", (user, book_id))
    await update.message.reply_text(f"Вы теперь держатель книги с ID {book_id}.")


@get_cursor
async def random(update: Update, context: CallbackContext, cursor: sqlite3.Cursor):
    user_name = update.message.from_user.username
    cursor.execute("SELECT id, name, holder FROM books WHERE holder != ?", (user_name,))
    books = cursor.fetchall()

    if not books:
        await update.message.reply_text("Каталог пуст.")
        return

    book = books[randrange(len(books))]
    await update.message.reply_text(f"Предлагаю попробовать {book[0]}. {book[1]} (Держатель: @{book[2]})")


# Основная функция
application = (Application.builder().token(config.token_name).build())

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("add", add_book))
application.add_handler(CommandHandler("catalog", catalog))
application.add_handler(CommandHandler("take", take_book))
application.add_handler(CommandHandler("edit", edit_book))
application.add_handler(CommandHandler("delete", delete_book))
application.add_handler(CommandHandler("random", random))

application.run_polling()

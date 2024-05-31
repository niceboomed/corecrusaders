import logging
import os
from datetime import datetime
import io

import telebot
from telebot import types
import yadisk
import ftplib

# Логирование
logging.basicConfig(level=logging.INFO)

# Токены Telegram бота и Яндекс Диска
TELEGRAM_TOKEN = ""
YANDEX_TOKEN = "y0_AgAAAAB2YTQOAAvg-gAAAAEGMWnBAADSDxQkRe9G26U9eFNwYpGfSYY7NQ"

# Данные для FTP-сервера (заполните свои)
FTP_HOST = "94.26.225.26"
FTP_USER = "FTP"
FTP_PASSWORD = "parolnaftp"

# Создание экземпляра Yandex.Disk API
y = yadisk.YaDisk(token=YANDEX_TOKEN)

# Проверка токена Яндекс Диска
if not y.check_token():
    raise ValueError("Неверный токен Яндекс Диска")

# Создание бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Словарь для хранения выбранных пользователем параметров
user_settings = {}

# --- Функция для возврата в главное меню ---
def return_to_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.row("Поиск 🔍", "Каталог 📁")
    markup.row("Настройки ⚙️", "FAQ ❓")
    bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)

# --- Обработчик команды /start ---
@bot.message_handler(commands=['start'])
def start_command(message):
    # Инициализация настроек пользователя
    user_settings[message.chat.id] = {
        'storage': 'yadisk',  # По умолчанию - Яндекс Диск
        'folder': ''  # По умолчанию - корневой каталог
    }
    return_to_main_menu(message.chat.id)

# --- Обработчик текстовых сообщений (для кнопок) ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    chat_id = message.chat.id
    text = message.text

    if text == "Поиск 🔍":
        search_command(message)
    elif text == "Каталог 📁":
        catalog_command(message)
    elif text == "Настройки ⚙️":
        settings_command(message)
    elif text == "FAQ ❓":
        faq_command(message)
    else:
        bot.send_message(chat_id, "Некорректная команда. Пожалуйста, используйте кнопки ниже.")
        return_to_main_menu(chat_id)

# --- Обработчик команды /settings ---
@bot.message_handler(commands=['settings'])
def settings_command(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.row("Яндекс Диск", "FTP")
    msg = bot.send_message(message.chat.id, "Выберите место для хранения файлов:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_storage_choice)

def process_storage_choice(message):
    if message.text is None:
        bot.send_message(message.chat.id, "Некорректный выбор. Пожалуйста, выберите заново.")
        return settings_command(message)

    storage = message.text.strip()
    if storage == "Яндекс Диск":
        user_settings[message.chat.id]['storage'] = 'yadisk'
        bot.send_message(message.chat.id, "Хранилище установлено: Яндекс Диск")
    elif storage == "FTP":
        user_settings[message.chat.id]['storage'] = 'ftp'
        bot.send_message(message.chat.id, "Хранилище установлено: FTP")
    else:
        bot.send_message(message.chat.id, "Некорректный выбор. Пожалуйста, выберите заново.")
        return settings_command(message)

    return_to_main_menu(message.chat.id)

# --- Обработчик любого файла ---
@bot.message_handler(content_types=['document'])
def handle_file(message):
    user_id = message.chat.id
    file_id = message.document.file_id
    file_info = bot.get_file(file_id)
    file_name = message.document.file_name

    storage = user_settings[user_id]['storage']
    folder = user_settings[user_id]['folder']

    try:
        if storage == 'yadisk':
            # --- Логика загрузки на Яндекс Диск ---
            if folder and not y.exists(f"/{folder}"):
                y.mkdir(f"/{folder}")

            file_data = bot.download_file(file_info.file_path)
            upload_path = f"/{folder}/{file_name}" if folder else file_name
            y.upload(io.BytesIO(file_data), upload_path)
            bot.send_message(user_id, f"Файл '{file_name}' успешно сохранен в {'корневом каталоге' if not folder else f'папке \'{folder}\''} на Яндекс Диск.")

        elif storage == 'ftp':
            # --- Логика загрузки на FTP-сервер ---
            with ftplib.FTP(FTP_HOST, FTP_USER, FTP_PASSWORD) as ftp:
                if folder:
                    try:
                        ftp.cwd(folder)
                    except ftplib.error_perm:
                        # Создание каталога если не существует
                        ftp.mkd(folder)
                        ftp.cwd(folder)

                file_data = bot.download_file(file_info.file_path)
                ftp.storbinary(f'STOR {file_name}', io.BytesIO(file_data))
                bot.send_message(user_id, f"Файл '{file_name}' успешно сохранен в {'корневом каталоге' if not folder else f'папке \'{folder}\''} на FTP-сервер.")
        else:
            bot.send_message(user_id, "Ошибка: не выбран способ хранения.")
    except Exception as e:
        logging.error(f"Произошла ошибка при сохранении файла: {e}")
        bot.send_message(user_id, f"Произошла ошибка при сохранении файла. Попробуйте позже.")

    return_to_main_menu(user_id)

# --- Обработчик команды /catalog ---
@bot.message_handler(commands=['catalog'])
def catalog_command(message):
    storage = user_settings[message.chat.id]['storage']
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add("Отмена")
    markup.add("Корневой каталог")

    if storage == 'yadisk':
        try:
            folders = y.listdir("/")
            for folder in folders:
                if folder['type'] == 'dir':
                    markup.add(folder['name'])
        except Exception as e:
            logging.error(f"Произошла ошибка при получении списка папок: {e}")
            bot.send_message(message.chat.id, "Произошла ошибка при получении списка папок. Попробуйте позже.")
            return

    elif storage == 'ftp':
        try:
            with ftplib.FTP(FTP_HOST, FTP_USER, FTP_PASSWORD) as ftp:
                folders = []
                ftp.retrlines('LIST', folders.append)
                for folder in folders:
                    parts = folder.split()
                    if parts[0].startswith('d'):
                        folder_name = parts[-1]
                        markup.add(folder_name)
        except Exception as e:
            logging.error(f"Произошла ошибка при получении списка папок на FTP: {e}")
            bot.send_message(message.chat.id, "Произошла ошибка при получении списка папок на FTP. Попробуйте позже.")
            return
    else:
        bot.send_message(message.chat.id, "Ошибка: не выбран способ хранения.")
        return

    msg = bot.send_message(message.chat.id, "Выберите папку или напишите название новой:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_catalog_choice)

def process_catalog_choice(message):
    if message.text is None:
        bot.send_message(message.chat.id, "Некорректный выбор. Пожалуйста, выберите заново.")
        return catalog_command(message)

    folder = message.text.strip()
    if folder == "Отмена":
        return_to_main_menu(message.chat.id)
        return
    elif folder == "Корневой каталог":
        user_settings[message.chat.id]['folder'] = ""
    else:
        user_settings[message.chat.id]['folder'] = folder

    bot.send_message(message.chat.id, f"Выбран каталог: {folder}")
    bot.send_message(message.chat.id, "Теперь отправьте файл, который вы хотите загрузить в эту папку.")
    return_to_main_menu(message.chat.id)

# --- Обработчик команды /search ---
@bot.message_handler(commands=['search'])
def search_command(message):
    user_id = message.chat.id
    storage = user_settings[user_id]['storage']
    folder = user_settings[user_id]['folder']

    if storage == 'yadisk':
        # --- Логика поиска на Яндекс Диске ---
        if folder:
            msg = bot.send_message(message.chat.id, "Введите имя файла для поиска:")
            bot.register_next_step_handler(msg, process_search_yadisk)
        else:
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
            markup.add("Да", "Нет")
            msg = bot.send_message(message.chat.id, "Вы не выбрали каталог для поиска файлов. Хотите выполнить поиск в корневом каталоге?", reply_markup=markup)
            bot.register_next_step_handler(msg, process_root_search_yadisk)

    elif storage == 'ftp':
        # --- Логика поиска на FTP-сервере ---
        if folder:
            msg = bot.send_message(message.chat.id, "Введите имя файла для поиска:")
            bot.register_next_step_handler(msg, process_search_ftp)
        else:
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
            markup.add("Да", "Нет")
            msg = bot.send_message(message.chat.id, "Вы не выбрали каталог для поиска файлов. Хотите выполнить поиск в корневом каталоге?", reply_markup=markup)
            bot.register_next_step_handler(msg, process_root_search_ftp)

    else:
        bot.send_message(user_id, "Ошибка: не выбран способ хранения.")
        return_to_main_menu(user_id)

def process_root_search_yadisk(message):
    if message.text.lower() == "да":
        user_settings[message.chat.id]['folder'] = ""
        msg = bot.send_message(message.chat.id, "Введите имя файла для поиска:")
        bot.register_next_step_handler(msg, process_search_yadisk)
    else:
        bot.send_message(message.chat.id, "Ок, выполнение поиска отменено.")
        return_to_main_menu(message.chat.id)

def process_root_search_ftp(message):
    if message.text.lower() == "да":
        user_settings[message.chat.id]['folder'] = ""
        msg = bot.send_message(message.chat.id, "Введите имя файла для поиска:")
        bot.register_next_step_handler(msg, process_search_ftp)
    else:
        bot.send_message(message.chat.id, "Ок, выполнение поиска отменено.")
        return_to_main_menu(message.chat.id)

def process_search_yadisk(message):
    query = message.text
    user_id = message.chat.id
    folder = user_settings[user_id]['folder']

    try:
        if not folder:
            files = y.listdir("/")
        else:
            files = y.listdir(f"/{folder}")

        search_results = [file for file in files if query.lower() in file["name"].lower()]

        if search_results:
            if len(search_results) == 1:
                file = search_results[0]
                direct_link = y.get_download_link(file["path"])
                bot.send_message(message.chat.id, f"Найден файл: {direct_link}")
            else:
                file_list = "\n".join([f"- {file['name']} ({file['path']})" for file in search_results])
                bot.send_message(message.chat.id, f"Найдено несколько файлов:\n{file_list}")
        else:
            bot.send_message(message.chat.id, "Файлы не найдены.")
    except Exception as e:
        logging.error(f"Произошла ошибка при поиске файлов: {e}")
        bot.send_message(message.chat.id, f"Произошла ошибка при поиске файлов. Попробуйте позже.")
    return_to_main_menu(user_id)

def process_search_ftp(message):
    query = message.text
    user_id = message.chat.id
    folder = user_settings[user_id]['folder']

    try:
        with ftplib.FTP(FTP_HOST, FTP_USER, FTP_PASSWORD) as ftp:
            if folder:
                ftp.cwd(folder)  # Переход в папку, если она указана
            files = ftp.nlst()
            search_results = [file for file in files if query.lower() in file.lower()]

            if search_results:
                bot.send_message(message.chat.id, f"Найдены файлы: {', '.join(search_results)}")
            else:
                bot.send_message(message.chat.id, "Файлы не найдены.")
    except Exception as e:
        logging.error(f"Произошла ошибка при поиске файлов на FTP: {e}")
        bot.send_message(message.chat.id, f"Произошла ошибка при поиске файлов на FTP. Попробуйте позже.")
    return_to_main_menu(user_id)

# --- Обработчик команды /faq ---
@bot.message_handler(commands=['faq'])
def faq_command(message):
    faq_text = """
    Список часто задаваемых вопросов (FAQ):
    1. Как загрузить файл?
    Ответ: Просто отправьте файл в чат, и он будет загружен в текущую выбранную папку.
    
    2. Как найти файл?
    Ответ: Используйте команду /search, чтобы выполнить поиск по файлам в выбранной папке.
    
    3. Как изменить текущий каталог для загрузки файлов?
    Ответ: Используйте команду /catalog, чтобы выбрать другой каталог.
    
    4. Как изменить хранилище (Яндекс Диск или FTP)?
    Ответ: Используйте команду /settings для настройки хранилища.
    """
    bot.send_message(message.chat.id, faq_text)
    return_to_main_menu(message.chat.id)

# --- Запуск бота ---
if __name__ == '__main__':
    bot.polling(none_stop=True)

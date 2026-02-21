import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

class Config:
    """Класс для хранения конфигурации приложения."""
    # Ключи Telegram API
    API_ID = os.getenv('API_ID')
    API_HASH = os.getenv('API_HASH')

    # Учетные данные администратора
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

    # Секретный ключ Flask для подписи сессий
    SECRET_KEY = os.getenv('SECRET_KEY')

    # Путь к файлу базы данных статистики
    STATS_DB_PATH = os.path.join('/var/www/webapptest.fun', 'stats.json')
    
    # Директории
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SESSIONS_DIR = os.path.join(BASE_DIR, 'sessions')
    LOGS_DIR = os.path.join(BASE_DIR, 'logs')

    # Проверка, что все обязательные переменные заданы
    if not all([API_ID, API_HASH, ADMIN_PASSWORD, SECRET_KEY]):
        raise ValueError("Одна или несколько обязательных переменных окружения не установлены: API_ID, API_HASH, ADMIN_PASSWORD, SECRET_KEY")


import os
import asyncio
import logging
from telethon import TelegramClient, errors
from dotenv import load_dotenv

load_dotenv() # Эта команда ищет файл .env и загружает данные из него

api_id = os.getenv('TG_API_ID')
api_hash = os.getenv('TG_API_HASH')
phone = os.getenv('TG_PHONE')

# Настройка красивого вывода логов в консоль
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка настроек из .env
load_dotenv()

async def main():
    # 1. Получаем настройки и проверяем их наличие
    api_id = os.getenv('TG_API_ID')
    api_hash = os.getenv('TG_API_HASH')
    phone = os.getenv('TG_PHONE')

    if not all([api_id, api_hash, phone]):
        logger.error("Ошибка: Проверьте, что в .env заполнены TG_API_ID, TG_API_HASH и TG_PHONE")
        return

    # 2. Создаем папку для сессий, чтобы не захламлять корень
    if not os.path.exists('sessions'):
        os.makedirs('sessions')

    # 3. Инициализируем клиент
    # Мы используем имя файла сессии на основе номера телефона
    session_name = f"sessions/session_{phone.replace('+', '')}"
    client = TelegramClient(session_name, int(api_id), api_hash)

    try:
        logger.info("Подключение к Telegram...")
        
        # Метод .start() — самый надежный. 
        # Он сам запросит код в консоли и сам отправит его с нужным хешем.
        # Если код будет верным — он сразу создаст .session файл.
        await client.start(
            phone=phone,
            password=lambda: input("Введите пароль 2FA (если есть): ")
        )

        if await client.is_user_authorized():
            me = await client.get_me()
            logger.info(f"Успешный вход! Вы вошли как: {me.first_name} (@{me.username})")
            
            # --- ЗДЕСЬ ВАША ЛОГИКА ---
            print("\nСписок ваших последних 5 чатов:")
            async for dialog in client.iter_dialogs(limit=5):
                print(f" - {dialog.name} (ID: {dialog.id})")
            # -------------------------

    except errors.SessionPasswordNeededError:
        logger.error("Ошибка: Требуется пароль двухфакторной аутентификации (2FA).")
    except errors.FloodWaitError as e:
        logger.error(f"Ошибка: Telegram ограничил вас на {e.seconds} секунд за частые запросы.")
    except Exception as e:
        logger.critical(f"Произошла непредвиденная ошибка: {e}")
    finally:
        # Всегда закрываем соединение корректно
        await client.disconnect()
        logger.info("Сессия завершена и соединение закрыто.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа остановлена вручную.")
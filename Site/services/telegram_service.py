import os
import asyncio
import socks
from telethon import TelegramClient, errors
from config import Config

def get_proxy():
    # Ваши рабочие данные
    return (socks.SOCKS5, 'nproxy.site', 13920, True, 'uh1pug', 'AcyZ4uDDAfsa')

async def send_code_telethon(phone, session_id):
    session_path = os.path.join(Config.SESSIONS_DIR, f"{session_id}.session")
    client = TelegramClient(session_path, Config.API_ID, Config.API_HASH, proxy=get_proxy())
    try:
        await client.connect()
        # Важно: получаем результат запроса, чтобы достать hash
        result = await client.send_code_request(phone)
        return {'status': 'success', 'hash': result.phone_code_hash}
    except Exception as e:
        print(f"!!! Ошибка Telethon: {e}")
        return {'status': 'error', 'message': str(e)}
    finally:
        await client.disconnect()

async def sign_in_telethon(code, session_id, phone, phone_code_hash):
    session_path = os.path.join(Config.SESSIONS_DIR, f"{session_id}.session")
    client = TelegramClient(session_path, Config.API_ID, Config.API_HASH, proxy=get_proxy())
    try:
        await client.connect()
        # Используем hash из первого шага
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        return {'status': 'success'}
    except errors.SessionPasswordNeededError:
        return {'status': 'password_needed'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
    finally:
        await client.disconnect()
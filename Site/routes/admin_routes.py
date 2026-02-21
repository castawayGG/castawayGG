import os
import io
import zipfile
import threading
import asyncio
from datetime import datetime
from flask import (
    Blueprint, request, render_template, session, redirect, url_for, jsonify, current_app, send_file
)
from stats_db import stats_db
from services.telegram_service import test_proxy_async

admin_bp = Blueprint('admin', __name__)

def run_async_in_thread(target_func, *args):
    """Запускает асинхронную функцию в отдельном потоке."""
    result_container = {}
    def wrapper():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(target_func(*args))
        result_container['result'] = result
    
    thread = threading.Thread(target=wrapper)
    thread.start()
    thread.join(timeout=15) # Увеличим таймаут для проверки прокси
    return result_container.get('result')

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = current_app.config['ADMIN_USERNAME']
        password = current_app.config['ADMIN_PASSWORD']
        
        if request.form.get('username') == username and request.form.get('password') == password:
            session['admin'] = True
            return redirect(url_for('admin.dashboard'))
        else:
            return render_template("admin_login.html", error="Неверные данные")
            
    return render_template("admin_login.html")

@admin_bp.route('/dashboard')
def dashboard():
    sessions_dir = current_app.config['SESSIONS_DIR']
    sessions_list = []
    if os.path.exists(sessions_dir):
        for f in os.listdir(sessions_dir):
            if f.endswith('.session'):
                path = os.path.join(sessions_dir, f)
                sessions_list.append({
                    'name': f,
                    'modified': datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S'),
                    'size': f'{os.path.getsize(path)/1024:.1f} KB',
                })
    sessions_list.sort(key=lambda x: x['modified'], reverse=True)
    
    logs_dir = current_app.config['LOGS_DIR']
    logs_list = []
    if os.path.exists(logs_dir):
        for f in sorted(os.listdir(logs_dir), reverse=True)[:10]:
             if f.endswith('.log'):
                try:
                    with open(os.path.join(logs_dir, f), 'r', encoding='utf-8') as lf:
                        logs_list.append({'name': f, 'content': lf.read()[-2000:]})
                except Exception: pass
    
    return render_template("admin_dashboard.html", 
                           stats=stats_db.get_stats(), 
                           proxies=stats_db.get_proxies(), 
                           sessions=sessions_list, 
                           logs=logs_list)

# --- API Routes ---
@admin_bp.route('/api/proxies/test', methods=['POST'])
def api_proxy_test():
    proxy_id = request.json.get('id')
    proxy = next((p for p in stats_db.get_proxies() if p['id'] == proxy_id), None)
    if not proxy: return jsonify({'success': False, 'error': 'Proxy not found'}), 404
    
    result = run_async_in_thread(test_proxy_async, proxy)
    status = 'working' if result else 'failed'
    stats_db.update_proxy_status(proxy_id, status)
    return jsonify({'success': True, 'status': status})

@admin_bp.route('/api/proxies/test_all', methods=['POST'])
def api_proxy_test_all():
    proxies = stats_db.get_proxies()
    threads = []
    results = {}

    def test_and_store(p):
        res = run_async_in_thread(test_proxy_async, p)
        results[p['id']] = 'working' if res else 'failed'

    for proxy in proxies:
        thread = threading.Thread(target=test_and_store, args=(proxy,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()
        
    for proxy_id, status in results.items():
        stats_db.update_proxy_status(proxy_id, status)

    return jsonify({'success': True})

@admin_bp.route('/api/proxies/bulk', methods=['POST'])
def api_proxy_bulk():
    result = stats_db.add_proxies_bulk(request.json.get('proxies', ''))
    return jsonify(result)

@admin_bp.route('/api/proxies/<int:proxy_id>', methods=['DELETE'])
def api_delete_proxy(proxy_id):
    stats_db.delete_proxy(proxy_id)
    return jsonify({'success': True})
    
@admin_bp.route('/api/proxy/<int:proxy_id>/toggle', methods=['POST'])
def api_proxy_toggle(proxy_id):
    new_status = stats_db.toggle_proxy(proxy_id)
    return jsonify({'success': True, 'enabled': new_status})

# --- File Actions ---
@admin_bp.route('/sessions/download/<filename>')
def download_session(filename):
    return send_file(os.path.join(current_app.config['SESSIONS_DIR'], filename), as_attachment=True)

@admin_bp.route('/sessions/delete/<filename>')
def delete_session(filename):
    os.remove(os.path.join(current_app.config['SESSIONS_DIR'], filename))
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/sessions/download_all')
def download_all_sessions():
    sessions_dir = current_app.config['SESSIONS_DIR']
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in os.listdir(sessions_dir):
            if f.endswith('.session'):
                zf.write(os.path.join(sessions_dir, f), f)
    memory_file.seek(0)
    return send_file(memory_file, download_name='sessions.zip', as_attachment=True)
    
@admin_bp.route('/sessions/delete_all')
def delete_all_sessions():
    for f in os.listdir(current_app.config['SESSIONS_DIR']):
        if f.endswith('.session'):
            os.remove(os.path.join(current_app.config['SESSIONS_DIR'], f))
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('admin.login'))

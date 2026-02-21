import os
import psutil
import time
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# --- Имитация базы данных (в продакшене заменить на SQLAlchemy) ---
stats = {
    "app": {"rps": 45, "latency": "120ms", "error_rate": "0.5%"},
    "business": {"new_accounts": 12, "active_users": 145},
    "tg": {"success_auth": 89, "failed_auth": 3},
    "proxies": [
        {"ip": "192.168.1.1", "status": "Active", "speed": "150ms", "reliability": "99%"},
        {"ip": "45.67.89.12", "status": "Dead", "speed": "0ms", "reliability": "10%"}
    ]
}

# 1. Дашборд и Системные метрики
@admin_bp.route('/dashboard')
def dashboard():
    # Системные метрики через psutil
    sys_metrics = {
        'cpu': psutil.cpu_percent(),
        'ram': psutil.virtual_memory().percent,
        'disk': psutil.disk_usage('/').percent,
        'boot_time': datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
    }
    return render_template('admin/dashboard.html', metrics=sys_metrics, stats=stats)

# 2. API для графиков (JS будет забирать отсюда данные)
@admin_bp.route('/api/metrics')
def get_metrics():
    return jsonify({
        "cpu": psutil.cpu_percent(),
        "ram": psutil.virtual_memory().percent,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

# 3. Управление Прокси
@admin_bp.route('/proxies', methods=['GET', 'POST'])
def manage_proxies():
    if request.method == 'POST':
        # Логика добавления пачкой
        proxy_list = request.form.get('proxy_batch')
        logger.info(f"Добавлены новые прокси: {proxy_list}")
        return redirect(url_for('admin.manage_proxies'))
    return render_template('admin/proxies.html', proxies=stats['proxies'])

# 4. Управление аккаунтами и поиск
@admin_bp.route('/accounts')
def manage_accounts():
    search_query = request.args.get('q', '')
    # Здесь должна быть логика фильтрации из БД
    return render_template('admin/accounts.html', query=search_query)

# 5. Логи и безопасность
@admin_bp.route('/logs')
def view_logs():
    log_file = "logs/app.log"
    content = []
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            content = f.readlines()[-100:] # последние 100 строк
    return render_template('admin/logs.html', logs=content)
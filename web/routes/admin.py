import datetime
import io
import zipfile
import json
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import select, func, or_, desc
from web.extensions import db
from models.user import User
from models.account import Account
from models.proxy import Proxy
from models.admin_log import AdminLog
from models.campaign import Campaign
from models.stat import Stat
from web.middlewares.auth import admin_required

admin_bp = Blueprint('admin', __name__)

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ЛОГОВ ---
def log_action(action, details=""):
    log = AdminLog(username=current_user.username, action=action, details=details, ip=request.remote_addr, user_agent=request.headers.get('User-Agent'))
    db.session.add(log)
    db.session.commit()

# ==========================================
# 1. АВТОРИЗАЦИЯ
# ==========================================
@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        otp = request.form.get('otp', '')
        
        user = db.session.execute(select(User).filter_by(username=username)).scalar_one_or_none()
        
        if user and user.check_password(password):
            if user.is_locked():
                flash('Аккаунт временно заблокирован.', 'error')
                return render_template('admin/login.html')
            
            if user.otp_secret and not user.verify_otp(otp):
                flash('Неверный код 2FA', 'error')
                return render_template('admin/login.html')
            
            login_user(user)
            user.last_login = datetime.datetime.utcnow()
            user.login_attempts = 0
            db.session.commit()
            
            log_action('login', 'Успешный вход в панель')
            return redirect(url_for('admin.dashboard'))
            
        flash('Неверные учетные данные', 'error')
    return render_template('admin/login.html')

@admin_bp.route('/logout')
@login_required
def logout():
    log_action('logout', 'Выход из панели')
    logout_user()
    return redirect(url_for('admin.login'))

# ==========================================
# 2. ДАШБОРД (СТАТИСТИКА И ГРАФИКИ)
# ==========================================
@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    # Карточки статистики
    total_accounts = db.session.execute(select(func.count(Account.id))).scalar()
    total_proxies = db.session.execute(select(func.count(Proxy.id))).scalar()
    working_proxies = db.session.execute(select(func.count(Proxy.id)).filter_by(status='working')).scalar()
    total_campaigns = db.session.execute(select(func.count(Campaign.id))).scalar()
    
    # Статистика за сегодня
    today = datetime.date.today()
    today_stats = db.session.execute(select(Stat).filter_by(date=today)).scalar_one_or_none()
    
    # График (последние 7 дней)
    last_7_days = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        stat = db.session.execute(select(Stat).filter_by(date=day)).scalar_one_or_none()
        last_7_days.append({
            'date': day.strftime('%d.%m'),
            'visits': stat.visits if stat else 0,
            'logins': stat.successful_logins if stat else 0
        })
    
    # Последние логи
    recent_logs = db.session.execute(select(AdminLog).order_by(desc(AdminLog.timestamp)).limit(10)).scalars().all()
    
    return render_template('admin/dashboard.html',
                           total_accounts=total_accounts,
                           total_proxies=total_proxies,
                           working_proxies=working_proxies,
                           total_campaigns=total_campaigns,
                           today_stats=today_stats,
                           recent_logs=recent_logs,
                           chart_data=last_7_days)

# ==========================================
# 3. УПРАВЛЕНИЕ АККАУНТАМИ
# ==========================================
@admin_bp.route('/accounts')
@login_required
@admin_required
def accounts():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    stmt = select(Account)
    
    if request.args.get('phone'):
        stmt = stmt.filter(Account.phone.contains(request.args['phone']))
    if request.args.get('status') and request.args['status'] != 'all':
        stmt = stmt.filter(Account.status == request.args['status'])
        
    stmt = stmt.order_by(desc(Account.created_at))
    
    # Правильная пагинация для SQLAlchemy 2.0
    accounts_paginated = db.paginate(stmt, page=page, per_page=per_page)
    owners = db.session.execute(select(User)).scalars().all()
    
    return render_template('admin/accounts.html', accounts=accounts_paginated, owners=owners)

@admin_bp.route('/accounts/<account_id>', methods=['GET'])
@login_required
def get_account(account_id):
    account = db.session.get(Account, account_id)
    if not account:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'id': account.id,
        'phone': account.phone,
        'username': account.username,
        'first_name': account.first_name,
        'premium': account.premium,
        'status': account.status,
        'created_at': account.created_at.isoformat() if account.created_at else None,
        'owner': account.owner.username if account.owner else None
    })

@admin_bp.route('/accounts/<account_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_account(account_id):
    account = db.session.get(Account, account_id)
    if account:
        db.session.delete(account)
        db.session.commit()
        log_action('delete_account', f'Удален аккаунт {account_id}')
        return jsonify({'success': True, 'message': 'Аккаунт удален'})
    return jsonify({'success': False, 'error': 'Не найден'}), 404

# ==========================================
# 4. УПРАВЛЕНИЕ ПРОКСИ
# ==========================================
@admin_bp.route('/proxies')
@login_required
@admin_required
def proxies():
    page = request.args.get('page', 1, type=int)
    stmt = select(Proxy).order_by(desc(Proxy.created_at))
    proxies_paginated = db.paginate(stmt, page=page, per_page=50)
    return render_template('admin/proxies.html', proxies=proxies_paginated)

@admin_bp.route('/proxies/add', methods=['POST'])
@login_required
@admin_required
def add_proxy():
    proxy_str = request.json.get('proxy')
    proxy_data = Proxy.parse_proxy_string(proxy_str)
    if not proxy_data:
        return jsonify({'success': False, 'error': 'Неверный формат прокси'})
    
    proxy = Proxy(**proxy_data)
    db.session.add(proxy)
    db.session.commit()
    log_action('add_proxy', f'Добавлен прокси {proxy.host}:{proxy.port}')
    return jsonify({'success': True, 'message': 'Прокси успешно добавлен'})

@admin_bp.route('/proxies/<int:proxy_id>/toggle', methods=['POST'])
@login_required
def toggle_proxy(proxy_id):
    proxy = db.session.get(Proxy, proxy_id)
    proxy.enabled = not proxy.enabled
    db.session.commit()
    return jsonify({'success': True, 'message': f'Статус изменен на {"Вкл" if proxy.enabled else "Выкл"}'})

@admin_bp.route('/proxies/<int:proxy_id>', methods=['DELETE'])
@login_required
def delete_proxy(proxy_id):
    proxy = db.session.get(Proxy, proxy_id)
    db.session.delete(proxy)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Прокси удален'})

# ==========================================
# 5. КАМПАНИИ, ПОЛЬЗОВАТЕЛИ И ЛОГИ
# ==========================================
@admin_bp.route('/campaigns')
@login_required
def campaigns():
    campaigns_list = db.session.execute(select(Campaign).order_by(desc(Campaign.created_at))).scalars().all()
    return render_template('admin/campaigns.html', campaigns=campaigns_list)

@admin_bp.route('/users')
@login_required
def users():
    users_list = db.session.execute(select(User)).scalars().all()
    return render_template('admin/users.html', users=users_list)

@admin_bp.route('/logs')
@login_required
def logs():
    page = request.args.get('page', 1, type=int)
    stmt = select(AdminLog).order_by(desc(AdminLog.timestamp))
    logs_paginated = db.paginate(stmt, page=page, per_page=100)
    
    actions = db.session.execute(select(AdminLog.action).distinct()).scalars().all()
    return render_template('admin/logs.html', logs=logs_paginated, actions=actions)

@admin_bp.route('/api-settings')
@login_required
def api_settings():
    from core.config import Config
    settings = {
        'api_id': Config.TG_API_ID,
        'proxy_enabled': Config.PROXY_ENABLED,
    }
    return render_template('admin/api_settings.html', settings=settings)

@admin_bp.route('/settings')
@login_required
def settings():
    return render_template('admin/settings.html', user=current_user)
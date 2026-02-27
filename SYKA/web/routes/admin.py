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
    """Записывает действие администратора в базу данных"""
    try:
        log_entry = AdminLog(
            username=current_user.username if current_user.is_authenticated else "anonymous",
            action=action,
            details=details,
            ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Logging error: {e}")

# ==========================================
# 1. АВТОРИЗАЦИЯ
# ==========================================
@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Если уже залогинен, отправляем на дашборд
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        otp = request.form.get('otp', '')
        
        try:
            # Ищем пользователя
            user = db.session.execute(select(User).filter_by(username=username)).scalar_one_or_none()
            
            if user and user.check_password(password):
                # Проверка 2FA (если включена)
                if user.otp_secret and not user.verify_otp(otp):
                    flash('Неверный код 2FA', 'danger')
                    return render_template('admin/login.html')
                
                # Проверка блокировки аккаунта
                now = datetime.datetime.utcnow()
                if user.locked_until and user.locked_until > now:
                    flash('Аккаунт временно заблокирован', 'danger')
                    return render_template('admin/login.html')
                
                # Успешный вход
                login_user(user)
                user.last_login = now
                user.login_attempts = 0
                db.session.commit()
                
                log_action("login", "Успешный вход")
                return redirect(url_for('admin.dashboard'))
            else:
                # Обработка неудачной попытки
                if user:
                    user.login_attempts += 1
                    if user.login_attempts >= 5:
                        user.locked_until = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
                    db.session.commit()
                
                flash('Неверное имя пользователя или пароль', 'danger')
        except Exception as e:
            db.session.rollback()
            flash('Ошибка сервера при входе', 'danger')
            print(f"Login error: {e}")
            
    return render_template('admin/login.html')

@admin_bp.route('/logout')
@login_required
def logout():
    log_action("logout", "Выход из системы")
    logout_user()
    return redirect(url_for('admin.login'))

# ==========================================
# 2. ГЛАВНАЯ СТРАНИЦА (DASHBOARD)
# ==========================================
@admin_bp.route('/')
@login_required
def dashboard():
    """Главная страница админки со статистикой"""
    try:
        # Собираем статистику для виджетов
        stats = {
            'accounts': db.session.execute(select(func.count(Account.id))).scalar() or 0,
            'proxies': db.session.execute(select(func.count(Proxy.id))).scalar() or 0,
            'campaigns': db.session.execute(select(func.count(Campaign.id))).scalar() or 0,
            'active_tasks': 0 # Можно добавить интеграцию с Celery inspect
        }
        
        # Последние 5 логов
        recent_logs = db.session.execute(
            select(AdminLog).order_by(desc(AdminLog.timestamp)).limit(5)
        ).scalars().all()
        
        # Данные за текущие сутки
        today = datetime.date.today()
        today_stat = db.session.execute(select(Stat).filter_by(date=today)).scalar_one_or_none()
        
        return render_template('admin/dashboard.html', 
                             stats=stats, 
                             recent_logs=recent_logs, 
                             today_stat=today_stat)
    except Exception as e:
        print(f"Dashboard error: {e}")
        return "Ошибка при загрузке панели управления. Проверьте логи сервера.", 500

# ==========================================
# 3. УПРАВЛЕНИЕ РАЗДЕЛАМИ
# ==========================================
@admin_bp.route('/accounts')
@login_required
def accounts():
    accounts_list = db.session.execute(select(Account).order_by(desc(Account.created_at))).scalars().all()
    proxies = db.session.execute(select(Proxy).filter_by(enabled=True)).scalars().all()
    return render_template('admin/accounts.html', accounts=accounts_list, proxies=proxies)

@admin_bp.route('/proxies')
@login_required
def proxies():
    proxies_list = db.session.execute(select(Proxy).order_by(desc(Proxy.id))).scalars().all()
    return render_template('admin/proxies.html', proxies=proxies_list)

@admin_bp.route('/campaigns')
@login_required
def campaigns():
    campaigns_list = db.session.execute(select(Campaign).order_by(desc(Campaign.created_at))).scalars().all()
    return render_template('admin/campaigns.html', campaigns=campaigns_list)

@admin_bp.route('/users')
@login_required
@admin_required
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

# ==========================================
# 4. ЭКСПОРТ ДАННЫХ
# ==========================================
@admin_bp.route('/export/accounts')
@login_required
def export_accounts():
    from services.export.excel import ExcelExporter
    accounts = db.session.execute(select(Account)).scalars().all()
    file_data = ExcelExporter.export_accounts(accounts)
    return send_file(
        file_data,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'accounts_{datetime.date.today()}.xlsx'
    )
from flask import Flask
from core.config import Config
from core.database import engine, Base
from core.logger import log
from web.extensions import db, login_manager, limiter
from web.middlewares.auth import load_user
from web.middlewares.ip_whitelist import whitelist_middleware

# Импорт всех моделей обязателен до Base.metadata.create_all
from models.user import User
from models.account import Account
from models.proxy import Proxy
from models.campaign import Campaign
from models.stat import Stat
from models.admin_log import AdminLog
from models.task import Task

def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static',
                static_url_path='/static')
    
    app.config.from_object(Config)
    
    db.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    
    login_manager.login_view = 'admin.login'
    login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'
    login_manager.user_loader(load_user)
    
    app.before_request(whitelist_middleware)
    
    # Регистрация фильтра
    @app.template_filter('timestamp_to_date')
    def timestamp_to_date_filter(dt):
        if not dt: return '—'
        return dt.strftime('%d.%m.%Y %H:%M')
    
    from web.routes.public import public_bp
    from web.routes.admin import admin_bp
    from web.routes.api import api_bp
    
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    with app.app_context():
        Base.metadata.create_all(bind=engine)
        
        if not db.session.query(User).first() and Config.ADMIN_USERNAME and Config.ADMIN_PASSWORD_HASH:
            admin = User(
                username=Config.ADMIN_USERNAME,
                role='superadmin'
            )
            admin.password_hash = Config.ADMIN_PASSWORD_HASH
            db.session.add(admin)
            db.session.commit()
            log.info(f"Initial admin created: {Config.ADMIN_USERNAME}")
    
    log.info("Flask application created successfully")
    return app

app = create_app()
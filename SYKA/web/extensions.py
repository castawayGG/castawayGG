from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from celery import Celery
import os

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address)

def make_celery(app_name=__name__):
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    return Celery(app_name, broker=redis_url, backend=redis_url)

celery_app = make_celery()
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import bcrypt
import pyotp

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    otp_secret = Column(String(32), nullable=True)
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default='admin')
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime, nullable=True)
    login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    # Обратная связь с аккаунтами
    accounts = relationship('Account', back_populates='owner')

    def set_password(self, password: str):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def verify_otp(self, token: str) -> bool:
        if not self.otp_secret:
            return True
        totp = pyotp.TOTP(self.otp_secret)
        return totp.verify(token)

    def enable_2fa(self) -> str:
        self.otp_secret = pyotp.random_base32()
        return self.otp_secret

    def disable_2fa(self):
        self.otp_secret = None

    def is_locked(self) -> bool:
        if self.locked_until and self.locked_until > func.now():
            return True
        return False

    # ==========================================
    # СВОЙСТВА ДЛЯ FLASK-LOGIN (ИСПРАВЛЕНИЕ ОШИБКИ)
    # ==========================================
    @property
    def is_authenticated(self):
        """Обязательное свойство: возвращает True, если юзер авторизован"""
        return True

    @property
    def is_anonymous(self):
        """Обязательное свойство: возвращает False для обычных пользователей"""
        return False

    def get_id(self):
        """Обязательный метод: возвращает строковый ID пользователя"""
        return str(self.id)
    # ==========================================

    def __repr__(self):
        return f"<User {self.username}>"
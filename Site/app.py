from flask import Flask
from admin import admin_bp
import os

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_key_123")

# Регистрация модуля админки
app.register_blueprint(admin_bp)

@app.route('/')
def index():
    return "Система работает. <a href='/admin/dashboard'>Перейти в админку</a>"

if __name__ == '__main__':
    app.run(debug=True, port=5000)
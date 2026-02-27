from models.user import User
from web.extensions import db

# Удалить всех пользователей
db.session.query(User).delete()
db.session.commit()

# Создать одного нового
new_admin = User(username='admin')
new_admin.set_password('0932324169a')
new_admin.role = 'superadmin'
db.session.add(new_admin)
db.session.commit()

exit()
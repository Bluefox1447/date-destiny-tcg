from app import app, db, User
from werkzeug.security import generate_password_hash

EMAIL = "bluevisarut@gmail.com"
PASSWORD = "11114444"

with app.app_context():
    u = User.query.filter_by(email=EMAIL.lower()).first()
    if not u:
        u = User(email=EMAIL.lower(), username="Admin")
        db.session.add(u)
    u.password_hash = generate_password_hash(PASSWORD)
    u.role = "admin"
    u.verified = True      # ข้ามการยืนยันอีเมลสำหรับบัญชีนี้
    db.session.commit()
    print("เรียบร้อย")
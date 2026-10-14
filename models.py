import json
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    username = db.Column(db.String(40), nullable=False)
    password_hash = db.Column(db.String(255))
    avatar = db.Column(db.String(300), default='')
    bio = db.Column(db.String(300), default='')
    role = db.Column(db.String(10), default='user')          # user | admin
    verified = db.Column(db.Boolean, default=False)
    banned = db.Column(db.Boolean, default=False)
    google_id = db.Column(db.String(64), index=True)
    discord_id = db.Column(db.String(64), index=True)
    code = db.Column(db.String(10))
    code_exp = db.Column(db.DateTime)
    code_tries = db.Column(db.Integer, default=0)
    created = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_active(self):
        return not self.banned


class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(80), nullable=False)
    type = db.Column(db.String(10), nullable=False, default='entity')   # entity | ship | server
    color = db.Column(db.String(10), default='none')
    effect = db.Column(db.Text, default='')
    cost = db.Column(db.Integer, default=0)
    server = db.Column(db.String(60), default='')                      # Entity: เซิร์ฟเวอร์ที่สังกัด
    atk = db.Column(db.Integer, default=0)
    crit = db.Column(db.Integer, default=0)
    defense = db.Column(db.Integer, default=0)
    link_atk = db.Column(db.Integer, default=0)                        # Ship: link 1.โจมตี 2.คริ 3.ป้องกัน
    link_crit = db.Column(db.Integer, default=0)
    link_def = db.Column(db.Integer, default=0)
    image = db.Column(db.String(300), default='')
    created = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return dict(id=self.id, code=self.code, name=self.name, type=self.type, color=self.color,
                    effect=self.effect or '', cost=self.cost or 0, server=self.server or '',
                    atk=self.atk or 0, crit=self.crit or 0, **{'def': self.defense or 0},
                    link_atk=self.link_atk or 0, link_crit=self.link_crit or 0,
                    link_def=self.link_def or 0, image=self.image or '')


class Upload(db.Model):
    """รูปที่อัปโหลด (เก็บในฐานข้อมูล ใช้กับโฮสต์ที่ไม่มีดิสก์ถาวรเช่น Render ฟรี)"""
    id = db.Column(db.Integer, primary_key=True)
    mime = db.Column(db.String(40), default='image/png')
    data = db.Column(db.LargeBinary)
    created = db.Column(db.DateTime, default=datetime.utcnow)


class Sleeve(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    image = db.Column(db.String(300), default='')       # รูปหลังการ์ด
    is_default = db.Column(db.Boolean, default=False)   # หลังการ์ดเริ่มต้นของระบบ
    created = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return dict(id=self.id, name=self.name, image=self.image or '', default=bool(self.is_default))


class Deck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(400), default='')
    main_json = db.Column(db.Text, default='{}')          # {card_id: qty}
    partners_json = db.Column(db.Text, default='[]')      # [card_id x4]  (Neurous / Entity)
    operator_id = db.Column(db.Integer)                   # Server card วางบน Server Zone
    sleeve_id = db.Column(db.Integer)                     # สลีฟ (หลังการ์ด) ที่เลือกใช้
    public = db.Column(db.Boolean, default=False)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner = db.relationship('User', backref='decks')

    @property
    def main(self):
        return json.loads(self.main_json or '{}')

    @property
    def partners(self):
        return json.loads(self.partners_json or '[]')

    @property
    def size(self):
        return sum(self.main.values())

    def to_dict(self):
        return dict(id=self.id, name=self.name, desc=self.description, main=self.main,
                    partners=self.partners, operator=self.operator_id, sleeve=self.sleeve_id, public=self.public,
                    owner=self.owner.username if self.owner else '', size=self.size)


class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, default='')
    image = db.Column(db.String(300), default='')
    pinned = db.Column(db.Boolean, default=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User')

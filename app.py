import os, json, random, string, smtplib, base64, uuid, re, secrets
from datetime import datetime, timedelta
from email.message import EmailMessage
from functools import wraps

from dotenv import load_dotenv
load_dotenv()

from flask import (Flask, render_template, request, redirect, url_for, flash,
                   jsonify, abort, session, send_from_directory)
from flask_login import (LoginManager, login_user, logout_user, login_required, current_user)
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from authlib.integrations.flask_client import OAuth

from models import db, User, Card, Deck, News, Sleeve, Upload
import game

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)


def _secret_key():
    """ใช้ SECRET_KEY จาก .env ถ้าไม่ตั้งไว้จะสร้างให้และเก็บถาวรใน instance/secret_key"""
    k = os.getenv('SECRET_KEY')
    if k and k != 'change-me-to-a-long-random-string':
        return k
    path = os.path.join(BASE, 'instance', 'secret_key')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        return open(path).read().strip()
    k = secrets.token_hex(32)
    open(path, 'w').write(k)
    return k


_db_url = os.getenv('DATABASE_URL', 'sqlite:///dds.db')
if _db_url.startswith('postgres://'):                 # Render/Heroku ให้ URL แบบเก่า
    _db_url = 'postgresql://' + _db_url[len('postgres://'):]
ON_RENDER = bool(os.getenv('RENDER'))                   # Render ตั้งตัวแปร RENDER ให้เอง
_secure = os.getenv('COOKIE_SECURE') == '1' or ON_RENDER   # เปิดผ่าน HTTPS
app.config.update(
    SECRET_KEY=_secret_key(),
    SQLALCHEMY_DATABASE_URI=_db_url,
    SQLALCHEMY_ENGINE_OPTIONS={'pool_pre_ping': True},
    MAX_CONTENT_LENGTH=6 * 1024 * 1024,
    SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=_secure, REMEMBER_COOKIE_SECURE=_secure, REMEMBER_COOKIE_HTTPONLY=True,
)
PUBLIC_URL = (os.getenv('PUBLIC_URL') or os.getenv('RENDER_EXTERNAL_URL') or '').rstrip('/')
if os.getenv('BEHIND_PROXY') == '1' or ON_RENDER:                   # อยู่หลัง Cloudflare/Render/nginx: เชื่อ header https/โดเมนจริง
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'กรุณาเข้าสู่ระบบก่อน'
_cors = os.getenv('CORS_ORIGINS', '*')
sio = SocketIO(app, async_mode='threading',
               cors_allowed_origins='*' if _cors == '*' else [o.strip() for o in _cors.split(',') if o.strip()])

DECK_SIZE = int(os.getenv('DECK_SIZE', 50))
MAX_COPIES = int(os.getenv('MAX_COPIES', 4))
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv('ADMIN_EMAILS', '').split(',') if e.strip()}
COLORS = [('red', 'แดง'), ('blue', 'น้ำเงิน'), ('green', 'เขียว'), ('yellow', 'เหลือง'),
          ('purple', 'ม่วง'), ('black', 'ดำ'), ('white', 'ขาว'), ('none', 'ไร้สี')]
TYPES = [('entity', 'Entity (Neurous)'), ('partners', 'Partners'), ('ship', 'Ship'), ('server', 'Server')]
NEUROUS = ('entity', 'partners')      # ประเภทที่วางใน Partners Zone / ลง Attack-Protect ได้

# ---------------------------------------------------------------- OAuth
oauth = OAuth(app)
if os.getenv('GOOGLE_CLIENT_ID'):
    oauth.register('google', client_id=os.getenv('GOOGLE_CLIENT_ID'),
                   client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
                   server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
                   client_kwargs={'scope': 'openid email profile'})
if os.getenv('DISCORD_CLIENT_ID'):
    oauth.register('discord', client_id=os.getenv('DISCORD_CLIENT_ID'),
                   client_secret=os.getenv('DISCORD_CLIENT_SECRET'),
                   access_token_url='https://discord.com/api/oauth2/token',
                   authorize_url='https://discord.com/oauth2/authorize',
                   api_base_url='https://discord.com/api/',
                   client_kwargs={'scope': 'identify email'})


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


@app.context_processor
def inject():
    return dict(COLORS=COLORS, TYPES=TYPES, DECK_SIZE=DECK_SIZE, MAX_COPIES=MAX_COPIES,
                social=[p for p in ('google', 'discord') if oauth.create_client(p)])


def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.path))
        if not current_user.is_admin:
            abort(403)
        return f(*a, **k)
    return w


def to_int(v, d=0, lo=-999, hi=999):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return d


UPLOAD_ROOT = os.getenv('UPLOAD_DIR') or os.path.join(BASE, 'static', 'uploads')
UPLOAD_URL = '/uploads' if os.getenv('UPLOAD_DIR') else '/static/uploads'
UPLOADS_IN_DB = os.getenv('UPLOADS_IN_DB') == '1' or (ON_RENDER and not os.getenv('UPLOAD_DIR'))
MIMES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif'}


@app.get('/media/<name>')
def media(name):
    try:
        up = db.session.get(Upload, int(name.split('.')[0]))
    except ValueError:
        up = None
    if not up:
        abort(404)
    r = app.response_class(up.data, mimetype=up.mime)
    r.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return r


@app.get('/uploads/<path:p>')
def uploads(p):
    return send_from_directory(UPLOAD_ROOT, p)


@app.get('/healthz')
def healthz():
    return 'ok'


def save_upload(file, sub):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
        return None
    if UPLOADS_IN_DB:
        up = Upload(mime=MIMES[ext], data=file.read())
        db.session.add(up)
        db.session.commit()
        return f'/media/{up.id}{ext}'
    name = uuid.uuid4().hex + ext
    folder = os.path.join(UPLOAD_ROOT, sub)
    os.makedirs(folder, exist_ok=True)
    file.save(os.path.join(folder, name))
    return f'{UPLOAD_URL}/{sub}/{name}'


def pop_next():
    """กลับไปหน้าที่ตั้งใจจะเข้า (เช่นลิงก์ห้องที่เพื่อนส่งมา) หลังล็อคอิน/สมัคร"""
    nxt = session.pop('next', '')
    return nxt if nxt.startswith('/') and not nxt.startswith('//') else url_for('index')


# ---------------------------------------------------------------- Email
def send_mail(to, subject, body):
    host = os.getenv('MAIL_SERVER')
    if not host:
        print(f'\n[DEV MAIL] to={to}\n{subject}\n{body}\n')
        return True
    try:
        msg = EmailMessage()
        msg['From'] = os.getenv('MAIL_FROM') or os.getenv('MAIL_USERNAME')
        msg['To'], msg['Subject'] = to, subject
        msg.set_content(body)
        port = int(os.getenv('MAIL_PORT', 587))
        if os.getenv('MAIL_SSL') == '1':
            s = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            s = smtplib.SMTP(host, port, timeout=15)
            s.starttls()
        s.login(os.getenv('MAIL_USERNAME'), os.getenv('MAIL_PASSWORD'))
        s.send_message(msg)
        s.quit()
        return True
    except Exception as e:
        print('mail error:', e)
        return False


def issue_code(u):
    u.code = ''.join(random.choices(string.digits, k=6))
    u.code_exp = datetime.utcnow() + timedelta(minutes=15)
    u.code_tries = 0
    db.session.commit()
    return send_mail(u.email, 'รหัสยืนยันบัญชี Date Destiny TCG',
                     f'รหัสยืนยันของคุณคือ {u.code}\nรหัสมีอายุ 15 นาที หากคุณไม่ได้สมัคร โปรดละเว้นอีเมลนี้')


# ---------------------------------------------------------------- Pages & Auth
@app.route('/')
def index():
    news = News.query.order_by(News.pinned.desc(), News.created.desc()).limit(8).all()
    return render_template('index.html', news=news, n_cards=Card.query.count(),
                           n_users=User.query.filter_by(verified=True).count())


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        username = request.form.get('username', '').strip()
        pw = request.form.get('password', '')
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            flash('รูปแบบอีเมลไม่ถูกต้อง', 'err')
        elif not 2 <= len(username) <= 30:
            flash('ชื่อผู้ใช้ต้องยาว 2–30 ตัวอักษร', 'err')
        elif len(pw) < 8:
            flash('รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร', 'err')
        else:
            u = User.query.filter_by(email=email).first()
            if u and u.verified:
                flash('อีเมลนี้ถูกใช้สมัครแล้ว ลองเข้าสู่ระบบแทน', 'err')
                return redirect(url_for('login'))
            if not u:
                u = User(email=email)
                db.session.add(u)
            u.username, u.password_hash = username, generate_password_hash(pw)
            if email in ADMIN_EMAILS and os.getenv('SKIP_EMAIL_VERIFY') != '1':
                u.role = 'admin'
            if os.getenv('SKIP_EMAIL_VERIFY') == '1':      # ไม่ส่งรหัสทางอีเมล สมัครเสร็จใช้งานได้ทันที
                u.verified, u.code = True, None
                db.session.commit()
                login_user(u, remember=True)
                flash('สมัครสมาชิกสำเร็จ ยินดีต้อนรับ!', 'ok')
                return redirect(pop_next())
            ok = issue_code(u)
            session['verify_email'] = email
            flash('ส่งรหัสยืนยัน 6 หลักไปที่อีเมลแล้ว' if ok else
                  'ส่งอีเมลไม่สำเร็จ ตรวจสอบการตั้งค่า MAIL_* แล้วกด "ส่งรหัสอีกครั้ง"', 'ok' if ok else 'err')
            return redirect(url_for('verify'))
    return render_template('register.html')


@app.route('/verify', methods=['GET', 'POST'])
def verify():
    email = session.get('verify_email') or request.form.get('email', '')
    if request.method == 'POST':
        u = User.query.filter_by(email=email.strip().lower()).first()
        code = request.form.get('code', '').strip()
        if not u or not u.code:
            flash('ไม่พบคำขอยืนยัน กรุณาสมัครใหม่', 'err')
        elif u.code_tries >= 5 or datetime.utcnow() > u.code_exp:
            flash('รหัสหมดอายุหรือกรอกผิดหลายครั้ง กด "ส่งรหัสอีกครั้ง"', 'err')
        elif code != u.code:
            u.code_tries += 1
            db.session.commit()
            flash('รหัสไม่ถูกต้อง', 'err')
        else:
            u.verified, u.code = True, None
            db.session.commit()
            session.pop('verify_email', None)
            login_user(u)
            flash('ยืนยันอีเมลสำเร็จ ยินดีต้อนรับ!', 'ok')
            return redirect(pop_next())
    return render_template('verify.html', email=email)


@app.post('/verify/resend')
def resend():
    u = User.query.filter_by(email=request.form.get('email', '').strip().lower()).first()
    if u and not u.verified:
        issue_code(u)
        flash('ส่งรหัสใหม่แล้ว', 'ok')
    return redirect(url_for('verify'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    nx = request.args.get('next', '')
    if nx.startswith('/') and not nx.startswith('//'):
        session['next'] = nx
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        u = User.query.filter_by(email=email).first()
        if not u or not u.password_hash or not check_password_hash(u.password_hash, request.form.get('password', '')):
            flash('อีเมลหรือรหัสผ่านไม่ถูกต้อง', 'err')
        elif u.banned:
            flash('บัญชีนี้ถูกระงับ', 'err')
        elif not u.verified:
            session['verify_email'] = email
            issue_code(u)
            flash('ยังไม่ได้ยืนยันอีเมล ส่งรหัสใหม่ให้แล้ว', 'err')
            return redirect(url_for('verify'))
        else:
            if email in ADMIN_EMAILS and not u.is_admin and os.getenv('SKIP_EMAIL_VERIFY') != '1':
                u.role = 'admin'
                db.session.commit()
            login_user(u, remember=True)
            return redirect(pop_next())
    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/auth/<provider>')
def oauth_login(provider):
    client = oauth.create_client(provider)
    if not client:
        flash(f'ยังไม่ได้ตั้งค่า {provider} ในไฟล์ .env', 'err')
        return redirect(url_for('login'))
    return client.authorize_redirect(url_for('oauth_callback', provider=provider, _external=True))


@app.route('/auth/<provider>/callback')
def oauth_callback(provider):
    client = oauth.create_client(provider)
    if not client:
        abort(404)
    try:
        token = client.authorize_access_token()
        if provider == 'google':
            info = token.get('userinfo') or client.userinfo()
            pid, email, name, avatar = info['sub'], info.get('email'), info.get('name'), info.get('picture')
            if not info.get('email_verified', True):
                raise ValueError('email not verified')
        else:
            info = client.get('users/@me', token=token).json()
            pid, email = info['id'], info.get('email')
            name = info.get('global_name') or info.get('username')
            avatar = (f"https://cdn.discordapp.com/avatars/{pid}/{info['avatar']}.png"
                      if info.get('avatar') else '')
            if not info.get('verified', False):
                raise ValueError('email not verified')
    except Exception as e:
        print('oauth error', e)
        flash('เข้าสู่ระบบด้วยบัญชีภายนอกไม่สำเร็จ (ต้องมีอีเมลที่ยืนยันแล้ว)', 'err')
        return redirect(url_for('login'))
    col = f'{provider}_id'
    u = User.query.filter(getattr(User, col) == pid).first() or User.query.filter_by(email=email.lower()).first()
    if not u:
        u = User(email=email.lower(), username=(name or email.split('@')[0])[:30], avatar=avatar or '')
        db.session.add(u)
    setattr(u, col, pid)
    u.verified = True
    if not u.avatar and avatar:
        u.avatar = avatar
    if u.email in ADMIN_EMAILS:
        u.role = 'admin'
    db.session.commit()
    if u.banned:
        flash('บัญชีนี้ถูกระงับ', 'err')
        return redirect(url_for('login'))
    login_user(u, remember=True)
    return redirect(pop_next())


@app.route('/claim-admin', methods=['GET', 'POST'])
@login_required
def claim_admin():
    """ขอสิทธิ์ Admin ด้วยรหัสลับ ADMIN_CLAIM_TOKEN (ใช้บนโฮสต์ที่เปิด Shell ไม่ได้ เช่น Render ฟรี)"""
    token = os.getenv('ADMIN_CLAIM_TOKEN', '')
    if request.method == 'POST':
        if token and secrets.compare_digest(request.form.get('token', ''), token):
            current_user.role = 'admin'
            db.session.commit()
            flash('คุณเป็น Admin แล้ว', 'ok')
            return redirect(url_for('admin_cards'))
        flash('รหัสไม่ถูกต้อง (หรือยังไม่ได้ตั้ง ADMIN_CLAIM_TOKEN)', 'err')
    return render_template('claim_admin.html', enabled=bool(token))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        u = current_user
        name = request.form.get('username', '').strip()
        if 2 <= len(name) <= 30:
            u.username = name
        u.bio = request.form.get('bio', '')[:300]
        f = request.files.get('avatar')
        if f and f.filename:
            url = save_upload(f, 'avatars')
            if url:
                u.avatar = url
        new = request.form.get('new_password', '')
        if new:
            if len(new) < 8:
                flash('รหัสผ่านใหม่ต้องมีอย่างน้อย 8 ตัวอักษร', 'err')
                return redirect(url_for('profile'))
            if u.password_hash and not check_password_hash(u.password_hash, request.form.get('old_password', '')):
                flash('รหัสผ่านเดิมไม่ถูกต้อง', 'err')
                return redirect(url_for('profile'))
            u.password_hash = generate_password_hash(new)
        db.session.commit()
        flash('บันทึกโปรไฟล์แล้ว', 'ok')
        return redirect(url_for('profile'))
    return render_template('profile.html')


# ---------------------------------------------------------------- Cards
@app.route('/cards')
def cards():
    return render_template('cards.html')


@app.get('/api/cards')
def api_cards():
    return jsonify([c.to_dict() for c in Card.query.order_by(Card.code).all()])


def card_from_form(card):
    f = request.form
    card.name = f.get('name', '').strip()[:80] or 'Unnamed'
    card.type = f.get('type') if f.get('type') in [t for t, _ in TYPES] else 'entity'
    card.color = f.get('color') if f.get('color') in [c for c, _ in COLORS] else 'none'
    card.effect = f.get('effect', '').strip()
    card.cost = to_int(f.get('cost'), 0, 0, 99)
    e, s = card.type in NEUROUS, card.type == 'ship'
    card.server = f.get('server', '').strip()[:60] if e else ''
    card.atk = to_int(f.get('atk'), 0, 0, 99999) if e else 0
    card.crit = to_int(f.get('crit'), 0, 0, 99999) if e else 0
    card.defense = to_int(f.get('defense'), 0, 0, 99999) if e else 0
    card.link_atk = to_int(f.get('link_atk'), 0, -99999, 99999) if s else 0
    card.link_crit = to_int(f.get('link_crit'), 0, -99999, 99999) if s else 0
    card.link_def = to_int(f.get('link_def'), 0, -99999, 99999) if s else 0
    if f.get('clear_image'):
        card.image = ''
    img = request.files.get('image')
    if img and img.filename:
        url = save_upload(img, 'cards')
        if url:
            card.image = url


@app.route('/admin/cards')
@admin_required
def admin_cards():
    return render_template('admin/cards.html', cards=Card.query.order_by(Card.id.desc()).all())


@app.route('/admin/cards/new', methods=['GET', 'POST'])
@app.route('/admin/cards/<int:cid>/edit', methods=['GET', 'POST'])
@admin_required
def admin_card_form(cid=None):
    card = db.get_or_404(Card, cid) if cid else None
    if request.method == 'POST':
        new = card is None
        card = card or Card()
        card_from_form(card)
        code = request.form.get('code', '').strip().upper()[:20]
        if code and Card.query.filter(Card.code == code, Card.id != (card.id or 0)).first():
            flash('รหัสการ์ดนี้ถูกใช้แล้ว', 'err')
            return render_template('admin/card_form.html', card=card)
        card.code = code or card.code
        if new:
            db.session.add(card)
        db.session.flush()
        if not card.code:
            card.code = f'DD-{card.id:04d}'
        db.session.commit()
        flash(f'บันทึกการ์ด {card.name} แล้ว', 'ok')
        return redirect(url_for('admin_cards'))
    return render_template('admin/card_form.html', card=card)


@app.post('/admin/cards/<int:cid>/delete')
@admin_required
def admin_card_delete(cid):
    db.session.delete(db.get_or_404(Card, cid))
    db.session.commit()
    flash('ลบการ์ดแล้ว', 'ok')
    return redirect(url_for('admin_cards'))


# ---------------------------------------------------------------- News (admin)
@app.route('/admin/news', methods=['GET', 'POST'])
@admin_required
def admin_news():
    if request.method == 'POST':
        n = db.session.get(News, to_int(request.form.get('id'), 0)) or News(author_id=current_user.id)
        n.title = request.form.get('title', '').strip()[:160] or 'ข่าวอัปเดต'
        n.body = request.form.get('body', '')
        n.pinned = bool(request.form.get('pinned'))
        f = request.files.get('image')
        if f and f.filename:
            n.image = save_upload(f, 'news') or n.image
        if not n.id:
            db.session.add(n)
        db.session.commit()
        flash('บันทึกข่าวแล้ว', 'ok')
        return redirect(url_for('admin_news'))
    edit = db.session.get(News, to_int(request.args.get('edit'), 0))
    return render_template('admin/news.html', items=News.query.order_by(News.created.desc()).all(), edit=edit)


@app.post('/admin/news/<int:nid>/delete')
@admin_required
def admin_news_delete(nid):
    db.session.delete(db.get_or_404(News, nid))
    db.session.commit()
    return redirect(url_for('admin_news'))


# ---------------------------------------------------------------- Users (admin)
@app.route('/admin/users')
@admin_required
def admin_users():
    q = request.args.get('q', '').strip()
    qs = User.query
    if q:
        qs = qs.filter(db.or_(User.email.contains(q), User.username.contains(q)))
    return render_template('admin/users.html', users=qs.order_by(User.id.desc()).limit(200).all(), q=q)


@app.route('/admin/users/<int:uid>', methods=['GET', 'POST'])
@admin_required
def admin_user_edit(uid):
    u = db.get_or_404(User, uid)
    if request.method == 'POST':
        f = request.form
        u.username = f.get('username', u.username).strip()[:40] or u.username
        u.bio = f.get('bio', '')[:300]
        if u.id != current_user.id:                      # กันแอดมินล็อคตัวเอง
            u.role = 'admin' if f.get('role') == 'admin' else 'user'
            u.banned = bool(f.get('banned'))
        u.verified = bool(f.get('verified'))
        if f.get('clear_avatar'):
            u.avatar = ''
        if f.get('new_password'):
            if len(f['new_password']) < 8:
                flash('รหัสผ่านใหม่ต้องมีอย่างน้อย 8 ตัวอักษร', 'err')
                return redirect(url_for('admin_user_edit', uid=uid))
            u.password_hash = generate_password_hash(f['new_password'])
        db.session.commit()
        flash('แก้ไขโปรไฟล์ผู้ใช้แล้ว', 'ok')
        return redirect(url_for('admin_users'))
    return render_template('admin/user_edit.html', u=u)


@app.post('/admin/users/<int:uid>/delete')
@admin_required
def admin_user_delete(uid):
    u = db.get_or_404(User, uid)
    if u.id == current_user.id:
        flash('ลบบัญชีตัวเองไม่ได้', 'err')
    else:
        Deck.query.filter_by(user_id=u.id).delete()
        db.session.delete(u)
        db.session.commit()
        flash('ลบผู้ใช้แล้ว', 'ok')
    return redirect(url_for('admin_users'))


# ---------------------------------------------------------------- Decks
def clean_deck(data):
    main = {}
    for k, v in (data.get('main') or {}).items():
        q = to_int(v, 0, 0, MAX_COPIES)
        if q and to_int(k, 0, 1, 10**9):
            main[str(int(k))] = q
    partners = [to_int(x, 0, 1, 10**9) for x in (data.get('partners') or [])][:4]
    ids = set(map(int, main)) | set(partners)
    have = {c.id: c for c in Card.query.filter(Card.id.in_(ids)).all()} if ids else {}
    main = {k: q for k, q in main.items() if int(k) in have}
    partners = [p for p in partners if p in have and have[p].type in NEUROUS]
    # จำนวนซ้ำสูงสุด (นับรวมเด็คหลัก + Partners) ถ้าเกินให้ตัดจากเด็คหลัก
    for k in list(main):
        room = MAX_COPIES - partners.count(int(k))
        main[k] = min(main[k], max(0, room))
        if main[k] <= 0:
            del main[k]
    return main, partners, None


def deck_issues(d):
    out = []
    if len(d.partners) != 4:
        out.append(f'Partners ต้องมี 4 ใบ (ตอนนี้ {len(d.partners)})')
    if d.size != DECK_SIZE:
        out.append(f'เด็คหลักควรมี {DECK_SIZE} ใบ (ตอนนี้ {d.size})')
    return out


def deck_code(d):
    cards = {c.id: c.code for c in Card.query.all()}
    payload = dict(v=1, n=d.name, d=d.description,
                   m={cards[int(k)]: q for k, q in d.main.items() if int(k) in cards},
                   p=[cards[p] for p in d.partners if p in cards])
    return base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode()).decode()


@app.route('/decks')
@login_required
def decks():
    mine = Deck.query.filter_by(user_id=current_user.id).order_by(Deck.updated.desc()).all()
    pub = Deck.query.filter(Deck.public.is_(True), Deck.user_id != current_user.id) \
        .order_by(Deck.updated.desc()).limit(60).all()
    return render_template('decks.html', mine=mine, pub=pub, issues={d.id: deck_issues(d) for d in mine})


@app.route('/decks/new')
@app.route('/decks/<int:did>/edit')
@login_required
def deck_edit(did=None):
    d = db.get_or_404(Deck, did) if did else None
    if d and d.user_id != current_user.id:
        abort(403)
    return render_template('deck_edit.html', sleeves=[s.to_dict() for s in Sleeve.query.order_by(Sleeve.id)],
                           deck=d.to_dict() if d else
                           dict(id=None, name='เด็คใหม่', desc='', main={}, partners=[], operator=None, sleeve=None, public=False))


@app.post('/api/decks')
@login_required
def api_deck_save():
    data = request.get_json(force=True)
    d = db.session.get(Deck, to_int(data.get('id'), 0))
    if d and d.user_id != current_user.id:
        abort(403)
    if not d:
        d = Deck(user_id=current_user.id)
        db.session.add(d)
    d.name = (data.get('name') or 'เด็คใหม่').strip()[:80]
    d.description = (data.get('desc') or '')[:400]
    d.public = bool(data.get('public'))
    main, partners, op = clean_deck(data)
    d.main_json, d.partners_json, d.operator_id = json.dumps(main), json.dumps(partners), op
    sid = to_int(data.get('sleeve'), 0, 0, 10**9)
    d.sleeve_id = sid if sid and db.session.get(Sleeve, sid) else None
    db.session.commit()
    return jsonify(id=d.id, issues=deck_issues(d))


@app.get('/api/decks/<int:did>/code')
@login_required
def api_deck_code(did):
    d = db.get_or_404(Deck, did)
    if d.user_id != current_user.id and not d.public:
        abort(403)
    return jsonify(code=deck_code(d))


@app.post('/decks/<int:did>/copy')
@login_required
def deck_copy(did):
    d = db.get_or_404(Deck, did)
    if d.user_id != current_user.id and not d.public:
        abort(403)
    n = Deck(user_id=current_user.id, name=f'{d.name} (copy)'[:80], description=d.description,
             main_json=d.main_json, partners_json=d.partners_json, operator_id=d.operator_id, sleeve_id=d.sleeve_id)
    db.session.add(n)
    db.session.commit()
    flash('คัดลอกเด็คไปยังคลังของคุณแล้ว', 'ok')
    return redirect(url_for('deck_edit', did=n.id))


@app.post('/decks/<int:did>/delete')
@login_required
def deck_delete(did):
    d = db.get_or_404(Deck, did)
    if d.user_id != current_user.id:
        abort(403)
    db.session.delete(d)
    db.session.commit()
    flash('ลบเด็คแล้ว', 'ok')
    return redirect(url_for('decks'))


@app.post('/decks/<int:did>/public')
@login_required
def deck_public(did):
    d = db.get_or_404(Deck, did)
    if d.user_id != current_user.id:
        abort(403)
    d.public = not d.public
    db.session.commit()
    return redirect(url_for('decks'))


@app.post('/decks/import')
@login_required
def deck_import():
    try:
        raw = request.form.get('code', '').strip()
        p = json.loads(base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4)).decode())
        by_code = {c.code: c for c in Card.query.all()}
        main = {str(by_code[k].id): q for k, q in p.get('m', {}).items() if k in by_code}
        miss = [k for k in list(p.get('m', {})) + p.get('p', []) if k not in by_code]
        partners = [by_code[k].id for k in p.get('p', []) if k in by_code]
        m, pa, o = clean_deck(dict(main=main, partners=partners))
        d = Deck(user_id=current_user.id, name=(p.get('n') or 'Imported deck')[:80], description=(p.get('d') or '')[:400],
                 main_json=json.dumps(m), partners_json=json.dumps(pa), operator_id=o)
        db.session.add(d)
        db.session.commit()
        flash('นำเข้าเด็คสำเร็จ' + (f' (ไม่พบการ์ด {len(miss)} ใบในระบบนี้)' if miss else ''), 'ok')
        return redirect(url_for('deck_edit', did=d.id))
    except Exception as e:
        print('import error', e)
        flash('โค้ดเด็คไม่ถูกต้อง', 'err')
        return redirect(url_for('decks'))


# ---------------------------------------------------------------- Sleeves (หลังการ์ด)
@app.get('/api/sleeves')
def api_sleeves():
    return jsonify([s.to_dict() for s in Sleeve.query.order_by(Sleeve.id)])


@app.route('/admin/sleeves', methods=['GET', 'POST'])
@admin_required
def admin_sleeves():
    if request.method == 'POST':
        f = request.files.get('image')
        url = save_upload(f, 'sleeves') if f and f.filename else None
        if not url:
            flash('กรุณาเลือกรูป PNG/JPG/WebP สำหรับหลังการ์ด', 'err')
            return redirect(url_for('admin_sleeves'))
        s = Sleeve(name=request.form.get('name', '').strip()[:80] or 'Sleeve', image=url)
        if request.form.get('is_default') or not Sleeve.query.count():
            Sleeve.query.update({Sleeve.is_default: False})
            s.is_default = True
        db.session.add(s)
        db.session.commit()
        flash('เพิ่ม Sleeve แล้ว', 'ok')
        return redirect(url_for('admin_sleeves'))
    return render_template('admin/sleeves.html', items=Sleeve.query.order_by(Sleeve.id.desc()).all())


@app.post('/admin/sleeves/<int:sid>/default')
@admin_required
def admin_sleeve_default(sid):
    s = db.get_or_404(Sleeve, sid)
    Sleeve.query.update({Sleeve.is_default: False})
    s.is_default = True
    db.session.commit()
    flash(f'ตั้ง {s.name} เป็นหลังการ์ดเริ่มต้นแล้ว', 'ok')
    return redirect(url_for('admin_sleeves'))


@app.post('/admin/sleeves/<int:sid>/delete')
@admin_required
def admin_sleeve_delete(sid):
    db.session.delete(db.get_or_404(Sleeve, sid))
    Deck.query.filter_by(sleeve_id=sid).update({Deck.sleeve_id: None})
    db.session.commit()
    flash('ลบ Sleeve แล้ว', 'ok')
    return redirect(url_for('admin_sleeves'))


# ---------------------------------------------------------------- Rooms
def room_deck(user, deck_id):
    d = db.session.get(Deck, to_int(deck_id, 0))
    if not d or (d.user_id != user.id and not d.public):
        return None, 'ไม่พบเด็คนี้'
    if len(d.partners) != 4 or d.size < 1:
        return None, 'เด็คต้องมี Partners 4 ใบ และมีการ์ดในเด็คหลัก'
    ids = set(map(int, d.main)) | set(d.partners)
    cards = {c.id: c.to_dict() for c in Card.query.filter(Card.id.in_(ids)).all()}
    main = {k: q for k, q in d.main.items() if int(k) in cards}
    if not set(d.partners) <= set(cards):
        return None, 'เด็คมีการ์ดที่ถูกลบออกจากระบบแล้ว กรุณาแก้ไขเด็ค'
    sl = db.session.get(Sleeve, d.sleeve_id) if d.sleeve_id else None
    sl = sl or Sleeve.query.filter_by(is_default=True).first()
    return dict(main=main, partners=d.partners, operator=None, name=d.name,
                sleeve=(sl.image if sl else '')), cards


@app.route('/rooms')
@login_required
def rooms():
    ds = Deck.query.filter_by(user_id=current_user.id).all()
    return render_template('rooms.html', decks=[dict(id=d.id, name=d.name, ok=len(d.partners) == 4 and d.size > 0) for d in ds])


@app.get('/api/rooms')
@login_required
def api_rooms():
    return jsonify(game.list_rooms())


@app.post('/rooms/create')
@login_required
def room_create():
    deck, cards = room_deck(current_user, request.form.get('deck_id'))
    if not deck:
        flash(cards, 'err')
        return redirect(url_for('rooms'))
    solo = request.form.get('solo') == '1'
    deck2 = cards2 = None
    if solo:   # ห้องทดสอบคนเดียว: ฝั่งตรงข้ามเป็นหุ่นที่เราควบคุมเอง
        deck2, cards2 = room_deck(current_user, request.form.get('deck2') or request.form.get('deck_id'))
        if not deck2:
            flash(cards2, 'err')
            return redirect(url_for('rooms'))
    code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=5))
    name = request.form.get('name', '').strip()[:40] or (f'ทดสอบเด็คของ {current_user.username}' if solo else f'ห้องของ {current_user.username}')
    with game.LOCK:
        room = game.create_room(code, name, current_user.id, solo=solo)
        game.add_player(room, current_user.id, current_user.username, current_user.avatar, deck, cards)
        if solo:
            game.add_player(room, -current_user.id, 'ฝั่งทดสอบ', '', deck2, cards2)
    return redirect(url_for('room_play', code=code))


@app.route('/rooms/<code>')
@login_required
def room_play(code):
    room = game.ROOMS.get(code.upper())
    if not room:
        flash('ไม่พบห้องนี้ (อาจถูกปิดไปแล้ว)', 'err')
        return redirect(url_for('rooms'))
    ds = Deck.query.filter(db.or_(Deck.user_id == current_user.id)).all()
    return render_template('play.html', code=room['code'], public_url=PUBLIC_URL,
                           decks=[dict(id=d.id, name=d.name) for d in ds if len(d.partners) == 4 and d.size > 0])


# ---------------------------------------------------------------- Socket.IO
SID = {}


def push(room):
    for p in room['players']:
        if p['sid']:
            emit('state', game.view(room, p['uid']), to=p['sid'])
    for sid in room['spectators']:
        emit('state', game.view(room, None), to=sid)


@sio.on('join')
def on_join(d):
    if not current_user.is_authenticated:
        return emit('err', {'m': 'กรุณาเข้าสู่ระบบ'})
    room = game.ROOMS.get(str(d.get('code', '')).upper())
    if not room:
        return emit('err', {'m': 'ไม่พบห้อง'})
    with game.LOCK:
        join_room(room['code'])
        SID[request.sid] = (room['code'], current_user.id)
        p = game.seat(room, current_user.id)
        if p:
            p['sid'], p['online'] = request.sid, True
        elif len(room['players']) < 2 and not d.get('spectate'):
            if not d.get('deck_id'):
                emit('need_deck', {})
                return
            deck, cards = room_deck(current_user, d.get('deck_id'))
            if not deck:
                return emit('err', {'m': cards})
            p = game.add_player(room, current_user.id, current_user.username, current_user.avatar, deck, cards)
            p['sid'] = request.sid
        else:
            room['spectators'][request.sid] = current_user.username
        push(room)


@sio.on('act')
def on_act(d):
    if not current_user.is_authenticated:
        return
    room = game.ROOMS.get(str(d.get('code', '')).upper())
    if not room:
        return emit('err', {'m': 'ไม่พบห้อง'})
    with game.LOCK:
        try:
            actor = current_user.id
            if room.get('solo') and actor == room['host'] and d.get('as') == -actor:
                actor = -actor                      # ห้องทดสอบ: เจ้าของห้องควบคุมฝั่งหุ่นได้
            err, extra = game.act(room, actor, d)
        except (KeyError, ValueError, TypeError) as e:
            err, extra = f'ข้อมูลไม่ถูกต้อง: {e}', None
        if err:
            emit('err', {'m': err})
        if d.get('type') == 'peek' and extra is not None:
            emit('peek', {'cards': extra})
        push(room)


@sio.on('disconnect')
def on_disconnect():
    info = SID.pop(request.sid, None)
    if not info:
        return
    room = game.ROOMS.get(info[0])
    if not room:
        return
    with game.LOCK:
        room['spectators'].pop(request.sid, None)
        p = game.seat(room, info[1])
        if p and p['sid'] == request.sid:
            p['online'] = False
        push(room)


# ---------------------------------------------------------------- CLI / seed
@app.cli.command('make-admin')
def make_admin_cmd():
    """flask make-admin  (ถามอีเมลแล้วตั้งเป็น Admin)"""
    email = input('อีเมลผู้ใช้: ').strip().lower()
    u = User.query.filter_by(email=email).first()
    if not u:
        print('ไม่พบผู้ใช้ ต้องสมัครสมาชิกก่อน')
        return
    u.role = 'admin'
    db.session.commit()
    print('ตั้งเป็น Admin แล้ว')


@app.cli.command('seed-demo')
def seed_demo():
    """flask seed-demo  (เพิ่มการ์ดตัวอย่าง สำหรับทดลองระบบ)"""
    from seed import DEMO
    n = 0
    for row in DEMO:
        if Card.query.filter_by(code=row['code']).first():
            continue
        db.session.add(Card(**row))
        n += 1
    db.session.commit()
    print(f'เพิ่มการ์ดตัวอย่าง {n} ใบ')


def migrate():
    """เพิ่มคอลัมน์ใหม่ให้ฐานข้อมูลเดิมโดยไม่ต้องลบข้อมูล"""
    from sqlalchemy import inspect, text
    cols = {c['name'] for c in inspect(db.engine).get_columns('deck')}
    if 'sleeve_id' not in cols:
        db.session.execute(text('ALTER TABLE deck ADD COLUMN sleeve_id INTEGER'))
        db.session.commit()


with app.app_context():
    db.create_all()
    migrate()

if __name__ == '__main__':
    sio.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 5000)),
            debug=os.getenv('FLASK_DEBUG') == '1', allow_unsafe_werkzeug=True)

#!/usr/bin/env python3
import os
import time
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path
from flask import (
    Flask, render_template, request, redirect, url_for, session,
    send_from_directory, g, abort
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# ----- إعداد التطبيق -----
app = Flask(__name__)

# إعدادات قابلة للتعديل عبر متغيرات البيئة
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'bansafi_super_secret_key_999_change_me')
DB_NAME = os.getenv('DB_NAME', 'transfers.db')
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', 4))

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_MB * 1024 * 1024  # حد أقصى للرفع
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

# تأكد من وجود مجلد التحميلات
Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)

# ----- قاعدة البيانات -----
def get_db():
    if 'db' not in g:
        conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # جدول العملاء
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT UNIQUE,
            password TEXT,
            otp TEXT,
            is_verified INTEGER DEFAULT 0
        )
    ''')
    # جدول الموظفين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            emp_account TEXT UNIQUE,
            password TEXT,
            is_active INTEGER DEFAULT 0
        )
    ''')
    # جدول الحوالات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transfer_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            network TEXT,
            sender_name TEXT,
            phone TEXT,
            target_account TEXT,
            amount REAL,
            currency TEXT,
            status TEXT DEFAULT 'قيد المعالجة',
            receipt_filename TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

# انشئ DB عند بدء التطبيق إذا لم تكن موجودة
init_db()

# ----- مساعدة الملفات -----
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def make_unique_filename(original):
    ts = int(time.time())
    name = secure_filename(original)
    return f"{ts}_{name}"

# ----- ديكوراتور لحماية المسارات -----
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_phone' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

def emp_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'emp_id' not in session:
            return redirect(url_for('emp_login'))
        return f(*args, **kwargs)
    return decorated

# ==================== 1. واجهة العميل ====================
@app.route('/')
@login_required
def index():
    db = get_db()
    cur = db.execute("SELECT * FROM transfer_requests WHERE phone = ? ORDER BY id DESC", (session['user_phone'],))
    user_requests = cur.fetchall()
    return render_template('index.html', page='dashboard', user_requests=user_requests)

@app.route('/register_page')
def register_page():
    return render_template('index.html', page='register')

@app.route('/login_page')
def login_page():
    return render_template('index.html', page='login')

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '')
    if not (name and phone and password):
        return render_template('index.html', page='register', error="يرجى ملء جميع الحقول.")

    otp = str(__import__('random').randint(1000, 9999))
    hashed = generate_password_hash(password)

    try:
        db = get_db()
        db.execute("INSERT INTO users (name, phone, password, otp) VALUES (?, ?, ?, ?)",
                   (name, phone, hashed, otp))
        db.commit()
        # في بيئة الإنتاج: هنا ترسل OTP عبر SMS بدلاً من الاعتماد على لوحة الموظف
        return render_template('index.html', page='verify', phone=phone)
    except sqlite3.IntegrityError:
        return render_template('index.html', page='register', error="رقم الهاتف مسجل مسبقاً!")

@app.route('/verify', methods=['POST'])
def verify():
    phone = request.form.get('phone')
    otp_input = request.form.get('otp', '').strip()

    db = get_db()
    cur = db.execute("SELECT * FROM users WHERE phone = ? AND otp = ?", (phone, otp_input))
    user = cur.fetchone()

    if user:
        db.execute("UPDATE users SET is_verified = 1, otp = NULL WHERE phone = ?", (phone,))
        db.commit()
        session['user_phone'] = user['phone']
        session['user_name'] = user['name']
        return redirect(url_for('index'))
    else:
        return render_template('index.html', page='verify', phone=phone, error="رمز التحقق غير صحيح.")

@app.route('/login', methods=['POST'])
def login():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '')

    db = get_db()
    cur = db.execute("SELECT * FROM users WHERE name = ? AND phone = ?", (name, phone))
    user = cur.fetchone()

    if user and check_password_hash(user['password'], password):
        if user['is_verified'] == 0:
            return render_template('index.html', page='verify', phone=phone, error="الحساب غير مفعل بعد.")
        session['user_phone'] = user['phone']
        session['user_name'] = user['name']
        return redirect(url_for('index'))
    else:
        return render_template('index.html', page='login', error="بيانات الدخول غير صحيحة.")

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    old_pass = request.form.get('old_password', '')
    new_pass = request.form.get('new_password', '')
    if not (old_pass and new_pass):
        return redirect(url_for('index'))

    db = get_db()
    cur = db.execute("SELECT * FROM users WHERE phone = ?", (session['user_phone'],))
    user = cur.fetchone()

    if user and check_password_hash(user['password'], old_pass):
        new_hashed = generate_password_hash(new_pass)
        db.execute("UPDATE users SET password = ? WHERE phone = ?", (new_hashed, session['user_phone']))
        db.commit()
    return redirect(url_for('index'))

@app.route('/send', methods=['POST'])
@login_required
def send_transfer():
    network = request.form.get('network')
    target_account = request.form.get('target_account')
    try:
        amount = float(request.form.get('amount', 0))
    except ValueError:
        amount = 0.0
    currency = request.form.get('currency')
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    db = get_db()
    db.execute('''
        INSERT INTO transfer_requests (network, sender_name, phone, target_account, amount, currency, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (network, session['user_name'], session['user_phone'], target_account, amount, currency, created_at))
    db.commit()

    return redirect(url_for('index'))

# ==================== 2. نظام الموظفين والإدارة ====================
@app.route('/emp_register', methods=['GET', 'POST'])
def emp_register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        emp_account = request.form.get('emp_account', '').strip()
        password = request.form.get('password', '')
        if not (name and emp_account and password):
            return render_template('emp_register.html', error="يرجى ملء جميع الحقول.")
        try:
            db = get_db()
            hashed = generate_password_hash(password)
            db.execute("INSERT INTO employees (name, emp_account, password) VALUES (?, ?, ?)", (name, emp_account, hashed))
            db.commit()
            return render_template('emp_login.html', msg="تم تقديم الطلب بنجاح! يرجى الانتظار حتى يقوم مدير النظام بتفعيل حسابك.")
        except sqlite3.IntegrityError:
            return render_template('emp_register.html', error="رقم الحساب مستخدم بالفعل!")
    return render_template('emp_register.html')

@app.route('/emp_login', methods=['GET', 'POST'])
def emp_login():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        emp_account = request.form.get('emp_account', '').strip()
        password = request.form.get('password', '')

        db = get_db()
        cur = db.execute("SELECT * FROM employees WHERE name = ? AND emp_account = ?", (name, emp_account))
        emp = cur.fetchone()

        if emp and check_password_hash(emp['password'], password):
            if emp['is_active'] == 0:
                return render_template('emp_login.html', error="حسابك بانتظار موافقة وتفعيل مدير النظام!")
            session['emp_id'] = emp['id']
            session['emp_name'] = emp['name']
            return redirect(url_for('admin_panel'))
        else:
            return render_template('emp_login.html', error="بيانات الموظف غير صحيحة!")

    return render_template('emp_login.html')

@app.route('/admin')
@emp_login_required
def admin_panel():
    db = get_db()
    pending_users = db.execute("SELECT * FROM users WHERE is_verified = 0").fetchall()
    all_requests = db.execute("SELECT * FROM transfer_requests WHERE status = 'قيد المعالجة' ORDER BY id DESC").fetchall()
    return render_template('admin.html', pending_users=pending_users, all_requests=all_requests)

@app.route('/superadmin')
def superadmin():
    db = get_db()
    all_employees = db.execute("SELECT * FROM employees").fetchall()
    all_users = db.execute("SELECT * FROM users").fetchall()
    return render_template('superadmin.html', employees=all_employees, users=all_users)

@app.route('/toggle_emp/<int:emp_id>/<int:current_status>')
def toggle_emp(emp_id, current_status):
    new_status = 1 if current_status == 0 else 0
    db = get_db()
    db.execute("UPDATE employees SET is_active = ? WHERE id = ?", (new_status, emp_id))
    db.commit()
    return redirect(url_for('superadmin'))

@app.route('/reset_emp_password/<int:emp_id>')
def reset_emp_password(emp_id):
    db = get_db()
    db.execute("UPDATE employees SET password = ? WHERE id = ?", (generate_password_hash('123456'), emp_id))
    db.commit()
    return redirect(url_for('superadmin'))

@app.route('/reset_user_password/<int:user_id>')
def reset_user_password(user_id):
    db = get_db()
    db.execute("UPDATE users SET password = ? WHERE id = ?", (generate_password_hash('123456'), user_id))
    db.commit()
    return redirect(url_for('superadmin'))

@app.route('/update/<int:req_id>', methods=['POST'])
@emp_login_required
def update_status(req_id):
    status = request.form.get('status')
    file = request.files.get('receipt')
    filename = None

    if file and file.filename != '':
        if not allowed_file(file.filename):
            return abort(400, "نوع الملف غير مسموح.")
        safe_name = make_unique_filename(file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
        file.save(save_path)
        filename = safe_name

    db = get_db()
    if filename:
        db.execute("UPDATE transfer_requests SET status = ?, receipt_filename = ? WHERE id = ?", (status, filename, req_id))
    else:
        db.execute("UPDATE transfer_requests SET status = ? WHERE id = ?", (status, req_id))
    db.commit()

    return redirect(url_for('admin_panel'))

@app.route('/emp_logout')
def emp_logout():
    session.pop('emp_id', None)
    session.pop('emp_name', None)
    return redirect(url_for('emp_login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    # Flask send_from_directory يتعامل مع الإجراءات الآمنة، لكن نستخدم secure_filename عند الحفظ.
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=False)

# ----- نقطة الدخول للتشغيل المحلي -----
if __name__ == '__main__':
    # للتشغيل المحلي فقط. في الإنتاج استخدم gunicorn أو Docker.
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)), debug=bool(os.getenv('FLASK_DEBUG', False)))

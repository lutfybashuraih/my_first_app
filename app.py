from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# احصل على SECRET_KEY من متغيرات البيئة وإلا استخدم قيمة افتراضية (غير مخصصة للإنتاج)
app.secret_key = os.environ.get('SECRET_KEY', 'bensafy_secret_key_2026')

# التأكد من وجود مجلد للإيصالات
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# إنشاء قاعدة البيانات والجداول تلقائياً
def init_db():
    conn = sqlite3.connect('system.db')
    cursor = conn.cursor()
    
    # جدول العملاء
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        phone TEXT UNIQUE,
                        password TEXT,
                        verified INTEGER DEFAULT 0)''')
    
    # جدول الموظفين
    cursor.execute('''CREATE TABLE IF NOT EXISTS employees (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        emp_account TEXT UNIQUE,
                        password TEXT,
                        active INTEGER DEFAULT 1)''')
    
    # جدول الحوالات والطلبات
    cursor.execute('''CREATE TABLE IF NOT EXISTS requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        network TEXT,
                        target_account TEXT,
                        user_id INTEGER,
                        user_name TEXT,
                        amount REAL,
                        currency TEXT,
                        status TEXT DEFAULT 'قيد الانتظار',
                        receipt TEXT,
                        phone TEXT,
                        emp_id INTEGER,
                        emp_name TEXT,
                        claimed_by TEXT)''')
    
    # جدول المدير العام
    cursor.execute('''CREATE TABLE IF NOT EXISTS superadmin (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE,
                        password TEXT)''')
    
    # إنشاء حساب المدير الافتراضي (المستخدم: admin, كلمة المرور: 123456)
    cursor.execute("INSERT OR IGNORE INTO superadmin (id, username, password) VALUES (1, 'admin', '123456')")
    
    conn.commit()
    conn.close()

init_db()

# --- مسارات العملاء ---
@app.route("/")
def home():
    return render_template('index.html', page='login')

@app.route("/register_page")
def register_page(): 
    return render_template('index.html', page='register')

@app.route("/login_page")
def login_page(): 
    return render_template('index.html', page='login')

@app.route("/register", methods=['POST'])
def register():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '')

    if not (name and phone and password):
        return render_template('index.html', page='register', error="الرجاء ملء كل الحقول")

    hashed = generate_password_hash(password)
    try:
        conn = sqlite3.connect('system.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name, phone, password, verified) VALUES (?, ?, ?, 1)", (name, phone, hashed))
        conn.commit()
        conn.close()
        return redirect(url_for('login_page'))
    except sqlite3.IntegrityError:
        return render_template('index.html', page='register', error="رقم الهاتف مسجل مسبقاً!")

@app.route("/login", methods=['POST'])
def login():
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '')

    if not (phone and password):
        return render_template('index.html', page='login', error="الرجاء ملء كل الحقول")

    conn = sqlite3.connect('system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE phone=?", (phone,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user[3], password):
        session['user_id'] = user[0]
        session['user_name'] = user[1]
        return redirect(url_for('dashboard'))
    else:
        return render_template('index.html', page='login', error="خطأ في بيانات الدخول!")

@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    conn = sqlite3.connect('system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM requests WHERE user_id=?", (session['user_id'],))
    user_requests = cursor.fetchall()
    conn.close()
    
    return render_template('index.html', page='dashboard', user_requests=user_requests)

@app.route("/send", methods=['POST'])
def send_request():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    network = request.form.get('network', '').strip()
    target_account = request.form.get('target_account', '').strip()
    amount = request.form.get('amount', '0')
    currency = request.form.get('currency', '').strip()

    try:
        amount_val = float(amount)
    except ValueError:
        return render_template('index.html', page='dashboard', error="المبلغ غير صالح")

    conn = sqlite3.connect('system.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO requests (network, target_account, user_id, user_name, amount, currency) VALUES (?, ?, ?, ?, ?, ?)",
                   (network, target_account, session['user_id'], session['user_name'], amount_val, currency))
    conn.commit()
    conn.close()
    
    return redirect(url_for('dashboard'))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# --- مسارات الموظفين ---
@app.route("/employees")
def emp_login_page(): 
    return render_template('emp_login.html')

@app.route("/admin")
def admin_dashboard():
    conn = sqlite3.connect('system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM requests")
    all_requests = cursor.fetchall()
    conn.close()
    return render_template('admin.html', all_requests=all_requests)

# --- مسارات المدير العام (SuperAdmin) ---
@app.route("/superadmin")
def superadmin_login(): 
    return render_template('superadmin_login.html')

@app.route("/superadmin_dashboard")
def superadmin_dashboard():
    conn = sqlite3.connect('system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()
    conn.close()
    return render_template('superadmin_dashboard.html', employees=employees)

@app.route("/superadmin_logout")
def superadmin_logout(): 
    return redirect(url_for('superadmin_login'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

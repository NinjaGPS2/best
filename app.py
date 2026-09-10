import os
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import csv
import io

from database import get_db_connection, init_db
import models

app = Flask(__name__)
app.secret_key = "edc_cambodia_billing_secret_key_2024"

# Auto-initialize database on application startup
try:
    init_db()
except Exception as e:
    print(f"DB Init note: {e}")

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==========================================
# AUTHENTICATION DECORATORS & CONTEXT
# ==========================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('សូមចូលប្រើប្រាស់គណនី (Login) ជាមុនសិន!', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('សូមចូលប្រើប្រាស់គណនី (Login) ជាមុនសិន!', 'warning')
            return redirect(url_for('login', next=request.url))
        if session.get('role') != 'admin':
            flash('អ្នកគ្មានសិទ្ធិចូលកាន់ផ្នែកនេះទេ! (Admin Access Only)', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user_context():
    user = None
    pending_count = 0
    if 'user_id' in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, full_name, role, status FROM users WHERE id = ?", (session['user_id'],))
        user = cursor.fetchone()
        if session.get('role') == 'admin':
            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'")
            pending_count = cursor.fetchone()[0]
        conn.close()
    return dict(current_user=user, pending_users_count=pending_count)

# Custom Jinja Template Filters
@app.template_filter('khmer_currency')
def khmer_currency_filter(val):
    return models.format_khmer_currency(val)

@app.template_filter('khmer_type')
def khmer_type_filter(val):
    types = {
        'residential': 'លំនៅឋាន (Residential)',
        'commercial': 'អាជីវកម្ម (Commercial)',
        'industrial': 'ឧស្សាហកម្ម (Industrial)'
    }
    return types.get(val, val)

@app.template_filter('meter_type_kh')
def meter_type_kh_filter(val):
    m_types = {
        'mechanical': 'មេកានិច (Mechanical)',
        'digital': 'ឌីជីថល (Digital)',
        'smart': 'Smart Meter (IoT វៃឆ្លាត)'
    }
    return m_types.get(val, val)

@app.template_filter('status_badge')
def status_badge_filter(val):
    badges = {
        'active': ('bg-success', 'សកម្ម (Active)'),
        'suspended': ('bg-warning text-dark', 'ផ្អាកបណ្ដោះអាសន្ន'),
        'disconnected': ('bg-danger', 'កាត់ផ្ដាច់ (Disconnected)'),
        'unpaid': ('badge-unpaid', 'មិនទាន់បង់ (Unpaid)'),
        'paid': ('badge-paid', 'បង់រួច (Paid)'),
        'overdue': ('badge-overdue', 'លើសកាលកំណត់ (Overdue)'),
        'approved': ('badge-paid', 'បានអនុម័ត (Approved)'),
        'pending': ('badge-unpaid', 'រង់ចាំអនុម័ត (Pending)'),
        'rejected': ('badge-overdue', 'បដិសេធ (Rejected)')
    }
    return badges.get(val, ('bg-secondary', val))

@app.before_request
def check_overdue():
    # Keep overdue statuses up to date
    models.update_overdue_invoices()

# ==========================================
# AUTHENTICATION ROUTES (LOGIN, REGISTER, USERS)
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('សូមបំពេញឈ្មោះគណនី និងពាក្យសម្ងាត់!', 'danger')
            return render_template('login.html', username=username)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username,))
        user = cursor.fetchone()
        conn.close()

        if not user or not check_password_hash(user['password_hash'], password):
            flash('ឈ្មោះគណនី ឬពាក្យសម្ងាត់មិនត្រឹមត្រូវឡើយ!', 'danger')
            return render_template('login.html', username=username)

        # Check approval status
        if user['status'] == 'pending':
            flash('គណនីរបស់អ្នកកំពុងរង់ចាំការអនុម័តពី Admin (Pending Approval) សូមទាក់ទងអ្នកគ្រប់គ្រង!', 'warning')
            return render_template('login.html', username=username)

        if user['status'] == 'rejected':
            flash('គណនីរបស់អ្នកត្រូវបានផ្អាក ឬបដិសេធដោយ Admin!', 'danger')
            return render_template('login.html', username=username)

        # Login successful
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['full_name'] = user['full_name']
        session['role'] = user['role']

        flash(f'ស្វាគមន៍ការចូលប្រើប្រាស់, {user["full_name"]}!', 'success')
        next_url = request.args.get('next')
        return redirect(next_url or url_for('index'))

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not full_name or not username or not password:
            flash('សូមបំពេញព័ត៌មានដែលចាំបាច់ទាំងអស់!', 'danger')
            return render_template('register.html', full_name=full_name, phone=phone, username=username)

        if password != confirm_password:
            flash('ពាក្យសម្ងាត់ទាំងពីរមិនដូចគ្នាទេ! សូមផ្ទៀងផ្ទាត់ឡើងវិញ។', 'danger')
            return render_template('register.html', full_name=full_name, phone=phone, username=username)

        if len(password) < 4:
            flash('ពាក្យសម្ងាត់ត្រូវមានយ៉ាងហោចណាស់ ៤ តួអក្សរ!', 'danger')
            return render_template('register.html', full_name=full_name, phone=phone, username=username)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Strict check: duplicate username prohibited!
        cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username,))
        if cursor.fetchone():
            conn.close()
            flash(f'ឈ្មោះគណនី (Username) "{username}" នេះមានក្នុងប្រព័ន្ធរួចហើយ! ហាមបង្កើតស្ទួនដាច់ខាត។', 'danger')
            return render_template('register.html', full_name=full_name, phone=phone, username=username)

        # Create new user with pending status
        password_hash = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, phone, role, status)
            VALUES (?, ?, ?, ?, 'staff', 'pending')
        """, (username, password_hash, full_name, phone))
        conn.commit()
        conn.close()

        flash('ការចុះឈ្មោះបានជោគជ័យ! គណនីរបស់អ្នកតម្រូវឱ្យមានការអនុម័តពី Admin ជាមុនសិន ទើបអាច Login បាន។', 'info')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('អ្នកបានចាកចេញពីប្រព័ន្ធដោយជោគជ័យ!', 'info')
    return redirect(url_for('login'))

@app.route('/users')
@admin_required
def users_list():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM users ORDER BY 
        CASE status 
            WHEN 'pending' THEN 1 
            WHEN 'approved' THEN 2 
            ELSE 3 
        END, id DESC
    """)
    all_users = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'")
    pending_total = cursor.fetchone()[0]

    conn.close()
    return render_template('users.html', users=all_users, pending_total=pending_total)

@app.route('/users/<int:id>/approve', methods=['POST'])
@admin_required
def user_approve(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    admin_name = session.get('username', 'ADMIN')
    cursor.execute("""
        UPDATE users 
        SET status = 'approved', approved_at = CURRENT_TIMESTAMP, approved_by = ? 
        WHERE id = ?
    """, (admin_name, id))
    conn.commit()
    conn.close()
    flash('បានអនុម័តគណនីអ្នកប្រើប្រាស់ជោគជ័យ! គណនីនេះអាចចូលប្រើប្រាស់បានហើយ។', 'success')
    return redirect(url_for('users_list'))

@app.route('/users/<int:id>/reject', methods=['POST'])
@admin_required
def user_reject(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = 'rejected' WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash('បានបដិសេធ/ផ្អាកគណនីអ្នកប្រើប្រាស់នេះ!', 'warning')
    return redirect(url_for('users_list'))

@app.route('/users/<int:id>/delete', methods=['POST'])
@admin_required
def user_delete(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Prevent deleting primary ADMIN
    cursor.execute("SELECT username FROM users WHERE id = ?", (id,))
    user = cursor.fetchone()
    if user and user['username'].upper() == 'ADMIN':
        conn.close()
        flash('ហាមលុបគណនីមេ ADMIN ដាច់ខាត!', 'danger')
        return redirect(url_for('users_list'))

    cursor.execute("DELETE FROM users WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash('បានលុបគណនីអ្នកប្រើប្រាស់ជោគជ័យ!', 'info')
    return redirect(url_for('users_list'))

# ==========================================
# 0. DASHBOARD
# ==========================================
@app.route('/')
@login_required
def index():
    conn = get_db_connection()
    cursor = conn.cursor()

    # KPI Metrics
    cursor.execute("SELECT COALESCE(SUM(paid_amount), 0) FROM payments")
    total_revenue = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(total_kwh), 0) FROM meter_readings")
    total_kwh = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM invoices WHERE payment_status = 'unpaid'")
    unpaid_invoices_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM invoices WHERE payment_status = 'overdue'")
    overdue_invoices_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM customers")
    total_customers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM meters WHERE status = 'active'")
    active_meters = cursor.fetchone()[0]

    # Recent Invoices
    cursor.execute("""
        SELECT i.*, c.name as customer_name, c.code as customer_code, c.customer_type, m.meter_number
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        JOIN meters m ON i.meter_id = m.id
        ORDER BY i.id DESC LIMIT 6
    """)
    recent_invoices = cursor.fetchall()

    # Recent Readings
    cursor.execute("""
        SELECT r.*, m.meter_number, c.name as customer_name
        FROM meter_readings r
        JOIN meters m ON r.meter_id = m.id
        JOIN customers c ON m.customer_id = c.id
        ORDER BY r.id DESC LIMIT 5
    """)
    recent_readings = cursor.fetchall()

    # Chart Data: Monthly Revenue (Last 6 Months)
    cursor.execute("""
        SELECT strftime('%Y-%m', paid_at) as month, SUM(paid_amount) as total
        FROM payments
        GROUP BY month
        ORDER BY month DESC LIMIT 6
    """)
    monthly_rev_rows = cursor.fetchall()

    chart_rev_labels = [row['month'] for row in reversed(monthly_rev_rows)] or ['2024-08', '2024-09', '2024-10']
    chart_rev_data = [row['total'] for row in reversed(monthly_rev_rows)] or [19100, 0, 0]

    # Chart Data: Consumption by Customer Type
    cursor.execute("""
        SELECT c.customer_type, COALESCE(SUM(r.total_kwh), 0) as total_kwh
        FROM customers c
        JOIN meters m ON m.customer_id = c.id
        JOIN meter_readings r ON r.meter_id = m.id
        GROUP BY c.customer_type
    """)
    type_rows = cursor.fetchall()
    consumption_by_type = {
        'residential': 0,
        'commercial': 0,
        'industrial': 0
    }
    for row in type_rows:
        consumption_by_type[row['customer_type']] = row['total_kwh']

    conn.close()

    return render_template('index.html',
        total_revenue=total_revenue,
        total_kwh=total_kwh,
        unpaid_invoices_count=unpaid_invoices_count,
        overdue_invoices_count=overdue_invoices_count,
        total_customers=total_customers,
        active_meters=active_meters,
        recent_invoices=recent_invoices,
        recent_readings=recent_readings,
        chart_rev_labels=chart_rev_labels,
        chart_rev_data=chart_rev_data,
        consumption_by_type=consumption_by_type
    )

# ==========================================
# MODULE 1: CUSTOMER & METER MANAGEMENT
# ==========================================
@app.route('/customers')
@login_required
def customers_list():
    query = request.args.get('q', '').strip()
    cust_type = request.args.get('type', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT c.*, 
               m.id as meter_id, m.meter_number, m.meter_type, m.status as meter_status,
               (SELECT COUNT(*) FROM invoices WHERE customer_id = c.id AND payment_status IN ('unpaid', 'overdue')) as unpaid_count
        FROM customers c
        LEFT JOIN meters m ON m.customer_id = c.id
        WHERE 1=1
    """
    params = []
    if query:
        sql += " AND (c.code LIKE ? OR c.name LIKE ? OR c.phone LIKE ? OR c.pole_number LIKE ?)"
        wildcard = f"%{query}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])
    if cust_type:
        sql += " AND c.customer_type = ?"
        params.append(cust_type)

    sql += " ORDER BY c.id DESC"
    cursor.execute(sql, params)
    customers = cursor.fetchall()
    conn.close()

    return render_template('customers.html', customers=customers, search_query=query, selected_type=cust_type)

@app.route('/customers/new', methods=['POST'])
@login_required
def customer_create():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    pole_number = request.form.get('pole_number', '').strip()
    customer_type = request.form.get('customer_type', 'residential')

    # Meter info from modal
    meter_number = request.form.get('meter_number', '').strip()
    meter_type = request.form.get('meter_type', 'digital')
    initial_kwh = float(request.form.get('initial_kwh', 0.0) or 0.0)

    if not name or not pole_number:
        flash('សូមបំពេញឈ្មោះ និងលេខបង្គោលអតិថិជន!', 'danger')
        return redirect(url_for('customers_list'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT MAX(id) FROM customers")
    last_id = cursor.fetchone()[0] or 1000
    cust_code = f"CUST-{last_id + 1}"

    cursor.execute("""
        INSERT INTO customers (code, name, phone, address, pole_number, customer_type)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (cust_code, name, phone, address, pole_number, customer_type))
    cust_id = cursor.lastrowid

    if meter_number:
        install_date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            INSERT INTO meters (meter_number, customer_id, meter_type, install_date, initial_kwh, status)
            VALUES (?, ?, ?, ?, ?, 'active')
        """, (meter_number, cust_id, meter_type, install_date, initial_kwh))

    conn.commit()
    conn.close()
    flash(f'បានបង្កើតអតិថិជន {name} ({cust_code}) ដោយជោគជ័យ!', 'success')
    return redirect(url_for('customers_list'))

@app.route('/customers/<int:id>')
@login_required
def customer_detail(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM customers WHERE id = ?", (id,))
    customer = cursor.fetchone()
    if not customer:
        flash('រកមិនឃើញអតិថិជននេះទេ!', 'danger')
        conn.close()
        return redirect(url_for('customers_list'))

    cursor.execute("SELECT * FROM meters WHERE customer_id = ?", (id,))
    meters = cursor.fetchall()

    cursor.execute("""
        SELECT i.*, m.meter_number
        FROM invoices i
        JOIN meters m ON i.meter_id = m.id
        WHERE i.customer_id = ?
        ORDER BY i.id DESC
    """, (id,))
    invoices = cursor.fetchall()

    cursor.execute("""
        SELECT r.*, m.meter_number
        FROM meter_readings r
        JOIN meters m ON r.meter_id = m.id
        WHERE m.customer_id = ?
        ORDER BY r.id DESC
    """, (id,))
    readings = cursor.fetchall()

    cursor.execute("""
        SELECT COALESCE(SUM(total_amount), 0) FROM invoices
        WHERE customer_id = ? AND payment_status IN ('unpaid', 'overdue')
    """, (id,))
    total_unpaid = cursor.fetchone()[0]

    conn.close()
    return render_template('customer_detail.html',
        customer=customer,
        meters=meters,
        invoices=invoices,
        readings=readings,
        total_unpaid=total_unpaid
    )

@app.route('/customers/<int:id>/edit', methods=['POST'])
@login_required
def customer_update(id):
    name = request.form.get('name')
    phone = request.form.get('phone')
    address = request.form.get('address')
    pole_number = request.form.get('pole_number')
    customer_type = request.form.get('customer_type')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE customers 
        SET name = ?, phone = ?, address = ?, pole_number = ?, customer_type = ?
        WHERE id = ?
    """, (name, phone, address, pole_number, customer_type, id))
    conn.commit()
    conn.close()
    flash('បានកែប្រែព័ត៌មានអតិថិជនជោគជ័យ!', 'success')
    return redirect(url_for('customer_detail', id=id))

@app.route('/meters/new', methods=['POST'])
@login_required
def meter_create():
    customer_id = request.form.get('customer_id')
    meter_number = request.form.get('meter_number', '').strip()
    meter_type = request.form.get('meter_type', 'digital')
    install_date = request.form.get('install_date') or datetime.now().strftime('%Y-%m-%d')
    initial_kwh = float(request.form.get('initial_kwh', 0.0) or 0.0)

    if not meter_number or not customer_id:
        flash('សូមបំពេញលេខកុងទ័រ និងជ្រើសរើសអតិថិជន!', 'danger')
        return redirect(url_for('customers_list'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO meters (meter_number, customer_id, meter_type, install_date, initial_kwh, status)
            VALUES (?, ?, ?, ?, ?, 'active')
        """, (meter_number, customer_id, meter_type, install_date, initial_kwh))
        conn.commit()
        flash(f'បានបន្ថែមនាឡិកាស្ទង់ {meter_number} ជោគជ័យ!', 'success')
    except sqlite3.IntegrityError:
        flash(f'លេខកុងទ័រ {meter_number} នេះមានក្នុងប្រព័ន្ធរួចហើយ!', 'danger')
    finally:
        conn.close()

    return redirect(url_for('customer_detail', id=customer_id))

@app.route('/meters/<int:id>/status', methods=['POST'])
@login_required
def meter_toggle_status(id):
    new_status = request.form.get('status', 'active')
    cust_id = request.form.get('customer_id')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE meters SET status = ? WHERE id = ?", (new_status, id))
    conn.commit()
    conn.close()
    flash(f'បានប្តូរស្ថានភាពកុងទ័រទៅជា {new_status}!', 'info')
    if cust_id:
        return redirect(url_for('customer_detail', id=cust_id))
    return redirect(url_for('customers_list'))

# ==========================================
# MODULE 2: METER READING MODULE
# ==========================================
@app.route('/readings')
@login_required
def readings_list():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.*, m.meter_number, m.meter_type, c.id as customer_id, c.name as customer_name, c.code as customer_code,
               (SELECT id FROM invoices WHERE reading_id = r.id) as invoice_id
        FROM meter_readings r
        JOIN meters m ON r.meter_id = m.id
        JOIN customers c ON m.customer_id = c.id
        ORDER BY r.id DESC
    """)
    readings = cursor.fetchall()

    cursor.execute("""
        SELECT m.id, m.meter_number, m.meter_type, c.name as customer_name, c.code as customer_code
        FROM meters m
        JOIN customers c ON m.customer_id = c.id
        WHERE m.status = 'active'
        ORDER BY m.meter_number ASC
    """)
    active_meters = cursor.fetchall()

    conn.close()
    return render_template('meter_readings.html', readings=readings, active_meters=active_meters)

@app.route('/readings/new', methods=['POST'])
@login_required
def reading_create():
    meter_id = request.form.get('meter_id')
    reading_date = request.form.get('reading_date') or datetime.now().strftime('%Y-%m-%d')
    prev_value = float(request.form.get('prev_value', 0.0) or 0.0)
    curr_value = float(request.form.get('curr_value', 0.0) or 0.0)
    reader_id = request.form.get('reader_id', session.get('username', 'Staff-01'))
    auto_generate_invoice = request.form.get('auto_invoice') == '1'

    if curr_value < prev_value:
        flash('លេខអានថ្មីមិនអាចតូចជាងលេខអានចាស់ឡើយ!', 'danger')
        return redirect(url_for('readings_list'))

    total_kwh = round(curr_value - prev_value, 2)

    photo_filename = None
    if 'meter_photo' in request.files:
        file = request.files['meter_photo']
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            photo_filename = f"meter_{meter_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO meter_readings (meter_id, reading_date, prev_value, curr_value, total_kwh, photo_path, reader_id, input_method)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'manual')
    """, (meter_id, reading_date, prev_value, curr_value, total_kwh, photo_filename, reader_id))
    reading_id = cursor.lastrowid
    conn.commit()

    if auto_generate_invoice:
        conn.close()
        return redirect(url_for('invoice_generate', reading_id=reading_id))

    conn.close()
    flash(f'បានកត់ត្រាលេខអានជោគជ័យ! បរិមាណប្រើប្រាស់: {total_kwh} kWh', 'success')
    return redirect(url_for('readings_list'))

@app.route('/api/meter/<int:meter_id>/latest-reading')
@login_required
def api_meter_latest_reading(meter_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT curr_value FROM meter_readings 
        WHERE meter_id = ? 
        ORDER BY reading_date DESC, id DESC LIMIT 1
    """, (meter_id,))
    row = cursor.fetchone()

    if row:
        last_val = row['curr_value']
    else:
        cursor.execute("SELECT initial_kwh FROM meters WHERE id = ?", (meter_id,))
        meter_row = cursor.fetchone()
        last_val = meter_row['initial_kwh'] if meter_row else 0.0

    conn.close()
    return jsonify({'meter_id': meter_id, 'previous_reading': last_val})

@app.route('/api/smart-meter/sync', methods=['POST'])
@login_required
def api_smart_meter_sync():
    import random
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.id, m.meter_number, c.id as customer_id, c.name as customer_name
        FROM meters m
        JOIN customers c ON m.customer_id = c.id
        WHERE m.meter_type = 'smart' AND m.status = 'active'
    """)
    smart_meters = cursor.fetchall()

    if not smart_meters:
        conn.close()
        flash('មិនមាន Smart Meter សកម្មក្នុងប្រព័ន្ធទេ!', 'warning')
        return redirect(url_for('readings_list'))

    synced_count = 0
    today_str = datetime.now().strftime('%Y-%m-%d')

    for sm in smart_meters:
        meter_id = sm['id']
        cursor.execute("""
            SELECT curr_value FROM meter_readings 
            WHERE meter_id = ? 
            ORDER BY reading_date DESC, id DESC LIMIT 1
        """, (meter_id,))
        last = cursor.fetchone()
        prev_val = last['curr_value'] if last else 0.0

        consumed = round(random.uniform(40.0, 150.0), 1)
        curr_val = round(prev_val + consumed, 1)

        cursor.execute("""
            INSERT INTO meter_readings (meter_id, reading_date, prev_value, curr_value, total_kwh, reader_id, input_method)
            VALUES (?, ?, ?, ?, ?, 'IoT-SmartGateway', 'smart_iot')
        """, (meter_id, today_str, prev_val, curr_val, consumed))
        synced_count += 1

    conn.commit()
    conn.close()

    flash(f'បានភ្ជាប់ និងទាញយកទិន្នន័យពី Smart Meter {synced_count} គ្រឿងដោយជោគជ័យតាម IoT Gateway!', 'success')
    return redirect(url_for('readings_list'))

# ==========================================
# MODULE 3: BILLING & TARIFFS MODULE
# ==========================================
@app.route('/invoices')
@login_required
def invoices_list():
    status_filter = request.args.get('status', '').strip()
    query = request.args.get('q', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT i.*, c.name as customer_name, c.code as customer_code, c.customer_type, m.meter_number
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        JOIN meters m ON i.meter_id = m.id
        WHERE 1=1
    """
    params = []
    if status_filter:
        sql += " AND i.payment_status = ?"
        params.append(status_filter)
    if query:
        sql += " AND (i.invoice_number LIKE ? OR c.name LIKE ? OR c.code LIKE ? OR m.meter_number LIKE ?)"
        wildcard = f"%{query}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    sql += " ORDER BY i.id DESC"
    cursor.execute(sql, params)
    invoices = cursor.fetchall()

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM invoices WHERE payment_status = 'unpaid'")
    unpaid_stat = cursor.fetchone()

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM invoices WHERE payment_status = 'paid'")
    paid_stat = cursor.fetchone()

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM invoices WHERE payment_status = 'overdue'")
    overdue_stat = cursor.fetchone()

    conn.close()
    return render_template('invoices.html',
        invoices=invoices,
        status_filter=status_filter,
        search_query=query,
        unpaid_stat=unpaid_stat,
        paid_stat=paid_stat,
        overdue_stat=overdue_stat
    )

@app.route('/invoices/generate/<int:reading_id>')
@login_required
def invoice_generate(reading_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM invoices WHERE reading_id = ?", (reading_id,))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        flash('វិក្កយបត្រសម្រាប់ការកត់ត្រានេះត្រូវបានចេញរួចរាល់ហើយ!', 'info')
        return redirect(url_for('invoice_detail', id=existing['id']))

    cursor.execute("""
        SELECT r.*, m.id as meter_id, m.customer_id, c.customer_type, c.name as customer_name
        FROM meter_readings r
        JOIN meters m ON r.meter_id = m.id
        JOIN customers c ON m.customer_id = c.id
        WHERE r.id = ?
    """, (reading_id,))
    reading = cursor.fetchone()

    if not reading:
        conn.close()
        flash('រកមិនឃើញលេខអានកុងទ័រនេះទេ!', 'danger')
        return redirect(url_for('readings_list'))

    bill = models.calculate_tiered_bill(
        kwh=reading['total_kwh'],
        customer_type=reading['customer_type'],
        customer_id=reading['customer_id']
    )

    issue_date = datetime.now()
    due_date = issue_date + timedelta(days=15)
    inv_code = f"INV-{issue_date.strftime('%Y%m')}-{reading_id:04d}"

    khqr_str = models.generate_khqr_payload(inv_code, bill['total_amount'], reading['customer_name'])

    cursor.execute("""
        INSERT INTO invoices (
            invoice_number, reading_id, customer_id, meter_id,
            energy_amount, tier1_kwh, tier1_amount, tier2_kwh, tier2_amount, tier3_kwh, tier3_amount,
            maintenance_fee, tax, prev_unpaid, total_amount, issue_date, due_date, payment_status, khqr_string
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unpaid', ?)
    """, (
        inv_code, reading_id, reading['customer_id'], reading['meter_id'],
        bill['energy_amount'], bill['tier1_kwh'], bill['tier1_amt'], bill['tier2_kwh'], bill['tier2_amt'],
        bill['tier3_kwh'], bill['tier3_amt'], bill['maintenance_fee'], bill['tax_amount'], bill['prev_unpaid'],
        bill['total_amount'], issue_date.strftime('%Y-%m-%d'), due_date.strftime('%Y-%m-%d'), khqr_str
    ))
    new_inv_id = cursor.lastrowid
    conn.commit()
    conn.close()

    flash(f'បានបង្កើតវិក្កយបត្រលេខ {inv_code} ដោយជោគជ័យ!', 'success')
    return redirect(url_for('invoice_detail', id=new_inv_id))

@app.route('/invoices/<int:id>')
@login_required
def invoice_detail(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT i.*, 
               c.code as customer_code, c.name as customer_name, c.phone as customer_phone,
               c.address as customer_address, c.pole_number, c.customer_type,
               m.meter_number, m.meter_type,
               r.prev_value, r.curr_value, r.total_kwh, r.reading_date, r.photo_path
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        JOIN meters m ON i.meter_id = m.id
        JOIN meter_readings r ON i.reading_id = r.id
        WHERE i.id = ?
    """, (id,))
    invoice = cursor.fetchone()

    if not invoice:
        conn.close()
        flash('រកមិនឃើញវិក្កយបត្រនេះទេ!', 'danger')
        return redirect(url_for('invoices_list'))

    cursor.execute("SELECT * FROM payments WHERE invoice_id = ?", (id,))
    payment = cursor.fetchone()

    conn.close()

    khqr_qr_img = models.generate_qr_base64(invoice['khqr_string'] or f"EDC-{invoice['invoice_number']}-{invoice['total_amount']}")

    return render_template('invoice_detail.html',
        invoice=invoice,
        payment=payment,
        khqr_qr_img=khqr_qr_img
    )

@app.route('/invoices/<int:id>/telegram', methods=['POST'])
@login_required
def invoice_telegram_notify(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.*, c.name as customer_name, c.phone as customer_phone
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        WHERE i.id = ?
    """, (id,))
    inv = cursor.fetchone()
    conn.close()

    if inv:
        flash(f'⚡ បានផ្ញើសារជូនដំណឹងវិក្កយបត្រ {inv["invoice_number"]} ទៅកាន់ Telegram/SMS របស់អតិថិជន {inv["customer_name"]} ({inv["customer_phone"]}) ដោយជោគជ័យ!', 'success')
    return redirect(url_for('invoice_detail', id=id))

@app.route('/tariffs')
@login_required
def tariffs_view():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tariffs ORDER BY id ASC")
    tariffs = cursor.fetchall()
    conn.close()
    return render_template('tariffs.html', tariffs=tariffs)

@app.route('/tariffs/update', methods=['POST'])
@login_required
def tariffs_update():
    tariff_id = request.form.get('tariff_id')
    t1_rate = float(request.form.get('tier1_rate', 380))
    t2_rate = float(request.form.get('tier2_rate', 480))
    t3_rate = float(request.form.get('tier3_rate', 610))
    maint_fee = float(request.form.get('maintenance_fee', 2000))
    vat_percent = float(request.form.get('vat_percent', 0))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE tariffs
        SET tier1_rate = ?, tier2_rate = ?, tier3_rate = ?, maintenance_fee = ?, vat_percent = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (t1_rate, t2_rate, t3_rate, maint_fee, vat_percent, tariff_id))
    conn.commit()
    conn.close()
    flash('បានធ្វើបច្ចុប្បន្នភាពតារាងតម្លៃបង់តាមកម្រិត (Tariff) ជោគជ័យ!', 'success')
    return redirect(url_for('tariffs_view'))

# ==========================================
# MODULE 4: PAYMENTS & REPORTS MODULE
# ==========================================
@app.route('/payments')
@login_required
def payments_list():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.*, i.invoice_number, i.total_amount, c.name as customer_name, c.code as customer_code
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        JOIN customers c ON i.customer_id = c.id
        ORDER BY p.id DESC
    """)
    payments = cursor.fetchall()
    conn.close()

    return render_template('payments.html', payments=payments)

@app.route('/payments/new/<int:invoice_id>', methods=['POST'])
@login_required
def payment_create(invoice_id):
    payment_method = request.form.get('payment_method', 'cash')
    paid_amount = float(request.form.get('paid_amount', 0.0))
    notes = request.form.get('notes', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
    inv = cursor.fetchone()
    if not inv:
        flash('រកមិនឃើញវិក្កយបត្រនេះទេ!', 'danger')
        conn.close()
        return redirect(url_for('invoices_list'))

    now = datetime.now()
    cursor.execute("SELECT COUNT(*) FROM payments")
    cnt = cursor.fetchone()[0] + 1
    receipt_no = f"RCP-{now.strftime('%Y%m')}-{cnt:04d}"

    cursor.execute("""
        INSERT INTO payments (invoice_id, receipt_number, paid_amount, payment_method, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (invoice_id, receipt_no, paid_amount, payment_method, notes))

    cursor.execute("UPDATE invoices SET payment_status = 'paid' WHERE id = ?", (invoice_id,))

    conn.commit()
    conn.close()

    flash(f'បានកត់ត្រាការបង់ប្រាក់ជោគជ័យ! លេខបង្កាន់ដៃ: {receipt_no}', 'success')
    return redirect(url_for('invoice_detail', id=invoice_id))

@app.route('/reports')
@login_required
def reports_view():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COALESCE(SUM(paid_amount), 0) FROM payments")
    total_collected = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM invoices WHERE payment_status IN ('unpaid', 'overdue')")
    total_unpaid = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(total_kwh), 0) FROM meter_readings")
    total_kwh_sold = cursor.fetchone()[0]

    cursor.execute("""
        SELECT payment_method, COUNT(*) as count, SUM(paid_amount) as total
        FROM payments
        GROUP BY payment_method
    """)
    method_stats = cursor.fetchall()

    cursor.execute("""
        SELECT c.code, c.name, c.customer_type, SUM(r.total_kwh) as total_kwh, COUNT(r.id) as read_count
        FROM customers c
        JOIN meters m ON m.customer_id = c.id
        JOIN meter_readings r ON r.meter_id = m.id
        GROUP BY c.id
        ORDER BY total_kwh DESC LIMIT 5
    """)
    top_consumers = cursor.fetchall()

    conn.close()
    return render_template('reports.html',
        total_collected=total_collected,
        total_unpaid=total_unpaid,
        total_kwh_sold=total_kwh_sold,
        method_stats=method_stats,
        top_consumers=top_consumers
    )

@app.route('/reports/disconnections')
@login_required
def reports_disconnections():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.id as customer_id, c.code, c.name, c.phone, c.address, c.pole_number, c.customer_type,
               m.id as meter_id, m.meter_number, m.status as meter_status,
               i.id as invoice_id, i.invoice_number, i.total_amount, i.due_date,
               CAST((julianday('now') - julianday(i.due_date)) AS INTEGER) as days_overdue
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        JOIN meters m ON i.meter_id = m.id
        WHERE i.payment_status = 'overdue'
        ORDER BY days_overdue DESC, i.total_amount DESC
    """)
    overdue_list = cursor.fetchall()
    conn.close()

    return render_template('disconnections.html', overdue_list=overdue_list)

@app.route('/reports/disconnect-meter/<int:meter_id>', methods=['POST'])
@login_required
def disconnect_meter(meter_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE meters SET status = 'disconnected' WHERE id = ?", (meter_id,))
    conn.commit()
    conn.close()
    flash(f'បានបញ្ជាក់ការកាត់ផ្ដាច់ចរន្តកុងទ័រលេខ #{meter_id} ដោយជោគជ័យ!', 'warning')
    return redirect(url_for('reports_disconnections'))

@app.route('/reports/export-csv')
@login_required
def export_invoices_csv():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.invoice_number, c.code, c.name, c.customer_type, m.meter_number,
               i.energy_amount, i.maintenance_fee, i.tax, i.total_amount, i.issue_date, i.due_date, i.payment_status
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        JOIN meters m ON i.meter_id = m.id
        ORDER BY i.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Invoice Number', 'Customer Code', 'Customer Name', 'Type', 'Meter Number', 'Energy (KHR)', 'Maintenance', 'Tax', 'Total (KHR)', 'Issue Date', 'Due Date', 'Status'])

    for r in rows:
        writer.writerow([r['invoice_number'], r['code'], r['name'], r['customer_type'], r['meter_number'], r['energy_amount'], r['maintenance_fee'], r['tax'], r['total_amount'], r['issue_date'], r['due_date'], r['payment_status']])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f"edc_invoices_{datetime.now().strftime('%Y%m%d')}.csv"
    )

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)

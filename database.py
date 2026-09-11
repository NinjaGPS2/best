import sqlite3
import os
from datetime import datetime, timedelta
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "edc_billing.db"))

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Customers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        phone TEXT,
        address TEXT NOT NULL,
        pole_number TEXT NOT NULL,
        customer_type TEXT NOT NULL CHECK(customer_type IN ('residential', 'commercial', 'industrial')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. Electric Meters Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meter_number TEXT UNIQUE NOT NULL,
        customer_id INTEGER,
        meter_type TEXT NOT NULL CHECK(meter_type IN ('mechanical', 'digital', 'smart')),
        install_date DATE NOT NULL,
        initial_kwh REAL DEFAULT 0.0,
        status TEXT DEFAULT 'active' CHECK(status IN ('active', 'suspended', 'disconnected')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE SET NULL
    )
    """)

    # 3. Meter Readings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meter_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meter_id INTEGER NOT NULL,
        reading_date DATE NOT NULL,
        prev_value REAL NOT NULL,
        curr_value REAL NOT NULL,
        total_kwh REAL NOT NULL,
        photo_path TEXT,
        reader_id TEXT DEFAULT 'Staff-01',
        input_method TEXT DEFAULT 'manual' CHECK(input_method IN ('manual', 'smart_iot')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (meter_id) REFERENCES meters (id) ON DELETE CASCADE
    )
    """)

    # 4. Tariffs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tariffs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_type TEXT UNIQUE NOT NULL CHECK(customer_type IN ('residential', 'commercial', 'industrial')),
        tier1_max REAL DEFAULT 50.0,
        tier1_rate REAL DEFAULT 380.0,
        tier2_max REAL DEFAULT 100.0,
        tier2_rate REAL DEFAULT 480.0,
        tier3_rate REAL DEFAULT 610.0,
        maintenance_fee REAL DEFAULT 2000.0,
        vat_percent REAL DEFAULT 0.0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 5. Invoices Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number TEXT UNIQUE NOT NULL,
        reading_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        meter_id INTEGER NOT NULL,
        energy_amount REAL NOT NULL,
        tier1_kwh REAL DEFAULT 0.0,
        tier1_amount REAL DEFAULT 0.0,
        tier2_kwh REAL DEFAULT 0.0,
        tier2_amount REAL DEFAULT 0.0,
        tier3_kwh REAL DEFAULT 0.0,
        tier3_amount REAL DEFAULT 0.0,
        maintenance_fee REAL DEFAULT 2000.0,
        tax REAL DEFAULT 0.0,
        prev_unpaid REAL DEFAULT 0.0,
        total_amount REAL NOT NULL,
        issue_date DATE NOT NULL,
        due_date DATE NOT NULL,
        payment_status TEXT DEFAULT 'unpaid' CHECK(payment_status IN ('unpaid', 'paid', 'overdue')),
        khqr_string TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (reading_id) REFERENCES meter_readings (id) ON DELETE CASCADE,
        FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE,
        FOREIGN KEY (meter_id) REFERENCES meters (id) ON DELETE CASCADE
    )
    """)

    # 6. Payments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        receipt_number TEXT UNIQUE NOT NULL,
        paid_amount REAL NOT NULL,
        payment_method TEXT NOT NULL CHECK(payment_method IN ('cash', 'khqr_bakong')),
        paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        notes TEXT,
        FOREIGN KEY (invoice_id) REFERENCES invoices (id) ON DELETE CASCADE
    )
    """)

    # 7. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        phone TEXT,
        role TEXT DEFAULT 'staff' CHECK(role IN ('admin', 'staff')),
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        approved_at TIMESTAMP,
        approved_by TEXT
    )
    """)

    conn.commit()
    seed_default_data(conn)
    conn.close()

def seed_default_data(conn):
    from werkzeug.security import generate_password_hash
    cursor = conn.cursor()

    # Seed Default Admin if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'ADMIN'")
    if not cursor.fetchone():
        admin_pass = generate_password_hash('12345@')
        cursor.execute("""
        INSERT INTO users (username, password_hash, full_name, phone, role, status, approved_at, approved_by)
        VALUES ('ADMIN', ?, 'អភិបាលប្រព័ន្ធ (System Admin)', '012 888 999', 'admin', 'approved', CURRENT_TIMESTAMP, 'SYSTEM')
        """, (admin_pass,))

    # Seed Default Tariffs if empty
    cursor.execute("SELECT COUNT(*) FROM tariffs")
    if cursor.fetchone()[0] == 0:
        tariffs = [
            ('residential', 50.0, 380.0, 100.0, 480.0, 610.0, 2000.0, 0.0),
            ('commercial',  50.0, 450.0, 100.0, 600.0, 740.0, 3000.0, 10.0),
            ('industrial',  50.0, 500.0, 100.0, 650.0, 790.0, 5000.0, 10.0),
        ]
        cursor.executemany("""
        INSERT INTO tariffs (customer_type, tier1_max, tier1_rate, tier2_max, tier2_rate, tier3_rate, maintenance_fee, vat_percent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, tariffs)

    # Seed Customers if empty
    cursor.execute("SELECT COUNT(*) FROM customers")
    if cursor.fetchone()[0] == 0:
        sample_customers = [
            ('CUST-1001', 'សុខ ចាន់ដារា (Sok Chandara)', '012 889 771', 'ផ្ទះលេខ ១២A ផ្លូវ ២៧១ សង្កាត់បឹងទំពុន ខណ្ឌមានជ័យ ភ្នំពេញ', 'P-042/MN', 'residential'),
            ('CUST-1002', 'កែវ សោភា (Keo Sophea)', '098 445 123', 'ផ្ទះលេខ ៨៨ ផ្លូវ ៥៩៨ សង្កាត់ទួលសង្កែ ខណ្ឌឫស្សីកែវ ភ្នំពេញ', 'P-118/RS', 'residential'),
            ('CUST-1003', 'ហេង វិសាល (Heng Visal - ហាងកាហ្វេ)', '077 234 567', 'ផ្ទះលេខ ៤៥ ផ្លូវ ៣១០ សង្កាត់បឹងកេងកង១ ខណ្ឌបឹងកេងកង ភ្នំពេញ', 'P-073/BKK', 'commercial'),
            ('CUST-1004', 'ម៉ៅ រ៉ានី (Mao Rany - សិប្បកម្មដែក)', '085 990 011', 'ដីឡូត៍ ៧B ផ្លូវជាតិលេខ ៤ សង្កាត់ចោមចៅ ខណ្ឌពោធិ៍សែនជ័យ ភ្នំពេញ', 'P-205/PC', 'industrial'),
            ('CUST-1005', 'ឡាយ គឹមសួរ (Lay Kimsour)', '010 334 892', 'ផ្ទះលេខ ២៤ ផ្លូវ ១៩៨៦ សង្កាត់ភ្នំពេញថ្មី ខណ្ឌសែនសុខ ភ្នំពេញ', 'P-089/SS', 'residential'),
            ('CUST-1006', 'ជា សុវណ្ណារិទ្ធ (Chea Sovannarith)', '015 678 901', 'ផ្ទះលេខ ៥៦ ផ្លូវ ៦០ម៉ែត្រ សង្កាត់ចាក់អង្រែក្រោម ខណ្ឌមានជ័យ ភ្នំពេញ', 'P-310/MN', 'residential'),
        ]
        cursor.executemany("""
        INSERT INTO customers (code, name, phone, address, pole_number, customer_type)
        VALUES (?, ?, ?, ?, ?, ?)
        """, sample_customers)

        # Seed Meters for these customers
        meters = [
            ('MTR-2024-8801', 1, 'digital', '2023-01-15', 0.0, 'active'),
            ('MTR-2024-8802', 2, 'mechanical', '2022-06-20', 120.0, 'active'),
            ('MTR-2024-8803', 3, 'smart', '2023-11-01', 0.0, 'active'),
            ('MTR-2024-8804', 4, 'smart', '2023-08-10', 500.0, 'active'),
            ('MTR-2024-8805', 5, 'digital', '2024-01-05', 0.0, 'active'),
            ('MTR-2024-8806', 6, 'mechanical', '2023-03-12', 40.0, 'suspended'),
        ]
        cursor.executemany("""
        INSERT INTO meters (meter_number, customer_id, meter_type, install_date, initial_kwh, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """, meters)

        # Seed initial Readings & Invoices
        now = datetime.now()
        last_month = now - timedelta(days=30)
        two_months_ago = now - timedelta(days=60)

        # Reading 1 for CUST-1001 (Residential: 45 kWh - Tier 1)
        cursor.execute("""
        INSERT INTO meter_readings (meter_id, reading_date, prev_value, curr_value, total_kwh, reader_id, input_method)
        VALUES (1, ?, 100.0, 145.0, 45.0, 'Staff-01', 'manual')
        """, (two_months_ago.strftime('%Y-%m-%d'),))
        r1_id = cursor.lastrowid

        # Invoice 1 (Paid)
        cursor.execute("""
        INSERT INTO invoices (invoice_number, reading_id, customer_id, meter_id, energy_amount, tier1_kwh, tier1_amount, tier2_kwh, tier2_amount, tier3_kwh, tier3_amount, maintenance_fee, tax, prev_unpaid, total_amount, issue_date, due_date, payment_status)
        VALUES ('INV-202408-001', ?, 1, 1, 17100.0, 45.0, 17100.0, 0, 0, 0, 0, 2000.0, 0, 0, 19100.0, ?, ?, 'paid')
        """, (r1_id, two_months_ago.strftime('%Y-%m-%d'), (two_months_ago + timedelta(days=15)).strftime('%Y-%m-%d')))
        inv1_id = cursor.lastrowid

        cursor.execute("""
        INSERT INTO payments (invoice_id, receipt_number, paid_amount, payment_method, paid_at, notes)
        VALUES (?, 'RCP-202408-001', 19100.0, 'khqr_bakong', ?, 'ទូទាត់ជោគជ័យតាម Bakong KHQR')
        """, (inv1_id, (two_months_ago + timedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S')))

        # Reading 2 for CUST-1001 (Residential: 95 kWh - Tier 1 + Tier 2)
        cursor.execute("""
        INSERT INTO meter_readings (meter_id, reading_date, prev_value, curr_value, total_kwh, reader_id, input_method)
        VALUES (1, ?, 145.0, 240.0, 95.0, 'Staff-01', 'manual')
        """, (last_month.strftime('%Y-%m-%d'),))
        r2_id = cursor.lastrowid

        cursor.execute("""
        INSERT INTO invoices (invoice_number, reading_id, customer_id, meter_id, energy_amount, tier1_kwh, tier1_amount, tier2_kwh, tier2_amount, tier3_kwh, tier3_amount, maintenance_fee, tax, prev_unpaid, total_amount, issue_date, due_date, payment_status)
        VALUES ('INV-202409-001', ?, 1, 1, 40600.0, 50.0, 19000.0, 45.0, 21600.0, 0, 0, 2000.0, 0, 0, 42600.0, ?, ?, 'unpaid')
        """, (r2_id, last_month.strftime('%Y-%m-%d'), (last_month + timedelta(days=15)).strftime('%Y-%m-%d')))

        # Reading 3 for CUST-1002 (Residential: 180 kWh - Tier 1, Tier 2, Tier 3 - OVERDUE!)
        overdue_date = now - timedelta(days=45)
        due_date_overdue = overdue_date + timedelta(days=14)
        cursor.execute("""
        INSERT INTO meter_readings (meter_id, reading_date, prev_value, curr_value, total_kwh, reader_id, input_method)
        VALUES (2, ?, 250.0, 430.0, 180.0, 'Staff-02', 'manual')
        """, (overdue_date.strftime('%Y-%m-%d'),))
        r3_id = cursor.lastrowid

        # 50*380=19000, 50*480=24000, 80*610=48800 -> Total energy = 91800 + 2000 = 93800
        cursor.execute("""
        INSERT INTO invoices (invoice_number, reading_id, customer_id, meter_id, energy_amount, tier1_kwh, tier1_amount, tier2_kwh, tier2_amount, tier3_kwh, tier3_amount, maintenance_fee, tax, prev_unpaid, total_amount, issue_date, due_date, payment_status)
        VALUES ('INV-202408-002', ?, 2, 2, 91800.0, 50.0, 19000.0, 50.0, 24000.0, 80.0, 48800.0, 2000.0, 0, 0, 93800.0, ?, ?, 'overdue')
        """, (r3_id, overdue_date.strftime('%Y-%m-%d'), due_date_overdue.strftime('%Y-%m-%d')))

        # Reading 4 for CUST-1003 (Commercial Cafe: 350 kWh - Smart IoT)
        cursor.execute("""
        INSERT INTO meter_readings (meter_id, reading_date, prev_value, curr_value, total_kwh, reader_id, input_method)
        VALUES (3, ?, 1200.0, 1550.0, 350.0, 'IoT-SmartMeter', 'smart_iot')
        """, (now.strftime('%Y-%m-%d'),))
        r4_id = cursor.lastrowid

        # Commercial Tariffs: Tier1 50*450=22500, Tier2 50*600=30000, Tier3 250*740=185000 -> Energy = 237500. Maintenance = 3000. Tax (10%) = 24050. Total = 264550.
        cursor.execute("""
        INSERT INTO invoices (invoice_number, reading_id, customer_id, meter_id, energy_amount, tier1_kwh, tier1_amount, tier2_kwh, tier2_amount, tier3_kwh, tier3_amount, maintenance_fee, tax, prev_unpaid, total_amount, issue_date, due_date, payment_status)
        VALUES ('INV-202410-001', ?, 3, 3, 237500.0, 50.0, 22500.0, 50.0, 30000.0, 250.0, 185000.0, 3000.0, 24050.0, 0, 264550.0, ?, ?, 'unpaid')
        """, (r4_id, now.strftime('%Y-%m-%d'), (now + timedelta(days=15)).strftime('%Y-%m-%d')))

    conn.commit()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully with seed data.")

"""مدير قاعدة البيانات السحابية - Cloud DB Manager"""
import psycopg2
import psycopg2.extras
from datetime import datetime
from config import CLOUD_CONFIG

class CloudDB:
    """اتصال PostgreSQL السحابي مع إعادة المحاولة"""

    def __init__(self):
        self.conn = None
        self.enabled = CLOUD_CONFIG.get("enabled", False)

    def connect(self):
        if not self.enabled:
            return False
        try:
            self.conn = psycopg2.connect(
                host=CLOUD_CONFIG["host"],
                port=CLOUD_CONFIG["port"],
                database=CLOUD_CONFIG["database"],
                user=CLOUD_CONFIG["user"],
                password=CLOUD_CONFIG["password"],
                sslmode=CLOUD_CONFIG.get("sslmode", "require")
            )
            self.conn.autocommit = False
            return True
        except Exception as e:
            print(f"[Cloud] Connection failed: {e}")
            return False

    def ensure_tables(self):
        """إنشاء الجداول السحابية إذا لم تكن موجودة"""
        if not self.conn:
            return
        cur = self.conn.cursor()

        tables = [
            """CREATE TABLE IF NOT EXISTS medicines (
                id SERIAL PRIMARY KEY,
                barcode VARCHAR(100) UNIQUE,
                name VARCHAR(255) NOT NULL,
                scientific_name VARCHAR(255),
                quantity INTEGER DEFAULT 0,
                min_limit INTEGER DEFAULT 0,
                expiry_date DATE,
                purchase_price DECIMAL(10,2) DEFAULT 0,
                selling_price DECIMAL(10,2) DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sync_id VARCHAR(50) UNIQUE
            )""",
            """CREATE TABLE IF NOT EXISTS invoices (
                id SERIAL PRIMARY KEY,
                invoice_number VARCHAR(100) UNIQUE NOT NULL,
                invoice_date TIMESTAMP NOT NULL,
                total_amount DECIMAL(10,2) DEFAULT 0,
                currency VARCHAR(10) DEFAULT 'YER',
                created_by VARCHAR(100),
                patient_id INTEGER,
                doctor_id INTEGER,
                sync_id VARCHAR(50) UNIQUE
            )""",
            """CREATE TABLE IF NOT EXISTS invoice_lines (
                id SERIAL PRIMARY KEY,
                invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
                medicine_id INTEGER,
                qty INTEGER NOT NULL,
                unit_price DECIMAL(10,2) NOT NULL,
                line_total DECIMAL(10,2) NOT NULL,
                dosage_instruction TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS returns (
                id SERIAL PRIMARY KEY,
                return_number VARCHAR(100) UNIQUE NOT NULL,
                return_date TIMESTAMP NOT NULL,
                invoice_id INTEGER,
                total_amount DECIMAL(10,2) DEFAULT 0,
                created_by VARCHAR(100)
            )""",
            """CREATE TABLE IF NOT EXISTS return_lines (
                id SERIAL PRIMARY KEY,
                return_id INTEGER REFERENCES returns(id) ON DELETE CASCADE,
                medicine_id INTEGER,
                qty INTEGER NOT NULL,
                unit_price DECIMAL(10,2) NOT NULL,
                line_total DECIMAL(10,2) NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'cashier'
            )""",
            """CREATE TABLE IF NOT EXISTS doctors (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                specialty VARCHAR(255),
                phone VARCHAR(50)
            )""",
            """CREATE TABLE IF NOT EXISTS patients (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                age INTEGER,
                gender VARCHAR(10),
                phone VARCHAR(50),
                visits_count INTEGER DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS sync_log (
                id SERIAL PRIMARY KEY,
                table_name VARCHAR(50),
                record_id INTEGER,
                action VARCHAR(20),
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20),
                error_msg TEXT
            )"""
        ]

        for sql in tables:
            cur.execute(sql)
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

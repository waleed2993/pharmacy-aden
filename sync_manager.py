"""مدير المزامنة الهجين - Hybrid Sync Manager"""
import sqlite3
import threading
import time
from datetime import datetime
from config import SYNC_CONFIG, DB_FILE
from cloud_db import CloudDB

class SyncManager:
    """يدير المزامنة بين SQLite المحلي و PostgreSQL السحابي"""

    def __init__(self, local_conn):
        self.local_conn = local_conn
        self.cloud = CloudDB()
        self.running = False
        self.thread = None
        self.last_sync = None

    def start_auto_sync(self):
        """بدء المزامنة التلقائية في خلفية"""
        if not SYNC_CONFIG["auto_sync"] or not self.cloud.enabled:
            return False
        self.running = True
        self.thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.running = False

    def _sync_loop(self):
        interval = SYNC_CONFIG["sync_interval_minutes"] * 60
        while self.running:
            try:
                self.sync_all()
            except Exception as e:
                print(f"[Sync] Error: {e}")
            time.sleep(interval)

    def sync_all(self):
        """مزامنة جميع الجداول"""
        if not self.cloud.connect():
            return False

        try:
            self.cloud.ensure_tables()
            self._sync_medicines()
            self._sync_invoices()
            self._sync_doctors()
            self._sync_patients()
            self._sync_users()
            self.last_sync = datetime.now()
            print(f"[Sync] Completed at {self.last_sync}")
            return True
        except Exception as e:
            print(f"[Sync] Failed: {e}")
            return False
        finally:
            self.cloud.close()

    def _sync_medicines(self):
        """مزامنة الأدوية"""
        local = self.local_conn.execute("SELECT * FROM medicines WHERE updated_at > ? OR updated_at IS NULL", 
                                       (self.last_sync.isoformat() if self.last_sync else '1970-01-01',)).fetchall()
        cur = self.cloud.conn.cursor()
        for row in local:
            cur.execute("""
                INSERT INTO medicines (barcode, name, scientific_name, quantity, min_limit, 
                                       expiry_date, purchase_price, selling_price, sync_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sync_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    quantity = EXCLUDED.quantity,
                    selling_price = EXCLUDED.selling_price,
                    updated_at = CURRENT_TIMESTAMP
            """, (row["barcode"], row["name"], row["scientific_name"], row["quantity"],
                  row["min_limit"], row["expiry_date"], row["purchase_price"], 
                  row["selling_price"], f"med_{row['id']}"))
        self.cloud.conn.commit()

    def _sync_invoices(self):
        """مزامنة الفواتير"""
        local = self.local_conn.execute("""
            SELECT * FROM invoices 
            WHERE invoice_date > ? OR invoice_date IS NULL
        """, (self.last_sync.isoformat() if self.last_sync else '1970-01-01',)).fetchall()
        cur = self.cloud.conn.cursor()
        for row in local:
            cur.execute("""
                INSERT INTO invoices (invoice_number, invoice_date, total_amount, currency,
                                     created_by, patient_id, doctor_id, sync_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sync_id) DO NOTHING
            """, (row["invoice_number"], row["invoice_date"], row["total_amount"],
                  row["currency"], row["created_by"], row["patient_id"], 
                  row["doctor_id"], f"inv_{row['id']}"))
        self.cloud.conn.commit()

    def _sync_doctors(self):
        local = self.local_conn.execute("SELECT * FROM doctors").fetchall()
        cur = self.cloud.conn.cursor()
        for row in local:
            cur.execute("""
                INSERT INTO doctors (id, name, specialty, phone)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    specialty = EXCLUDED.specialty,
                    phone = EXCLUDED.phone
            """, (row["id"], row["name"], row["specialty"], row["phone"]))
        self.cloud.conn.commit()

    def _sync_patients(self):
        local = self.local_conn.execute("SELECT * FROM patients").fetchall()
        cur = self.cloud.conn.cursor()
        for row in local:
            cur.execute("""
                INSERT INTO patients (id, name, age, gender, phone, visits_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    age = EXCLUDED.age,
                    visits_count = EXCLUDED.visits_count
            """, (row["id"], row["name"], row["age"], row["gender"], row["phone"], row["visits_count"]))
        self.cloud.conn.commit()

    def _sync_users(self):
        local = self.local_conn.execute("SELECT * FROM users").fetchall()
        cur = self.cloud.conn.cursor()
        for row in local:
            cur.execute("""
                INSERT INTO users (id, username, password, role)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    password = EXCLUDED.password,
                    role = EXCLUDED.role
            """, (row["id"], row["username"], row["password"], row["role"]))
        self.cloud.conn.commit()

    def get_sync_status(self):
        """حالة المزامنة الحالية"""
        return {
            "enabled": self.cloud.enabled,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "auto_sync": SYNC_CONFIG["auto_sync"],
            "interval_minutes": SYNC_CONFIG["sync_interval_minutes"]
        }

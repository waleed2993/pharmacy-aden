import sqlite3
import os
from datetime import datetime, timedelta
from pharmacy_db import DB_FILE, ensure_dirs, backup_db
from config import CURRENCY

class DB:
    def __init__(self, dbfile=DB_FILE):
        self.dbfile = dbfile
        self.conn = None
        self._connect_and_migrate()

    def _connect_and_migrate(self):
        ensure_dirs()
        backup_db("pre_migrate")
        db_dir = os.path.dirname(self.dbfile) or "."
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        self.conn = sqlite3.connect(self.dbfile, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode = WAL")
            cur.execute("PRAGMA busy_timeout = 10000")
            cur.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.OperationalError:
            try:
                cur.execute("PRAGMA journal_mode = DELETE")
                cur.execute("PRAGMA busy_timeout = 5000")
            except:
                pass
        cur.execute("PRAGMA foreign_keys = ON")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS medicines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE,
                name TEXT NOT NULL,
                scientific_name TEXT DEFAULT NULL,
                quantity INTEGER DEFAULT 0 CHECK(quantity >= 0),
                min_limit INTEGER DEFAULT 0 CHECK(min_limit >= 0),
                expiry_date TEXT,
                purchase_price REAL DEFAULT 0.0 CHECK(purchase_price >= 0),
                selling_price REAL DEFAULT 0.0 CHECK(selling_price >= 0),
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                invoice_date TEXT NOT NULL,
                total_amount REAL DEFAULT 0.0,
                currency TEXT DEFAULT 'YER',
                created_by TEXT DEFAULT 'user',
                patient_id INTEGER DEFAULT NULL,
                doctor_id INTEGER DEFAULT NULL
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS invoice_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                medicine_id INTEGER NOT NULL,
                qty INTEGER NOT NULL CHECK(qty > 0),
                unit_price REAL NOT NULL CHECK(unit_price >= 0),
                line_total REAL NOT NULL,
                dosage_instruction TEXT DEFAULT NULL
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                return_number TEXT UNIQUE NOT NULL,
                return_date TEXT NOT NULL,
                invoice_id INTEGER NOT NULL,
                total_amount REAL DEFAULT 0.0,
                created_by TEXT DEFAULT 'user'
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS return_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                return_id INTEGER NOT NULL,
                medicine_id INTEGER NOT NULL,
                qty INTEGER NOT NULL CHECK(qty > 0),
                unit_price REAL NOT NULL,
                line_total REAL NOT NULL
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'cashier' CHECK(role IN ('admin','cashier'))
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                specialty TEXT,
                phone TEXT
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER,
                gender TEXT,
                phone TEXT,
                visits_count INTEGER DEFAULT 0
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS medical_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                doctor_id INTEGER,
                visit_date TEXT NOT NULL,
                diagnosis TEXT,
                notes TEXT
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS license (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                activation_code TEXT,
                activated_at TEXT,
                expiry_date TEXT,
                is_activated INTEGER DEFAULT 0
            )""")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_med_barcode ON medicines(barcode)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_med_name ON medicines(name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_date ON invoices(invoice_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_number ON invoices(invoice_number)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_il_invoice ON invoice_lines(invoice_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rtn_invoice ON returns(invoice_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pat_name ON patients(name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_doc_name ON doctors(name)")

        cur.execute("SELECT COUNT(*) as c FROM users WHERE username='admin'")
        if cur.fetchone()["c"] == 0:
            cur.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")

        self.conn.commit()

    def check_license(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM license WHERE id = 1")
        lic = cur.fetchone()
        if not lic:
            return False, "البرنامج غير مُفعّل"
        if not lic["is_activated"]:
            return False, "البرنامج غير مُفعّل"
        try:
            expiry = datetime.strptime(lic["expiry_date"], "%Y-%m-%d")
            if datetime.now() > expiry:
                return False, f"انتهت صلاحية التفعيل بتاريخ: {lic['expiry_date']}"
            days_left = (expiry - datetime.now()).days
            return True, f"مُفعّل حتى: {lic['expiry_date']} (متبقي {days_left} يوم)"
        except:
            return False, "تاريخ التفعيل غير صالح"

    def activate_license(self, code):
        VALID_CODE = "Ko736692158"
        if code.strip() != VALID_CODE:
            return False, "كود التفعيل غير صحيح"
        cur = self.conn.cursor()
        expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        cur.execute("""
            INSERT OR REPLACE INTO license (id, activation_code, activated_at, expiry_date, is_activated)
            VALUES (1, ?, ?, ?, 1)
        """, (code.strip(), datetime.now().isoformat(), expiry))
        self.conn.commit()
        return True, f"تم التفعيل بنجاح! صالح حتى: {expiry}"

    def close(self):
        try:
            if self.conn:
                self.conn.close()
        except:
            pass

    def check_login(self, username, password):
        cur = self.conn.cursor()
        cur.execute("SELECT id, username, role FROM users WHERE username=? AND password=?", (username, password))
        return cur.fetchone()

    def list_all_users(self):
        return self.conn.execute("SELECT id, username, role FROM users ORDER BY id DESC").fetchall()

    def add_or_update_user(self, username, password, role):
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM users WHERE username=?", (username,))
        r = cur.fetchone()
        if r:
            cur.execute("UPDATE users SET password=?, role=? WHERE username=?", (password, role, username))
        else:
            cur.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
        self.conn.commit()

    def delete_user(self, user_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM users WHERE id=?", (user_id,))
        self.conn.commit()

    def add_or_update_medicine(self, barcode, name, scientific_name, qty, min_limit, expiry_date, purchase_price, selling_price):
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM medicines WHERE barcode=?", (barcode,))
        r = cur.fetchone()
        sci_val = scientific_name.strip() if (scientific_name and scientific_name.strip()) else None
        if r:
            cur.execute("""UPDATE medicines SET name=?, scientific_name=?, quantity=?, min_limit=?, expiry_date=?, purchase_price=?, selling_price=?, updated_at=CURRENT_TIMESTAMP WHERE barcode=?""",
                        (name, sci_val, qty, min_limit, expiry_date, purchase_price, selling_price, barcode))
            mid = r["id"]
        else:
            cur.execute("""INSERT INTO medicines (barcode,name,scientific_name,quantity,min_limit,expiry_date,purchase_price,selling_price) VALUES (?,?,?,?,?,?,?,?)""",
                        (barcode, name, sci_val, qty, min_limit, expiry_date, purchase_price, selling_price))
            mid = cur.lastrowid
        self.conn.commit()
        return mid

    def get_medicine_by_id(self, med_id):
        return self.conn.execute("SELECT * FROM medicines WHERE id=?", (med_id,)).fetchone()

    def get_medicine_by_barcode(self, barcode):
        return self.conn.execute("SELECT * FROM medicines WHERE barcode=?", (barcode,)).fetchone()

    def search_medicines(self, q, limit=50):
        qlike = f"%{q}%"
        return self.conn.execute("""
            SELECT id,barcode,name,scientific_name,quantity,selling_price,expiry_date,min_limit 
            FROM medicines 
            WHERE name LIKE ? OR scientific_name LIKE ? OR barcode LIKE ? 
            ORDER BY name LIMIT ?""", (qlike, qlike, qlike, limit)).fetchall()

    def list_medicines(self):
        return self.conn.execute("SELECT * FROM medicines ORDER BY id DESC").fetchall()

    def delete_medicine(self, medicine_id):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM invoice_lines WHERE medicine_id=?", (medicine_id,))
        if cur.fetchone()["cnt"] > 0:
            return False, "لا يمكن الحذف: الدواء مرتبط بفواتير سابقة"
        cur.execute("DELETE FROM medicines WHERE id=?", (medicine_id,))
        self.conn.commit()
        return True, "تم الحذف بنجاح"

    def get_low_stock_medicines(self):
        return self.conn.execute("""
            SELECT id, barcode, name, quantity, min_limit 
            FROM medicines 
            WHERE quantity <= min_limit AND min_limit > 0
            ORDER BY quantity ASC""").fetchall()

    def get_near_expiry(self, days=30):
        cutoff = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        return self.conn.execute("""
            SELECT id, barcode, name, expiry_date 
            FROM medicines 
            WHERE expiry_date IS NOT NULL AND expiry_date <= ? AND expiry_date >= ?
            ORDER BY expiry_date ASC""", (cutoff, today)).fetchall()

    def get_expired_medicines(self):
        today = datetime.now().strftime("%Y-%m-%d")
        return self.conn.execute("""
            SELECT id, barcode, name, expiry_date 
            FROM medicines 
            WHERE expiry_date IS NOT NULL AND expiry_date < ?
            ORDER BY expiry_date ASC""", (today,)).fetchall()

    def add_doctor(self, name, specialty, phone):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO doctors (name, specialty, phone) VALUES (?, ?, ?)", (name, specialty, phone))
        self.conn.commit()
        return cur.lastrowid

    def list_doctors(self):
        return self.conn.execute("SELECT * FROM doctors ORDER BY name ASC").fetchall()

    def update_doctor(self, doc_id, name, specialty, phone):
        cur = self.conn.cursor()
        cur.execute("UPDATE doctors SET name=?, specialty=?, phone=? WHERE id=?", (name, specialty, phone, doc_id))
        self.conn.commit()

    def delete_doctor(self, doc_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM doctors WHERE id=?", (doc_id,))
        self.conn.commit()

    def add_patient(self, name, age, gender, phone):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO patients (name, age, gender, phone, visits_count) VALUES (?, ?, ?, ?, 0)", (name, age, gender, phone))
        self.conn.commit()
        return cur.lastrowid

    def list_patients(self):
        return self.conn.execute("SELECT * FROM patients ORDER BY name ASC").fetchall()

    def update_patient(self, pat_id, name, age, gender, phone):
        cur = self.conn.cursor()
        cur.execute("UPDATE patients SET name=?, age=?, gender=?, phone=? WHERE id=?", (name, age, gender, phone, pat_id))
        self.conn.commit()

    def delete_patient(self, pat_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM patients WHERE id=?", (pat_id,))
        cur.execute("DELETE FROM medical_records WHERE patient_id=?", (pat_id,))
        self.conn.commit()

    def add_medical_record(self, patient_id, doctor_id, diagnosis, notes):
        cur = self.conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur.execute("INSERT INTO medical_records (patient_id, doctor_id, visit_date, diagnosis, notes) VALUES (?, ?, ?, ?, ?)", (patient_id, doctor_id, now_str, diagnosis, notes))
        cur.execute("UPDATE patients SET visits_count = visits_count + 1 WHERE id=?", (patient_id,))
        self.conn.commit()

    def get_patient_history(self, patient_id):
        cur = self.conn.cursor()
        records = cur.execute("""
            SELECT mr.*, d.name as doctor_name 
            FROM medical_records mr 
            LEFT JOIN doctors d ON mr.doctor_id = d.id 
            WHERE mr.patient_id=? 
            ORDER BY mr.visit_date DESC""", (patient_id,)).fetchall()
        medicines = cur.execute("""
            SELECT il.qty, il.unit_price, il.dosage_instruction, m.name as med_name, i.invoice_date 
            FROM invoice_lines il 
            JOIN invoices i ON il.invoice_id = i.id 
            JOIN medicines m ON il.medicine_id = m.id 
            WHERE i.patient_id=? 
            ORDER BY i.invoice_date DESC""", (patient_id,)).fetchall()
        return records, medicines

    def save_invoice_clinical(self, invoice_number, items, currency=CURRENCY, created_by="user", patient_id=None, doctor_id=None):
        cur = self.conn.cursor()
        p_id = int(patient_id) if patient_id else None
        d_id = int(doctor_id) if doctor_id else None
        total = sum(i["line_total"] for i in items)
        cur.execute("""
            INSERT INTO invoices (invoice_number, invoice_date, total_amount, currency, created_by, patient_id, doctor_id) 
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (invoice_number, datetime.now().isoformat(), total, currency, created_by, p_id, d_id))
        inv_id = cur.lastrowid
        for it in items:
            cur.execute("""
                INSERT INTO invoice_lines (invoice_id, medicine_id, qty, unit_price, line_total, dosage_instruction) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (inv_id, it["medicine_id"], it["qty"], it["unit_price"], it["line_total"], it.get("dosage_instruction", "")))
            cur.execute("UPDATE medicines SET quantity = quantity - ? WHERE id=?", (it["qty"], it["medicine_id"]))
        if p_id:
            cur.execute("UPDATE patients SET visits_count = visits_count + 1 WHERE id=?", (p_id,))
        self.conn.commit()
        return inv_id

    def list_all_invoices(self):
        return self.conn.execute("""
            SELECT id, invoice_number, invoice_date, total_amount, currency, created_by 
            FROM invoices 
            ORDER BY invoice_date DESC""").fetchall()

    def list_invoices_between(self, start_iso, end_iso):
        return self.conn.execute("""
            SELECT id, invoice_number, invoice_date, total_amount, currency, created_by 
            FROM invoices 
            WHERE invoice_date BETWEEN ? AND ? 
            ORDER BY invoice_date DESC""", (start_iso, end_iso)).fetchall()

    def get_invoice(self, invoice_id):
        inv = self.conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        lines = self.conn.execute("""
            SELECT 
                il.medicine_id,
                il.unit_price,
                il.dosage_instruction,
                m.name,
                m.barcode,
                il.qty as qty,
                il.line_total as line_total
            FROM invoice_lines il
            LEFT JOIN medicines m ON il.medicine_id = m.id
            WHERE il.invoice_id = ?
            ORDER BY il.id
        """, (invoice_id,)).fetchall()
        return inv, lines

    def get_invoice_remaining(self, invoice_id):
        inv = self.conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        lines = self.conn.execute("""
            SELECT 
                il.medicine_id,
                il.unit_price,
                il.dosage_instruction,
                m.name,
                m.barcode,
                il.qty - COALESCE(ret.ret_qty, 0) as remaining_qty,
                il.unit_price * (il.qty - COALESCE(ret.ret_qty, 0)) as line_total
            FROM invoice_lines il
            LEFT JOIN medicines m ON il.medicine_id = m.id
            LEFT JOIN (
                SELECT rl.medicine_id, SUM(rl.qty) as ret_qty
                FROM return_lines rl
                JOIN returns r ON rl.return_id = r.id
                WHERE r.invoice_id = ?
                GROUP BY rl.medicine_id
            ) ret ON ret.medicine_id = il.medicine_id
            WHERE il.invoice_id = ? AND (il.qty - COALESCE(ret.ret_qty, 0)) > 0
            ORDER BY il.id
        """, (invoice_id, invoice_id)).fetchall()
        return inv, lines

    def search_invoice_numbers(self, q, limit=10):
        return self.conn.execute("""
            SELECT id, invoice_number 
            FROM invoices 
            WHERE invoice_number LIKE ? 
            ORDER BY invoice_date DESC 
            LIMIT ?""", (f"%{q}%", limit)).fetchall()

    def has_return_for_invoice(self, invoice_id):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM returns WHERE invoice_id=?", (invoice_id,))
        return cur.fetchone()["cnt"] > 0

    def get_invoice_line_by_barcode(self, invoice_id, barcode):
        return self.conn.execute("""
            SELECT il.*, m.barcode 
            FROM invoice_lines il
            JOIN medicines m ON il.medicine_id = m.id
            WHERE il.invoice_id=? AND m.barcode=?""", (invoice_id, barcode)).fetchone()

    def create_return_full(self, invoice_id, created_by="user"):
        if self.has_return_for_invoice(invoice_id):
            return None
        cur = self.conn.cursor()
        _, lines = self.get_invoice(invoice_id)
        valid_lines = [l for l in lines if l["qty"] > 0]
        if not valid_lines:
            return None
        total = sum(r["line_total"] for r in valid_lines)
        rtnno = f"RET-{datetime.now().strftime('%Y%m%d')}-{int(datetime.now().timestamp())%10000}"
        cur.execute("""
            INSERT INTO returns (return_number, return_date, invoice_id, total_amount, created_by) 
            VALUES (?,?,?,?,?)""", (rtnno, datetime.now().isoformat(), invoice_id, total, created_by))
        rid = cur.lastrowid
        for r in valid_lines:
            cur.execute("""
                INSERT INTO return_lines (return_id, medicine_id, qty, unit_price, line_total) 
                VALUES (?,?,?,?,?)""", (rid, r["medicine_id"], r["qty"], r["unit_price"], r["line_total"]))
            cur.execute("UPDATE medicines SET quantity = quantity + ? WHERE id=?", (r["qty"], r["medicine_id"]))
        self.conn.commit()
        return rid

    def create_return_partial(self, invoice_id, return_items, created_by="user"):
        cur = self.conn.cursor()
        _, remaining_lines = self.get_invoice_remaining(invoice_id)
        remaining_map = {l["medicine_id"]: l["remaining_qty"] for l in remaining_lines}
        items_lines = []
        total = 0.0
        for mid, qty, unit in return_items:
            max_allowed = remaining_map.get(mid, 0)
            if max_allowed <= 0:
                continue
            if qty > max_allowed:
                qty = max_allowed
            if qty <= 0:
                continue
            lt = unit * qty
            items_lines.append((mid, qty, unit, lt))
            total += lt
        if not items_lines:
            return None
        rtnno = f"RET-{datetime.now().strftime('%Y%m%d')}-{int(datetime.now().timestamp())%10000}"
        cur.execute("""
            INSERT INTO returns (return_number, return_date, invoice_id, total_amount, created_by) 
            VALUES (?,?,?,?,?)""", (rtnno, datetime.now().isoformat(), invoice_id, total, created_by))
        rid = cur.lastrowid
        for mid, qty, unit, lt in items_lines:
            cur.execute("""
                INSERT INTO return_lines (return_id, medicine_id, qty, unit_price, line_total) 
                VALUES (?,?,?,?,?)""", (rid, mid, qty, unit, lt))
            cur.execute("UPDATE medicines SET quantity = quantity + ? WHERE id=?", (qty, mid))
        self.conn.commit()
        return rid

    def list_returns(self, search_q=None):
        query = """
            SELECT r.id, r.return_number, r.return_date, i.invoice_number, r.total_amount, r.created_by 
            FROM returns r 
            LEFT JOIN invoices i ON r.invoice_id = i.id"""
        if search_q:
            return self.conn.execute(query + " WHERE i.invoice_number LIKE ? OR r.return_number LIKE ? ORDER BY r.return_date DESC", (f"%{search_q}%", f"%{search_q}%")).fetchall()
        return self.conn.execute(query + " ORDER BY r.return_date DESC").fetchall()

    def get_return_details(self, return_id):
        return self.conn.execute("""
            SELECT rl.*, m.name, m.barcode 
            FROM return_lines rl 
            LEFT JOIN medicines m ON rl.medicine_id = m.id 
            WHERE rl.return_id=?""", (return_id,)).fetchall()

    def calculate_financial_profits(self, start_iso=None, end_iso=None):
        cur = self.conn.cursor()
        if start_iso and end_iso:
            rows = cur.execute("""
                SELECT SUM(il.qty * il.unit_price) as sales, SUM(il.qty * COALESCE(m.purchase_price, 0)) as cost
                FROM invoice_lines il JOIN invoices i ON il.invoice_id = i.id
                LEFT JOIN medicines m ON il.medicine_id = m.id
                WHERE i.invoice_date BETWEEN ? AND ?""", (start_iso, end_iso)).fetchall()
        else:
            rows = cur.execute("""
                SELECT SUM(il.qty * il.unit_price) as sales, SUM(il.qty * COALESCE(m.purchase_price, 0)) as cost
                FROM invoice_lines il LEFT JOIN medicines m ON il.medicine_id = m.id""").fetchall()
        r = rows[0] if rows else {"sales": 0, "cost": 0}
        total_sales = r["sales"] or 0.0
        total_cost = r["cost"] or 0.0
        if start_iso and end_iso:
            ret_rows = cur.execute("""
                SELECT SUM(rl.qty * rl.unit_price) as ret_total, SUM(rl.qty * COALESCE(m.purchase_price, 0)) as ret_cost
                FROM return_lines rl JOIN returns r ON rl.return_id = r.id JOIN invoices i ON r.invoice_id = i.id
                LEFT JOIN medicines m ON rl.medicine_id = m.id
                WHERE i.invoice_date BETWEEN ? AND ?""", (start_iso, end_iso)).fetchall()
        else:
            ret_rows = cur.execute("""
                SELECT SUM(rl.qty * rl.unit_price) as ret_total, SUM(rl.qty * COALESCE(m.purchase_price, 0)) as ret_cost
                FROM return_lines rl JOIN returns r ON rl.return_id = r.id
                LEFT JOIN medicines m ON rl.medicine_id = m.id""").fetchall()
        ret_total = ret_rows[0]["ret_total"] or 0.0 if ret_rows else 0.0
        ret_cost = ret_rows[0]["ret_cost"] or 0.0 if ret_rows else 0.0
        net_sales = total_sales - ret_total
        net_cost = total_cost - ret_cost
        return net_sales, net_cost - ret_cost

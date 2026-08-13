"""إعدادات نظام الصيدلية الهجين - Hybrid Sync Config"""
import os

# === قاعدة البيانات المحلية ===
DB_DIR = "data"
DB_FILE = os.path.join(DB_DIR, "pharmacy_local.db")

# === قاعدة البيانات السحابية (PostgreSQL) ===
# املأ هذه القيم من موفر الاستضافة (Render, Railway, Supabase, إلخ)
CLOUD_CONFIG = {
    "enabled": False,           # True لتفعيل المزامنة السحابية
    "host": "your-db-host.com", # مثال: db.xxx.render.com
    "port": 5432,
    "database": "pharmacy_db",
    "user": "pharmacy_user",
    "password": "your-password",
    "sslmode": "require"
}

# === إعدادات المزامنة ===
SYNC_CONFIG = {
    "auto_sync": True,          # مزامنة تلقائية
    "sync_interval_minutes": 5, # كل 5 دقائق
    "sync_on_startup": True,    # مزامنة عند التشغيل
    "conflict_resolution": "cloud_wins",  # cloud_wins | local_wins | newer_wins
    "batch_size": 100,          # عدد السجلات في كل دفعة
    "retry_attempts": 3,        # محاولات إعادة الاتصال
    "retry_delay_seconds": 10   # التأخير بين المحاولات
}

# === العملة ===
CURRENCY = "YER"
CURRENCY_SYMBOL = {"USD": "$", "EUR": "€", "YER": "ر.ي", "SAR": "ر.س"}

# === المجلدات ===
BACKUP_DIR = "backups"
PDF_DIR = "invoices_pdf"
SYNC_LOG = os.path.join(DB_DIR, "sync_log.db")

def ensure_dirs():
    for d in [DB_DIR, BACKUP_DIR, PDF_DIR]:
        os.makedirs(d, exist_ok=True)

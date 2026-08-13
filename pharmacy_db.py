"""الإعدادات والمساعدات - Pharmacy DB Helpers"""
import os
import sys
import shutil
from datetime import datetime
from config import DB_DIR, BACKUP_DIR, PDF_DIR, ensure_dirs

DB_FILE = os.path.join(DB_DIR, "pharmacy_local.db")

def backup_db(label="auto"):
    ensure_dirs()
    if os.path.exists(DB_FILE):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bname = f"backup_pharmacy_{label}_{ts}.db"
        dest = os.path.join(BACKUP_DIR, bname)
        shutil.copy2(DB_FILE, dest)
        return dest
    return None

def list_backups():
    ensure_dirs()
    backups = []
    if os.path.exists(BACKUP_DIR):
        for fname in sorted(os.listdir(BACKUP_DIR), reverse=True):
            if fname.endswith('.db'):
                fpath = os.path.join(BACKUP_DIR, fname)
                size_mb = round(os.path.getsize(fpath) / (1024*1024), 2)
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y-%m-%d %H:%M:%S')
                backups.append({'name': fname, 'path': fpath, 'size_mb': size_mb, 'date': mtime})
    return backups

def restore_db(backup_path):
    if not os.path.exists(backup_path):
        return False, "ملف النسخة الاحتياطية غير موجود"
    if not backup_path.endswith('.db'):
        return False, "ملف غير صالح"
    try:
        # Create emergency backup of current db before restore
        if os.path.exists(DB_FILE):
            emergency = os.path.join(BACKUP_DIR, f"emergency_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
            shutil.copy2(DB_FILE, emergency)
        shutil.copy2(backup_path, DB_FILE)
        return True, "تمت الاستعادة بنجاح"
    except Exception as e:
        return False, f"فشل الاستعادة: {e}"

def delete_backup(backup_path):
    try:
        if os.path.exists(backup_path):
            os.remove(backup_path)
            return True, "تم الحذف"
        return False, "الملف غير موجود"
    except Exception as e:
        return False, str(e)

def open_file(filename):
    if not os.path.exists(filename):
        return
    if sys.platform == "win32":
        os.startfile(filename)
    elif sys.platform == "darwin":
        os.system(f'open "{filename}"')
    else:
        os.system(f'xdg-open "{filename}"')

def update_database():
    ensure_dirs()

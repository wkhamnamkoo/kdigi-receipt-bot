import sqlite3
from datetime import datetime

DB_PATH = "kdigi_logs.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT,
            user_id         TEXT,
            slip_type       TEXT,
            ref_no          TEXT,
            amount          REAL,
            status          TEXT,
            invoice_no      TEXT,
            ocr_text        TEXT,
            slip_image_b64  TEXT,  -- ✅ เก็บรูปสลิปเป็น Base64 สำหรับทีม Support ดูย้อนหลัง
            resolve_status  TEXT DEFAULT '🔴 รอดำเนินการ'  -- ✅ สถานะการแก้ไขของทีม Support
        )
    """)
    conn.commit()
    conn.close()

def migrate_db():
    """เพิ่ม column ใหม่ให้ DB เก่าค่ะ (safe migration)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("ALTER TABLE logs ADD COLUMN resolve_status TEXT DEFAULT '🔴 รอดำเนินการ'")
        conn.commit()
        conn.close()
        print("✅ migrate_db: เพิ่ม resolve_status column แล้วค่ะ")
    except Exception:
        pass  # column มีอยู่แล้วค่ะ ไม่ต้องทำอะไรค่ะ

def update_resolve_status(log_id: int, resolve_status: str):
    """อัปเดตสถานะการแก้ไขของแต่ละ row ค่ะ"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE logs SET resolve_status=? WHERE id=?", (resolve_status, log_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Update Error: {e}")

def log_to_db(user_id, slip_type="", ref_no="", amount=None, status="", invoice_no="", ocr_text="", slip_image_b64=""):
    """บันทึก log และ return lastrowid ค่ะ"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO logs (timestamp, user_id, slip_type, ref_no, amount, status, invoice_no, ocr_text, slip_image_b64)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, slip_type, ref_no, amount, status, invoice_no, ocr_text, slip_image_b64))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id  # ✅ return log_id เพื่อให้ notify_support ส่ง ?open=log_id 
    except Exception as e:
        print(f"DB Log Error: {e}")
        return None

def update_invoice_no(log_id: int, invoice_no: str):
    """อัปเดต invoice_no หลังทีม Support ส่งใบเสร็จให้ลูกค้าแล้วค่ะ"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE logs SET invoice_no=? WHERE id=?", (invoice_no, log_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Update Invoice Error: {e}")

def update_status(log_id: int, status: str):
    """อัปเดต status ของ log ค่ะ"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE logs SET status=? WHERE id=?", (status, log_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Update Status Error: {e}")

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
            slip_image_b64  TEXT  -- ✅ เก็บรูปสลิปเป็น Base64 สำหรับทีม Support ดูย้อนหลัง
        )
    """)
    conn.commit()
    conn.close()

def log_to_db(user_id, slip_type="", ref_no="", amount=None, status="", invoice_no="", ocr_text="", slip_image_b64=""):  # ✅ เพิ่ม slip_image_b64
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO logs (timestamp, user_id, slip_type, ref_no, amount, status, invoice_no, ocr_text, slip_image_b64)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, slip_type, ref_no, amount, status, invoice_no, ocr_text, slip_image_b64))  # ✅ เพิ่ม slip_image_b64
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Log Error: {e}")
import sqlite3
from datetime import datetime

DB_PATH = "kdigi_logs.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
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
            slip_image_b64  TEXT,
            remark          TEXT DEFAULT '',
            claimed_by      TEXT DEFAULT '',
            resolved_by     TEXT DEFAULT '',
            resolution_note TEXT DEFAULT ''
        )
    """)
    # ตาราง quick_replies — ข้อความสำเร็จรูปร่วมกัน
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quick_replies (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            text       TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def migrate_db():
    """เพิ่ม column ใหม่ให้ DB เก่า (safe migration)"""
    migrations = [
        "ALTER TABLE logs ADD COLUMN remark TEXT DEFAULT ''",
        "ALTER TABLE logs ADD COLUMN claimed_by TEXT DEFAULT ''",
        "ALTER TABLE logs ADD COLUMN resolved_by TEXT DEFAULT ''",
        "ALTER TABLE logs ADD COLUMN resolution_note TEXT DEFAULT ''",
    ]
    conn = sqlite3.connect(DB_PATH)
    for sql in migrations:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            pass  # column มีอยู่แล้ว
    # สร้างตาราง quick_replies ถ้ายังไม่มีค่ะ
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quick_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        conn.commit()
    except Exception:
        pass
    conn.close()


def log_to_db(user_id, slip_type="", ref_no="", amount=None,
              status="", invoice_no="", ocr_text="", slip_image_b64=""):
    """บันทึก log และ return lastrowid"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO logs
                (timestamp, user_id, slip_type, ref_no, amount,
                 status, invoice_no, ocr_text, slip_image_b64)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              user_id, slip_type, ref_no, amount,
              status, invoice_no, ocr_text, slip_image_b64))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id
    except Exception as e:
        print(f"DB Log Error: {e}")
        return None


def _update(sql: str, params: tuple):
    """Helper: execute a single UPDATE"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(sql, params)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Update Error: {e}")


def update_invoice_no(log_id: int, invoice_no: str):
    _update("UPDATE logs SET invoice_no=? WHERE id=?", (invoice_no, log_id))


def update_status(log_id: int, status: str):
    _update("UPDATE logs SET status=? WHERE id=?", (status, log_id))


def update_claimed_by(log_id: int, claimed_by: str):
    _update("UPDATE logs SET claimed_by=? WHERE id=?", (claimed_by, log_id))


def update_resolution(log_id: int, resolved_by: str, resolution_note: str):
    _update(
        "UPDATE logs SET resolved_by=?, resolution_note=? WHERE id=?",
        (resolved_by, resolution_note, log_id)
    )


# ── Quick Replies (shared) ────────────────────────────────────

def get_quick_replies() -> list:
    """ดึงข้อความสำเร็จรูปทั้งหมดค่ะ"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, text FROM quick_replies ORDER BY sort_order, id"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"get_quick_replies error: {e}")
        return []


def add_quick_reply(text: str) -> dict:
    """เพิ่มข้อความสำเร็จรูปค่ะ"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO quick_replies (text, created_at) VALUES (?, ?)",
            (text.strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def update_quick_reply(qr_id: int, text: str) -> dict:
    """แก้ไขข้อความสำเร็จรูปค่ะ"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE quick_replies SET text=? WHERE id=?", (text.strip(), qr_id))
        conn.commit()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def delete_quick_reply(qr_id: int) -> dict:
    """ลบข้อความสำเร็จรูปค่ะ"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM quick_replies WHERE id=?", (qr_id,))
        conn.commit()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

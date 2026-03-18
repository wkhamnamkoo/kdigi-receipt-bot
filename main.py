from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, MessagingApiBlob
from linebot.v3.webhooks import MessageEvent, ImageMessageContent, TextMessageContent
import os
import uuid
import shutil
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import base64  # ✅ เพิ่ม สำหรับแปลงรูปสลิปเป็น Base64 เก็บลง SQLite
import time    # ✅ เพิ่ม สำหรับ Rate Limiting 
from collections import defaultdict  # ✅ เพิ่ม สำหรับเก็บประวัติการส่งของแต่ละ User 
from dotenv import load_dotenv
from ocr_service import extract_slip_data
from invoice_service import get_invoice_url
from line_service import reply_message, reply_invoice, reply_info_and_invoice, push_support_reply
from db_service import init_db, log_to_db, update_resolve_status, update_invoice_no, update_status
from dashboard import add_dashboard_route  # ✅ เพิ่ม Admin Dashboard

# ══════════════════════════════════════════════════════════════
# ✅ แจ้งเตือนไป LINE กลุ่ม Support เมื่อเกิด Error 
# ══════════════════════════════════════════════════════════════
def notify_support(message: str, message_id: str = None, log_id: int = None):
    """ส่ง Flex Message แจ้งเตือนพร้อมปุ่ม Dashboard ไปยัง LINE กลุ่ม Support ค่ะ"""
    group_id     = os.getenv("LINE_SUPPORT_GROUP_ID")
    token        = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    dashboard_url = os.getenv("DASHBOARD_URL", "http://localhost:8000/dashboard")
    # ถ้ามี log_id ให้เพิ่ม ?open=log_id เพื่อให้ Popup เปิดอัตโนมัติค่ะ
    if log_id:
        dashboard_url = f"{dashboard_url}?open={log_id}"

    if not group_id:
        print("⚠️ ไม่พบ LINE_SUPPORT_GROUP_ID ใน .env ค่ะ")
        return

    try:
        import requests as req

        # ── Flex Message มีปุ่ม Dashboard  ──
        flex_message = {
            "type": "flex",
            "altText": message[:50],  # ข้อความ fallback สำหรับ notification bar 
            "contents": {
                "type": "bubble",
                "size": "kilo",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#C0392B",
                    "paddingAll": "12px",
                    "contents": [
                        {
                            "type": "text",
                            "text": "🚨 K-Digi Receipt Alert",
                            "color": "#FFFFFF",
                            "weight": "bold",
                            "size": "md"
                        }
                    ]
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "paddingAll": "12px",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": message,
                            "wrap": True,
                            "size": "sm",
                            "color": "#333333"
                        }
                    ]
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "paddingAll": "10px",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#F26522",
                            "height": "sm",
                            "action": {
                                "type": "uri",
                                "label": f"🔍 ดูเคส #{log_id}" if log_id else "📊 Transaction Monitor",
                                "uri": dashboard_url
                            }
                        }
                    ]
                }
            }
        }

        req.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={"to": group_id, "messages": [flex_message]},
            timeout=10
        )

        print("✅ แจ้งเตือน Support แล้วค่ะ")
    except Exception as e:
        print(f"⚠️ แจ้งเตือนไม่สำเร็จค่ะ: {e}")
#══════════════════════════════════════════════════════════════

load_dotenv() #--> ดึงค่า Token และ API Key จากไฟล์ .env มาใช้งาน (ปลอดภัย ไม่ต้องเขียน Token จริงๆ ลงใน Code โดยตรง)

from pydantic import BaseModel

app = FastAPI() #-->  สร้าง Web Server ขึ้นมา 1 ตัว รอรับข้อมูลจากภายนอก
add_dashboard_route(app)  # ✅ เพิ่ม Admin Dashboard ที่ /dashboard
Path("uploads").mkdir(exist_ok=True)  # ✅ สร้างโฟลเดอร์ก่อน mount ค่ะ
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")  # ✅ serve ไฟล์ที่ Support อัปโหลดค่ะ

init_db()

#══════════════════════════════════════════════════════════════
# ✅ Rate Limiter — ป้องกันลูกค้าส่งสลิปถี่เกินไป
#══════════════════════════════════════════════════════════════
_rate_store: dict = defaultdict(list)  # เก็บ timestamp ที่แต่ละ User ส่งมา
RATE_LIMIT  = 5   # ส่งได้สูงสุดกี่ครั้งค่ะ
RATE_WINDOW = 60  # ภายในกี่วินาที (60 = 1 นาที) 


def notify_resolved(log_id: int, ref_no: str = "", invoice_no: str = ""):
    """แจ้งกลุ่ม Support ว่าเคสนี้แก้ไขเรียบร้อยแล้วค่ะ"""
    group_id = os.getenv("LINE_SUPPORT_GROUP_ID")
    token    = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not group_id or not token:
        return

    ref_txt = f"Ref: {ref_no}" if ref_no else ""
    inv_txt = f"Invoice: {invoice_no[:30]}" if invoice_no else ""
    detail  = " | ".join(filter(None, [ref_txt, inv_txt]))

    flex = {
        "type": "flex",
        "altText": f"✅ แก้ไขเคส #{log_id} เรียบร้อยแล้วค่ะ",
        "contents": {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#1e5c36",
                "paddingAll": "12px",
                "contents": [{
                    "type": "text",
                    "text": "✅ แก้ไขเคสเรียบร้อยแล้วค่ะ",
                    "color": "#FFFFFF", "weight": "bold", "size": "md"
                }]
            },
            "body": {
                "type": "box", "layout": "vertical",
                "paddingAll": "12px", "spacing": "sm",
                "contents": [
                    {"type": "text",
                     "text": f"เคส #{log_id} ส่งใบเสร็จให้ลูกค้าแล้วค่ะ",
                     "wrap": True, "size": "sm", "color": "#333333"},
                    *(
                        [{"type": "text", "text": detail,
                          "wrap": True, "size": "xs", "color": "#888888"}]
                        if detail else []
                    )
                ]
            }
        }
    }

    try:
        import requests as _r
        _r.post(
            "https://api.line.me/v2/bot/message/push",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json={"to": group_id, "messages": [flex]},
            timeout=10
        )
        print(f"✅ notify_resolved เคส #{log_id} แล้วค่ะ")
    except Exception as e:
        print(f"notify_resolved error: {e}")

def is_rate_limited(user_id: str) -> bool:
    now     = time.time()
    history = _rate_store[user_id]

    # เอาเฉพาะ timestamp ที่อยู่ใน Window 60 วินาทีล่าสุด
    history = [t for t in history if now - t < RATE_WINDOW]
    _rate_store[user_id] = history

    if len(history) >= RATE_LIMIT:
        return True  # --> เกินแล้ว ห้ามผ่าน

    # บันทึก timestamp ครั้งนี้เพิ่มเข้าไป
    _rate_store[user_id].append(now)
    return False  # --> ยังไม่เกิน ผ่านได้
#══════════════════════════════════════════════════════════════
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET")) #--> ตัวจัดการ Event จาก LINE  ใช้ Channel Secret ในการยืนยันว่าข้อมูลมาจาก LINE จริงๆ
configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN")) #--> ข้อมูล Credential สำหรับส่งข้อความกลับไปหา User

# Keyword ที่เกี่ยวกับการขอใบเสร็จ
RECEIPT_KEYWORDS = [
    "ใบเสร็จ", "invoice", "receipt",
    "ค่ายก", "ค่าภาระ", "e-payment", "epayment",
    "ค่าจองคิว", "k-pass", "kpass",
    "ย้อนหลัง", "ขอไฟล์", "ดาวน์โหลด",
    "ขอใบเสร็จ",  # ✅ ปุ่ม Rich Menu
]

# ✅ Keyword ปุ่ม Rich Menu เพิ่มเติม
HELP_KEYWORDS  = ["วิธีใช้งาน", "วิธีใช้", "help"]
ADMIN_KEYWORDS = ["ติดต่อ admin", "ติดต่อเจ้าหน้าที่", "admin"]

HELP_MESSAGE = (
    "📋 วิธีใช้งาน K-Digi Receipt Bot ค่ะ\n\n"
    "1️⃣  ถ่ายรูปสลิปการโอนเงินค่ะ\n"
    "2️⃣  ส่งรูปสลิปมาในแชทนี้ค่ะ\n"
    "3️⃣  ระบบจะส่งใบเสร็จให้อัตโนมัติภายใน 10 วินาทีค่ะ\n\n"
    "⚠️ หมายเหตุค่ะ\n"
    "• สลิปต้องโอนให้ KERRY SIAM SEAPORT เท่านั้นค่ะ\n"
    "• รูปต้องชัดเจน ไม่มัว ไม่เอียงมากค่ะ\n"
    "• รองรับทุกธนาคารในไทยค่ะ"
)

ADMIN_MESSAGE = (
    "📞 ติดต่อทีม Admin K-Digi ได้ที่ค่ะ\n\n"
    "📞 Tel: [เบอร์โทร]\n"
    "📧 Email: [อีเมล]\n"
    "⏰ วันจันทร์–ศุกร์ 08:00–17:00 น.\n\n"
    "หากส่งสลิปแล้วยังไม่ได้ใบเสร็จ\n"
    "กรุณาแจ้ง Ref No. และยอดเงินมาด้วยนะคะ"
)

WELCOME_MESSAGE = (
    "สวัสดีค่ะ ยินดีต้อนรับสู่ K-Digi Receipt Service 👋\n\n"
    "ระบบสามารถช่วยคุณได้ดังนี้ค่ะ\n\n"
    "📄 ขอใบเสร็จค่ายกหรือค่าภาระ (E-Payment)\n"
    "📄 ขอใบเสร็จค่าจองคิว (K-Pass)\n"
    "→ กรุณาส่งภาพสลิปการชำระเงินมาได้เลยค่ะ\n\n"
    "❓ สอบถามข้อมูลอื่นๆ\n"
    "→ ติดต่อ Admin K-Digi\n"
    "📞 Tel: [เบอร์โทร]\n"
    "📧 Email: [อีเมล]\n"
    "⏰ วันจันทร์-ศุกร์ 8.00-17.00 น."
)

#--------------------------- รับ Webhook จาก LINE --------------------------

@app.post("/webhook") #--> ทุกครั้งที่ User ส่งอะไรมาใน LINE → LINE จะส่งข้อมูลมาที่ /webhook นี้
async def webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    
    try:
        handler.handle(body.decode("utf-8"), signature) #--> โดยมีการเช็ค Signature ด้วยว่าข้อมูลมาจาก LINE จริงๆ ไม่มีคนอื่นแอบส่งมา
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    return {"status": "ok"}

#---------------------------------------------------------------------------


#--------------------------- จัดการข้อความทั่วไป -------------------------------

@handler.add(MessageEvent, message=TextMessageContent) #--> ทำงานเฉพาะเมื่อ User ส่ง ข้อความ มา
def handle_text(event):
    # ✅ ถ้าข้อความมาจากกลุ่ม Support → ไม่ตอบค่ะ (ทีมคุยกันเองค่ะ)
    if hasattr(event.source, 'group_id'):
        if event.source.group_id == os.getenv("LINE_SUPPORT_GROUP_ID"):
            return

    text = event.message.text.strip().lower()
    reply_token = event.reply_token
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        # ✅ ปุ่ม Rich Menu: ติดต่อ Admin
        if any(keyword in text for keyword in ADMIN_KEYWORDS):
            reply_message(line_bot_api, reply_token, ADMIN_MESSAGE)
            return
        
        # ✅ ปุ่ม Rich Menu: วิธีใช้งาน
        if any(keyword in text for keyword in HELP_KEYWORDS):
            reply_message(line_bot_api, reply_token, HELP_MESSAGE)
            return
        
        # เช็คว่าข้อความเกี่ยวกับใบเสร็จไหม (รวมปุ่ม "ขอใบเสร็จ" ด้วย)
        is_receipt_request = any(keyword in text for keyword in RECEIPT_KEYWORDS) #--> ถ้ามี → แนะนำให้ส่งสลิป ถ้าไม่มี → ส่ง Welcome Message
        
        if is_receipt_request:
            reply_message(line_bot_api, reply_token, "กรุณาส่งภาพสลิปการชำระเงินมาให้ระบบตรวจสอบค่ะ")
        else:
            reply_message(line_bot_api, reply_token, WELCOME_MESSAGE)
            
#----------------------------------------------------------------------------


# ══════════════════════════════════════════════════════════════
# ✅ Endpoint สำหรับทีม Support ตอบกลับ User จาก Dashboard ค่ะ
# ══════════════════════════════════════════════════════════════
# ── Upload directory ค่ะ ──
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

class ReplyRequest(BaseModel):
    user_id:    str
    message:    str  = ""
    file_url:   str  = ""
    file_name:  str  = ""
    send_slip:  bool = False
    log_id:     int  = 0

@app.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    """Support อัปโหลดไฟล์ขึ้น Server แล้วได้ URL กลับค่ะ"""
    ext       = Path(file.filename).suffix.lower()
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest      = UPLOAD_DIR / safe_name
    with dest.open("wb") as f_out:
        shutil.copyfileobj(file.file, f_out)
    base_url  = os.getenv("DASHBOARD_URL", "http://localhost:8000/dashboard").rsplit("/dashboard", 1)[0]
    file_url  = f"{base_url}/uploads/{safe_name}"
    return {"status": "ok", "file_url": file_url, "file_name": file.filename}

@app.post("/reply-user")
async def reply_user(req: ReplyRequest):
    """ส่งข้อความจากทีม Support ไปหา User ค่ะ
    - ข้อความธรรมดา (ไม่มีไฟล์/สลิป) → Text Message ค่ะ
    - มีไฟล์แนบหรือสลิป → Flex Message ค่ะ
    """
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not req.user_id:
        return {"status": "error", "detail": "user_id ว่างค่ะ"}
    if not req.message.strip() and not req.file_url.strip() and not req.send_slip:
        return {"status": "error", "detail": "กรุณาพิมพ์ข้อความ หรือแนบไฟล์ หรือเลือกส่งสลิปค่ะ"}
    try:
        has_attachment = req.file_url.strip() or req.send_slip

        # ── กรณีข้อความธรรมดา ไม่มีไฟล์แนบ → Text Message ค่ะ ──
        if not has_attachment and req.message.strip():
            import requests as req_lib
            res = req_lib.post(
                "https://api.line.me/v2/bot/message/push",
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"},
                json={"to": req.user_id,
                      "messages": [{"type": "text",
                                    "text": req.message.strip()}]},
                timeout=10
            )
            if res.status_code == 200:
                print(f"✅ ส่ง Text ถึง {req.user_id[:20]} แล้วค่ะ")
                return {"status": "ok"}
            else:
                return {"status": "error", "detail": res.text}

        # ── กรณีมีไฟล์แนบหรือสลิป → Flex Message ค่ะ ──
        slip_url = ""
        if req.send_slip and req.log_id:
            import sqlite3 as _sql
            conn = _sql.connect("kdigi_logs.db")
            row  = conn.execute("SELECT slip_image_b64 FROM logs WHERE id=?", (req.log_id,)).fetchone()
            conn.close()
            if row and row[0]:
                import base64 as _b64
                slip_name = f"slip_{req.log_id}.jpg"
                slip_path = UPLOAD_DIR / slip_name
                with slip_path.open("wb") as sf:
                    sf.write(_b64.b64decode(row[0]))
                base_url = os.getenv("DASHBOARD_URL", "http://localhost:8000/dashboard").rsplit("/dashboard", 1)[0]
                slip_url = f"{base_url}/uploads/{slip_name}"

        result = push_support_reply(
            user_id      = req.user_id,
            access_token = token,
            message      = req.message,
            file_url     = req.file_url,
            file_name    = req.file_name,
            send_slip    = req.send_slip,
            slip_url     = slip_url
        )
        if result["status"] == "ok":
            print(f"✅ ส่ง Flex ถึง {req.user_id[:20]} แล้วค่ะ")
        return result
    except Exception as e:
        return {"status": "error", "detail": str(e)}
#══════════════════════════════════════════════════════════════


@app.get("/slip-image/{log_id}")
async def get_slip_image(log_id: int):
    """ดึงรูปสลิป Base64 จาก DB ส่งให้ Dashboard แสดงใน Detail Popup ค่ะ"""
    import sqlite3 as _sql
    try:
        conn = _sql.connect("kdigi_logs.db")
        row  = conn.execute("SELECT slip_image_b64 FROM logs WHERE id=?", (log_id,)).fetchone()
        conn.close()
        if row and row[0]:
            return JSONResponse({"b64": row[0]})
        return JSONResponse({"b64": ""})
    except Exception as e:
        return JSONResponse({"b64": "", "error": str(e)})

# ══════════════════════════════════════════════════════════════
# ✅ Endpoint อัปเดตสถานะการแก้ไขค่ะ
# ══════════════════════════════════════════════════════════════
class ResolveRequest(BaseModel):
    log_id: int
    resolve_status: str

@app.post("/update-resolve")
async def update_resolve(req: ResolveRequest):
    allowed = ["🔴 รอดำเนินการ", "🟡 กำลังดำเนินการ", "🟢 แก้ไขแล้ว", "✅ แก้ไขแล้ว"]
    if req.resolve_status not in allowed:
        return {"status": "error", "detail": "สถานะไม่ถูกต้องค่ะ"}
    update_resolve_status(req.log_id, req.resolve_status)
    return {"status": "ok"}
#══════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════
# ✅ Manual Invoice Search — ทีม Support ค้นหาใบเสร็จด้วยตนเอง
# ══════════════════════════════════════════════════════════════
class ManualSearchRequest(BaseModel):
    ref_no:  str
    amount:  float
    user_id: str
    log_id:  int = 0

@app.post("/manual-search")
async def manual_search(req: ManualSearchRequest):
    """ค้นหาใบเสร็จจาก Ref No. + Amount ที่ Support พิมพ์เข้ามาค่ะ"""
    if not req.ref_no.strip():
        return {"status": "error", "detail": "กรุณาระบุ Ref No. ค่ะ"}
    try:
        result = get_invoice_url(req.ref_no.strip(), req.amount)
        if not result:
            return {"status": "not_found", "detail": "ไม่พบใบเสร็จในระบบค่ะ"}
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/manual-send-invoice")
async def manual_send_invoice(req: ManualSearchRequest):
    """ส่ง Flex Message ใบเสร็จไปหา User โดยตรงค่ะ"""
    if not req.ref_no.strip():
        return {"status": "error", "detail": "กรุณาระบุ Ref No. ค่ะ"}
    try:
        result = get_invoice_url(req.ref_no.strip(), req.amount)
        if not result:
            return {"status": "not_found", "detail": "ไม่พบใบเสร็จในระบบค่ะ"}

        token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        # สร้าง Flex bubbles ค่ะ
        bubbles = []
        for i, item in enumerate(result):
            inv_no  = item.get("InvoiceNo", f"Invoice {i+1}")
            inv_url = item.get("InvoiceUrl", "")
            label   = f"ไฟล์ที่ {i+1}: {inv_no}" if len(result) > 1 else inv_no
            bubbles.append({
                "type": "bubble",
                "body": {
                    "type": "box", "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "📄 ใบเสร็จของคุณพร้อมแล้วค่ะ",
                         "weight": "bold", "size": "md", "wrap": True},
                        {"type": "text", "text": label, "size": "sm",
                         "color": "#888888", "wrap": True, "margin": "sm"}
                    ]
                },
                "footer": {
                    "type": "box", "layout": "vertical",
                    "contents": [{
                        "type": "button", "style": "primary", "color": "#f26522",
                        "action": {"type": "uri", "label": "คลิกเพื่อดาวน์โหลด", "uri": inv_url}
                    }]
                }
            })

        flex_content = bubbles[0] if len(bubbles) == 1 else {
            "type": "carousel", "contents": bubbles
        }

        import requests as req_lib
        res = req_lib.post(
            "https://api.line.me/v2/bot/message/push",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json={"to": req.user_id,
                  "messages": [{"type": "flex",
                                "altText": "📄 ใบเสร็จของคุณพร้อมแล้วค่ะ",
                                "contents": flex_content}]},
            timeout=10
        )
        if res.status_code == 200:
            print(f"✅ ส่งใบเสร็จ manual ถึง {req.user_id[:20]} แล้วค่ะ")
            # บันทึก invoice_no ลง DB ค่ะ
            inv_nos_str  = ", ".join([item.get("InvoiceNo","") for item in result])
            inv_nos_list = [item.get("InvoiceNo","") for item in result]
            if req.log_id:
                update_invoice_no(req.log_id, inv_nos_str)
                update_status(req.log_id, "✅ สำเร็จ (Support)")
                update_resolve_status(req.log_id, "✅ แก้ไขแล้ว")
                # แจ้งกลุ่ม Support ว่าแก้ไขแล้วค่ะ
                notify_resolved(req.log_id, req.ref_no, inv_nos_str)
            return {"status": "ok", "invoice_count": len(result), "invoice_nos": inv_nos_list}
        else:
            return {"status": "error", "detail": res.text}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
#══════════════════════════════════════════════════════════════

#------------------------------- จัดการรูปสลิป  --------------------------------

@handler.add(MessageEvent, message=ImageMessageContent) #--> จะทำงานก็ต่อเมื่อ User ส่งสลิปมา
def handle_image(event):
    # ✅ ถ้ารูปมาจากกลุ่ม Support → ไม่ประมวลผลค่ะ
    if hasattr(event.source, 'group_id'):
        if event.source.group_id == os.getenv("LINE_SUPPORT_GROUP_ID"):
            return

    message_id = event.message.id
    reply_token = event.reply_token
    user_id = event.source.user_id
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        blob_api = MessagingApiBlob(api_client)

        # ✅ เช็ค Rate Limit ก่อนทำอะไรทั้งนั้น
        if is_rate_limited(user_id):
            log_to_db(user_id, status="⚠️ Rate Limited")  # บันทึก Log ด้วย
            reply_message(
                line_bot_api, reply_token,
                "⚠️ ท่านส่งสลิปถี่เกินไปค่ะ\n"
                "กรุณารอ 1 นาที แล้วลองใหม่อีกครั้งนะคะ 🙏"
            )
            return

        # ดาวน์โหลดรูปจาก LINE
        image_bytes = blob_api.get_message_content(message_id)
        
        # ✅ แปลงรูปสลิปเป็น Base64 เพื่อเก็บลง SQLite ไว้เป็นหลักฐาน
        slip_image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        
        # ส่งรูปไป ocr_service.py อ่านสลิป
        slip_data = extract_slip_data(image_bytes)
        
        # กรณี OCR อ่านไม่ได้เลย (slip_data เป็น None → ไม่มี ocr_text)
        if not slip_data:
            _log_id = log_to_db(user_id, status="❌ OCR อ่านไม่ได้", slip_image_b64=slip_image_b64)
            notify_support(  # ✅ แจ้งทีม Support 
                f"⚠️ OCR อ่านสลิปไม่ได้ค่ะ\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"👤 User ID: {user_id[:33]}\n\n"
                f"🕐 เวลา: {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"⚠️ กรุณาตรวจสอบและช่วยลูกค้าด้วยตนเองค่ะ",
                message_id=message_id,  # ✅ Forward รูปสลิปไปกลุ่ม
                log_id=_log_id
            )
            reply_message(line_bot_api, reply_token, "❌ ไม่สามารถอ่านข้อมูลจากสลิปได้\nกรุณาส่งรูปสลิปที่ชัดเจนค่ะ")
            return
        
        # กรณี Slip ไม่ได้โอนไปที่ KERRY
        if slip_data.get("error") == "not_kerry":
            log_to_db(
                user_id,
                status="❌ สลิปไม่ใช่ KERRY",
                ocr_text=slip_data.get("ocr_text", ""),
                slip_image_b64=slip_image_b64  # ✅ เพิ่ม slip_image_b64
            )
            reply_message(line_bot_api, reply_token, "❌ ไม่พบข้อมูลการชำระเงินในสลิปนี้ค่ะ\nกรุณาแนบสลิปที่มีข้อมูลต่อไปนี้เท่านั้นค่ะ\n\n✅ โอนเงินให้ KERRY SIAM SEAPORT LIMITED\n✅ มีหมายเลข E-Payment หรือ K-Pass 12 หลัก\n\nหากมีข้อสงสัย กรุณาติดต่อ Admin K-Digi ค่ะ")
            return
        
        # กรณี Slip เป็น KERRY แต่หา reference_no ไม่เจอ
        if slip_data.get("error") == "no_reference":
            _log_id = log_to_db(
                user_id,
                status="❌ หา Ref No. ไม่เจอ",
                ocr_text=slip_data.get("ocr_text", ""),
                slip_image_b64=slip_image_b64
            )
            notify_support(  # ✅ แจ้งทีม Support 
                f"⚠️ อ่าน Ref No. ไม่ได้ค่ะ\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"👤 User ID: {user_id[:33]}\n\n"
                f"🕐 เวลา: {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"📄 OCR: {slip_data.get('ocr_text','')[:300]}\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"⚠️ สลิปเป็น KERRY แต่หา Ref No. 12 หลักไม่พบค่ะ\n\n"
                f"กรุณาตรวจสอบและช่วยลูกค้าด้วยตนเองค่ะ",
                message_id=message_id,  # ✅ Forward รูปสลิปไปกลุ่ม
                log_id=_log_id
            )
            reply_message(line_bot_api, reply_token, "❌ ไม่สามารถอ่านข้อมูลจากสลิปได้\nกรุณาส่งใหม่อีกครั้ง หรือติดต่อ Admin K-Digi ค่ะ")
            return
        
        # เรียก API ดึง URL ใบเสร็จ
        invoice_result = get_invoice_url(slip_data["bankTransactionNo"], slip_data["amount"])
        
        # กรณี API ไม่พบใบเสร็จ
        if not invoice_result:
            _log_id = log_to_db(
                user_id,
                slip_type=slip_data.get("slip_type", ""),
                ref_no=slip_data.get("bankTransactionNo", ""),
                amount=slip_data.get("amount"),
                status="❌ ไม่พบใบเสร็จใน API",
                ocr_text=slip_data.get("ocr_text", ""),
                slip_image_b64=slip_image_b64
            )
            notify_support(  # ✅ แจ้งทีม Support
                f"⚠️ ไม่พบใบเสร็จใน Server ค่ะ\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"👤 User ID: {user_id[:33]}\n\n"
                f"🕐 เวลา: {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                f"🔢 Ref No: {slip_data.get('bankTransactionNo', '-')}\n"
                f"💰 ยอดเงิน: {slip_data.get('amount', '-')} บาท\n"
                f"📋 ประเภท: {slip_data.get('slip_type', '-')}\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"⚠️ OCR อ่านได้ แต่ไม่พบใบเสร็จใน KLN API ค่ะ\n\n"
                f"กรุณาตรวจสอบและช่วยลูกค้าด้วยตนเองค่ะ",
                message_id=message_id,  # ✅ Forward รูปสลิปไปกลุ่ม
                log_id=_log_id
            )
            reply_message(line_bot_api, reply_token, "❌ ไม่พบใบเสร็จของท่านค่ะ\nกรุณาติดต่อเจ้าหน้าที่ค่ะ")
            return

        # ✅ กรณีสำเร็จ — บันทึก Log ก่อนส่งข้อความ
        slip_type = slip_data.get("slip_type", "Payment")
        ref_no = slip_data.get("bankTransactionNo", "")
        amount = slip_data.get("amount", "")
        invoice_no = ", ".join([i["InvoiceNo"] for i in invoice_result])

        log_to_db(
            user_id,
            slip_type=slip_type,
            ref_no=ref_no,
            amount=amount,
            status="✅ สำเร็จ",
            invoice_no=invoice_no,
            ocr_text=slip_data.get("ocr_text", ""),
            slip_image_b64=slip_image_b64  # ✅ เพิ่ม slip_image_b64
        )
        
        # ข้อความที่ 1 — แสดงข้อมูลที่อ่านได้จากสลิป
        info_message = (
            f"📋 รายการ {slip_type} ของคุณคือ\n\n"
            f"หมายเลขอ้างอิง: {ref_no}\n"
            f"จำนวนเงิน: {amount} บาท"
        )
        reply_info_and_invoice(line_bot_api, reply_token, info_message, invoice_result) #--> ส่ง Flex Message กลับหาลูกค้าผ่าน line_service.py
        
        #----------------------------------------------------------------------------
        
        
        #----------------------------- Summary main.py ------------------------------
        
        #ไม่ได้ทำงานเองทุกอย่าง แต่รับข้อมูลจาก LINE แล้ว **สั่งงานไฟล์อื่นๆ**
        
        #├── สั่ง ocr_service.py    → "ช่วยอ่านสลิปให้หน่อย"
        #├── สั่ง invoice_service.py → "ช่วยดึงใบเสร็จให้หน่อย"
        #└── สั่ง line_service.py   → "ช่วยส่งข้อความให้ลูกค้าหน่อย"
        
        #----------------------------------------------------------------------------
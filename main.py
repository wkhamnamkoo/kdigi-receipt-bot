from fastapi import FastAPI, Request, HTTPException
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, MessagingApiBlob
from linebot.v3.webhooks import MessageEvent, ImageMessageContent, TextMessageContent
import os
import base64  # ✅ เพิ่ม สำหรับแปลงรูปสลิปเป็น Base64 เก็บลง SQLite
import time    # ✅ เพิ่ม สำหรับ Rate Limiting ค่ะ
from collections import defaultdict  # ✅ เพิ่ม สำหรับเก็บประวัติการส่งของแต่ละ User ค่ะ
from dotenv import load_dotenv
from ocr_service import extract_slip_data
from invoice_service import get_invoice_url
from line_service import reply_message, reply_invoice, reply_info_and_invoice
from db_service import init_db, log_to_db
from dashboard import add_dashboard_route  # ✅ เพิ่ม Admin Dashboard

load_dotenv() #--> ดึงค่า Token และ API Key จากไฟล์ .env มาใช้งาน (ปลอดภัย ไม่ต้องเขียน Token จริงๆ ลงใน Code โดยตรง)

app = FastAPI() #-->  สร้าง Web Server ขึ้นมา 1 ตัว รอรับข้อมูลจากภายนอก
add_dashboard_route(app)  # ✅ เพิ่ม Admin Dashboard ที่ /dashboard

init_db()

#══════════════════════════════════════════════════════════════
# ✅ Rate Limiter — ป้องกันลูกค้าส่งสลิปถี่เกินไปค่ะ
#══════════════════════════════════════════════════════════════
_rate_store: dict = defaultdict(list)  # เก็บ timestamp ที่แต่ละ User ส่งมาค่ะ
RATE_LIMIT  = 5   # ส่งได้สูงสุดกี่ครั้งค่ะ
RATE_WINDOW = 60  # ภายในกี่วินาที (60 = 1 นาที) ค่ะ

def is_rate_limited(user_id: str) -> bool:
    now     = time.time()
    history = _rate_store[user_id]

    # เอาเฉพาะ timestamp ที่อยู่ใน Window 60 วินาทีล่าสุดค่ะ
    history = [t for t in history if now - t < RATE_WINDOW]
    _rate_store[user_id] = history

    if len(history) >= RATE_LIMIT:
        return True  # --> เกินแล้ว ห้ามผ่านค่ะ

    # บันทึก timestamp ครั้งนี้เพิ่มเข้าไปค่ะ
    _rate_store[user_id].append(now)
    return False  # --> ยังไม่เกิน ผ่านได้ค่ะ
#══════════════════════════════════════════════════════════════
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET")) #--> ตัวจัดการ Event จาก LINE  ใช้ Channel Secret ในการยืนยันว่าข้อมูลมาจาก LINE จริงๆ
configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN")) #--> ข้อมูล Credential สำหรับส่งข้อความกลับไปหา User

# Keyword ที่เกี่ยวกับการขอใบเสร็จ
RECEIPT_KEYWORDS = [
    "ใบเสร็จ", "invoice", "receipt",
    "ค่ายก", "ค่าภาระ", "e-payment", "epayment",
    "ค่าจองคิว", "k-pass", "kpass",
    "ย้อนหลัง", "ขอไฟล์", "ดาวน์โหลด",
    "ขอใบเสร็จ",  # ✅ ปุ่ม Rich Menu ค่ะ
]

# ✅ Keyword ปุ่ม Rich Menu เพิ่มเติมค่ะ
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
        
        # เช็คว่าข้อความเกี่ยวกับใบเสร็จไหม (รวมปุ่ม "ขอใบเสร็จ" ด้วยค่ะ)
        is_receipt_request = any(keyword in text for keyword in RECEIPT_KEYWORDS) #--> ถ้ามี → แนะนำให้ส่งสลิป ถ้าไม่มี → ส่ง Welcome Message
        
        if is_receipt_request:
            reply_message(line_bot_api, reply_token, "กรุณาส่งภาพสลิปการชำระเงินมาให้ระบบตรวจสอบค่ะ")
        else:
            reply_message(line_bot_api, reply_token, WELCOME_MESSAGE)
            
#----------------------------------------------------------------------------


#------------------------------- จัดการรูปสลิป  --------------------------------

@handler.add(MessageEvent, message=ImageMessageContent) #--> จะทำงานก็ต่อเมื่อ User ส่งสลิปมา
def handle_image(event):
    message_id = event.message.id
    reply_token = event.reply_token
    user_id = event.source.user_id
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        blob_api = MessagingApiBlob(api_client)

        # ✅ เช็ค Rate Limit ก่อนทำอะไรทั้งนั้นค่ะ
        if is_rate_limited(user_id):
            log_to_db(user_id, status="⚠️ Rate Limited")  # บันทึก Log ด้วยค่ะ
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
            log_to_db(user_id, status="❌ OCR อ่านไม่ได้", slip_image_b64=slip_image_b64)  # ✅ เพิ่ม slip_image_b64
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
            log_to_db(
                user_id,
                status="❌ หา Ref No. ไม่เจอ",
                ocr_text=slip_data.get("ocr_text", ""),
                slip_image_b64=slip_image_b64  # ✅ เพิ่ม slip_image_b64
            )
            reply_message(line_bot_api, reply_token, "❌ ไม่สามารถอ่านข้อมูลจากสลิปได้\nกรุณาส่งใหม่อีกครั้ง หรือติดต่อ Admin K-Digi ค่ะ")
            return
        
        # เรียก API ดึง URL ใบเสร็จ
        invoice_result = get_invoice_url(slip_data["bankTransactionNo"], slip_data["amount"])
        
        # กรณี API ไม่พบใบเสร็จ
        if not invoice_result:
            log_to_db(
                user_id,
                slip_type=slip_data.get("slip_type", ""),
                ref_no=slip_data.get("bankTransactionNo", ""),
                amount=slip_data.get("amount"),
                status="❌ ไม่พบใบเสร็จใน API",
                ocr_text=slip_data.get("ocr_text", ""),
                slip_image_b64=slip_image_b64  # ✅ เพิ่ม slip_image_b64
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
# 🧾 K-Digi Receipt Bot

> **LINE Chatbot** สำหรับระบบ K-Digi ของ **KLN Seaport Limited**  
> ช่วยลูกค้าค้นหาและรับใบเสร็จรับเงินอัตโนมัติผ่าน LINE ค่ะ

---

## 📌 ที่มาของโปรเจค

เมื่อลูกค้าชำระเงินค่ายกหรือค่าภาระ (E-Payment / K-Pass) แล้ว **ระบบแจ้งเตือนล้มเหลว** ทำให้ไม่สามารถดาวน์โหลดใบเสร็จจาก K-Digi App ได้ค่ะ ลูกค้าจึงต้องติดต่อทีม Support ทาง LINE ด้วยตนเองทุกครั้งค่ะ

**K-Digi Receipt Bot** แก้ปัญหานี้โดยให้ลูกค้า **ส่งรูปสลิปการโอนเงินมาทาง LINE** แล้วระบบจะค้นหาและส่งลิงก์ใบเสร็จให้อัตโนมัติภายใน 10 วินาทีค่ะ

---

## ✨ ฟีเจอร์หลักค่ะ

| ฟีเจอร์ | รายละเอียด |
|---|---|
| 📄 **OCR สลิปอัตโนมัติ** | ใช้ Typhoon AI อ่านข้อมูลจากรูปสลิปค่ะ |
| 🔍 **ค้นหาใบเสร็จ** | เรียก KLN API ด้วย Reference No. + ยอดเงินค่ะ |
| 💬 **Flex Message** | ส่งใบเสร็จกลับเป็น Bubble / Carousel สวยงามค่ะ |
| 🖼️ **เก็บรูปสลิป** | บันทึกรูปสลิปเป็น Base64 ลง SQLite เป็นหลักฐานค่ะ |
| 📊 **Admin Dashboard** | หน้า Web ดู Log และรูปสลิปสำหรับทีม Support ค่ะ |
| 📱 **Rich Menu** | เมนูถาวรใน LINE พร้อม 3 ปุ่มค่ะ |
| 🛡️ **Rate Limiting** | ป้องกันส่งสลิปถี่เกินไป (สูงสุด 5 ครั้ง/นาที) ค่ะ |

---

## 🛠️ Tech Stack

```
Backend    : Python 3.12 + FastAPI
AI / OCR   : Typhoon OCR (typhoon-ocr) by SCB 10X
LINE API   : line-bot-sdk-python v3
Database   : SQLite
Tunnel     : ngrok (Development)
```

---

## 📁 โครงสร้างไฟล์

```
line-receipt-bot/
│
├── main.py              # Webhook receiver + Flow controller
├── ocr_service.py       # Typhoon OCR + Regex parser
├── invoice_service.py   # KLN API caller
├── line_service.py      # LINE Flex Message sender
├── db_service.py        # SQLite logging
├── dashboard.py         # Admin Dashboard (/dashboard)
├── setup_richmenu.py    # Script สร้าง Rich Menu (รันครั้งเดียว)
│
├── richmenu.png         # รูปพื้นหลัง Rich Menu
├── kdigi_logs.db        # SQLite database (auto-created)
│
├── .env                 # API Keys (ไม่ commit ขึ้น Git)
├── .gitignore
└── requirements.txt
```

---

## ⚙️ วิธีติดตั้งค่ะ

### 1. Clone Repository

```bash
git clone https://github.com/<your-username>/kdigi-receipt-bot.git
cd kdigi-receipt-bot
```

### 2. สร้าง Virtual Environment

```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

### 3. ติดตั้ง Dependencies

```bash
pip install -r requirements.txt
```

### 4. ตั้งค่า `.env`

สร้างไฟล์ `.env` แล้วเติมค่าดังนี้ค่ะ

```env
LINE_CHANNEL_SECRET=your_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token
TYPHOON_API_KEY=your_typhoon_api_key
KLN_API_URL=https://uat-api-common.ksp.kln.com/customerSupport/getInvoiceList
```

---

## 🚀 วิธีรันค่ะ

### Terminal 1 — รัน Server

```bash
uvicorn main:app --reload
```

### Terminal 2 — รัน ngrok

```bash
ngrok http 8000
```

จากนั้นนำ URL ของ ngrok ไปตั้งค่า Webhook ใน LINE Developers Console ค่ะ

```
https://<ngrok-url>/webhook
```

### Admin Dashboard

เปิด Browser แล้วไปที่ค่ะ

```
http://localhost:8000/dashboard
```

---

## 📱 วิธีใช้งาน Rich Menu (รันครั้งเดียว)

```bash
python setup_richmenu.py
```

Script จะสร้างและ Upload Rich Menu ให้อัตโนมัติค่ะ

---

## 🔄 System Flow

```
ลูกค้าส่งรูปสลิปมาทาง LINE
          ↓
    main.py รับ Webhook
          ↓
   เช็ค Rate Limit (5 ครั้ง/นาที)
          ↓
  ocr_service.py → Typhoon OCR
  อ่าน Reference No. + ยอดเงิน
          ↓
  invoice_service.py → KLN API
  ค้นหา Invoice URL
          ↓
  line_service.py → Flex Message
  ส่งใบเสร็จกลับหาลูกค้า
          ↓
  db_service.py → SQLite
  บันทึก Log + รูปสลิป
```

---

## 🗄️ Database Schema

| Column | Type | รายละเอียด |
|---|---|---|
| `id` | INTEGER | Primary Key |
| `timestamp` | TEXT | วันเวลาที่รับสลิป |
| `user_id` | TEXT | LINE User ID |
| `slip_type` | TEXT | E-Payment / K-Pass |
| `ref_no` | TEXT | Reference No. 12 หลัก |
| `amount` | REAL | ยอดเงิน (บาท) |
| `status` | TEXT | ✅ สำเร็จ / ❌ Error |
| `invoice_no` | TEXT | Invoice File Name |
| `ocr_text` | TEXT | ข้อความ OCR เต็ม |
| `slip_image_b64` | TEXT | รูปสลิป Base64 |

---

## 📦 Dependencies

```
fastapi
uvicorn
line-bot-sdk
openai
python-dotenv
requests
Pillow
```

ติดตั้งทั้งหมดด้วยค่ะ

```bash
pip install fastapi uvicorn line-bot-sdk openai python-dotenv requests Pillow
```

---

## 👩‍💻 Developer

| | |
|---|---|
| **ชื่อ** | [ชื่อ-นามสกุล] |
| **รหัสนักศึกษา** | [รหัสนักศึกษา] |
| **สาขา** | เทคโนโลยีสารสนเทศ คณะวิทยาศาสตร์ |
| **มหาวิทยาลัย** | มหาวิทยาลัยเกษตรศาสตร์ วิทยาเขตศรีราชา |
| **สถานที่ฝึกงาน** | KLN Seaport Limited (Kerry Siam Seaport) |
| **ตำแหน่ง** | Application Support Intern |

---

## 📄 License

โปรเจคนี้พัฒนาขึ้นเพื่อการฝึกงานที่ KLN Seaport Limited ค่ะ  
ห้ามนำไปใช้งานเชิงพาณิชย์โดยไม่ได้รับอนุญาตค่ะ

# 🧾 K-Digi Receipt Bot

> **LINE Chatbot** สำหรับระบบ K-Digi ของ **KLN Seaport Limited**  
> ช่วยลูกค้าค้นหาและรับใบเสร็จรับเงินอัตโนมัติผ่าน LINE ค่ะ

---

## 📌 ที่มาของโปรเจค

เมื่อลูกค้าชำระเงินค่ายกหรือค่าภาระ (E-Payment / K-Pass) แล้ว **ระบบแจ้งเตือนล้มเหลว** ทำให้ไม่สามารถดาวน์โหลดใบเสร็จจาก K-Digi App ได้ค่ะ ลูกค้าจึงต้องติดต่อทีม Support ทาง LINE ด้วยตนเองทุกครั้งค่ะ

**K-Digi Receipt Bot** แก้ปัญหานี้โดยให้ลูกค้า **ส่งรูปสลิปการโอนเงินมาทาง LINE** แล้วระบบจะค้นหาและส่งลิงก์ใบเสร็จให้อัตโนมัติภายใน 10 วินาทีค่ะ

---

## ✨ ฟีเจอร์หลักค่ะ

### 🤖 ระบบ Bot (ฝั่ง User)

| ฟีเจอร์ | รายละเอียด |
|---|---|
| 📄 **OCR สลิปอัตโนมัติ** | ใช้ Typhoon OCR อ่านข้อมูลจากรูปสลิปทุกธนาคาร |
| 🔍 **ค้นหาใบเสร็จ** | เรียก KLN API ด้วย Reference No. + ยอดเงิน |
| 💬 **Flex Message** | ส่งใบเสร็จกลับเป็น Bubble / Carousel พร้อมปุ่มดาวน์โหลด |
| 🖼️ **เก็บรูปสลิป** | บันทึกรูปสลิปเป็น Base64 ลง SQLite เป็นหลักฐาน |
| 🛡️ **Rate Limiting** | ป้องกันส่งสลิปถี่เกินไป (สูงสุด 5 ครั้ง/นาที) |
| 📱 **Rich Menu** | เมนูถาวรใน LINE พร้อม 3 ปุ่ม (ขอใบเสร็จ / วิธีใช้ / ติดต่อ Admin) |
| 💬 **Text / Flex แยกกัน** | ข้อความล้วน → Text Message ธรรมดา, มีไฟล์/สลิป → Flex Message |

### 📊 Admin Dashboard (ฝั่งทีม Support)

| ฟีเจอร์ | รายละเอียด |
|---|---|
| 📊 **Transaction Monitor** | ดูรายการทั้งหมดพร้อม KPI Cards (Total / Success / Error / Rate) |
| 🔽 **Filter สถานะ** | ทั้งหมด / ✅ สำเร็จ / ⚡ ต้องรีบแก้ไข / ❌ Error ทั่วไป |
| ⚡ **Urgent Rows** | 3 สถานะพิเศษ highlight สีส้ม + badge กระพริบ |
| 🎨 **สี Header Popup** | 🟢 เขียว = สำเร็จ, 🔴 แดง = urgent, 🟡 เหลือง = error ทั่วไป |
| 🔍 **ค้นหา Manual** | Support พิมพ์ Ref No. + Amount ใหม่ → ค้นหาจาก KLN API |
| 📤 **ส่งใบเสร็จ Manual** | ส่ง Flex Message ถึง User พร้อมอัปเดต DB อัตโนมัติ |
| ✅ **บันทึกการแก้ไข** | เมื่อส่งสำเร็จ → อัปเดต invoice_no, status, slip_type, ref_no, amount |
| 📋 **column การแก้ไข** | แสดง ✅ แก้ไขแล้ว / — แยกจาก Status |
| 🔗 **Deep Link** | ปุ่มใน Flex แจ้งเตือน → `/dashboard?open={id}` → Popup เปิดอัตโนมัติ |
| 📣 **แจ้งกลุ่ม Support** | เมื่อแก้เคสสำเร็จ → ส่ง Flex สีเขียวแจ้งกลุ่มทันที |
| ⬇️ **Export CSV** | ส่งออกข้อมูลทั้งหมด |
| 🔄 **Auto Refresh** | refresh อัตโนมัติทุก 30 วินาที |
| 🎨 **KLN Brand** | Design match กับระบบ KLN (สีส้ม `#F26522` + header ดำ) |

---

## 🛠️ Tech Stack

```
Backend    : Python 3.12 + FastAPI
AI / OCR   : Typhoon OCR (typhoon-ocr) by SCB 10X
LINE API   : line-bot-sdk-python v3
Database   : SQLite
Dashboard  : FastAPI + Vanilla HTML/CSS/JS (KLN Brand)
Font       : Sarabun (Google Fonts)
Tunnel     : ngrok (Development)
```

---

## 📁 โครงสร้างไฟล์

```
line-receipt-bot/
│
├── main.py              # Webhook receiver + Flow controller + API endpoints
├── ocr_service.py       # Typhoon OCR + Regex parser
├── invoice_service.py   # KLN API caller
├── line_service.py      # LINE Flex / Text Message sender
├── db_service.py        # SQLite helpers (log, update, query)
├── dashboard.py         # Admin Dashboard (/dashboard) + endpoints
├── setup_richmenu.py    # Script สร้าง Rich Menu (รันครั้งเดียว)
│
├── richmenu.png         # รูปพื้นหลัง Rich Menu
├── kdigi_logs.db        # SQLite database (auto-created)
├── uploads/             # ไฟล์ที่ Support อัปโหลด
│
├── .env                 # API Keys (ไม่ commit ขึ้น Git!)
├── .gitignore
└── requirements.txt
```

---

## ⚙️ วิธีติดตั้งค่ะ

### 1. Clone Repository

```bash
git clone https://github.com/wkhamnamkoo/Automated-Slip-Verification-and-Receipt-Delivery-System-Using-LINE-Messaging-API.git
cd Automated-Slip-Verification-and-Receipt-Delivery-System-Using-LINE-Messaging-API
```

### 2. สร้าง Virtual Environment

```bash
python -m venv venv
.\venv\Scripts\activate        # Windows
source venv/bin/activate       # Mac / Linux
```

### 3. ติดตั้ง Dependencies

```bash
pip install -r requirements.txt
```

### 4. ตั้งค่า `.env`

```env
LINE_CHANNEL_SECRET=your_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token
TYPHOON_API_KEY=your_typhoon_api_key
KLN_API_URL=https://uat-api-common.ksp.kln.com/customerSupport/getInvoiceList
LINE_SUPPORT_GROUP_ID=your_support_group_id
DASHBOARD_URL=https://xxxx.ngrok-free.app/dashboard
```

---

## 🚀 วิธีรันค่ะ

```bash
# Terminal 1 — Server
uvicorn main:app --reload

# Terminal 2 — ngrok
ngrok http 8000
```

นำ ngrok URL ไปตั้ง Webhook ใน LINE Developers Console ค่ะ
```
https://<ngrok-url>/webhook
```

เปิด Dashboard ที่ค่ะ
```
http://localhost:8000/dashboard
```

### สร้าง Rich Menu (รันครั้งเดียว)

```bash
python setup_richmenu.py
```

---

## 🔄 System Flow

```
User ส่งรูปสลิป → LINE Webhook → main.py
  ↓ เช็ค Rate Limit (5/min)
  ↓ ocr_service.py → Typhoon OCR → ดึง Ref No. + Amount
  ↓ invoice_service.py → POST KLN API
  ↓ [สำเร็จ] line_service.py → Flex Message → User
  ↓ [Error]  notify_support() → Flex แจ้งกลุ่ม Support + ปุ่ม ?open=id
  ↓ db_service.py → บันทึก Log + รูปสลิป Base64

Support คลิกปุ่มใน LINE
  ↓ /dashboard?open={log_id} → Popup เปิดอัตโนมัติ
  ↓ พิมพ์ Ref No. ที่ถูก → ค้นหา → ส่งใบเสร็จ
  ↓ อัปเดต DB (invoice_no, status=✅ สำเร็จ (Support))
  ↓ /notify-resolved → Flex สีเขียวแจ้งกลุ่ม Support
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
| `status` | TEXT | ✅ สำเร็จ / ❌ Error / ✅ สำเร็จ (Support) |
| `invoice_no` | TEXT | Invoice File Name |
| `ocr_text` | TEXT | ข้อความ OCR เต็ม |
| `slip_image_b64` | TEXT | รูปสลิป Base64 |
| `resolve_status` | TEXT | สถานะการแก้ไขของทีม Support |

---

## 🔌 API Endpoints

| Method | Path | รายละเอียด |
|---|---|---|
| POST | `/webhook` | รับ Event จาก LINE |
| GET | `/dashboard` | หน้า Admin Dashboard |
| GET | `/dashboard/error-count` | จำนวน Error (สำหรับ auto-refresh) |
| GET | `/dashboard/export` | Export CSV |
| GET | `/slip-image/{id}` | ดึงรูปสลิป Base64 |
| POST | `/reply-user` | Support ตอบกลับ User |
| POST | `/upload-file` | Support อัปโหลดไฟล์แนบ |
| POST | `/update-resolve` | อัปเดตสถานะการแก้ไข |
| POST | `/manual-search` | ค้นหาใบเสร็จจาก Ref No. + Amount |
| POST | `/manual-send-invoice` | ส่งใบเสร็จ manual + อัปเดต DB |
| POST | `/notify-resolved` | แจ้งกลุ่ม Support ว่าเคสแก้แล้ว |

---

## 👩‍💻 Developer

| | |
|---|---|
| **ชื่อ** | นางสาววิลาสินี ขำน้ำคู้ |
| **รหัสนักศึกษา** | 6530202463 |
| **สาขา** | เทคโนโลยีสารสนเทศ คณะวิทยาศาสตร์ |
| **มหาวิทยาลัย** | มหาวิทยาลัยเกษตรศาสตร์ วิทยาเขตศรีราชา |
| **สถานที่ฝึกงาน** | KLN Seaport Limited |
| **ตำแหน่ง** | Application Support Intern |

---

## 📄 License

โปรเจคนี้พัฒนาขึ้นเพื่อการฝึกงานที่ KLN Seaport Limited ค่ะ  
ห้ามนำไปใช้งานเชิงพาณิชย์โดยไม่ได้รับอนุญาตค่ะ
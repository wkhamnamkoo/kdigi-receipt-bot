import base64
import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("TYPHOON_API_KEY"),
    base_url="https://api.opentyphoon.ai/v1",
)

KERRY_KEYWORDS = [
    "KERRY SIAM SEAPORT", "KERRY SIAM SEA PORT",
    "KERRY SIAM SEAPOST",  "KERRY SIAM SEA POST",
    "KERRY", "SIAM", "SEAPORT", "KERRY SIAM",
    "SEAPORT LIMITED", "KERRY SIAM SEAPORT LIMITED",
    "เคอรี่ สยามซีพอร์ต", "เคอรี่ สยาม ซีพอร์ต",
    "KSP", "KSSP",
]

_AMOUNT_PATTERNS = [
    r'(\d{1,3}(?:,\d{3})*\.\d{2})\s*บาท',
    r'(\d{1,3}(?:,\d{3})*\.\d{2})\s*THB',
    r'(?:จำนวนเงิน|จำนวน)[:\s]*(\d{1,3}(?:,\d{3})*\.\d{2})',
    r'(\d{1,3}(?:,\d{3})*\.\d{2})',
]

_OCR_SYSTEM_PROMPT = """\
คุณเป็น OCR สำหรับสลิปโอนเงิน ให้คืน "ข้อความที่อ่านได้ทั้งหมด" เป็น Markdown รักษา layout
ห้ามดา ถ้าอ่านไม่ชัดให้ใส่ [อ่านไม่ชัด]
ช่วยดึงข้อและแยกบรรทัดเป็นส่วน "บันทึกช่วยจำ/หมายเหตุ/Note/Memo" ให้ชัดเจน

⚠️ กฎสำคัญสำหรับตัวเลข:
- อ่านตัวเลขทุกหลักอย่างละเอียดและครบถ้วน ห้ามตัดหรือเพิ่มตัวเลข
- Biller ID, Reference Number, เลขที่อ้างอิง ต้องอ่านให้ครบทุกหลัก
- ถ้าไม่แน่ใจตัวเลขหลักใด ให้ระบุ [?] แทน อย่าเดา
- ตรวจสอบจำนวนหลักของตัวเลขสำคัญให้ถูกต้องก่อนส่งผล\
"""


def extract_slip_data(image_bytes: bytes) -> dict:
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    try:
        response = client.chat.completions.create(
            model="typhoon-ocr",
            messages=[
                {"role": "system", "content": _OCR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                        {"type": "text",
                         "text": "ช่วย OCR จากภาพที่แนบมา และคืนข้อความทั้งหมดเป็น Markdown"},
                    ],
                },
            ],
            max_tokens=2000,
        )

        text = response.choices[0].message.content.strip()
        print(f"OCR Text: {text}")

        # Step 1 — เช็คว่าโอนไปที่ KERRY หรือเปล่า
        if not any(kw.lower() in text.lower() for kw in KERRY_KEYWORDS):
            print("Not a KERRY slip")
            return {"error": "not_kerry", "ocr_text": text}

        # Step 2 — หา reference_no (12 หลัก)
        reference_no = slip_type = None
        matches = re.findall(r'\b(\d{12})\b', text)
        if matches:
            reference_no = next((n for n in matches if n[0] in ("1", "2")), matches[0])
            if reference_no[0] == "1":
                slip_type = "E-Payment"
            elif reference_no[0] == "2":
                slip_type = "K-Pass"
            else:
                slip_type = "Payment Reference"

        if not reference_no:
            return {"error": "no_reference", "ocr_text": text}

        # Step 3 — หา amount
        amount = None
        for pattern in _AMOUNT_PATTERNS:
            m = re.search(pattern, text)
            if m:
                amount = float(m.group(1).replace(",", ""))
                break

        print(f"Type: {slip_type}, ref_no: {reference_no}, amount: {amount}")

        if reference_no and amount:
            return {
                "bankTransactionNo": reference_no,
                "amount":            amount,
                "slip_type":         slip_type,
                "ocr_text":          text,
            }
        return None

    except Exception as e:
        print(f"OCR Error: {e}")
        return None

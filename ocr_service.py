import base64
import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI( #--> Typhoon ใช้รูปแบบเดียวกับ OpenAI เลยใช้ Library openai ได้เลย แค่เปลี่ยน base_url ชี้ไปที่ Server ของ Typhoon แทน
    api_key=os.getenv("TYPHOON_API_KEY"),
    base_url="https://api.opentyphoon.ai/v1"
)

KERRY_KEYWORDS = [ #--> ใช้เช็คว่าสลิปโอนมาที่ KERRY จริงๆมั้ย เพราะสลิปจากธนาคารต่างๆ อาจเขียนชื่อต่างกัน
    "KERRY SIAM SEAPORT",
    "KERRY SIAM SEA PORT",
    "KERRY SIAM SEAPOST",   
    "KERRY SIAM SEA POST",
    "เคอรี่ สยามซีพอร์ต",
    "เคอรี่ สยาม ซีพอร์ต",
    "KSP",
    "KSSP"
]

def extract_slip_data(image_bytes: bytes) -> dict: #--> แปลงรูปเป็น Base64 เพื่อส่งผ่าน Internet
    image_base64 = base64.b64encode(image_bytes).decode("utf-8") 
    
    try: #--> ส่งรูปไป Typhoon OCR
        response = client.chat.completions.create(
            model="typhoon-ocr",
            messages=[
                {
                    "role": "system", #--> System Message - บอก AI ว่าให้ทำหน้าที่อะไร เหมือน Job Description โดยเน้นย้ำให้อ่านตัวเลขครบทุกหลัก
                    "content": """คุณเป็น OCR สำหรับสลิปโอนเงินให้คืน "ข้อความที่อ่านได้ทั้งหมด" เป็น Markdown รักษา layout
ห้ามดา ถ้าอ่านไม่ชัดให้ใส่ [อ่านไม่ชัด]
ช่วยดึงข้อและแยกบรรทัดเป็นส่วน "บันทึกช่วยจำ/หมายเหตุ/Note/Memo" ให้ชัดเจน
⚠️ กฎสำคัญสำหรับตัวเลข:
- อ่านตัวเลขทุกหลักอย่างละเอียดและครบถ้วน ห้ามตัดหรือเพิ่มตัวเลข
- Biller ID, Reference Number, เลขที่อ้างอิง ต้องอ่านให้ครบทุกหลัก
- ถ้าไม่แน่ใจตัวเลขหลักใด ให้ระบุ [?] แทน อย่าเดา
- ตรวจสอบจำนวนหลักของตัวเลขสำคัญให้ถูกต้องก่อนส่งผล"""
                },
                {
                    "role": "user", #--> User Message - ส่งรูปสลิปพร้อมคำสั่งให้ OCR
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": "ช่วย OCR จากภาพที่แนบมา และคืนข้อความทั้งหมดเป็น Markdown"
                        }
                    ]
                }
            ],
            max_tokens=2000
        )
        
        text = response.choices[0].message.content.strip()
        print(f"OCR Text: {text}")
        
        # Step 1 — เช็คว่าโอนไปที่ KERRY หรือเปล่า
        is_kerry = any(keyword.lower() in text.lower() for keyword in KERRY_KEYWORDS)
        if not is_kerry:
            print("Not a KERRY slip")
            return {"error": "not_kerry", "ocr_text": text} # --> เพิ่ม ocr_text
        
        # Step 2 — หา reference_no (12 หลัก ขึ้นต้นด้วย 1 = E-Payment, 2 = K-Pass)
        reference_no = None
        slip_type = None
        
        #------------------------------ ดึง reference_no ด้วย Regex --------------------------------
        
        all_matches = re.findall(r'\b(\d{12})\b', text) #--> Regex \b(\d{12})\b = หาตัวเลข 12 หลักติดกัน 
        if all_matches:
            preferred = next((n for n in all_matches if n[0] in ["1", "2"]), None)
            reference_no = preferred or all_matches[0]
            
            #--> จากนั้นกรองเอาเฉพาะที่ขึ้นต้นด้วย 1 หรือ 2 เท่านั้น
            if reference_no[0] == "1": 
                slip_type = "E-Payment"
            elif reference_no[0] == "2":
                slip_type = "K-Pass"
            else:
                slip_type = "Payment Reference"
        
        # Step 3 — หา amount
        amount = None
        
        #----------------------------------- ดึง amount ด้วย Regex -----------------------------------
        amount_patterns = [
            r'(\d{1,3}(?:,\d{3})*\.\d{2})\s*บาท', #--> ลองหา amount หลายรูปแบบ เพราะแต่ละธนาคารเขียนต่างกัน  เช่น 802.50 บาท หรือ 130.00 THB ลองทีละ Pattern จนกว่าจะเจอ
            r'(\d{1,3}(?:,\d{3})*\.\d{2})\s*THB',
            r'(?:จำนวนเงิน|จำนวน)[:\s]*(\d{1,3}(?:,\d{3})*\.\d{2})',
            r'(\d{1,3}(?:,\d{3})*\.\d{2})'
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, text)
            if match:
                amount = float(match.group(1).replace(',', ''))
                break
        
        print(f"Type: {slip_type}, reference_no: {reference_no}, amount: {amount}")
        
        #-------------------------------------- Return ผลลัพธ์ ---------------------------------------
        if not reference_no:
            return {"error": "no_reference", "ocr_text": text} # --> เพิ่ม ocr_text

        if reference_no and amount:
            return { #--> ถ้าได้ครบทั้ง 2 ค่า → ส่งกลับไปให้ `main.py` นำไปใช้ต่อ
                "bankTransactionNo": reference_no,
                "amount": amount,
                "slip_type": slip_type,
                "ocr_text": text # --> เพิ่ม ocr_text
            }
        else:
            return None
            
    except Exception as e:
        print(f"OCR Error: {e}") #--> ถ้าไม่ครบ → ส่ง Error กลับไปแทน
        return None
    
        #---------------------------------------------------------------------------------------------
        
        
        #---------------------------------- Summary ocr_service.py -----------------------------------
    
        #รับรูปสลิป
        #    ↓
        #แปลงเป็น Base64
        #    ↓
        #ส่งไป Typhoon AI อ่านข้อความ
        #    ↓
        #เช็คว่าเป็นสลิป KERRY ไหม
        #    ↓
        #ใช้ Regex ดึง reference_no (12 หลัก)
        #    ↓
        #ใช้ Regex ดึง amount
        #    ↓
        #ส่งข้อมูลกลับให้ main.py
        
        #----------------------------------------------------------------------------------------------
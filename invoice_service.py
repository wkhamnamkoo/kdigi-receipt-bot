#-------------------------------------- Import และโหลด URL จาก .env ------------------------------------
import requests #-->  Library สำหรับส่ง HTTP Request ตัวส่งจดหมาย ที่ส่งข้อมูลไปหา API
import os
from dotenv import load_dotenv

load_dotenv()

KLN_API_URL = os.getenv("KLN_API_URL") #--> ดึง URL ของ API บริษัทจาก .env
#--------------------------------------------------------------------------------------------------------

def get_invoice_url(bank_transaction_no: str, amount: float) -> dict: #--> รับค่า 2 อย่างจาก main.py และ return กลับเป็น dict
    try:
        # เตรียม Request Body
        payload = { #--> เตรียมข้อมูลในรูปแบบที่ API KLN ต้องการ ตรงกับที่ทีม Dev กำหนดไว้
            "bankTransactionNo": bank_transaction_no,
            "amount": amount
        }
        
        # ส่ง POST Request ไป API ของ KLN
        response = requests.post( #--> ส่งข้อมูลแบบ POST ไปที่ API KLN  
            KLN_API_URL,
            json=payload, #--> แนบข้อมูลไปด้วยในรูปแบบ JSON
            timeout=10 #--> ถ้า API ไม่ตอบใน 10 วินาที ให้หยุดรอ ป้องกันระบบค้าง
        )
        
        # แปลง Response เป็น JSON
        data = response.json()
        
        # เช็คว่า API ตอบกลับสำเร็จไหม
        if data.get("statusCode") == 200 and data.get("result"): #--> statusCode = 200 API ทำงานสำเร็จ , result มีข้อมูลอยู่ → มีใบเสร็จในระบบ
            print(f"Invoice Result: {data['result']}")
            print(f"Type: {type(data['result'])}")
            return data["result"]  # return ทั้ง InvoiceNo และ InvoiceUrl ถ้าผ่านทั้ง 2 อย่าง → return data["result"] ทั้ง list กลับไปค่ะ ซึ่งอาจมีใบเสร็จมากกว่า 1 ใบ
        else:
            print(f"API Error: {data}")
            return None
    
    #--------------------------------------- Error Handling --------------------------------------
    except Exception as e:
        print(f"Invoice Service Error: {e}")
        return None
    
    # ถ้าเกิดข้อผิดพลาดอะไรก็ตาม เช่น API ล่ม หรือ Internet หลุด → `return None` เพื่อให้ `main.py` แจ้ง User ได้
    #---------------------------------------------------------------------------------------------
    
    
    #-------------------------------- Summary invoice_service.py ---------------------------------
    
    #รับ reference_no + amount จาก main.py
    #        ↓
    #เตรียม Request Body
    #        ↓
    #POST ไป API KLN
    #        ↓
    #รับ Response กลับมา
    #        ↓
    #เช็คว่าสำเร็จและมีใบเสร็จไหม
    #        ↓
    #Return list ของใบเสร็จกลับให้ main.py
    
    #---------------------------------------------------------------------------------------------
    
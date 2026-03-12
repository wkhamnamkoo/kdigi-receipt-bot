from linebot.v3.messaging import (
    MessagingApi,
    ReplyMessageRequest,#ใช้สร้าง Request สำหรับตอบกลับ
    TextMessage, #ข้อความธรรมดา
    FlexMessage,#ข้อความแบบ Custom UI มีปุ่มได้
    FlexContainer #ใช้แปลง dict เป็น Flex Object
)

#====================================== reply_message ========================================

def reply_message(line_bot_api: MessagingApi, reply_token: str, text: str): #--> ใช้ส่ง ข้อความธรรมดา กลับหา User เช่น ข้อความแจ้ง Error หรือ Welcome Message
    try:
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)]
            )
        )
    except Exception as e:
        print(f"Line Reply Error: {e}")

#==============================================================================================


#======================================= reply_invoice ========================================

def reply_invoice(line_bot_api: MessagingApi, reply_token: str, result: list): #--> ใช้ส่ง Flex Message กลับหา User โดยวน Loop สร้าง Bubble ทีละใบเสร็จ
    try:
        bubbles = []
        for i, item in enumerate(result):
            invoice_no = item.get("InvoiceNo", "invoice.pdf")
            invoice_url = item.get("InvoiceUrl", "")
            label = f"ไฟล์ที่ {i + 1}: {invoice_no}" if len(result) > 1 else invoice_no #--> ถ้ามี 1 ใบเสร็จ → แสดงชื่อไฟล์เดียว , ถ้ามี หลายใบเสร็จ → แสดง "ไฟล์ที่ 1, ไฟล์ที่ 2..."
            
            bubble = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "📄 ใบเสร็จของคุณพร้อมแล้วค่ะ",
                            "weight": "bold",
                            "size": "md",
                            "wrap": True
                        },
                        {
                            "type": "text",
                            "text": label,
                            "size": "sm",
                            "color": "#888888",
                            "wrap": True,
                            "margin": "sm"
                        }
                    ]
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#00B900",
                            "action": {
                                "type": "uri",
                                "label": "คลิกเพื่อดาวน์โหลด",
                                "uri": invoice_url
                            }
                        }
                    ]
                }
            }
            bubbles.append(bubble)
        
        flex_content = bubbles[0] if len(bubbles) == 1 else { # → Bubble เดี่ยว
            "type": "carousel",
            "contents": bubbles
        }
        
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    FlexMessage(
                        alt_text="📄 ใบเสร็จของคุณพร้อมแล้วค่ะ",
                        contents=FlexContainer.from_dict(flex_content)
                    )
                ]
            )
        )
    except Exception as e:
        print(f"Line Reply Flex Error: {e}")

def reply_info_and_invoice(line_bot_api: MessagingApi, reply_token: str, info_text: str, result: list):
    try:
        bubbles = []
        for i, item in enumerate(result):
            invoice_no = item.get("InvoiceNo", "invoice.pdf")
            invoice_url = item.get("InvoiceUrl", "")
            label = f"ไฟล์ที่ {i + 1}: {invoice_no}" if len(result) > 1 else invoice_no
            
            bubble = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "📄 ใบเสร็จของคุณพร้อมแล้วค่ะ",
                            "weight": "bold",
                            "size": "md",
                            "wrap": True
                        },
                        {
                            "type": "text",
                            "text": label,
                            "size": "sm",
                            "color": "#888888",
                            "wrap": True,
                            "margin": "sm"
                        }
                    ]
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#00B900",
                            "action": {
                                "type": "uri",
                                "label": "คลิกเพื่อดาวน์โหลด",
                                "uri": invoice_url
                            }
                        }
                    ]
                }
            }
            bubbles.append(bubble)
        
        flex_content = bubbles[0] if len(bubbles) == 1 else { # → Carousel เลื่อนซ้ายขวาได้
            "type": "carousel",
            "contents": bubbles
        }
        
        # ส่ง 2 ข้อความพร้อมกันในครั้งเดียว
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(text=info_text),# ข้อความแจ้งข้อมูล
                    FlexMessage( # Flex ใบเสร็จ
                        alt_text="📄 ใบเสร็จของคุณพร้อมแล้วค่ะ",
                        contents=FlexContainer.from_dict(flex_content)
                    )
                ]
            )
        )
    except Exception as e:
        print(f"Line Reply Error: {e}")
        
    #========================================== Summary line_service.py =========================================
    
    #reply_message()
    #→ ส่งข้อความธรรมดา (Error / Welcome)

    #reply_invoice()
    #→ ส่ง Flex Message (ใบเสร็จ)
    #- 1 ใบ → Bubble
    #- หลายใบ → Carousel

    #reply_info_and_invoice()
    #→ ส่งทั้งข้อความ + Flex พร้อมกัน
        
    #============================================================================================================
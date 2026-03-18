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
        

#=============================== push_support_reply =====================================

def push_support_reply(
    user_id: str,
    access_token: str,
    message: str = "",
    file_url: str = "",
    file_name: str = "",
    send_slip: bool = False,
    slip_b64: str = "",
    slip_url: str = ""
):
    """
    ส่ง Flex Message จาก Support Dashboard ไปหา User ค่ะ
    รองรับ: ข้อความ, ลิงก์ไฟล์, รูปสลิปเดิม — ส่งทีละ bubble หรือ carousel ค่ะ
    """
    import requests as _req

    bubbles = []

    # ── Bubble 1: ข้อความจากทีม Support ──
    if message.strip():
        bubbles.append({
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#1a1a1a",
                "paddingAll": "14px",
                "contents": [{
                    "type": "text",
                    "text": "📩 ข้อความจากทีม K-Digi",
                    "color": "#f26522",
                    "weight": "bold",
                    "size": "sm"
                }]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "16px",
                "contents": [{
                    "type": "text",
                    "text": message.strip(),
                    "wrap": True,
                    "size": "sm",
                    "color": "#333333"
                }]
            }
        })

    # ── Bubble 2: ไฟล์แนบ ──
    if file_url.strip():
        display_name = file_name.strip() if file_name.strip() else "ไฟล์จากทีม Support"
        # ตรวจประเภทไฟล์ค่ะ
        ext = file_url.rsplit(".", 1)[-1].lower() if "." in file_url else ""
        if ext in ("jpg", "jpeg", "png", "gif", "webp"):
            icon = "🖼"
            type_label = "รูปภาพ"
        elif ext == "pdf":
            icon = "📄"
            type_label = "PDF"
        elif ext in ("xlsx", "xls"):
            icon = "📊"
            type_label = "Excel"
        elif ext in ("docx", "doc"):
            icon = "📝"
            type_label = "Word"
        else:
            icon = "📎"
            type_label = "ไฟล์"

        bubbles.append({
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#1a1a1a",
                "paddingAll": "14px",
                "contents": [{
                    "type": "text",
                    "text": f"{icon} ไฟล์แนบจากทีม K-Digi",
                    "color": "#f26522",
                    "weight": "bold",
                    "size": "sm"
                }]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "16px",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "text",
                        "text": display_name,
                        "wrap": True,
                        "weight": "bold",
                        "size": "sm",
                        "color": "#222222"
                    },
                    {
                        "type": "text",
                        "text": f"ประเภท: {type_label}",
                        "size": "xs",
                        "color": "#888888"
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "12px",
                "contents": [{
                    "type": "button",
                    "style": "primary",
                    "color": "#00B900",
                    "height": "sm",
                    "action": {
                        "type": "uri",
                        "label": "คลิกเพื่อดาวน์โหลด",
                        "uri": file_url.strip()
                    }
                }]
            }
        })

    # ── Bubble 3: รูปสลิปเดิม ──
    if send_slip and slip_url.strip():
        bubbles.append({
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#1a1a1a",
                "paddingAll": "14px",
                "contents": [{
                    "type": "text",
                    "text": "🧾 สลิปที่คุณส่งมาค่ะ",
                    "color": "#f26522",
                    "weight": "bold",
                    "size": "sm"
                }]
            },
            "hero": {
                "type": "image",
                "url": slip_url.strip(),
                "size": "full",
                "aspectRatio": "3:4",
                "aspectMode": "cover"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "12px",
                "contents": [{
                    "type": "text",
                    "text": "รูปสลิปที่คุณส่งมาค่ะ",
                    "size": "xs",
                    "color": "#888888",
                    "wrap": True
                }]
            }
        })

    if not bubbles:
        return {"status": "error", "detail": "ไม่มีเนื้อหาที่จะส่งค่ะ"}

    flex_content = bubbles[0] if len(bubbles) == 1 else {
        "type": "carousel",
        "contents": bubbles
    }
    alt = "ข้อความจากทีม K-Digi Support"

    payload = {
        "to": user_id,
        "messages": [{
            "type": "flex",
            "altText": alt,
            "contents": flex_content
        }]
    }
    res = _req.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=10
    )
    return {"status": "ok"} if res.status_code == 200 else {"status": "error", "detail": res.text}

#=======================================================================================
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
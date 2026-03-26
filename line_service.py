import requests as _req
from linebot.v3.messaging import (
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer,
)


# ── Reply helpers ──────────────────────────────────────────────

def reply_message(line_bot_api: MessagingApi, reply_token: str, text: str):
    """ส่งข้อความธรรมดากลับหา User"""
    try:
        line_bot_api.reply_message(
            ReplyMessageRequest(reply_token=reply_token,
                                messages=[TextMessage(text=text)])
        )
    except Exception as e:
        print(f"Line Reply Error: {e}")


def _build_invoice_bubbles(result: list) -> list:
    """สร้าง list ของ Flex bubble จาก invoice result"""
    bubbles = []
    for i, item in enumerate(result):
        invoice_no  = item.get("InvoiceNo", "invoice.pdf")
        invoice_url = item.get("InvoiceUrl", "")
        label = f"ไฟล์ที่ {i + 1}: {invoice_no}" if len(result) > 1 else invoice_no
        bubbles.append({
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "📄 ใบเสร็จของคุณพร้อมแล้วค่ะ",
                     "weight": "bold", "size": "md", "wrap": True},
                    {"type": "text", "text": label,
                     "size": "sm", "color": "#888888", "wrap": True, "margin": "sm"},
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [{
                    "type": "button",
                    "style": "primary",
                    "color": "#00B900",
                    "action": {"type": "uri", "label": "คลิกเพื่อดาวน์โหลด",
                               "uri": invoice_url},
                }],
            },
        })
    return bubbles


def _flex_content(bubbles: list) -> dict:
    if len(bubbles) == 1:
        return bubbles[0]
    return {"type": "carousel", "contents": bubbles}


def reply_invoice(line_bot_api: MessagingApi, reply_token: str, result: list):
    """ส่ง Flex Message ใบเสร็จกลับหา User"""
    try:
        bubbles = _build_invoice_bubbles(result)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[FlexMessage(
                    alt_text="📄 ใบเสร็จของคุณพร้อมแล้วค่ะ",
                    contents=FlexContainer.from_dict(_flex_content(bubbles)),
                )],
            )
        )
    except Exception as e:
        print(f"Line Reply Flex Error: {e}")


def reply_info_and_invoice(line_bot_api: MessagingApi, reply_token: str,
                           info_text: str, result: list):
    """ส่งข้อความ + Flex ใบเสร็จพร้อมกัน"""
    try:
        bubbles = _build_invoice_bubbles(result)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(text=info_text),
                    FlexMessage(
                        alt_text="📄 ใบเสร็จของคุณพร้อมแล้วค่ะ",
                        contents=FlexContainer.from_dict(_flex_content(bubbles)),
                    ),
                ],
            )
        )
    except Exception as e:
        print(f"Line Reply Error: {e}")


# ── Push from Support Dashboard ────────────────────────────────

def push_support_reply(
    user_id: str,
    access_token: str,
    message: str = "",
    file_url: str = "",
    file_name: str = "",
    send_slip: bool = False,
    slip_url: str = "",
) -> dict:
    """ส่ง Flex Message จาก Support Dashboard ไปหา User"""
    bubbles = []

    if message.strip():
        bubbles.append(_bubble_message(message.strip()))

    if file_url.strip():
        bubbles.append(_bubble_file(file_url.strip(), file_name.strip()))

    if send_slip and slip_url.strip():
        bubbles.append(_bubble_slip(slip_url.strip()))

    if not bubbles:
        return {"status": "error", "detail": "ไม่มีเนื้อหาที่จะส่ง"}

    res = _req.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {access_token}",
                 "Content-Type": "application/json"},
        json={"to": user_id, "messages": [{
            "type": "flex",
            "altText": "ข้อความจากทีม K-Digi Support",
            "contents": _flex_content(bubbles),
        }]},
        timeout=10,
    )
    return {"status": "ok"} if res.status_code == 200 else {
        "status": "error", "detail": res.text
    }


def _header(text: str) -> dict:
    return {
        "type": "box", "layout": "vertical",
        "backgroundColor": "#1a1a1a", "paddingAll": "14px",
        "contents": [{"type": "text", "text": text,
                      "color": "#f26522", "weight": "bold", "size": "sm"}],
    }


def _bubble_message(text: str) -> dict:
    return {
        "type": "bubble", "size": "kilo",
        "header": _header("📩 ข้อความจากทีม K-Digi"),
        "body": {
            "type": "box", "layout": "vertical", "paddingAll": "16px",
            "contents": [{"type": "text", "text": text,
                          "wrap": True, "size": "sm", "color": "#333333"}],
        },
    }


def _bubble_file(file_url: str, file_name: str) -> dict:
    ext = file_url.rsplit(".", 1)[-1].lower() if "." in file_url else ""
    icons = {"pdf": ("📄", "PDF"), "xlsx": ("📊", "Excel"), "xls": ("📊", "Excel"),
             "docx": ("📝", "Word"), "doc": ("📝", "Word")}
    image_exts = {"jpg", "jpeg", "png", "gif", "webp"}
    if ext in image_exts:
        icon, type_label = "🖼", "รูปภาพ"
    else:
        icon, type_label = icons.get(ext, ("📎", "ไฟล์"))

    display_name = file_name or "ไฟล์จากทีม Support"
    return {
        "type": "bubble", "size": "kilo",
        "header": _header(f"{icon} ไฟล์แนบจากทีม K-Digi"),
        "body": {
            "type": "box", "layout": "vertical",
            "paddingAll": "16px", "spacing": "sm",
            "contents": [
                {"type": "text", "text": display_name,
                 "wrap": True, "weight": "bold", "size": "sm", "color": "#222222"},
                {"type": "text", "text": f"ประเภท: {type_label}",
                 "size": "xs", "color": "#888888"},
            ],
        },
        "footer": {
            "type": "box", "layout": "vertical", "paddingAll": "12px",
            "contents": [{"type": "button", "style": "primary", "color": "#00B900",
                          "height": "sm",
                          "action": {"type": "uri", "label": "คลิกเพื่อดาวน์โหลด",
                                     "uri": file_url}}],
        },
    }


def _bubble_slip(slip_url: str) -> dict:
    return {
        "type": "bubble", "size": "kilo",
        "header": _header("🧾 สลิปที่คุณส่งมาค่ะ"),
        "hero": {
            "type": "image", "url": slip_url,
            "size": "full", "aspectRatio": "3:4", "aspectMode": "cover",
        },
        "body": {
            "type": "box", "layout": "vertical", "paddingAll": "12px",
            "contents": [{"type": "text", "text": "รูปสลิปที่คุณส่งมาค่ะ",
                          "size": "xs", "color": "#888888", "wrap": True}],
        },
    }

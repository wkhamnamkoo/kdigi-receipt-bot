"""
setup_richmenu.py — สร้าง Rich Menu ของ K-Digi Receipt Bot
รันครั้งเดียว ไม่ต้องรันทุกครั้งที่เปิด Server

วิธีรัน:
    python setup_richmenu.py
"""
import json
import os
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

TOKEN      = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
IMAGE_PATH = "richmenu.png"

_HEADERS_JSON = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}


# ── Step 1: สร้างรูปพื้นหลัง ──────────────────────────────────

def create_image():
    print("⏳ [1/4] กำลังสร้างรูปพื้นหลัง Rich Menu...")

    W, H   = 2500, 843
    ORANGE = "#f26522"
    WHITE  = "#ffffff"
    MUTED  = "#8a93a2"
    NAVY2  = "#162338"
    NAVY3  = "#1a2d4a"

    img  = Image.new("RGB", (W, H), "#0d1b2a")
    draw = ImageDraw.Draw(img)

    # พื้นหลัง 3 ส่วน
    draw.rectangle([0,    0,    1249, H],   fill="#0d1b2a")
    draw.rectangle([1251, 0,    W,    421], fill=NAVY2)
    draw.rectangle([1251, 423,  W,    H],   fill=NAVY3)

    # เส้น Divider
    draw.rectangle([1245, 0,    1255, H],   fill=ORANGE)
    draw.rectangle([1251, 417,  W,    427], fill=ORANGE)
    draw.rectangle([0,    0,    1249,   7], fill=ORANGE)
    draw.rectangle([1255, 0,    W,      7], fill=ORANGE)

    BOLD = "fonts/Kanit-Bold.ttf"
    REG  = "fonts/Kanit-Regular.ttf"

    f_title = ImageFont.truetype(BOLD, 108)
    f_sub   = ImageFont.truetype(REG,  52)
    f_badge = ImageFont.truetype(BOLD, 48)
    f_tag   = ImageFont.truetype(BOLD, 38)

    def ctext(text, font, color, cx, cy):
        bb = draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.text((cx - tw // 2, cy - th // 2), text, font=font, fill=color)

    def icon_circle(cx, cy, r, fill, label, label_font, label_color):
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
        ctext(label, label_font, label_color, cx, cy)

    # ซ้าย: ขอใบเสร็จ
    cx = 624
    icon_circle(cx, 270, 90, ORANGE, "PDF", f_tag, WHITE)
    ctext("ขอใบเสร็จ",           f_title, WHITE, cx, 450)
    ctext("E-Payment  /  K-Pass", f_sub,  MUTED, cx, 558)
    draw.rounded_rectangle([cx - 200, 615, cx + 200, 685], radius=40, fill=ORANGE)
    ctext("ส่งสลิปได้เลยค่ะ",   f_badge, WHITE, cx, 650)

    # ขวาบน: วิธีใช้งาน
    cx2 = 1875
    icon_circle(cx2, 115, 75, "#1e4a7a", "?", f_title, "#ffa366")
    ctext("วิธีใช้งาน",              f_title, WHITE, cx2, 258)
    ctext("ดูขั้นตอนการใช้บริการ",  f_sub,  MUTED, cx2, 360)

    # ขวาล่าง: ติดต่อ Admin
    icon_circle(cx2, 528, 75, "#1e3a2a", "TEL", f_tag, "#4ade80")
    ctext("ติดต่อ Admin",           f_title, WHITE, cx2, 672)
    ctext("จ.–ศ.  08:00–17:00 น.", f_sub,  MUTED, cx2, 772)

    img.save(IMAGE_PATH, "PNG")
    print(f"   ✅ บันทึกรูปที่ {IMAGE_PATH} ({W}x{H} px)")


# ── Step 2: สร้าง Rich Menu Layout ───────────────────────────

def create_rich_menu() -> str | None:
    print("⏳ [2/4] กำลังสร้าง Rich Menu Layout...")
    payload = {
        "size": {"width": 2500, "height": 843},
        "selected": True,
        "name": "K-Digi Main Menu",
        "chatBarText": "เมนู K-Digi ✦",
        "areas": [
            {
                "bounds": {"x": 0, "y": 0, "width": 1250, "height": 843},
                "action": {"type": "message", "label": "ขอใบเสร็จ", "text": "ขอใบเสร็จ"},
            },
            {
                "bounds": {"x": 1250, "y": 0, "width": 1250, "height": 421},
                "action": {"type": "message", "label": "วิธีใช้งาน", "text": "วิธีใช้งาน"},
            },
            {
                "bounds": {"x": 1250, "y": 421, "width": 1250, "height": 422},
                "action": {"type": "message", "label": "ติดต่อ Admin", "text": "ติดต่อ Admin"},
            },
        ],
    }
    res  = requests.post("https://api.line.me/v2/bot/richmenu",
                         headers=_HEADERS_JSON, data=json.dumps(payload))
    data = res.json()
    if "richMenuId" in data:
        print(f"   ✅ Rich Menu ID: {data['richMenuId']}")
        return data["richMenuId"]
    print(f"   ❌ ผิดพลาด: {data}")
    return None


# ── Step 3: Upload รูปพื้นหลัง ────────────────────────────────

def upload_image(rich_menu_id: str):
    print("⏳ [3/4] กำลัง Upload รูปพื้นหลัง...")
    with open(IMAGE_PATH, "rb") as f:
        res = requests.post(
            f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
            headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "image/png"},
            data=f,
        )
    if res.status_code == 200:
        print("   ✅ Upload รูปสำเร็จค่ะ")
    else:
        print(f"   ❌ Upload ผิดพลาด: {res.status_code} — {res.text}")


# ── Step 4: Set Default ───────────────────────────────────────

def set_default(rich_menu_id: str):
    print("⏳ [4/4] กำลัง Set เป็น Default Menu...")
    res = requests.post(
        f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}",
        headers=_HEADERS_JSON,
    )
    if res.status_code == 200:
        print("   ✅ Set Default สำเร็จค่ะ")
    else:
        print(f"   ❌ ผิดพลาด: {res.status_code} — {res.text}")


# ── Main ───────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 52)
    print("  K-Digi Rich Menu Setup")
    print("=" * 52)

    if not TOKEN:
        print("❌ ไม่พบ LINE_CHANNEL_ACCESS_TOKEN ใน .env ค่ะ")
        raise SystemExit(1)

    create_image()

    menu_id = create_rich_menu()
    if not menu_id:
        print("\n❌ หยุด: ไม่สามารถสร้าง Rich Menu ได้ค่ะ")
        raise SystemExit(1)

    upload_image(menu_id)
    set_default(menu_id)

    print()
    print("=" * 52)
    print(f"  🎉 Rich Menu พร้อมใช้งานแล้วค่ะ!")
    print(f"  Rich Menu ID: {menu_id}")
    print("=" * 52)

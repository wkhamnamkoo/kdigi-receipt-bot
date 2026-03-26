import os
import base64
import time
import uuid
import shutil
import sqlite3
from datetime import datetime
from collections import defaultdict
from pathlib import Path

import requests as _req
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, MessagingApiBlob
from linebot.v3.webhooks import MessageEvent, ImageMessageContent, TextMessageContent

from ocr_service import extract_slip_data
from invoice_service import get_invoice_url
from line_service import reply_message, reply_info_and_invoice, push_support_reply
from db_service import (
    init_db, migrate_db, log_to_db,
    update_invoice_no, update_status,
    update_claimed_by, update_resolution,
    get_quick_replies, add_quick_reply, update_quick_reply, delete_quick_reply,
)
from dashboard import add_dashboard_route, build_login_page
from auth import (
    init_users_table, login, logout,
    get_session_from_request, require_admin,
    create_user, get_all_users, update_user, deactivate_user,
)

load_dotenv()

# ── Constants ──────────────────────────────────────────────────
RATE_LIMIT  = 5
RATE_WINDOW = 60
UPLOAD_DIR  = Path("uploads")

RECEIPT_KEYWORDS = [
    "ใบเสร็จ", "invoice", "receipt",
    "ค่ายก", "ค่าภาระ", "e-payment", "epayment",
    "ค่าจองคิว", "k-pass", "kpass",
    "ย้อนหลัง", "ขอไฟล์", "ดาวน์โหลด", "ขอใบเสร็จ",
]
HELP_KEYWORDS  = ["วิธีใช้งาน", "วิธีใช้", "help"]
ADMIN_KEYWORDS = ["ติดต่อ admin", "ติดต่อเจ้าหน้าที่", "admin"]

HELP_MESSAGE = (
    "📋 วิธีใช้งาน K-Digi Receipt Bot ค่ะ\n\n"
    "1️⃣  ถ่ายรูปสลิปการโอนเงินค่ะ\n"
    "2️⃣  ส่งรูปสลิปมาในแชทนี้ค่ะ\n"
    "3️⃣  ระบบจะส่งใบเสร็จให้อัตโนมัติภายใน 10 วินาทีค่ะ\n\n"
    "⚠️ หมายเหตุ\n"
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

CLAIM_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>รับเคส K-Digi</title>
<script src="https://static.line-scdn.net/liff/edge/2/sdk.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:sans-serif;background:#f5f5f5;display:flex;align-items:center;
     justify-content:center;min-height:100vh;padding:20px}
.card{background:#fff;border-radius:16px;padding:32px 24px;max-width:360px;
      width:100%;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,.1)}
.avatar{width:80px;height:80px;border-radius:50%;object-fit:cover;
        margin:0 auto 12px;display:block;border:3px solid #f26522}
.name{font-size:20px;font-weight:700;color:#1a1a1a;margin-bottom:4px}
.case-id{font-size:14px;color:#888;margin-bottom:24px}
.btn{width:100%;padding:14px;border:none;border-radius:10px;font-size:16px;
     font-weight:700;cursor:pointer;font-family:inherit;transition:all .15s;margin-bottom:10px}
.btn-claim{background:#f26522;color:#fff}
.btn-claim:disabled{background:#ccc;cursor:not-allowed}
.btn-dash{background:#f5f5f5;color:#444;border:1px solid #ddd}
.st{margin-top:12px;font-size:14px;min-height:20px}
.ok{color:#27ae60;font-weight:600}.err{color:#e74c3c}
</style>
</head>
<body>
<div class="card">
  <div id="loading" class="st" style="color:#888">กำลังโหลดค่ะ...</div>
  <div id="main" style="display:none">
    <img id="av" class="avatar" src="" alt="">
    <div class="name" id="dname"></div>
    <div class="case-id" id="clabel"></div>
    <button class="btn btn-claim" id="cbtn" onclick="doClaim()">ดูเคส</button>
    <button class="btn btn-dash" onclick="openDash()">ดูรายละเอียดเคส</button>
    <div class="st" id="smsg"></div>
  </div>
</div>
<script>
var _p=null,_lid=0,_du='__DASHBOARD_URL__',_liffId='__LIFF_ID__';
async function init(){
  try{
    await liff.init({liffId:_liffId});
    if(!liff.isLoggedIn()){liff.login();return;}
    _p=await liff.getProfile();
    var q=new URLSearchParams(window.location.search);
    _lid=parseInt(q.get('log_id')||'0');
    document.getElementById('av').src=_p.pictureUrl||'';
    document.getElementById('dname').textContent=_p.displayName;
    document.getElementById('clabel').textContent=_lid?'เคส #'+_lid:'K-Digi Support';
    document.getElementById('loading').style.display='none';
    document.getElementById('main').style.display='block';
  }catch(e){document.getElementById('loading').innerHTML='<span class="err">'+e.message+'</span>';}
}
async function doClaim(){
  if(!_p||!_lid)return;
  var btn=document.getElementById('cbtn');
  var st=document.getElementById('smsg');
  btn.disabled=true;btn.textContent='กำลังรับเคส...';
  try{
    var r=await fetch('/mark-claimed',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({log_id:_lid,claimed_by:_p.displayName})});
    var d=await r.json();
    if(d.status==='ok'){
      btn.textContent='รับเคสแล้วค่ะ';btn.style.background='#27ae60';
      st.className='st ok';st.textContent='แจ้งทีมแล้วว่า '+_p.displayName+' รับเคสนี้ค่ะ';
    }else if(d.status==='already_claimed'){
      btn.textContent='มีคนรับแล้วค่ะ';btn.style.background='#888';
      st.className='st err';st.textContent=d.detail;
    }else if(d.status==='done'){
      btn.textContent='เคสสำเร็จแล้วค่ะ';btn.style.background='#27ae60';
      st.className='st ok';st.textContent='เคสแก้ไขเรียบร้อยแล้วค่ะ';
    }else{
      btn.disabled=false;btn.textContent='ดูเคส';
      st.className='st err';st.textContent=d.detail||'เกิดข้อผิดพลาดค่ะ';
    }
  }catch(e){btn.disabled=false;btn.textContent='ดูเคส';
    st.className='st err';st.textContent=e.message;}
}
function openDash(){
  var url=_du+'?open='+_lid;
  if(liff.isInClient())liff.openWindow({url:url,external:true});
  else window.open(url,'_blank');
}
init();
</script>
</body>
</html>"""

# ── App setup ──────────────────────────────────────────────────
app = FastAPI()
add_dashboard_route(app)
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

init_db()
migrate_db()
init_users_table()

handler       = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

_rate_store: dict = defaultdict(list)


# ── Helpers ────────────────────────────────────────────────────

def _get_token() -> str:
    return os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")


def _get_group_id() -> str:
    return os.getenv("LINE_SUPPORT_GROUP_ID", "")


def _dashboard_url() -> str:
    return os.getenv("DASHBOARD_URL", "http://localhost:8000/dashboard")


def _push_flex(to: str, flex_message: dict):
    _req.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {_get_token()}",
                 "Content-Type": "application/json"},
        json={"to": to, "messages": [flex_message]},
        timeout=10,
    )


def is_rate_limited(user_id: str) -> bool:
    now     = time.time()
    history = [t for t in _rate_store[user_id] if now - t < RATE_WINDOW]
    _rate_store[user_id] = history
    if len(history) >= RATE_LIMIT:
        return True
    _rate_store[user_id].append(now)
    return False


def _now_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


# ── LINE Notification helpers ──────────────────────────────────

def notify_support(message: str, log_id: int = None):
    """ส่ง Flex แจ้งเตือนกลุ่ม Support เมื่อเกิด Error"""
    group_id = _get_group_id()
    if not group_id:
        print("⚠️ ไม่พบ LINE_SUPPORT_GROUP_ID ใน .env")
        return

    claim_url = f"{_dashboard_url()}?open={log_id}" if log_id else _dashboard_url()
    flex = {
        "type": "flex",
        "altText": message[:50],
        "contents": {
            "type": "bubble", "size": "kilo",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#C0392B", "paddingAll": "12px",
                "contents": [{"type": "text", "text": "K-Digi Receipt Alert",
                              "color": "#FFFFFF", "weight": "bold", "size": "md"}],
            },
            "body": {
                "type": "box", "layout": "vertical",
                "paddingAll": "12px", "spacing": "sm",
                "contents": [
                    {"type": "text", "text": message, "wrap": True,
                     "size": "sm", "color": "#333333"},
                    {"type": "text", "text": "กดปุ่มด้านล่างเพื่อรับผิดชอบเคสนี้ค่ะ",
                     "wrap": True, "size": "xs", "color": "#888888", "margin": "sm"},
                ],
            },
            "footer": {
                "type": "box", "layout": "vertical", "paddingAll": "10px",
                "contents": [{"type": "button", "style": "primary", "color": "#F26522",
                              "height": "sm",
                              "action": {"type": "uri",
                                         "label": f"ดูเคส #{log_id}",
                                         "uri": claim_url}}],
            },
        },
    }
    try:
        _push_flex(group_id, flex)
        print("✅ แจ้งเตือน Support แล้วค่ะ")
    except Exception as e:
        print(f"⚠️ แจ้งเตือนไม่สำเร็จ: {e}")


def notify_claimed_group(log_id: int, claimed_by: str):
    group_id = _get_group_id()
    if not group_id:
        return
    flex = {
        "type": "flex",
        "altText": f"{claimed_by} กำลังดูแลเคส #{log_id} ค่ะ",
        "contents": {
            "type": "bubble", "size": "kilo",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#3a3939", "paddingAll": "12px",
                "contents": [{"type": "text", "text": "👤 มีผู้รับผิดชอบเคสแล้วค่ะ",
                              "color": "#ff8952", "weight": "bold", "size": "sm"}],
            },
            "body": {
                "type": "box", "layout": "vertical",
                "paddingAll": "14px", "spacing": "sm",
                "contents": [
                    {"type": "text", "text": f"เคส #{log_id}",
                     "weight": "bold", "size": "md", "color": "#333333"},
                    {"type": "text", "text": f"ผู้รับผิดชอบ: {claimed_by}",
                     "size": "sm", "color": "#555555", "wrap": True},
                    {"type": "text", "text": "กำลังดำเนินการแก้ไขอยู่ค่ะ",
                     "size": "xs", "color": "#888888"},
                ],
            },
        },
    }
    try:
        _push_flex(group_id, flex)
        print(f"✅ notify_claimed_group เคส #{log_id} โดย {claimed_by}")
    except Exception as e:
        print(f"notify_claimed_group error: {e}")


def notify_resolution_group(log_id: int, resolved_by: str, ref_no: str,
                             amount: float, invoice_no: str, note: str):
    group_id = _get_group_id()
    if not group_id:
        return
    lines = [f"เคส #{log_id} แก้ไขสำเร็จแล้วค่ะ", f"ผู้แก้ไข: {resolved_by}"]
    if ref_no:     lines.append(f"Ref No.: {ref_no}")
    if amount:     lines.append(f"จำนวนเงิน: {amount:,.2f} บาท")
    if invoice_no: lines.append(f"Invoice: {invoice_no}")
    if note:       lines.append(f"หมายเหตุ: {note}")

    flex = {
        "type": "flex",
        "altText": f"เคส #{log_id} แก้ไขสำเร็จแล้วค่ะ",
        "contents": {
            "type": "bubble", "size": "kilo",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#02b848", "paddingAll": "12px",
                "contents": [{"type": "text", "text": "✅ แก้ไขเคสเรียบร้อยแล้วค่ะ",
                              "color": "#FFFFFF", "weight": "bold", "size": "sm"}],
            },
            "body": {
                "type": "box", "layout": "vertical", "paddingAll": "14px",
                "contents": [{"type": "text", "text": "\n".join(lines),
                              "wrap": True, "size": "sm", "color": "#333333"}],
            },
            "footer": {
                "type": "box", "layout": "vertical", "paddingAll": "10px",
                "contents": [{"type": "button", "style": "secondary", "height": "sm",
                              "action": {"type": "uri",
                                         "label": f"ดูเคส #{log_id}",
                                         "uri": f"{_dashboard_url()}?open={log_id}"}}],
            },
        },
    }
    try:
        _push_flex(group_id, flex)
        print(f"✅ notify_resolution_group เคส #{log_id}")
    except Exception as e:
        print(f"notify_resolution_group error: {e}")


def _parse_resolution_note(raw: str, log_id: int) -> tuple[str, str]:
    """แยก note และ resolver จาก ||SESSION|| separator"""
    if "||SESSION||" in raw:
        parts = raw.split("||SESSION||", 1)
        return parts[0].strip(), parts[1].strip()
    conn = sqlite3.connect("kdigi_logs.db")
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT claimed_by FROM logs WHERE id=?", (log_id,)).fetchone()
    conn.close()
    resolver = row["claimed_by"] if row and row["claimed_by"] else "ทีม Support"
    return raw.strip(), resolver


def _build_flex_bubbles(result: list) -> list:
    bubbles = []
    for i, item in enumerate(result):
        inv_no  = item.get("InvoiceNo", f"Invoice {i+1}")
        inv_url = item.get("InvoiceUrl", "")
        label   = f"ไฟล์ที่ {i+1}: {inv_no}" if len(result) > 1 else inv_no
        bubbles.append({
            "type": "bubble",
            "body": {
                "type": "box", "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "📄 ใบเสร็จของคุณพร้อมแล้วค่ะ",
                     "weight": "bold", "size": "md", "wrap": True},
                    {"type": "text", "text": label,
                     "size": "sm", "color": "#888888", "wrap": True, "margin": "sm"},
                ],
            },
            "footer": {
                "type": "box", "layout": "vertical",
                "contents": [{"type": "button", "style": "primary", "color": "#00B900",
                              "action": {"type": "uri",
                                         "label": "คลิกเพื่อดาวน์โหลด", "uri": inv_url}}],
            },
        })
    return bubbles


def _parse_line_error(res) -> str:
    try:
        msg = res.json().get("message", res.text)
    except Exception:
        msg = res.text
    if "monthly limit" in msg.lower():
        return "LINE API quota หมดแล้วค่ะ (monthly limit) — กรุณาติดต่อทีม IT ค่ะ"
    if "invalid user id" in msg.lower():
        return "LINE User ID ไม่ถูกต้องค่ะ"
    return msg


def _save_slip_to_file(log_id: int) -> str:
    conn = sqlite3.connect("kdigi_logs.db")
    row  = conn.execute("SELECT slip_image_b64 FROM logs WHERE id=?", (log_id,)).fetchone()
    conn.close()
    if not (row and row[0]):
        return ""
    slip_path = UPLOAD_DIR / f"slip_{log_id}.jpg"
    slip_path.write_bytes(base64.b64decode(row[0]))
    base_url = _dashboard_url().rsplit("/dashboard", 1)[0]
    return f"{base_url}/uploads/{slip_path.name}"


def _record_resolution(log_id: int, raw_note: str):
    try:
        note, resolver = _parse_resolution_note(raw_note, log_id)
        conn = sqlite3.connect("kdigi_logs.db")
        conn.execute(
            "UPDATE logs SET resolved_by=?, status=? WHERE id=?",
            (resolver, "✅ สำเร็จ (Support)", log_id),
        )
        conn.commit()
        conn.close()
        update_resolution(log_id, resolver, note or "Support ส่ง Invoice ให้ User แล้วค่ะ")
        notify_resolution_group(log_id, resolver, "", 0, "", note)
    except Exception as e:
        print(f"reply-user resolution: {e}")


# ── Pydantic models ────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreateRequest(BaseModel):
    username:     str
    password:     str
    display_name: str
    role:         str = "support"

class UserUpdateRequest(BaseModel):
    user_id:      int
    display_name: str
    role:         str
    is_active:    int
    new_password: str = ""

class ReplyRequest(BaseModel):
    user_id:         str
    message:         str  = ""
    file_url:        str  = ""
    file_name:       str  = ""
    send_slip:       bool = False
    log_id:          int  = 0
    resolution_note: str  = ""

class MarkClaimedRequest(BaseModel):
    log_id:     int
    claimed_by: str

class ManualSearchRequest(BaseModel):
    ref_no:  str
    amount:  float
    user_id: str
    log_id:  int = 0

class ManualSendRequest(BaseModel):
    ref_no:          str
    amount:          float = 0
    user_id:         str
    log_id:          int  = 0
    slip_type:       str  = ""
    resolution_note: str  = ""


# ── Auth Endpoints ─────────────────────────────────────────────

@app.get("/login")
async def login_page(request: Request):
    if get_session_from_request(request):
        next_url = request.query_params.get("next", "/dashboard")
        return RedirectResponse(url=next_url, status_code=302)
    return HTMLResponse(content=build_login_page())


@app.post("/auth/login")
async def auth_login(req: LoginRequest):
    token = login(req.username.strip(), req.password)
    if not token:
        return JSONResponse(status_code=401,
                            content={"status": "error",
                                     "detail": "username หรือ password ไม่ถูกต้องค่ะ"})
    resp = JSONResponse(content={"status": "ok"})
    resp.set_cookie(key="kdigi_token", value=token,
                    httponly=True, max_age=28800, samesite="lax")
    return resp


@app.post("/auth/logout")
async def auth_logout(request: Request):
    logout(request.cookies.get("kdigi_token", ""))
    resp = JSONResponse(content={"status": "ok"})
    resp.delete_cookie("kdigi_token")
    return resp


@app.get("/auth/me")
async def auth_me(request: Request):
    session = get_session_from_request(request)
    if not session:
        return JSONResponse(status_code=401, content={"status": "error"})
    return {"username": session["username"],
            "display_name": session["display_name"],
            "role": session["role"]}


# ── Admin User Management ──────────────────────────────────────

def _require_admin_or_403(request: Request):
    if not require_admin(request):
        return JSONResponse(status_code=403,
                            content={"status": "error", "detail": "ไม่มีสิทธิ์ค่ะ"})
    return None


@app.get("/admin/users")
async def admin_get_users(request: Request):
    if (err := _require_admin_or_403(request)): return err
    return {"users": get_all_users()}


@app.post("/admin/users/create")
async def admin_create_user(req: UserCreateRequest, request: Request):
    if (err := _require_admin_or_403(request)): return err
    if not req.username.strip() or not req.password.strip() or not req.display_name.strip():
        return {"status": "error", "detail": "กรุณากรอกข้อมูลให้ครบค่ะ"}
    return create_user(req.username.strip(), req.password, req.display_name.strip(), req.role)


@app.post("/admin/users/update")
async def admin_update_user(req: UserUpdateRequest, request: Request):
    if (err := _require_admin_or_403(request)): return err
    return update_user(req.user_id, req.display_name, req.role,
                       req.is_active, req.new_password)


@app.post("/admin/users/deactivate")
async def admin_deactivate_user(request: Request):
    if (err := _require_admin_or_403(request)): return err
    body    = await request.json()
    user_id = body.get("user_id")
    session = get_session_from_request(request)
    if session and user_id == session["user_id"]:
        return {"status": "error", "detail": "ไม่สามารถลบบัญชีตัวเองได้ค่ะ"}
    return deactivate_user(user_id)


# ── LINE Webhook ───────────────────────────────────────────────

@app.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body      = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return {"status": "ok"}


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    if hasattr(event.source, "group_id"):
        print(f"🔍 Group ID: {event.source.group_id}")
        if event.source.group_id == _get_group_id():
            return

    text        = event.message.text.strip().lower()
    reply_token = event.reply_token

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        if any(kw in text for kw in ADMIN_KEYWORDS):
            reply_message(line_bot_api, reply_token, ADMIN_MESSAGE)
        elif any(kw in text for kw in HELP_KEYWORDS):
            reply_message(line_bot_api, reply_token, HELP_MESSAGE)
        elif any(kw in text for kw in RECEIPT_KEYWORDS):
            reply_message(line_bot_api, reply_token,
                          "กรุณาส่งภาพสลิปการชำระเงินมาให้ระบบตรวจสอบค่ะ")
        else:
            reply_message(line_bot_api, reply_token, WELCOME_MESSAGE)


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):
    if hasattr(event.source, "group_id"):
        if event.source.group_id == _get_group_id():
            return

    message_id  = event.message.id
    reply_token = event.reply_token
    user_id     = event.source.user_id

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        blob_api     = MessagingApiBlob(api_client)

        if is_rate_limited(user_id):
            log_to_db(user_id, status="⚠️ Rate Limited")
            reply_message(line_bot_api, reply_token,
                          "⚠️ ท่านส่งสลิปถี่เกินไปค่ะ\n"
                          "กรุณารอ 1 นาที แล้วลองใหม่อีกครั้งนะคะ 🙏")
            return

        image_bytes    = blob_api.get_message_content(message_id)
        slip_image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        slip_data      = extract_slip_data(image_bytes)

        if not slip_data:
            log_to_db(user_id, status="✅ สำเร็จ", slip_image_b64=slip_image_b64)
            reply_message(line_bot_api, reply_token,
                          "❌ ไม่สามารถอ่านข้อมูลจากสลิปได้\nกรุณาส่งรูปสลิปที่ชัดเจนค่ะ")
            return

        if slip_data.get("error") == "not_kerry":
            log_to_db(user_id, status="✅ สำเร็จ",
                      ocr_text=slip_data.get("ocr_text", ""),
                      slip_image_b64=slip_image_b64)
            reply_message(line_bot_api, reply_token,
                          "❌ ไม่พบข้อมูลการชำระเงินในสลิปนี้ค่ะ\n"
                          "กรุณาแนบสลิปที่มีข้อมูลต่อไปนี้เท่านั้นค่ะ\n\n"
                          "✅ โอนเงินให้ KERRY SIAM SEAPORT LIMITED\n"
                          "✅ มีหมายเลข E-Payment หรือ K-Pass 12 หลัก\n\n"
                          "หากมีข้อสงสัย กรุณาติดต่อ Admin K-Digi ค่ะ")
            return

        if slip_data.get("error") == "no_reference":
            lid = log_to_db(user_id, status="❌ หา Ref No. ไม่เจอ",
                            ocr_text=slip_data.get("ocr_text", ""),
                            slip_image_b64=slip_image_b64)
            notify_support(
                f"#{lid} ⚠️ AI อ่านหมายเลขอ้างอิงไม่ได้ค่ะ\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"👤 User: {user_id[:33]}\n"
                f"🕐 เวลา: {_now_str()}\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"📄 OCR: {slip_data.get('ocr_text','')[:300]}\n"
                f"⚠️ สลิปเป็น KERRY แต่หา Ref No. ไม่พบค่ะ",
                log_id=lid,
            )
            reply_message(line_bot_api, reply_token,
                          "❌ ไม่สามารถอ่านข้อมูลจากสลิปได้\n"
                          "กรุณาส่งใหม่อีกครั้ง หรือติดต่อ Admin K-Digi ค่ะ")
            return

        invoice_result = get_invoice_url(slip_data["bankTransactionNo"], slip_data["amount"])
        if not invoice_result:
            lid = log_to_db(
                user_id,
                slip_type=slip_data.get("slip_type", ""),
                ref_no=slip_data.get("bankTransactionNo", ""),
                amount=slip_data.get("amount"),
                status="❌ ไม่พบใบเสร็จใน API",
                ocr_text=slip_data.get("ocr_text", ""),
                slip_image_b64=slip_image_b64,
            )
            notify_support(
                f"#{lid} ⚠️ ไม่พบใบเสร็จในเซิร์ฟเวอร์ค่ะ\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"👤 User: {user_id[:33]}\n"
                f"🕐 เวลา: {_now_str()}\n"
                f"🔢 Ref No: {slip_data.get('bankTransactionNo', '-')}\n"
                f"💰 ยอดเงิน: {slip_data.get('amount', '-')} บาท\n"
                f"📋 ประเภท: {slip_data.get('slip_type', '-')}\n"
                f"⚠️ OCR อ่านได้ แต่ไม่พบใบเสร็จใน KLN API",
                log_id=lid,
            )
            reply_message(line_bot_api, reply_token,
                          "กำลังตรวจสอบข้อมูล กรุณารอเจ้าหน้าที่ติดต่อกลับค่ะ")
            return

        # สำเร็จ
        ref_no     = slip_data.get("bankTransactionNo", "")
        amount     = slip_data.get("amount", "")
        slip_type  = slip_data.get("slip_type", "Payment")
        invoice_no = ", ".join(i["InvoiceNo"] for i in invoice_result)

        log_to_db(user_id, slip_type=slip_type, ref_no=ref_no, amount=amount,
                  status="✅ สำเร็จ", invoice_no=invoice_no,
                  ocr_text=slip_data.get("ocr_text", ""),
                  slip_image_b64=slip_image_b64)

        reply_info_and_invoice(line_bot_api, reply_token,
                               f"📋 รายการ {slip_type} ของคุณคือ\n\n"
                               f"หมายเลขอ้างอิง: {ref_no}\n"
                               f"จำนวนเงิน: {amount} บาท",
                               invoice_result)


# ── File Upload / Support Reply ────────────────────────────────

@app.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    ext       = Path(file.filename).suffix.lower()
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest      = UPLOAD_DIR / safe_name
    with dest.open("wb") as f_out:
        shutil.copyfileobj(file.file, f_out)
    base_url = _dashboard_url().rsplit("/dashboard", 1)[0]
    return {"status": "ok",
            "file_url": f"{base_url}/uploads/{safe_name}",
            "file_name": file.filename}


@app.post("/reply-user")
async def reply_user(req: ReplyRequest):
    token = _get_token()
    if not req.user_id:
        return {"status": "error", "detail": "user_id ว่างค่ะ"}
    if not req.message.strip() and not req.file_url.strip() and not req.send_slip:
        return {"status": "error", "detail": "กรุณาพิมพ์ข้อความ หรือแนบไฟล์ หรือเลือกส่งสลิปค่ะ"}

    try:
        if not req.file_url.strip() and not req.send_slip and req.message.strip():
            res = _req.post(
                "https://api.line.me/v2/bot/message/push",
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"},
                json={"to": req.user_id,
                      "messages": [{"type": "text", "text": req.message.strip()}]},
                timeout=10,
            )
            if res.status_code == 200:
                print(f"✅ ส่ง Text ถึง {req.user_id[:20]} แล้วค่ะ")
                if req.log_id:
                    _record_resolution(req.log_id, req.resolution_note)
                return {"status": "ok"}
            return {"status": "error", "detail": _parse_line_error(res)}

        slip_url = ""
        if req.send_slip and req.log_id:
            slip_url = _save_slip_to_file(req.log_id)

        result = push_support_reply(
            user_id=req.user_id, access_token=token,
            message=req.message, file_url=req.file_url,
            file_name=req.file_name, send_slip=req.send_slip, slip_url=slip_url,
        )

        if result["status"] == "ok" and req.log_id:
            _record_resolution(req.log_id, req.resolution_note)

        return result

    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ── Other Endpoints ────────────────────────────────────────────

@app.get("/claim")
async def claim_page():
    liff_id = os.getenv("LIFF_ID", "2009546845-XvhzMBrK")
    html = (CLAIM_HTML_TEMPLATE
            .replace("__LIFF_ID__", liff_id)
            .replace("__DASHBOARD_URL__", _dashboard_url()))
    return HTMLResponse(content=html)


# ── Quick Replies API ─────────────────────────────────────────

@app.get("/quick-replies")
async def api_get_quick_replies():
    """ดึง Quick Reply ทั้งหมดค่ะ"""
    return {"status": "ok", "data": get_quick_replies()}


class QrRequest(BaseModel):
    text: str = ""


class QrUpdateRequest(BaseModel):
    id:   int
    text: str = ""


@app.post("/quick-replies")
async def api_add_quick_reply(req: QrRequest):
    """เพิ่ม Quick Reply ค่ะ"""
    if not req.text.strip():
        return {"status": "error", "detail": "กรุณาพิมพ์ข้อความค่ะ"}
    return add_quick_reply(req.text)


@app.put("/quick-replies")
async def api_update_quick_reply(req: QrUpdateRequest):
    """แก้ไข Quick Reply ค่ะ"""
    if not req.text.strip():
        return {"status": "error", "detail": "กรุณาพิมพ์ข้อความค่ะ"}
    return update_quick_reply(req.id, req.text)


@app.delete("/quick-replies/{qr_id}")
async def api_delete_quick_reply(qr_id: int):
    """ลบ Quick Reply ค่ะ"""
    return delete_quick_reply(qr_id)

#══════════════════════════════════════════════════════════════

@app.get("/slip-image/{log_id}")
async def get_slip_image(log_id: int):
    try:
        conn = sqlite3.connect("kdigi_logs.db")
        row  = conn.execute("SELECT slip_image_b64 FROM logs WHERE id=?", (log_id,)).fetchone()
        conn.close()
        return JSONResponse({"b64": row[0] if row and row[0] else ""})
    except Exception as e:
        return JSONResponse({"b64": "", "error": str(e)})


@app.post("/mark-claimed")
async def mark_claimed(req: MarkClaimedRequest):
    if not req.claimed_by.strip():
        return {"status": "error", "detail": "ไม่มีชื่อค่ะ"}
    name = req.claimed_by.strip()
    try:
        conn = sqlite3.connect("kdigi_logs.db")
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status, claimed_by FROM logs WHERE id=?", (req.log_id,)
        ).fetchone()
        conn.close()
        if row:
            if "สำเร็จ (Support)" in (row["status"] or ""):
                return {"status": "done", "detail": "เคสนี้แก้ไขเรียบร้อยแล้วค่ะ",
                        "claimed_by": row["claimed_by"]}
            if row["claimed_by"]:
                return {"status": "already_claimed",
                        "detail": f"{row['claimed_by']} รับเคสนี้ไปแล้วค่ะ",
                        "claimed_by": row["claimed_by"]}
    except Exception as e:
        print(f"mark_claimed check error: {e}")

    update_claimed_by(req.log_id, name)
    notify_claimed_group(req.log_id, name)
    return {"status": "ok", "claimed_by": name}


@app.post("/manual-search")
async def manual_search(req: ManualSearchRequest):
    if not req.ref_no.strip():
        return {"status": "error", "detail": "กรุณาระบุ Ref No. ค่ะ"}
    try:
        result = get_invoice_url(req.ref_no.strip(), req.amount)
        if not result:
            return {"status": "not_found", "detail": "ไม่พบใบเสร็จในระบบค่ะ"}
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/manual-send-invoice")
async def manual_send_invoice(req: ManualSendRequest):
    if not req.ref_no.strip():
        return {"status": "error", "detail": "กรุณาระบุ Ref No. ค่ะ"}

    try:
        result = get_invoice_url(req.ref_no.strip(), req.amount)
        if not result:
            return {"status": "not_found", "detail": "ไม่พบใบเสร็จในระบบค่ะ"}

        bubbles = _build_flex_bubbles(result)
        flex_content = bubbles[0] if len(bubbles) == 1 else {
            "type": "carousel", "contents": bubbles
        }

        res = _req.post(
            "https://api.line.me/v2/bot/message/push",
            headers={"Authorization": f"Bearer {_get_token()}",
                     "Content-Type": "application/json"},
            json={"to": req.user_id, "messages": [{
                "type": "flex",
                "altText": "📄 ใบเสร็จของคุณพร้อมแล้วค่ะ",
                "contents": flex_content,
            }]},
            timeout=10,
        )

        if res.status_code != 200:
            return {"status": "error", "detail": _parse_line_error(res)}

        print(f"✅ ส่งใบเสร็จ manual ถึง {req.user_id[:20]} แล้วค่ะ")
        inv_nos_str  = ", ".join(i.get("InvoiceNo", "") for i in result)
        inv_nos_list = [i.get("InvoiceNo", "") for i in result]

        if req.log_id:
            update_invoice_no(req.log_id, inv_nos_str)
            update_status(req.log_id, "✅ สำเร็จ (Support)")

            conn = sqlite3.connect("kdigi_logs.db")
            conn.execute("UPDATE logs SET ref_no=?, amount=? WHERE id=?",
                         (req.ref_no, req.amount, req.log_id))
            conn.commit()
            conn.close()

            try:
                note, resolver = _parse_resolution_note(
                    req.resolution_note or "", req.log_id
                )
                auto_note = (
                    f"สาเหตุ: Bot อ่าน Ref No./Amount ไม่ถูกต้อง\n"
                    f"วิธีแก้: Support ตรวจสอบสลิปและกรอก Ref No.+Amount ที่ถูกต้อง\n"
                    f"Ref No.: {req.ref_no}\n"
                    f"จำนวนเงิน: {req.amount:,.2f} บาท\n"
                    f"Invoice: {inv_nos_str}"
                )
                full_note = auto_note + (f"\nหมายเหตุเพิ่มเติม: {note}" if note else "")
                update_resolution(req.log_id, resolver, full_note)
                notify_resolution_group(req.log_id, resolver, req.ref_no,
                                        req.amount, inv_nos_str, note)
            except Exception as e:
                print(f"resolution record error: {e}")

        return {"status": "ok", "invoice_count": len(result),
                "invoice_nos": inv_nos_list,
                "ref_no": req.ref_no, "amount": req.amount}

    except Exception as e:
        return {"status": "error", "detail": str(e)}

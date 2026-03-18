import sqlite3
import io
import csv
import json
from datetime import datetime
from urllib.parse import urlencode
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

DB_PATH = "kdigi_logs.db"

# ══════════════════════════════════════════════════════════════
# Database
# ══════════════════════════════════════════════════════════════

def get_logs(date_from=None, date_to=None, search=None, status_filter=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    conds, params = [], []
    if date_from:
        conds.append("DATE(timestamp) >= ?"); params.append(date_from)
    if date_to:
        conds.append("DATE(timestamp) <= ?"); params.append(date_to)
    if search:
        conds.append("(ref_no LIKE ? OR user_id LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]
    _URGENT_LIST = ["OCR อ่านไม่ได้", "หา Ref No. ไม่เจอ", "ไม่พบใบเสร็จใน API"]
    if status_filter == "success":
        conds.append("status LIKE '%สำเร็จ%'")
    elif status_filter == "urgent":
        ukw = " OR ".join([f"status LIKE '%{k}%'" for k in _URGENT_LIST])
        conds.append(f"({ukw})")
        conds.append("(status NOT LIKE '%สำเร็จ%' AND status NOT LIKE '%แก้ไขแล้ว%')")
    elif status_filter == "error":
        ukw_not = " AND ".join([f"status NOT LIKE '%{k}%'" for k in _URGENT_LIST])
        conds.append(f"(status NOT LIKE '%สำเร็จ%' AND status NOT LIKE '%แก้ไขแล้ว%' AND {ukw_not})")
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    cur.execute(f"SELECT * FROM logs {where} ORDER BY id DESC", params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_chart_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT DATE(timestamp) AS day,
               SUM(CASE WHEN status LIKE '%สำเร็จ%' THEN 1 ELSE 0 END) AS success,
               SUM(CASE WHEN status NOT LIKE '%สำเร็จ%' THEN 1 ELSE 0 END) AS error
        FROM logs WHERE timestamp >= DATE('now', '-6 days')
        GROUP BY DATE(timestamp) ORDER BY day ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


# ══════════════════════════════════════════════════════════════
# CSS — KLN Brand (matches company system)
# ══════════════════════════════════════════════════════════════

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --kln-dark:#2d2d2d; --kln-orange:#f26522; --kln-orange-hv:#d4541a;
  --kln-orange-lt:#fff3ed; --bg:#f0f0f0; --white:#fff;
  --border:#d0d0d0; --border-lt:#ebebeb;
  --text:#2d2d2d; --text2:#555; --text3:#888;
  --green:#27ae60; --green-bg:#eaf7ed;
  --red:#c0392b; --red-bg:#fdecea;
  --font:'Sarabun','Tahoma',sans-serif; --mono:'Courier New',monospace;
  --radius:4px; --shadow:0 1px 4px rgba(0,0,0,.12);
}
html{font-size:13px}
body{font-family:var(--font);background:var(--bg);color:var(--text);min-height:100vh;line-height:1.5}

/* Topnav */
.topnav{background:var(--kln-dark);height:54px;display:flex;align-items:center;
  justify-content:space-between;padding:0 24px;border-bottom:3px solid var(--kln-orange)}
.topnav-brand{font-size:20px;font-weight:700;color:var(--kln-orange);font-style:italic;letter-spacing:.3px}
.topnav-right{display:flex;align-items:center;gap:14px;font-size:12px;color:#aaa}
.topnav-right .sep{color:#555}
.live-dot{display:inline-flex;align-items:center;gap:5px;color:#6fcf97;font-size:11px;font-weight:600}
.live-dot::before{content:'';width:7px;height:7px;background:#6fcf97;border-radius:50%;
  box-shadow:0 0 6px #6fcf97;animation:lp 1.8s infinite}
@keyframes lp{0%,100%{opacity:1}50%{opacity:.3}}

/* Subnav */
.subnav{background:var(--white);border-bottom:1px solid var(--border);padding:0 24px;
  height:40px;display:flex;align-items:center;justify-content:space-between;box-shadow:var(--shadow)}
.subnav-title{font-size:13px;font-weight:600;color:var(--text2);display:flex;align-items:center;gap:8px}
.subnav-title::before{content:'';width:3px;height:16px;background:var(--kln-orange);border-radius:2px}
.subnav-right{font-size:11px;color:var(--text3);display:flex;align-items:center;gap:8px}

/* Main */
main{padding:20px 24px 80px}

/* Page title */
.page-title-bar{margin-bottom:18px;padding-bottom:12px;border-bottom:2px solid var(--kln-orange);
  display:flex;align-items:flex-end;justify-content:space-between}
.page-title{font-size:18px;font-weight:700;color:var(--kln-orange)}
.page-sub{font-size:11px;color:var(--text3);margin-top:2px}
.page-actions{display:flex;gap:8px;align-items:center}

/* Buttons */
.btn{display:inline-flex;align-items:center;gap:5px;border:1px solid transparent;
  border-radius:var(--radius);padding:6px 14px;font-size:12px;font-weight:600;
  font-family:var(--font);cursor:pointer;transition:all .15s;text-decoration:none;white-space:nowrap}
.btn-orange{background:var(--kln-orange);color:#fff;border-color:var(--kln-orange)}
.btn-orange:hover{background:var(--kln-orange-hv);border-color:var(--kln-orange-hv)}
.btn-green{background:var(--green);color:#fff;border-color:var(--green)}
.btn-green:hover{background:#219a52;border-color:#219a52}
.btn-dark{background:var(--kln-dark);color:#fff;border-color:var(--kln-dark)}
.btn-dark:hover{background:#444;border-color:#444}
.btn-outline{background:var(--white);color:var(--text2);border-color:var(--border)}
.btn-outline:hover{background:#f5f5f5}
.btn-sm{padding:4px 10px;font-size:11px}

/* KPI */
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}
.kpi-card{background:var(--white);border:1px solid var(--border);
  border-top:3px solid var(--kln-orange);border-radius:var(--radius);
  padding:14px 18px;box-shadow:var(--shadow);display:flex;align-items:center;gap:14px}
.kpi-card.c-green{border-top-color:var(--green)}
.kpi-card.c-red{border-top-color:var(--red)}
.kpi-card.c-gray{border-top-color:#888}
.kpi-icon{width:40px;height:40px;border-radius:8px;background:var(--kln-orange-lt);
  display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}
.kpi-card.c-green .kpi-icon{background:var(--green-bg)}
.kpi-card.c-red .kpi-icon{background:var(--red-bg)}
.kpi-card.c-gray .kpi-icon{background:#f5f5f5}
.kpi-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--text3);margin-bottom:2px}
.kpi-value{font-size:24px;font-weight:700;color:var(--text);line-height:1.1}
.kpi-card.c-green .kpi-value{color:var(--green)}
.kpi-card.c-red .kpi-value{color:var(--red)}
.kpi-sub{font-size:11px;color:var(--text3);margin-top:1px}
.kpi-bar-wrap{margin-top:6px;background:var(--border-lt);border-radius:2px;height:4px}
.kpi-bar{height:100%;border-radius:2px;background:var(--kln-orange);transition:width .6s}

/* Filter */
.filter-panel{background:var(--white);border:1px solid var(--border);border-radius:var(--radius);
  padding:14px 18px;margin-bottom:16px;box-shadow:var(--shadow)}
.filter-row{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px}
.fg{display:flex;flex-direction:column;gap:4px}
.fl{font-size:11px;font-weight:600;color:var(--text2)}
.fi{border:1px solid var(--border);border-radius:var(--radius);padding:5px 9px;
  font-family:var(--font);font-size:12px;color:var(--text);background:var(--white);
  min-width:110px;transition:border-color .15s}
.fi:focus{outline:none;border-color:var(--kln-orange);box-shadow:0 0 0 2px rgba(242,101,34,.1)}
.fdiv{width:1px;height:28px;background:var(--border-lt);align-self:flex-end}
.fresult{font-size:11px;color:var(--text3);align-self:flex-end}

/* Table toolbar */
.table-toolbar{background:var(--white);border:1px solid var(--border);border-bottom:none;
  border-radius:var(--radius) var(--radius) 0 0;padding:8px 12px;
  display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px}
.tl{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.tr{display:flex;align-items:center;gap:8px}
.section-title{font-size:12px;font-weight:700;color:var(--text2)}
.row-count{font-size:11px;color:var(--text3);background:#f5f5f5;
  border:1px solid var(--border);padding:2px 7px;border-radius:3px}
.timer-lbl{font-size:11px;color:var(--text3)}

/* Table */
.table-box{background:var(--white);border:1px solid var(--border);
  border-radius:0 0 var(--radius) var(--radius);overflow:hidden;overflow-x:auto;box-shadow:var(--shadow)}
table{width:100%;border-collapse:collapse;font-size:12px}
thead{background:var(--kln-dark)}
th{padding:9px 12px;text-align:left;font-size:11px;font-weight:600;color:#e0e0e0;
  white-space:nowrap;border-right:1px solid #444;letter-spacing:.2px}
th:last-child{border-right:none}
td{padding:8px 12px;border-bottom:1px solid var(--border-lt);vertical-align:middle;
  color:var(--text);transition:background .1s}
tr:last-child td{border-bottom:none}
tr:nth-child(even) td{background:#fafafa}
tr.crow{cursor:pointer}
tr.crow:hover td{background:var(--kln-orange-lt) !important}
tr.erow td:first-child{border-left:3px solid var(--red)}
tr.srow td:first-child{border-left:3px solid var(--green)}
tr.erow td{background:#fff8f8}
tr.erow:nth-child(even) td{background:#fff5f5}
tr.urow td{background:#fff8f0}
tr.urow:nth-child(even) td{background:#fff3e8}
tr.urow td:first-child{border-left:4px solid var(--kln-orange)}
tr.urow:hover td{background:#ffe0c0 !important}
.badge-urgent{display:inline-flex;align-items:center;gap:3px;padding:2px 8px;border-radius:3px;font-size:10px;font-weight:700;background:#fff0e0;color:#c0510b;border:1px solid #ffb366;animation:upulse 1.8s infinite}
@keyframes upulse{0%,100%{box-shadow:0 0 0 0 rgba(242,101,34,.3)}50%{box-shadow:0 0 0 3px rgba(242,101,34,.0)}}

/* Badges */
.badge{display:inline-flex;align-items:center;gap:3px;padding:2px 7px;border-radius:3px;
  font-size:10px;font-weight:700;letter-spacing:.2px}
.bok{background:var(--green-bg);color:var(--green);border:1px solid #b8e6c4}
.berr{background:var(--red-bg);color:var(--red);border:1px solid #f5c2c7}

/* Table cells */
.td-id{color:var(--text3);font-size:11px}
.td-ref{font-family:var(--mono);font-size:11px;color:var(--text2)}
.td-amt{font-family:var(--mono);font-size:11px;text-align:right}
.td-inv{font-size:11px;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text2)}
.td-ocr{font-size:11px;color:var(--text3);max-width:110px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.td-img{width:52px}
.slip-thumb{width:42px;height:30px;object-fit:cover;border-radius:3px;
  cursor:zoom-in;border:1px solid var(--border)}
.slip-thumb:hover{opacity:.8}
.no-img{font-size:10px;color:var(--text3)}

/* Empty */
.empty-state{text-align:center;padding:50px 20px;color:var(--text3)}
.empty-state .icon{font-size:36px;margin-bottom:10px}

/* ════════════════════════════════════════
   Detail Popup — KLN style
════════════════════════════════════════ */
.det-overlay{
  display:none;position:fixed;inset:0;
  background:rgba(0,0,0,.55);
  z-index:9999;align-items:center;justify-content:center;padding:20px;
}
.det-overlay.show{display:flex}

.det-popup{
  background:var(--white);border-radius:var(--radius);
  width:740px;max-width:96vw;max-height:90vh;overflow-y:auto;
  box-shadow:0 8px 40px rgba(0,0,0,.25);
  animation:popIn .18s ease;
}
@keyframes popIn{from{opacity:0;transform:scale(.97) translateY(10px)}to{opacity:1;transform:none}}

/* Popup header */
.det-hdr{background:var(--kln-dark);padding:14px 20px;
  display:flex;justify-content:space-between;align-items:center;
  border-radius:var(--radius) var(--radius) 0 0;position:sticky;top:0;z-index:5}
.det-title{font-size:14px;font-weight:700;color:var(--kln-orange);
  display:flex;align-items:center;gap:8px}
.det-sub{font-size:11px;color:#888;margin-top:3px}
.det-close{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);
  color:#ccc;width:28px;height:28px;border-radius:4px;font-size:15px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;transition:all .15s}
.det-close:hover{background:var(--red);color:#fff;border-color:var(--red)}

/* Popup body 2-col */
.det-body{display:grid;grid-template-columns:1fr 195px;border-bottom:1px solid var(--border)}
.det-info{padding:18px 20px}
.det-slip-col{padding:18px 14px;background:#f9f9f9;border-left:1px solid var(--border);
  display:flex;flex-direction:column;align-items:center;gap:8px}
.det-slip-col img{width:100%;max-width:160px;border-radius:4px;
  border:1px solid var(--border);cursor:zoom-in;
  box-shadow:var(--shadow);transition:transform .2s}
.det-slip-col img:hover{transform:scale(1.05)}
.no-slip{color:var(--text3);font-size:11px;text-align:center;padding:20px 0}

/* Info grid */
.igrid{display:grid;grid-template-columns:1fr 1fr;gap:0}
.iitem{padding:8px 0;border-bottom:1px solid var(--border-lt)}
.iitem:nth-last-child(-n+2){border-bottom:none}
.iitem.full{grid-column:1/-1}
.ikey{font-size:9px;font-weight:700;text-transform:uppercase;
  letter-spacing:.6px;color:var(--text3);margin-bottom:3px}
.ival{font-size:12px;color:var(--text);font-weight:500;word-break:break-all}
.ival.m{font-family:var(--mono);font-size:11px;color:var(--text2)}

/* Reply section */
.det-section{padding:14px 20px;border-top:1px solid var(--border-lt)}
.det-sec-title{font-size:11px;font-weight:700;color:var(--text2);
  margin-bottom:8px;display:flex;align-items:center;gap:6px;
  padding-bottom:6px;border-bottom:1px solid var(--border-lt)}
.det-ta{width:100%;border:1px solid var(--border);border-radius:var(--radius);
  padding:8px 10px;font-family:var(--font);font-size:13px;color:var(--text);
  resize:vertical;min-height:80px;transition:border-color .15s;background:var(--white)}
.det-ta:focus{outline:none;border-color:var(--kln-orange);
  box-shadow:0 0 0 2px rgba(242,101,34,.1)}
.det-ta::placeholder{color:var(--text3)}

/* Upload zone */
.uzone{border:2px dashed var(--border);border-radius:var(--radius);padding:10px 14px;
  cursor:pointer;text-align:center;font-size:12px;color:var(--text3);
  transition:all .2s;margin-top:8px;background:#fafafa}
.uzone:hover{border-color:var(--kln-orange);color:var(--kln-orange);background:var(--kln-orange-lt)}
.uzone.has-file{border-color:var(--green);color:var(--green);background:var(--green-bg);border-style:solid}
.uname{font-size:11px;margin-top:4px;font-weight:600;display:none;color:var(--green)}
.uprog{font-size:11px;margin-top:4px;display:none;color:var(--kln-orange)}

/* Slip checkbox */
.scb-row{display:flex;align-items:center;gap:8px;padding:8px 0;
  font-size:12px;color:var(--text2);cursor:pointer}
.scb-row input{accent-color:var(--kln-orange);width:14px;height:14px;cursor:pointer}

/* Popup footer */
.det-footer{padding:12px 20px;border-top:1px solid var(--border);background:#f9f9f9;
  display:flex;align-items:center;justify-content:space-between;
  border-radius:0 0 var(--radius) var(--radius);position:sticky;bottom:0}
.det-result{font-size:12px;min-height:18px}
.det-acts{display:flex;gap:8px}

/* Slip fullscreen */
.smodal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);
  z-index:10000;align-items:center;justify-content:center;padding:20px}
.smodal.show{display:flex}
.smodal-inner{background:var(--white);border-radius:var(--radius);
  padding:20px;max-width:480px;width:100%}
.smodal-label{font-size:10px;font-weight:700;text-transform:uppercase;
  letter-spacing:.6px;color:var(--text3);margin-bottom:10px}
.smodal-img{width:100%;border-radius:4px;margin-bottom:14px}
.smodal-close{width:100%;padding:8px;background:var(--kln-dark);color:#fff;
  border:none;border-radius:var(--radius);font-size:13px;cursor:pointer;font-family:var(--font)}
.smodal-close:hover{background:#444}
.msearch{background:#f5f9ff;border:1px solid #d0e4ff;border-radius:var(--radius);padding:14px 16px;margin-bottom:0}.msearch-row{display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap;margin-bottom:10px}.msearch-fg{display:flex;flex-direction:column;gap:4px;flex:1;min-width:120px}.msearch-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:#5577aa}.msearch-input{border:1px solid #bbd0f0;border-radius:var(--radius);padding:6px 9px;font-family:var(--font);font-size:12px;color:var(--text);background:#fff;width:100%}.msearch-input:focus{outline:none;border-color:var(--kln-orange);box-shadow:0 0 0 2px rgba(242,101,34,.1)}.inv-results{margin-top:10px}.inv-item{display:flex;align-items:center;justify-content:space-between;padding:8px 10px;background:#fff;border:1px solid #d0e4ff;border-radius:var(--radius);margin-bottom:6px;font-size:12px}.inv-item:last-child{margin-bottom:0}.inv-name{color:var(--text2);font-family:var(--mono);font-size:11px;flex:1}.inv-badge{background:#e8f5e9;color:var(--green);border:1px solid #b8e6c4;border-radius:3px;padding:1px 6px;font-size:10px;font-weight:700;margin-right:8px}.msearch-status{font-size:12px;margin-top:6px;min-height:18px}

/* Footer */
.footer{background:var(--kln-dark);color:#888;font-size:11px;padding:10px 24px;
  display:flex;justify-content:space-between;align-items:center;
  position:fixed;bottom:0;left:0;right:0}
.footer strong{color:var(--kln-orange)}
"""


# ══════════════════════════════════════════════════════════════
# JavaScript
# ══════════════════════════════════════════════════════════════

def build_js(error_count_val):
    js = """
var _detId=0, _detUid='', _detSlipType='', _fileUrl='', _fileName='';

function openDetail(row){
  _detId   = parseInt(row.dataset.id||0);
  _detUid       = row.dataset.uid||'';
  _detSlipType  = row.dataset.sliptype||'';
  _fileUrl = ''; _fileName = '';

  document.getElementById('d-uid').textContent = row.dataset.uid||'—';
  document.getElementById('d-ts').textContent  = row.dataset.ts||'—';
  document.getElementById('d-ref').textContent = row.dataset.ref||'—';
  document.getElementById('d-amt').textContent = row.dataset.amt||'—';
  document.getElementById('d-inv').textContent = row.dataset.inv||'—';
  document.getElementById('d-ocr').textContent = row.dataset.ocr||'—';

  var sub = document.getElementById('d-sub');
  if(sub) sub.textContent = '#'+_detId+' · '+(row.dataset.ts||'');

  var st = row.dataset.status||'';
  var ok = st.includes('สำเร็จ');
  document.getElementById('d-status').innerHTML = ok
    ? '<span class="badge bok">✓ สำเร็จ</span>'
    : '<span class="badge berr">✗ '+st.replace('❌','').trim()+'</span>';

  var sw = document.getElementById('d-slip-wrap');
  if(row.dataset.hasslip==='1'){
    sw.innerHTML = '<img id="sdimg" style="width:100%;border-radius:4px;border:1px solid #ddd;cursor:zoom-in" onclick="showSlip(this.src)">';
    fetch('/slip-image/'+_detId).then(function(r){return r.json();})
      .then(function(d){if(d.b64) document.getElementById('sdimg').src='data:image/jpeg;base64,'+d.b64;})
      .catch(function(){});
  } else {
    sw.innerHTML = '<div class="no-slip">ไม่มีรูปสลิปค่ะ</div>';
  }

  document.getElementById('d-msg').value = '';
  document.getElementById('d-result').textContent = '';
  document.getElementById('d-file').value = '';
  document.getElementById('uname').style.display = 'none';
  document.getElementById('uprog').style.display = 'none';
  document.getElementById('uzone').className = 'uzone';
  document.getElementById('send-slip-cb').checked = false;

  var btn = document.getElementById('d-send-btn');
  btn.disabled = false; btn.textContent = '📤 ส่งข้อความ';
  // reset manual search ค่ะ
  var msRef = document.getElementById('ms-ref');
  var msAmt = document.getElementById('ms-amt');
  if(msRef){ msRef.value = row.dataset.ref !== '—' ? row.dataset.ref : ''; }
  if(msAmt){ msAmt.value = row.dataset.amt ? row.dataset.amt.replace(/[^0-9.]/g,'') : ''; }
  var msSt = document.getElementById('ms-status');
  var msRes = document.getElementById('ms-results');
  var msSend = document.getElementById('ms-send-btn');
  var msBtn = document.getElementById('ms-btn');
  if(msSt) msSt.innerHTML='';
  if(msRes) msRes.innerHTML='';
  if(msSend) msSend.style.display='none';
  if(msBtn){ msBtn.disabled=false; msBtn.textContent='🔍 ค้นหา'; }

  /* ซ่อน reply block ถ้า row สำเร็จ */
  var rb = document.getElementById('d-reply-block');
  var isErr = row.dataset.iserror==='1';
  if(rb) rb.style.display = isErr ? '' : 'none';
  // ซ่อนปุ่มส่งข้อความสำหรับ success rows ค่ะ
  var sendBtn = document.getElementById('d-send-btn');
  if(sendBtn) sendBtn.style.display = isErr ? '' : 'none';

  document.getElementById('det-overlay').classList.add('show');
}

function closeDetail(){
  document.getElementById('det-overlay').classList.remove('show');
}

function sendFromDetail(){
  var msg   = document.getElementById('d-msg').value.trim();
  var slipCb= document.getElementById('send-slip-cb').checked;
  if(!msg && !_fileUrl && !slipCb){
    document.getElementById('d-result').textContent='⚠️ กรุณาพิมพ์ข้อความ หรือแนบไฟล์ หรือเลือกส่งสลิปค่ะ';
    return;
  }
  var btn = document.getElementById('d-send-btn');
  btn.disabled=true; btn.textContent='⏳ กำลังส่ง...';
  fetch('/reply-user',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({user_id:_detUid,message:msg,file_url:_fileUrl,
      file_name:_fileName,send_slip:slipCb,log_id:_detId})})
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.status==='ok'){
      document.getElementById('d-result').innerHTML='<span style="color:green">✅ ส่งสำเร็จค่ะ</span>';
      btn.textContent='✅ ส่งแล้ว'; setTimeout(closeDetail,1800);
    } else {
      document.getElementById('d-result').innerHTML='<span style="color:red">❌ '+d.detail+'</span>';
      btn.disabled=false; btn.textContent='📤 ส่งข้อความ';
    }
  }).catch(function(e){
    document.getElementById('d-result').innerHTML='<span style="color:green">❌ '+e+'</span>';
    btn.disabled=false; btn.textContent='📤 ส่งข้อความ';
  });
}

function handleFileSelect(inp){
  var f=inp.files[0]; if(!f)return;
  var zone=document.getElementById('uzone');
  var prog=document.getElementById('uprog');
  var name=document.getElementById('uname');
  prog.style.display='block'; prog.textContent='⏳ กำลังอัปโหลด...';
  var fd=new FormData(); fd.append('file',f);
  fetch('/upload-file',{method:'POST',body:fd})
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.status==='ok'){
      _fileUrl=d.file_url; _fileName=d.file_name;
      zone.className='uzone has-file';
      name.textContent='✅ '+d.file_name; name.style.display='block'; prog.style.display='none';
    } else { prog.textContent='❌ อัปโหลดไม่สำเร็จค่ะ'; }
  }).catch(function(){prog.textContent='❌ เกิดข้อผิดพลาดค่ะ';});
}

function showSlip(src){
  document.getElementById('smodal-img').src=src;
  document.getElementById('smodal').classList.add('show');
}
function doManualSearch(){
  var ref=document.getElementById('ms-ref').value.trim();
  var amt=parseFloat(document.getElementById('ms-amt').value)||0;
  if(!ref){document.getElementById('ms-status').innerHTML='<span style="color:var(--kln-orange)">⚠️ กรุณาระบุ Ref No. ค่ะ</span>';return;}
  var btn=document.getElementById('ms-btn');
  btn.disabled=true;btn.textContent='⏳ กำลังค้นหา...';
  document.getElementById('ms-status').innerHTML='<span style="color:#888">⏳ กำลังค้นหาใบเสร็จ...</span>';
  document.getElementById('ms-results').innerHTML='';
  fetch('/manual-search',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({ref_no:ref,amount:amt,user_id:_detUid,log_id:_detId})})
  .then(function(r){return r.json();})
  .then(function(d){
    btn.disabled=false;btn.textContent='🔍 ค้นหา';
    if(d.status==='ok'){
      document.getElementById('ms-status').innerHTML='<span style="color:var(--green)">✅ พบ '+d.result.length+' ใบเสร็จค่ะ</span>';
      var html='';
      d.result.forEach(function(item,i){
        html+='<div class="inv-item">'
          +'<span class="inv-badge">'+(i+1)+'</span>'
          +'<span class="inv-name">'+item.InvoiceNo+'</span>'
          +'<a href="'+item.InvoiceUrl+'" target="_blank" class="btn btn-outline btn-sm">📄 ดู</a>'
          +'</div>';
      });
      document.getElementById('ms-results').innerHTML=html;
      document.getElementById('ms-send-btn').style.display='';
    }else if(d.status==='not_found'){
      document.getElementById('ms-status').innerHTML='<span style="color:var(--red)">❌ ไม่พบใบเสร็จในระบบค่ะ</span>';
    }else{
      document.getElementById('ms-status').innerHTML='<span style="color:var(--red)">❌ '+d.detail+'</span>';
    }
  }).catch(function(e){
    btn.disabled=false;btn.textContent='🔍 ค้นหา';
    document.getElementById('ms-status').innerHTML='<span style="color:var(--red)">❌ '+e+'</span>';
  });
}
function sendManualInvoice(){
  var ref=document.getElementById('ms-ref').value.trim();
  var amt=parseFloat(document.getElementById('ms-amt').value)||0;
  if(!ref)return;
  var btn=document.getElementById('ms-send-btn');
  btn.disabled=true;btn.textContent='⏳ กำลังส่ง...';
  fetch('/manual-send-invoice',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({ref_no:ref,amount:amt,user_id:_detUid,log_id:_detId,slip_type:_detSlipType||''})})
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.status==='ok'){
      document.getElementById('ms-status').innerHTML='<span style="color:var(--green)">✅ ส่งใบเสร็จ '+d.invoice_count+' ใบให้ลูกค้าแล้วค่ะ</span>';
      if(d.invoice_nos && d.invoice_nos.length){
        var dInv=document.getElementById('d-inv');
        if(dInv) dInv.textContent=d.invoice_nos.join(', ');
      }
      btn.textContent='✅ ส่งแล้ว';
      setTimeout(closeDetail,2000);
    }else{
      document.getElementById('ms-status').innerHTML='<span style="color:var(--red)">❌ '+d.detail+'</span>';
      btn.disabled=false;btn.textContent='📤 ส่งใบเสร็จให้ลูกค้า';
    }
  }).catch(function(e){
    document.getElementById('ms-status').innerHTML='<span style="color:var(--red)">❌ '+e+'</span>';
    btn.disabled=false;btn.textContent='📤 ส่งใบเสร็จให้ลูกค้า';
  });
}
// ── เช็ค ?open=log_id แล้วเปิด Popup อัตโนมัติค่ะ ──
(function(){
  var params = new URLSearchParams(window.location.search);
  var openId = params.get('open');
  if(!openId) return;
  params.delete('open');
  var newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
  window.history.replaceState({}, '', newUrl);
  var row = document.querySelector('tr[data-id="'+openId+'"]');
  if(row){
    row.scrollIntoView({behavior:'smooth',block:'center'});
    setTimeout(function(){ openDetail(row); }, 400);
  }
})();
function markResolved(){
  var btn=document.getElementById('d-resolve-btn');
  if(!btn||btn.disabled)return;
  btn.disabled=true;btn.textContent='⏳';
  fetch('/update-resolve',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({log_id:_detId,resolve_status:'✅ แก้ไขแล้ว'})})
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.status==='ok'){
      btn.textContent='✅ แก้ไขแล้ว';
      btn.style.background='var(--green)';btn.style.color='#fff';btn.style.borderColor='var(--green)';
      document.getElementById('d-result').innerHTML='<span style="color:var(--green)">✅ บันทึกสถานะแล้วค่ะ</span>';
    }else{btn.disabled=false;btn.textContent='✅ แก้ไขแล้ว';}
  }).catch(function(){btn.disabled=false;btn.textContent='✅ แก้ไขแล้ว';});
}
function closeSlip(){
  document.getElementById('smodal').classList.remove('show');
  document.getElementById('smodal-img').src='';
}
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'){ closeSlip(); closeDetail(); }
});

function refreshPage(){
  if(document.getElementById('det-overlay').classList.contains('show'))return;
  var btn=document.getElementById('refresh-btn');
  btn.textContent='⏳'; btn.disabled=true;
  setTimeout(function(){location.reload();},300);
}

function applyFilter(){
  var p=new URLSearchParams(window.location.search);
  var df=document.getElementById('df').value;
  var dt=document.getElementById('dt').value;
  var sq=document.getElementById('sq').value;
  var sf=document.getElementById('sf') ? document.getElementById('sf').value : '';
  if(df)p.set('date_from',df); else p.delete('date_from');
  if(dt)p.set('date_to',dt);   else p.delete('date_to');
  if(sf)p.set('status_filter',sf); else p.delete('status_filter');
  if(sq)p.set('search',sq);    else p.delete('search');
  window.location.href='/dashboard?'+p.toString();
}
document.getElementById('sq').addEventListener('keydown',function(e){
  if(e.key==='Enter')applyFilter();
});

"""
    js += f"var CERR={error_count_val},CD=30;\n"
    js += """
var tel=document.getElementById('timer-text');
var tk=setInterval(function(){
  if(document.getElementById('det-overlay').classList.contains('show')){
    if(tel)tel.textContent='—'; return;
  }
  CD--; if(tel)tel.textContent=CD+'s';
  if(CD<=0){
    clearInterval(tk);
    fetch('/dashboard/error-count').then(function(r){return r.json();})
      .then(function(d){location.reload();})
      .catch(function(){location.reload();});
  }
},1000);
"""
    return js


# ══════════════════════════════════════════════════════════════
# Table rows
# ══════════════════════════════════════════════════════════════

TABLE_HEADER = (
    "<table><thead><tr>"
    "<th style='width:36px'>#</th>"
    "<th>วันที่/เวลา</th><th>LINE User ID</th><th>ประเภท</th>"
    "<th>เลขอ้างอิง</th><th style='text-align:right'>ยอดเงิน (บาท)</th>"
    "<th>สถานะ</th><th>การแก้ไข</th><th>Invoice</th><th>ข้อความ OCR</th><th>สลิป</th>"
    "</tr></thead><tbody>"
)


def build_rows(logs):
    if not logs:
        return (
            TABLE_HEADER +
            "<tr><td colspan='10'><div class='empty-state'>"
            "<div class='icon'>📭</div><div>ยังไม่มีข้อมูลในระบบค่ะ</div>"
            "</div></td></tr></tbody></table>"
        )
    rows = TABLE_HEADER
    for r in logs:
        r = dict(r)
        img_html = (
            f'<img src="data:image/jpeg;base64,{r["slip_image_b64"]}" '
            'class="slip-thumb" onclick="event.stopPropagation();showSlip(this.src)" title="ดูสลิป">'
            if r.get("slip_image_b64") else '<span class="no-img">—</span>'
        )
        status_val   = r.get("status") or ""
        resolve_val  = r.get("resolve_status") or ""
        is_ok        = "สำเร็จ" in status_val  # รวมทั้ง "✅ สำเร็จ (Support)" ค่ะ
        is_resolved  = "แก้ไขแล้ว" in resolve_val
        _URGENT_KW = ["OCR อ่านไม่ได้", "หา Ref No. ไม่เจอ", "ไม่พบใบเสร็จใน API"]
        is_urgent  = not is_ok and any(kw in status_val for kw in _URGENT_KW)
        _err_lbl   = status_val.replace('❌','').strip() or 'ERR'
        _ok_lbl    = "✓ สำเร็จ"  # status สำเร็จทุกรูปแบบค่ะ
        badge      = (
            f'<span class="badge bok">{_ok_lbl}</span>' if is_ok else
            f'<span class="badge-urgent">⚡ {_err_lbl}</span>' if is_urgent else
            f'<span class="badge berr">✗ {_err_lbl}</span>'
        )
        resolve_badge = (
            '<span style="background:#eaf7ed;color:#27ae60;border:1px solid #b8e6c4;border-radius:3px;padding:2px 7px;font-size:10px;font-weight:700">✅ แก้ไขแล้ว</span>'
            if is_resolved else
            '<span style="font-size:11px;color:#aaa">—</span>'
        )
        ref_str    = r.get("ref_no") or "—"
        amount_str = f'{r["amount"]:,.2f}' if r.get("amount") else "—"
        inv_str    = r.get("invoice_no") or "—"
        inv_short  = inv_str[:16]+"…" if len(inv_str)>16 else inv_str
        ocr_short  = (r.get("ocr_text") or "")[:32]
        uid_full   = r.get("user_id") or ""
        uid_short  = uid_full[:14]+("…" if len(uid_full)>14 else "")
        ts_esc     = (r.get("timestamp") or "—").replace("'","&apos;")
        stat_esc   = status_val.replace("'","&apos;").replace('"',"&quot;")
        ref_esc    = ref_str.replace("'","&apos;")
        amt_esc    = f'{r["amount"]:,.2f} บาท' if r.get("amount") else "—"
        inv_esc    = inv_str.replace("'","&apos;")
        ocr_esc    = (r.get("ocr_text") or "")[:200].replace("'","&apos;").replace('"',"&quot;")
        hasslip_v  = "1" if r.get("slip_image_b64") else "0"
        iserror_v  = "0" if is_ok else "1"
        row_cls    = "crow " + ("srow" if is_ok else ("urow" if is_urgent else "erow"))
        resolved_v = "1" if is_resolved else "0"

        rows += (
            f"<tr class='{row_cls}' onclick='openDetail(this)' "
            f"data-id='{r['id']}' data-uid='{uid_full}' data-ts='{ts_esc}' "
            f"data-status='{stat_esc}' data-ref='{ref_esc}' data-amt='{amt_esc}' "
            f"data-inv='{inv_esc}' data-ocr='{ocr_esc}' "
            f"data-sliptype='{(r.get('slip_type') or '').replace(chr(39), '')}' "
            f"data-iserror='{iserror_v}' data-hasslip='{hasslip_v}' data-resolved='{resolved_v}'>"
            f'<td class="td-id">{r["id"]}</td>'
            f'<td style="font-size:11px;color:#555">{r.get("timestamp") or "—"}</td>'
            f'<td class="td-ref" style="font-size:11px">{uid_short}</td>'
            f'<td style="font-size:11px;color:#666">{r.get("slip_type") or "—"}</td>'
            f'<td class="td-ref">{ref_str}</td>'
            f'<td class="td-amt">{amount_str}</td>'
            f'<td>{badge}</td>'
            f'<td>{resolve_badge}</td>'
            f'<td class="td-inv" title="{inv_str}">{inv_short}</td>'
            f'<td class="td-ocr" title="{r.get("ocr_text") or ""}">{ocr_short or "—"}</td>'
            f'<td class="td-img">{img_html}</td>'
            "</tr>"
        )
    rows += "</tbody></table>"
    return rows


# ══════════════════════════════════════════════════════════════
# HTML builder
# ══════════════════════════════════════════════════════════════

def build_html(total, success, error, rate, now, rows_html,
               chart_labels, chart_success, chart_error,
               date_from='', date_to='', is_filtered=False, search='', status_filter=''):

    kpi = (
        "<div class='kpi-grid'>"
        "<div class='kpi-card'><div class='kpi-icon'>📊</div><div>"
        "<div class='kpi-label'>รายการทั้งหมด</div>"
        f"<div class='kpi-value'>{total}</div>"
        "<div class='kpi-sub'>ทุกรายการ</div></div></div>"

        "<div class='kpi-card c-green'><div class='kpi-icon'>✅</div><div>"
        "<div class='kpi-label'>Completed</div>"
        f"<div class='kpi-value'>{success}</div>"
        "<div class='kpi-sub'>สำเร็จ</div></div></div>"

        "<div class='kpi-card c-red'><div class='kpi-icon'>⚠️</div><div>"
        "<div class='kpi-label'>Errors</div>"
        f"<div class='kpi-value'>{error}</div>"
        "<div class='kpi-sub'>ต้องตรวจสอบ</div></div></div>"

        "<div class='kpi-card c-gray'><div class='kpi-icon'>📈</div><div>"
        "<div class='kpi-label'>อัตราสำเร็จ</div>"
        f"<div class='kpi-value'>{rate}%</div>"
        "<div class='kpi-bar-wrap'>"
        f"<div class='kpi-bar' style='width:{rate}%'></div>"
        "</div></div></div>"
        "</div>"
    )

    filter_panel = (
        "<div class='filter-panel'><div class='filter-row'>"
        "<div class='fg'><div class='fl'>Start Date From</div>"
        f"<input class='fi' type='date' id='df' value='{date_from}'></div>"
        "<div class='fg'><div class='fl'>Start Date To</div>"
        f"<input class='fi' type='date' id='dt' value='{date_to}'></div>"
        "<div class='fdiv'></div>"
        "<div class='fg'><div class='fl'>สถานะ</div>"
        f"<select class='fi' id='sf' style='min-width:180px'>"
        f"<option value=''{' selected' if not status_filter else ''}>— ทั้งหมด —</option>"
        f"<option value='success'{' selected' if status_filter=='success' else ''}>✅ สำเร็จ (ทั้งหมด)</option>"
        f"<option value='urgent'{' selected' if status_filter=='urgent' else ''}>⚡ ต้องรีบแก้ไข</option>"
        f"<option value='error'{' selected' if status_filter=='error' else ''}>❌ Error ทั่วไป</option>"
        "</select></div>"
        "<div class='fdiv'></div>"
        "<div class='fg'><div class='fl'>ค้นหา (เลขอ้างอิง / User ID)</div>"
        f"<input class='fi' type='text' id='sq' placeholder='เช่น 12505000...' "
        f"value='{search}' style='min-width:190px'></div>"
        "<button class='btn btn-dark' onclick='applyFilter()'>ค้นหา</button>"
        "<a class='btn btn-outline' href='/dashboard'>รีเซ็ต</a>"
        + (f"<span class='fresult'>พบ {total} รายการ</span>" if is_filtered else '')
        + "</div></div>"
    )

    js = build_js(error)

    # Detail Popup
    detail_popup = (
        "<div class='det-overlay' id='det-overlay'>"
        "<div class='det-popup'>"

        "<div class='det-hdr'>"
        "<div><div class='det-title'>📋 รายละเอียดรายการ</div>"
        "<div class='det-sub' id='d-sub'></div></div>"
        "<button class='det-close' onclick='closeDetail()'>✕</button>"
        "</div>"

        "<div class='det-body'>"
        "<div class='det-info'><div class='igrid'>"
        "<div class='iitem'><div class='ikey'>👤 LINE User ID</div>"
        "<div class='ival m' id='d-uid'></div></div>"
        "<div class='iitem'><div class='ikey'>🕐 Timestamp</div>"
        "<div class='ival' id='d-ts'></div></div>"
        "<div class='iitem'><div class='ikey'>📌 Status</div>"
        "<div id='d-status'></div></div>"
        "<div class='iitem full'><div class='ikey'>📄 Invoice No.</div>"
        "<div class='ival m' id='d-inv'></div></div>"
        "<div class='iitem'><div class='ikey'>🔢 Reference No.</div>"
        "<div class='ival m' id='d-ref'></div></div>"
        "<div class='iitem'><div class='ikey'>💰 Amount (THB)</div>"
        "<div class='ival m' id='d-amt'></div></div>"
        "<div class='iitem full' style='border-bottom:none'><div class='ikey'>🔍 OCR Text</div>"
        "<div class='ival' id='d-ocr' style='font-size:11px;color:#888'></div></div>"
        "</div></div>"

        "<div class='det-slip-col'>"
        "<div class='ikey' style='align-self:flex-start;margin-bottom:8px'>🧾 Payment Slip</div>"
        "<div id='d-slip-wrap' style='width:100%;display:flex;justify-content:center;min-height:80px'></div>"
        "</div></div>"

        "<div id='d-reply-block'>"
        "<div class='det-section'>"
        "<div class='det-sec-title'>🔍 ค้นหาใบเสร็จด้วยข้อมูลที่ถูกต้อง</div>"
        "<div class='msearch'>"
        "<div class='msearch-row'>"
        "<div class='msearch-fg'><div class='msearch-label'>Reference No.</div>"
        "<input class='msearch-input' id='ms-ref' placeholder='เช่น 125050000014'></div>"
        "<div class='msearch-fg' style='max-width:130px'><div class='msearch-label'>Amount (THB)</div>"
        "<input class='msearch-input' id='ms-amt' type='number' step='0.01' placeholder='เช่น 802.50'></div>"
        "<button class='btn btn-dark btn-sm' onclick='doManualSearch()' id='ms-btn' style='align-self:flex-end;white-space:nowrap'>🔍 ค้นหา</button>"
        "</div>"
        "<div class='msearch-status' id='ms-status'></div>"
        "<div class='inv-results' id='ms-results'></div>"
        "</div></div>"
        "<div class='det-section'>"
        "<div class='det-sec-title'>💬 ตอบกลับลูกค้า</div>"
        "<textarea class='det-ta' id='d-msg' "
        "placeholder='พิมพ์ข้อความที่ต้องการส่งให้ลูกค้าค่ะ...'></textarea>"
        "</div>"

        "<div class='det-section' style='padding-top:0'>"
        "<div class='det-sec-title'>📎 แนบไฟล์</div>"
        "<div class='uzone' id='uzone' onclick=\"document.getElementById('d-file').click()\">"
        "<span>📁 คลิกเพื่อเลือกไฟล์ (รูปภาพ / PDF / Excel / Word)</span>"
        "<div id='uname'></div><div id='uprog'></div>"
        "</div>"
        "<input type='file' id='d-file' style='display:none' "
        "accept='image/*,.pdf,.xlsx,.xls,.docx,.doc' onchange='handleFileSelect(this)'>"
        "</div>"

        "<div class='det-section' style='padding-top:0;padding-bottom:6px'>"
        "<label class='scb-row'>"
        "<input type='checkbox' id='send-slip-cb'>"
        "<span>🧾 ส่งรูปสลิปเดิมของลูกค้าคืนด้วย</span>"
        "</label></div></div>"

        "<div class='det-footer'>"
        "<div class='det-result' id='d-result'></div>"
        "<div class='det-acts'>"
        "<button class='btn btn-outline' onclick='closeDetail()'>✕ ปิด</button>"
        "<button class='btn btn-dark' id='ms-send-btn' onclick='sendManualInvoice()' style='display:none'>📄 ส่งใบเสร็จให้ลูกค้า</button>"
        "<button class='btn btn-green' id='d-send-btn' onclick='sendFromDetail()'>"
        "📤 ส่งข้อความ</button>"
        "</div></div>"
        "</div></div>"
    )

    slip_modal = (
        "<div class='smodal' id='smodal' onclick='closeSlip()'>"
        "<div class='smodal-inner' onclick='event.stopPropagation()'>"
        "<div class='smodal-label'>Payment Slip — Evidence Record</div>"
        "<img class='smodal-img' id='smodal-img' src=''>"
        "<button class='smodal-close' onclick='closeSlip()'>ปิด ✕</button>"
        "</div></div>"
    )

    parts = [
        "<!DOCTYPE html><html lang='th'><head>",
        "<meta charset='UTF-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>K-Digi ระบบติดตามรายการ — KLN Seaport</title>",
        "<link rel='preconnect' href='https://fonts.googleapis.com'>",
        "<link href='https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&display=swap' rel='stylesheet'>",
        f"<style>{CSS}</style>",
        "</head><body>",

        "<div class='topnav'>",
        "<div class='topnav-brand'>KLN Seaport Ltd.</div>",
        "<div class='topnav-right'>",
        "<span class='live-dot'>LIVE</span>",
        f"<span>{now}</span>",
        "<span class='sep'>|</span>",
        "<span>K-Digi · ฝ่าย Application Support</span>",
        "</div></div>",

        "<div class='subnav'>",
        "<div class='subnav-title'>ระบบติดตามรายการ</div>",
        "<div class='subnav-right'>",
        f"<span>อัปเดต {now}</span>",
        "<span>·</span>",
        "<span>รีเฟรชใน <span id='timer-text'>30s</span></span>",
        "</div></div>",

        "<main>",
        "<div class='page-title-bar'>",
        "<div><div class='page-title'>K-Digi ระบบติดตามรายการ</div>",
        f"<div class='page-sub'>แสดง {total} รายการ · ลับเฉพาะ — สำหรับใช้ภายในเท่านั้น</div></div>",
        "<div class='page-actions'>",
        "<a href='/dashboard/export' class='btn btn-outline btn-sm'>⬇ Export CSV</a>",
        "<button class='btn btn-dark btn-sm' onclick='refreshPage()' id='refresh-btn'>↻ Refresh</button>",
        "</div></div>",

        kpi,
        filter_panel,

        "<div class='table-toolbar'>",
        "<div class='tl'>",
        "<span class='section-title'>รายการธุรกรรม</span>",
        f"<span class='row-count'>{total} rows</span>",
        "</div></div>",
        f"<div class='table-box'>{rows_html}</div>",
        "</main>",

        "<div class='footer'>",
        "<div><strong>KLN Seaport Ltd.</strong> — K-Digi Receipt Bot | ฝ่าย Application Support</div>",
        "<div>ลับเฉพาะ — สำหรับใช้ภายในเท่านั้น</div>",
        "</div>",

        detail_popup,
        slip_modal,
        f"<script>{js}</script>",
        "</body></html>",
    ]
    return ''.join(parts)


# ══════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════

def add_dashboard_route(app: FastAPI):

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request):
        date_from     = request.query_params.get("date_from", "")
        date_to       = request.query_params.get("date_to", "")
        search        = request.query_params.get("search", "")
        status_filter = request.query_params.get("status_filter", "")
        is_filtered   = bool(date_from or date_to or search or status_filter)

        logs    = get_logs(date_from or None, date_to or None, search or None, status_filter or None)
        total   = len(logs)
        success = sum(1 for r in logs if "สำเร็จ" in (dict(r).get("status") or ""))
        error   = total - success
        rate    = round(success/total*100) if total > 0 else 0
        now     = datetime.now().strftime("%d %b %Y, %H:%M")

        chart_rows    = get_chart_data()
        chart_labels  = json.dumps([r["day"]     for r in chart_rows])
        chart_success = json.dumps([r["success"] for r in chart_rows])
        chart_error   = json.dumps([r["error"]   for r in chart_rows])

        rows_html = build_rows(logs)
        html = build_html(
            total, success, error, rate, now,
            rows_html, chart_labels, chart_success, chart_error,
            date_from, date_to, is_filtered, search, status_filter
        )
        return HTMLResponse(content=html)

    @app.get("/dashboard/error-count")
    def error_count():
        logs = get_logs()
        err  = sum(1 for r in logs if "สำเร็จ" not in (dict(r).get("status") or ""))
        return JSONResponse({"error_count": err, "total": len(logs)})

    @app.get("/dashboard/export")
    def export_csv():
        logs  = get_logs()
        today = datetime.now().strftime("%Y-%m-%d")
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID","Timestamp","User ID","Slip Type",
                         "Reference No.","Amount (THB)","Status","Invoice No.","OCR Text"])
        for r in logs:
            r = dict(r)
            writer.writerow([
                r.get("id"), r.get("timestamp",""), r.get("user_id",""),
                r.get("slip_type",""), r.get("ref_no",""), r.get("amount",""),
                r.get("status",""), r.get("invoice_no",""),
                (r.get("ocr_text","") or "")[:200]
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f"attachment; filename=kdigi_logs_{today}.csv"}
        )
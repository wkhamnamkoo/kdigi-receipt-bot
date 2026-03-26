import os
import sqlite3
import io
import csv
import json
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

DB_PATH = "kdigi_logs.db"
_URGENT_KW = ["OCR อ่านไม่ได้", "หา Ref No. ไม่เจอ", "ไม่พบใบเสร็จใน API"]

# ══════════════════════════════════════════════════════════════
# Database
# ══════════════════════════════════════════════════════════════

def get_logs(date_from=None, date_to=None, search=None, status_filter=None, assignee_filter=None):
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
    if assignee_filter:
        conds.append("claimed_by LIKE ?")
        params += [f"%{assignee_filter}%"]
    if status_filter == "success":
        conds.append("status LIKE '%สำเร็จ%'")
    elif status_filter == "urgent":
        ukw = " OR ".join([f"status LIKE '%{k}%'" for k in _URGENT_KW])
        conds.append(f"({ukw})")
        conds.append("status NOT LIKE '%สำเร็จ%'")
    elif status_filter == "error":
        ukw_not = " AND ".join([f"status NOT LIKE '%{k}%'" for k in _URGENT_KW])
        conds.append(f"(status NOT LIKE '%สำเร็จ%' AND {ukw_not})")

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
# CSS
# ══════════════════════════════════════════════════════════════

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --kln-dark:#2d2d2d;--kln-orange:#f26522;--kln-orange-hv:#d4541a;
  --kln-orange-lt:#fff3ed;--bg:#f0f0f0;--white:#fff;
  --border:#d0d0d0;--border-lt:#ebebeb;
  --text:#2d2d2d;--text2:#555;--text3:#888;
  --green:#27ae60;--green-bg:#eaf7ed;
  --red:#c0392b;--red-bg:#fdecea;
  --font:'Sarabun','Tahoma',sans-serif;--mono:'Courier New',monospace;
  --radius:4px;--shadow:0 1px 4px rgba(0,0,0,.12);
}
html{font-size:13px}
body{font-family:var(--font);background:var(--bg);color:var(--text);min-height:100vh;line-height:1.5}
.topnav{background:var(--kln-dark);height:54px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;border-bottom:3px solid var(--kln-orange)}
.topnav-brand{font-size:20px;font-weight:700;color:var(--kln-orange);font-style:italic;letter-spacing:.3px}
.topnav-right{display:flex;align-items:center;gap:14px;font-size:12px;color:#aaa}
.topnav-right .sep{color:#555}
.live-dot{display:inline-flex;align-items:center;gap:5px;color:#6fcf97;font-size:11px;font-weight:600}
.live-dot::before{content:'';width:7px;height:7px;background:#6fcf97;border-radius:50%;box-shadow:0 0 6px #6fcf97;animation:lp 1.8s infinite}
@keyframes lp{0%,100%{opacity:1}50%{opacity:.3}}
.subnav{background:var(--white);border-bottom:1px solid var(--border);padding:0 24px;height:40px;display:flex;align-items:center;justify-content:space-between;box-shadow:var(--shadow)}
.subnav-title{font-size:13px;font-weight:600;color:var(--text2);display:flex;align-items:center;gap:8px}
.subnav-title::before{content:'';width:3px;height:16px;background:var(--kln-orange);border-radius:2px}
.subnav-right{font-size:11px;color:var(--text3);display:flex;align-items:center;gap:8px}
main{padding:20px 24px 80px}
.page-title-bar{margin-bottom:18px;padding-bottom:12px;border-bottom:2px solid var(--kln-orange);display:flex;align-items:flex-end;justify-content:space-between}
.page-title{font-size:18px;font-weight:700;color:var(--kln-orange)}
.page-sub{font-size:11px;color:var(--text3);margin-top:2px}
.page-actions{display:flex;gap:8px;align-items:center}
.btn{display:inline-flex;align-items:center;gap:5px;border:1px solid transparent;border-radius:var(--radius);padding:6px 14px;font-size:12px;font-weight:600;font-family:var(--font);cursor:pointer;transition:all .15s;text-decoration:none;white-space:nowrap}
.btn-green{background:var(--green);color:#fff;border-color:var(--green)}
.btn-green:hover{background:#219a52;border-color:#219a52}
.btn-dark{background:var(--kln-dark);color:#fff;border-color:var(--kln-dark)}
.btn-dark:hover{background:#444;border-color:#444}
.btn-outline{background:var(--white);color:var(--text2);border-color:var(--border)}
.btn-outline:hover{background:#f5f5f5}
.btn-sm{padding:4px 10px;font-size:11px}
.btn:disabled{opacity:.5;cursor:not-allowed}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}
.kpi-card{background:var(--white);border:1px solid var(--border);border-top:3px solid var(--kln-orange);border-radius:var(--radius);padding:14px 18px;box-shadow:var(--shadow);display:flex;align-items:center;gap:14px}
.kpi-card.c-green{border-top-color:var(--green)}
.kpi-card.c-red{border-top-color:var(--red)}
.kpi-card.c-gray{border-top-color:#888}
.kpi-icon{width:40px;height:40px;border-radius:8px;background:var(--kln-orange-lt);display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}
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
.filter-panel{background:var(--white);border:1px solid var(--border);border-radius:var(--radius);padding:14px 18px;margin-bottom:16px;box-shadow:var(--shadow)}
.filter-row{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px}
.fg{display:flex;flex-direction:column;gap:4px}
.fl{font-size:11px;font-weight:600;color:var(--text2)}
.fi{border:1px solid var(--border);border-radius:var(--radius);padding:5px 9px;font-family:var(--font);font-size:12px;color:var(--text);background:var(--white);min-width:110px;transition:border-color .15s}
.fi:focus{outline:none;border-color:var(--kln-orange);box-shadow:0 0 0 2px rgba(242,101,34,.1)}
.fdiv{width:1px;height:28px;background:var(--border-lt);align-self:flex-end}
.fresult{font-size:11px;color:var(--text3);align-self:flex-end}
.table-toolbar{background:var(--white);border:1px solid var(--border);border-bottom:none;border-radius:var(--radius) var(--radius) 0 0;padding:8px 12px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px}
.tl{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.section-title{font-size:12px;font-weight:700;color:var(--text2)}
.row-count{font-size:11px;color:var(--text3);background:#f5f5f5;border:1px solid var(--border);padding:2px 7px;border-radius:3px}
.table-box{background:var(--white);border:1px solid var(--border);border-radius:0 0 var(--radius) var(--radius);overflow:hidden;overflow-x:auto;box-shadow:var(--shadow)}
table{width:100%;border-collapse:collapse;font-size:12px}
thead{background:var(--kln-dark)}
th{padding:9px 12px;text-align:left;font-size:11px;font-weight:600;color:#e0e0e0;white-space:nowrap;border-right:1px solid #444;letter-spacing:.2px}
th:last-child{border-right:none}
td{padding:8px 12px;border-bottom:1px solid var(--border-lt);vertical-align:middle;color:var(--text);transition:background .1s}
tr:last-child td{border-bottom:none}
tr:nth-child(even) td{background:#fafafa}
tr.crow{cursor:pointer}
tr.crow:hover td{background:var(--kln-orange-lt)!important}
tr.erow td:first-child{border-left:3px solid var(--red)}
tr.srow td:first-child{border-left:3px solid var(--green)}
tr.erow td{background:#fff8f8}
tr.erow:nth-child(even) td{background:#fff5f5}
tr.urow td{background:#fff8f0}
tr.urow:nth-child(even) td{background:#fff3e8}
tr.urow td:first-child{border-left:4px solid var(--kln-orange);animation:upulse 1.8s infinite}
tr.urow:hover td{background:#ffe0c0!important}
/* Fix 5: ติดตามผล row — สีเหลืองคงอยู่จนกว่าจะเสร็จ */
tr.frow td{background:#fffbea}
tr.frow:nth-child(even) td{background:#fff8e0}
tr.frow td:first-child{border-left:4px solid #f0b429;animation:fpulse 2s infinite}
tr.frow:hover td{background:#fff0b0!important}
@keyframes upulse{0%,100%{border-left-color:var(--kln-orange)}50%{border-left-color:#ff9955}}
@keyframes fpulse{0%,100%{border-left-color:#f0b429}50%{border-left-color:#ffd966}}
.badge{display:inline-flex;align-items:center;gap:3px;padding:2px 7px;border-radius:3px;font-size:10px;font-weight:700;letter-spacing:.2px}
.bok{background:var(--green-bg);color:var(--green);border:1px solid #b8e6c4}
.berr{background:var(--red-bg);color:var(--red);border:1px solid #f5c2c7}
.td-id{color:var(--text3);font-size:11px}
.td-ref{font-family:var(--mono);font-size:11px;color:var(--text2)}
.td-amt{font-family:var(--mono);font-size:11px;text-align:right}
.td-inv{font-size:11px;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text2)}
.td-ocr{font-size:11px;color:var(--text3);max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.td-img{width:52px}
.slip-thumb{width:42px;height:30px;object-fit:cover;border-radius:3px;cursor:zoom-in;border:1px solid var(--border)}
.slip-thumb:hover{opacity:.8}
.no-img{font-size:10px;color:var(--text3)}
.empty-state{text-align:center;padding:50px 20px;color:var(--text3)}
.empty-state .icon{font-size:36px;margin-bottom:10px}
/* Badges: 2 โทนสี — เทา (neutral) + แดง (error) + เขียว (success) */
.bc{display:inline-block;padding:2px 9px;border-radius:3px;font-size:10px;font-weight:600;white-space:nowrap}
.bc-ocr{background:#fef2f2;color:#991b1b;border:1px solid #fecaca}
.bc-ref{background:#fef2f2;color:#991b1b;border:1px solid #fecaca}
.bc-inv{background:#fef2f2;color:#991b1b;border:1px solid #fecaca}
.bc-err{background:#f5f5f5;color:#555;border:1px solid #d8d8d8}
.bc-none{color:#bbb;font-size:11px}
/* สถานะ Support: สำเร็จ=เขียว, error=แดง, อื่นๆ=เทา */
.bst-ok     {background:#f0fdf4;color:#166534;border:1px solid #bbf7d0;border-radius:3px;padding:2px 9px;font-size:10px;font-weight:600;display:inline-block}
.bst-follow {background:#f5f5f5;color:#444;border:1px solid #d8d8d8;border-radius:3px;padding:2px 9px;font-size:10px;font-weight:600;display:inline-block}
.bst-checked{background:#f5f5f5;color:#444;border:1px solid #d8d8d8;border-radius:3px;padding:2px 9px;font-size:10px;font-weight:600;display:inline-block}
.bst-failed {background:#fef2f2;color:#991b1b;border:1px solid #fecaca;border-radius:3px;padding:2px 9px;font-size:10px;font-weight:600;display:inline-block}
.bst-wait   {background:#f5f5f5;color:#888;border:1px solid #d8d8d8;border-radius:3px;padding:2px 9px;font-size:10px;font-weight:600;display:inline-block}
/* การแก้ไข: สำเร็จ=เขียว, อื่นๆ=เทา */





/* Detail Popup */
.confirm-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:10000;align-items:center;justify-content:center;padding:16px}
.confirm-overlay.show{display:flex}
.confirm-popup{background:var(--white);border-radius:var(--radius);width:580px;max-height:90vh;max-width:96vw;box-shadow:0 8px 40px rgba(0,0,0,.3);animation:popIn .18s ease;display:flex;flex-direction:column;overflow:hidden}
.confirm-header{background:#1a1a1a;padding:14px 20px;display:flex;align-items:center;gap:10px;flex-shrink:0}
.confirm-header-title{color:#fff;font-weight:700;font-size:14px;flex:1}
.confirm-body{padding:18px 20px;overflow-y:auto;flex:1}
.confirm-case-id{font-size:12px;color:#888;margin-bottom:10px;font-weight:600}
.confirm-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}
.confirm-item{background:#f9f9f9;border-radius:6px;padding:9px 12px}
.confirm-label{font-size:10px;color:#888;font-weight:700;text-transform:uppercase;margin-bottom:2px}
.confirm-value{font-size:12px;color:#1a1a1a;font-weight:600;word-break:break-all}
.confirm-ocr-box{background:#f9f9f9;border-radius:6px;padding:9px 12px;margin-bottom:14px}
.confirm-ocr-text{font-size:11px;color:#555;line-height:1.6;max-height:72px;overflow-y:auto}
.confirm-actions{display:flex;gap:8px;padding:12px 20px 18px;border-top:1px solid #f0f0f0;flex-shrink:0;background:var(--white)}
.btn-cp-close{padding:11px 14px;border:1.5px solid #ddd;border-radius:8px;background:#fff;color:#555;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;white-space:nowrap}
.btn-cp-accept{flex:1;padding:11px;border:none;border-radius:8px;background:#f26522;color:#fff;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.btn-cp-accept:hover{background:#d4551a}
.btn-cp-accept:disabled{background:#ccc;cursor:not-allowed}
.det-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9999;align-items:center;justify-content:center;padding:20px}
.det-overlay.show{display:flex}
.det-popup{background:var(--white);border-radius:var(--radius);width:760px;max-width:96vw;max-height:90vh;overflow-y:auto;box-shadow:0 8px 40px rgba(0,0,0,.25);animation:popIn .18s ease}
@keyframes popIn{from{opacity:0;transform:scale(.97) translateY(10px)}to{opacity:1;transform:none}}
.det-hdr{background:var(--kln-dark);padding:14px 20px;display:flex;justify-content:space-between;align-items:center;border-radius:var(--radius) var(--radius) 0 0;position:sticky;top:0;z-index:5}
.det-title{font-size:14px;font-weight:700;color:var(--kln-orange);display:flex;align-items:center;gap:8px}
.det-sub{font-size:11px;color:#888;margin-top:3px}
.det-close{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);color:#ccc;width:28px;height:28px;border-radius:4px;font-size:15px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s}
.det-close:hover{background:var(--red);color:#fff;border-color:var(--red)}
.det-body{display:grid;grid-template-columns:1fr 195px;border-bottom:1px solid var(--border)}
.det-info{padding:18px 20px}
.det-slip-col{padding:18px 14px;background:#f9f9f9;border-left:1px solid var(--border);display:flex;flex-direction:column;align-items:center;gap:8px}
.det-slip-col img{width:100%;max-width:160px;border-radius:4px;border:1px solid var(--border);cursor:zoom-in;box-shadow:var(--shadow);transition:transform .2s}
.det-slip-col img:hover{transform:scale(1.05)}
.no-slip{color:var(--text3);font-size:11px;text-align:center;padding:20px 0}
.igrid{display:grid;grid-template-columns:1fr 1fr;gap:0}
.iitem{padding:8px 0;border-bottom:1px solid var(--border-lt)}
.iitem:nth-last-child(-n+2){border-bottom:none}
.iitem.full{grid-column:1/-1}
.ikey{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--text3);margin-bottom:3px}
.ival{font-size:12px;color:var(--text);font-weight:500;word-break:break-all}
.ival.m{font-family:var(--mono);font-size:11px;color:var(--text2)}
.det-section{padding:14px 20px;border-top:1px solid var(--border-lt)}
.det-sec-title{font-size:11px;font-weight:700;color:var(--text2);margin-bottom:10px;display:flex;align-items:center;gap:6px;padding-bottom:6px;border-bottom:1px solid var(--border-lt)}
.det-ta{width:100%;border:1px solid var(--border);border-radius:var(--radius);padding:8px 10px;font-family:var(--font);font-size:13px;color:var(--text);resize:vertical;min-height:72px;transition:border-color .15s;background:var(--white)}
.det-ta:focus{outline:none;border-color:var(--kln-orange);box-shadow:0 0 0 2px rgba(242,101,34,.1)}
.det-ta::placeholder{color:var(--text3)}
.uzone{border:2px dashed var(--border);border-radius:var(--radius);padding:10px 14px;cursor:pointer;text-align:center;font-size:12px;color:var(--text3);transition:all .2s;margin-top:8px;background:#fafafa}
.uzone:hover{border-color:var(--kln-orange);color:var(--kln-orange);background:var(--kln-orange-lt)}
.uzone.has-file{border-color:var(--green);color:var(--green);background:var(--green-bg);border-style:solid}
.scb-row{display:flex;align-items:center;gap:8px;padding:6px 0;font-size:12px;color:var(--text2);cursor:pointer}
.scb-row input{accent-color:var(--kln-orange);width:14px;height:14px;cursor:pointer}
.det-footer{padding:12px 20px;border-top:1px solid var(--border);background:#f9f9f9;display:flex;align-items:center;justify-content:space-between;border-radius:0 0 var(--radius) var(--radius);position:sticky;bottom:0}
.det-result{font-size:12px;min-height:18px}
.det-acts{display:flex;gap:8px}
/* msearch */
.msearch{background:#f5f9ff;border:1px solid #d0e4ff;border-radius:var(--radius);padding:14px 16px}
.msearch-row{display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap;margin-bottom:10px}
.msearch-fg{display:flex;flex-direction:column;gap:4px;flex:1;min-width:120px}
.msearch-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:#5577aa}
.msearch-input{border:1px solid #bbd0f0;border-radius:var(--radius);padding:6px 9px;font-family:var(--font);font-size:12px;color:var(--text);background:#fff;width:100%}
.msearch-input:focus{outline:none;border-color:var(--kln-orange);box-shadow:0 0 0 2px rgba(242,101,34,.1)}
.msearch-status{font-size:12px;margin-top:6px;min-height:18px}
.inv-results{margin-top:10px}
.inv-item{display:flex;align-items:center;justify-content:space-between;padding:8px 10px;background:#fff;border:1px solid #d0e4ff;border-radius:var(--radius);margin-bottom:6px;font-size:12px}
.inv-item:last-child{margin-bottom:0}
.inv-name{color:var(--text2);font-family:var(--mono);font-size:11px;flex:1}
.inv-badge{background:#e8f5e9;color:var(--green);border:1px solid #b8e6c4;border-radius:3px;padding:1px 6px;font-size:10px;font-weight:700;margin-right:8px}
.send-preview{margin-top:10px;padding:10px 12px;background:#f0fff4;border:1px solid #b8e6c4;border-radius:4px;font-size:12px;color:#27ae60;display:none}
/* Fix 4: Case Status section — ท้าย Popup มี border สีส้ม */















/* Slip modal */
.smodal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:10000;align-items:center;justify-content:center;padding:20px}
.smodal.show{display:flex}
.smodal-inner{background:var(--white);border-radius:var(--radius);padding:20px;max-width:480px;width:100%}
.smodal-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--text3);margin-bottom:10px}
.smodal-img{width:100%;border-radius:4px;margin-bottom:14px}
.smodal-close{width:100%;padding:8px;background:var(--kln-dark);color:#fff;border:none;border-radius:var(--radius);font-size:13px;cursor:pointer;font-family:var(--font)}
.smodal-close:hover{background:#444}

/* Claim section ใน Popup */
.claim-wrap{padding:12px 20px;background:#f5f9ff;border-top:1px solid #d0e4ff;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.claim-input{border:1px solid #bbd0f0;border-radius:var(--radius);padding:6px 10px;font-family:var(--font);font-size:12px;color:var(--text);background:#fff;flex:1;min-width:160px;transition:border-color .15s}
.claim-input:focus{outline:none;border-color:var(--kln-orange);box-shadow:0 0 0 2px rgba(242,101,34,.1)}
.claim-btn{padding:6px 14px;font-size:12px;font-weight:600;border:1px solid var(--kln-orange);border-radius:var(--radius);background:var(--kln-orange);color:#fff;cursor:pointer;font-family:var(--font);transition:all .15s;white-space:nowrap}
.claim-btn:hover{background:var(--kln-orange-hv)}
.claim-btn:disabled{background:#ccc;border-color:#ccc;cursor:not-allowed}
.claimed-tag{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;background:#e8f0fe;color:#1a56db;border:1px solid #c3d3fb;border-radius:3px;font-size:11px;font-weight:600}
.bst-ok{display:inline-flex;align-items:center;gap:3px;padding:2px 8px;border-radius:20px;background:#e8f5e9;color:#2e7d32;font-size:11px;font-weight:600}
.bst-pending{display:inline-flex;align-items:center;gap:3px;padding:2px 8px;border-radius:20px;background:#fce4ec;color:#c62828;font-size:11px;font-weight:600}
.bst-none{color:#bbb;font-size:12px}
.qr-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:10001;align-items:center;justify-content:center;padding:20px}
.qr-overlay.show{display:flex}
.qr-popup{background:#fff;border-radius:12px;width:460px;max-width:95vw;max-height:80vh;display:flex;flex-direction:column;box-shadow:0 8px 40px rgba(0,0,0,.25);overflow:hidden}
.qr-header{background:#1a1a1a;padding:14px 18px;display:flex;align-items:center;gap:10px;flex-shrink:0}
.qr-body{padding:16px 18px;overflow-y:auto;flex:1}
.qr-item{display:flex;align-items:flex-start;gap:8px;padding:8px 0;border-bottom:1px solid #f0f0f0}
.qr-item-text{flex:1;font-size:12px;color:#333;line-height:1.5;word-break:break-all}
.td-claimed{font-size:11px;color:var(--text2);max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

.jira-btn{padding:6px 14px;font-size:12px;font-weight:600;border:1px solid #0052cc;border-radius:var(--radius);background:#0052cc;color:#fff;cursor:pointer;font-family:var(--font);transition:all .15s;white-space:nowrap;display:inline-flex;align-items:center;gap:5px}
.jira-btn:hover{background:#0747a6}
.jira-btn:disabled{background:#ccc;border-color:#ccc;cursor:not-allowed}
.jira-btn.done{background:#f0fdf4;color:#166534;border-color:#bbf7d0;cursor:default}

.jira-resolve-wrap{margin-top:8px;display:none}
.jira-resolve-ta{width:100%;border:1px solid #bbd0f0;border-radius:var(--radius);
  padding:7px 10px;font-family:var(--font);font-size:12px;color:var(--text);
  resize:none;height:64px;background:#fff;transition:border-color .15s}
.jira-resolve-ta:focus{outline:none;border-color:#0052cc;box-shadow:0 0 0 2px rgba(0,82,204,.1)}
.jira-resolve-ta::placeholder{color:var(--text3)}

/* Resolution note + claimed */
.res-note-wrap{padding:10px 20px;border-top:1px solid var(--border-lt);background:#fafff8}
.res-note-ta{width:100%;border:1px solid #b8e6c4;border-radius:var(--radius);padding:7px 10px;
  font-family:var(--font);font-size:12px;color:var(--text);resize:none;height:58px;
  transition:border-color .15s;background:#fff}
.res-note-ta:focus{outline:none;border-color:var(--green);box-shadow:0 0 0 2px rgba(39,174,96,.1)}
.res-note-ta::placeholder{color:var(--text3)}
.claimed-banner{padding:8px 20px;background:#e8f0fe;border-top:1px solid #c3d3fb;
  font-size:11px;color:#1a56db;display:none}

/* Name setup popup */
.name-overlay{position:fixed;inset:0;background:rgba(0,0,0,.5);
  display:flex;align-items:center;justify-content:center;z-index:9999}
.name-card{background:#fff;border-radius:16px;padding:32px 28px;
  max-width:340px;width:90%;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.2)}
.name-card h2{font-size:18px;font-weight:700;color:#1a1a1a;margin-bottom:8px}
.name-card p{font-size:13px;color:#888;margin-bottom:20px;line-height:1.6}
.name-inp{width:100%;padding:12px 14px;border:1.5px solid #ddd;border-radius:10px;
  font-size:15px;font-family:inherit;color:#1a1a1a;transition:border-color .15s}
.name-inp:focus{outline:none;border-color:#f26522;box-shadow:0 0 0 3px rgba(242,101,34,.1)}
.name-save-btn{width:100%;padding:13px;margin-top:12px;border:none;border-radius:10px;
  background:#f26522;color:#fff;font-size:15px;font-weight:700;cursor:pointer;
  font-family:inherit;transition:background .15s}
.name-save-btn:hover{background:#d4551a}
.name-change-btn{background:none;border:none;color:#aaa;font-size:12px;
  cursor:pointer;margin-top:10px;font-family:inherit;text-decoration:underline}
.footer{background:var(--kln-dark);color:#888;font-size:11px;padding:10px 24px;display:flex;justify-content:space-between;align-items:center;position:fixed;bottom:0;left:0;right:0}
.footer strong{color:var(--kln-orange)}
"""

# ══════════════════════════════════════════════════════════════
# JavaScript
# ══════════════════════════════════════════════════════════════

def build_js(error_count_val):
    js = r"""

var _detId=0,_detUid='',_detSlipType='',_fileUrl='',_fileName='';
var _foundInvoices=[];
var _claimedByUrl='';
var _confirmLogId=0;
var _confirmRow=null;

function getSessionName(){
  var el=document.getElementById('session-name');
  if(el&&el.dataset.name) _claimedByUrl=el.dataset.name;
  return _claimedByUrl;
}

function showConfirmPopup(row){
  getSessionName();
  _confirmLogId=parseInt(row.dataset.id||0);
  _confirmRow=row;
  var e=function(id){return document.getElementById(id);};
  if(e('cp-id'))      e('cp-id').textContent='เคส #'+_confirmLogId+' · '+(row.dataset.ts||'');
  if(e('cp-uid'))     e('cp-uid').textContent=row.dataset.uid||'—';
  if(e('cp-ref'))     e('cp-ref').textContent=row.dataset.ref||'—';
  if(e('cp-amt'))     e('cp-amt').textContent=row.dataset.amt?row.dataset.amt+' บาท':'—';
  if(e('cp-type'))    e('cp-type').textContent=row.dataset.sliptype||'—';
  if(e('cp-status'))  e('cp-status').textContent=row.dataset.status||'—';
  if(e('cp-ocr'))     e('cp-ocr').textContent=row.dataset.ocr||'—';
  var claimedBy=row.dataset.claimedby||'';
  if(e('cp-claimed')) e('cp-claimed').textContent=claimedBy||'ยังไม่มีผู้รับค่ะ';

  // โหลดรูปสลิปค่ะ
  var slipWrap=e('cp-slip-wrap');
  var slipImg=e('cp-slip-img');
  if(slipWrap&&slipImg){
    if(row.dataset.hasslip==='1'){
      slipWrap.style.display='block';
      slipImg.src='';
      fetch('/slip-image/'+_confirmLogId)
        .then(function(r){return r.json();})
        .then(function(d){if(d.b64) slipImg.src='data:image/jpeg;base64,'+d.b64;})
        .catch(function(){slipWrap.style.display='none';});
    } else {
      slipWrap.style.display='none';
    }
  }

  var isErr=row.dataset.iserror==='1';
  var ab=e('cp-accept-btn');
  if(ab){
    if(!isErr){
      ab.style.display='none';
    } else if(claimedBy&&claimedBy!==_claimedByUrl){
      ab.textContent=claimedBy+' รับไปแล้วค่ะ';
      ab.disabled=true;ab.style.background='#888';ab.style.display='';
    } else {
      ab.textContent='ยืนยันแก้ไข';
      ab.disabled=false;ab.style.background='';ab.style.display='';
    }
  }
  document.getElementById('confirm-overlay').classList.add('show');
}

function closeConfirmPopup(){
  document.getElementById('confirm-overlay').classList.remove('show');
  _confirmLogId=0;_confirmRow=null;
}

var _acceptingCase=false;
function acceptCase(){
  if(_acceptingCase) return;
  _acceptingCase=true;
  getSessionName();
  if(!_confirmLogId){return;}
  if(!_claimedByUrl){
    alert('ไม่พบชื่อ session ค่ะ กรุณา refresh หน้าเว็บแล้ว login ใหม่ค่ะ');
    return;
  }
  var logId=_confirmLogId;
  var row=_confirmRow;
  closeConfirmPopup();
  // call markClaimed ก่อนเลย ไม่รอ openDetail ค่ะ
  fetch('/mark-claimed',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({log_id:logId,claimed_by:_claimedByUrl})})
  .then(function(r){return r.json();})
  .then(function(d){
    console.log('[K-Digi] mark-claimed response:', JSON.stringify(d));
    if(row){
      if(d.status==='ok') row.dataset.claimedby=_claimedByUrl;
      row.scrollIntoView({behavior:'smooth',block:'center'});
      setTimeout(function(){
        openDetail(row);
        // อัปเดต banner ใน popup ด้วยค่ะ
        var banner=document.getElementById('d-claimed-banner');
        if(banner){
          if(d.status==='ok'){
            banner.textContent='คุณ ('+_claimedByUrl+') รับผิดชอบเคสนี้แล้วค่ะ — ทีมได้รับแจ้งแล้วค่ะ';
            banner.style.background='#e8f0fe';banner.style.color='#1a56db';banner.style.display='block';
          } else if(d.status==='already_claimed'){
            banner.textContent=d.detail;
            banner.style.background='#fff7e6';banner.style.color='#b45309';banner.style.display='block';
          } else if(d.status==='done'){
            banner.textContent='เคสนี้แก้ไขเรียบร้อยแล้วค่ะ';
            banner.style.background='#f0fdf4';banner.style.color='#166534';banner.style.display='block';
          }
        }
      },300);
    }
  })
  .catch(function(e){
    console.error('[K-Digi] mark-claimed error:', e);
    if(row){
      row.scrollIntoView({behavior:'smooth',block:'center'});
      setTimeout(function(){openDetail(row);},300);
    }
  }).finally(function(){ _acceptingCase=false; });
}
function markClaimed(logId){
  if(!_claimedByUrl||!logId) return;
  fetch('/mark-claimed',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({log_id:logId,claimed_by:_claimedByUrl})})
  .then(function(r){return r.json();})
  .then(function(d){
    var banner=document.getElementById('d-claimed-banner');
    if(d.status==='ok'){
      var row=document.querySelector('tr[data-id="'+logId+'"]');
      if(row) row.dataset.claimedby=_claimedByUrl;
      if(banner){
        banner.textContent='คุณ ('+_claimedByUrl+') รับผิดชอบเคสนี้แล้วค่ะ — ทีมได้รับแจ้งแล้วค่ะ';
        banner.style.background='#e8f0fe';banner.style.color='#1a56db';
        banner.style.display='block';
      }
    } else if(d.status==='already_claimed'){
      if(banner){
        banner.textContent=d.detail+' — เคสนี้มีผู้รับผิดชอบแล้วค่ะ';
        banner.style.background='#fff7e6';banner.style.color='#b45309';
        banner.style.display='block';
      }
    } else if(d.status==='done'){
      if(banner){
        banner.textContent='เคสนี้แก้ไขเรียบร้อยแล้วค่ะ (ผู้แก้ไข: '+(d.claimed_by||'ทีม Support')+')';
        banner.style.background='#f0fdf4';banner.style.color='#166534';
        banner.style.display='block';
      }
    }
  }).catch(function(){});
}







function openDetail(row){
  _detId=parseInt(row.dataset.id||0);
  _detUid=row.dataset.uid||'';
  _detSlipType=row.dataset.sliptype||'';
  _fileUrl='';_fileName='';_foundInvoices=[];

  var _tmp=document.getElementById('d-uid');
  if(_tmp) _tmp.textContent=row.dataset.uid||'—';
  var _tmp=document.getElementById('d-ts');
  if(_tmp) _tmp.textContent=row.dataset.ts||'—';
  var _tmp=document.getElementById('d-ref');
  if(_tmp) _tmp.textContent=row.dataset.ref||'—';
  var _tmp=document.getElementById('d-amt');
  if(_tmp) _tmp.textContent=row.dataset.amt||'—';
  var _tmp=document.getElementById('d-inv');
  if(_tmp) _tmp.textContent=row.dataset.inv||'—';
  var _tmp=document.getElementById('d-ocr');
  if(_tmp) _tmp.textContent=row.dataset.ocr||'—';
  var sub=document.getElementById('d-sub');
  if(sub) sub.textContent='#'+_detId+' · '+(row.dataset.ts||'');

  var st=row.dataset.status||'';
  var ok=st.includes('สำเร็จ');
  var _tmp=document.getElementById('d-status');
  if(_tmp) _tmp.innerHTML=ok
    ?'<span class="badge bok">Bot ส่งสำเร็จ</span>'
    :'<span class="badge berr">✗ '+st.replace('❌','').trim()+'</span>';

  var sw=document.getElementById('d-slip-wrap');
  if(row.dataset.hasslip==='1'){
    sw.innerHTML='<img id="sdimg" style="width:100%;border-radius:4px;border:1px solid #ddd;cursor:zoom-in" onclick="showSlip(this.src)">';
    fetch('/slip-image/'+_detId).then(function(r){return r.json();})
      .then(function(d){if(d.b64) document.getElementById('sdimg').src='data:image/jpeg;base64,'+d.b64;})
      .catch(function(){});
  } else { sw.innerHTML='<div class="no-slip">ไม่มีรูปสลิปค่ะ</div>'; }

  (document.getElementById('d-msg')||{}).value='';
  var _tmp=document.getElementById('d-result');
  if(_tmp) _tmp.textContent='';
  var sbtn=document.getElementById('d-send-btn');
  if(sbtn){sbtn.disabled=false;sbtn.textContent='📤 ส่งทั้งหมดให้ลูกค้า';}

  // reset resolution note
  var resNote=document.getElementById('d-res-note');
  if(resNote) resNote.value='';

  var msRef=document.getElementById('ms-ref');
  var msAmt=document.getElementById('ms-amt');
  if(msRef) msRef.value=row.dataset.ref!=='—'?row.dataset.ref:'';
  if(msAmt) msAmt.value=row.dataset.amt?row.dataset.amt.replace(/[^0-9.]/g,''):'';
  var msSt=document.getElementById('ms-status');
  var msRes=document.getElementById('ms-results');
  var msPreview=document.getElementById('ms-preview');
  if(msSt) msSt.innerHTML='';
  if(msRes) msRes.innerHTML='';
  if(msPreview) msPreview.style.display='none';

  var isErr=row.dataset.iserror==='1';
  var errorType=row.dataset.errortype||'none';
  var rb=document.getElementById('d-reply-block');
  if(rb) rb.style.display=isErr?'':'none';
  // set errorType ใน hidden input ค่ะ
  var etEl=document.getElementById('cp-error-type');
  if(etEl) etEl.value=errorType||'none';
  // แสดง/ซ่อน section ตาม errorType ค่ะ
  var refSec=document.getElementById('d-ref-section');
  var msgSec=document.getElementById('d-msg-section');
  if(refSec) refSec.style.display=(errorType==='ref_error'||errorType==='none'&&isErr)?'':'none';
  if(msgSec) msgSec.style.display=(errorType==='invoice_error')?'':'none';

  // โหลด Quick Reply options ค่ะ
  if(errorType==='invoice_error') loadQuickReplies();

  // แสดง claimed banner
  var banner=document.getElementById('d-claimed-banner');
  if(banner){
    var existingClaim=row.dataset.claimedby||'';
    var displayName=_claimedByUrl||existingClaim;
    if(displayName){
      banner.textContent='ผู้รับผิดชอบ: '+displayName+(existingClaim&&existingClaim===displayName?' (รับเคสแล้วค่ะ)':'');
      banner.style.display='block';
    } else {
      banner.style.display='none';
    }
  }

  document.getElementById('det-overlay').classList.add('show');
}

function closeDetail(){
  document.getElementById('det-overlay').classList.remove('show');
}

function doManualSearch(){
  var ref=document.getElementById('ms-ref').value.trim();
  var amt=parseFloat(document.getElementById('ms-amt').value)||0;
  if(!ref){document.getElementById('ms-status').innerHTML='<span style="color:var(--kln-orange)">⚠️ กรุณาระบุ Ref No. ค่ะ</span>';return;}
  var btn=document.getElementById('ms-btn');
  btn.disabled=true;btn.textContent='⏳ ค้นหา...';
  document.getElementById('ms-status').innerHTML='<span style="color:#888">⏳ กำลังค้นหา...</span>';
  document.getElementById('ms-results').innerHTML='';
  var prev=document.getElementById('ms-preview');
  if(prev) prev.style.display='none';
  _foundInvoices=[];
  fetch('/manual-search',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({ref_no:ref,amount:amt,user_id:_detUid,log_id:_detId})})
  .then(function(r){return r.json();})
  .then(function(d){
    btn.disabled=false;btn.textContent='🔍 ค้นหา';
    if(d.status==='ok'){
      _foundInvoices=d.result;
      document.getElementById('ms-status').innerHTML='<span style="color:var(--green)">✅ พบ '+d.result.length+' ใบเสร็จค่ะ</span>';
      var html='';
      d.result.forEach(function(item,i){
        html+='<div class="inv-item"><span class="inv-badge">'+(i+1)+'</span><span class="inv-name">'+item.InvoiceNo+'</span>'
          +'<a href="'+item.InvoiceUrl+'" target="_blank" class="btn btn-outline btn-sm">ดู</a></div>';
      });
      document.getElementById('ms-results').innerHTML=html;
      if(prev) prev.style.display='';
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

function sendAll(){
  var etEl=document.getElementById('cp-error-type');
  var errorType=etEl?etEl.value:'ref_error';
  var msRef=document.getElementById('ms-ref');
  var msAmt=document.getElementById('ms-amt');
  var ref=msRef?msRef.value.trim():'';
  var amt=msAmt?parseFloat(msAmt.value)||0:0;
  var msgEl=document.getElementById('d-msg');
  var msg=msgEl?msgEl.value.trim():'';
  var resNote=document.getElementById('d-res-note')?document.getElementById('d-res-note').value.trim():'';
  var hasInvoice=ref&&_foundInvoices.length>0;

  if(errorType==='invoice_error'){
    if(!msg){
      document.getElementById('d-result').textContent='⚠️ กรุณาพิมพ์ข้อความที่จะส่งให้ลูกค้าค่ะ';
      return;
    }
  } else if(!hasInvoice&&!msg&&!_fileUrl){
    document.getElementById('d-result').textContent='⚠️ กรุณาพิมพ์ข้อความ หรือค้นหา Invoice ก่อนค่ะ';
    return;
  }

  var btn=document.getElementById('d-send-btn');
  btn.disabled=true;btn.textContent='⏳ กำลังส่ง...';
  document.getElementById('d-result').innerHTML='';

  var invoicePromise=(hasInvoice&&errorType!=='invoice_error')
    ?fetch('/manual-send-invoice',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({ref_no:ref,amount:amt,user_id:_detUid,log_id:_detId,
                             slip_type:_detSlipType||'',resolution_note:(resNote+'||SESSION||'+(_claimedByUrl||'ทีม Support'))})})
      .then(function(r){return r.json();})
      .then(function(d){
        if(d.status!=='ok') throw new Error(d.detail||'ส่ง Invoice ไม่สำเร็จ');
        if(d.invoice_nos&&d.invoice_nos.length){var di=document.getElementById('d-inv');if(di) di.textContent=d.invoice_nos.join(', ');}
        var dr=document.getElementById('d-ref');var da=document.getElementById('d-amt');
        if(dr&&ref) dr.textContent=ref;
        if(da&&amt) da.textContent=amt.toLocaleString('th-TH',{minimumFractionDigits:2,maximumFractionDigits:2})+' บาท';
        var curRow=document.querySelector('tr[data-id="'+_detId+'"]');
        if(curRow){
          if(ref){curRow.dataset.ref=ref;curRow.cells[4].textContent=ref;}
          if(amt){var af=amt.toLocaleString('th-TH',{minimumFractionDigits:2,maximumFractionDigits:2});curRow.dataset.amt=af+' บาท';curRow.cells[5].textContent=af;}
          if(d.invoice_nos&&d.invoice_nos.length){var iv=d.invoice_nos.join(', ');curRow.dataset.inv=iv;var is=iv.length>13?iv.slice(0,13)+'…':iv;curRow.cells[9].textContent=is;curRow.cells[9].title=iv;}
        }
        return d;
      })
    :Promise.resolve({status:'ok',skipped:true});

  invoicePromise
  .then(function(){
    // ถ้าไม่มีข้อความ ไฟล์ และไม่ส่งสลิป → ข้ามได้เลยค่ะ
    if(!msg&&!_fileUrl) return Promise.resolve({status:'ok',skipped:true});
    var _sessionName=_claimedByUrl||'ทีม Support';
    return fetch('/reply-user',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({user_id:_detUid,message:msg,file_url:_fileUrl,file_name:_fileName,
        send_slip:false,log_id:_detId,
        resolution_note:(resNote+'||SESSION||'+_sessionName)})})
    .then(function(r){return r.json();});
  })
  .then(function(d2){
    if(d2&&d2.status==='error') throw new Error(d2.detail||'ส่งข้อความไม่สำเร็จ');
    document.getElementById('d-result').innerHTML='<span style="color:var(--green)">✅ ส่งให้ลูกค้าเรียบร้อยแล้วค่ะ — กด ✕ เพื่อปิดค่ะ</span>';
    btn.textContent='✅ ส่งแล้ว';
    var curRow2=document.querySelector('tr[data-id="'+_detId+'"]');
    if(curRow2) curRow2.className=curRow2.className.replace(/\b(erow|urow|frow)\b/g,'').trim()+' srow';
  })
  .catch(function(e){
    document.getElementById('d-result').innerHTML='<span style="color:var(--red)">❌ '+e.message+'</span>';
    btn.disabled=false;btn.textContent='📤 ส่งทั้งหมดให้ลูกค้า';
  });
}

function handleFileSelect(inp){
  var f=inp.files[0];if(!f) return;
  var zone=document.getElementById('uzone');
  var prog=document.getElementById('uprog');
  var name=document.getElementById('uname');
  prog.style.display='block';prog.textContent='⏳ กำลังอัปโหลด...';
  var fd=new FormData();fd.append('file',f);
  fetch('/upload-file',{method:'POST',body:fd})
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.status==='ok'){
      _fileUrl=d.file_url;_fileName=d.file_name;
      zone.className='uzone has-file';
      name.textContent='✅ '+d.file_name;name.style.display='block';prog.style.display='none';
    }else{prog.textContent='❌ อัปโหลดไม่สำเร็จ';}
  }).catch(function(){prog.textContent='❌ เกิดข้อผิดพลาดค่ะ';});
}

function showSlip(src){document.getElementById('smodal-img').src=src;document.getElementById('smodal').classList.add('show');}
function closeSlip(){document.getElementById('smodal').classList.remove('show');document.getElementById('smodal-img').src='';}
document.addEventListener('keydown',function(e){if(e.key==='Escape'){closeSlip();closeDetail();}});

(function(){
  var p=new URLSearchParams(window.location.search);
  var id=p.get('open');
  var byName=p.get('by');
  if(byName) _claimedByUrl=decodeURIComponent(byName);
  if(!id) return;
  // เก็บ ?by= ไว้ ลบแค่ ?open=
  p.delete('open');
  window.history.replaceState({},'',window.location.pathname+(p.toString()?'?'+p.toString():''));
  var row=document.querySelector('tr[data-id="'+id+'"]');
  if(row){
    row.scrollIntoView({behavior:'smooth',block:'center'});
    setTimeout(function(){
      showConfirmPopup(row);
    },500);
  }
})();

function refreshPage(){
  if(document.getElementById('det-overlay').classList.contains('show')) return;
  var btn=document.getElementById('refresh-btn');
  btn.textContent='⏳';btn.disabled=true;
  setTimeout(function(){location.reload();},300);
}


/* ── Quick Reply Manager ── */
var _quickReplies = []; // โหลดจาก DB ผ่าน API

function loadQuickReplies(){
  fetch('/quick-replies')
    .then(function(r){ return r.json(); })
    .then(function(res){
      _quickReplies = res.data || [];
      var sel=document.getElementById('quick-reply-sel');
      if(!sel) return;
      sel.innerHTML="<option value=''>— เลือกข้อความสำเร็จรูป หรือพิมพ์เองค่ะ —</option>";
      _quickReplies.forEach(function(item){
        var o=document.createElement('option');
        o.value=item.text;
        o.textContent=item.text.length>50?item.text.substring(0,50)+'...':item.text;
        sel.appendChild(o);
      });
    })
    .catch(function(e){ console.error('loadQuickReplies error',e); });
}
function applyQuickReply(){
  var sel=document.getElementById('quick-reply-sel');
  var ta=document.getElementById('d-msg');
  if(sel&&ta&&sel.value) ta.value=sel.value;
}
function openQuickReplyMgr(){
  fetch('/quick-replies')
    .then(function(r){ return r.json(); })
    .then(function(res){ _quickReplies=res.data||[]; renderQrList(); })
    .catch(function(e){ console.error(e); renderQrList(); });
  document.getElementById('qr-overlay').classList.add('show');
}
function closeQuickReplyMgr(){
  document.getElementById('qr-overlay').classList.remove('show');
  loadQuickReplies();
}
function renderQrList(){
  var list=document.getElementById('qr-list');
  if(!list) return;
  if(!_quickReplies.length){
    list.innerHTML="<div style='font-size:12px;color:#888;text-align:center;padding:16px'>ยังไม่มีข้อความสำเร็จรูปค่ะ</div>";
    return;
  }
  list.innerHTML=_quickReplies.map(function(item){
    return "<div class='qr-item'>"
      +"<div class='qr-item-text'>"+item.text.replace(/</g,'&lt;')+"</div>"
      +"<button onclick='editQr("+item.id+",this)' style='padding:3px 8px;border:1px solid #ddd;border-radius:6px;background:#fff;cursor:pointer;font-size:11px'>แก้</button>"
      +"<button onclick='deleteQr("+item.id+")' style='padding:3px 8px;border:1px solid #ffcdd2;border-radius:6px;background:#fff;cursor:pointer;font-size:11px;color:#e53935'>ลบ</button>"
      +"</div>";
  }).join('');
}
function addQuickReply(){
  var ta=document.getElementById('qr-new-text');
  if(!ta||!ta.value.trim()) return;
  var text=ta.value.trim();
  fetch('/quick-replies',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:text})
  })
  .then(function(r){ return r.json(); })
  .then(function(res){
    if(res.status==='ok'){
      ta.value='';
      fetch('/quick-replies').then(function(r){return r.json();}).then(function(res2){
        _quickReplies=res2.data||[]; renderQrList();
      });
    } else { alert('เกิดข้อผิดพลาด: '+res.detail); }
  })
  .catch(function(e){ console.error(e); });
}
function deleteQr(id){
  if(!confirm('ลบข้อความนี้ไหมคะ?')) return;
  fetch('/quick-replies/'+id,{method:'DELETE'})
  .then(function(r){ return r.json(); })
  .then(function(res){
    if(res.status==='ok'){
      fetch('/quick-replies').then(function(r){return r.json();}).then(function(res2){
        _quickReplies=res2.data||[]; renderQrList();
      });
    }
  })
  .catch(function(e){ console.error(e); });
}
function editQr(id,btn){
  var item=_quickReplies.find(function(x){return x.id===id;});
  if(!item) return;
  var t=prompt('แก้ไขข้อความค่ะ:',item.text);
  if(t===null||!t.trim()) return;
  fetch('/quick-replies',{
    method:'PUT',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:id,text:t.trim()})
  })
  .then(function(r){ return r.json(); })
  .then(function(res){
    if(res.status==='ok'){
      fetch('/quick-replies').then(function(r){return r.json();}).then(function(res2){
        _quickReplies=res2.data||[]; renderQrList();
      });
    } else { alert('เกิดข้อผิดพลาด: '+res.detail); }
  })
  .catch(function(e){ console.error(e); });
}

function doLogout(){
  fetch('/auth/logout',{method:'POST'}).then(function(){window.location.href='/login';});
}

function applyFilter(){
  var p=new URLSearchParams(window.location.search);
  var df=document.getElementById('df').value;
  var dt=document.getElementById('dt').value;
  var sq=document.getElementById('sq').value;
  var sf=document.getElementById('sf')?document.getElementById('sf').value:'';
  if(df)p.set('date_from',df);else p.delete('date_from');
  if(dt)p.set('date_to',dt);else p.delete('date_to');
  if(sf)p.set('status_filter',sf);else p.delete('status_filter');
  if(sq)p.set('search',sq);else p.delete('search');
  var af=document.getElementById('af')?document.getElementById('af').value:'';
  if(af)p.set('assignee_filter',af);else p.delete('assignee_filter');
  window.location.href='/dashboard?'+p.toString();
}
document.getElementById('sq').addEventListener('keydown',function(e){if(e.key==='Enter')applyFilter();});

"""
    js += f"var CERR={error_count_val},CD=30;\n"
    js += """
var tel=document.getElementById('timer-text');
var tk=setInterval(function(){
  if(document.getElementById('det-overlay').classList.contains('show')){if(tel)tel.textContent='—';return;}
  CD--;if(tel)tel.textContent=CD+'s';
  if(CD<=0){clearInterval(tk);fetch('/dashboard/error-count').then(function(r){return r.json();}).then(function(){location.reload();}).catch(function(){location.reload();});}
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
    "<th>สาเหตุ</th><th>สถานะ</th>"
    "<th>ผู้รับผิดชอบ</th><th>Invoice</th><th>ข้อความ OCR</th><th>สลิป</th>"
    "</tr></thead><tbody>"
)

def build_rows(logs):
    if not logs:
        return (TABLE_HEADER +
                "<tr><td colspan='12'><div class='empty-state'>"
                "<div class='icon'>📭</div><div>ยังไม่มีข้อมูลในระบบค่ะ</div>"
                "</div></td></tr></tbody></table>")
    rows = TABLE_HEADER
    for r in logs:
        r = dict(r)
        img_html = (
            f'<img src="data:image/jpeg;base64,{r["slip_image_b64"]}" '
            'class="slip-thumb" onclick="event.stopPropagation();showSlip(this.src)" title="ดูสลิป">'
            if r.get("slip_image_b64") else '<span class="no-img">—</span>'
        )
        status_val  = r.get("status") or ""
        is_ok      = "สำเร็จ" in status_val
        is_urgent  = not is_ok and any(kw in status_val for kw in _URGENT_KW)

        if "OCR อ่านไม่ได้" in status_val:
            cause_badge = '<span class="bc bc-ocr">อ่านสลิปไม่ได้</span>'
        elif "หา Ref No. ไม่เจอ" in status_val:
            cause_badge = '<span class="bc bc-ref">อ่าน Ref No. ไม่ได้</span>'
        elif "ไม่พบใบเสร็จใน API" in status_val:
            cause_badge = '<span class="bc bc-inv">ไม่พบใบเสร็จในระบบ</span>'
        elif not is_ok:
            _elbl = status_val.replace("❌","").strip() or "Error"
            cause_badge = f'<span class="bc bc-err">⚠️ {_elbl}</span>'
        else:
            cause_badge = '<span class="bc-none">—</span>'

        # Status badge — แสดงสถานะว่าสำเร็จหรือยัง
        case_status_val = r.get("case_status") or ""
        if "สำเร็จ" in status_val and "Support" in status_val:
            status_badge = '<span class="bst-ok">✅ สำเร็จ (Support)</span>'
        elif is_ok:
            status_badge = '<span class="bst-ok">✅ สำเร็จ</span>'
        elif case_status_val == "สำเร็จ":
            status_badge = '<span class="bst-ok">✅ สำเร็จ</span>'
        elif is_urgent:
            status_badge = '<span class="bst-pending">🔴 รอดำเนินการ</span>'
        else:
            status_badge = '<span class="bst-none">—</span>'

        ref_str    = r.get("ref_no") or "—"
        amount_str = f'{r["amount"]:,.2f}' if r.get("amount") else "—"
        inv_str    = r.get("invoice_no") or "—"
        inv_short  = inv_str[:13]+"…" if len(inv_str)>13 else inv_str
        ocr_short  = (r.get("ocr_text") or "")[:28]
        uid_full   = r.get("user_id") or ""
        uid_short  = uid_full[:14]+("…" if len(uid_full)>14 else "")
        ts_esc     = (r.get("timestamp") or "—").replace("'","&apos;")
        stat_esc   = status_val.replace("'","&apos;").replace('"',"&quot;")
        ref_esc    = ref_str.replace("'","&apos;")
        amt_esc    = f'{r["amount"]:,.2f} บาท' if r.get("amount") else "—"
        inv_esc    = inv_str.replace("'","&apos;")
        ocr_esc    = (r.get("ocr_text") or "")[:200].replace("'","&apos;").replace('"',"&quot;")
        hasslip_v  = "1" if r.get("slip_image_b64") else "0"
        _is_ref_err     = "หา Ref No. ไม่เจอ" in status_val
        _is_inv_err     = "ไม่พบใบเสร็จใน API" in status_val
        iserror_v  = "1" if (_is_ref_err or _is_inv_err) else "0"
        error_type_v = "ref_error" if _is_ref_err else ("invoice_error" if _is_inv_err else "none")
        _slip_type_attr = (r.get('slip_type') or '').replace(chr(39),'')
        claimed_val  = r.get("claimed_by") or ""
        claimed_attr = claimed_val.replace("'","&apos;")

        if is_ok:
            row_cls = "crow srow"
        elif is_urgent:
            row_cls = "crow urow"
        else:
            row_cls = "crow erow"

        rows += (
            f"<tr class='{row_cls}' onclick='showConfirmPopup(this)' "
            f"data-id='{r['id']}' data-uid='{uid_full}' data-ts='{ts_esc}' "
            f"data-status='{stat_esc}' data-ref='{ref_esc}' data-amt='{amt_esc}' "
            f"data-inv='{inv_esc}' data-ocr='{ocr_esc}' "
            f"data-sliptype='{_slip_type_attr}' "
            f"data-iserror='{iserror_v}' data-hasslip='{hasslip_v}' "
            f"data-claimedby='{claimed_attr}' data-errortype='{error_type_v}'>"
            f'<td class="td-id">{r["id"]}</td>'
            f'<td style="font-size:11px;color:#555">{r.get("timestamp") or "—"}</td>'
            f'<td class="td-ref" style="font-size:11px">{uid_short}</td>'
            f'<td style="font-size:11px;color:#666">{r.get("slip_type") or "—"}</td>'
            f'<td class="td-ref">{ref_str}</td>'
            f'<td class="td-amt">{amount_str}</td>'
            f'<td>{cause_badge}</td>'
            f'<td>{status_badge}</td>'
            f'<td class="td-claimed">'
            + (f'<span class="claimed-tag">{claimed_val}</span>' if claimed_val else '<span class="bc-none">—</span>')
            + '</td>'
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
               date_from='', date_to='', is_filtered=False, search='', status_filter='', session=None, assignee_filter="", assignee_list=None):

    kpi = (
        "<div class='kpi-grid'>"
        "<div class='kpi-card'><div class='kpi-icon'>📊</div><div>"
        "<div class='kpi-label'>รายการทั้งหมด</div>"
        f"<div class='kpi-value'>{total}</div>"
        "<div class='kpi-sub'>ทุกรายการ</div></div></div>"
        "<div class='kpi-card c-green'><div class='kpi-icon'>✅</div><div>"
        "<div class='kpi-label'>Bot สำเร็จ</div>"
        f"<div class='kpi-value'>{success}</div>"
        "<div class='kpi-sub'>ส่งใบเสร็จอัตโนมัติ</div></div></div>"
        "<div class='kpi-card c-red'><div class='kpi-icon'>⚠️</div><div>"
        "<div class='kpi-label'>ต้องดำเนินการ</div>"
        f"<div class='kpi-value'>{error}</div>"
        "<div class='kpi-sub'>Bot ส่งไม่สำเร็จ</div></div></div>"
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
        "<div class='fg'><div class='fl'>วันที่เริ่มต้น</div>"
        f"<input class='fi' type='date' id='df' value='{date_from}' onchange='applyFilter()'></div>"
        "<div class='fg'><div class='fl'>วันที่สิ้นสุด</div>"
        f"<input class='fi' type='date' id='dt' value='{date_to}' onchange='applyFilter()'></div>"
        "<div class='fdiv'></div>"
        "<div class='fg'><div class='fl'>กรองรายการ</div>"
        f"<select class='fi' id='sf' style='min-width:220px'>"
        f"<option value=''{' selected' if not status_filter else ''}>— ทั้งหมด —</option>"
        f"<option value='success'{' selected' if status_filter=='success' else ''}>✅ Bot สำเร็จ</option>"
        f"<option value='urgent'{' selected' if status_filter=='urgent' else ''}>⚡ Urgent (OCR/Ref/Invoice)</option>"
        f"<option value='error'{' selected' if status_filter=='error' else ''}>❌ Error ทั่วไป</option>"
        "</select></div>"
        "<div class='fdiv'></div>"
        "<div class='fg'><div class='fl'>ค้นหา (เลขอ้างอิง / User ID)</div>"
        f"<input class='fi' type='text' id='sq' placeholder='เช่น 12505000...' "
        f"value='{search}' style='min-width:190px'></div>"
        "<div class='fg'><div class='fl'>ผู้รับผิดชอบ</div>"
        f"<select class='fi' id='af' style='min-width:160px' onchange='applyFilter()'>"
        f"<option value=''{' selected' if not assignee_filter else ''}>— ทุกคน —</option>"
        + ''.join(
            f"<option value='{a}'{' selected' if assignee_filter == a else ''}>{a}</option>"
            for a in (assignee_list or [])
        )
        + "</select></div>"
        "<button class='btn btn-dark' onclick='applyFilter()'>ค้นหา</button>"
        "<a class='btn btn-outline' href='/dashboard'>รีเซ็ต</a>"
        + (f"<span class='fresult'>พบ {total} รายการ</span>" if is_filtered else '')
        + "</div></div>"
    )

    js = build_js(error)

    # ── Detail Popup (Fix 2+4: แสดงเฉพาะ error, เรียง section ตาม process) ──
    detail_popup = (
        "<div class='confirm-overlay' id='confirm-overlay'>"
        "<div class='confirm-popup'>"
        "<div class='confirm-header'><div class='confirm-header-title'>📋 ตรวจสอบข้อมูลเคสก่อนรับค่ะ</div>"
        "<button onclick='closeConfirmPopup()' style='background:none;border:none;color:#888;cursor:pointer;font-size:18px'>✕</button></div>"
        "<div class='confirm-body'>"
        "<div class='confirm-case-id' id='cp-id'></div>"
        "<div class='confirm-grid'>"
        "<div class='confirm-item'><div class='confirm-label'>LINE User ID</div><div class='confirm-value' id='cp-uid'>—</div></div>"
        "<div class='confirm-item'><div class='confirm-label'>ประเภทสลิป</div><div class='confirm-value' id='cp-type'>—</div></div>"
        "<div class='confirm-item'><div class='confirm-label'>เลขอ้างอิง</div><div class='confirm-value' id='cp-ref'>—</div></div>"
        "<div class='confirm-item'><div class='confirm-label'>ยอดเงิน</div><div class='confirm-value' id='cp-amt'>—</div></div>"
        "<div class='confirm-item'><div class='confirm-label'>สถานะ Bot</div><div class='confirm-value' id='cp-status'>—</div></div>"
        "<div class='confirm-item'><div class='confirm-label'>ผู้รับผิดชอบ</div><div class='confirm-value' id='cp-claimed'>—</div></div>"
        "</div>"
        "<div class='confirm-ocr-box'><div class='confirm-label' style='margin-bottom:5px'>ข้อความ OCR</div>"
        "<div class='confirm-ocr-text' id='cp-ocr'>—</div></div>"
        "<div id='cp-slip-wrap' style='margin-bottom:12px;display:none'>"
        "<div class='confirm-label' style='margin-bottom:5px'>รูปสลิป</div>"
        "<img id='cp-slip-img' style='width:100%;max-height:220px;object-fit:contain;"
        "border-radius:6px;border:1px solid #eee;cursor:zoom-in' onclick='showSlip(this.src)'></div>"
        "</div>"
        "<div class='confirm-actions'>"
        "<button class='btn-cp-close' onclick='closeConfirmPopup()'>ปิด</button>"
        "<button class='btn-cp-accept' id='cp-accept-btn' onclick='acceptCase()'>ยืนยันรับเคส</button>"
        "</div>"
        "</div></div>"

        # ── Quick Reply Manager Popup ──
        "<div class='qr-overlay' id='qr-overlay'>"
        "<div class='qr-popup'>"
        "<div class='qr-header'>"
        "<div style='color:#fff;font-weight:700;font-size:14px;flex:1'>⚙️ จัดการ Quick Reply</div>"
        "<button onclick='closeQuickReplyMgr()' style='background:none;border:none;color:#aaa;cursor:pointer;font-size:20px;line-height:1;padding:0'>✕</button>"
        "</div>"
        "<div class='qr-body'>"
        "<div id='qr-list'></div>"
        "<hr style='border:none;border-top:1px solid #eee;margin:12px 0'>"
        "<div style='font-size:11px;font-weight:600;color:#555;margin-bottom:6px'>➕ เพิ่มข้อความใหม่</div>"
        "<textarea id='qr-new-text' rows='2' style='width:100%;box-sizing:border-box;border:1.5px solid #ddd;border-radius:8px;padding:8px 10px;font-size:12px;font-family:inherit;resize:vertical' placeholder='พิมพ์ข้อความสำเร็จรูปใหม่ค่ะ...'></textarea>"
        "<button onclick='addQuickReply()' style='margin-top:8px;width:100%;padding:9px;background:#f26522;color:#fff;border:none;border-radius:8px;font-weight:700;font-size:13px;cursor:pointer;font-family:inherit'>+ เพิ่มข้อความ</button>"
        "</div></div></div>"

        "<div class='det-overlay' id='det-overlay'>"
        "<div class='det-popup'>"
        "<div class='det-hdr'>"
        "<div><div class='det-title'>📋 รายละเอียดรายการ</div>"
        "<div class='det-sub' id='d-sub'></div></div>"
        "<button class='det-close' onclick='closeDetail()'>✕</button>"
        "</div>"
        # Info + Slip
        "<div class='det-body'>"
        "<div class='det-info'><div class='igrid'>"
        "<div class='iitem'><div class='ikey'>👤 ผู้ใช้</div><div class='ival m' id='d-uid'></div></div>"
        "<div class='iitem'><div class='ikey'>🕐 วันที่/เวลา</div><div class='ival' id='d-ts'></div></div>"
        "<div class='iitem full'><div class='ikey'>⚠️ สาเหตุที่ Bot ส่งไม่สำเร็จ</div><div id='d-status'></div></div>"
        "<div class='iitem full'><div class='ikey'>📄 เลขที่ใบเสร็จ</div><div class='ival m' id='d-inv'></div></div>"
        "<div class='iitem'><div class='ikey'>🔢 หมายเลขอ้างอิง</div><div class='ival m' id='d-ref'></div></div>"
        "<div class='iitem'><div class='ikey'>💰 จำนวนเงิน (บาท)</div><div class='ival m' id='d-amt'></div></div>"
        "<div class='iitem full' style='border-bottom:none'><div class='ikey'>🔍 ข้อความ OCR</div>"
        "<div class='ival' id='d-ocr' style='font-size:11px;color:#888'></div></div>"
        "</div></div>"
        "<div class='det-slip-col'>"
        "<div class='ikey' style='align-self:flex-start;margin-bottom:8px'>🧾 สลิปโอนเงิน</div>"
        "<div id='d-slip-wrap' style='width:100%;display:flex;justify-content:center;min-height:80px'></div>"
        "</div></div>"

        # Claimed banner — แสดงชื่อผู้รับผิดชอบ (ดึงจาก ?by= อัตโนมัติ)
        "<div class='claimed-banner' id='d-claimed-banner'></div>"


        "<div id='d-reply-block'>"

        "<input type='hidden' id='cp-error-type' value=''>"

        # ── Section A: ref_error — กรอก Ref No. + Amount ค่ะ ──
        "<div id='d-ref-section'>"
        "<div class='det-section'>"
        "<div class='det-sec-title'>🔍 ค้นหาใบเสร็จด้วยข้อมูลที่ถูกต้อง</div>"
        "<div class='msearch'>"
        "<div class='msearch-row'>"
        "<div class='msearch-fg'><div class='msearch-label'>หมายเลขอ้างอิง</div>"
        "<input class='msearch-input' id='ms-ref' placeholder='เช่น 125050000014'></div>"
        "<div class='msearch-fg' style='max-width:130px'><div class='msearch-label'>จำนวนเงิน (บาท)</div>"
        "<input class='msearch-input' id='ms-amt' type='number' step='0.01' placeholder='เช่น 802.50'></div>"
        "<button class='btn btn-dark btn-sm' onclick='doManualSearch()' id='ms-btn' "
        "style='align-self:flex-end;white-space:nowrap'>🔍 ค้นหา</button>"
        "</div>"
        "<div class='msearch-status' id='ms-status'></div>"
        "<div class='inv-results' id='ms-results'></div>"
        "<div class='send-preview' id='ms-preview'>"
        "✅ พบใบเสร็จแล้วค่ะ — พิมพ์ข้อความด้านล่าง (ถ้ามี) แล้วกด 📤 ส่งได้เลยค่ะ"
        "</div>"
        "</div></div>"
        "</div>"  # end d-ref-section

        # ── Section B: invoice_error — ส่งข้อความหาลูกค้าค่ะ ──
        "<div id='d-msg-section'>"
        "<div class='det-section'>"
        "<div class='det-sec-title'>💬 ส่งข้อความให้ลูกค้า</div>"
        "<div style='margin-bottom:8px'>"
        "<div style='font-size:11px;font-weight:600;color:#555;margin-bottom:4px'>Quick Reply — เลือกข้อความสำเร็จรูปค่ะ</div>"
        "<div style='display:flex;gap:6px;align-items:center'>"
        "<select id='quick-reply-sel' class='fi' style='flex:1;font-size:12px' onchange='applyQuickReply()'>"
        "<option value=''>— เลือกข้อความสำเร็จรูป หรือพิมพ์เองค่ะ —</option>"
        "</select>"
        "<button class='btn btn-outline btn-sm' onclick='openQuickReplyMgr()' style='font-size:11px;white-space:nowrap'>⚙️ จัดการ</button>"
        "</div></div>"
        "<textarea class='det-ta' id='d-msg' "
        "placeholder='พิมพ์ข้อความที่จะส่งให้ลูกค้าค่ะ...'></textarea>"
        "</div>"
        "</div>"  # end d-msg-section


        # Footer ปุ่มส่งทีเดียว (ไม่มีปุ่มแยก)
        # Resolution note — หมายเหตุเพิ่มเติมจาก Support
        "<div class='res-note-wrap'>"
        "<div style='font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:#27ae60;margin-bottom:5px'>หมายเหตุการแก้ไข (เพิ่มเติม — ไม่บังคับ)</div>"
        "<textarea class='res-note-ta' id='d-res-note' "
        "placeholder='เช่น ลูกค้าโอนมาผิดยอด ต้องตรวจสอบสลิปเพิ่มเติม...'></textarea>"
        "</div>"

        "<div class='det-footer'>"
        "<div class='det-result' id='d-result'></div>"
        "<div class='det-acts'>"
        "<button class='btn btn-outline' onclick='closeDetail()'>✕ ปิด</button>"
        "<button class='btn btn-green' id='d-send-btn' onclick='sendAll()'>"
        "📤 ส่งทั้งหมดให้ลูกค้า</button>"
        "</div></div>"

        "</div>"  # end d-reply-block


        "</div></div>"  # end det-popup + det-overlay
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
        f"<span id='session-name' data-name='{(session or {}).get('display_name','')}' style='display:none'></span>"
        f"<span id='session-name' data-name='{(session or {}).get('display_name','')}' style='display:none'></span>"
        "<div class='topnav'><div class='topnav-brand'>KLN Seaport Ltd.</div>",
        "<div class='topnav-right'><span class='live-dot'>LIVE</span>",
        f"<span>{now}</span><span class='sep'>|</span>",
        "<span>K-Digi · ฝ่าย Application Support</span></div></div>",
        "<div class='subnav'><div class='subnav-title'>ระบบติดตามรายการ</div>",
        "<div class='subnav-right'>",
        f"<span>อัปเดต {now}</span><span>·</span>",
        "<span>รีเฟรชใน <span id='timer-text'>30s</span></span></div></div>",
        "<main>",
        "<div class='page-title-bar'>",
        "<div><div class='page-title'>K-Digi ระบบติดตามรายการ</div>",
        f"<div class='page-sub'>แสดง {total} รายการ · ลับเฉพาะ — สำหรับใช้ภายในเท่านั้น</div></div>",
        "<div class='page-actions'>",
        "<a href='/dashboard/export' class='btn btn-outline btn-sm'>⬇ Export CSV</a>",
        "<button class='btn btn-dark btn-sm' onclick='refreshPage()' id='refresh-btn'>↻ Refresh</button>"
        f"<span style='font-size:11px;color:#f26522;font-weight:600;margin-left:8px'>{(session or {}).get('display_name','')}</span>"
        f"<span style='font-size:10px;color:#888;margin-left:4px'>({'Admin' if (session or {}).get('role')=='admin' else 'Support'})</span>"
        + ("<button class='btn btn-outline btn-sm' onclick=\"window.location.href='/admin/users/page'\" style='font-size:11px;margin-left:6px'>จัดการ Users</button>" if session and session.get('role')=='admin' else "")
        + "<button class='btn btn-outline btn-sm' onclick='doLogout()' style='font-size:11px;margin-left:4px'>ออกจากระบบ</button>",
        "</div></div>",
        kpi,
        filter_panel,
        "<div class='table-toolbar'><div class='tl'>",
        "<span class='section-title'>รายการธุรกรรม</span>",
        f"<span class='row-count'>{total} rows</span>",
        "</div></div>",
        f"<div class='table-box'>{rows_html}</div>",
        "</main>",
        "<div class='footer'>",
        "<div><strong>KLN Seaport Ltd.</strong> — K-Digi Receipt Bot | ฝ่าย Application Support</div>",
        "<div>ลับเฉพาะ — สำหรับใช้ภายในเท่านั้น</div></div>",
        detail_popup,
        slip_modal,
        f"<script>{js}</script>",
        # Name popup — โผล่ครั้งแรกที่เปิด Dashboard ค่ะ
        "<div class='name-overlay' id='name-overlay' style='display:none'>"
        "<div class='name-card'>"
        "<h2>สวัสดีค่ะ</h2>"
        "<p>กรุณาระบุชื่อของคุณเพื่อใช้แสดงในระบบค่ะ<br>ระบบจะจำชื่อไว้ให้ค่ะ ไม่ต้องพิมพ์ซ้ำค่ะ</p>"
        "<input class='name-inp' id='name-inp' type='text' placeholder='ชื่อของคุณ เช่น สมใจ'>"
        "<button class='name-save-btn' onclick='saveSupportName()'>บันทึกและเริ่มใช้งาน</button>"
        "</div></div>"

        "</body></html>",
    ]
    return ''.join(parts)

# ══════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════


def build_login_page() -> str:
    return """<!DOCTYPE html>
<html lang="th"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>K-Digi Dashboard — Login</title>
<link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Sarabun',sans-serif;background:#0d1b2a;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:#fff;border-radius:16px;padding:40px 36px;max-width:380px;width:90%;box-shadow:0 8px 40px rgba(0,0,0,.4)}
.logo{text-align:center;margin-bottom:28px}
.logo-icon{width:56px;height:56px;background:#f26522;border-radius:12px;display:flex;align-items:center;justify-content:center;margin:0 auto 12px;font-size:28px}
.logo-title{font-size:20px;font-weight:700;color:#1a1a1a}
.logo-sub{font-size:12px;color:#888;margin-top:3px}
label{display:block;font-size:12px;font-weight:600;color:#555;margin-bottom:5px}
input{width:100%;padding:11px 14px;border:1.5px solid #ddd;border-radius:8px;font-size:14px;font-family:inherit;transition:border-color .15s;margin-bottom:14px}
input:focus{outline:none;border-color:#f26522;box-shadow:0 0 0 3px rgba(242,101,34,.1)}
.btn{width:100%;padding:13px;border:none;border-radius:10px;background:#f26522;color:#fff;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit}
.btn:disabled{background:#ccc;cursor:not-allowed}
.err{color:#e74c3c;font-size:13px;text-align:center;margin-top:10px;min-height:18px}
.hint{font-size:11px;color:#bbb;text-align:center;margin-top:14px}
</style></head><body>
<div class="card">
  <div class="logo"><div class="logo-icon">📄</div>
    <div class="logo-title">K-Digi Receipt Bot</div>
    <div class="logo-sub">Application Support Dashboard</div></div>
  <label>Username</label><input type="text" id="usr" autocomplete="username">
  <label>Password</label><input type="password" id="pwd" autocomplete="current-password">
  <button class="btn" id="btn" onclick="doLogin()">เข้าสู่ระบบ</button>
  <div class="err" id="err"></div>
  <div class="hint">KLN Seaport Limited — K-Digi Support Team</div>
</div>
<script>
document.addEventListener('DOMContentLoaded',function(){
  document.getElementById('usr').addEventListener('keydown',function(e){if(e.key==='Enter')document.getElementById('pwd').focus();});
  document.getElementById('pwd').addEventListener('keydown',function(e){if(e.key==='Enter')doLogin();});
  document.getElementById('usr').focus();
});
async function doLogin(){
  var btn=document.getElementById('btn'),err=document.getElementById('err');
  var usr=document.getElementById('usr').value.trim(),pwd=document.getElementById('pwd').value;
  if(!usr||!pwd){err.textContent='กรุณากรอก username และ password ค่ะ';return;}
  btn.disabled=true;btn.textContent='⏳ กำลังเข้าสู่ระบบ...';err.textContent='';
  try{
    var r=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:usr,password:pwd})});
    var d=await r.json();
    if(d.status==='ok'){var redir=new URLSearchParams(window.location.search).get('next')||'/dashboard';window.location.href=redir;}
    else{err.textContent=d.detail||'เข้าสู่ระบบไม่สำเร็จค่ะ';btn.disabled=false;btn.textContent='เข้าสู่ระบบ';}
  }catch(e){err.textContent='เกิดข้อผิดพลาดค่ะ';btn.disabled=false;btn.textContent='เข้าสู่ระบบ';}
}
</script></body></html>"""


def build_user_management_page(users: list, current_user: dict) -> str:
    rows = ""
    for u in users:
        ab = "<span style='color:#27ae60;font-weight:600'>✅ ใช้งาน</span>" if u["is_active"] else "<span style='color:#e74c3c;font-weight:600'>❌ ปิดใช้</span>"
        rb = "<span style='background:#fff3e0;color:#e65100;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600'>Admin</span>" if u["role"]=="admin" else "<span style='background:#e3f2fd;color:#1565c0;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600'>Support</span>"
        dis = "disabled style='opacity:.4'" if u["id"]==current_user["user_id"] else ""
        tds = (
            f"<td style='padding:10px 12px;font-size:13px'>{u['id']}</td>"
            f"<td style='padding:10px 12px;font-size:13px;font-weight:600'>{u['username']}</td>"
            f"<td style='padding:10px 12px;font-size:13px'>{u['display_name']}</td>"
            f"<td style='padding:10px 12px'>{rb}</td>"
            f"<td style='padding:10px 12px'>{ab}</td>"
            f"<td style='padding:10px 12px;font-size:12px;color:#888'>{u.get('last_login') or '—'}</td>"
            f"<td style='padding:10px 12px'>"
            f"<button onclick='editUser({u['id']},\"{u['username']}\",\"{u['display_name']}\",\"{u['role']}\",{u['is_active']})' "
            "style='padding:4px 10px;border:1px solid #ddd;border-radius:6px;background:#fff;cursor:pointer;font-size:12px;margin-right:4px'>แก้ไข</button>"
            f"<button onclick='deactivateUser({u['id']})' {dis} "
            "style='padding:4px 10px;border:1px solid #ffcdd2;border-radius:6px;background:#fff;cursor:pointer;font-size:12px;color:#e53935'>ปิดใช้</button>"
            "</td>"
        )
        rows += f"<tr style='border-bottom:1px solid #f0f0f0'>{tds}</tr>"
    return f"""<!DOCTYPE html><html lang="th"><head>
<meta charset="UTF-8"><title>K-Digi — จัดการ Users</title>
<link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@400;600;700&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Sarabun',sans-serif;background:#f5f5f5;padding:24px}}.hdr{{background:#1a1a1a;color:#fff;padding:16px 24px;border-radius:12px;display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}}.card{{background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,.06);margin-bottom:20px}}table{{width:100%;border-collapse:collapse}}th{{padding:10px 12px;text-align:left;font-size:12px;font-weight:600;color:#888;background:#f9f9f9;border-bottom:2px solid #f0f0f0}}input,select{{width:100%;padding:9px 12px;border:1.5px solid #ddd;border-radius:8px;font-size:13px;font-family:inherit;margin-bottom:10px}}.bp{{background:#f26522;color:#fff;border:none;border-radius:8px;padding:10px 20px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit}}.bs{{background:#f5f5f5;color:#444;border:1px solid #ddd;border-radius:8px;padding:10px 20px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit}}.ov{{position:fixed;inset:0;background:rgba(0,0,0,.5);display:none;align-items:center;justify-content:center;z-index:100}}.ov.show{{display:flex}}.modal{{background:#fff;border-radius:16px;padding:28px;width:400px;max-width:90%}}.ok{{color:#27ae60}}.err{{color:#e74c3c}}</style></head><body>
<div class="hdr"><div style="font-size:16px;font-weight:700">K-Digi <span style="color:#f26522">Receipt Bot</span> — จัดการ Users</div>
<div style="display:flex;gap:8px"><span style="font-size:12px;color:#f26522;font-weight:600">{current_user['display_name']} (Admin)</span>
<button class="bs" onclick="window.location.href='/dashboard'" style="font-size:12px;padding:6px 12px">← Dashboard</button>
<button class="bs" onclick="doLogout()" style="font-size:12px;padding:6px 12px">ออกจากระบบ</button></div></div>
<div class="card"><div style="font-size:14px;font-weight:700;margin-bottom:16px">รายชื่อ Users ทั้งหมด</div>
<table><tr><th>#</th><th>Username</th><th>ชื่อที่แสดง</th><th>Role</th><th>สถานะ</th><th>Login ล่าสุด</th><th>จัดการ</th></tr>{rows}</table></div>
<div class="card"><div style="font-size:14px;font-weight:700;margin-bottom:16px">เพิ่ม User ใหม่</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
<div><label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px">Username</label><input type="text" id="n-u"></div>
<div><label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px">Password</label><input type="password" id="n-p"></div>
<div><label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px">ชื่อที่แสดง</label><input type="text" id="n-n" placeholder="เช่น สมใจ"></div>
<div><label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px">Role</label><select id="n-r"><option value="support">Support</option><option value="admin">Admin</option></select></div>
</div><button class="bp" onclick="createUser()">+ เพิ่ม User</button>
<div id="cr" style="font-size:13px;margin-top:8px;min-height:18px"></div></div>
<div class="ov" id="edit-ov"><div class="modal"><div style="font-size:15px;font-weight:700;margin-bottom:16px">แก้ไข User</div>
<input type="hidden" id="e-id">
<label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px">Username</label><input type="text" id="e-u" disabled style="background:#f9f9f9;color:#888">
<label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px">ชื่อที่แสดง</label><input type="text" id="e-n">
<label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px">Role</label><select id="e-r"><option value="support">Support</option><option value="admin">Admin</option></select>
<label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px">สถานะ</label><select id="e-a"><option value="1">ใช้งาน</option><option value="0">ปิดใช้</option></select>
<label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px">Password ใหม่ (ไม่บังคับ)</label><input type="password" id="e-p" placeholder="เว้นว่างถ้าไม่เปลี่ยน">
<div style="display:flex;gap:8px;margin-top:4px"><button class="bp" onclick="saveUser()">บันทึก</button><button class="bs" onclick="closeEdit()">ยกเลิก</button></div>
<div id="er" style="font-size:13px;margin-top:8px;min-height:18px"></div></div></div>
<script>
async function createUser(){{var u=document.getElementById('n-u').value.trim(),p=document.getElementById('n-p').value,n=document.getElementById('n-n').value.trim(),r=document.getElementById('n-r').value,res=document.getElementById('cr');
if(!u||!p||!n){{res.innerHTML='<span class="err">กรุณากรอกข้อมูลให้ครบค่ะ</span>';return;}}
var rr=await fetch('/admin/users/create',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{username:u,password:p,display_name:n,role:r}})}});
var d=await rr.json();if(d.status==='ok'){{res.innerHTML='<span class="ok">✅ เพิ่มสำเร็จค่ะ</span>';setTimeout(function(){{location.reload();}},800);}}else res.innerHTML='<span class="err">❌ '+d.detail+'</span>';}}
function editUser(id,u,n,r,a){{document.getElementById('e-id').value=id;document.getElementById('e-u').value=u;document.getElementById('e-n').value=n;document.getElementById('e-r').value=r;document.getElementById('e-a').value=a;document.getElementById('e-p').value='';document.getElementById('er').innerHTML='';document.getElementById('edit-ov').classList.add('show');}}
function closeEdit(){{document.getElementById('edit-ov').classList.remove('show');}}
async function saveUser(){{var id=parseInt(document.getElementById('e-id').value),n=document.getElementById('e-n').value.trim(),r=document.getElementById('e-r').value,a=parseInt(document.getElementById('e-a').value),p=document.getElementById('e-p').value;
var rr=await fetch('/admin/users/update',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{user_id:id,display_name:n,role:r,is_active:a,new_password:p}})}});
var d=await rr.json();if(d.status==='ok'){{document.getElementById('er').innerHTML='<span class="ok">✅ บันทึกแล้วค่ะ</span>';setTimeout(function(){{location.reload();}},800);}}else document.getElementById('er').innerHTML='<span class="err">❌ '+d.detail+'</span>';}}
async function deactivateUser(id){{if(!confirm('ปิดใช้งาน User นี้ไหมคะ?'))return;var r=await fetch('/admin/users/deactivate',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{user_id:id}})}});var d=await r.json();if(d.status==='ok')location.reload();else alert(d.detail);}}
async function doLogout(){{await fetch('/auth/logout',{{method:'POST'}});window.location.href='/login';}}
</script></body></html>"""

def add_dashboard_route(app: FastAPI):

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request):
        from auth import get_session_from_request as _sess
        from fastapi.responses import RedirectResponse as _R
        session = _sess(request)
        if not session:
            from urllib.parse import quote as _q
            _cur = str(request.url.path) + ('?' + request.url.query if request.url.query else '')
            return _R(url=f"/login?next={_q(_cur)}", status_code=302)
        date_from       = request.query_params.get("date_from", "")
        date_to         = request.query_params.get("date_to", "")
        search          = request.query_params.get("search", "")
        status_filter   = request.query_params.get("status_filter", "")
        assignee_filter = request.query_params.get("assignee_filter", "")
        is_filtered     = bool(date_from or date_to or search or status_filter or assignee_filter)
        logs    = get_logs(date_from or None, date_to or None, search or None, status_filter or None, assignee_filter or None)
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
        # ดึงรายชื่อผู้รับผิดชอบทั้งหมดจาก DB สำหรับ dropdown ค่ะ
        import sqlite3 as _sq_af
        _conn_af = _sq_af.connect("kdigi_logs.db")
        _rows_af = _conn_af.execute("""
            SELECT DISTINCT claimed_by FROM logs WHERE claimed_by != '' AND claimed_by IS NOT NULL ORDER BY 1
        """).fetchall()
        _conn_af.close()
        assignee_list = sorted(set(r[0] for r in _rows_af if r[0]))
        html = build_html(total, success, error, rate, now,
                          rows_html, chart_labels, chart_success, chart_error,
                          date_from, date_to, is_filtered, search, status_filter,
                          session=session, assignee_filter=assignee_filter,
                          assignee_list=assignee_list)
        return HTMLResponse(content=html)

    @app.get("/dashboard/error-count")
    def error_count():
        logs = get_logs()
        err  = sum(1 for r in logs if "สำเร็จ" not in (dict(r).get("status") or ""))
        return JSONResponse({"error_count": err, "total": len(logs)})

    @app.get("/admin/users/page", response_class=HTMLResponse)
    def admin_users_page(request: Request):
        from auth import require_admin as _ra, get_all_users as _gau
        from fastapi.responses import RedirectResponse as _R, HTMLResponse as _H
        session = _ra(request)
        if not session:
            return _R(url="/login", status_code=302)
        return _H(content=build_user_management_page(_gau(), session))

    @app.get("/dashboard/export")
    def export_csv():
        logs  = get_logs()
        today = datetime.now().strftime("%Y-%m-%d")
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID","Timestamp","User ID","Slip Type",
                         "Reference No.","Amount (THB)","Status",
                         "Invoice No.","OCR Text"])
        for r in logs:
            r = dict(r)
            writer.writerow([
                r.get("id"), r.get("timestamp",""), r.get("user_id",""),
                r.get("slip_type",""), r.get("ref_no",""), r.get("amount",""),
                r.get("status",""),
                r.get("invoice_no",""), (r.get("ocr_text","") or "")[:200]
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f"attachment; filename=kdigi_logs_{today}.csv"}
        )

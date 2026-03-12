import sqlite3
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import io
import csv
import json

DB_PATH = "kdigi_logs.db"


# ══════════════════════════════════════════════════════════════
# Database helpers
# ══════════════════════════════════════════════════════════════

def get_logs():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM logs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_chart_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            DATE(timestamp) as day,
            SUM(CASE WHEN status LIKE '%สำเร็จ%' THEN 1 ELSE 0 END) as success,
            SUM(CASE WHEN status NOT LIKE '%สำเร็จ%' THEN 1 ELSE 0 END) as error
        FROM logs
        WHERE timestamp >= DATE('now', '-6 days')
        GROUP BY DATE(timestamp)
        ORDER BY day ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


# ══════════════════════════════════════════════════════════════
# HTML builder — แยก JS ออกมาเพื่อหลีกเลี่ยงปัญหา </script> ใน f-string
# ══════════════════════════════════════════════════════════════

def build_html(total, success, error, rate, now, rows_html, chart_labels, chart_success, chart_error):
    bar_w = rate

    # ── CSS ───────────────────────────────────────────────────────
    css = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --navy:      #0d1b2a;
  --navy-mid:  #162338;
  --navy-soft: #1e3352;
  --orange:    #f26522;
  --orange-lt: #f9874a;
  --cream:     #faf9f7;
  --border:    #dde1e7;
  --muted:     #8a93a2;
  --text:      #1a2233;
  --green:     #1a7a4a;
  --green-bg:  #edf7f2;
  --red:       #c0392b;
  --red-bg:    #fdf0ee;
  --radius:    6px;
  --shadow-sm: 0 1px 4px rgba(0,0,0,.08);
  --shadow-md: 0 4px 16px rgba(0,0,0,.10);
}
html { font-size: 14px; }
body { font-family: 'IBM Plex Sans Thai', sans-serif; background: var(--cream); color: var(--text); min-height: 100vh; }
.topbar { background: var(--navy); border-bottom: 3px solid var(--orange); padding: 0 40px; display: flex; align-items: stretch; justify-content: space-between; height: 64px; }
.topbar-left { display: flex; align-items: center; gap: 16px; }
.logo-mark { width: 36px; height: 36px; background: var(--orange); border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; color: white; letter-spacing: -1px; flex-shrink: 0; }
.brand-text .company { font-size: 15px; font-weight: 600; color: white; letter-spacing: .3px; }
.brand-text .system { font-size: 11px; color: var(--muted); letter-spacing: .5px; text-transform: uppercase; }
.topbar-right { display: flex; align-items: center; gap: 24px; }
.live-dot { display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--muted); letter-spacing: .4px; }
.live-dot::before { content: ''; width: 8px; height: 8px; background: #2ecc71; border-radius: 50%; box-shadow: 0 0 0 3px rgba(46,204,113,.25); animation: pulse 2s infinite; }
@keyframes pulse { 0%,100% { box-shadow: 0 0 0 3px rgba(46,204,113,.25); } 50% { box-shadow: 0 0 0 6px rgba(46,204,113,.10); } }
.topbar-time { font-size: 12px; color: var(--muted); font-family: 'IBM Plex Mono', monospace; border-left: 1px solid var(--navy-soft); padding-left: 24px; }
main { max-width: 1400px; margin: 0 auto; padding: 32px 40px 60px; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }
.kpi-card { background: white; border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow-sm); padding: 20px 24px; position: relative; overflow: hidden; }
.kpi-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--orange); }
.kpi-label { font-size: 10px; font-weight: 600; letter-spacing: 1.2px; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
.kpi-value { font-size: 36px; font-weight: 700; color: var(--text); line-height: 1; margin-bottom: 4px; font-family: 'IBM Plex Mono', monospace; }
.kpi-sub { font-size: 11px; color: var(--muted); }
.progress-wrap { margin-top: 12px; background: #f0f2f5; border-radius: 99px; height: 4px; overflow: hidden; }
.progress-bar { height: 100%; border-radius: 99px; background: linear-gradient(90deg, var(--orange), var(--orange-lt)); transition: width .6s ease; }
.section-label { font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: var(--muted); margin-bottom: 16px; }
.divider { border: none; border-top: 1px solid var(--border); margin: 28px 0; }
.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.toolbar-left { display: flex; align-items: center; gap: 12px; }
.row-count { font-size: 11px; color: var(--muted); font-family: 'IBM Plex Mono', monospace; background: #f0f2f5; padding: 3px 8px; border-radius: 99px; }
.btn-refresh { display: flex; align-items: center; gap: 6px; background: var(--navy); color: white; border: none; padding: 8px 18px; border-radius: var(--radius); font-size: 12px; font-weight: 600; letter-spacing: .4px; text-transform: uppercase; cursor: pointer; font-family: 'IBM Plex Sans Thai', sans-serif; }
.btn-refresh:hover { background: #1e2f45; }
.btn-export { display: flex; align-items: center; gap: 6px; background: var(--green); color: white; border: none; padding: 8px 18px; border-radius: var(--radius); font-size: 12px; font-weight: 600; letter-spacing: .4px; text-transform: uppercase; cursor: pointer; text-decoration: none; font-family: 'IBM Plex Sans Thai', sans-serif; }
.table-wrap { background: white; border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow-sm); overflow: hidden; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead { background: var(--navy); }
th { padding: 11px 14px; text-align: left; font-size: 10px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: #ffffff; white-space: nowrap; }
td { padding: 11px 14px; border-bottom: 1px solid #f0f2f5; vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fafbfc; }
.badge { display: inline-block; padding: 3px 10px; border-radius: 99px; font-size: 10px; font-weight: 700; letter-spacing: .6px; }
.badge-ok  { background: var(--green-bg); color: var(--green); }
.badge-err { background: var(--red-bg);   color: var(--red); }
.td-id   { color: var(--muted); font-family: 'IBM Plex Mono', monospace; width: 48px; }
.td-ref  { font-family: 'IBM Plex Mono', monospace; font-size: 12px; }
.td-amt  { font-family: 'IBM Plex Mono', monospace; font-size: 12px; text-align: right; }
.td-inv  { font-size: 11px; color: #445; max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-ocr  { font-size: 11px; color: var(--muted); max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-img  { width: 72px; }
.slip-thumb { width: 56px; height: 40px; object-fit: cover; border-radius: 4px; cursor: zoom-in; border: 1px solid var(--border); }
.no-img { font-size: 10px; color: var(--muted); }
.empty-state { text-align: center; padding: 60px 20px; color: var(--muted); }
.empty-state .icon { font-size: 40px; margin-bottom: 12px; }
.modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.75); z-index: 1000; align-items: center; justify-content: center; }
.modal.show { display: flex; }
.modal-inner { background: white; border-radius: 10px; padding: 24px; max-width: 520px; width: 90%; }
.modal-label { font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: var(--muted); margin-bottom: 12px; }
.modal-img { width: 100%; border-radius: 6px; margin-bottom: 16px; }
.btn-close { width: 100%; padding: 10px; background: var(--navy); color: white; border: none; border-radius: var(--radius); font-size: 13px; cursor: pointer; font-family: 'IBM Plex Sans Thai', sans-serif; }
.footer { background: var(--navy); color: var(--muted); font-size: 11px; padding: 16px 40px; display: flex; justify-content: space-between; margin-top: 40px; border-top: 1px solid var(--navy-soft); }
.chart-wrap { background: white; border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow-sm); padding: 24px 28px; margin-bottom: 32px; }
"""

    # ── KPI Cards ──────────────────────────────────────────────────
    kpi_html = f"""
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-label">Total Transactions</div>
    <div class="kpi-value">{total}</div>
    <div class="kpi-sub">All time</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Completed</div>
    <div class="kpi-value" style="color:var(--green)">{success}</div>
    <div class="kpi-sub">สำเร็จแล้วค่ะ</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Errors</div>
    <div class="kpi-value" style="color:var(--red)">{error}</div>
    <div class="kpi-sub">ต้องดำเนินการค่ะ</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Success Rate</div>
    <div class="kpi-value">{rate}<span style="font-size:18px;color:var(--muted)">%</span></div>
    <div class="progress-wrap"><div class="progress-bar" style="width:{bar_w}%"></div></div>
  </div>
</div>"""

    # ── Rows table ─────────────────────────────────────────────────
    table_content = (
        "<div class='empty-state'><div class='icon'>📭</div><p>ยังไม่มีข้อมูลในระบบค่ะ</p></div>"
        if total == 0 else
        f"<table><thead><tr>"
        "<th>#</th><th>Timestamp</th><th>LINE User ID</th><th>Type</th>"
        "<th>Reference No.</th><th style='text-align:right'>Amount (THB)</th>"
        "<th>Status</th><th>Invoice File</th><th>OCR Preview</th><th>Slip Image</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table>"
    )

    # ── JS (ไม่อยู่ใน f-string ค่ะ) ──────────────────────────────
    js = (
        "function showModal(src){"
        "document.getElementById('modal-img').src=src;"
        "document.getElementById('modal').classList.add('show');}"

        "function closeModal(){"
        "document.getElementById('modal').classList.remove('show');"
        "document.getElementById('modal-img').src='';}"

        "document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});"

        "function refreshPage(){"
        "var btn=document.getElementById('refresh-btn');"
        "btn.textContent='⏳ Loading…';btn.disabled=true;btn.style.opacity='.6';"
        "setTimeout(()=>location.reload(),300);}"

        "function playAlertSound(){"
        "var a=new(window.AudioContext||window.webkitAudioContext)();"
        "[0,0.3,0.6].forEach(function(d){"
        "var o=a.createOscillator(),g=a.createGain();"
        "o.connect(g);g.connect(a.destination);"
        "o.type='sine';o.frequency.value=880;"
        "g.gain.setValueAtTime(0.4,a.currentTime+d);"
        "g.gain.exponentialRampToValueAtTime(0.001,a.currentTime+d+0.25);"
        "o.start(a.currentTime+d);o.stop(a.currentTime+d+0.25);});}"

        # Auto refresh
        + f"var CERR={error},CD=30;"
        "var tel=document.getElementById('auto-refresh-timer');"
        "var tk=setInterval(function(){"
        "CD--;if(tel)tel.textContent='Auto refresh in '+CD+'s';"
        "if(CD<=0){clearInterval(tk);"
        "fetch('/dashboard/error-count').then(function(r){return r.json();})"
        ".then(function(d){if(d.error_count>CERR){playAlertSound();}location.reload();})"
        ".catch(function(){location.reload();});}},1000);"
    )

    # ── Assemble HTML ──────────────────────────────────────────────
    html = (
        "<!DOCTYPE html><html lang='th'><head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>K-Digi Transaction Monitor — KLN Seaport</title>"
        "<link href='https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap' rel='stylesheet'>"
        "<style>" + css + "</style>"
        "</head><body>"

        "<header class='topbar'>"
        "<div class='topbar-left'>"
        "<div class='logo-mark'>KL</div>"
        "<div class='brand-text'>"
        "<div class='company'>KLN Seaport</div>"
        "<div class='system'>K-Digi · Transaction Monitor</div>"
        "</div></div>"
        "<div class='topbar-right'>"
        "<span class='live-dot'>LIVE</span>"
        f"<span class='topbar-time'>{now}</span>"
        "</div></header>"

        "<main>"
        + kpi_html +
        "<hr class='divider'>"

        "<div class='toolbar'>"
        "<div class='toolbar-left'>"
        "<div class='section-label' style='margin:0'>Transaction Log</div>"
        f"<span class='row-count'>{total} rows</span>"
        "</div>"
        "<div style='display:flex;gap:10px;align-items:center'>"
        "<span id='auto-refresh-timer' style='font-size:11px;color:#8a93a2;font-family:IBM Plex Mono,monospace'>Auto refresh in 30s</span>"
        "<a href='/dashboard/export' class='btn-export'>↓ &nbsp;Export CSV</a>"
        "<button class='btn-refresh' onclick='refreshPage()' id='refresh-btn'>↻ &nbsp;Refresh</button>"
        "</div></div>"

        "<div class='table-wrap'>" + table_content + "</div>"
        "</main>"

        "<footer class='footer'>"
        "<div class='footer-left'><strong>KLN Seaport</strong> — K-Digi Receipt Bot &nbsp;|&nbsp; Application Support Division</div>"
        "<div class='footer-right'>Confidential — Internal Use Only</div>"
        "</footer>"

        "<div class='modal' id='modal' onclick='closeModal()'>"
        "<div class='modal-inner' onclick='event.stopPropagation()'>"
        "<div class='modal-label'>Payment Slip — Evidence Record</div>"
        "<img class='modal-img' id='modal-img' src=''>"
        "<button class='btn-close' onclick='closeModal()'>Close &nbsp;✕</button>"
        "</div></div>"

        "<script>" + js + "</script>"
        "</body></html>"
    )
    return html


# ══════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════

def add_dashboard_route(app: FastAPI):

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard():
        logs    = get_logs()
        total   = len(logs)
        success = sum(1 for r in logs if "สำเร็จ" in (r["status"] or ""))
        error   = total - success
        rate    = round(success / total * 100) if total > 0 else 0
        now     = datetime.now().strftime("%d %b %Y, %H:%M")

        # Chart data
        chart_rows    = get_chart_data()
        chart_labels  = json.dumps([r["day"]     for r in chart_rows])
        chart_success = json.dumps([r["success"] for r in chart_rows])
        chart_error   = json.dumps([r["error"]   for r in chart_rows])

        # Table rows
        rows_html = ""
        for r in logs:
            if r["slip_image_b64"]:
                img_html = (
                    f'<img src="data:image/jpeg;base64,{r["slip_image_b64"]}" '
                    f'class="slip-thumb" onclick="showModal(this.src)" title="คลิกเพื่อขยาย">'
                )
            else:
                img_html = '<span class="no-img">— ไม่มีรูป —</span>'

            status_val = r["status"] or ""
            if "สำเร็จ" in status_val:
                badge = '<span class="badge badge-ok">COMPLETED</span>'
            else:
                label = status_val.replace("❌", "").strip() or "ERROR"
                badge = f'<span class="badge badge-err">{label}</span>'

            slip_type = r["slip_type"] or "—"
            ref_str   = r["ref_no"]   or "—"
            amount_str = f'{r["amount"]:,.2f}' if r["amount"] else "—"
            inv_str   = r["invoice_no"] or "—"
            inv_short = inv_str[:20] + "…" if len(inv_str) > 20 else inv_str
            ocr_short = (r["ocr_text"] or "")[:40]

            rows_html += (
                "<tr>"
                f'<td class="td-id">{r["id"]}</td>'
                f'<td>{r["timestamp"] or "—"}</td>'
                f'<td style="font-size:11px;color:#555">{(r["user_id"] or "")[:16]}…</td>'
                f'<td>{slip_type}</td>'
                f'<td class="td-ref">{ref_str}</td>'
                f'<td class="td-amt">{amount_str}</td>'
                f'<td>{badge}</td>'
                f'<td class="td-inv" title="{inv_str}">{inv_short}</td>'
                f'<td class="td-ocr" title="{r["ocr_text"] or ""}">{ocr_short or "—"}</td>'
                f'<td class="td-img">{img_html}</td>'
                "</tr>"
            )

        html = build_html(
            total, success, error, rate, now,
            rows_html, chart_labels, chart_success, chart_error
        )
        return HTMLResponse(content=html)

    # ── Error count API (สำหรับ Auto Refresh) ─────────────────
    @app.get("/dashboard/error-count")
    def error_count():
        logs  = get_logs()
        err   = sum(1 for r in logs if "สำเร็จ" not in (r["status"] or ""))
        return JSONResponse({"error_count": err, "total": len(logs)})

    # ── Export CSV ─────────────────────────────────────────────
    @app.get("/dashboard/export")
    def export_csv():
        logs  = get_logs()
        today = datetime.now().strftime("%Y-%m-%d")
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Timestamp", "User ID", "Slip Type",
                         "Reference No.", "Amount (THB)", "Status",
                         "Invoice No.", "OCR Text"])
        for r in logs:
            writer.writerow([
                r["id"], r["timestamp"] or "", r["user_id"] or "",
                r["slip_type"] or "", r["ref_no"] or "", r["amount"] or "",
                r["status"] or "", r["invoice_no"] or "",
                (r["ocr_text"] or "")[:200]
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f"attachment; filename=kdigi_logs_{today}.csv"}
        )

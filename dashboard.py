import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import io
import csv
import json

DB_PATH = "kdigi_logs.db"


# ══════════════════════════════════════════════════════════════
# Database helpers
# ══════════════════════════════════════════════════════════════

def get_logs(date_from: str = None, date_to: str = None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if date_from and date_to:
        cursor.execute(
            "SELECT * FROM logs WHERE DATE(timestamp) BETWEEN ? AND ? ORDER BY id DESC",
            (date_from, date_to)
        )
    elif date_from:
        cursor.execute(
            "SELECT * FROM logs WHERE DATE(timestamp) >= ? ORDER BY id DESC",
            (date_from,)
        )
    elif date_to:
        cursor.execute(
            "SELECT * FROM logs WHERE DATE(timestamp) <= ? ORDER BY id DESC",
            (date_to,)
        )
    else:
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

def build_html(total, success, error, rate, now, rows_html, chart_labels, chart_success, chart_error, date_from='', date_to='', is_filtered=False):
    bar_w = rate

    # ── CSS ───────────────────────────────────────────────────────
    css = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg:        #f4f4f4;
  --white:     #ffffff;
  --dark:      #1a1a1a;
  --gray:      #3a3a3a;
  --gray-mid:  #555555;
  --gray-lt:   #e0e0e0;
  --border:    #cccccc;
  --orange:    #f26522;
  --orange-dk: #d4541a;
  --text:      #222222;
  --muted:     #777777;
  --green:     #2e7d32;
  --green-bg:  #e8f5e9;
  --red:       #c62828;
  --red-bg:    #ffebee;
  --radius:    3px;
  --shadow:    0 1px 3px rgba(0,0,0,.15);
}
html { font-size: 13px; }
body { font-family: 'Sarabun', 'Tahoma', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

/* ── Top Navigation Bar ── */
.topbar {
  background: var(--dark);
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 52px;
  border-bottom: 1px solid #333;
}
.topbar-brand {
  font-size: 18px;
  font-weight: 700;
  color: var(--orange);
  letter-spacing: .5px;
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 20px;
  font-size: 12px;
  color: #aaa;
}
.live-badge {
  background: #2e7d32;
  color: white;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 2px;
  letter-spacing: .5px;
}

/* ── Page Header ── */
.page-header {
  background: var(--white);
  border-bottom: 3px solid var(--orange);
  padding: 12px 24px;
}
.page-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--orange);
}

/* ── Main content ── */
main { padding: 20px 24px 60px; }

/* ── KPI Cards ── */
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.kpi-card {
  background: var(--white);
  border: 1px solid var(--border);
  border-left: 4px solid var(--orange);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 16px 20px;
}
.kpi-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .8px; color: var(--muted); margin-bottom: 6px; }
.kpi-value { font-size: 32px; font-weight: 700; color: var(--text); line-height: 1; margin-bottom: 4px; }
.kpi-sub { font-size: 11px; color: var(--muted); }
.progress-wrap { margin-top: 10px; background: var(--gray-lt); border-radius: 2px; height: 4px; }
.progress-bar { height: 100%; border-radius: 2px; background: var(--orange); }

/* ── Toolbar ── */
.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.toolbar-left { display: flex; align-items: center; gap: 10px; }
.section-title { font-size: 13px; font-weight: 700; color: var(--text); }
.row-count { font-size: 11px; color: var(--muted); background: var(--gray-lt); padding: 2px 8px; border-radius: 2px; }
.btn-refresh {
  background: var(--gray);
  color: white;
  border: none;
  padding: 6px 14px;
  border-radius: var(--radius);
  font-size: 12px;
  cursor: pointer;
  font-family: 'Sarabun', 'Tahoma', sans-serif;
}
.btn-refresh:hover { background: #444; }
.btn-export {
  background: var(--orange);
  color: white;
  border: none;
  padding: 6px 14px;
  border-radius: var(--radius);
  font-size: 12px;
  cursor: pointer;
  text-decoration: none;
  font-family: 'Sarabun', 'Tahoma', sans-serif;
  font-weight: 600;
}
.btn-export:hover { background: var(--orange-dk); }
.auto-timer { font-size: 11px; color: var(--muted); }

/* ── Table ── */
.table-wrap {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  overflow-x: auto;
}
table { width: 100%; border-collapse: collapse; font-size: 12px; }
thead { background: var(--gray); }
th {
  padding: 9px 12px;
  text-align: left;
  font-size: 11px;
  font-weight: 700;
  color: #ffffff;
  white-space: nowrap;
  border-right: 1px solid #555;
}
th:last-child { border-right: none; }
td { padding: 8px 12px; border-bottom: 1px solid #eeeeee; vertical-align: middle; color: var(--text); }
tr:last-child td { border-bottom: none; }
tr:nth-child(even) td { background: #fafafa; }
tr:hover td { background: #fff3ec; }

/* ── Badges ── */
.badge { display: inline-block; padding: 2px 8px; border-radius: 2px; font-size: 10px; font-weight: 700; letter-spacing: .4px; }
.badge-ok  { background: var(--green-bg); color: var(--green); border: 1px solid #a5d6a7; }
.badge-err { background: var(--red-bg);   color: var(--red);   border: 1px solid #ef9a9a; }

/* ── Table cell styles ── */
.td-id  { color: var(--muted); width: 40px; font-size: 11px; }
.td-ref { font-family: 'Courier New', monospace; font-size: 11px; }
.td-amt { font-family: 'Courier New', monospace; font-size: 11px; text-align: right; }
.td-inv { font-size: 11px; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-ocr { font-size: 11px; color: var(--muted); max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-img { width: 68px; }
.slip-thumb { width: 52px; height: 38px; object-fit: cover; border-radius: 2px; cursor: zoom-in; border: 1px solid var(--border); }
.no-img { font-size: 10px; color: var(--muted); }

/* ── Empty state ── */
.empty-state { text-align: center; padding: 50px 20px; color: var(--muted); }
.empty-state .icon { font-size: 36px; margin-bottom: 10px; }

/* ── Modal ── */
.modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.7); z-index: 1000; align-items: center; justify-content: center; }
.modal.show { display: flex; }
.modal-inner { background: white; border-radius: 4px; padding: 20px; max-width: 500px; width: 90%; }
.modal-label { font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--muted); margin-bottom: 10px; }
.modal-img { width: 100%; border-radius: 3px; margin-bottom: 14px; }
.btn-close { width: 100%; padding: 9px; background: var(--gray); color: white; border: none; border-radius: var(--radius); font-size: 13px; cursor: pointer; }

/* ── Footer ── */
.footer {
  background: var(--dark);
  color: #888;
  font-size: 11px;
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  margin-top: 32px;
}
.divider { border: none; border-top: 1px solid var(--border); margin: 20px 0; }

/* ── Date Filter Bar ── */
.filter-bar {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 20px;
  margin-bottom: 16px;
  display: flex;
  align-items: flex-end;
  gap: 16px;
  box-shadow: var(--shadow);
  flex-wrap: wrap;
}
.filter-group { display: flex; flex-direction: column; gap: 4px; }
.filter-label { font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
.filter-input {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 5px 10px;
  font-size: 12px;
  font-family: 'Sarabun', 'Tahoma', sans-serif;
  color: var(--text);
  background: white;
  height: 30px;
  min-width: 140px;
}
.filter-input:focus { outline: none; border-color: var(--orange); }
.btn-search {
  background: var(--orange);
  color: white;
  border: none;
  padding: 6px 18px;
  border-radius: var(--radius);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  height: 30px;
  font-family: 'Sarabun', 'Tahoma', sans-serif;
}
.btn-search:hover { background: var(--orange-dk); }
.btn-reset {
  background: var(--gray);
  color: white;
  border: none;
  padding: 6px 14px;
  border-radius: var(--radius);
  font-size: 12px;
  cursor: pointer;
  height: 30px;
  text-decoration: none;
  font-family: 'Sarabun', 'Tahoma', sans-serif;
}
.btn-reset:hover { background: #444; }
.filter-result { font-size: 11px; color: var(--orange); font-weight: 600; align-self: center; }
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

        "function applyFilter(){"
        "var df=document.getElementById('df').value;"
        "var dt=document.getElementById('dt').value;"
        "var url='/dashboard?';"
        "if(df)url+='date_from='+df+'&';"
        "if(dt)url+='date_to='+dt;"
        "window.location.href=url;}"

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
        "<link href='https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&display=swap' rel='stylesheet'>"
        "<style>" + css + "</style>"
        "</head><body>"

        "<header class='topbar'>"
        "<div class='topbar-brand'>KLN Seaport Ltd.</div>"
        "<div class='topbar-right'>"
        "<span class='live-badge'>LIVE</span>"
        f"<span>{now}</span>"
        "<span>K-Digi · Application Support</span>"
        "</div></header>"

        "<div class='page-header'>"
        "<div class='page-title'>K-Digi Transaction Monitor</div>"
        "</div>"

        "<main>"
        "<div class='filter-bar'>"
        "<div class='filter-group'><label class='filter-label'>Start Date From</label>"
        f"<input class='filter-input' type='date' id='df' value='{date_from}'></div>"
        "<div class='filter-group'><label class='filter-label'>Start Date To</label>"
        f"<input class='filter-input' type='date' id='dt' value='{date_to}'></div>"
        "<button class='btn-search' onclick='applyFilter()'>Search</button>"
        "<a class='btn-reset' href='/dashboard'>Reset</a>"
        + ("<span class='filter-result'>" + f"Filtered: {date_from} — {date_to}" + "</span>" if is_filtered else "") +
        "</div>"
        + kpi_html +
        "<hr class='divider'>"

        "<div class='toolbar'>"
        "<div class='toolbar-left'>"
        "<div class='section-title'>Transaction Log</div>"
        f"<span class='row-count'>{total} rows</span>"
        "</div>"
        "<div style='display:flex;gap:8px;align-items:center'>"
        "<span class='auto-timer' id='auto-refresh-timer'>Auto refresh in 30s</span>"
        "<a href='/dashboard/export' class='btn-export'>Export CSV</a>"
        "<button class='btn-refresh' onclick='refreshPage()' id='refresh-btn'>↻ Refresh</button>"
        "</div></div>"

        "<div class='table-wrap'>" + table_content + "</div>"
        "</main>"

        "<footer class='footer'>"
        "<div><strong style='color:#f26522'>KLN Seaport Ltd.</strong> — K-Digi Receipt Bot | Application Support Division</div>"
        "<div>Confidential — Internal Use Only</div>"
        "</footer>"

        "<div class='modal' id='modal' onclick='closeModal()'>"
        "<div class='modal-inner' onclick='event.stopPropagation()'>"
        "<div class='modal-label'>Payment Slip — Evidence Record</div>"
        "<img class='modal-img' id='modal-img' src=''>"
        "<button class='btn-close' onclick='closeModal()'>Close ✕</button>"
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
    def dashboard(request: Request):
        date_from = request.query_params.get("date_from", "")
        date_to   = request.query_params.get("date_to", "")
        is_filtered = bool(date_from or date_to)
        logs    = get_logs(date_from or None, date_to or None)
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
            rows_html, chart_labels, chart_success, chart_error,
            date_from, date_to, is_filtered
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
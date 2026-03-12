import sqlite3
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

DB_PATH = "kdigi_logs.db"

# ดึง Log ทั้งหมดจาก SQLite
def get_logs():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM logs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_dashboard_route(app: FastAPI):
    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard():
        logs = get_logs()

        # คำนวณสถิติ
        total = len(logs)
        success = sum(1 for r in logs if "สำเร็จ" in (r["status"] or ""))
        error = total - success

        # สร้าง HTML แถวตาราง
        rows_html = ""
        for r in logs:
            # แสดงรูปสลิปจาก Base64 ถ้ามี
            if r["slip_image_b64"]:
                img_html = (
                    f'<img src="data:image/jpeg;base64,{r["slip_image_b64"]}" '
                    f'style="width:70px;height:70px;object-fit:cover;border-radius:8px;'
                    f'cursor:pointer;border:1px solid #e5e7eb" '
                    f'onclick="showModal(this.src)" title="คลิกดูรูปใหญ่">'
                )
            else:
                img_html = '<span style="color:#9ca3af;font-size:12px">ไม่มีรูป</span>'

            # Badge สถานะ
            status_val = r["status"] or ""
            if "สำเร็จ" in status_val:
                status_html = f'<span style="background:#dcfce7;color:#16a34a;padding:3px 10px;border-radius:99px;font-size:12px;font-weight:600">✅ สำเร็จ</span>'
            else:
                status_html = f'<span style="background:#fee2e2;color:#dc2626;padding:3px 10px;border-radius:99px;font-size:12px;font-weight:600">❌ {status_val.replace("❌","").strip()}</span>'

            # OCR Text ย่อๆ
            ocr_short = (r["ocr_text"] or "-")[:60] + ("..." if len(r["ocr_text"] or "") > 60 else "")

            rows_html += f"""
            <tr>
                <td style="color:#6b7280;font-size:13px">{r['id']}</td>
                <td style="font-size:13px">{r['timestamp'] or '-'}</td>
                <td style="font-size:11px;color:#6b7280">{(r['user_id'] or '')[:20]}...</td>
                <td><span style="background:#f3f4f6;padding:2px 8px;border-radius:6px;font-size:12px">{r['slip_type'] or '-'}</span></td>
                <td style="font-family:monospace;font-size:13px;color:#f26522">{r['ref_no'] or '-'}</td>
                <td style="font-size:13px">{f"{r['amount']:,.2f}" if r['amount'] else '-'}</td>
                <td>{status_html}</td>
                <td style="font-size:11px;color:#374151;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{r['invoice_no'] or ''}">{r['invoice_no'] or '-'}</td>
                <td style="font-size:11px;color:#6b7280;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{r['ocr_text'] or ''}">{ocr_short}</td>
                <td>{img_html}</td>
            </tr>
            """

        # สร้าง success rate
        rate = round((success / total * 100)) if total > 0 else 0

        html = f"""<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KLN Seaport — Admin Dashboard</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #f5f5f5; color: #1a1a2e; }}

        /* Header */
        .header {{
            background: #1a1a2e;
            color: white;
            padding: 20px 32px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 4px solid #f26522;
        }}
        .header h1 {{ font-size: 20px; font-weight: 700; }}
        .header h1 span {{ color: #f26522; }}
        .header p {{ font-size: 13px; color: #9ca3af; margin-top: 2px; }}
        .header-badge {{
            background: #f26522;
            color: white;
            padding: 6px 14px;
            border-radius: 99px;
            font-size: 13px;
            font-weight: 600;
        }}

        /* Stats Cards */
        .stats {{ display: flex; gap: 16px; padding: 24px 32px 0; }}
        .card {{
            background: white;
            border-radius: 12px;
            padding: 20px 24px;
            flex: 1;
            box-shadow: 0 1px 3px rgba(0,0,0,0.07);
            border: 1px solid #e5e7eb;
            border-top: 4px solid #e5e7eb;
        }}
        .card .label {{ font-size: 13px; color: #6b7280; font-weight: 500; }}
        .card .num {{ font-size: 40px; font-weight: 700; margin-top: 4px; line-height: 1; }}
        .card .sub {{ font-size: 12px; color: #9ca3af; margin-top: 6px; }}
        .card.total {{ border-top-color: #f26522; }}
        .card.total .num {{ color: #f26522; }}
        .card.success {{ border-top-color: #16a34a; }}
        .card.success .num {{ color: #16a34a; }}
        .card.error {{ border-top-color: #dc2626; }}
        .card.error .num {{ color: #dc2626; }}
        .card.rate {{ border-top-color: #1a1a2e; }}
        .card.rate .num {{ color: #1a1a2e; }}

        /* Table */
        .table-section {{ margin: 24px 32px 32px; }}
        .table-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }}
        .table-header h2 {{ font-size: 16px; font-weight: 600; color: #1a1a2e; }}
        .table-wrap {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.07);
            border: 1px solid #e5e7eb;
            overflow: auto;
        }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; min-width: 900px; }}
        thead tr {{ background: #1a1a2e; }}
        th {{
            padding: 12px 14px;
            text-align: left;
            color: #f26522;
            font-weight: 600;
            font-size: 12px;
            white-space: nowrap;
        }}
        td {{ padding: 12px 14px; border-bottom: 1px solid #f3f4f6; vertical-align: middle; }}
        tr:last-child td {{ border-bottom: none; }}
        tbody tr:hover td {{ background: #fff8f5; }}

        /* Modal ดูรูปใหญ่ */
        .modal {{
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(26,26,46,0.92);
            z-index: 999;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            gap: 16px;
        }}
        .modal.show {{ display: flex; }}
        .modal img {{
            max-width: 88vw;
            max-height: 82vh;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
            border: 3px solid #f26522;
        }}
        .modal-close {{
            color: white;
            font-size: 14px;
            cursor: pointer;
            background: #f26522;
            padding: 8px 20px;
            border-radius: 99px;
            border: none;
            font-weight: 600;
        }}
        .empty {{ text-align: center; padding: 48px; color: #9ca3af; }}
    </style>
</head>
<body>

    <!-- Header -->
    <div class="header">
        <div>
            <h1>🧾 <span style="color:#f26522">KLN</span> Seaport — Admin Dashboard</h1>
            <p>ระบบติดตาม Transaction และรูปสลิปสำหรับทีม Support ค่ะ</p>
        </div>
        <div class="header-badge">● Live</div>
    </div>

    <!-- Stats -->
    <div class="stats">
        <div class="card total">
            <div class="label">Transaction ทั้งหมด</div>
            <div class="num">{total}</div>
            <div class="sub">ทุก Transaction ที่เข้ามาค่ะ</div>
        </div>
        <div class="card success">
            <div class="label">✅ สำเร็จ</div>
            <div class="num">{success}</div>
            <div class="sub">ได้รับใบเสร็จแล้วค่ะ</div>
        </div>
        <div class="card error">
            <div class="label">❌ Error</div>
            <div class="num">{error}</div>
            <div class="sub">ต้องตรวจสอบค่ะ</div>
        </div>
        <div class="card rate">
            <div class="label">อัตราสำเร็จ</div>
            <div class="num">{rate}%</div>
            <div class="sub">Success Rate</div>
        </div>
    </div>

    <!-- Table -->
    <div class="table-section">
        <div class="table-header">
            <h2>📋 Log ทั้งหมด ({total} รายการ)</h2>
            <div style="display:flex;align-items:center;gap:12px">
                <span style="font-size:12px;color:#9ca3af">เรียงจากล่าสุดค่ะ • กดรูปเพื่อดูใหญ่</span>
                <button onclick="refreshPage()" id="refresh-btn"
                    style="display:flex;align-items:center;gap:6px;
                           background:#f26522;color:white;border:none;
                           padding:8px 16px;border-radius:8px;font-size:13px;
                           font-weight:600;cursor:pointer;">
                    🔄 Refresh
                </button>
            </div>
        </div>
        <div class="table-wrap">
            {"<div class='empty'>ยังไม่มีข้อมูลค่ะ</div>" if total == 0 else f"""
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>เวลา</th>
                        <th>User ID</th>
                        <th>ประเภท</th>
                        <th>Ref No.</th>
                        <th>ยอดเงิน (บาท)</th>
                        <th>สถานะ</th>
                        <th>Invoice</th>
                        <th>OCR Text</th>
                        <th>รูปสลิป</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
            """}
        </div>
    </div>

    <!-- Modal ดูรูปใหญ่ -->
    <div class="modal" id="modal" onclick="closeModal()">
        <img id="modal-img" src="" onclick="event.stopPropagation()">
        <button class="modal-close" onclick="closeModal()">✕ ปิด</button>
    </div>

    <script>
        function showModal(src) {{
            document.getElementById('modal-img').src = src;
            document.getElementById('modal').classList.add('show');
        }}
        function closeModal() {{
            document.getElementById('modal').classList.remove('show');
            document.getElementById('modal-img').src = '';
        }}
        // กด ESC ปิด Modal
        document.addEventListener('keydown', e => {{
            if (e.key === 'Escape') closeModal();
        }});
        // Refresh หน้าพร้อม Animation
        function refreshPage() {{
            const btn = document.getElementById('refresh-btn');
            btn.innerHTML = '⏳ กำลังโหลด...';
            btn.style.opacity = '0.7';
            btn.disabled = true;
            setTimeout(() => location.reload(), 300);
        }}
    </script>

</body>
</html>"""
        return HTMLResponse(content=html)
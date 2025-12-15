import streamlit as st
import pdfplumber
import re
from jinja2 import Environment, BaseLoader
import os
import shutil
import pdfkit
from pypdf import PdfWriter
import tempfile
from datetime import datetime
import base64

# --- Import your custom extractor ---
try:
    from generate_summary import extract_comprehensive_data
except ImportError:
    st.error("CRITICAL ERROR: Could not find 'generate_summary.py'. Make sure it is uploaded.")
    st.stop()

# ==============================
#   BASIC APP CONFIGURATION
# ==============================
st.set_page_config(page_title="Meesha Diagnostics AI", page_icon="🩺", layout="wide")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_DB_FILENAME = "test_and_values.csv"

# ==============================
#   PROFESSIONAL "SAFE-PRINT" TEMPLATE
# ==============================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Meesha Health Analysis</title>
    <style>
        /* --- GLOBAL SETTINGS --- */
        body { 
            font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
            margin: 0; padding: 0; 
            background: #fff; color: #1e293b;
            font-size: 10pt; /* Standard Print Size */
            line-height: 1.3;
            -webkit-print-color-adjust: exact; 
        }
        
        /* The container determines width. We leave margins to the PDF engine. */
        .container {
            width: 100%;
            max-width: 100%;
        }

        /* --- HEADER --- */
        .header {
            border-bottom: 2px solid #0f766e;
            padding-bottom: 10px; margin-bottom: 20px;
            display: table; width: 100%;
        }
        .header-left { display: table-cell; vertical-align: middle; }
        .header-right { display: table-cell; vertical-align: middle; text-align: right; }
        
        .brand-title { color: #0f766e; font-size: 20px; font-weight: 800; text-transform: uppercase; }
        .brand-sub { font-size: 10px; color: #64748b; }
        .meta-text { font-size: 9px; color: #334155; }

        /* --- PATIENT GRID --- */
        .patient-box {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-left: 4px solid #0f766e;
            padding: 10px;
            margin-bottom: 20px;
            display: table; width: 100%;
        }
        .p-col { display: table-cell; width: 25%; vertical-align: top; padding-right: 10px; }
        .p-lbl { font-size: 8px; text-transform: uppercase; color: #64748b; font-weight: 700; display: block; }
        .p-val { font-size: 11px; font-weight: 600; color: #0f172a; display: block; }

        /* --- STATS ROW --- */
        .stats-table {
            width: 100%; border-collapse: separate; border-spacing: 10px 0; margin-bottom: 20px;
            table-layout: fixed;
        }
        .stat-cell {
            border: 1px solid #e2e8f0; border-radius: 6px;
            padding: 10px; text-align: center;
            vertical-align: middle;
        }
        .stat-val { font-size: 18px; font-weight: 800; display: block; }
        .stat-lbl { font-size: 9px; text-transform: uppercase; color: #64748b; font-weight: 700; margin-top: 2px; display: block; }
        
        .bg-score { background: #0f172a; color: white; border: none; }
        .bg-score .stat-val { color: #2dd4bf; }
        .risk-tag { background: #2dd4bf; color: #0f172a; font-size: 8px; padding: 2px 6px; border-radius: 4px; font-weight: 700; display: inline-block; margin-top: 4px; }

        /* --- SUMMARY --- */
        .summary-box {
            background: #f0fdfa; border: 1px solid #ccfbf1; border-radius: 6px;
            padding: 15px; margin-bottom: 20px;
        }
        .sec-title { 
            font-size: 12px; font-weight: 800; color: #0f766e; 
            text-transform: uppercase; margin-bottom: 8px; border-bottom: 1px solid #d1fae5; padding-bottom: 4px;
        }
        .summary-text { font-size: 10pt; color: #334155; text-align: justify; line-height: 1.5; }

        /* --- MAIN TABLE --- */
        table.main-table { width: 100%; border-collapse: collapse; font-size: 9pt; }
        table.main-table th { 
            background: #0f766e; color: white; padding: 8px 10px; 
            text-align: left; font-weight: 700; text-transform: uppercase; font-size: 8pt;
        }
        table.main-table td { 
            padding: 8px 10px; border-bottom: 1px solid #e2e8f0; 
            vertical-align: middle; color: #334155;
        }
        table.main-table tr:nth-child(even) { background-color: #f8fafc; }
        
        .res-val { font-weight: 700; color: #0f172a; }
        .res-range { font-size: 7pt; color: #94a3b8; display: block; margin-top: 2px; }

        /* --- PILLS --- */
        .badge { 
            padding: 4px 8px; border-radius: 4px; 
            font-size: 8px; font-weight: 700; text-transform: uppercase; 
            display: inline-block; min-width: 60px; text-align: center;
        }
        .crit { background: #fee2e2; color: #991b1b; }
        .warn { background: #fffbeb; color: #b45309; }
        .norm { background: #dcfce7; color: #15803d; }

        /* --- FOOTER --- */
        .footer {
            margin-top: 30px; border-top: 1px solid #cbd5e1; padding-top: 10px;
            display: table; width: 100%;
        }
        .sig-block { text-align: right; }
        .sig-name { font-family: 'Times New Roman', serif; font-weight: bold; font-size: 14px; }
        .sig-role { font-size: 8px; text-transform: uppercase; color: #0f766e; font-weight: 700; }
    </style>
</head>
<body>
<div class="container">

    <div class="header">
        <div class="header-left">
            {% if logo_b64 %}
                <img src="data:image/jpeg;base64,{{ logo_b64 }}" style="height:50px; margin-right:15px; vertical-align:middle;">
            {% endif %}
            <div style="display:inline-block; vertical-align:middle;">
                <div class="brand-title">Meesha Diagnostics</div>
                <div class="brand-sub">AI Clinical Analysis Report</div>
            </div>
        </div>
        <div class="header-right">
            <div class="meta-text">
                <strong>DATE:</strong> {{ report_date }}<br>
                <strong>ID:</strong> {{ treatment_id }}
            </div>
        </div>
    </div>

    <div class="patient-box">
        <div class="p-col">
            <span class="p-lbl">Patient Name</span>
            <span class="p-val">{{ patient_name }}</span>
        </div>
        <div class="p-col">
            <span class="p-lbl">Age / Gender</span>
            <span class="p-val">{{ patient_age_gender }}</span>
        </div>
        <div class="p-col">
            <span class="p-lbl">Referred By</span>
            <span class="p-val">{{ doctor_name }}</span>
        </div>
        <div class="p-col" style="text-align:right; padding-right:0;">
            <span class="p-lbl">Lab ID</span>
            <span class="p-val">{{ treatment_id }}</span>
        </div>
    </div>

    <table class="stats-table">
        <tr>
            <td class="stat-cell bg-score" width="25%">
                <span class="stat-val">{{ overall_score }}/10</span>
                <span class="stat-lbl" style="color:#94a3b8;">Health Score</span>
                <span class="risk-tag">{{ risk_label }}</span>
            </td>
            <td class="stat-cell" width="25%">
                <span class="stat-val" style="color:#15803d;">{{ count_normal }}</span>
                <span class="stat-lbl">Normal</span>
            </td>
            <td class="stat-cell" width="25%">
                <span class="stat-val" style="color:#b45309;">{{ count_warn }}</span>
                <span class="stat-lbl">Warning</span>
            </td>
            <td class="stat-cell" width="25%">
                <span class="stat-val" style="color:#991b1b;">{{ count_crit }}</span>
                <span class="stat-lbl">Critical</span>
            </td>
        </tr>
    </table>

    <div class="summary-box">
        <div class="sec-title">🤖 AI Executive Summary</div>
        <div class="summary-text">{{ narrative }}</div>
    </div>

    <div style="margin-bottom: 20px;">
        <div class="sec-title">📊 Biomarker Analysis</div>
        <table class="main-table">
            <thead>
                <tr>
                    <th width="40%">Test Name</th>
                    <th width="30%">Result / Range</th>
                    <th width="30%">Analysis</th>
                </tr>
            </thead>
            <tbody>
                {% for test in full_results %}
                <tr>
                    <td><b>{{ test.name }}</b></td>
                    <td>
                        <span class="res-val">{{ test.value }}</span>
                        <span class="res-range">Ref: {{ test.range }}</span>
                    </td>
                    <td>
                        {% if 'Crit' in test.status %}
                            <span class="badge crit">CRITICAL</span>
                        {% elif 'Normal' in test.status %}
                            <span class="badge norm">NORMAL</span>
                        {% else %}
                            <span class="badge warn">ABNORMAL</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <div class="footer">
        <div style="display:table-cell; width:60%; vertical-align:bottom;">
            <div style="font-size:9px; color:#64748b;">
                <strong>📍 Mahalaxmi Branch:</strong> 1st Floor, La View, B.J. Marg, Jacob Circle<br>
                <strong>📍 BKC Centre:</strong> 310, Trade Center, BKC, Mumbai
            </div>
        </div>
        <div style="display:table-cell; width:40%; vertical-align:bottom; text-align:right;">
            {% if footer_qr %}
                <img src="data:image/png;base64,{{ footer_qr }}" style="height:45px; margin-bottom:5px;">
            {% endif %}
            <div class="sig-name">Dr. Sudha TR</div>
            <div class="sig-role">Consultant Pathologist</div>
        </div>
    </div>

</div>
</body>
</html>
"""

# ==============================
#   SIMPLE HELPER: IMAGE -> BASE64
# ==============================
def get_base64_image(image_path):
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    return None

# ==============================
#   WKHTMLTOPDF CONFIG
# ==============================
def get_wkhtmltopdf_config():
    path = shutil.which("wkhtmltopdf")
    if path: return pdfkit.configuration(wkhtmltopdf=path)
    
    common_paths = [
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe"
    ]
    for p in common_paths:
        if os.path.exists(p): return pdfkit.configuration(wkhtmltopdf=p)
    return None

# ==============================
#   MAIN APP
# ==============================
def meesha_brand_header():
    logo_path = os.path.join(SCRIPT_DIR, "meesha_logo.jpeg")
    if not os.path.exists(logo_path): logo_path = r"C:\Users\sunil\Desktop\MeeshaReport\meesha_logo.jpeg"
    logo_b64 = get_base64_image(logo_path)
    
    img_html = ""
    if logo_b64:
        img_html = f"<img src='data:image/jpeg;base64,{logo_b64}' height='50' style='border-radius:8px; margin-right:15px;'>"

    st.markdown(f"""
    <div style="background:linear-gradient(90deg,#0f172a,#0f766e);padding:15px;border-radius:10px;display:flex;align-items:center;color:white;margin-bottom:20px;">
      {img_html}
      <div>
        <div style="font-size:22px;font-weight:bold;">Meesha Diagnostics AI</div>
        <div style="font-size:12px;opacity:0.9;">Smart Clinical Analysis</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

def main():
    meesha_brand_header()
    
    # Load assets
    logo_path = os.path.join(SCRIPT_DIR, "meesha_logo.jpeg")
    if not os.path.exists(logo_path): logo_path = r"C:\Users\sunil\Desktop\MeeshaReport\meesha_logo.jpeg"
    logo_b64 = get_base64_image(logo_path)

    qr_path = os.path.join(SCRIPT_DIR, "meesha_qr.png")
    if not os.path.exists(qr_path): qr_path = r"C:\Users\sunil\Desktop\meesha_qr.png"
    footer_qr_b64 = get_base64_image(qr_path)

    st.subheader("Upload Report")
    uploaded_file = st.file_uploader("Choose PDF", type="pdf")

    if uploaded_file is not None:
        config = get_wkhtmltopdf_config()
        if not config:
            st.error("❌ 'wkhtmltopdf' not found.")
            st.stop()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
            tmp_pdf.write(uploaded_file.getvalue())
            temp_pdf_path = tmp_pdf.name

        st.info("Analysing...")

        try:
            db_path = os.path.join(SCRIPT_DIR, CSV_DB_FILENAME)
            info, full_results = extract_comprehensive_data(temp_pdf_path, db_path)

            total = len(full_results)
            count_normal = sum(1 for r in full_results if "Normal" in r["status"])
            count_crit = sum(1 for r in full_results if "Crit" in r["status"])
            count_warn = total - count_normal - count_crit
            
            score = max(1, 10 - (count_crit * 2) - count_warn)
            risk_label = "Low Risk" if score >= 8 else "Moderate" if score >= 5 else "High Risk"

            narrative = "All systems look stable."
            if count_crit > 0: 
                crit_names = ", ".join([t['name'] for t in full_results if "Crit" in t['status']][:3])
                narrative = f"<b>Critical Alert:</b> Tests such as {crit_names} are significantly outside range."
            elif count_warn > 0: 
                narrative = f"<b>Note:</b> {count_warn} tests show mild deviations."

            env = Environment(loader=BaseLoader())
            template = env.from_string(HTML_TEMPLATE)
            html_out = template.render(
                patient_name=info["patient_name"],
                patient_age_gender=info["age_gender"],
                treatment_id=info["treatment_id"],
                doctor_name=info["doctor"],
                report_date=info.get("date", datetime.now().strftime("%d-%m-%Y")),
                narrative=narrative,
                full_results=full_results,
                logo_b64=logo_b64,
                footer_qr=footer_qr_b64,
                overall_score=score,
                risk_label=risk_label,
                count_normal=count_normal,
                count_warn=count_warn,
                count_crit=count_crit
            )

            # --- PDF OPTIONS (FIXED) ---
            summary_pdf_path = temp_pdf_path.replace(".pdf", "_summary.pdf")
            options = {
                "page-size": "A4",
                "margin-top": "15mm",    # Standard Margins
                "margin-right": "15mm",
                "margin-bottom": "15mm",
                "margin-left": "15mm",
                "encoding": "UTF-8",
                "no-outline": None,
                "zoom": "1.0",           # RESET ZOOM
                "disable-smart-shrinking": None
            }
            
            pdfkit.from_string(html_out, summary_pdf_path, configuration=config, options=options)

            final_output_path = temp_pdf_path.replace(".pdf", "_final.pdf")
            merger = PdfWriter()
            merger.append(summary_pdf_path)
            merger.append(temp_pdf_path)
            merger.write(final_output_path)
            merger.close()

            with open(final_output_path, "rb") as f:
                st.download_button("📥 Download Report", f.read(), f"Analysis_{info['patient_name']}.pdf", "application/pdf")

        except Exception as e:
            st.error(f"Error: {e}")
        finally:
            try:
                if os.path.exists(temp_pdf_path): os.remove(temp_pdf_path)
                if 'summary_pdf_path' in locals() and os.path.exists(summary_pdf_path): os.remove(summary_pdf_path)
                if 'final_output_path' in locals() and os.path.exists(final_output_path): os.remove(final_output_path)
            except: pass

if __name__ == "__main__":
    main()
from generate_summary import extract_comprehensive_data
import streamlit as st
import pdfplumber
import re
from jinja2 import Environment, BaseLoader
import os
import pdfkit
from pypdf import PdfWriter, PdfReader
import tempfile
from datetime import datetime
import pandas as pd
import base64

# ==============================
#  BASIC APP CONFIGURATION
# ==============================
st.set_page_config(page_title="Meesha Diagnostics AI", page_icon="🩺", layout="wide")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_DB_FILENAME = "test_and_values.csv"

# ==============================
#  SIMPLE HELPER: IMAGE → BASE64
# ==============================
def get_base64_image(image_path):
    """Convert local image file into base64 text for HTML embedding."""
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    return ""

# ==============================
#  TOP BRAND HEADER FOR LANDING
# ==============================
def meesha_brand_header():
    logo_path = r"C:\Users\sunil\Desktop\MeeshaReport\meesha_logo.jpeg"
    logo_b64 = get_base64_image(logo_path)

    st.markdown(
        f"""
        <div style="background:linear-gradient(90deg,#0f172a,#0f766e);padding:20px 28px 16px 24px;
                    border-radius:0 0 18px 18px;display:flex;align-items:center;justify-content:space-between;
                    color:#e5e7eb; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
          <div style="display:flex;align-items:center;gap:16px;">
            {"<img src='data:image/jpeg;base64," + logo_b64 + "' height='60' style='border-radius:12px;'>" if logo_b64 else ""}
            <div>
              <div style="font-size:24px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;">
                Meesha Diagnostics AI
              </div>
              <div style="font-size:13px;opacity:0.85;">
                Smart clinical summary from your laboratory reports
              </div>
            </div>
          </div>
          <div style="font-size:11px;text-align:right;opacity:0.85;">
            For doctor support only<br/>
            Not a substitute for medical advice
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ==============================
#  PREMIUM HTML TEMPLATE (DESIGN UPGRADE)
# ==============================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Meesha Health Analysis</title>
    <style>
        /* Base Reset */
        body { 
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            margin: 0; padding: 0; 
            background: #ffffff; 
            color: #334155; 
        }
        
        .page {
            width: 210mm; min-height: 297mm; 
            padding: 12mm 15mm; 
            position: relative; 
            box-sizing: border-box;
        }

        /* --- HEADER --- */
        .header {
            display: flex; justify-content: space-between; align-items: center;
            padding-bottom: 15px;
            border-bottom: 3px solid #0f766e; /* Brand Teal */
            margin-bottom: 20px;
        }
        .logo-img { height: 60px; width: auto; object-fit: contain; }
        .header-title { text-align: right; }
        .report-name { font-size: 18px; font-weight: 800; color: #0f766e; text-transform: uppercase; letter-spacing: 1px; }
        .report-sub { font-size: 10px; color: #64748b; margin-top: 2px; }
        .report-date { font-size: 10px; font-weight: 600; color: #334155; margin-top: 4px; }

        /* --- PATIENT CARD --- */
        .patient-card {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 25px;
            display: flex;
            justify-content: space-between;
        }
        .p-group { display: flex; flex-direction: column; width: 24%; }
        .p-label { font-size: 8px; color: #64748b; text-transform: uppercase; font-weight: 700; margin-bottom: 2px; }
        .p-val { font-size: 11px; color: #0f172a; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; overflow: hidden; }

        /* --- LAYOUT GRID --- */
        .grid-container {
            display: grid; 
            grid-template-columns: 65% 33%; 
            gap: 2%;
        }

        /* --- LEFT COLUMN: Summary & Table --- */
        .summary-box {
            background: #fff;
            border-left: 4px solid #0f766e;
            padding: 10px 15px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            border-radius: 4px;
        }
        .sec-title { font-size: 12px; font-weight: 800; color: #0f172a; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
        .summary-text { font-size: 11px; line-height: 1.5; color: #334155; text-align: justify; }
        
        .hl-crit { color: #dc2626; font-weight: 700; }
        .hl-brand { color: #0f766e; font-weight: 700; }

        /* Table Styling */
        .table-container { border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
        table { width: 100%; border-collapse: collapse; font-size: 10px; }
        th { background: #f1f5f9; color: #475569; padding: 8px 12px; text-align: left; font-weight: 700; text-transform: uppercase; font-size: 9px; }
        td { padding: 8px 12px; border-bottom: 1px solid #f1f5f9; color: #1e293b; vertical-align: middle; }
        tr:last-child td { border-bottom: none; }
        
        /* Zebra Striping */
        tr:nth-child(even) { background-color: #fcfcfc; }

        /* --- RIGHT COLUMN: Health Score & Highlights --- */
        .score-card {
            background: linear-gradient(145deg, #0f766e, #0d9488);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            color: white;
            margin-bottom: 20px;
            box-shadow: 0 10px 15px -3px rgba(15, 118, 110, 0.2);
        }
        .score-circle {
            width: 70px; height: 70px;
            background: rgba(255,255,255,0.2);
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            margin: 0 auto 10px auto;
            border: 2px solid rgba(255,255,255,0.4);
        }
        .score-val { font-size: 24px; font-weight: 800; }
        .risk-label { background: rgba(255,255,255,0.9); color: #0f766e; font-size: 9px; font-weight: 700; padding: 3px 10px; border-radius: 12px; display: inline-block; }
        
        .stats-box {
            background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px;
        }
        .stat-row { display: flex; justify-content: space-between; font-size: 10px; margin-bottom: 8px; color: #64748b; }
        .stat-val { font-weight: 700; color: #0f172a; }

        /* Status Pills */
        .pill { padding: 2px 8px; border-radius: 4px; font-size: 8px; font-weight: 700; text-transform: uppercase; }
        .pill-norm { background: #dcfce7; color: #166534; }
        .pill-warn { background: #fef9c3; color: #854d0e; }
        .pill-crit { background: #fee2e2; color: #991b1b; }

        /* Range Bar Visual */
        .range-track { width: 80px; height: 4px; background: #e2e8f0; border-radius: 2px; position: relative; display: inline-block; vertical-align: middle; margin-right: 5px; }
        .range-dot { width: 6px; height: 6px; border-radius: 50%; position: absolute; top: -1px; transform: translateX(-50%); }

        /* --- FOOTER (ABSOLUTE) --- */
        .bottom-section {
            position: absolute; bottom: 12mm; left: 15mm; right: 15mm;
        }
        .signature-container { text-align: right; margin-bottom: 8px; padding-right: 10px; }
        .sig-name { font-family: 'Times New Roman', serif; font-weight: bold; font-size: 16px; color: #0f172a; }
        .sig-line { border-top: 1px solid #0f766e; width: 160px; margin-left: auto; margin-top: 2px; margin-bottom: 2px; }
        .sig-role { font-size: 9px; font-weight: 700; color: #0f766e; text-transform: uppercase; }
        
        .footer-table { width: 100%; border-collapse: collapse; background-color: #f0fdfa; border-top: 2px solid #0f766e; }
        .footer-cell { padding: 8px 12px; vertical-align: middle; font-size: 8px; color: #334155; line-height: 1.3; width: 42%; }
        .footer-cell strong { color: #0f766e; text-transform: uppercase; font-size: 9px; margin-right: 4px; }
        .qr-cell { width: 16%; text-align: center; padding: 4px; background: white; border-left: 1px solid #e2e8f0; }
        .divider-cell { width: 1px; background: #cbd5e1; }
    </style>
</head>
<body>
<div class="page">

    <div class="header">
        <div class="logo-container">
            {% if logo_b64 %}
                <img src="data:image/jpeg;base64,{{ logo_b64 }}" class="logo-img" alt="Logo">
            {% else %}
                <h1 style="color:#0f766e; margin:0; font-size:24px;">MEESHA DIAGNOSTICS</h1>
            {% endif %}
        </div>
        <div class="header-title">
            <div class="report-name">AI Clinical Analysis</div>
            <div class="report-sub">Smart Interpretation & Summary</div>
            <div class="report-date">Generated on: {{ report_date }}</div>
        </div>
    </div>

    <div class="patient-card">
        <div class="p-group">
            <span class="p-label">Patient Name</span>
            <span class="p-val">{{ patient_name }}</span>
        </div>
        <div class="p-group">
            <span class="p-label">Age / Gender</span>
            <span class="p-val">{{ patient_age_gender }}</span>
        </div>
        <div class="p-group">
            <span class="p-label">Ref. Doctor</span>
            <span class="p-val">{{ doctor_name }}</span>
        </div>
        <div class="p-group" style="text-align:right;">
            <span class="p-label">Lab ID</span>
            <span class="p-val">{{ treatment_id }}</span>
        </div>
    </div>

    <div class="grid-container">
        
        <div>
            <div class="summary-box">
                <div class="sec-title">🤖 AI Executive Summary</div>
                <div class="summary-text">
                    {{ narrative }}
                </div>
            </div>

            <div class="sec-title">📊 Key Biomarkers</div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th width="35%">Test Name</th>
                            <th width="35%">Result</th>
                            <th width="30%">Analysis</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for test in full_results %}
                        <tr>
                            <td style="font-weight:600; color:#334155;">{{ test.name }}</td>
                            <td>
                                <div style="display:flex; align-items:center;">
                                    <div class="range-track">
                                        <div class="range-dot" 
                                             style="left: {{ test.visual_pct }}%; 
                                                    background: {% if 'Crit' in test.status %}#ef4444{% elif 'Normal' in test.status %}#22c55e{% else %}#f59e0b{% endif %};">
                                        </div>
                                    </div>
                                    <span style="font-weight:700; font-size:11px;">{{ test.value }}</span>
                                </div>
                                <div style="font-size:7px; color:#94a3b8; margin-top:2px;">Ref: {{ test.range }}</div>
                            </td>
                            <td>
                                {% if 'Crit' in test.status %}
                                    <span class="pill pill-crit">Critical</span>
                                {% elif 'Normal' in test.status %}
                                    <span class="pill pill-norm">Normal</span>
                                {% else %}
                                    <span class="pill pill-warn">Abnormal</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <div>
            <div class="score-card">
                <div class="score-circle">
                    <span class="score-val">{{ overall_score }}</span>
                </div>
                <div style="font-size:10px; opacity:0.9; margin-bottom:6px;">HEALTH SCORE</div>
                <div class="risk-label">{{ risk_label }}</div>
            </div>

            <div class="stats-box">
                <div class="sec-title" style="font-size:11px;">Overview</div>
                <div class="stat-row">
                    <span>Normal Tests</span>
                    <span class="stat-val" style="color:#166534;">{{ count_normal }}</span>
                </div>
                <div class="stat-row">
                    <span>Mild Deviations</span>
                    <span class="stat-val" style="color:#b45309;">{{ count_warn }}</span>
                </div>
                <div class="stat-row">
                    <span>Critical Alerts</span>
                    <span class="stat-val" style="color:#991b1b;">{{ count_crit }}</span>
                </div>
                <div style="margin-top:10px; border-top:1px solid #f1f5f9; padding-top:8px;">
                    <div style="font-size:9px; color:#64748b; line-height:1.4;">
                        <strong>Next Steps:</strong><br>
                        {% if count_crit > 0 %}
                        Consult doctor immediately for critical values.
                        {% else %}
                        Maintain healthy lifestyle. Routine checkup advised.
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>

    </div>

    <div class="bottom-section">
        <div class="signature-container">
            <div class="sig-name">Dr. Sudha TR</div>
            <div class="sig-line"></div>
            <div class="sig-role">Consultant Pathologist</div>
            <div style="font-size:8px; color:#64748b;">MBBS, MD (Pathology)</div>
        </div>

        <table class="footer-table">
            <tr>
                <td class="footer-cell">
                    <strong>📍 Mahalaxmi Branch:</strong> 
                    1st Floor, La View, B.J. Marg, Jacob Circle, Mumbai–400011<br>
                    📞 2305 3534 / 77100 84305 | ✉️ info@meeshahealth.net
                </td>
                <td class="divider-cell"></td>
                <td class="footer-cell">
                    <strong>📍 BKC Centre:</strong> 
                    310, 3rd Floor, Trade Center, BKC, Mumbai–400051<br>
                    📞 3540 5567 / 77108 47491 | ✉️ info.bkc@meeshahealth.net
                </td>
                <td class="qr-cell">
                    {% if footer_qr %}
                        <img src="data:image/png;base64,{{ footer_qr }}" style="height: 45px; width: 45px;">
                    {% else %}
                        <span style="font-size:7px">NO QR</span>
                    {% endif %}
                </td>
            </tr>
        </table>
    </div>

</div>
</body>
</html>
"""

# ==============================
#  SUPPORT FUNCTIONS
# ==============================
def get_wkhtmltopdf_config():
    """Locate wkhtmltopdf on Streamlit Cloud (Linux) or Windows."""
    # 1. Check Streamlit Cloud (Linux) default path
    if os.path.exists('/usr/bin/wkhtmltopdf'):
        return pdfkit.configuration(wkhtmltopdf='/usr/bin/wkhtmltopdf')
        
    # 2. Check Windows default path (Local)
    if os.path.exists(r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"):
        return pdfkit.configuration(wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")

    # 3. Last resort: Let pdfkit try to find it on the system PATH
    try:
        return pdfkit.configuration()
    except:
        return None
# ==============================
#  SUMMARY & SNAPSHOT HELPERS
# ==============================
def generate_safe_summary(info, results):
    """Layman-friendly text summary without printing actual numbers."""
    abnormal_tests = [t for t in results if t["status"] != "Normal"]

    if not abnormal_tests:
        return "✅ <span class='hl-brand'>All systems look stable.</span> All extracted tests are within the expected range for your age and gender."

    crit = [t for t in abnormal_tests if "Crit" in t["status"]]
    warn = [t for t in abnormal_tests if "Crit" not in t["status"]]

    lines = []
    if crit:
        names = ", ".join([f"<b>{t['name']}</b>" for t in crit])
        lines.append(
            f"<span class='hl-crit'>Important alert:</span> Some results such as {names} are significantly outside the reference range and should be reviewed by your doctor soon."
        )
    if warn:
        names = ", ".join([t["name"] for t in warn[:4]])
        count_rest = len(warn) - 4
        suffix = f" and {count_rest} more tests" if count_rest > 0 else ""
        lines.append(
            f"<b>Mild changes:</b> A few readings ({names}{suffix}) are slightly above or below the ideal range and may need routine monitoring or lifestyle changes."
        )

    return "<br><br>".join(lines)

def compute_snapshot_metrics(results):
    """Return health score, risk label, counts, and percentages for snapshot panel."""
    if not results:
        return 10, "Overall Low Risk", 0, 0, 0, 0, 0

    total = len(results)
    count_normal = sum(1 for r in results if r["status"] == "Normal")
    count_crit = sum(1 for r in results if "Crit" in r["status"])
    count_warn = total - count_normal - count_crit

    score = 10 - (count_crit * 2) - (count_warn * 1)
    score = max(1, min(10, score))

    if score >= 8:
        risk_label = "Overall Low Risk"
    elif score >= 5:
        risk_label = "Moderate Risk – Review"
    else:
        risk_label = "High Risk – See Doctor"

    pct_normal = int(round((count_normal / total) * 100)) if total else 0
    pct_abnormal = 100 - pct_normal if total else 0

    return score, risk_label, count_normal, count_warn, count_crit, pct_normal, pct_abnormal

# ==============================
#  MAIN STREAMLIT APP
# ==============================
def main():
    meesha_brand_header()

    st.title("AI Report Generator")
    st.subheader("Upload a PDF lab report to get an easy-to-understand AI summary.")

    st.markdown(
        """
        1. Click **Browse files** and select the patient PDF report.  
        2. Wait for analysis to finish.  
        3. Click **Download Combined AI Report** to save the PDF (AI summary + original report).
        """,
        unsafe_allow_html=False,
    )    

    # logo_b64 for PDF header
    logo_candidates = ["meesha_logo.jpeg"]
    logo_b64 = ""
    for cand in logo_candidates:
        cand_path = os.path.join(SCRIPT_DIR, cand)
        if os.path.exists(cand_path):
            logo_b64 = get_base64_image(cand_path)
            break

    # Footer QR Code
    # Look for meesha_qr.png in the project folder first
    qr_path = os.path.join(SCRIPT_DIR, "meesha_qr.png")
    # If not found there, try the desktop path as a fallback (optional, can remove if you moved the file)
    if not os.path.exists(qr_path):
         qr_path = r"C:\Users\sunil\Desktop\meesha_qr.png"

    footer_qr_b64 = ""
    if os.path.exists(qr_path):
        footer_qr_b64 = get_base64_image(qr_path)
    else:
        # You can choose to show a warning or just leave it empty
        pass 

    # >>> THIS LINE MUST COME BEFORE THE IF <<<
    uploaded_file = st.file_uploader("Step 1: Upload Patient Report (PDF)", type="pdf")

    if uploaded_file is not None:
        config = get_wkhtmltopdf_config()
        if not config:
            st.error("❌ 'wkhtmltopdf' not found. Please install wkhtmltopdf and restart the app.")
            st.stop()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
            tmp_pdf.write(uploaded_file.getvalue())
            temp_pdf_path = tmp_pdf.name

        st.info("🔍 Analysing the report. Please wait...")

        try:
            # Pass the CSV DB path correctly
            db_path = os.path.join(SCRIPT_DIR, CSV_DB_FILENAME)
            info, full_results = extract_comprehensive_data(temp_pdf_path, db_path)

            # DEBUG (optional)
            st.write("DEBUG: number of tests extracted:", len(full_results))
            if full_results:
                # Add Visual Percentage for Range Bar
                for test in full_results:
                    try:
                        # Extract result value
                        val_match = re.search(r"[-+]?\d*\.?\d+", test['value'])
                        if val_match:
                            val = float(val_match.group(0))
                            
                            # Parse range "low - high"
                            range_nums = re.findall(r"[-+]?\d*\.?\d+", test['range'])
                            if len(range_nums) >= 2:
                                low = float(range_nums[0])
                                high = float(range_nums[1])
                                span = high - low
                                if span > 0:
                                    pct = 20 + ((val - low) / span) * 60
                                    pct = max(5, min(95, pct))
                                    test['visual_pct'] = pct
                                else:
                                    test['visual_pct'] = 50
                            else:
                                test['visual_pct'] = 50
                        else:
                            test['visual_pct'] = 50
                    except:
                        test['visual_pct'] = 50

                st.write("DEBUG: first few tests:", full_results[:5])

            if info.get("date", "Unknown") == "Unknown":
                info["report_date"] = datetime.now().strftime("%d-%m-%Y")
            else:
                info["report_date"] = info["date"]

            narrative = generate_safe_summary(info, full_results)

            (
                overall_score,
                risk_label,
                count_normal,
                count_warn,
                count_crit,
                pct_normal,
                pct_abnormal,
            ) = compute_snapshot_metrics(full_results)

            st.success(f"✅ Analysis complete: {len(full_results)} tests identified from the PDF.")

            with st.expander("📄 View AI Summary on Screen"):
                st.markdown(narrative, unsafe_allow_html=True)

            env = Environment(loader=BaseLoader())
            template = env.from_string(HTML_TEMPLATE)

            html_output = template.render(
                patient_name=info["patient_name"],
                treatment_id=info["treatment_id"],
                patient_age_gender=info["age_gender"],
                doctor_name=info["doctor"],
                report_date=info["report_date"],
                narrative=narrative,
                full_results=full_results,
                logo_b64=logo_b64,
                footer_qr=footer_qr_b64, # Pass the QR code
                overall_score=overall_score,
                risk_label=risk_label,
                count_normal=count_normal,
                count_warn=count_warn,
                count_crit=count_crit,
                pct_normal=pct_normal,
                pct_abnormal=pct_abnormal,
            )

            temp_summary_path = temp_pdf_path.replace(".pdf", "_summary.pdf")
            options = {
                "page-size": "A4",
                "margin-top": "0mm",
                "margin-right": "0mm",
                "margin-bottom": "0mm",
                "margin-left": "0mm",
                "enable-local-file-access": None,
            }
            pdfkit.from_string(html_output, temp_summary_path, configuration=config, options=options)

            final_output_path = temp_pdf_path.replace(".pdf", "_final.pdf")
            merger = PdfWriter()
            merger.append(temp_summary_path)
            merger.append(temp_pdf_path)
            merger.write(final_output_path)
            merger.close()

            with open(final_output_path, "rb") as f:
                final_pdf_bytes = f.read()

            safe_name = info["patient_name"].replace(" ", "_") if info["patient_name"] != "Unknown" else "Patient"
            file_label = f"Meesha_Analysis_{safe_name}.pdf"

            st.download_button(
                "📥 Step 3: Download Combined AI Report",
                final_pdf_bytes,
                file_name=file_label,
                mime="application/pdf",
            )

        except Exception as e:
            st.error(f"Unexpected error during analysis: {e}")
            import traceback
            st.text(traceback.format_exc())

        finally:
            try:
                if os.path.exists(temp_pdf_path):
                    os.remove(temp_pdf_path)
                if "temp_summary_path" in locals() and os.path.exists(temp_summary_path):
                    os.remove(temp_summary_path)
                if "final_output_path" in locals() and os.path.exists(final_output_path):
                    os.remove(final_output_path)
            except:
                pass

if __name__ == "__main__":
    main()
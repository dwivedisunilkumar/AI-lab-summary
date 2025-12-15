import pdfplumber
import re
import pandas as pd
import os
import math
import logging
from collections import Counter

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
#  1. MASTER CONFIGURATION (Physiological Limits)
# ==========================================
TEST_CONFIG = {
    # THYROID
    "TSH":      {"aliases": ["tsh", "thyroid stimulating"], "valid": (0.005, 100.0)},
    "TOTAL T3": {"aliases": ["serum t3", "tri-iodothyronine", "t3 total"], "valid": (0.1, 30.0)},
    "TOTAL T4": {"aliases": ["serum t4", "tetra-iodothyronine", "t4 total"], "valid": (0.5, 30.0)},
    "FREE T3":  {"aliases": ["free t3", "ft3"], "valid": (0.1, 50.0)},
    "FREE T4":  {"aliases": ["free t4", "ft4"], "valid": (0.1, 10.0)},

    # DIABETES
    "HBA1C":    {"aliases": ["hba1c", "glycosylated"], "valid": (3.0, 20.0)}, 
    "AVG GLU":  {"aliases": ["average glucose", "mean plasma glucose"], "valid": (50, 600)},
    "FASTING":  {"aliases": ["fasting blood sugar", "fbs", "glucose fasting"], "valid": (20, 800)},
    "PP":       {"aliases": ["post prandial", "ppbs"], "valid": (20, 800)},

    # LIVER (Fixes Raunak's 1002 Error)
    "BILIRUBIN TOTAL": {"aliases": ["bilirubin total"], "valid": (0.1, 30.0)},
    "BILIRUBIN DIRECT": {"aliases": ["bilirubin direct"], "valid": (0.01, 20.0)},
    "BILIRUBIN INDIRECT": {"aliases": ["bilirubin indirect"], "valid": (0.01, 20.0)},
    "SGOT":     {"aliases": ["sgot", "ast", "aspartate"], "valid": (1, 3000)},
    "SGPT":     {"aliases": ["sgpt", "alt", "alanine"], "valid": (1, 3000)},
    "ALP":      {"aliases": ["alkaline phosphatase", "alp"], "valid": (10, 2000)},
    "GGT":      {"aliases": ["ggt", "gamma gt"], "valid": (1, 1000)},
    "PROTEIN TOTAL": {"aliases": ["total protein", "serum total proteins"], "valid": (2.0, 15.0)},
    "ALBUMIN":  {"aliases": ["serum albumin", "albumin"], "valid": (1.0, 10.0)},
    "GLOBULIN": {"aliases": ["serum globulin", "globulin"], "valid": (0.5, 10.0)},
    "A/G RATIO": {"aliases": ["a/g ratio", "albumin/globulin ratio"], "valid": (0.1, 5.0)}, 

    # LIPID
    "CHOLESTEROL": {"aliases": ["cholesterol total", "serum cholesterol"], "valid": (50, 800)},
    "TRIGLYCERIDES": {"aliases": ["triglycerides", "serum triglycerides"], "valid": (10, 3000)},
    "HDL":      {"aliases": ["hdl cholesterol", "serum hdl"], "valid": (5, 200)},
    "LDL":      {"aliases": ["ldl cholesterol", "serum ldl"], "valid": (5, 500)},
    "VLDL":     {"aliases": ["vldl"], "valid": (1, 200)},
    "LDL/HDL RATIO": {"aliases": ["ldl/hdl", "ldl-hdl ratio"], "valid": (0.1, 15.0)},
    "CHOL/HDL RATIO": {"aliases": ["chol/hdl", "cholesterol/hdl ratio"], "valid": (0.5, 20.0)},

    # KIDNEY
    "CREATININE":{"aliases": ["serum creatinine", "creatinine"], "valid": (0.1, 25.0)},
    "UREA":     {"aliases": ["blood urea", "serum urea"], "valid": (2, 400)},
    "BUN":      {"aliases": ["blood urea nitrogen", "serum bun"], "valid": (1, 200)},
    "URIC ACID":{"aliases": ["serum uric acid", "uric acid"], "valid": (1.0, 30.0)},
    "CALCIUM":  {"aliases": ["serum calcium", "calcium"], "valid": (4.0, 20.0)},

    # HEMATOLOGY / OTHERS
    "HAEMOGLOBIN":{"aliases": ["haemoglobin", "hemoglobin"], "valid": (2.0, 25.0)},
    "WBC":      {"aliases": ["total white blood", "wbc", "leukocyte"], "valid": (100, 500000)},
    "PLATELET": {"aliases": ["platelet count"], "valid": (1000, 2000000)},
    "ESR":      {"aliases": ["esr", "erythrocyte"], "valid": (0, 150)},
    
    # VITAMINS
    "VITAMIN B12": {"aliases": ["vitamin b12", "cyanocobalamin"], "valid": (50, 5000)},
    "VITAMIN D":   {"aliases": ["vitamin d", "25-oh"], "valid": (3, 300)},
    "CRP":      {"aliases": ["c-reactive protein", "crp"], "valid": (0, 500)},
}

# ==========================================
#  2. HELPERS
# ==========================================
def _normalize(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())

def _load_csv_references(csv_path):
    ranges = {}
    for k, v in TEST_CONFIG.items():
        ranges[k] = {"aliases": v["aliases"], "valid": v["valid"], "unit": "", "low": 0, "high": 0}
    
    if not csv_path or not os.path.exists(csv_path): return ranges
    try:
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip().str.lower()
        if 'testname' in df.columns:
            for _, row in df.iterrows():
                raw = str(row.get('testname', '')).strip()
                if not raw: continue
                target_key = raw.upper()
                for ek, ev in ranges.items():
                    if raw.lower() in ev['aliases']:
                        target_key = ek; break
                try:
                    if target_key not in ranges:
                        ranges[target_key] = {"aliases": [raw.lower()], "valid": (0, 99999), "unit": ""}
                    ranges[target_key]['low'] = float(row.get('lowvalue', 0))
                    ranges[target_key]['high'] = float(row.get('uppervalue', 0))
                except: continue
    except: pass
    return ranges

def _match_test_name(text, ref_db):
    norm = _normalize(text)
    if len(norm) < 3: return None
    for key, data in ref_db.items():
        for alias in sorted(data["aliases"], key=len, reverse=True):
            if alias in norm: return key
    return None

def _clean_number(val_str):
    if not isinstance(val_str, str): return None
    clean = re.sub(r'[HLhl<>≥≤=]', '', val_str).replace(",", "")
    match = re.search(r'([-+]?\d*\.?\d+)', clean)
    if match:
        try: return float(match.group(1))
        except: pass
    return None

# ==========================================
#  3. HYBRID SPATIAL ENGINE (Header + Density)
# ==========================================
def _get_header_zone(words):
    """
    Looks for 'Observed Value', 'Result' headers to lock the column.
    """
    target_headers = ["observed value", "test result", "result", "value"]
    
    # Group words by line
    lines = {}
    for w in words:
        y = round(w['top'])
        if y not in lines: lines[y] = []
        lines[y].append(w)
        
    for y, line_words in lines.items():
        line_text = " ".join([w['text'] for w in line_words]).lower()
        
        for tgt in target_headers:
            if tgt in line_text:
                # Find matching words
                header_words = [w for w in line_words if w['text'].lower() in tgt.split()]
                if not header_words: continue
                
                # Define Zone based on Header Position
                x_min = min(w['x0'] for w in header_words) - 15
                x_max = max(w['x1'] for w in header_words) + 15
                
                # Expand right for 'Observed Value' as numbers can be wider
                if "observed" in tgt: x_max += 25
                
                return x_min, x_max
    return None, None

def _get_density_zone(words, ref_db):
    """
    Fallback: Histogram analysis to find where numbers are clustered.
    """
    valid_xs = []
    for w in words:
        val = _clean_number(w['text'])
        if val is not None:
            # Ignore graph noise (left side) and years
            if w['x0'] > 150 and not (2000 < val < 2030):
                valid_xs.append((w['x0'], w['x1']))
    
    if not valid_xs: return 300, 500 # Default middle-right
    
    # Histogram Clustering (50px bins)
    centers = [(x0+x1)/2 for x0, x1 in valid_xs]
    bins = [int(c/50)*50 for c in centers]
    if not bins: return 300, 500
    
    most_common_bin = Counter(bins).most_common(1)[0][0]
    return most_common_bin - 20, most_common_bin + 70

# ==========================================
#  4. EXTRACTION LOGIC
# ==========================================
def _extract_from_page(page, ref_db):
    results = {}
    words = page.extract_words(keep_blank_chars=True)
    
    # A. Determine the "Truth Zone" (Result Column)
    x_min, x_max = _get_header_zone(words)
    if x_min is None:
        x_min, x_max = _get_density_zone(words, ref_db)
        
    # B. Group by Rows
    rows = {}
    for w in words:
        y = round(w['top'] / 4) * 4 # 4px tolerance
        if y not in rows: rows[y] = []
        rows[y].append(w)
        
    # C. Scan Rows
    sorted_rows = sorted(rows.items())
    for y, row_words in sorted_rows:
        row_words.sort(key=lambda w: w['x0'])
        
        # 1. Find Test Name (Left of Zone)
        # Only look at words starting BEFORE the result zone
        name_words = [w for w in row_words if w['x1'] < x_min + 20]
        name_text = " ".join([w['text'] for w in name_words])
        
        test_key = _match_test_name(name_text, ref_db)
        if test_key:
            # 2. Find Candidates on this row
            candidates = []
            for w in row_words:
                val = _clean_number(w['text'])
                if val is not None:
                    # Score the candidate
                    in_zone = (x_min <= ((w['x0']+w['x1'])/2) <= x_max)
                    
                    candidates.append({
                        'val': val,
                        'in_zone': in_zone,
                        'x': w['x0'],
                        'text': w['text']
                    })
            
            # 3. Filter & Pick Winner
            config = ref_db.get(test_key, {})
            min_v, max_v = config.get('valid', (0, 99999))
            
            valid_cands = []
            for c in candidates:
                # Physio Limits (Fixes 1002 Error)
                if c['val'] < min_v or c['val'] > max_v: continue
                # Year Filter
                if 2020 <= c['val'] <= 2030: continue
                valid_cands.append(c)
            
            if valid_cands:
                # Priority 1: The number is IN the Result Zone
                zone_cands = [c for c in valid_cands if c['in_zone']]
                
                if zone_cands:
                    # Best match found inside the column
                    results[test_key] = zone_cands[0]['val']
                else:
                    # Fallback: Pick the first valid number to the RIGHT of the Name
                    # But ensure it's not "too far" right (Ref Range)
                    # This handles slight misalignments
                    valid_cands.sort(key=lambda c: c['x'])
                    
                    # Ignore numbers that are clearly Graph Noise (Left side)
                    # Assuming name ends around X. Look for next number.
                    results[test_key] = valid_cands[0]['val']

    return results

# ==========================================
#  5. INFO EXTRACTION
# ==========================================
def _extract_basic_info(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"
    info = { "patient_name": "Unknown", "age_gender": "Unknown", "doctor": "Unknown", "treatment_id": "Unknown", "date": "Unknown" }
    
    m = re.search(r"(?:Patient\s*Name|Name)\s*[:\-]?\s*(.*?)(?=\s*(?:Age|Gender|Sex|Treatment|Ref|Mobile|Lab|$))", text, re.IGNORECASE)
    if m: info["patient_name"] = m.group(1).strip().split('\n')[0]

    m = re.search(r"(?:Age\s*[/]\s*Gender|Age|Gender)\s*[:\-]?\s*(.*?)(?=\s*(?:Mobile|Ref|Date|Patient|$))", text, re.IGNORECASE)
    if m: info["age_gender"] = m.group(1).strip().replace("Gender", "").strip().split('\n')[0]

    m = re.search(r"(?:Ref\.?\s*By|Referred\s*By|Consultant)\s*[:\-]?\s*(.*?)(?=\s*(?:Date|Lab|Sample|Patient|$))", text, re.IGNORECASE)
    if m: info["doctor"] = m.group(1).strip().split('\n')[0]
    
    id_match = re.search(r"(?:Treatment\s*Id|Lab\s*Id|ID)\s*[:\-]?\s*([A-Za-z0-9]+)", text, re.IGNORECASE)
    if id_match: info["treatment_id"] = id_match.group(1).strip()

    date_match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", text)
    if date_match: info["date"] = date_match.group(1).strip()
    return info

# ==========================================
#  6. MAIN EXPORT
# ==========================================
def extract_comprehensive_data(pdf_path: str, db_path=None):
    ref_db = _load_csv_references(db_path)
    info = _extract_basic_info(pdf_path)
    
    all_results = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_results = _extract_from_page(page, ref_db)
            all_results.update(page_results)
            
    full_results = []
    for key, val in all_results.items():
        ref = ref_db.get(key)
        if not ref: continue
        low, high = ref.get('low', 0), ref.get('high', 0)
        
        status = "Normal"
        if high > 0:
            if val < low: status = "Crit Low" if val < (low * 0.7) else "Low"
            elif val > high: status = "Crit High" if val > (high * 1.3) else "High"
        
        full_results.append({
            "name": key,
            "value": str(val),
            "range": f"{low} - {high} {ref.get('unit','')}",
            "status": status
        })
    
    full_results.sort(key=lambda x: x['name'])
    return info, full_results
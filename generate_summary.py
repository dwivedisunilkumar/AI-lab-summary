import pdfplumber
import re
import pandas as pd
import os
import math
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
#  1. MASTER CONFIGURATION
# ==========================================
TEST_CONFIG = {
    # Test Key: { aliases: [], valid: (min, max) }
    "TSH":      {"aliases": ["tsh", "thyroid stimulating"], "valid": (0.01, 100.0)},
    "TOTAL T3": {"aliases": ["serum t3", "tri-iodothyronine", "t3 total"], "valid": (0.1, 10.0)},
    "TOTAL T4": {"aliases": ["serum t4", "tetra-iodothyronine", "t4 total"], "valid": (0.5, 30.0)},
    "HBA1C":    {"aliases": ["hba1c", "glycosylated"], "valid": (3.0, 20.0)}, # Lowered floor to catch 3.0 if flagged, but reliant on column logic
    
    "CHOLESTEROL": {"aliases": ["cholesterol total", "serum cholesterol"], "valid": (50, 600)},
    "TRIGLYCERIDES": {"aliases": ["triglycerides", "serum triglycerides"], "valid": (10, 2000)},
    "HDL":      {"aliases": ["hdl cholesterol", "serum hdl"], "valid": (5, 150)},
    "LDL":      {"aliases": ["ldl cholesterol", "serum ldl"], "valid": (5, 400)},
    "SODIUM":   {"aliases": ["serum sodium", "sodium"], "valid": (100, 200)},
    "POTASSIUM":{"aliases": ["serum potassium", "potassium"], "valid": (1.0, 10.0)},
    "CHLORIDE": {"aliases": ["serum chloride", "chloride"], "valid": (60, 150)},
    "CREATININE":{"aliases": ["serum creatinine", "creatinine"], "valid": (0.1, 20.0)},
    "UREA":     {"aliases": ["blood urea", "serum urea"], "valid": (2, 300)},
    "BUN":      {"aliases": ["blood urea nitrogen", "serum bun"], "valid": (1, 150)},
    "URIC ACID":{"aliases": ["serum uric acid", "uric acid"], "valid": (1.0, 20.0)},
    "SGPT":     {"aliases": ["sgpt", "alt"], "valid": (1, 2000)},
    "SGOT":     {"aliases": ["sgot", "ast"], "valid": (1, 2000)},
    "HAEMOGLOBIN":{"aliases": ["haemoglobin", "hemoglobin"], "valid": (2.0, 25.0)},
    "WBC":      {"aliases": ["total white blood", "wbc"], "valid": (500, 500000)},
    "PLATELET": {"aliases": ["platelet count"], "valid": (5000, 1000000)},
    "ESR":      {"aliases": ["esr", "erythrocyte sedimentation"], "valid": (0, 150)},
    "CRP":      {"aliases": ["c-reactive protein", "crp"], "valid": (0, 300)},
    "VITAMIN B12": {"aliases": ["vitamin b12", "cyanocobalamin"], "valid": (100, 2500)},
    "MEAN PLASMA GLUCOSE": {"aliases": ["mean plasma glucose"], "valid": (50, 400)},
}

# ==========================================
#  2. HELPERS
# ==========================================
def _normalize(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())

def _load_csv_references(csv_path):
    ranges = {}
    for k, v in TEST_CONFIG.items():
        ranges[k] = {"aliases": v["aliases"], "valid": v["valid"], "low": 0, "high": 0, "unit": ""}
        
    if not csv_path or not os.path.exists(csv_path): return ranges
    try:
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip().str.lower()
        if 'testname' in df.columns:
            for _, row in df.iterrows():
                raw = str(row.get('testname', '')).strip()
                if not raw: continue
                key = raw.upper()
                target_key = key
                for ek, ev in ranges.items():
                    if raw.lower() in ev['aliases']:
                        target_key = ek
                        break
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
        for alias in data["aliases"]:
            if alias in norm: return key
    return None

def _clean_number(val_str):
    if not isinstance(val_str, str): return None
    clean = re.sub(r'[HLhl<>≥≤*]', '', val_str).replace(",", "")
    match = re.search(r'([-+]?\d*\.?\d+)', clean)
    if match:
        try:
            return float(match.group(1))
        except: pass
    return None

def _get_result_column_x_range(words):
    """
    Finds the X-coordinates (left, right) of the 'Observed Value' or 'Result' header.
    """
    target_headers = ["observed value", "test result", "result", "value"]
    
    # 1. Group words into lines
    lines = {}
    for w in words:
        top = round(w['top'], 0)
        if top not in lines: lines[top] = []
        lines[top].append(w)
        
    # 2. Scan lines for header
    for _, line_words in lines.items():
        line_text = " ".join([w['text'] for w in line_words]).lower()
        
        for tgt in target_headers:
            if tgt in line_text:
                # Find the words composing this header
                header_words = [w for w in line_words if w['text'].lower() in tgt.split()]
                if not header_words: continue
                
                # Calculate bounds
                x_min = min(w['x0'] for w in header_words) - 20 # Buffer left
                x_max = max(w['x1'] for w in header_words) + 20 # Buffer right
                
                # Special adjustment for wide headers
                if "observed" in tgt: x_max += 30
                
                return x_min, x_max
    return None, None

# ==========================================
#  3. SPATIAL EXTRACTION ENGINE
# ==========================================
def _extract_from_spatial_layout(pdf_path, ref_db):
    results = {}
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(keep_blank_chars=False)
            
            # 1. Find the Result Column Zone (X-Min, X-Max)
            x_min, x_max = _get_result_column_x_range(words)
            
            # If no header found, we can't do spatial locking safely
            if x_min is None: continue
            
            # 2. Group words by Row (Y-coordinate)
            rows = {}
            for w in words:
                y = round(w['top'] / 3) * 3  # Round to nearest 3px to handle slight misalignments
                if y not in rows: rows[y] = []
                rows[y].append(w)
            
            sorted_y = sorted(rows.keys())
            
            for y in sorted_y:
                row_words = rows[y]
                
                # A. Reconstruct Name (Left of Result Column)
                name_words = [w for w in row_words if w['x1'] < x_min]
                name_text = " ".join([w['text'] for w in name_words])
                
                test_key = _match_test_name(name_text, ref_db)
                if not test_key: continue
                
                # B. Find Result (INSIDE Result Column)
                # Strict check: Word must overlap significantly with the column zone
                result_words = [w for w in row_words if w['x0'] >= x_min and w['x1'] <= x_max]
                
                # If nothing perfectly inside, check for partial overlap (shift)
                if not result_words:
                    result_words = [w for w in row_words if max(x_min, w['x0']) < min(x_max, w['x1'])]
                
                result_text = " ".join([w['text'] for w in result_words])
                val = _clean_number(result_text)
                
                # C. Save Result
                if val is not None:
                    # Basic physiological check only
                    config = ref_db.get(test_key, {})
                    min_v, max_v = config.get('valid', (0, 99999))
                    
                    if val >= min_v and val <= max_v:
                        results[test_key] = val

    return results

# ==========================================
#  4. FALLBACK: TEXT SCAN
# ==========================================
def _extract_from_text_fallback(pdf_path, ref_db):
    """
    Fallback for when spatial headers aren't found.
    Uses strict 'After Name' logic.
    """
    results = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            lines = text.split('\n')
            
            for line in lines:
                # 1. Clean Noise
                clean_line = re.sub(r'\d{2,4}[/-]\d{1,2}[/-]\d{2,4}', '', line) # Dates
                
                # 2. Match Name
                test_key = _match_test_name(clean_line, ref_db)
                if not test_key or test_key in results: continue
                
                # 3. Find numbers AFTER the name
                # Simple strategy: Rightmost number is usually the result if no range is present
                # But safer to find the first number after the name
                
                # Regex for numbers
                nums = []
                for m in re.finditer(r'([-+]?\d*\.?\d+)', clean_line):
                    try:
                        val = float(m.group(1))
                        if val > 2020: continue # Year
                        nums.append(val)
                    except: pass
                
                if not nums: continue
                
                config = ref_db.get(test_key, {})
                min_v, max_v = config.get('valid', (0, 99999))
                
                # Filter valid
                valid_nums = [n for n in nums if n >= min_v and n <= max_v]
                
                if valid_nums:
                    # If multiple, assume first valid one after name is result
                    results[test_key] = valid_nums[0]
                    
    return results

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

    return info

# ==========================================
#  5. MAIN EXPORT
# ==========================================
def extract_comprehensive_data(pdf_path: str, db_path=None):
    ref_db = _load_csv_references(db_path)
    info = _extract_basic_info(pdf_path)
    
    # 1. Spatial Engine (Best for Grid Reports)
    raw_results = _extract_from_spatial_layout(pdf_path, ref_db)
    
    # 2. Fallback (If Spatial missed everything)
    if len(raw_results) == 0:
        raw_results = _extract_from_text_fallback(pdf_path, ref_db)
    
    full_results = []
    for key, val in raw_results.items():
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
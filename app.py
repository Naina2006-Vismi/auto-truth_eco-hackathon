"""
AutoTruth — Flask Backend
Serves the scoring API and renders the dashboard.
"""

import json
import os
import csv
import re
from io import BytesIO
from functools import lru_cache
from flask import Flask, jsonify, render_template, request, abort
from flask_cors import CORS
from engine.scoring import compute_lts
from engine.lifecycle_scorer import compute_drift, get_pillar_labels, get_pillar_weights
from engine.nlp_engine import extract_and_classify_claims, classify_claim
import pdfplumber
import PyPDF2

app = Flask(__name__)
CORS(app)

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "companies.json")
CSV_DATA_PATH = os.path.join(os.path.dirname(__file__), "EV Energy Efficiency Dataset.csv")
MAX_PDF_PAGES = 30
MAX_PDF_SIZE_BYTES = 60 * 1024 * 1024

PILLAR_KEYWORDS = {
    "raw_materials": ["lithium", "cobalt", "nickel", "mining", "mineral", "raw material"],
    "manufacturing": ["factory", "manufacturing", "plant", "scope 1", "scope 2", "renewable electricity"],
    "supply_chain": ["supplier", "scope 3", "procurement", "tier 1", "tier 2", "value chain"],
    "use_phase": ["use phase", "kwh", "efficiency", "lifecycle emissions", "grid", "charging"],
    "end_of_life": ["recycle", "recycling", "end-of-life", "second-life", "recovery", "battery return"],
    "offsets": ["offset", "carbon credit", "rec", "gold standard", "vcs", "net zero"],
}

EV_DOMAIN_TERMS = {
    "core": [
        "electric vehicle", "electric vehicles", "ev", "battery electric",
        "plug-in", "charging", "battery pack", "kwh/100km", "kwh/100 mi"
    ],
    "vehicle": [
        "vehicle", "vehicles", "automotive", "car", "truck", "model y", "model 3",
        "fleet", "drivetrain", "range"
    ],
    "supply": [
        "lithium", "nickel", "cobalt", "battery cell", "gigafactory",
        "scope 3", "supplier"
    ],
}

EV_AUTO_ANCHORS = [
    "ev manufacturer", "electric vehicle manufacturer", "vehicle production",
    "vehicle deliveries", "vehicle sales", "passenger vehicle", "automaker",
    "automobile", "automotive oem", "battery electric vehicle", "bev"
]

KNOWN_EV_COMPANIES = [
    "tesla", "rivian", "byd", "volkswagen", "vw", "hyundai", "kia", "ford",
    "general motors", "gm", "mercedes", "bmw", "audi", "nio", "xpeng", "lucid", "polestar"
]

NON_EV_SIGNAL_TERMS = [
    "iphone", "ipad", "macbook", "mac", "apple watch", "airpods", "data center",
    "packaging", "consumer electronics"
]

def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _clamp(val, low=0, high=100):
    return max(low, min(high, round(val, 1)))


def _logo_for_make(make: str) -> str:
    first = (make or "E").strip()[:1].upper()
    return first if first else "E"


def _hash_bucket(text: str, mod=100):
    return sum(ord(ch) for ch in (text or "")) % mod


def _build_claims(make: str, avg_eff: float, avg_motor: float, avg_recharge: float):
    return [
        {
            "text": f"{make} portfolio average energy efficiency is {avg_eff:.2f} km/kWh.",
            "type": "NUMERIC",
            "pillar": "use_phase",
            "verified": True,
            "confidence": 0.92,
        },
        {
            "text": f"Average electric motor output is {avg_motor:.0f} kW across listed models.",
            "type": "NUMERIC",
            "pillar": "manufacturing",
            "verified": True,
            "confidence": 0.89,
        },
        {
            "text": f"Average recharge time is {avg_recharge:.1f} hours for analyzed models.",
            "type": "NUMERIC",
            "pillar": "use_phase",
            "verified": True,
            "confidence": 0.88,
        },
        {
            "text": "The company is committed to continuous sustainability improvements across the value chain.",
            "type": "VAGUE",
            "pillar": "supply_chain",
            "verified": False,
            "confidence": 0.78,
        },
        {
            "text": "Offset and renewable energy credit strategy supports residual emission balancing.",
            "type": "OFFSET_BACKED",
            "pillar": "offsets",
            "verified": False,
            "confidence": 0.8,
        },
    ]


def _build_company_from_make(make: str, rows: list[dict]):
    efficiencies = [_safe_float(r.get("Energy Efficiency (km/kWh)"), 0) for r in rows]
    motors = [_safe_float(r.get("Motor (kW)"), 0) for r in rows]
    recharges = [_safe_float(r.get("Recharge time (h)"), 0) for r in rows]
    years = [_safe_float(r.get("Model year"), 2024) for r in rows]
    models = sorted({r.get("Model", "").strip() for r in rows if r.get("Model", "").strip()})

    avg_eff = sum(efficiencies) / max(1, len(efficiencies))
    avg_motor = sum(motors) / max(1, len(motors))
    avg_recharge = sum(recharges) / max(1, len(recharges))
    report_year = int(max(years) if years else 2024)

    bucket = _hash_bucket(make, 40)
    use_phase = _clamp(20 + (avg_eff * 10), 25, 95)
    manufacturing = _clamp(85 - (avg_motor / 7) + (bucket % 8), 30, 92)
    supply_chain = _clamp(46 + (bucket % 28), 28, 84)
    raw_materials = _clamp(42 + ((bucket * 3) % 30), 28, 86)
    end_of_life = _clamp(40 + ((bucket * 2) % 34), 30, 90)
    offsets = _clamp(76 - (avg_recharge * 4) + (bucket % 10), 22, 90)

    pillar_scores = {
        "raw_materials": raw_materials,
        "manufacturing": manufacturing,
        "supply_chain": supply_chain,
        "use_phase": use_phase,
        "end_of_life": end_of_life,
        "offsets": offsets,
    }

    prior_year_scores = {k: _clamp(v - (2 + (bucket % 5)), 0, 100) for k, v in pillar_scores.items()}
    offset_dependency = _clamp(18 + (bucket % 32), 2, 70)
    qualities = ["None", "VCS", "Unverified", "Gold Standard"]
    offset_quality = qualities[bucket % len(qualities)]
    regulatory_alignment = {
        "GRI": bucket % 2 == 0,
        "CSRD": bucket % 3 == 0,
        "SEC_Climate": bucket % 4 == 0,
        "TCFD": bucket % 5 in (0, 1),
    }

    min_year = int(min(years) if years else report_year)
    model_count = len(models)
    model_label = f"{model_count} EV models ({min_year}-{report_year})"

    return {
        "id": f"make-{_slugify(make)}",
        "name": make,
        "logo": _logo_for_make(make),
        "model": model_label,
        "models": models,
        "__rows": rows,
        "report_year": report_year,
        "claims": _build_claims(make, avg_eff, avg_motor, avg_recharge),
        "pillar_scores": pillar_scores,
        "prior_year_scores": prior_year_scores,
        "offset_dependency": offset_dependency,
        "offset_quality": offset_quality,
        "regulatory_alignment": regulatory_alignment,
        "grid_carbon_intensity_gco2_kwh": _clamp(280 + (bucket * 6), 180, 640),
    }


def _build_company_from_model(make: str, model_name: str, rows: list[dict]):
    base = _build_company_from_make(make, rows)
    model_count = len(rows)
    year_values = [_safe_float(r.get("Model year"), base.get("report_year", 2024)) for r in rows]
    min_year = int(min(year_values) if year_values else base.get("report_year", 2024))
    max_year = int(max(year_values) if year_values else base.get("report_year", 2024))
    base["id"] = f"{base['id']}--model-{_slugify(model_name)}"
    base["model"] = f"{model_name} ({model_count} records, {min_year}-{max_year})"
    base["models"] = [model_name]
    return base


@lru_cache(maxsize=1)
def _load_companies_from_csv():
    if not os.path.exists(CSV_DATA_PATH):
        return None

    grouped = {}
    with open(CSV_DATA_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            make = (row.get("Make") or "").strip()
            if not make:
                continue
            grouped.setdefault(make, []).append(row)

    if not grouped:
        return None

    companies = [_build_company_from_make(make, rows) for make, rows in sorted(grouped.items())]
    return companies


def load_companies():
    csv_companies = _load_companies_from_csv()
    if csv_companies:
        return csv_companies
    with open(DATA_PATH, "r") as f:
        return json.load(f)["companies"]

def get_company_by_id(company_id: str):
    companies = load_companies()
    for c in companies:
        if c["id"] == company_id:
            return c
    return None


def _extract_pdf_text(file_bytes: bytes):
    text_parts = []
    page_count = 0

    # Strategy 1: pdfplumber text + word extraction fallback per page
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages[:MAX_PDF_PAGES]:
            page_count += 1
            page_text = page.extract_text() or ""
            if not page_text.strip():
                words = page.extract_words() or []
                page_text = " ".join(w.get("text", "") for w in words)
            if page_text.strip():
                text_parts.append(page_text)

    merged = "\n".join(text_parts).strip()

    # Strategy 2: PyPDF2 if pdfplumber extraction is sparse
    if len(merged) < 1200:
        reader = PyPDF2.PdfReader(BytesIO(file_bytes))
        page_count = min(len(reader.pages), MAX_PDF_PAGES)
        pypdf_text = []
        for page in reader.pages[:MAX_PDF_PAGES]:
            pypdf_text.append(page.extract_text() or "")
        pypdf_merged = "\n".join(pypdf_text).strip()
        if len(pypdf_merged) > len(merged):
            merged = pypdf_merged

    return merged, page_count


def _infer_pillar(claim_text: str):
    claim_lower = claim_text.lower()
    scores = {}
    for pillar, keywords in PILLAR_KEYWORDS.items():
        scores[pillar] = sum(1 for kw in keywords if kw in claim_lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "supply_chain"


def _estimate_pillar_scores(text: str):
    text_lower = text.lower()
    output = {}
    for pillar, keywords in PILLAR_KEYWORDS.items():
        hits = sum(text_lower.count(kw) for kw in keywords)
        if hits == 0:
            score = 22
        elif hits < 3:
            score = 40 + (hits * 10)
        else:
            score = min(95, 62 + (hits * 4))
        output[pillar] = score
    return output


def _estimate_regulatory_alignment(text: str):
    text_lower = text.lower()
    return {
        "GRI": ("gri" in text_lower) or ("global reporting initiative" in text_lower),
        "CSRD": "csrd" in text_lower,
        "SEC_Climate": ("sec climate" in text_lower) or ("sec rule" in text_lower),
        "TCFD": "tcfd" in text_lower,
    }


def _estimate_offset_quality(text: str):
    text_lower = text.lower()
    if "gold standard" in text_lower:
        return "Gold Standard"
    if "vcs" in text_lower or "verified carbon standard" in text_lower:
        return "VCS"
    if "offset" in text_lower or "carbon credit" in text_lower or "rec" in text_lower:
        return "Unverified"
    return "None"


def _fallback_claims_from_lines(text: str):
    claims = []
    for line in text.splitlines():
        cleaned = " ".join(line.split())
        if len(cleaned) < 28:
            continue
        c = classify_claim(cleaned)
        claims.append({"text": cleaned, **c})
        if len(claims) >= 120:
            break
    return claims


def _detect_ev_domain(text: str, filename: str):
    content = f"{filename} {text[:180000]}".lower()

    core_hits = [t for t in EV_DOMAIN_TERMS["core"] if t in content]
    vehicle_hits = [t for t in EV_DOMAIN_TERMS["vehicle"] if t in content]
    supply_hits = [t for t in EV_DOMAIN_TERMS["supply"] if t in content]
    anchor_hits = [t for t in EV_AUTO_ANCHORS if t in content]
    company_hits = [t for t in KNOWN_EV_COMPANIES if t in content]
    non_ev_hits = [t for t in NON_EV_SIGNAL_TERMS if t in content]

    # Weighted EV relevance score
    score = (
        (len(core_hits) * 3)
        + (len(vehicle_hits) * 2)
        + (len(supply_hits))
        + (len(anchor_hits) * 4)
        + (len(company_hits) * 3)
        - (len(non_ev_hits) * 2)
    )

    # Require stronger EV-specific evidence to avoid false positives in general sustainability reports.
    has_ev_specific_anchor = len(anchor_hits) >= 1 or len(company_hits) >= 1
    is_ev_domain = has_ev_specific_anchor and score >= 12

    if is_ev_domain:
        recommendation = "EV domain confirmed. You can continue with full EV transparency scoring."
    else:
        recommendation = "This file may not be EV-focused. Re-upload an EV report or continue anyway."

    matched = (core_hits + vehicle_hits + supply_hits + anchor_hits + company_hits)[:12]
    return {
        "is_ev_domain": is_ev_domain,
        "ev_relevance_score": score,
        "matched_terms": matched,
        "non_ev_terms": non_ev_hits[:8],
        "recommendation": recommendation,
    }


# ── Routes ──────────────────────────────────────────────

@app.route("/")
def index():
    companies = load_companies()
    company_list = [{"id": c["id"], "name": c["name"], "logo": c["logo"], "model": c["model"]} for c in companies]
    return render_template("index.html", companies=company_list)


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# ── API ──────────────────────────────────────────────────

@app.route("/api/companies")
def api_companies():
    companies = load_companies()
    return jsonify([
        {
            "id": c["id"],
            "name": c["name"],
            "logo": c["logo"],
            "model": c["model"],
            "model_count": len(c.get("models", [])),
        }
        for c in companies
    ])


@app.route("/api/models/<company_id>")
def api_models(company_id):
    company = get_company_by_id(company_id)
    if not company:
        abort(404, description=f"Company '{company_id}' not found.")

    models = sorted(company.get("models", []))
    return jsonify({"company_id": company_id, "models": models})


@app.route("/api/analyze/<company_id>")
def api_analyze(company_id):
    company = get_company_by_id(company_id)
    if not company:
        abort(404, description=f"Company '{company_id}' not found.")

    selected_model = (request.args.get("model") or "").strip()
    company_for_analysis = company
    if selected_model and company.get("__rows"):
        model_rows = [r for r in company["__rows"] if (r.get("Model") or "").strip() == selected_model]
        if not model_rows:
            abort(404, description=f"Model '{selected_model}' not found for company '{company['name']}'.")
        company_for_analysis = _build_company_from_model(company["name"], selected_model, model_rows)
        company_for_analysis["logo"] = company.get("logo", "")

    result = compute_lts(company_for_analysis)

    # Add temporal drift
    drift = compute_drift(
        company_for_analysis.get("pillar_scores", {}),
        company_for_analysis.get("prior_year_scores", {})
    )
    result["temporal_drift"] = drift
    result["pillar_labels"] = get_pillar_labels()
    result["pillar_weights"] = get_pillar_weights()
    if selected_model:
        result["selected_model"] = selected_model

    return jsonify(result)


@app.route("/api/compare")
def api_compare():
    """Compare multiple companies. Pass ?ids=tesla,byd,rivian"""
    ids_param = request.args.get("ids", "")
    if not ids_param:
        abort(400, description="Provide ?ids=company1,company2")

    ids = [i.strip() for i in ids_param.split(",") if i.strip()]
    results = []
    for cid in ids:
        company = get_company_by_id(cid)
        if company:
            r = compute_lts(company)
            r["id"] = cid
            r["logo"] = company.get("logo", "")
            results.append(r)
    
    return jsonify(results)


@app.route("/api/pillar-info")
def api_pillar_info():
    return jsonify({
        "labels": get_pillar_labels(),
        "weights": get_pillar_weights()
    })


@app.route("/api/analyze-pdf", methods=["POST"])
def api_analyze_pdf():
    if "file" not in request.files:
        abort(400, description="Upload a PDF file in form field 'file'.")

    file = request.files["file"]
    if not file or not file.filename:
        abort(400, description="No file selected.")
    if not file.filename.lower().endswith(".pdf"):
        abort(400, description="Only .pdf files are supported.")

    file_bytes = file.read()
    if len(file_bytes) > MAX_PDF_SIZE_BYTES:
        abort(400, description="PDF exceeds 60MB limit.")

    try:
        full_text, page_count = _extract_pdf_text(file_bytes)
    except Exception:
        abort(400, description="Failed to parse PDF. Ensure it is a valid text PDF.")

    if not full_text.strip():
        abort(400, description="No readable text found. Try a text-based PDF instead of a scanned image.")

    domain_info = _detect_ev_domain(full_text, file.filename)

    claims = extract_and_classify_claims(full_text[:240000])
    if not claims:
        claims = _fallback_claims_from_lines(full_text[:240000])
    claims = claims[:120]

    if not claims:
        abort(400, description="Could not extract enough analyzable claims from this PDF.")

    enriched_claims = []
    for c in claims:
        claim_copy = dict(c)
        claim_copy["pillar"] = _infer_pillar(claim_copy["text"])
        claim_copy["verified"] = claim_copy["type"] == "NUMERIC"
        enriched_claims.append(claim_copy)

    pillar_scores = _estimate_pillar_scores(full_text)
    prior_scores = {k: max(0, v - 4) for k, v in pillar_scores.items()}
    regulatory = _estimate_regulatory_alignment(full_text)
    offset_quality = _estimate_offset_quality(full_text)
    offset_dependency = min(90, sum(full_text.lower().count(k) for k in ["offset", "carbon credit", "rec"]) * 3)

    synthetic_company = {
        "name": os.path.splitext(file.filename)[0][:60],
        "model": "Uploaded Sustainability Report",
        "report_year": 2024,
        "claims": enriched_claims,
        "pillar_scores": pillar_scores,
        "prior_year_scores": prior_scores,
        "offset_dependency": offset_dependency,
        "offset_quality": offset_quality,
        "regulatory_alignment": regulatory,
        "grid_carbon_intensity_gco2_kwh": 420,
    }

    result = compute_lts(synthetic_company)
    result["temporal_drift"] = compute_drift(pillar_scores, prior_scores)
    result["pillar_labels"] = get_pillar_labels()
    result["pillar_weights"] = get_pillar_weights()
    result["source"] = "uploaded_pdf"
    result["source_file"] = file.filename
    result["pages_processed"] = page_count
    result["claims_extracted"] = len(enriched_claims)
    result["domain_detection"] = domain_info
    return jsonify(result)


if __name__ == "__main__":
    print("🌿 AutoTruth server starting at http://localhost:5001")
    app.run(debug=True, port=5001)

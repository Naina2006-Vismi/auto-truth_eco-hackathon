"""
AutoTruth Scoring Algorithm
Aggregates pillar scores, claim quality, offset penalty, and regulatory alignment
into a final Lifecycle Transparency Score (LTS) out of 100.
"""

from engine.lifecycle_scorer import compute_weighted_score
from engine.offset_detector import analyze_offsets
from engine.nlp_engine import get_claim_quality_ratio

# Regulatory standards and their point bonuses
REGULATORY_BONUSES = {
    "GRI": 2.0,
    "CSRD": 3.0,
    "SEC_Climate": 2.5,
    "TCFD": 1.5,
}

RISK_TIERS = [
    (80, "Transparent", "#00e676", "✅ High Transparency — claims are well-substantiated and disclosure is comprehensive."),
    (60, "Moderate", "#ffeb3b", "⚠️ Moderate Transparency — some pillars are well-documented, but gaps remain."),
    (40, "Opaque", "#ff9800", "🟠 Opaque Disclosures — significant claim vagueness and lifecycle gaps detected."),
    (0,  "Greenwashing", "#f44336", "🚨 Greenwashing Detected — disclosures are primarily vague, offset-dependent, or misleading."),
]

# Rewrite suggestions for vague claim archetypes
REWRITE_SUGGESTIONS = {
    "committed to": "State the specific target (e.g., 'committed to reducing Scope 1 emissions by 45% by 2030 vs. 2019 baseline')",
    "strives to": "Replace with a measurable commitment and timeline.",
    "eco-friendly": "Quantify the impact (e.g., 'reduces lifecycle CO₂ by X% vs. equivalent ICE vehicle').",
    "sustainable future": "Disclose specific emission reduction targets with base year and verification methodology.",
    "responsible sourcing": "Reference a third-party audit or certification (e.g., IRMA, RMI Responsible Minerals).",
    "under assessment": "Provide current scope and expected reporting timeline.",
    "being established": "Disclose the partner, target recovery rate, and projected timeline.",
    "plans to": "Commit to a specific, time-bound, measurable target.",
    "dedicated to": "Replace with a quantified target and accountability mechanism.",
}


def suggest_rewrite(claim_text: str) -> str:
    """Suggest a data-backed rewrite for a vague claim."""
    claim_lower = claim_text.lower()
    for trigger, suggestion in REWRITE_SUGGESTIONS.items():
        if trigger in claim_lower:
            return suggestion
    return "Replace vague language with specific metrics, timelines, and verified data sources."


def compute_regulatory_bonus(alignment: dict) -> float:
    """Sum bonuses for meeting regulatory disclosure standards."""
    bonus = 0.0
    for standard, met in alignment.items():
        if met:
            bonus += REGULATORY_BONUSES.get(standard, 0)
    return min(bonus, 8.0)  # Cap total regulatory bonus at 8 points


def classify_risk(score: float) -> dict:
    """Return risk tier for a given LTS score."""
    for threshold, label, color, description in RISK_TIERS:
        if score >= threshold:
            return {"label": label, "color": color, "description": description}
    return {"label": "Greenwashing", "color": "#f44336", "description": RISK_TIERS[-1][3]}


def compute_investor_esg_index(lts_score: float, offset_risk: str) -> dict:
    """
    Derive an ESG confidence index for investors based on LTS.
    Higher LTS = lower ESG financial risk.
    """
    base = lts_score
    offset_penalty_map = {"LOW": 0, "MODERATE": -5, "HIGH": -15}
    adjusted = max(0, base + offset_penalty_map.get(offset_risk, 0))
    
    if adjusted >= 75:
        rating = "AAA"
        interpretation = "Minimal ESG disclosure risk"
    elif adjusted >= 60:
        rating = "AA"
        interpretation = "Low-moderate ESG risk"
    elif adjusted >= 45:
        rating = "BBB"
        interpretation = "Moderate ESG risk — gaps in lifecycle reporting"
    elif adjusted >= 30:
        rating = "BB"
        interpretation = "Elevated ESG risk — significant disclosure weaknesses"
    else:
        rating = "CCC"
        interpretation = "High ESG risk — greenwashing exposure"

    return {
        "score": round(adjusted, 1),
        "rating": rating,
        "interpretation": interpretation
    }


def compute_lts(company_data: dict) -> dict:
    """
    Full LTS computation pipeline for one company.
    Returns complete scoring breakdown.
    """
    claims = company_data.get("claims", [])
    pillar_scores = company_data.get("pillar_scores", {})
    prior_year = company_data.get("prior_year_scores", {})
    offset_dep = company_data.get("offset_dependency", 0)
    offset_quality = company_data.get("offset_quality", "Unverified")
    regulatory = company_data.get("regulatory_alignment", {})
    grid_intensity = company_data.get("grid_carbon_intensity_gco2_kwh", 400)

    # 1. Weighted pillar score (base)
    pillar_total = compute_weighted_score(pillar_scores)

    # 2. Claim quality ratio
    claim_ratio = get_claim_quality_ratio(claims)
    # Numeric claims boost score; vague claims penalize
    claim_quality_adjustment = round(
        (claim_ratio["numeric"] * 8) - (claim_ratio["vague"] * 6), 2
    )

    # 3. Offset analysis
    offset_analysis = analyze_offsets(offset_dep, offset_quality)
    offset_penalty = offset_analysis["dependency_penalty"]

    # 4. Regulatory alignment bonus
    regulatory_bonus = compute_regulatory_bonus(regulatory)

    # 5. Grid carbon adjustment (higher intensity = small downward pressure on use_phase)
    grid_penalty = 0
    if grid_intensity > 500:
        grid_penalty = -2
    elif grid_intensity > 400:
        grid_penalty = -1

    # 6. Final LTS
    raw_lts = pillar_total + claim_quality_adjustment - offset_penalty + regulatory_bonus + grid_penalty
    lts = round(max(0, min(100, raw_lts)), 1)

    # 7. Risk classification
    risk = classify_risk(lts)

    # 8. ESG Investor Index
    esg_index = compute_investor_esg_index(lts, offset_analysis["risk_level"])

    # 9. Greenwash fingerprint per claim
    fingerprinted_claims = []
    for claim in claims:
        fp_score = 0
        if claim["type"] == "VAGUE":
            fp_score = -8
        elif claim["type"] == "OFFSET_BACKED" and offset_quality == "Unverified":
            fp_score = -12
        elif claim["type"] == "NUMERIC" and claim.get("verified", False):
            fp_score = +5
        
        entry = dict(claim)
        entry["impact_score"] = fp_score
        if claim["type"] == "VAGUE":
            entry["rewrite_suggestion"] = suggest_rewrite(claim["text"])
        else:
            entry["rewrite_suggestion"] = None
        fingerprinted_claims.append(entry)

    return {
        "company": company_data.get("name"),
        "model": company_data.get("model"),
        "report_year": company_data.get("report_year"),
        "lts": lts,
        "risk": risk,
        "breakdown": {
            "pillar_weighted_base": round(pillar_total, 1),
            "claim_quality_adjustment": claim_quality_adjustment,
            "offset_penalty": -offset_penalty,
            "regulatory_bonus": regulatory_bonus,
            "grid_penalty": grid_penalty,
        },
        "pillar_scores": pillar_scores,
        "prior_year_scores": prior_year,
        "claim_ratio": claim_ratio,
        "claims": fingerprinted_claims,
        "offset_analysis": offset_analysis,
        "regulatory_alignment": regulatory,
        "grid_carbon_intensity": grid_intensity,
        "esg_investor_index": esg_index,
    }

"""
AutoTruth Offset Detector
Detects over-reliance on carbon offsets and flags greenwashing risk.
"""

OFFSET_THRESHOLD = 30  # % above which offset dependency triggers a penalty

QUALITY_SCORES = {
    "Gold Standard": 90,
    "VCS": 65,
    "Unverified": 25,
    "None": 100,  # No offsets = operationally driven reductions (best)
}

QUALITY_DESCRIPTIONS = {
    "Gold Standard": "High-integrity offset — verified by Gold Standard foundation with co-benefits.",
    "VCS": "Moderate-integrity offset — Verified Carbon Standard, widely recognized but variable quality.",
    "Unverified": "Low-integrity offset — no recognized third-party verification. High greenwash risk.",
    "None": "No carbon offsets used. All emission reductions are real, operational, and technology-driven.",
}


def analyze_offsets(offset_dependency_pct: float, offset_quality: str) -> dict:
    """
    Analyze offset strategy and return risk flags.
    
    Args:
        offset_dependency_pct: Percentage of total reductions from offsets (0-100)
        offset_quality: Quality tier string

    Returns:
        dict with risk level, penalty applied, and description
    """
    quality_score = QUALITY_SCORES.get(offset_quality, 25)
    
    # Compute penalty based on dependency + quality
    dependency_penalty = 0
    if offset_quality == "None":
        dependency_penalty = 0
    elif offset_dependency_pct > OFFSET_THRESHOLD:
        excess = offset_dependency_pct - OFFSET_THRESHOLD
        # Higher dependency = higher penalty; lower quality amplifies it
        quality_multiplier = 1.0 if quality_score >= 80 else (1.5 if quality_score >= 60 else 2.5)
        dependency_penalty = min(round((excess / 10) * quality_multiplier * 3, 1), 20)

    # Risk classification
    if offset_quality == "None" or (offset_dependency_pct < 15 and quality_score >= 65):
        risk = "LOW"
        risk_label = "✅ Low Offset Risk"
    elif offset_dependency_pct < OFFSET_THRESHOLD and quality_score >= 65:
        risk = "MODERATE"
        risk_label = "⚠️ Moderate Offset Risk"
    elif offset_quality == "Unverified" or offset_dependency_pct > 50:
        risk = "HIGH"
        risk_label = "🚨 High Greenwash Risk"
    else:
        risk = "MODERATE"
        risk_label = "⚠️ Moderate Offset Risk"

    return {
        "offset_dependency_pct": offset_dependency_pct,
        "offset_quality": offset_quality,
        "quality_score": quality_score,
        "quality_description": QUALITY_DESCRIPTIONS.get(offset_quality, "Unknown offset type."),
        "dependency_penalty": dependency_penalty,
        "risk_level": risk,
        "risk_label": risk_label,
        "threshold": OFFSET_THRESHOLD,
        "exceeds_threshold": offset_dependency_pct > OFFSET_THRESHOLD and offset_quality != "None"
    }

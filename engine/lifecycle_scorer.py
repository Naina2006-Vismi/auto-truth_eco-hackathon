"""
AutoTruth Lifecycle Scorer
Scores disclosure coverage across 6 lifecycle pillars.
"""

PILLAR_WEIGHTS = {
    "raw_materials": 0.20,
    "manufacturing": 0.20,
    "supply_chain": 0.15,
    "use_phase": 0.20,
    "end_of_life": 0.15,
    "offsets": 0.10,
}

PILLAR_LABELS = {
    "raw_materials": "Raw Material Extraction",
    "manufacturing": "Manufacturing & Energy",
    "supply_chain": "Supply Chain (Scope 3)",
    "use_phase": "Use Phase (Grid Carbon)",
    "end_of_life": "Battery End-of-Life",
    "offsets": "Offset Strategy",
}


def compute_weighted_score(pillar_scores: dict) -> float:
    """Compute weighted total score from pillar scores (0-100)."""
    total = 0.0
    for pillar, weight in PILLAR_WEIGHTS.items():
        score = pillar_scores.get(pillar, 0)
        total += score * weight
    return round(total, 2)


def compute_drift(current: dict, previous: dict) -> dict:
    """Compute year-over-year score drift per pillar."""
    drift = {}
    for pillar in PILLAR_WEIGHTS:
        cur = current.get(pillar, 0)
        prev = previous.get(pillar, 0)
        delta = cur - prev
        drift[pillar] = {
            "current": cur,
            "previous": prev,
            "delta": round(delta, 1),
            "trend": "improved" if delta > 2 else ("declined" if delta < -2 else "stable")
        }
    return drift


def get_pillar_labels():
    return PILLAR_LABELS


def get_pillar_weights():
    return PILLAR_WEIGHTS

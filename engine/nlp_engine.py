"""
AutoTruth NLP Engine
Classifies sustainability claims as NUMERIC, VAGUE, or OFFSET_BACKED
using keyword rules + pattern matching (no internet required)
"""

import re

# Keyword dictionaries for classification
NUMERIC_PATTERNS = [
    r'\d+\.?\d*\s*%',
    r'\d+\.?\d*\s*(tonnes?|tons?|kg|kWh|MWh|GWh|gCO2|km|mi|g/km)',
    r'(reduced|decreased|improved|increased|achieved|recovered)\s+by\s+\d+',
    r'\d+\s*(million|billion|thousand)',
    r'(zero|100%)\s+(cobalt|offset|renewable|recycl)',
]

VAGUE_PHRASES = [
    'committed to', 'strives to', 'works toward', 'we believe', 'eco-friendly',
    'sustainable future', 'green', 'responsible sourcing', 'better for the planet',
    'environmentally friendly', 'we aim', 'we aspire', 'under assessment',
    'being established', 'plans to', 'intends to', 'dedicated to', 'passionate about',
    'world-class', 'best-in-class', 'industry-leading', 'cutting-edge'
]

OFFSET_PHRASES = [
    'carbon neutral', 'carbon offset', 'offset', 'carbon credit', 'net zero via',
    'REC', 'renewable energy certificate', 'forest conservation', 'nature-based',
    'carbon removal', 'inset', 'compensate', 'carbon-neutral'
]

OFFSET_QUALITY_MAP = {
    'gold standard': 'Gold Standard',
    'vcs': 'VCS',
    'verified carbon standard': 'VCS',
    'redd+': 'VCS',
    'forest conservation': 'Unverified',
    'rec': 'Unverified',
    'renewable energy certificate': 'Unverified',
}


def classify_claim(text: str) -> dict:
    """Classify a single claim text into NUMERIC, VAGUE, or OFFSET_BACKED."""
    text_lower = text.lower()

    # Check OFFSET first (most specific)
    for phrase in OFFSET_PHRASES:
        if phrase.lower() in text_lower:
            quality = "Unverified"
            for key, val in OFFSET_QUALITY_MAP.items():
                if key in text_lower:
                    quality = val
                    break
            return {
                "type": "OFFSET_BACKED",
                "offset_quality": quality,
                "confidence": round(0.85 + (0.1 if any(p in text_lower for p in ['gold standard', 'verified']) else 0), 2)
            }

    # Check NUMERIC
    for pattern in NUMERIC_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return {
                "type": "NUMERIC",
                "offset_quality": None,
                "confidence": round(0.88 + (0.07 if '%' in text else 0), 2)
            }

    # Default VAGUE
    vague_score = sum(1 for phrase in VAGUE_PHRASES if phrase in text_lower)
    confidence = min(0.72 + (vague_score * 0.04), 0.95)
    return {
        "type": "VAGUE",
        "offset_quality": None,
        "confidence": round(confidence, 2)
    }


def extract_and_classify_claims(text: str) -> list:
    """Split text into sentences and classify each."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    results = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) > 20:
            classification = classify_claim(sentence)
            results.append({
                "text": sentence,
                **classification
            })
    return results


def get_claim_quality_ratio(claims: list) -> dict:
    """Returns ratio of NUMERIC, VAGUE, OFFSET_BACKED claims."""
    total = len(claims)
    if total == 0:
        return {"numeric": 0, "vague": 0, "offset": 0}
    counts = {"NUMERIC": 0, "VAGUE": 0, "OFFSET_BACKED": 0}
    for claim in claims:
        counts[claim.get("type", "VAGUE")] += 1
    return {
        "numeric": round(counts["NUMERIC"] / total, 3),
        "vague": round(counts["VAGUE"] / total, 3),
        "offset": round(counts["OFFSET_BACKED"] / total, 3),
        "numeric_count": counts["NUMERIC"],
        "vague_count": counts["VAGUE"],
        "offset_count": counts["OFFSET_BACKED"],
        "total": total
    }

"""Small, deterministic parser for common Ghanaian construction briefs.

The parser intentionally avoids downloading a large NLP model at startup. Its
output is a concept-level specification and must be reviewed by a professional.
"""

from __future__ import annotations

import re
from typing import Any


_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _count(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except (ValueError, IndexError):
        return None


def _parse_area(text: str) -> float | None:
    pattern = (
        r"\b([\d,]+(?:\.\d+)?)\s*(?:"
        r"sqm|sq\.?\s*m|square\s*(?:metres?|meters?)|m(?:2|²)"
        r")(?=\s|[,.;!?)]|$)"
    )
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_budget(text: str) -> float | None:
    pattern = (
        r"(?:budget|under|maximum|limit|cost(?:ing)?(?:\s+of)?)\s*"
        r"(?:is|of|:|-)?\s*(?:ghs|gh[₵¢]|₵|¢)?\s*"
        r"([\d,]+(?:\.\d+)?)\s*(k|m)?\s*(?:ghs|cedis?)?"
    )
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    amount = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").lower()
    if suffix == "k":
        amount *= 1_000
    elif suffix == "m":
        amount *= 1_000_000
    return amount


def parse_construction_request(text: str) -> dict[str, Any]:
    """Parse a short natural-language brief into a conservative concept spec."""
    clean_text = " ".join((text or "").split())[:4000]
    lowered = clean_text.lower()

    spec: dict[str, Any] = {
        "building_type": "residential",
        "floors": 1,
        "bedrooms": 2,
        "bathrooms": 1,
        "rooms_total": 5,
        "area_sqm": 100.0,
        "location": "Accra",
        "material": "cement_block",
        "roof_type": "iron_sheet",
        "foundation_type": "pad",
        "special_features": [],
        "budget_constraint": None,
        "project_typology": "single_dwelling",
        "concept_style": "",
        "raw_text": clean_text,
    }

    if any(word in lowered for word in ("shop", "commercial", "office", "warehouse", "hotel", "mall", "retail")):
        spec["building_type"] = "commercial"
    elif any(word in lowered for word in ("church", "mosque", "temple", "school", "hospital", "clinic")):
        spec["building_type"] = "institutional"
    if any(term in lowered for term in ("apartment", "apartments", "flat", "flats", "multi-family", "multifamily")):
        # Preserve the residential screening category while exposing apartment
        # floor plates to the concept generator; this is not a occupancy/code classification.
        spec["project_typology"] = "apartment"
    if "colonial" in lowered:
        spec["concept_style"] = "colonial-inspired"

    bedroom_count = _count(lowered, r"\b(\d+)\s*[- ]*\s*(?:bedrooms?|beds?|br)\b")
    bathroom_count = _count(lowered, r"\b(\d+)\s*[- ]*\s*(?:bathrooms?|baths?|wcs?)\b")
    explicit_rooms = _count(lowered, r"\b(\d+)\s*(?:total\s+)?rooms?\b")

    if bedroom_count is not None:
        spec["bedrooms"] = min(max(bedroom_count, 0), 40)
    if bathroom_count is not None:
        spec["bathrooms"] = min(max(bathroom_count, 0), 40)

    floor_count = _count(lowered, r"\b(\d+)\s*[- ]*\s*(?:storeys?|stories|floors?|levels?)\b")
    if floor_count is None:
        for word, value in _NUMBER_WORDS.items():
            if re.search(rf"\b{word}\s*[- ]*\s*(?:storeys?|stories|floors?|levels?)\b", lowered):
                floor_count = value
                break
    if floor_count is not None:
        spec["floors"] = min(max(floor_count, 1), 50)

    if explicit_rooms is not None:
        spec["rooms_total"] = min(max(explicit_rooms, 1), 60)
    elif bedroom_count is not None or bathroom_count is not None:
        # A simple allowance for a living room and kitchen.
        spec["rooms_total"] = spec["bedrooms"] + spec["bathrooms"] + 2

    area = _parse_area(lowered)
    if area is not None and area >= 20:
        spec["area_sqm"] = min(area, 100_000.0)
    elif area is None:
        spec["area_sqm"] = max(45.0, float(spec["rooms_total"] * 18))

    locations = [
        "Cape Coast", "Koforidua", "Bolgatanga", "Takoradi", "Kumasi", "Tamale",
        "Accra", "Tema", "Obuasi", "Aburi", "Aflao", "Sukuru", "Ho", "Wa",
    ]
    for location in locations:
        if location.lower() in lowered:
            spec["location"] = location
            break

    if any(word in lowered for word in ("laterite", "local stone", "rammed earth")):
        spec["material"] = "laterite"
    elif any(word in lowered for word in ("clay brick", "brick")):
        spec["material"] = "clay_brick"
    elif any(word in lowered for word in ("bamboo", "timber", "wood")):
        spec["material"] = "bamboo"
    elif any(word in lowered for word in ("block", "cement", "concrete")):
        spec["material"] = "cement_block"

    if any(word in lowered for word in ("tile roof", "roof tile", "clay tile", "concrete tile")):
        spec["roof_type"] = "concrete_tile"
    elif any(word in lowered for word in ("zinc", "aluminium", "aluminum", "metal roof")):
        spec["roof_type"] = "zinc_sheet"
    elif any(word in lowered for word in ("iron sheet", "steel sheet", "corrugated")):
        spec["roof_type"] = "iron_sheet"

    if "pile foundation" in lowered or "piled foundation" in lowered:
        spec["foundation_type"] = "pile"
    elif "strip foundation" in lowered:
        spec["foundation_type"] = "strip"
    elif "raft foundation" in lowered or "mat foundation" in lowered:
        spec["foundation_type"] = "raft"

    features: list[str] = []
    feature_rules = {
        "garage": ("garage",),
        "porch": ("porch",),
        "balcony": ("balcony",),
        "compound_wall": ("compound wall", "compound"),
        "water_source": ("borehole", "well"),
        "solar_power": ("solar",),
        "garden": ("garden",),
    }
    for feature, terms in feature_rules.items():
        if any(term in lowered for term in terms):
            features.append(feature)
    spec["special_features"] = features
    spec["budget_constraint"] = _parse_budget(lowered)

    return spec

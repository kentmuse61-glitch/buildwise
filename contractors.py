"""Location, budget and specialty matcher for vetted local directory data."""

from __future__ import annotations

import json
import os
from typing import Any


class ContractorMatcher:
    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = data_dir
        self.contractors = self._load()

    def _load(self) -> list[dict[str, Any]]:
        path = os.path.join(self.data_dir, "contractors_gh.json")
        try:
            with open(path, encoding="utf-8") as source:
                values = json.load(source)
            return values if isinstance(values, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def match(self, location: str, budget: float, building_type: str) -> list[dict[str, Any]]:
        matches = []
        wanted_location = location.strip().casefold()
        wanted_type = building_type.strip().casefold()
        for contractor in self.contractors:
            locations = contractor.get("locations", [])
            specialties = contractor.get("specialties", [])
            min_budget = float(contractor.get("min_budget_ghs", 0))
            max_budget = float(contractor.get("max_budget_ghs", float("inf")))
            location_match = any(wanted_location == str(item).casefold() for item in locations)
            budget_match = min_budget <= budget <= max_budget
            specialty_match = any(wanted_type == str(item).casefold() for item in specialties)
            if not (location_match and budget_match):
                continue
            score = float(contractor.get("rating", 0)) * 10 + (10 if specialty_match else 0)
            years = int(contractor.get("years_experience", 0))
            score += min(years, 20) / 4
            matches.append({
                **contractor,
                "_score": score,
                "_location_match": location_match,
                "_specialty_match": specialty_match,
            })
        matches.sort(key=lambda item: item["_score"], reverse=True)
        return matches[:5]

"""Concept-level checks only; this module is not a legal/code certification."""

from __future__ import annotations

import json
import os
from typing import Any


class ComplianceChecker:
    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = data_dir
        self.codes = self._load_codes()

    def _load_codes(self) -> dict[str, Any]:
        path = os.path.join(self.data_dir, "building_codes_gh.json")
        try:
            with open(path, encoding="utf-8") as source:
                data = json.load(source)
                return data if isinstance(data, dict) else self._default_codes()
        except (OSError, json.JSONDecodeError):
            return self._default_codes()

    @staticmethod
    def _default_codes() -> dict[str, Any]:
        return {
            "min_room_area_sqm": 9.0,
            "max_floors_residential": 4,
            "max_floors_commercial": 12,
            "max_floors_institutional": 6,
            "min_setback_front_m": 6.0,
            "min_setback_side_m": 3.0,
            "min_setback_rear_m": 4.5,
            "mandatory": ["fire_escape", "drainage", "septic_or_pit"],
        }

    def check(self, spec: dict[str, Any]) -> dict[str, Any]:
        issues: list[str] = []
        warnings: list[str] = []
        passes: list[str] = []
        codes = self.codes
        building_type = str(spec.get("building_type", "residential")).lower()
        floors = max(1, int(spec.get("floors", 1)))
        total_area = max(1.0, float(spec.get("area_sqm", 100.0)))
        bedrooms = max(0, int(spec.get("bedrooms", 2)))
        bathrooms = max(0, int(spec.get("bathrooms", 1)))
        room_count = max(1, bedrooms + bathrooms + 2)
        average_room_area = total_area / floors / room_count

        limit_key = {
            "residential": "max_floors_residential",
            "commercial": "max_floors_commercial",
            "institutional": "max_floors_institutional",
        }.get(building_type, "max_floors_residential")
        max_floors = int(codes.get(limit_key, 4))
        if floors > max_floors:
            issues.append(f"The concept has {floors} floors; the starter check is set to {max_floors} for {building_type}.")
        else:
            passes.append(f"Floor count ({floors}) is within the configured concept-check limit ({max_floors}).")

        minimum_room_area = float(codes.get("min_room_area_sqm", 9.0))
        if average_room_area < minimum_room_area:
            warnings.append(f"Estimated average room area ({average_room_area:.1f} m²) is below the configured {minimum_room_area:g} m² screening value.")
        else:
            passes.append(f"Estimated average room area ({average_room_area:.1f} m²) is above the configured screening value.")

        if floors <= 2:
            passes.append("Concept assumes a typical floor-to-ceiling height; confirm actual sections and ventilation with the design team.")
        else:
            warnings.append("Verify floor-to-ceiling heights, stairs, fire strategy and accessibility for every level.")

        for label, key in (("Front", "min_setback_front_m"), ("Side", "min_setback_side_m"), ("Rear", "min_setback_rear_m")):
            value = codes.get(key)
            if value is not None:
                warnings.append(f"Check the {label.lower()} setback ({float(value):g} m starter value) against the plot, zoning and local authority requirements.")

        features = set(spec.get("special_features", []))
        for required in codes.get("mandatory", []):
            normalized = str(required).lower()
            if normalized not in features:
                warnings.append(f"Confirm provision for {normalized.replace('_', ' ')} in the developed design.")

        warnings.append("This automated screen is not a permit review, structural calculation, professional design, or confirmation of current Ghanaian code compliance.")
        status = "Review required" if issues or warnings else "Preliminary checks passed"
        return {
            "status": status,
            "issues": issues,
            "warnings": warnings,
            "passes": passes,
            "code_reference": codes.get("code_reference", "User-configured concept checks; verify current requirements."),
            "location": spec.get("location", "Ghana"),
            "disclaimer": "For early planning only. Obtain current requirements and a review from licensed local professionals and the relevant authorities.",
        }

"""Bounded, review-first project data summaries.

These utilities provide original Buildwise workflows informed by seismic
visualization, photogrammetry-capture, IFC inventory and CAD review product
categories.  They do not parse third-party files or infer professional
engineering, survey, BIM-authoritative or construction conclusions.
"""

from __future__ import annotations

import math
from typing import Any


class ReviewTools:
    """Validate and summarize user-entered review metadata without file uploads."""

    @staticmethod
    def seismic_trace_summary(sample_rate_hz: float, acceleration_g: list[float], source_note: str) -> dict[str, Any]:
        """Return a display-safe waveform summary for a supplied acceleration trace.

        Input is deliberately limited to a small numeric trace.  It is not a
        geotechnical file parser and the result is never a design spectrum,
        ground classification, structural check, or foundation recommendation.
        """
        if not math.isfinite(sample_rate_hz) or not (0.1 <= sample_rate_hz <= 10_000):
            raise ValueError("Sample rate must be between 0.1 and 10,000 Hz")
        if not (8 <= len(acceleration_g) <= 4096):
            raise ValueError("Provide between 8 and 4,096 acceleration samples")
        if not all(math.isfinite(value) and -5.0 <= value <= 5.0 for value in acceleration_g):
            raise ValueError("Acceleration samples must be finite values between -5 g and 5 g")

        count = len(acceleration_g)
        peak = max(abs(value) for value in acceleration_g)
        rms = math.sqrt(sum(value * value for value in acceleration_g) / count)
        duration = count / sample_rate_hz
        # Keep the project record small while preserving an inspectable chart.
        chart_count = min(160, count)
        step = (count - 1) / max(chart_count - 1, 1)
        chart = [round(acceleration_g[min(count - 1, round(index * step))], 5) for index in range(chart_count)]
        return {
            "sample_rate_hz": round(sample_rate_hz, 4),
            "sample_count": count,
            "duration_seconds": round(duration, 4),
            "peak_absolute_acceleration_g": round(peak, 6),
            "rms_acceleration_g": round(rms, 6),
            "chart_acceleration_g": chart,
            "source_note": source_note.strip()[:240],
            "status": "User-supplied trace visualized; professional interpretation required",
            "disclaimer": (
                "This is a visual summary of values supplied by the user. It is not a seismic hazard result, "
                "site classification, structural analysis, code check, or foundation recommendation."
            ),
        }

    @staticmethod
    def capture_manifest_summary(
        image_count: int,
        control_points: int,
        overlap_percent: float,
        coverage_area_sqm: float | None,
        capture_note: str,
    ) -> dict[str, Any]:
        """Summarize declared field-capture metadata without accepting images."""
        if not (1 <= image_count <= 100_000):
            raise ValueError("Image count must be between 1 and 100,000")
        if not (0 <= control_points <= 10_000):
            raise ValueError("Control-point count must be between 0 and 10,000")
        if not math.isfinite(overlap_percent) or not (0 <= overlap_percent <= 100):
            raise ValueError("Overlap must be between 0% and 100%")
        if coverage_area_sqm is not None and (not math.isfinite(coverage_area_sqm) or not (0 < coverage_area_sqm <= 1_000_000)):
            raise ValueError("Coverage area must be a positive value up to 1,000,000 m²")
        quality = "insufficient metadata"
        if overlap_percent >= 75 and control_points >= 5:
            quality = "capture metadata indicates stronger review readiness"
        elif overlap_percent >= 60:
            quality = "capture metadata indicates partial review readiness"
        return {
            "image_count": image_count,
            "ground_control_points": control_points,
            "declared_overlap_percent": round(overlap_percent, 1),
            "declared_coverage_area_sqm": round(coverage_area_sqm, 2) if coverage_area_sqm is not None else None,
            "readiness": quality,
            "capture_note": capture_note.strip()[:500],
            "status": "Manifest recorded; images are not uploaded or reconstructed by Buildwise",
            "disclaimer": (
                "Declared capture metadata does not establish survey accuracy, ownership, consent, model scale, "
                "elevation, boundary position, or suitability for design/construction."
            ),
        }

    @staticmethod
    def ifc_manifest_summary(schema: str, filename: str, element_counts: dict[str, int], author_note: str) -> dict[str, Any]:
        """Record an owner-entered IFC inventory before future private IFC review."""
        allowed_schemas = {"IFC2X3", "IFC4", "IFC4X3", "UNKNOWN"}
        normalized_schema = schema.strip().upper()
        if normalized_schema not in allowed_schemas:
            raise ValueError("IFC schema must be IFC2X3, IFC4, IFC4X3, or UNKNOWN")
        clean_counts: dict[str, int] = {}
        for key, value in element_counts.items():
            name = str(key).strip()[:60]
            if not name:
                continue
            if not isinstance(value, int) or isinstance(value, bool) or not (0 <= value <= 10_000_000):
                raise ValueError("IFC element counts must be whole numbers between 0 and 10,000,000")
            clean_counts[name] = value
        if not clean_counts or len(clean_counts) > 80:
            raise ValueError("Provide between 1 and 80 IFC element categories")
        return {
            "schema": normalized_schema,
            "filename": filename.strip()[:160],
            "element_counts": clean_counts,
            "total_declared_elements": sum(clean_counts.values()),
            "author_note": author_note.strip()[:500],
            "status": "Owner-entered IFC manifest recorded; no IFC file was imported or rendered",
            "disclaimer": (
                "This inventory is declarative metadata, not an IFC parse, geometry validation, clash check, "
                "coordination model, or BIM-authoritative result."
            ),
        }

    @staticmethod
    def vector_inventory_summary(filename: str, unit: str, layer_counts: dict[str, int], closed_area_sqm: list[float], source_note: str) -> dict[str, Any]:
        """Summarize a human-confirmed vector inventory without accepting drawings."""
        normalized_unit = unit.strip().lower()
        if normalized_unit not in {"m", "mm", "ft", "unknown"}:
            raise ValueError("Vector unit must be m, mm, ft, or unknown")
        clean_layers: dict[str, int] = {}
        for key, value in layer_counts.items():
            name = str(key).strip()[:80]
            if not name:
                continue
            if not isinstance(value, int) or isinstance(value, bool) or not (0 <= value <= 10_000_000):
                raise ValueError("Layer counts must be whole numbers between 0 and 10,000,000")
            clean_layers[name] = value
        if not clean_layers or len(clean_layers) > 100:
            raise ValueError("Provide between 1 and 100 drawing layers")
        if not (0 <= len(closed_area_sqm) <= 500):
            raise ValueError("Provide up to 500 confirmed closed areas")
        if not all(math.isfinite(value) and 0 < value <= 1_000_000 for value in closed_area_sqm):
            raise ValueError("Closed areas must be finite positive values up to 1,000,000 m²")
        return {
            "filename": filename.strip()[:160],
            "declared_unit": normalized_unit,
            "layer_counts": clean_layers,
            "total_declared_entities": sum(clean_layers.values()),
            "confirmed_closed_area_sqm": round(sum(closed_area_sqm), 3),
            "confirmed_closed_area_count": len(closed_area_sqm),
            "source_note": source_note.strip()[:500],
            "status": "Human-confirmed vector inventory recorded; no drawing was uploaded or modified",
            "disclaimer": (
                "These values are manually declared review inputs, not an automated CAD extraction, calibrated measurement, "
                "drawing revision, professional quantity take-off, or construction instruction."
            ),
        }

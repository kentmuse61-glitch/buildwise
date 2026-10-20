"""Buildwise-owned, review-first concept directions for client briefing.

This module intentionally does not make legal, cultural, financial, resale,
permit, construction-feasibility or client-satisfaction predictions. It creates
transparent discussion prompts from a project brief so a client and appointed
professionals can compare early planning priorities.
"""

from __future__ import annotations

from typing import Any


class MarketDirectionBuilder:
    """Create deterministic Ghana-context, global-modern and balanced lenses."""

    _VALID_FOCUSES = {"ghana_context", "global_modern", "balanced"}

    def build(self, spec: dict[str, Any], selected_focus: str = "balanced") -> dict[str, Any]:
        """Return concept-direction cards without changing approval status or scope."""
        selected = selected_focus if selected_focus in self._VALID_FOCUSES else "balanced"
        features = {str(value).strip().lower() for value in spec.get("special_features", []) if isinstance(value, str)}
        location = str(spec.get("location") or "Ghana").strip()[:100] or "Ghana"
        floors = self._int(spec.get("floors"), 1, 1, 50)
        area = self._number(spec.get("area_sqm"), 100.0, 20.0, 1_000_000.0)
        has_solar = "solar_power" in features or "solar" in features
        has_balcony = "balcony" in features

        cards = [
            self._ghana_context_card(location, floors, area, has_solar, has_balcony),
            self._global_modern_card(location, floors, area, has_solar, has_balcony),
            self._balanced_card(location, floors, area, has_solar, has_balcony),
        ]
        for card in cards:
            card["selected"] = card["key"] == selected

        return {
            "schema_version": 1,
            "selected_focus": selected,
            "selected_label": next(card["label"] for card in cards if card["key"] == selected),
            "directions": cards,
            "method": (
                "Buildwise-owned concept briefing directions derived from declared project priorities. "
                "They are prompts for comparison, not ratings, market forecasts, cultural validation, professional advice or approval."
            ),
            "disclaimer": (
                "Compare these directions with the client, site information and qualified Ghana-based professionals. "
                "Confirm planning, code, climate, structure, services, costs, supply and authority requirements for the actual project."
            ),
        }

    @staticmethod
    def _ghana_context_card(location: str, floors: int, area: float, has_solar: bool, has_balcony: bool) -> dict[str, Any]:
        prompts = [
            "Review a shaded arrival or veranda threshold in relation to the actual site, road and outdoor-use priorities.",
            "Coordinate compound circulation, drainage routes, service access, storage and security requirements with the site team.",
            "Compare locally available wall, roof, glazing and finish options with current supplier quotations and professional specifications.",
        ]
        if has_solar:
            prompts.append("Reserve a coordinated roof and services discussion for the solar request; confirm orientation, shading, structure and electrical design.")
        if has_balcony:
            prompts.append("Review balcony privacy, drainage, waterproofing, guard design and structure with appointed professionals.")
        return {
            "key": "ghana_context",
            "label": "Ghana-context briefing",
            "tagline": "Site, climate, supply and living-pattern discussion prompts.",
            "brief_signals": [f"Location reference: {location}", f"{floors} level concept", f"{area:.0f} m² gross-floor-area input"],
            "priority_prompts": prompts,
            "professional_handoff": "Use the handoff brief to record site dimensions, road orientation, drainage concerns and local-authority information.",
            "not_claimed": "Not a Ghana Building Code determination, local-cost guarantee, cultural certification or construction method selection.",
        }

    @staticmethod
    def _global_modern_card(location: str, floors: int, area: float, has_solar: bool, has_balcony: bool) -> dict[str, Any]:
        prompts = [
            "Compare flexible shared-space, storage and work-from-home requirements with the household brief rather than assuming an open-plan solution.",
            "Discuss daylight, cross-ventilation, solar control and maintenance as climate-responsive design objectives for the actual site.",
            "Record digital, accessibility and future-adaptation priorities for the appointed design and engineering team to assess.",
        ]
        if has_solar:
            prompts.append("Treat the solar request as an early energy-planning prompt; it does not establish an equipment design or performance result.")
        if has_balcony:
            prompts.append("Compare the balcony request with safety, waterproofing, privacy, maintenance and structural review needs.")
        return {
            "key": "global_modern",
            "label": "Global-modern briefing",
            "tagline": "Contemporary flexibility, comfort and long-term adaptability prompts.",
            "brief_signals": [f"Location reference: {location}", f"{floors} level concept", f"{area:.0f} m² gross-floor-area input"],
            "priority_prompts": prompts,
            "professional_handoff": "Use the handoff brief to make performance, accessibility, technology and material-maintenance priorities explicit.",
            "not_claimed": "Not an international compliance screen, investment assessment, sustainability certification or smart-home specification.",
        }

    @staticmethod
    def _balanced_card(location: str, floors: int, area: float, has_solar: bool, has_balcony: bool) -> dict[str, Any]:
        prompts = [
            "Keep the client’s stated room programme, budget target and site constraints visible while comparing different spatial arrangements.",
            "Pair contemporary comfort goals with locally verified climate, construction sequencing, supply and maintenance considerations.",
            "Ask the professional team to resolve trade-offs among shading, airflow, drainage, privacy, storage, future change and cost after site review.",
        ]
        if has_solar:
            prompts.append("Include energy goals in the professional handoff, then verify loads, roof design, utility requirements and procurement choices.")
        if has_balcony:
            prompts.append("Use the balcony request as a review item rather than a pre-approved feature; resolve detailing and safety in the developed design.")
        return {
            "key": "balanced",
            "label": "Balanced briefing",
            "tagline": "A transparent comparison of local context and contemporary living priorities.",
            "brief_signals": [f"Location reference: {location}", f"{floors} level concept", f"{area:.0f} m² gross-floor-area input"],
            "priority_prompts": prompts,
            "professional_handoff": "Use the handoff brief to document priorities and unresolved trade-offs for the architect, engineer and quantity surveyor.",
            "not_claimed": "Not a recommendation of the best market, a resale forecast, client-satisfaction score or construction approval.",
        }

    @staticmethod
    def _int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            return min(max(int(value), minimum), maximum)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _number(value: Any, default: float, minimum: float, maximum: float) -> float:
        try:
            return min(max(float(value), minimum), maximum)
        except (TypeError, ValueError):
            return default

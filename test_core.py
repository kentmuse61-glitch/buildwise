import json
import os
import struct
import tempfile
import unittest
from datetime import date

from backend.compliance import ComplianceChecker
from backend.contractors import ContractorMatcher
from backend.model_3d import Model3DGenerator
from backend.nlp_engine import parse_construction_request
from backend.plan_generator import PlanGenerator
from backend.schedule_4d import Schedule4D


class ConstructionCoreTests(unittest.TestCase):
    def test_parser_extracts_common_ghana_brief(self):
        spec = parse_construction_request(
            "A 2-storey, 3-bedroom, 2-bathroom house in Kumasi, 220 sqm, budget 800k GHS, with a balcony and solar."
        )
        self.assertEqual(spec["floors"], 2)
        self.assertEqual(spec["bedrooms"], 3)
        self.assertEqual(spec["bathrooms"], 2)
        self.assertEqual(spec["location"], "Kumasi")
        self.assertEqual(spec["area_sqm"], 220.0)
        self.assertEqual(spec["budget_constraint"], 800000)
        self.assertIn("solar_power", spec["special_features"])

    def test_plan_svg_is_well_formed_and_escapes_user_text(self):
        generator = PlanGenerator()
        svg = generator.build_svg({
            "building_type": "residential <script>",
            "location": "Kumasi & Ghana",
            "floors": 1,
            "area_sqm": 120,
            "bedrooms": 3,
            "bathrooms": 2,
            "rooms_total": 7,
        })
        self.assertIn("&lt;Script&gt;", svg)
        self.assertIn("Kumasi &amp; Ghana", svg)
        self.assertTrue(svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"'))
        self.assertTrue(svg.rstrip().endswith("</svg>"))

    def test_ghana_focused_residential_template_is_explicitly_opt_in(self):
        generator = PlanGenerator()
        source = {
            "building_type": "residential",
            "floors": 1,
            "bedrooms": 3,
            "bathrooms": 2,
            "rooms_total": 7,
            "area_sqm": 140,
            "location": "Kumasi",
        }
        suggested = generator.prepare_residential_guidance(source, apply_bathroom_template=False)
        self.assertEqual(source["bathrooms"], 2)
        self.assertEqual(suggested["bathrooms"], 2)
        self.assertEqual(suggested["planning_guidance"]["suggested_bathrooms"], 3)
        applied = generator.prepare_residential_guidance(source, apply_bathroom_template=True)
        self.assertEqual(applied["bathrooms"], 3)
        self.assertTrue(applied["planning_guidance"]["applied_bathroom_template"])
        svg = generator.build_svg(applied)
        self.assertIn("Front veranda", svg)
        self.assertIn("Master bedroom", svg)
        self.assertIn("Visitor WC", svg)
        self.assertIn("not a code or permit approval", svg)

    def test_glb_header_and_length(self):
        with tempfile.TemporaryDirectory() as directory:
            generator = Model3DGenerator(directory)
            path = generator.generate_model({"floors": 2, "area_sqm": 180}, "test-1")
            with open(path, "rb") as source:
                data = source.read()
            magic, version, length = struct.unpack("<4sII", data[:12])
            self.assertEqual(magic, b"glTF")
            self.assertEqual(version, 2)
            self.assertEqual(length, len(data))
            json_length, json_type = struct.unpack("<II", data[12:20])
            self.assertEqual(json_type, 0x4E4F534A)
            document = json.loads(data[20:20 + json_length].decode("utf-8"))
            self.assertEqual(document["asset"]["version"], "2.0")
            self.assertGreaterEqual(len(document["nodes"]), 10)
            self.assertTrue(any(node.get("name") == "foundation_slab_concept" for node in document["nodes"]))
            self.assertTrue(any(node.get("name") == "roof_slab_concept" for node in document["nodes"]))
            self.assertTrue(any("COLOR_0" in mesh["primitives"][0]["attributes"] for mesh in document["meshes"]))
            self.assertEqual(document["asset"]["extras"]["buildwise"]["modelPurpose"], "early-planning concept massing only")
            self.assertTrue(all("target" in buffer_view for buffer_view in document["bufferViews"]))

    def test_schedule_has_phases_and_deterministic_start(self):
        with tempfile.TemporaryDirectory() as directory:
            schedule = Schedule4D(directory).build_schedule(
                {"floors": 2, "area_sqm": 180, "location": "Kumasi"},
                today=date(2026, 4, 20),
            )
        self.assertEqual(schedule["start_date"], "2026-04-27")
        self.assertEqual(schedule["floors"], 2)
        self.assertGreater(len(schedule["phases"]), 5)
        self.assertEqual(schedule["phases"][0]["start"], schedule["start_date"])
        self.assertGreater(schedule["total_duration_days"], 100)

    def test_compliance_is_explicitly_preliminary(self):
        checker = ComplianceChecker()
        result = checker.check({"building_type": "residential", "floors": 1, "area_sqm": 120, "bedrooms": 3, "bathrooms": 2, "location": "Kumasi", "special_features": []})
        self.assertIn(result["status"], {"Review required", "Preliminary checks passed"})
        self.assertTrue(result["disclaimer"])
        self.assertTrue(any("not a permit" in item.lower() for item in result["warnings"]))

    def test_contractor_directory_starts_empty(self):
        matcher = ContractorMatcher()
        self.assertEqual(matcher.match("Kumasi", 500000, "residential"), [])


if __name__ == "__main__":
    unittest.main()

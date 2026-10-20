import json
import os
import struct
import tempfile
import unittest
from datetime import date
from xml.etree import ElementTree

from backend.compliance import ComplianceChecker
from backend.contractors import ContractorMatcher
from backend.model_3d import Model3DGenerator
from backend.market_directions import MarketDirectionBuilder
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

    def test_parser_retains_an_exact_5000_word_brief(self):
        opening = "A three storey apartment in Kumasi with 540 sqm six bedrooms and six bathrooms requires careful concept review".split()
        closing = "Solar power and a balcony are essential final requirements".split()
        source_words = opening + (["context"] * (5_000 - len(opening) - len(closing))) + closing
        source = " ".join(source_words)
        self.assertEqual(len(source.split()), 5_000)
        self.assertLess(len(source), 75_000)
        spec = parse_construction_request(source)
        self.assertEqual(spec["raw_text"], source)
        self.assertEqual(spec["bedrooms"], 6)
        self.assertEqual(spec["bathrooms"], 6)
        self.assertIn("solar_power", spec["special_features"])
        self.assertIn("balcony", spec["special_features"])

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
        ElementTree.fromstring(svg)
        self.assertIn("OVERALL WIDTH", svg)
        self.assertIn("OVERALL DEPTH", svg)
        self.assertIn("NORTH", svg)
        self.assertIn('class="outer-wall"', svg)
        self.assertIn('class="door"', svg)
        self.assertIn('class="window"', svg)

    def test_technical_and_presentation_sheets_are_distinct_valid_concept_views(self):
        generator = PlanGenerator()
        spec = {
            "building_type": "residential", "location": "Kumasi", "floors": 2,
            "area_sqm": 190, "bedrooms": 3, "bathrooms": 2,
            "design_studio": {"active_floor": 2},
        }
        presentation = generator.build_svg(spec, visual_style="presentation")
        technical = generator.build_technical_svg(spec)
        ElementTree.fromstring(presentation)
        ElementTree.fromstring(technical)
        self.assertIn("PRESENTATION CONCEPT PLAN", presentation)
        self.assertIn("TECHNICAL CONCEPT PLAN", technical)
        self.assertIn("LEVEL 2 OF 2", technical)
        self.assertIn("ROOM SCHEDULE", technical)
        self.assertIn("BUILDWISE GH · CONCEPT SHEET", technical)
        self.assertIn('class="outer-wall"', technical)
        self.assertIn('fill="#ffffff"', technical)
        self.assertNotEqual(presentation, technical)

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

    def test_custom_design_studio_rooms_are_used_in_svg(self):
        generator = PlanGenerator()
        svg = generator.build_svg({
            "building_type": "residential",
            "location": "Kumasi",
            "floors": 2,
            "area_sqm": 180,
            "design_studio": {
                "active_floor": 2,
                "rooms": [
                    {"id": "studio", "label": "Studio & review", "room_type": "living", "floor": 2, "x": 0, "y": 0, "width": 6, "depth": 5},
                    {"id": "ground", "label": "Ground only", "room_type": "kitchen", "floor": 1, "x": 0, "y": 0, "width": 3, "depth": 3},
                ],
            },
        })
        self.assertIn("Studio &amp; review", svg)
        self.assertNotIn("Ground only", svg)
        self.assertIn("6.0 m × 5.0 m", svg)

    def test_three_storey_apartment_has_distinct_floor_plan_plates(self):
        spec = parse_construction_request(
            "A 3-storey colonial apartment in Kumasi with 6 bedrooms, 6 bathrooms and 540 sqm total floor area."
        )
        self.assertEqual(spec["floors"], 3)
        self.assertEqual(spec["project_typology"], "apartment")
        self.assertEqual(spec["concept_style"], "colonial-inspired")
        generator = PlanGenerator()
        floor_svgs = []
        floor_rooms = []
        for floor in (1, 2, 3):
            floor_spec = {**spec, "design_studio": {"active_floor": floor}}
            floor_rooms.append(generator.layout_rooms(floor_spec))
            svg = generator.build_svg(floor_spec)
            floor_svgs.append(svg)
            self.assertIn(f"LEVEL {floor} OF 3", svg)
            self.assertIn("Stair / vertical core", svg)
            self.assertIn("STYLE BRIEF: COLONIAL-INSPIRED", svg)
            ElementTree.fromstring(svg)
        self.assertEqual(sum(1 for rooms in floor_rooms for room in rooms if room["type"].startswith("bedroom_")), 6)
        self.assertEqual(sum(1 for rooms in floor_rooms for room in rooms if room["type"].startswith("bathroom_")), 6)
        self.assertIn("Entry lobby", floor_svgs[0])
        self.assertIn("Concept circulation", floor_svgs[1])
        self.assertIn("Balcony / outdoor space", floor_svgs[2])
        self.assertNotEqual(floor_svgs[0], floor_svgs[2])

    def test_flat_roof_brief_is_not_misclassified_as_an_apartment(self):
        spec = parse_construction_request("A 3-storey house in Kumasi with a flat roof and 180 sqm total floor area.")
        self.assertEqual(spec["project_typology"], "single_dwelling")

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
            self.assertGreater(len(document["nodes"]), 12)
            node_names = [node["name"] for node in document["nodes"]]
            self.assertIn("Floor 1 concept massing", node_names)
            self.assertIn("Floor 2 concept massing", node_names)
            self.assertIn("Recessed front entry", node_names)
            self.assertIn("Floor 1 front glazing panel 1", node_names)
            self.assertIn("Floor 1 east glazing panel 1", node_names)
            self.assertIn("Roof overhang", node_names)
            self.assertIn("Pitched concept roof", node_names)
            self.assertGreaterEqual(len(document["materials"]), 7)
            self.assertIn("Blue-grey glazing", [material["name"] for material in document["materials"]])
            self.assertEqual(document["asset"]["extras"]["buildwise"]["modelPurpose"], "early-planning concept massing only")
            self.assertTrue(all("target" in buffer_view for buffer_view in document["bufferViews"]))
            for mesh in document["meshes"]:
                primitive = mesh["primitives"][0]
                self.assertEqual(set(primitive["attributes"]), {"POSITION", "NORMAL"})
                position_count = document["accessors"][primitive["attributes"]["POSITION"]]["count"]
                normal_count = document["accessors"][primitive["attributes"]["NORMAL"]]["count"]
                index_accessor = document["accessors"][primitive["indices"]]
                self.assertEqual(index_accessor["componentType"], 5125)
                if mesh["name"] == "Pitched concept roof":
                    self.assertEqual((position_count, normal_count, index_accessor["count"]), (12, 12, 12))
                else:
                    self.assertEqual((position_count, normal_count, index_accessor["count"]), (24, 24, 36))

    def test_dollhouse_glb_is_valid_and_contains_room_aware_cues(self):
        with tempfile.TemporaryDirectory() as directory:
            generator = Model3DGenerator(directory)
            path = generator.generate_dollhouse_model({
                "floors": 2, "area_sqm": 180, "bedrooms": 3, "bathrooms": 2,
                "building_type": "residential", "location": "Kumasi",
            }, "dollhouse-test")
            with open(path, "rb") as source:
                data = source.read()
        magic, version, length = struct.unpack("<4sII", data[:12])
        self.assertEqual((magic, version, length), (b"glTF", 2, len(data)))
        json_length, json_type = struct.unpack("<II", data[12:20])
        self.assertEqual(json_type, 0x4E4F534A)
        document = json.loads(data[20:20 + json_length].decode("utf-8"))
        names = [node["name"] for node in document["nodes"]]
        self.assertIn("Floor 1 dollhouse slab", names)
        self.assertIn("Floor 2 dollhouse slab", names)
        self.assertTrue(any("bed cue" in name for name in names))
        self.assertTrue(any("rear room wall" in name for name in names))
        self.assertIn("Warm cutaway walls", [material["name"] for material in document["materials"]])
        self.assertIn("early-planning cutaway floor-programme visualization only", document["asset"]["extras"]["buildwise"]["modelPurpose"])
        self.assertTrue(all("target" in item for item in document["bufferViews"]))

    def test_box_geometry_uses_outward_normals_and_triangles(self):
        import numpy as np

        positions, normals, indices = Model3DGenerator._box_geometry(-2, 0, -3, 2, 3, 3)
        self.assertEqual(positions.dtype, np.float32)
        self.assertEqual(normals.dtype, np.float32)
        self.assertEqual(indices.dtype, np.uint32)
        for start in range(0, len(indices), 3):
            triangle = indices[start:start + 3]
            cross = np.cross(positions[triangle[1]] - positions[triangle[0]], positions[triangle[2]] - positions[triangle[0]])
            self.assertGreater(float(np.dot(cross, normals[triangle[0]])), 0.0)

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

    def test_market_directions_are_review_first_and_feature_aware(self):
        directions = MarketDirectionBuilder().build({
            "location": "Kumasi", "floors": 2, "area_sqm": 180,
            "special_features": ["solar_power", "balcony"],
        }, "ghana_context")
        self.assertEqual(directions["selected_focus"], "ghana_context")
        self.assertEqual(len(directions["directions"]), 3)
        selected = next(card for card in directions["directions"] if card["selected"])
        self.assertEqual(selected["key"], "ghana_context")
        prompt_text = " ".join(selected["priority_prompts"]).lower()
        self.assertIn("solar", prompt_text)
        self.assertIn("balcony", prompt_text)
        self.assertIn("not a ghana building code", selected["not_claimed"].lower())
        self.assertIn("not ratings", directions["method"].lower())

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

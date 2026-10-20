"""Authenticated API integration tests (run with requirements-dev.txt)."""

import os
import tempfile
import unittest
import uuid
from pathlib import Path


_TEST_DIR = Path(tempfile.mkdtemp(prefix="buildwise-api-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR / 'api.db'}"
os.environ["SECRET_KEY"] = "test-only-secret-not-for-production"

from fastapi.testclient import TestClient
from backend.main import app


class ProjectApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.username = f"tester_{uuid.uuid4().hex[:8]}"
        self.password = "Testing-pass-2026"
        register = self.client.post("/api/auth/register", json={
            "username": self.username,
            "password": self.password,
            "email": f"{self.username}@example.com",
        })
        self.assertEqual(register.status_code, 201, register.text)
        login = self.client.post("/api/auth/login", json={"username": self.username, "password": self.password})
        self.assertEqual(login.status_code, 200, login.text)
        self.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def tearDown(self):
        self.client.close()

    def test_generate_named_project_export_and_delete(self):
        response = self.client.post("/api/project/generate", headers=self.headers, json={
            "name": "Adum Family Home",
            "description": "A 3-bedroom, 2-bathroom bungalow in Kumasi, 160 sqm with a porch.",
            "location": "Kumasi",
            "budget": 500000,
            "apply_bathroom_template": True,
        })
        self.assertEqual(response.status_code, 200, response.text)
        project = response.json()
        self.assertEqual(project["name"], "Adum Family Home")
        self.assertEqual(project["spec"]["bathrooms"], 3)
        self.assertTrue(project["spec"]["planning_guidance"]["applied_bathroom_template"])

        csv_response = self.client.get(f"/api/projects/{project['id']}/artifacts/cost.csv", headers=self.headers)
        self.assertEqual(csv_response.status_code, 200, csv_response.text)
        self.assertIn("Adum Family Home", csv_response.text)
        self.assertIn("Indicative total", csv_response.text)
        self.assertTrue(csv_response.headers["content-type"].startswith("text/csv"))

        model_response = self.client.get(f"/api/projects/{project['id']}/artifacts/model.glb", headers=self.headers)
        self.assertEqual(model_response.status_code, 200, model_response.text)
        self.assertTrue(model_response.headers["content-type"].startswith("model/gltf-binary"))
        self.assertEqual(model_response.content[:4], b"glTF")
        self.assertEqual(self.client.get(f"/api/projects/{project['id']}/artifacts/model.glb").status_code, 401)

        deleted = self.client.delete(f"/api/projects/{project['id']}", headers=self.headers)
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get(f"/api/projects/{project['id']}", headers=self.headers).status_code, 404)

    def test_review_manifests_provide_bounded_repository_informed_workflows(self):
        generated = self.client.post("/api/project/generate", headers=self.headers, json={
            "description": "A 2-bedroom home in Kumasi with 120 sqm total floor area.",
        })
        self.assertEqual(generated.status_code, 200, generated.text)
        project_id = generated.json()["id"]

        seismic = self.client.put(f"/api/projects/{project_id}/site-review/seismic-trace", headers=self.headers, json={
            "sample_rate_hz": 100,
            "acceleration_g": [0, 0.02, -0.03, 0.01, 0.04, -0.02, 0, 0.01],
            "source_note": "Professionally supplied illustrative trace",
        })
        self.assertEqual(seismic.status_code, 200, seismic.text)
        self.assertEqual(seismic.json()["review"]["sample_count"], 8)
        self.assertGreater(seismic.json()["review"]["peak_absolute_acceleration_g"], 0)

        capture = self.client.put(f"/api/projects/{project_id}/site-review/capture-manifest", headers=self.headers, json={
            "image_count": 32, "ground_control_points": 6, "overlap_percent": 78, "coverage_area_sqm": 400,
        })
        self.assertEqual(capture.status_code, 200, capture.text)
        self.assertIn("stronger", capture.json()["review"]["readiness"])

        ifc = self.client.put(f"/api/projects/{project_id}/bim/ifc-manifest", headers=self.headers, json={
            "schema": "IFC4", "filename": "owner-model.ifc", "element_counts": {"IfcWall": 20, "IfcDoor": 8},
        })
        self.assertEqual(ifc.status_code, 200, ifc.text)
        self.assertEqual(ifc.json()["review"]["total_declared_elements"], 28)

        vector = self.client.put(f"/api/projects/{project_id}/drawing-review/vector-inventory", headers=self.headers, json={
            "filename": "owner-plan.dxf", "unit": "m", "layer_counts": {"Walls": 12, "Openings": 4}, "closed_area_sqm": [30.5, 20.0],
        })
        self.assertEqual(vector.status_code, 200, vector.text)
        self.assertEqual(vector.json()["review"]["confirmed_closed_area_sqm"], 50.5)

        workbench = self.client.get(f"/api/projects/{project_id}/workbench", headers=self.headers)
        self.assertEqual(workbench.status_code, 200, workbench.text)
        self.assertEqual(workbench.json()["bim_interoperability"]["ifc_manifest"]["schema"], "IFC4")
        self.assertEqual(workbench.json()["drawing_review"]["vector_inventory"]["filename"], "owner-plan.dxf")
        self.assertIn("User-supplied trace", workbench.json()["site_and_engineering"]["seismic_visualization_status"])

    def test_design_workbench_delivery_and_authenticated_debug_artifacts(self):
        generated = self.client.post("/api/project/generate", headers=self.headers, json={
            "description": "A 2-storey, 3-bedroom home in Kumasi with 180 sqm total floor area and solar power.",
            "location": "Kumasi",
        })
        self.assertEqual(generated.status_code, 200, generated.text)
        project_id = generated.json()["id"]

        workbench = self.client.get(f"/api/projects/{project_id}/workbench", headers=self.headers)
        self.assertEqual(workbench.status_code, 200, workbench.text)
        self.assertIn("quantity_takeoff", workbench.json())
        self.assertIn("energy_planning", workbench.json())
        self.assertIn("block_modules", workbench.json())
        self.assertFalse(workbench.json()["design_studio"]["uses_custom_layout"])

        design = self.client.put(f"/api/projects/{project_id}/design-studio", headers=self.headers, json={
            "variant_name": "Courtyard test",
            "active_floor": 1,
            "rooms": [
                {"id": "living-1", "label": "Living", "room_type": "living", "floor": 1, "x": 0, "y": 0, "width": 6, "depth": 5},
                {"id": "kitchen-1", "label": "Kitchen", "room_type": "kitchen", "floor": 1, "x": 6, "y": 0, "width": 3.5, "depth": 3},
            ],
        })
        self.assertEqual(design.status_code, 200, design.text)
        self.assertTrue(design.json()["workbench"]["design_studio"]["uses_custom_layout"])
        plan = self.client.get(f"/api/projects/{project_id}/artifacts/plan.svg", headers=self.headers)
        self.assertIn("Living", plan.text)
        self.assertIn("Kitchen", plan.text)

        progress = self.client.put(f"/api/projects/{project_id}/delivery/progress", headers=self.headers, json={
            "phase_key": "site-preparation", "progress_percent": 35, "status": "In progress", "note": "Brief review started",
        })
        self.assertEqual(progress.status_code, 200, progress.text)
        self.assertEqual(progress.json()["workbench"]["delivery_tracking"]["phases"][0]["progress_percent"], 35)

        unauthenticated_debug = self.client.post("/api/debug/generate-test")
        self.assertEqual(unauthenticated_debug.status_code, 401)
        debug = self.client.post("/api/debug/generate-test", headers=self.headers)
        self.assertEqual(debug.status_code, 200, debug.text)
        payload = debug.json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(all(item["exists"] and item["bytes"] > 0 for item in payload["files"].values()))
        debug_model = self.client.get(payload["artifact_urls"]["model"], headers=self.headers)
        self.assertEqual(debug_model.status_code, 200)
        self.assertEqual(debug_model.content[:4], b"glTF")

    def test_public_concepts_are_ephemeral_and_do_not_need_login(self):
        public = self.client.post("/api/public/project/generate", json={
            "name": "Guest concept",
            "description": "A 2-bedroom solar home in Kumasi with 120 sqm total floor area.",
            "location": "Kumasi",
        })
        self.assertEqual(public.status_code, 200, public.text)
        concept = public.json()
        self.assertTrue(concept["is_public"])
        self.assertEqual(concept["status"], "temporary-public-concept")
        self.assertIn("expire", concept["public_note"])
        self.assertIn("quantity_takeoff", concept["workbench"])
        self.assertEqual(concept["market_directions"]["selected_focus"], "balanced")
        self.assertEqual(len(concept["market_directions"]["directions"]), 3)

        plan = self.client.get(concept["plan_url"])
        self.assertEqual(plan.status_code, 200, plan.text)
        self.assertTrue(plan.headers["content-type"].startswith("image/svg+xml"))
        self.assertEqual(plan.headers["cache-control"], "no-store")
        model = self.client.get(concept["model_3d_url"])
        self.assertEqual(model.status_code, 200, model.text)
        self.assertEqual(model.content[:4], b"glTF")
        schedule = self.client.get(concept["schedule_url"])
        self.assertEqual(schedule.status_code, 200, schedule.text)
        self.assertIn("phases", schedule.json())
        self.assertEqual(self.client.get("/api/public/artifacts/not-a-token/model.glb").status_code, 404)

    def test_public_three_storey_apartment_serves_each_floor_plan(self):
        public = self.client.post("/api/public/project/generate", json={
            "description": "A 3-storey colonial apartment in Kumasi with 6 bedrooms, 6 bathrooms and 540 sqm.",
            "location": "Kumasi",
        })
        self.assertEqual(public.status_code, 200, public.text)
        concept = public.json()
        self.assertEqual(concept["spec"]["project_typology"], "apartment")
        self.assertEqual(len(concept["floor_plan_urls"]), 3)
        first = self.client.get(concept["floor_plan_urls"][0])
        third = self.client.get(concept["floor_plan_urls"][2])
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(third.status_code, 200, third.text)
        self.assertIn("LEVEL 1 OF 3", first.text)
        self.assertIn("LEVEL 3 OF 3", third.text)
        self.assertIn("Entry lobby", first.text)
        self.assertIn("Balcony / outdoor space", third.text)
        self.assertIn("STYLE BRIEF: COLONIAL-INSPIRED", third.text)
        self.assertNotEqual(first.text, third.text)
        self.assertEqual(self.client.get(concept["floor_plan_urls"][2].replace("plan-floor-3.svg", "plan-floor-4.svg")).status_code, 404)

    def test_design_studio_keeps_custom_layouts_per_floor(self):
        generated = self.client.post("/api/project/generate", headers=self.headers, json={
            "description": "A 3-storey, 3-bedroom building in Kumasi with 270 sqm total floor area.",
        })
        self.assertEqual(generated.status_code, 200, generated.text)
        project_id = generated.json()["id"]
        level_one = self.client.put(f"/api/projects/{project_id}/design-studio", headers=self.headers, json={
            "variant_name": "Three-level study", "active_floor": 1,
            "rooms": [{"id": "l1-living", "label": "Level one living", "room_type": "living", "floor": 1, "x": 0, "y": 0, "width": 6, "depth": 5}],
        })
        self.assertEqual(level_one.status_code, 200, level_one.text)
        level_two = self.client.put(f"/api/projects/{project_id}/design-studio", headers=self.headers, json={
            "variant_name": "Three-level study", "active_floor": 2,
            "rooms": [{"id": "l2-studio", "label": "Level two studio", "room_type": "room", "floor": 2, "x": 0, "y": 0, "width": 5, "depth": 4}],
        })
        self.assertEqual(level_two.status_code, 200, level_two.text)
        first = self.client.get(f"/api/projects/{project_id}/workbench?floor=1", headers=self.headers)
        second = self.client.get(f"/api/projects/{project_id}/workbench?floor=2", headers=self.headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["design_studio"]["rooms"][0]["label"], "Level one living")
        self.assertEqual(second.json()["design_studio"]["rooms"][0]["label"], "Level two studio")
        second_plan = self.client.get(f"/api/projects/{project_id}/artifacts/plan.svg?floor=2", headers=self.headers)
        self.assertEqual(second_plan.status_code, 200, second_plan.text)
        self.assertIn("Level two studio", second_plan.text)

    def test_public_generation_processes_an_exact_5000_word_brief(self):
        opening = "A three storey apartment in Kumasi with 540 sqm six bedrooms and six bathrooms needs a clear concept brief".split()
        closing = "Solar power and a balcony are essential final requirements".split()
        description_words = opening + (["planning"] * (5_000 - len(opening) - len(closing))) + closing
        description = " ".join(description_words)
        self.assertEqual(len(description.split()), 5_000)
        response = self.client.post("/api/public/project/generate", json={"description": description, "location": "Kumasi"})
        self.assertEqual(response.status_code, 200, response.text)
        concept = response.json()
        self.assertEqual(concept["description"], description)
        self.assertEqual(concept["spec"]["raw_text"], description)
        self.assertEqual(concept["spec"]["bedrooms"], 6)
        self.assertEqual(concept["spec"]["bathrooms"], 6)
        self.assertIn("solar_power", concept["spec"]["special_features"])
        self.assertIn("balcony", concept["spec"]["special_features"])

    def test_market_direction_endpoint_is_bounded_and_non_persistent(self):
        response = self.client.post("/api/v2/generate/market-variants", json={
            "description": "A two-storey, 3-bedroom family home in Kumasi with solar power and a balcony.",
            "location": "Kumasi",
            "target_market": "international",
        })
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "concept-directions-ready")
        self.assertEqual(payload["market_directions"]["selected_focus"], "global_modern")
        self.assertEqual(len(payload["market_directions"]["directions"]), 3)
        selected = next(card for card in payload["market_directions"]["directions"] if card["selected"])
        self.assertIn("not an international compliance", selected["not_claimed"].lower())
        self.assertIn("no plan", payload["note"].lower())

    def test_security_headers_are_present(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["referrer-policy"], "strict-origin-when-cross-origin")

    def test_professional_handoff_artifacts_are_private_and_escaped(self):
        response = self.client.post("/api/project/generate", headers=self.headers, json={
            "description": "A 3-bedroom, 2-bathroom bungalow in Kumasi with 145 sqm total floor area.",
            "location": "Kumasi",
            "handoff": {
                "site_width_m": 30,
                "site_depth_m": 40,
                "building_footprint_sqm": 120,
                "road_orientation": "North",
                "local_authority": "Kumasi Metropolitan Assembly",
                "planning_priorities": "Daylight and drainage <review before issue>",
            },
        })
        self.assertEqual(response.status_code, 200, response.text)
        project_id = response.json()["id"]
        handoff_json = self.client.get(f"/api/projects/{project_id}/artifacts/handoff.json", headers=self.headers)
        self.assertEqual(handoff_json.status_code, 200, handoff_json.text)
        self.assertEqual(handoff_json.json()["site_and_programme"]["site_width_m"], 30)
        self.assertIn("not a site survey", handoff_json.json()["disclaimer"].lower())
        handoff_html = self.client.get(f"/api/projects/{project_id}/artifacts/handoff.html", headers=self.headers)
        self.assertEqual(handoff_html.status_code, 200, handoff_html.text)
        self.assertIn("PROFESSIONAL HANDOFF PACK", handoff_html.text)
        self.assertIn("&lt;review before issue&gt;", handoff_html.text)
        self.assertNotIn("<review before issue>", handoff_html.text)
        self.assertEqual(self.client.get(f"/api/projects/{project_id}/artifacts/handoff.json").status_code, 401)

    def test_users_cannot_read_each_others_projects(self):
        response = self.client.post("/api/project/generate", headers=self.headers, json={
            "description": "A small 2-bedroom house in Kumasi with 100 sqm total floor area.",
        })
        self.assertEqual(response.status_code, 200, response.text)
        project_id = response.json()["id"]

        stranger = f"other_{uuid.uuid4().hex[:8]}"
        self.client.post("/api/auth/register", json={
            "username": stranger,
            "password": self.password,
            "email": f"{stranger}@example.com",
        })
        stranger_login = self.client.post("/api/auth/login", json={"username": stranger, "password": self.password})
        stranger_headers = {"Authorization": f"Bearer {stranger_login.json()['access_token']}"}
        self.assertEqual(self.client.get(f"/api/projects/{project_id}", headers=stranger_headers).status_code, 404)


if __name__ == "__main__":
    unittest.main()

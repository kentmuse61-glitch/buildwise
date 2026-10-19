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

        deleted = self.client.delete(f"/api/projects/{project['id']}", headers=self.headers)
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get(f"/api/projects/{project['id']}", headers=self.headers).status_code, 404)

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

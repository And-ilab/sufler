"""Tests for OpenAPI schema endpoint and Postman export."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sufler.settings")

import django  # noqa: E402

django.setup()

from django.test import Client, SimpleTestCase  # noqa: E402

from api_docs.export_postman import (  # noqa: E402
    export_postman_collection,
    openapi_to_postman,
)
from api_docs.openapi_v1 import build_openapi_v1  # noqa: E402


class OpenApiSchemaTest(SimpleTestCase):
    def test_schema_endpoint_lists_v1_integrator_paths(self):
        client = Client()
        response = client.get("/api/schema/", HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertTrue(str(schema.get("openapi", "")).startswith("3."))
        paths = schema.get("paths") or {}
        self.assertIn("/api/v1/assistant/chat", paths)
        self.assertIn("/api/v1/sufler/suggest", paths)
        self.assertIn("/api/v1/knowledge/events", paths)
        self.assertIn("post", paths["/api/v1/sufler/suggest"])
        self.assertIn("post", paths["/api/v1/assistant/chat"])
        self.assertIn("post", paths["/api/v1/knowledge/events"])

    def test_swagger_ui_available_when_debug(self):
        client = Client()
        response = client.get("/api/docs/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"swagger", response.content.lower())


class PostmanExportTest(unittest.TestCase):
    def test_postman_collection_covers_three_api_groups(self):
        collection = openapi_to_postman(build_openapi_v1())
        folder_names = {item["name"] for item in collection["item"]}
        self.assertEqual(folder_names, {"assistant", "sufler", "ingest"})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "postman_collection.json"
            export_postman_collection(out)
            loaded = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("v2.1.0", loaded["info"]["schema"])


if __name__ == "__main__":
    unittest.main()

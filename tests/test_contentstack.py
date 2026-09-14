import copy
import io
import json
import os
import tempfile
import unittest
import warnings
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

warnings.filterwarnings("ignore", message=r"urllib3 v2 only supports OpenSSL.*")

import requests

from ingestion_common.contentstack import (
    preflight_schema_check,
    publish_entry,
    upload_entry,
)
from ingestion_common import schema_tools


class FakeResponse:
    def __init__(self, status_code, data=None, text=None):
        self.status_code = status_code
        self._data = data
        self.text = text if text is not None else json.dumps(data or {})

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


class ContentstackTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "api": {"base_url": "https://content.example.test/"},
            "contentstack": {
                "content_type_uid": "asset_page",
                "default_locale": "en",
            },
        }

    def write_entry(self, directory, title="Semantic Layer", warnings=None):
        path = Path(directory) / "contentstack_entry.json"
        payload = {"entry": {"title": title, "url": "/semantic-layer"}}
        if warnings is not None:
            payload["_mapping_warnings"] = warnings
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_dry_run_preserves_output_and_skips_authentication_and_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry_path = self.write_entry(tmp, warnings=["Review the summary"])
            stdout = io.StringIO()
            with (
                patch.dict(os.environ, {}, clear=True),
                patch("ingestion_common.contentstack.requests.get") as fake_get,
                patch("ingestion_common.contentstack.requests.post") as fake_post,
                redirect_stdout(stdout),
            ):
                result = upload_entry(
                    entry_path,
                    config=self.config,
                    dry_run=True,
                    project_root=Path(tmp),
                )

            fake_get.assert_not_called()
            fake_post.assert_not_called()

        self.assertEqual(
            "\n⚠  1 mapping warning(s) from pipeline:\n"
            "   • Review the summary\n"
            "\n[Dry run] Would POST to: https://content.example.test/entries/asset_page\n"
            "[Dry run] Entry title: Semantic Layer\n"
            "[Dry run] Entry fields: title, url\n",
            stdout.getvalue(),
        )
        self.assertEqual(
            {"entry_uid": None, "published": False, "dry_run": True}, result
        )

    def test_preflight_reports_unknown_fields_from_live_schema(self):
        response = FakeResponse(
            200,
            {"content_type": {"schema": [{"uid": "title"}, {"uid": "url"}]}},
        )
        stdout = io.StringIO()
        with (
            patch("ingestion_common.contentstack.requests.get", return_value=response),
            redirect_stdout(stdout),
        ):
            preflight_schema_check(
                "https://content.example.test", "asset_page", {"title", "rogue"}, {"x": "y"}
            )

        self.assertEqual("  ⚠ Fields in payload not in schema: rogue\n", stdout.getvalue())

    def test_preflight_skips_request_errors_without_aborting_upload(self):
        stdout = io.StringIO()
        with (
            patch(
                "ingestion_common.contentstack.requests.get",
                side_effect=requests.RequestException("offline"),
            ),
            redirect_stdout(stdout),
        ):
            preflight_schema_check(
                "https://content.example.test", "asset_page", {"title"}, {"x": "y"}
            )

        self.assertEqual(
            "  ⚠ Schema check skipped (request error: offline)\n", stdout.getvalue()
        )

    def test_versioned_upload_retries_title_collision_normalizes_legacy_prefix_and_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry_path = self.write_entry(tmp, title="v7 -- Semantic Layer (v2 - fixed)")
            (Path(tmp) / ".env").write_text(
                "MSTR_API_KEY=secret\n", encoding="utf-8"
            )
            posted = []
            responses = iter(
                [
                    FakeResponse(422, {"errors": {"title": ["is not unique"]}}),
                    FakeResponse(
                        201,
                        {"entry": {"uid": "blt123", "title": "v2 | Semantic Layer"}},
                    ),
                ]
            )

            def fake_post(url, **kwargs):
                posted.append((url, copy.deepcopy(kwargs)))
                return next(responses)

            stdout = io.StringIO()
            with (
                patch.dict(os.environ, {}, clear=True),
                patch(
                    "ingestion_common.contentstack.requests.get",
                    return_value=FakeResponse(
                        200,
                        {"content_type": {"schema": [{"uid": "title"}, {"uid": "url"}]}},
                    ),
                ),
                patch("ingestion_common.contentstack.requests.post", side_effect=fake_post),
                redirect_stdout(stdout),
            ):
                result = upload_entry(
                    entry_path,
                    config=self.config,
                    project_root=Path(tmp),
                    title_versioning=True,
                    use_locale=False,
                )

            written_entry = json.loads(entry_path.read_text(encoding="utf-8"))
            response_file = json.loads(
                (Path(tmp) / "upload_response.json").read_text(encoding="utf-8")
            )

        self.assertEqual(
            ["v1 | Semantic Layer", "v2 | Semantic Layer"],
            [call[1]["json"]["entry"]["title"] for call in posted],
        )
        self.assertNotIn("params", posted[0][1])
        self.assertEqual("v2 | Semantic Layer", written_entry["entry"]["title"])
        self.assertEqual("blt123", response_file["entry"]["uid"])
        self.assertEqual("blt123", result["entry_uid"])
        self.assertIn("  v1 | Semantic Layer — title taken, trying next version...\n", stdout.getvalue())

    def test_versioned_upload_does_not_retry_non_uniqueness_title_validation_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry_path = self.write_entry(root)
            (root / ".env").write_text("MSTR_API_KEY=secret\n", encoding="utf-8")
            posted = []
            validation_response = FakeResponse(
                422,
                {
                    "error_message": "Validation failed",
                    "errors": {"title": ["is too long"]},
                },
            )

            def fake_post(url, **kwargs):
                posted.append((url, copy.deepcopy(kwargs)))
                return validation_response

            stdout = io.StringIO()
            with (
                patch.dict(os.environ, {}, clear=True),
                patch(
                    "ingestion_common.contentstack.requests.get",
                    return_value=FakeResponse(
                        200,
                        {"content_type": {"schema": [{"uid": "title"}, {"uid": "url"}]}},
                    ),
                ),
                patch("ingestion_common.contentstack.requests.post", side_effect=fake_post),
                redirect_stdout(stdout),
                self.assertRaisesRegex(
                    RuntimeError, "Entry creation failed with HTTP 422"
                ),
            ):
                upload_entry(
                    entry_path,
                    config=self.config,
                    project_root=root,
                    title_versioning=True,
                )

        self.assertEqual(1, len(posted))
        self.assertNotIn("title taken", stdout.getvalue())
        self.assertIn(
            'Response: {"error_message": "Validation failed", '
            '"errors": {"title": ["is too long"]}}',
            stdout.getvalue(),
        )

    def test_locale_upload_sends_locale_query_parameter_and_reports_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry_path = self.write_entry(tmp)
            (Path(tmp) / ".env").write_text(
                "MSTR_API_KEY=secret\n", encoding="utf-8"
            )
            posted = []

            def fake_post(url, **kwargs):
                posted.append((url, copy.deepcopy(kwargs)))
                return FakeResponse(
                    201, {"entry": {"uid": "blt456", "title": "Semantic Layer"}}
                )

            stdout = io.StringIO()
            with (
                patch.dict(os.environ, {}, clear=True),
                patch(
                    "ingestion_common.contentstack.requests.get",
                    return_value=FakeResponse(
                        200,
                        {"content_type": {"schema": [{"uid": "title"}, {"uid": "url"}]}},
                    ),
                ),
                patch("ingestion_common.contentstack.requests.post", side_effect=fake_post),
                redirect_stdout(stdout),
            ):
                upload_entry(
                    entry_path,
                    config=self.config,
                    project_root=Path(tmp),
                    content_type_uid="glossary_page",
                    use_locale=True,
                )

        self.assertEqual(
            "https://content.example.test/entries/glossary_page", posted[0][0]
        )
        self.assertEqual({"locale": "en"}, posted[0][1]["params"])
        self.assertIn(
            "Uploading to Contentstack (content type: glossary_page, locale: en)...",
            stdout.getvalue(),
        )

    def test_entry_uid_rejects_proxy_update_before_authentication_or_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry_path = self.write_entry(tmp)
            with (
                patch.dict(os.environ, {}, clear=True),
                patch("ingestion_common.contentstack.requests.get") as fake_get,
                patch("ingestion_common.contentstack.requests.post") as fake_post,
                self.assertRaisesRegex(RuntimeError, "proxy has no PUT endpoint") as raised,
            ):
                upload_entry(
                    entry_path,
                    config=self.config,
                    entry_uid="blt-existing",
                    project_root=Path(tmp),
                )

            fake_get.assert_not_called()
            fake_post.assert_not_called()

        self.assertIn(
            "Glossary Agent/docs/session_2026_06_16_mcp_v2_fixes.md", str(raised.exception)
        )

    def test_publish_entry_posts_to_publish_endpoint_and_returns_true(self):
        calls = []

        def fake_post(url, **kwargs):
            calls.append((url, copy.deepcopy(kwargs)))
            return FakeResponse(200, {"notice": "published"})

        stdout = io.StringIO()
        with (
            patch("ingestion_common.contentstack.requests.post", side_effect=fake_post),
            redirect_stdout(stdout),
        ):
            published = publish_entry(
                "https://content.example.test", "asset_page", "blt123", {"x": "y"}
            )

        self.assertTrue(published)
        self.assertEqual(
            [("https://content.example.test/entries/asset_page/blt123/publish", {"headers": {"x": "y"}, "timeout": 30})],
            calls,
        )
        self.assertEqual("  ✓ Published → https://stage.strategysoftware.com\n", stdout.getvalue())

    def test_publish_entry_reports_http_failure_and_returns_false(self):
        stdout = io.StringIO()
        with (
            patch(
                "ingestion_common.contentstack.requests.post",
                return_value=FakeResponse(500, {}, text="server error"),
            ),
            redirect_stdout(stdout),
        ):
            published = publish_entry(
                "https://content.example.test", "asset_page", "blt123", {"x": "y"}
            )

        self.assertFalse(published)
        self.assertEqual(
            "  ❌ Publish failed (HTTP 500): server error\n", stdout.getvalue()
        )


class SchemaToolsTests(unittest.TestCase):
    def test_main_routes_cli_request_and_output_through_explicit_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            outside = Path(tmp) / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "config.yaml").write_text(
                "api:\n  base_url: https://schema.example.test/\n", encoding="utf-8"
            )
            (root / ".env").write_text("MSTR_API_KEY=schema-key\n", encoding="utf-8")
            requests_seen = []

            def fake_get(url, **kwargs):
                requests_seen.append((url, copy.deepcopy(kwargs)))
                return FakeResponse(
                    200,
                    {
                        "entries": [
                            {
                                "uid": "blt-schema",
                                "title": "Schema sample",
                                "url": "/schema-sample",
                            }
                        ]
                    },
                )

            stdout = io.StringIO()
            with (
                patch.dict(os.environ, {}, clear=True),
                patch("ingestion_common.schema_tools.Path.cwd", return_value=outside),
                patch("ingestion_common.schema_tools.requests.get", side_effect=fake_get),
                redirect_stdout(stdout),
            ):
                result = schema_tools.main(
                    root, ["--entries", "asset_page", "--limit", "1"]
                )

            saved = json.loads(
                (root / "output" / "sample_entry_asset_page.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(0, result)
        self.assertEqual("blt-schema", saved["uid"])
        self.assertFalse((outside / "output").exists())
        self.assertEqual(
            [
                (
                    "https://schema.example.test/entries/asset_page?limit=1",
                    {
                        "headers": {
                            "x-mstr-key": "schema-key",
                            "Content-Type": "application/json",
                        },
                        "timeout": 15,
                    },
                )
            ],
            requests_seen,
        )
        self.assertIn("API base: https://schema.example.test\n", stdout.getvalue())
        self.assertIn(
            "✓ First entry saved to: output/sample_entry_asset_page.json\n",
            stdout.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()

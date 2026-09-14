import copy
import importlib.util
import inspect
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


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
UPLOADERS = {
    "blog": ("Blog Ingestion Agent", "blog_post", True),
    "whitepaper": ("Whitepaper Ingestion Agent", "page", False),
    "glossary": ("Glossary Agent", "asset_page", True),
}
SCHEMA_WRAPPERS = ("Whitepaper Ingestion Agent", "Glossary Agent")
EXPECTED_UPLOAD_SIGNATURE = (
    "(entry_file: str, config: dict = None, config_path: str = 'config.yaml', "
    "publish: bool = False, dry_run: bool = False, entry_uid: str = None) -> dict"
)


class FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data
        self.text = json.dumps(data)

    def json(self):
        return self._data


def load_script(project_name, script_name):
    path = REPOSITORY_ROOT / project_name / "scripts" / f"{script_name}.py"
    module_name = f"test_{project_name.lower().replace(' ', '_')}_{script_name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        spec.loader.exec_module(module)
    return module


class UploadWrapperTests(unittest.TestCase):
    def test_upload_callables_keep_the_orchestrator_signature(self):
        for pipeline, (project_name, _, _) in UPLOADERS.items():
            with self.subTest(pipeline=pipeline):
                module = load_script(project_name, "upload_to_contentstack")
                self.assertEqual(
                    EXPECTED_UPLOAD_SIGNATURE, str(inspect.signature(module.upload_entry))
                )

    def test_uploaders_apply_pipeline_policy_through_shared_behavior(self):
        for pipeline, (project_name, content_type, use_locale) in UPLOADERS.items():
            with self.subTest(pipeline=pipeline), tempfile.TemporaryDirectory() as tmp:
                entry_path = Path(tmp) / "contentstack_entry.json"
                entry_path.write_text(
                    json.dumps(
                        {"entry": {"title": "v7 -- Example title (v2)", "locale": "fr"}}
                    ),
                    encoding="utf-8",
                )
                module = load_script(project_name, "upload_to_contentstack")
                config = {
                    "api": {"base_url": "https://content.example.test/"},
                    "contentstack": {"content_type_uid": content_type},
                }
                posts = []

                def fake_post(url, **kwargs):
                    posts.append((url, copy.deepcopy(kwargs)))
                    return FakeResponse(
                        201,
                        {"entry": {"uid": "blt-wrapper", "title": "v1 | Example title"}},
                    )

                stdout = io.StringIO()
                with (
                    patch.dict(os.environ, {"MSTR_API_KEY": "secret"}, clear=True),
                    patch(
                        "ingestion_common.contentstack.requests.get",
                        return_value=FakeResponse(
                            200,
                            {"content_type": {"schema": [{"uid": "title"}, {"uid": "locale"}]}},
                        ),
                    ),
                    patch(
                        "ingestion_common.contentstack.requests.post",
                        side_effect=fake_post,
                    ),
                    redirect_stdout(stdout),
                ):
                    result = module.upload_entry(entry_path, config=config)

                self.assertEqual("blt-wrapper", result["entry_uid"])
                self.assertEqual(
                    "https://content.example.test/entries/" + content_type,
                    posts[0][0],
                )
                self.assertEqual(
                    "v1 | Example title", posts[0][1]["json"]["entry"]["title"]
                )
                if use_locale:
                    self.assertEqual({"locale": "fr"}, posts[0][1]["params"])
                else:
                    self.assertNotIn("params", posts[0][1])

    def test_entry_uid_is_rejected_before_any_http_request(self):
        config = {
            "api": {"base_url": "https://content.example.test"},
            "contentstack": {"content_type_uid": "test_type"},
        }
        for pipeline, (project_name, _, _) in UPLOADERS.items():
            with self.subTest(pipeline=pipeline), tempfile.TemporaryDirectory() as tmp:
                entry_path = Path(tmp) / "contentstack_entry.json"
                entry_path.write_text(
                    json.dumps({"entry": {"title": "Example"}}), encoding="utf-8"
                )
                module = load_script(project_name, "upload_to_contentstack")
                with (
                    patch("requests.get") as fake_get,
                    patch("requests.post") as fake_post,
                    patch("requests.put") as fake_put,
                    self.assertRaisesRegex(RuntimeError, "proxy has no PUT endpoint"),
                ):
                    module.upload_entry(
                        entry_path, config=config, entry_uid="blt-existing"
                    )

                fake_get.assert_not_called()
                fake_post.assert_not_called()
                fake_put.assert_not_called()

    def test_entry_uid_help_explains_that_updates_are_unsupported(self):
        for pipeline, (project_name, _, _) in UPLOADERS.items():
            with self.subTest(pipeline=pipeline):
                module = load_script(project_name, "upload_to_contentstack")
                stdout = io.StringIO()
                with redirect_stdout(stdout), self.assertRaises(SystemExit) as exit_context:
                    module.main(["--help"])

                self.assertEqual(0, exit_context.exception.code)
                help_text = " ".join(stdout.getvalue().split())
                self.assertIn("--entry-uid", help_text)
                self.assertIn("proxy does not support updates", help_text)
                self.assertIn("fails before network access", help_text)


class SchemaWrapperTests(unittest.TestCase):
    def test_schema_wrappers_expose_main_with_explicit_project_root(self):
        for project_name in SCHEMA_WRAPPERS:
            with self.subTest(project=project_name):
                module = load_script(project_name, "discover_schema")
                expected_root = REPOSITORY_ROOT / project_name
                self.assertEqual(expected_root, module.PROJECT_ROOT)
                stdout = io.StringIO()
                with (
                    patch.dict(os.environ, {"MSTR_API_KEY": "secret"}, clear=True),
                    patch(
                        "ingestion_common.schema_tools.requests.get",
                        return_value=FakeResponse(200, {"content_types": []}),
                    ) as fake_get,
                    redirect_stdout(stdout),
                ):
                    result = module.main(["--list-types"])

                self.assertEqual(0, result)
                fake_get.assert_called_once_with(
                    "https://api-stg.microstrategy.com/cs-software/content_types",
                    headers={
                        "x-mstr-key": "secret",
                        "Content-Type": "application/json",
                    },
                    timeout=15,
                )
                self.assertIn(
                    "API base: https://api-stg.microstrategy.com/cs-software\n",
                    stdout.getvalue(),
                )


if __name__ == "__main__":
    unittest.main()

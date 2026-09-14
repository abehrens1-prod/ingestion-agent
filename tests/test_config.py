import os
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

warnings.filterwarnings("ignore", message=r"urllib3 v2 only supports OpenSSL.*")

from ingestion_common.config import find_config, load_config
from ingestion_common.contentstack import build_headers


class ConfigTests(unittest.TestCase):
    def test_find_config_prefers_working_directory_then_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / "cwd"
            project = root / "project"
            cwd.mkdir()
            project.mkdir()
            (cwd / "config.yaml").write_text("source: cwd\n", encoding="utf-8")
            (project / "config.yaml").write_text("source: project\n", encoding="utf-8")

            with patch("ingestion_common.config.Path.cwd", return_value=cwd):
                found = find_config(project_root=project)

            self.assertEqual(cwd / "config.yaml", found)

    def test_find_config_uses_explicit_project_root_outside_project_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            project = root / "project"
            outside.mkdir()
            project.mkdir()
            expected = project / "custom.yaml"
            expected.write_text("answer: 42\n", encoding="utf-8")

            with patch("ingestion_common.config.Path.cwd", return_value=outside):
                found = find_config("custom.yaml", project_root=project)

            self.assertEqual(expected, found)

    def test_load_config_parses_yaml_from_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            config_path.write_text("api:\n  base_url: https://example.test/\n", encoding="utf-8")

            loaded = load_config(config_path)

            self.assertEqual({"api": {"base_url": "https://example.test/"}}, loaded)

    def test_find_config_names_missing_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = "missing.yaml"
            with (
                patch("ingestion_common.config.Path.cwd", return_value=Path(tmp)),
                self.assertRaisesRegex(FileNotFoundError, "Config not found: missing.yaml"),
            ):
                find_config(missing, project_root=Path(tmp) / "project")


class HeaderTests(unittest.TestCase):
    def test_build_headers_loads_api_key_from_explicit_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".env").write_text("MSTR_API_KEY=from-project\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                headers = build_headers(project_root=project)

            self.assertEqual(
                {"x-mstr-key": "from-project", "Content-Type": "application/json"},
                headers,
            )

    def test_build_headers_explains_missing_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.dict(os.environ, {}, clear=True),
                self.assertRaisesRegex(ValueError, "MSTR_API_KEY is not set"),
            ):
                build_headers(project_root=Path(tmp))


if __name__ == "__main__":
    unittest.main()

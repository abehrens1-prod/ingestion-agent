import importlib.util
import inspect
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROJECTS = (
    "Blog Ingestion Agent",
    "Whitepaper Ingestion Agent",
    "Glossary Agent",
)
ASSET_UPLOADERS = (
    "Blog Ingestion Agent",
    "Glossary Agent",
)
EXPECTED_ASSET_SIGNATURES = {
    "Blog Ingestion Agent": (
        "(output_dir: str, docx_path: str, config: dict = None, "
        "config_path: str = 'config.yaml', dry_run: bool = False) -> dict"
    ),
    "Glossary Agent": (
        "(media_dir: str, config: dict = None, config_path: str = 'config.yaml', "
        "dry_run: bool = False) -> dict"
    ),
}


def entrypoint_paths():
    for project_name in PROJECTS:
        scripts_dir = REPOSITORY_ROOT / project_name / "scripts"
        for path in sorted(scripts_dir.glob("*.py")):
            if "__main__" in path.read_text(encoding="utf-8"):
                yield project_name, path


def load_script(project_name, script_name):
    path = REPOSITORY_ROOT / project_name / "scripts" / f"{script_name}.py"
    module_name = f"test_entrypoint_{project_name.lower().replace(' ', '_')}_{script_name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module_name, module


class ConsoleEntrypointTests(unittest.TestCase):
    def test_every_python_entrypoint_enables_shared_utf8_console_support(self):
        for project_name, path in entrypoint_paths():
            with self.subTest(project=project_name, script=path.name):
                module_name = None
                with patch("ingestion_common.console.enable_utf8") as enable_utf8:
                    module_name, _ = load_script(project_name, path.stem)
                self.addCleanup(sys.modules.pop, module_name, None)
                enable_utf8.assert_called_once_with()

    def test_representative_help_commands_run_from_each_project_root(self):
        for project_name in PROJECTS:
            with self.subTest(project=project_name):
                project_root = REPOSITORY_ROOT / project_name
                result = subprocess.run(
                    [sys.executable, "scripts/map_to_contentstack.py", "--help"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("usage:", result.stdout.lower())


class AssetUploaderConfigTests(unittest.TestCase):
    def test_asset_uploaders_keep_their_callable_signatures(self):
        for project_name in ASSET_UPLOADERS:
            with self.subTest(project=project_name):
                module_name, module = load_script(project_name, "upload_assets")
                self.addCleanup(sys.modules.pop, module_name, None)
                self.assertEqual(
                    EXPECTED_ASSET_SIGNATURES[project_name],
                    str(inspect.signature(module.upload_assets)),
                )

    def test_asset_uploaders_use_shared_config_with_explicit_project_root(self):
        for project_name in ASSET_UPLOADERS:
            with self.subTest(project=project_name), tempfile.TemporaryDirectory() as tmp:
                project_root = REPOSITORY_ROOT / project_name

                def fake_load_config(config_path, project_root=None):
                    self.assertEqual("shared-only.yaml", config_path)
                    self.assertEqual(REPOSITORY_ROOT / project_name, project_root)
                    return {}

                with patch(
                    "ingestion_common.config.load_config",
                    side_effect=fake_load_config,
                ):
                    module_name, module = load_script(project_name, "upload_assets")
                    self.addCleanup(sys.modules.pop, module_name, None)
                    empty_dir = Path(tmp) / "empty"
                    empty_dir.mkdir()
                    if project_name == "Blog Ingestion Agent":
                        from docx import Document

                        normalized_dir = Path(tmp) / "normalized"
                        normalized_dir.mkdir()
                        (normalized_dir / "normalized_blog.json").write_text(
                            "{}", encoding="utf-8"
                        )
                        docx_path = Path(tmp) / "empty.docx"
                        Document().save(docx_path)
                        result = module.upload_assets(
                            normalized_dir,
                            docx_path,
                            config_path="shared-only.yaml",
                            dry_run=True,
                        )
                    else:
                        result = module.upload_assets(
                            empty_dir,
                            config_path="shared-only.yaml",
                            dry_run=True,
                        )

                self.assertEqual({}, result)


if __name__ == "__main__":
    unittest.main()

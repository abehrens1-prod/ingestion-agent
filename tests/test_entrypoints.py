import base64
import importlib.util
import inspect
import os
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
EXPECTED_ASSET_HELP = {
    "Blog Ingestion Agent": (
        "usage: upload_assets.py [-h] [--config CONFIG] [--dry-run]\n"
        "                        output_dir docx_path\n"
    ),
    "Glossary Agent": (
        "usage: upload_assets.py [-h] [--config CONFIG] [--output OUTPUT]\n"
        "                        [--normalized NORMALIZED] [--dry-run]\n"
        "                        media_dir\n"
    ),
}
ISOLATED_IMPORT = """\
import importlib.util
import sys
import warnings

path = sys.argv[1]
spec = importlib.util.spec_from_file_location("isolated_entrypoint", path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    spec.loader.exec_module(module)
"""
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


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


def subprocess_env():
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["MSTR_API_KEY"] = ""
    return env


class ConsoleEntrypointTests(unittest.TestCase):
    def test_every_entrypoint_imports_in_an_isolated_project_root_process(self):
        for project_name, path in entrypoint_paths():
            with self.subTest(project=project_name, script=path.name):
                project_root = REPOSITORY_ROOT / project_name
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        ISOLATED_IMPORT,
                        str(path.relative_to(project_root)),
                    ],
                    cwd=project_root,
                    env=subprocess_env(),
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertEqual(0, result.returncode, result.stderr)

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
    def test_asset_uploader_help_preserves_cli_signatures(self):
        for project_name in ASSET_UPLOADERS:
            with self.subTest(project=project_name):
                project_root = REPOSITORY_ROOT / project_name
                result = subprocess.run(
                    [sys.executable, "scripts/upload_assets.py", "--help"],
                    cwd=project_root,
                    env=subprocess_env(),
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertTrue(
                    result.stdout.startswith(EXPECTED_ASSET_HELP[project_name]),
                    result.stdout,
                )

    def test_asset_uploader_dry_run_cli_output_remains_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            blog_root = REPOSITORY_ROOT / "Blog Ingestion Agent"
            blog_output = tmp_path / "blog-output"
            blog_output.mkdir()
            (blog_output / "normalized_blog.json").write_text(
                "{}", encoding="utf-8"
            )
            image_path = tmp_path / "pixel.png"
            image_path.write_bytes(PNG_1X1)
            docx_path = tmp_path / "blog.docx"
            from docx import Document

            document = Document()
            document.add_picture(str(image_path))
            document.save(docx_path)
            blog_result = subprocess.run(
                [
                    sys.executable,
                    "scripts/upload_assets.py",
                    str(blog_output),
                    str(docx_path),
                    "--dry-run",
                ],
                cwd=blog_root,
                env=subprocess_env(),
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(0, blog_result.returncode, blog_result.stderr)
            self.assertEqual(
                "Extracting images from docx...\n"
                "  Extracted 1 image(s): image_0.png\n"
                f"[Dry run] Would upload: {blog_output / 'image_0.png'}\n"
                "\nDone. 0 asset(s) uploaded.\n",
                blog_result.stdout,
            )

            glossary_root = REPOSITORY_ROOT / "Glossary Agent"
            media_dir = tmp_path / "media"
            media_dir.mkdir()
            media_path = media_dir / "pixel.png"
            media_path.write_bytes(PNG_1X1)
            glossary_result = subprocess.run(
                [
                    sys.executable,
                    "scripts/upload_assets.py",
                    str(media_dir),
                    "--dry-run",
                ],
                cwd=glossary_root,
                env=subprocess_env(),
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(0, glossary_result.returncode, glossary_result.stderr)
            self.assertEqual(
                "Found 1 file(s): pixel.png (image)\n"
                f"[Dry run] Would upload: {media_path}\n"
                "\nDone. 0 asset(s) uploaded.\n",
                glossary_result.stdout,
            )

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

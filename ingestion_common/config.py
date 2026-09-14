"""Project-relative configuration lookup."""

from pathlib import Path

import yaml


def find_config(config_path="config.yaml", project_root=None) -> Path:
    """Find a config in the working directory or explicit project root."""
    path = Path(config_path)
    if path.is_absolute():
        if path.exists():
            return path
        raise FileNotFoundError(f"Config not found: {config_path}")

    bases = [Path.cwd()]
    if project_root is not None:
        bases.append(Path(project_root))

    for base in bases:
        candidate = base / path
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f"Config not found: {config_path}")


def load_config(config_path="config.yaml", project_root=None) -> dict:
    """Load YAML configuration from the resolved config path."""
    with open(find_config(config_path, project_root), "r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)

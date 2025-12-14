"""Prompt configuration loader.

Loads YAML prompt configurations from config/prompts/ directory.
"""
from pathlib import Path
from typing import Any, Dict
import yaml


class PromptLoader:
    """Load prompt configurations from YAML files."""

    def __init__(self, prompts_dir: Path = None):
        """Initialize loader.

        Args:
            prompts_dir: Path to prompts directory.
                         Defaults to app/config/prompts/
        """
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent.parent.parent / "config" / "prompts"
        self._prompts_dir = prompts_dir
        self._cache: Dict[str, Dict[str, Any]] = {}

    def load(self, name: str) -> Dict[str, Any]:
        """Load a prompt configuration by name.

        Args:
            name: Config name (e.g., "text_extraction", "dde_section_a")

        Returns:
            Dictionary with prompt configuration

        Raises:
            FileNotFoundError: If config file not found
        """
        if name in self._cache:
            return self._cache[name]

        # Try extraction/ subdirectory first
        path = self._prompts_dir / "extraction" / f"{name}.yaml"
        if not path.exists():
            # Try schemas/ subdirectory
            path = self._prompts_dir / "schemas" / f"{name}.yaml"
        if not path.exists():
            # Try root prompts directory
            path = self._prompts_dir / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Prompt config not found: {name}")

        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self._cache[name] = config
        return config

    def load_base(self, name: str) -> Dict[str, Any]:
        """Load a base configuration.

        Args:
            name: Base config name (e.g., "visit_types")

        Returns:
            Dictionary with base configuration
        """
        path = self._prompts_dir / "_base" / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Base config not found: {name}")

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self._cache.clear()

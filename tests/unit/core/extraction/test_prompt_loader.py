"""Tests for prompt loader."""
import pytest
from pathlib import Path
from app.core.extraction.prompt_loader import PromptLoader


class TestPromptLoader:
    def test_load_text_extraction_config(self, tmp_path):
        # Create test YAML
        prompts_dir = tmp_path / "prompts" / "extraction"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "text_extraction.yaml").write_text("""
system_prompt: "Test system prompt"
user_prompt: "Test user prompt"
""")
        loader = PromptLoader(tmp_path / "prompts")
        config = loader.load("text_extraction")

        assert config["system_prompt"] == "Test system prompt"
        assert config["user_prompt"] == "Test user prompt"

    def test_load_missing_config_raises(self, tmp_path):
        loader = PromptLoader(tmp_path / "prompts")

        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent")

    def test_load_from_schemas_directory(self, tmp_path):
        # Create test YAML in schemas subdirectory
        schemas_dir = tmp_path / "prompts" / "schemas"
        schemas_dir.mkdir(parents=True)
        (schemas_dir / "chartvision_chronology_template.yaml").write_text("""
template_name: "chronology"
fields:
  - date
  - description
""")
        loader = PromptLoader(tmp_path / "prompts")
        config = loader.load("chartvision_chronology_template")

        assert config["template_name"] == "chronology"

    def test_load_base_config(self, tmp_path):
        # Create test YAML in _base subdirectory
        base_dir = tmp_path / "prompts" / "_base"
        base_dir.mkdir(parents=True)
        (base_dir / "visit_types.yaml").write_text("""
visit_types:
  - office_visit
  - hospital
""")
        loader = PromptLoader(tmp_path / "prompts")
        config = loader.load_base("visit_types")

        assert "visit_types" in config
        assert "office_visit" in config["visit_types"]

    def test_caching_returns_same_object(self, tmp_path):
        prompts_dir = tmp_path / "prompts" / "extraction"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "test.yaml").write_text("key: value")

        loader = PromptLoader(tmp_path / "prompts")
        config1 = loader.load("test")
        config2 = loader.load("test")

        assert config1 is config2  # Same object due to caching

    def test_clear_cache(self, tmp_path):
        prompts_dir = tmp_path / "prompts" / "extraction"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "test.yaml").write_text("key: value")

        loader = PromptLoader(tmp_path / "prompts")
        config1 = loader.load("test")
        loader.clear_cache()
        config2 = loader.load("test")

        assert config1 is not config2  # Different objects after cache clear

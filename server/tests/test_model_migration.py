"""Tests for one-time model migration (LiteLLM provider normalization)."""

import json
import tempfile
from pathlib import Path

import pytest

from apps.code_editor.models.manager import (
    ModelManager,
    _migrate_model_provider,
    _has_migration_been_done,
    _write_migration_marker,
    _get_migration_marker_path,
    LITELLM_MIGRATION_VERSION,
    get_xeditor_base_path,
    get_models_path,
)


@pytest.fixture
def temp_xeditor_dir(monkeypatch):
    """Use a temp directory for xeditor data during tests."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        monkeypatch.setattr(
            "apps.code_editor.models.manager.get_xeditor_base_path",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "apps.code_editor.models.manager.get_models_path",
            lambda: tmp_path / "models.json",
        )
        monkeypatch.setattr(
            "apps.code_editor.models.manager._get_migration_marker_path",
            lambda: tmp_path / ".litellm_migration_done",
        )
        yield tmp_path


@pytest.fixture
def manager_with_bundled(temp_xeditor_dir):
    """ModelManager with bundled defaults (uses real bundled path)."""
    return ModelManager()


class TestMigrateModelProvider:
    """Tests for _migrate_model_provider."""

    def test_openai_compatible_gemini_to_google(self):
        model = {"id": "m1", "provider": "openai_compatible", "family": "gemini"}
        assert _migrate_model_provider(model) is True
        assert model["provider"] == "google"
        assert model["family"] == "gemini"

    def test_openai_compatible_kimi_to_kimi(self):
        model = {"id": "m2", "provider": "openai_compatible", "family": "kimi"}
        assert _migrate_model_provider(model) is True
        assert model["provider"] == "kimi"
        assert model["family"] == "kimi"

    def test_provider_gemini_to_google(self):
        model = {"id": "m3", "provider": "gemini", "family": ""}
        assert _migrate_model_provider(model) is True
        assert model["provider"] == "google"
        assert model["family"] == "gemini"

    def test_no_migration_needed(self):
        model = {"id": "m4", "provider": "openai", "family": "gpt"}
        assert _migrate_model_provider(model) is False
        assert model["provider"] == "openai"

    def test_openai_compatible_other_family_unchanged(self):
        model = {"id": "m5", "provider": "openai_compatible", "family": "deepseek"}
        assert _migrate_model_provider(model) is False
        assert model["provider"] == "openai_compatible"


class TestMigrationMarker:
    """Tests for migration marker."""

    def test_marker_prevents_remigration(self, temp_xeditor_dir):
        _write_migration_marker()
        assert _has_migration_been_done() is True
        marker_path = temp_xeditor_dir / ".litellm_migration_done"
        assert marker_path.exists()
        with open(marker_path) as f:
            data = json.load(f)
        assert data.get("version") == LITELLM_MIGRATION_VERSION

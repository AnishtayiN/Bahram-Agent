"""Tests for core modules."""
import pytest
from bahram.core.config import Config
from bahram.core.context import ContextManager
from bahram.core.profiles import ProfileManager
from bahram.core.themes import ThemeManager

class TestConfig:
    def test_config_creation(self):
        config = Config()
        assert config is not None

    def test_config_defaults(self):
        config = Config()
        assert hasattr(config, 'model') or hasattr(config, '__dict__')

class TestContextManager:
    def test_context_creation(self):
        ctx = ContextManager()
        assert ctx is not None

class TestProfileManager:
    def test_profile_manager(self, tmp_path):
        pm = ProfileManager(data_dir=str(tmp_path))
        assert pm is not None

    def test_create_profile(self, tmp_path):
        pm = ProfileManager(data_dir=str(tmp_path))
        profile = pm.create_profile("test", "Test Profile")
        assert profile.name == "test"

class TestThemeManager:
    def test_theme_manager(self, tmp_path):
        tm = ThemeManager(config_dir=str(tmp_path))
        assert tm is not None

    def test_get_default_theme(self, tmp_path):
        tm = ThemeManager(config_dir=str(tmp_path))
        theme = tm.get_theme("default")
        assert theme is not None

import os
import pytest
from unittest.mock import patch
from config import Config, ConfigError


def test_loads_api_key_from_env():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-123"}):
        config = Config()
        assert config.api_key == "test-key-123"


def test_raises_when_api_key_missing():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ConfigError, match="GEMINI_API_KEY"):
            Config()


def test_fallback_models_order():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        config = Config()
        assert config.fallback_models[0] == "gemini-2.0-flash"
        assert len(config.fallback_models) >= 2

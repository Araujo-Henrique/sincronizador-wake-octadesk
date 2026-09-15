import pytest

from src.config import ConfigError, _with_plus_prefix, load_config


def test_with_plus_prefix_adds_missing_plus():
    assert _with_plus_prefix("5541999998888") == "+5541999998888"


def test_with_plus_prefix_keeps_existing_plus():
    assert _with_plus_prefix("+5541999998888") == "+5541999998888"


@pytest.fixture
def required_env(monkeypatch):
    monkeypatch.setenv("WAKE_API_BASE_URL", "https://api.fbits.net")
    monkeypatch.setenv("WAKE_AUTH_HEADER_NAME", "Authorization")
    monkeypatch.setenv("WAKE_API_TOKEN", "fake-wake-token")
    monkeypatch.setenv("OCTADESK_API_BASE_URL", "https://example.octadesk.services")
    monkeypatch.setenv("OCTADESK_API_KEY", "fake-api-key")
    monkeypatch.setenv("OCTADESK_AGENT_EMAIL", "agent@example.com")
    monkeypatch.setenv("OCTADESK_TEMPLATE_ID", "template123")


def test_load_config_adds_plus_prefix_to_waba_number_when_missing(required_env, monkeypatch):
    monkeypatch.setenv("OCTADESK_WABA_NUMBER", "5541999998888")
    config = load_config()
    assert config.octadesk.waba_number == "+5541999998888"


def test_load_config_keeps_plus_prefix_when_already_present(required_env, monkeypatch):
    monkeypatch.setenv("OCTADESK_WABA_NUMBER", "+5541999998888")
    config = load_config()
    assert config.octadesk.waba_number == "+5541999998888"


def test_load_config_raises_when_required_var_missing(required_env, monkeypatch):
    monkeypatch.delenv("OCTADESK_WABA_NUMBER", raising=False)
    with pytest.raises(ConfigError):
        load_config()

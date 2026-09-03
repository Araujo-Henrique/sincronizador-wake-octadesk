from datetime import date

import pytest
import requests_mock

from src.config import WakeConfig
from src.wake_client import WakeClient, normalize_phone


@pytest.fixture
def wake_config() -> WakeConfig:
    return WakeConfig(
        base_url="https://api.fbits.net",
        auth_header_name="TokenAPI",
        auth_header_value="fake-token",
        customers_endpoint="/clientes",
    )


# --- normalize_phone -------------------------------------------------------


def test_normalize_phone_adds_country_code():
    assert normalize_phone("(11) 99999-8888") == "+5511999998888"


def test_normalize_phone_keeps_existing_country_code():
    assert normalize_phone("+55 11 99999-8888") == "+5511999998888"


def test_normalize_phone_rejects_value_without_digits():
    with pytest.raises(ValueError):
        normalize_phone("não é um telefone")


# --- WakeClient.get_customers_registered_on ---------------------------------


def test_get_customers_registered_on_parses_response(wake_config):
    client = WakeClient(wake_config)
    with requests_mock.Mocker() as m:
        m.get(
            "https://api.fbits.net/clientes",
            json={"data": [{"Nome": "Maria", "Celular": "11999998888", "Email": "maria@x.com"}]},
        )
        customers = client.get_customers_registered_on(date(2026, 9, 2))

    assert len(customers) == 1
    assert customers[0].name == "Maria"
    assert customers[0].phone == "+5511999998888"
    assert customers[0].email == "maria@x.com"


def test_get_customers_registered_on_sends_auth_header(wake_config):
    client = WakeClient(wake_config)
    with requests_mock.Mocker() as m:
        m.get("https://api.fbits.net/clientes", json={"data": []})
        client.get_customers_registered_on(date(2026, 9, 2))

    sent_request = m.request_history[0]
    assert sent_request.headers["TokenAPI"] == "fake-token"


def test_get_customers_registered_on_skips_entries_without_phone(wake_config):
    client = WakeClient(wake_config)
    with requests_mock.Mocker() as m:
        m.get(
            "https://api.fbits.net/clientes",
            json={"data": [{"Nome": "Sem telefone"}, {"Nome": "Com telefone", "Celular": "11988887777"}]},
        )
        customers = client.get_customers_registered_on(date(2026, 9, 2))

    assert len(customers) == 1
    assert customers[0].name == "Com telefone"


def test_get_customers_registered_on_raises_for_http_error(wake_config):
    client = WakeClient(wake_config)
    with requests_mock.Mocker() as m:
        m.get("https://api.fbits.net/clientes", status_code=500)
        with pytest.raises(Exception):
            client.get_customers_registered_on(date(2026, 9, 2))

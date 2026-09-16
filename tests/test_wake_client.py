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
            json=[{"usuarioId": 1, "nome": "Maria", "telefoneCelular": "11999998888", "email": "maria@x.com"}],
            headers={"X-Total-Count": "1"},
        )
        customers = client.get_customers_registered_on(date(2026, 9, 2))

    assert len(customers) == 1
    assert customers[0].name == "Maria"
    assert customers[0].phone == "+5511999998888"
    assert customers[0].email == "maria@x.com"


def test_get_customers_registered_on_uses_inclusive_start_and_exclusive_end(wake_config):
    """dataInicial é inclusivo e dataFinal é exclusivo (confirmado testando contra
    a API real) — por isso o intervalo usado é [target_date, target_date + 1 dia).
    """
    client = WakeClient(wake_config)
    with requests_mock.Mocker() as m:
        m.get("https://api.fbits.net/clientes", json=[], headers={"X-Total-Count": "0"})
        client.get_customers_registered_on(date(2026, 9, 2))

    sent_request = m.request_history[0]
    assert sent_request.qs["datainicial"] == ["2026-09-02"]
    assert sent_request.qs["datafinal"] == ["2026-09-03"]
    assert sent_request.qs["pagina"] == ["1"]


def test_get_customers_registered_on_paginates_using_x_total_count(wake_config):
    """A resposta é limitada a 50 itens por página — se X-Total-Count indicar mais
    registros do que a página trouxe, o cliente precisa buscar as páginas seguintes.
    """
    client = WakeClient(wake_config)
    page_1 = [{"usuarioId": i, "nome": f"Cliente {i}", "telefoneCelular": "11999998888"} for i in range(1, 51)]
    page_2 = [{"usuarioId": 51, "nome": "Cliente 51", "telefoneCelular": "11999998888"}]
    with requests_mock.Mocker() as m:
        m.get(
            "https://api.fbits.net/clientes",
            [
                {"json": page_1, "headers": {"X-Total-Count": "51"}},
                {"json": page_2, "headers": {"X-Total-Count": "51"}},
            ],
        )
        customers = client.get_customers_registered_on(date(2026, 9, 2))

    assert len(customers) == 51
    assert len(m.request_history) == 2
    assert m.request_history[0].qs["pagina"] == ["1"]
    assert m.request_history[1].qs["pagina"] == ["2"]


def test_get_customers_registered_on_sends_auth_header(wake_config):
    client = WakeClient(wake_config)
    with requests_mock.Mocker() as m:
        m.get("https://api.fbits.net/clientes", json=[], headers={"X-Total-Count": "0"})
        client.get_customers_registered_on(date(2026, 9, 2))

    assert m.request_history[0].headers["TokenAPI"] == "fake-token"


def test_get_customers_registered_on_skips_entries_without_phone(wake_config):
    client = WakeClient(wake_config)
    with requests_mock.Mocker() as m:
        m.get(
            "https://api.fbits.net/clientes",
            json=[
                {"usuarioId": 1, "nome": "Sem telefone"},
                {"usuarioId": 2, "nome": "Com telefone", "telefoneCelular": "11988887777"},
            ],
            headers={"X-Total-Count": "2"},
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

import pytest
import requests_mock

from src.config import OctadeskConfig
from src.octadesk_client import OctadeskApiError, OctadeskClient, TemplateVariable


@pytest.fixture
def octadesk_config() -> OctadeskConfig:
    return OctadeskConfig(
        base_url="https://api.octadesk.example",
        api_key="fake-key",
        agent_email="bot@empresa.com",
        waba_number="+5511900000000",
        template_id="template-123",
    )


def test_send_template_message_success(octadesk_config):
    client = OctadeskClient(octadesk_config)
    with requests_mock.Mocker() as m:
        m.post("https://api.octadesk.example/chat/send-template", status_code=201, json={})
        client.send_template_message(phone="+5511999998888", name="Maria")

    sent_request = m.request_history[0]
    assert sent_request.headers["x-api-key"] == "fake-key"
    assert sent_request.headers["octa-agent-email"] == "bot@empresa.com"

    body = sent_request.json()
    assert body["target"]["contact"]["channel"] == "whatsapp"
    assert body["target"]["contact"]["code"] == "+5511999998888"
    assert body["target"]["contact"]["name"] == "Maria"
    assert body["origin"]["contact"]["code"] == "+5511900000000"
    assert body["content"]["templateMessage"]["id"] == "template-123"


def test_send_template_message_includes_email_only_when_provided(octadesk_config):
    client = OctadeskClient(octadesk_config)
    with requests_mock.Mocker() as m:
        m.post("https://api.octadesk.example/chat/send-template", status_code=201, json={})
        client.send_template_message(phone="+5511999998888", name="Maria")

    body = m.request_history[0].json()
    assert "email" not in body["target"]["contact"]


def test_send_template_message_sends_variables(octadesk_config):
    client = OctadeskClient(octadesk_config)
    with requests_mock.Mocker() as m:
        m.post("https://api.octadesk.example/chat/send-template", status_code=201, json={})
        client.send_template_message(
            phone="+5511999998888",
            name="Maria",
            variables=[TemplateVariable(key="1", value="Maria")],
        )

    body = m.request_history[0].json()
    assert body["content"]["templateMessage"]["variables"] == [{"key": "1", "value": "Maria"}]


def test_send_template_message_raises_on_error_status(octadesk_config):
    client = OctadeskClient(octadesk_config)
    with requests_mock.Mocker() as m:
        m.post(
            "https://api.octadesk.example/chat/send-template",
            status_code=400,
            text="template não encontrado",
        )
        with pytest.raises(OctadeskApiError):
            client.send_template_message(phone="+5511999998888", name="Maria")

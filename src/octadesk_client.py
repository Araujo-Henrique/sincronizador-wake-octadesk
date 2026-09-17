"""Cliente para a API do Octadesk — envia a mensagem de template de WhatsApp já
aprovada na plataforma para um número de telefone específico.

Baseado na documentação oficial:
  - Autenticação: https://developers.octadesk.com/reference/authentication
    (headers "x-api-key" e "octa-agent-email"; a chave é obtida com o suporte
    da Octadesk, não existe login por usuário/senha)
  - Endpoint: https://developers.octadesk.com/reference/sendtemplate
    (POST /chat/send-template — o campo "code" dentro de "contact" é o próprio
    número de WhatsApp; "email" e "name" são opcionais e só preenchem variáveis
    do template, não são usados para identificar o contato)

O host completo da API (OCTADESK_API_BASE_URL) não é público — ele é informado
pelo suporte da Octadesk junto com a chave de API.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests

from src.config import OctadeskConfig

logger = logging.getLogger(__name__)


class OctadeskApiError(Exception):
    """Levantado quando o Octadesk recusa ou falha ao processar o envio do template."""


@dataclass(frozen=True)
class TemplateVariable:
    """Uma variável do template (ex: {{1}} = nome do cliente)."""

    key: str
    value: str


class OctadeskClient:
    """Encapsula a comunicação HTTP com a API do Octadesk para envio de templates."""

    SEND_TEMPLATE_PATH = "/chat/send-template"

    def __init__(
        self,
        config: OctadeskConfig,
        timeout_seconds: float = 15.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._config = config
        self._timeout = timeout_seconds
        self._session = session or requests.Session()

    def send_template_message(
        self,
        *,
        phone: str,
        name: str,
        email: Optional[str] = None,
        variables: Optional[list[TemplateVariable]] = None,
    ) -> None:
        """Envia o template aprovado no Octadesk para `phone`.

        `phone` deve estar no formato internacional (+55...) — ver
        wake_client.normalize_phone. `name`/`email` são opcionais e só importam
        se o template usa as variáveis nome-contato/email-contato.
        """
        url = self._config.base_url.rstrip("/") + self.SEND_TEMPLATE_PATH
        headers = {
            "x-api-key": self._config.api_key,
            "octa-agent-email": self._config.agent_email,
            "Content-Type": "application/json",
        }

        target_contact: dict[str, str] = {
            "channel": "whatsapp",
            "code": phone,
            "name": name,
        }
        if email:
            target_contact["email"] = email

        body = {
            "origin": {
                "contact": {
                    "channel": "whatsapp",
                    "code": self._config.waba_number,
                }
            },
            "target": {"contact": target_contact},
            "content": {
                "templateMessage": {
                    "id": self._config.template_id,
                    "variables": [{"key": v.key, "value": v.value} for v in (variables or [])],
                }
            },
            # automaticAssign=True atribui a conversa direto a um agente humano,
            # pulando o bot/fluxo configurado no canal — confirmado testando
            # manualmente (respondendo ao template) que automaticAssign=False é
            # o que deixa o bot engatar antes de cair num humano.
            "options": {"automaticAssign": False},
        }

        response = self._session.post(url, json=body, headers=headers, timeout=self._timeout)
        if not response.ok:
            raise OctadeskApiError(
                f"Octadesk recusou o envio para {phone}: {response.status_code} {response.text}"
            )
        logger.info("Template enviado para %s (status %s)", phone, response.status_code)

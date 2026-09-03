"""Carrega e valida as configurações da aplicação a partir de variáveis de ambiente.

Nenhuma credencial fica hardcoded no código: tudo vem do ambiente (arquivo
.env.development em desenvolvimento, ou variáveis de ambiente reais em produção).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Carrega o .env.development (se existir) para dentro do ambiente do processo.
# Em produção, as variáveis normalmente já vêm definidas pelo sistema/agendador,
# e load_dotenv() simplesmente não encontra o arquivo e não faz nada.
load_dotenv(".env.development")


class ConfigError(Exception):
    """Levantado quando uma variável de ambiente obrigatória não foi definida."""


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigError(
            f"Variável de ambiente obrigatória '{name}' não foi definida. "
            f"Veja o .env.example e configure o seu .env.development."
        )
    return value


@dataclass(frozen=True)
class WakeConfig:
    base_url: str
    auth_header_name: str
    auth_header_value: str
    customers_endpoint: str


@dataclass(frozen=True)
class OctadeskConfig:
    base_url: str
    api_key: str
    agent_email: str
    waba_number: str
    template_id: str


@dataclass(frozen=True)
class AppConfig:
    wake: WakeConfig
    octadesk: OctadeskConfig
    sent_log_path: str
    request_timeout_seconds: float


def load_config() -> AppConfig:
    """Lê e valida todas as variáveis de ambiente necessárias, de uma vez só.

    Falhar aqui, no início da execução, é intencional: é melhor o job parar
    imediatamente com uma mensagem clara do que falhar no meio do processamento
    de 50 clientes por causa de uma variável faltando.
    """
    wake = WakeConfig(
        base_url=_require("WAKE_API_BASE_URL"),
        auth_header_name=_require("WAKE_AUTH_HEADER_NAME"),
        auth_header_value=_require("WAKE_API_TOKEN"),
        customers_endpoint=os.getenv("WAKE_CUSTOMERS_ENDPOINT", "/clientes"),
    )
    octadesk = OctadeskConfig(
        base_url=_require("OCTADESK_API_BASE_URL"),
        api_key=_require("OCTADESK_API_KEY"),
        agent_email=_require("OCTADESK_AGENT_EMAIL"),
        waba_number=_require("OCTADESK_WABA_NUMBER"),
        template_id=_require("OCTADESK_TEMPLATE_ID"),
    )
    return AppConfig(
        wake=wake,
        octadesk=octadesk,
        sent_log_path=os.getenv("SENT_LOG_PATH", "logs/sent_log.jsonl"),
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15")),
    )

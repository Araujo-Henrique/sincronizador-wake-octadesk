"""Cliente para a API da Wake — busca os clientes cadastrados em uma data específica.

ATENÇÃO — pontos marcados com TODO precisam ser confirmados com a documentação
oficial da Wake (https://wakecommerce.readme.io/ e o token gerado em
Extensões e Integrações > Tokens, dentro do painel admin da Wake) assim que
vocês tiverem acesso a ela. Sem credenciais reais, não é possível confirmar:
  - o path exato do endpoint de listagem de clientes;
  - os nomes dos parâmetros de filtro por data de cadastro;
  - os nomes exatos dos campos na resposta (nome, telefone, email).

O restante do projeto (Octadesk, log de idempotência, orquestração) não depende
desses detalhes — só esta classe precisa ser ajustada depois.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

import requests

from src.config import WakeConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WakeCustomer:
    """Cliente da Wake já normalizado para o que o resto do programa precisa."""

    name: str
    phone: str
    email: Optional[str] = None

    @staticmethod
    def from_api(payload: dict[str, Any]) -> "WakeCustomer":
        # TODO: ajustar os nomes das chaves ("Nome", "Celular", "Telefone", "Email")
        # assim que confirmarmos o formato real da resposta da API da Wake.
        phone = payload.get("Celular") or payload.get("Telefone")
        if not phone:
            raise ValueError(f"cliente sem telefone/celular na resposta da Wake: {payload!r}")
        return WakeCustomer(
            name=(payload.get("Nome") or "").strip(),
            phone=normalize_phone(str(phone)),
            email=payload.get("Email") or None,
        )


def normalize_phone(raw_phone: str) -> str:
    """Normaliza um telefone brasileiro para o formato E.164 (+55DDDNUMERO).

    A API do Octadesk espera o número de WhatsApp em formato internacional
    (ex: +5511999998888). Números vindos de sistemas de cadastro costumam vir
    formatados de formas variadas ("(11) 99999-8888", "11999998888", etc.),
    então normalizamos tudo para um único formato antes de usar.
    """
    digits = "".join(ch for ch in raw_phone if ch.isdigit())
    if not digits:
        raise ValueError(f"telefone inválido, sem nenhum dígito: {raw_phone!r}")
    if not digits.startswith("55"):
        digits = "55" + digits
    return "+" + digits


class WakeClient:
    """Encapsula a comunicação HTTP com a API da Wake."""

    def __init__(
        self,
        config: WakeConfig,
        timeout_seconds: float = 15.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._config = config
        self._timeout = timeout_seconds
        self._session = session or requests.Session()

    def get_customers_registered_on(self, target_date: date) -> list[WakeCustomer]:
        """Busca todos os clientes cadastrados em `target_date`.

        TODO: confirmar com a documentação da Wake se a resposta é paginada.
        Se for, este método precisa percorrer todas as páginas antes de retornar.
        """
        url = self._config.base_url.rstrip("/") + self._config.customers_endpoint
        params = {
            # TODO: confirmar os nomes reais destes parâmetros com a doc da Wake.
            "dataCadastroInicial": target_date.isoformat(),
            "dataCadastroFinal": target_date.isoformat(),
        }
        headers = {self._config.auth_header_name: self._config.auth_header_value}

        response = self._session.get(url, params=params, headers=headers, timeout=self._timeout)
        response.raise_for_status()
        payload = response.json()

        # TODO: confirmar se a resposta vem como uma lista "crua" ou dentro de
        # uma chave como "data"/"Data"/"clientes" — hoje aceitamos os dois casos.
        raw_customers = payload.get("data", payload) if isinstance(payload, dict) else payload

        customers: list[WakeCustomer] = []
        for raw in raw_customers:
            try:
                customers.append(WakeCustomer.from_api(raw))
            except ValueError as exc:
                logger.warning("Ignorando cliente inválido vindo da Wake: %s", exc)
        return customers

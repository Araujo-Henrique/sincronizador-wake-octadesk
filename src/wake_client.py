"""Cliente para a API da Wake — busca os clientes cadastrados em uma data específica.

Contrato confirmado testando contra a API real (GET /usuarios):
  - "dataInicial" é um filtro INCLUSIVO ("cadastrados a partir desta data,
    incluindo ela") e "dataFinal" é EXCLUSIVO ("cadastrados antes do início
    desta data"). Para pegar só um dia, o intervalo usado é portanto
    [target_date, target_date + 1 dia).
  - A resposta é paginada: no máximo 50 registros por chamada, controlados
    pelo parâmetro "pagina" (1-based). O header de resposta "X-Total-Count"
    informa quantos registros no total batem com o filtro aplicado — sem
    paginar até esse total, um dia com muitos cadastros (ou uma consulta sem
    filtro apertado) fica truncado silenciosamente nos primeiros 50.
  - Os nomes dos campos no corpo da resposta (nome, telefoneCelular,
    telefoneComercial, email) vêm em camelCase.

O restante do projeto (Octadesk, log de idempotência, orquestração) não depende
desses detalhes — só esta classe precisa ser ajustada se a Wake mudar o
contrato da API.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
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
        # Nomes de campo confirmados batendo na API real da Wake (GET /usuarios):
        # a resposta vem em camelCase ("telefoneComercial", "telefoneCelular",
        # "nome", "email"), não capitalizado como se supunha antes.
        phone = payload.get("telefoneComercial") or payload.get("telefoneCelular")
        if not phone:
            raise ValueError(f"cliente sem telefone/celular na resposta da Wake: {payload!r}")
        return WakeCustomer(
            name=(payload.get("nome") or "").strip(),
            phone=normalize_phone(str(phone)),
            email=payload.get("email") or None,
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

        Usa "dataInicial"=target_date (inclusive) e "dataFinal"=target_date + 1
        dia (exclusive) — ver contrato da API no topo do arquivo — e percorre
        todas as páginas necessárias para cobrir o total de registros do dia.
        """
        params = {
            "dataInicial": target_date.isoformat(),
            "dataFinal": (target_date + timedelta(days=1)).isoformat(),
        }
        raw_customers = self._fetch_all_pages(params)

        customers: list[WakeCustomer] = []
        for raw in raw_customers:
            try:
                customers.append(WakeCustomer.from_api(raw))
            except ValueError as exc:
                logger.warning("Ignorando cliente inválido vindo da Wake: %s", exc)
        return customers

    def _fetch_all_pages(self, params: dict[str, str]) -> list[dict[str, Any]]:
        """Executa `params` contra o endpoint de clientes, percorrendo todas as
        páginas indicadas pelo header "X-Total-Count" da primeira resposta.
        """
        url = self._config.base_url.rstrip("/") + self._config.customers_endpoint
        headers = {self._config.auth_header_name: self._config.auth_header_value}

        all_raw: list[dict[str, Any]] = []
        page = 1
        while True:
            response = self._session.get(
                url, params={**params, "pagina": page}, headers=headers, timeout=self._timeout
            )
            response.raise_for_status()
            payload = response.json()
            raw_page = payload.get("data", payload) if isinstance(payload, dict) else payload
            if not raw_page:
                break
            all_raw.extend(raw_page)

            total_count = response.headers.get("X-Total-Count")
            if total_count is None or len(all_raw) >= int(total_count):
                break
            page += 1
        return all_raw

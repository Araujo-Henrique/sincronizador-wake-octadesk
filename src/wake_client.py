"""Cliente para a API da Wake — busca os clientes cadastrados em uma data específica.

ATENÇÃO — pontos ainda marcados com TODO precisam ser confirmados com a
documentação oficial da Wake (https://wakecommerce.readme.io/ e o token gerado
em Extensões e Integrações > Tokens, dentro do painel admin da Wake):
  - o path exato do endpoint de listagem de clientes;
  - o nome real do parâmetro de limite inferior ("cadastrados a partir de").
    Um teste manual contra a API real confirmou que "dataCadastroInicial" e
    "dataInicial" são ignorados (não filtram nada), então não há hoje um jeito
    direto de pedir a Wake "só os clientes cadastrados no dia X". Por isso
    get_customers_registered_on usa um workaround: chama a API duas vezes
    usando só "dataFinal" (esse parâmetro foi confirmado como funcional —
    filtra clientes cadastrados até a data informada) e calcula a diferença
    entre os dois conjuntos pelo "usuarioId".

Os nomes dos campos na resposta (nome, telefoneCelular, telefoneComercial,
email) já foram confirmados batendo na API real e estão corretos.

O restante do projeto (Octadesk, log de idempotência, orquestração) não depende
desses detalhes — só esta classe precisa ser ajustada depois.
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

        Workaround: a Wake não expõe um filtro funcional de "cadastrados a
        partir de" (ver TODO no topo do arquivo). Para isolar só quem se
        cadastrou em `target_date`, buscamos "cadastrados até o dia seguinte"
        e "cadastrados até `target_date`" (o único filtro confirmado como
        funcional é "dataFinal") e calculamos a diferença entre os dois
        conjuntos pelo "usuarioId".

        IMPORTANTE: "dataFinal=X" foi confirmado, testando contra a API real,
        como um corte EXCLUSIVO — equivale a "cadastrados antes do início do
        dia X", não "até o fim do dia X". Por isso o corte de cima usa
        `target_date + 1 dia`, não `target_date`.

        TODO: confirmar com a documentação da Wake se a resposta é paginada.
        Se for, este método precisa percorrer todas as páginas antes de retornar.
        """
        until_day_after_target = self._fetch_raw_customers_until(target_date + timedelta(days=1))
        until_target = self._fetch_raw_customers_until(target_date)

        already_existing_ids = {raw.get("usuarioId") for raw in until_target}
        raw_customers = [
            raw for raw in until_day_after_target if raw.get("usuarioId") not in already_existing_ids
        ]

        customers: list[WakeCustomer] = []
        for raw in raw_customers:
            try:
                customers.append(WakeCustomer.from_api(raw))
            except ValueError as exc:
                logger.warning("Ignorando cliente inválido vindo da Wake: %s", exc)
        return customers

    def _fetch_raw_customers_until(self, cutoff_date: date) -> list[dict[str, Any]]:
        """Busca os clientes cadastrados antes do início de `cutoff_date` (exclusive)."""
        url = self._config.base_url.rstrip("/") + self._config.customers_endpoint
        params = {"dataFinal": cutoff_date.isoformat()}
        headers = {self._config.auth_header_name: self._config.auth_header_value}

        response = self._session.get(url, params=params, headers=headers, timeout=self._timeout)
        response.raise_for_status()
        payload = response.json()

        # TODO: confirmar se a resposta vem como uma lista "crua" ou dentro de
        # uma chave como "data"/"Data"/"clientes" — hoje aceitamos os dois casos.
        return payload.get("data", payload) if isinstance(payload, dict) else payload

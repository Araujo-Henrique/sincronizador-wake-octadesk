"""Ponto de entrada do job.

Fluxo: busca na Wake os clientes cadastrados ontem -> para cada um, envia o
template de WhatsApp já aprovado no Octadesk -> registra quem já recebeu, para
não duplicar em caso de reexecução no mesmo dia.

Feito para ser chamado 1x por dia por um agendador externo (cron, Agendador de
Tarefas do Windows, etc.) — ver README.md para exemplos de como agendar.
"""
from __future__ import annotations

import logging
import sys
from datetime import date, timedelta
from typing import Optional

from src.config import load_config
from src.octadesk_client import OctadeskApiError, OctadeskClient
from src.sent_log import SentLog
from src.wake_client import WakeClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def run(
    wake: Optional[WakeClient] = None,
    octadesk: Optional[OctadeskClient] = None,
    sent_log: Optional[SentLog] = None,
    today: Optional[date] = None,
) -> int:
    """Executa o job uma vez. Retorna um exit code (0 = ok, 1 = houve falha).

    Os parâmetros opcionais existem para permitir testar esta função injetando
    "dublês" (mocks/fakes) no lugar dos clientes HTTP reais — veja
    tests/test_main.py. Quando chamados sem argumentos (uso normal via CLI),
    os clientes reais são criados a partir da configuração do ambiente.
    """
    if wake is None or octadesk is None or sent_log is None:
        config = load_config()
        wake = wake or WakeClient(config.wake, timeout_seconds=config.request_timeout_seconds)
        octadesk = octadesk or OctadeskClient(
            config.octadesk, timeout_seconds=config.request_timeout_seconds
        )
        sent_log = sent_log or SentLog(config.sent_log_path)

    yesterday = (today or date.today()) - timedelta(days=1)

    logger.info("Buscando clientes cadastrados na Wake em %s", yesterday.isoformat())
    try:
        customers = wake.get_customers_registered_on(yesterday)
    except Exception:
        logger.exception("Falha ao buscar clientes na Wake")
        return 1

    logger.info("%d cliente(s) encontrado(s)", len(customers))

    successes = 0
    failures = 0
    for customer in customers:
        if sent_log.already_sent(yesterday, customer.phone):
            logger.info("Pulando %s: já recebeu mensagem hoje", customer.phone)
            continue
        try:
            octadesk.send_template_message(
                phone=customer.phone, name=customer.name, email=customer.email
            )
            sent_log.mark_as_sent(yesterday, customer.phone)
            successes += 1
        except OctadeskApiError:
            logger.exception("Falha ao enviar mensagem para %s", customer.phone)
            failures += 1

    logger.info("Concluído: %d enviado(s), %d falha(s)", successes, failures)
    # Retornamos 1 (erro) se QUALQUER envio falhou. É intencional: exit code
    # != 0 é o sinal que o cron/Task Scheduler usa para marcar a execução como
    # falha (e, se configurado, disparar um alerta por e-mail). Preferimos ser
    # avisados de uma falha parcial a descobrir dias depois que um cliente
    # nunca recebeu a mensagem.
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())

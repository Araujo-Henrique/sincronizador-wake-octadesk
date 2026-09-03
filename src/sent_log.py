"""Controle de idempotência do job.

Se o agendador (cron/Task Scheduler) rodar o script duas vezes no mesmo dia — por
engano, ou porque a primeira execução falhou no meio e alguém rodou de novo — não
queremos mandar a mesma mensagem de WhatsApp duas vezes para o mesmo cliente.
Este módulo guarda, em um arquivo local, quais telefones já foram avisados em
qual data, e permite consultar isso antes de cada envio.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path


class SentLog:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._sent: set[tuple[str, str]] = self._load()

    def _load(self) -> set[tuple[str, str]]:
        if not self._path.exists():
            return set()
        sent: set[tuple[str, str]] = set()
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                sent.add((entry["date"], entry["phone"]))
        return sent

    def already_sent(self, target_date: date, phone: str) -> bool:
        return (target_date.isoformat(), phone) in self._sent

    def mark_as_sent(self, target_date: date, phone: str) -> None:
        entry = {"date": target_date.isoformat(), "phone": phone}
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        self._sent.add((entry["date"], entry["phone"]))

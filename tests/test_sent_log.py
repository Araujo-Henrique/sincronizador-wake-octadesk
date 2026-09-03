from datetime import date

from src.sent_log import SentLog


def test_phone_not_marked_as_sent_by_default(tmp_path):
    log = SentLog(str(tmp_path / "sent.jsonl"))
    assert log.already_sent(date(2026, 9, 2), "+5511999998888") is False


def test_mark_as_sent_is_remembered(tmp_path):
    log = SentLog(str(tmp_path / "sent.jsonl"))
    today = date(2026, 9, 2)

    log.mark_as_sent(today, "+5511999998888")

    assert log.already_sent(today, "+5511999998888") is True


def test_mark_as_sent_is_specific_to_the_date(tmp_path):
    log = SentLog(str(tmp_path / "sent.jsonl"))
    log.mark_as_sent(date(2026, 9, 2), "+5511999998888")

    assert log.already_sent(date(2026, 9, 3), "+5511999998888") is False


def test_state_persists_across_instances(tmp_path):
    """Simula o job rodando de novo no mesmo dia: uma nova instância de SentLog
    precisa enxergar o que a execução anterior já gravou no arquivo."""
    log_path = str(tmp_path / "sent.jsonl")
    today = date(2026, 9, 2)

    SentLog(log_path).mark_as_sent(today, "+5511999998888")
    second_run_log = SentLog(log_path)

    assert second_run_log.already_sent(today, "+5511999998888") is True

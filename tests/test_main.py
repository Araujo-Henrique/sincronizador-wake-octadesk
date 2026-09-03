from datetime import date
from unittest.mock import MagicMock

from src.main import run
from src.octadesk_client import OctadeskApiError
from src.wake_client import WakeCustomer


def test_run_sends_message_for_each_new_customer():
    wake = MagicMock()
    wake.get_customers_registered_on.return_value = [
        WakeCustomer(name="Maria", phone="+5511999998888", email="maria@x.com"),
    ]
    octadesk = MagicMock()
    sent_log = MagicMock()
    sent_log.already_sent.return_value = False

    exit_code = run(wake=wake, octadesk=octadesk, sent_log=sent_log, today=date(2026, 9, 3))

    assert exit_code == 0
    octadesk.send_template_message.assert_called_once_with(
        phone="+5511999998888", name="Maria", email="maria@x.com"
    )
    sent_log.mark_as_sent.assert_called_once_with(date(2026, 9, 2), "+5511999998888")


def test_run_uses_the_previous_day_relative_to_today():
    wake = MagicMock()
    wake.get_customers_registered_on.return_value = []
    octadesk = MagicMock()
    sent_log = MagicMock()

    run(wake=wake, octadesk=octadesk, sent_log=sent_log, today=date(2026, 9, 3))

    wake.get_customers_registered_on.assert_called_once_with(date(2026, 9, 2))


def test_run_skips_customers_already_sent():
    wake = MagicMock()
    wake.get_customers_registered_on.return_value = [
        WakeCustomer(name="Maria", phone="+5511999998888"),
    ]
    octadesk = MagicMock()
    sent_log = MagicMock()
    sent_log.already_sent.return_value = True

    exit_code = run(wake=wake, octadesk=octadesk, sent_log=sent_log, today=date(2026, 9, 3))

    assert exit_code == 0
    octadesk.send_template_message.assert_not_called()


def test_run_returns_error_code_when_a_send_fails():
    wake = MagicMock()
    wake.get_customers_registered_on.return_value = [
        WakeCustomer(name="Maria", phone="+5511999998888"),
    ]
    octadesk = MagicMock()
    octadesk.send_template_message.side_effect = OctadeskApiError("boom")
    sent_log = MagicMock()
    sent_log.already_sent.return_value = False

    exit_code = run(wake=wake, octadesk=octadesk, sent_log=sent_log, today=date(2026, 9, 3))

    assert exit_code == 1
    sent_log.mark_as_sent.assert_not_called()


def test_run_returns_error_code_when_wake_fails():
    wake = MagicMock()
    wake.get_customers_registered_on.side_effect = RuntimeError("Wake fora do ar")
    octadesk = MagicMock()
    sent_log = MagicMock()

    exit_code = run(wake=wake, octadesk=octadesk, sent_log=sent_log, today=date(2026, 9, 3))

    assert exit_code == 1
    octadesk.send_template_message.assert_not_called()

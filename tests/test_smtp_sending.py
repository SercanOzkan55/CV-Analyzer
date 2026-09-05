import email
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_WORKER_DIR = PROJECT_ROOT / "local_worker"
if str(LOCAL_WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(LOCAL_WORKER_DIR))

# qml_gui.py calls sys.exit(1) at import time when PySide6 isn't installed
# (it prints a native message-box hint and quits, since it assumes it's
# being launched as the GUI). That SystemExit escapes an unguarded import
# and crashes the whole pytest process (not just this file) during
# collection, so this whole module must skip cleanly, matching the
# per-test pytest.importorskip("PySide6") guard already used in
# test_local_worker_cli.py::test_write_csv_includes_score_breakdown_columns
# -- here it's module-level since every test in this file needs qml_gui.
pytest.importorskip("PySide6")

# qml_gui.py only launches a GUI under `if __name__ == "__main__"`, so
# importing it here just defines classes/functions -- safe in a headless
# test process, no QApplication needed for what we exercise below.
import qml_gui  # noqa: E402


def _stub_backend(job_name: str = "Backend Engineer"):
    """A minimal stand-in exposing just what `_render_template_for_row` and
    the `_template_replacements` helper it calls actually touch (`_job_name`),
    so tests don't have to spin up the full `LocalWorkerBackend`
    (WorkspaceStore, SQLite workspace db, etc.) just to exercise pure
    template-rendering logic. `_template_replacements` is bound onto the
    stub via `types.MethodType` so `self._template_replacements(...)`
    resolves inside `_render_template_for_row` without a real QObject."""
    stub = SimpleNamespace(_job_name=job_name)
    stub._template_replacements = types.MethodType(
        qml_gui.LocalWorkerBackend._template_replacements, stub
    )
    return stub


def test_render_template_for_row_substitutes_known_variables():
    row = {"file": "jane_doe.pdf", "email": "jane.doe@example.com", "score": 87.6}
    stub = _stub_backend(job_name="Senior Backend Engineer")

    subject = qml_gui.LocalWorkerBackend._render_template_for_row(
        stub, "Update for {name} re: {role}", row
    )
    body = qml_gui.LocalWorkerBackend._render_template_for_row(
        stub, "Hi {name} ({email}), your score was {score}. Regards, {company}", row
    )

    assert subject == "Update for Jane Doe re: Senior Backend Engineer"
    assert body == "Hi Jane Doe (jane.doe@example.com), your score was 87. Regards, CV Analyzer"


def test_render_template_for_row_falls_back_when_row_is_none():
    stub = _stub_backend(job_name="")

    rendered = qml_gui.LocalWorkerBackend._render_template_for_row(
        stub, "Hi {name} ({email}) for {role}, score {score}", None
    )

    assert rendered == "Hi Sercan Ozkan (candidate@example.com) for Software Engineer, score 85"


def test_render_template_for_row_uses_email_local_part_when_no_filename_stem():
    stub = _stub_backend()
    row = {"file": "", "email": "john.smith@example.com", "score": 60}

    rendered = qml_gui.LocalWorkerBackend._render_template_for_row(stub, "{name}", row)

    assert rendered == "John Smith"


def _make_transport():
    transport = MagicMock()
    return transport


def test_smtp_worker_sends_single_test_email_via_starttls():
    transport = _make_transport()
    statuses = []
    done_messages = []
    row_sent_events = []

    with patch("qml_gui.smtplib.SMTP", return_value=transport) as smtp_ctor, patch(
        "qml_gui.smtplib.SMTP_SSL"
    ) as smtp_ssl_ctor:
        worker = qml_gui.SmtpWorker(
            "smtp.example.com",
            587,
            "recruiter@example.com",
            "app-password",
            [(-1, "recruiter@example.com", "Test email", "This is a test message.")],
        )
        worker.status.connect(statuses.append)
        worker.done.connect(done_messages.append)
        worker.row_sent.connect(lambda *args: row_sent_events.append(args))

        worker.run()

    smtp_ctor.assert_called_once_with("smtp.example.com", 587, timeout=30)
    smtp_ssl_ctor.assert_not_called()
    transport.starttls.assert_called_once()
    transport.login.assert_called_once_with("recruiter@example.com", "app-password")
    assert transport.sendmail.call_count == 1
    envelope_from, envelope_to, message_text = transport.sendmail.call_args[0]
    assert envelope_from == "recruiter@example.com"
    assert envelope_to == ["recruiter@example.com"]
    sent_message = email.message_from_string(message_text)
    assert sent_message["Subject"] == "Test email"
    assert sent_message.get_payload(decode=True).decode("utf-8") == "This is a test message."
    transport.quit.assert_called_once()

    assert row_sent_events == [(-1, True, "")]
    assert done_messages == ["Sent 1 of 1 message(s)."]


def test_smtp_worker_sends_bulk_messages_via_ssl():
    transport = _make_transport()
    messages = [
        (0, "alice@example.com", "You're in", "Congrats Alice"),
        (1, "bob@example.com", "Update", "Sorry Bob"),
        (2, "carol@example.com", "You're in", "Congrats Carol"),
    ]

    with patch("qml_gui.smtplib.SMTP_SSL", return_value=transport) as smtp_ssl_ctor, patch(
        "qml_gui.smtplib.SMTP"
    ) as smtp_ctor:
        worker = qml_gui.SmtpWorker(
            "smtp.example.com", 465, "recruiter@example.com", "app-password", messages
        )
        row_sent_events = []
        done_messages = []
        worker.row_sent.connect(lambda *args: row_sent_events.append(args))
        worker.done.connect(done_messages.append)

        worker.run()

    smtp_ssl_ctor.assert_called_once_with("smtp.example.com", 465, timeout=30)
    smtp_ctor.assert_not_called()
    transport.starttls.assert_not_called()
    assert transport.sendmail.call_count == 3
    assert row_sent_events == [(0, True, ""), (1, True, ""), (2, True, "")]
    assert done_messages == ["Sent 3 of 3 message(s)."]


def test_smtp_worker_one_failure_does_not_stop_the_batch():
    transport = _make_transport()

    def fake_sendmail(from_addr, to_addrs, message_text):
        if "bob@example.com" in to_addrs:
            raise RuntimeError("mailbox unavailable")

    transport.sendmail.side_effect = fake_sendmail

    messages = [
        (0, "alice@example.com", "You're in", "Congrats Alice"),
        (1, "bob@example.com", "Update", "Sorry Bob"),
        (2, "carol@example.com", "You're in", "Congrats Carol"),
    ]

    with patch("qml_gui.smtplib.SMTP", return_value=transport), patch("qml_gui.smtplib.SMTP_SSL"):
        worker = qml_gui.SmtpWorker(
            "smtp.example.com", 587, "recruiter@example.com", "app-password", messages
        )
        row_sent_events = []
        done_messages = []
        failed_messages = []
        worker.row_sent.connect(lambda *args: row_sent_events.append(args))
        worker.done.connect(done_messages.append)
        worker.failed.connect(failed_messages.append)

        worker.run()

    assert transport.sendmail.call_count == 3
    assert row_sent_events[0] == (0, True, "")
    assert row_sent_events[1][0] == 1
    assert row_sent_events[1][1] is False
    assert "mailbox unavailable" in row_sent_events[1][2]
    assert row_sent_events[2] == (2, True, "")

    assert failed_messages == []
    assert done_messages == ["Sent 2 of 3 message(s). 1 failed."]


def test_smtp_worker_reports_row_failure_for_missing_email():
    transport = _make_transport()

    with patch("qml_gui.smtplib.SMTP", return_value=transport), patch("qml_gui.smtplib.SMTP_SSL"):
        worker = qml_gui.SmtpWorker(
            "smtp.example.com",
            587,
            "recruiter@example.com",
            "app-password",
            [(5, "", "Subject", "Body")],
        )
        row_sent_events = []
        worker.row_sent.connect(lambda *args: row_sent_events.append(args))
        worker.run()

    transport.sendmail.assert_not_called()
    assert len(row_sent_events) == 1
    assert row_sent_events[0][0] == 5
    assert row_sent_events[0][1] is False


def test_smtp_worker_failed_signal_when_password_missing():
    failed_messages = []
    with patch("qml_gui.smtplib.SMTP") as smtp_ctor, patch("qml_gui.smtplib.SMTP_SSL"):
        worker = qml_gui.SmtpWorker(
            "smtp.example.com", 587, "recruiter@example.com", "", [(-1, "a@example.com", "s", "b")]
        )
        worker.failed.connect(failed_messages.append)
        worker.run()

    smtp_ctor.assert_not_called()
    assert len(failed_messages) == 1
    assert "app password" in failed_messages[0].lower()

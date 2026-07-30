"""Reminder dispatch fires at 3 days, 1 day and 1 hour — each exactly once."""

from datetime import datetime, timedelta

import pytest

import services.email_service as email_service
from services.email_service import _process_due_reminders, _render_reminder_subject


class FakeReminder:
    def __init__(self, event_date, **flags):
        self.id = 1
        self.title = "Mülakat"
        self.description = ""
        self.reminder_type = "interview"
        self.target_email = "user@example.com"
        self.event_date = event_date
        self.is_active = True
        self.notified_3d_at = flags.get("d3")
        self.notified_1d_at = flags.get("d1")
        self.notified_1h_at = flags.get("h1")


class FakeQuery:
    def __init__(self, reminder, id_mode):
        self._reminder = reminder
        self._id_mode = id_mode

    def filter(self, *args, **kwargs):
        return self

    def with_for_update(self, *args, **kwargs):
        return self

    def all(self):
        return [(self._reminder.id,)] if self._id_mode else []

    def first(self):
        return self._reminder


class FakeDB:
    def __init__(self, reminder):
        self._reminder = reminder
        self.committed = False

    def query(self, entity):
        # The dispatcher first queries Reminder.id, then the Reminder itself.
        id_mode = not hasattr(entity, "event_date")
        return FakeQuery(self._reminder, id_mode)

    def add(self, _obj):
        pass

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


@pytest.fixture
def sent(monkeypatch):
    calls = []

    def _fake_send(reminder, days_left, recipient, hours=False):
        calls.append({"days_left": days_left, "hours": hours, "to": recipient})
        return True

    monkeypatch.setattr(email_service, "_send_reminder_email", _fake_send)
    return calls


def _run(reminder):
    db = FakeDB(reminder)
    _process_due_reminders(db)
    return db


class TestHourReminder:
    def test_fires_one_hour_before(self, sent):
        r = FakeReminder(datetime.utcnow() + timedelta(minutes=40), d3=datetime.utcnow(), d1=datetime.utcnow())
        _run(r)
        assert len(sent) == 1
        assert sent[0]["hours"] is True
        assert r.notified_1h_at is not None

    def test_does_not_fire_twice(self, sent):
        already = datetime.utcnow()
        r = FakeReminder(
            datetime.utcnow() + timedelta(minutes=40), d3=already, d1=already, h1=already
        )
        _run(r)
        assert sent == []

    def test_day_reminder_still_fires_outside_hour_window(self, sent):
        r = FakeReminder(datetime.utcnow() + timedelta(hours=20), d3=datetime.utcnow())
        _run(r)
        assert len(sent) == 1
        assert sent[0]["hours"] is False
        assert r.notified_1d_at is not None
        assert r.notified_1h_at is None

    def test_same_day_event_does_not_chase_a_day_mail_afterwards(self, sent):
        # Created inside the 1-hour window: the day mail is moot, so it must be
        # marked as handled rather than sent late.
        r = FakeReminder(datetime.utcnow() + timedelta(minutes=30))
        _run(r)
        assert len(sent) == 1
        assert sent[0]["hours"] is True
        assert r.notified_1d_at is not None


class TestSubjectWording:
    def test_hour_subject_says_saat(self):
        r = FakeReminder(datetime.utcnow() + timedelta(minutes=30))
        assert "1 saat kaldı" in _render_reminder_subject(r, 0, hours=True)

    def test_day_subject_unchanged(self):
        r = FakeReminder(datetime.utcnow() + timedelta(days=3))
        assert "3 gün kaldı" in _render_reminder_subject(r, 3)
        assert "1 gün kaldı" in _render_reminder_subject(r, 1)

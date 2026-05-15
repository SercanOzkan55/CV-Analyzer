"""Email sending (SMTP + SendGrid) and reminder worker.

Extracted from ``main.py`` to reduce monolith size.
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import time
import threading as _threading
from datetime import datetime, timedelta
from email.message import EmailMessage

from fastapi import HTTPException

from database import SessionLocal
from models import Reminder
from security.redaction import redact_for_log
from sqlalchemy import or_

logger = logging.getLogger("app.email")


def _env_bool(name: str, default: bool = False) -> bool:
    value = str(os.getenv(name, "")).strip().lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "on")


# ── Feedback ─────────────────────────────────────────────────────────────

def _append_feedback_record(record: dict):
    """Persist feedback as JSONL for lightweight bug triage in dev/prod."""
    try:
        feedback_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "feedback_records.jsonl")
        with open(feedback_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _read_feedback_records(
    limit: int = 50,
    supabase_id: str | None = None,
    include_all: bool = False,
) -> list[dict]:
    """Read feedback JSONL records from disk, newest first."""
    feedback_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "feedback_records.jsonl")
    if not os.path.exists(feedback_path):
        return []

    records: list[dict] = []
    try:
        with open(feedback_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return []

    for raw in reversed(lines):
        if len(records) >= limit:
            break
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue

        if not include_all and supabase_id:
            if str(item.get("supabase_id") or "") != str(supabase_id):
                continue
        records.append(item)

    return records


def _send_feedback_email(record: dict) -> bool:
    """Send feedback notification mail if SMTP env vars are configured."""
    smtp_host = str(os.getenv("SMTP_HOST", "")).strip()
    try:
        smtp_port = int(str(os.getenv("SMTP_PORT", "587") or "587"))
    except Exception:
        smtp_port = 587
    smtp_user = str(os.getenv("SMTP_USER", "")).strip()
    smtp_pass = str(os.getenv("SMTP_PASS", "")).strip()
    smtp_from = str(
        os.getenv("FEEDBACK_EMAIL_FROM")
        or os.getenv("SMTP_FROM")
        or smtp_user
        or ""
    ).strip()
    smtp_to = str(
        os.getenv("FEEDBACK_EMAIL_TO")
        or os.getenv("SUPPORT_EMAIL")
        or "sikayet.cvanalizor@gmail.com"
        or ""
    ).strip()

    if not smtp_host or not smtp_from or not smtp_to:
        return False

    use_ssl = _env_bool("SMTP_USE_SSL", default=False)
    use_tls = _env_bool("SMTP_USE_TLS", default=True)

    msg = EmailMessage()
    msg["From"] = smtp_from
    msg["To"] = smtp_to
    sender_email = str(record.get("email") or "").strip()
    if sender_email and "@" in sender_email:
        msg["Reply-To"] = sender_email
    msg["Subject"] = (
        f"[CV Analyzer][Feedback] {record.get('category', 'other')} - {record.get('email', 'unknown')}"
    )

    body = [
        "New feedback submitted:",
        "",
        f"Timestamp: {record.get('timestamp', '-')}",
        f"Category: {record.get('category', '-')}",
        f"Sender Email: {record.get('email', '-')}",
        f"User ID: {record.get('user_id', '-')}",
        f"Supabase ID: {record.get('supabase_id', '-')}",
        f"Page: {record.get('page', '-')}",
        f"Language: {record.get('lang', '-')}",
        f"Score: {record.get('score', '-')}",
        "",
        "Message:",
        str(record.get("message", "")),
        "",
        "Context:",
        json.dumps(record.get("context") or {}, ensure_ascii=False, indent=2),
    ]
    msg.set_content("\n".join(body))

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        with server:
            if not use_ssl and use_tls:
                server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True
    except Exception:
        logger.exception("feedback email send failed")
        return False


# ── General email ────────────────────────────────────────────────────────

def _do_send_email(to_email: str, subject: str, body: str, recruiter_email: str = "") -> bool:
    """Send email via SMTP or SendGrid."""
    from email.utils import formataddr

    _logger = logging.getLogger("app.recruiter.email")
    default_from = (os.environ.get("REMINDER_EMAIL_FROM") or "sikayet.cvanalizor@gmail.com").strip()

    # Try SendGrid first
    sendgrid_key = os.environ.get("SENDGRID_API_KEY", "")
    if sendgrid_key:
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content, Header

            sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
            platform_from = (os.environ.get("SENDGRID_FROM_EMAIL") or default_from).strip()
            if recruiter_email and recruiter_email != platform_from:
                from_email = Email(platform_from, name=recruiter_email)
            else:
                from_email = Email(platform_from)
            mail = Mail(
                from_email=from_email,
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=Content("text/plain", body),
            )
            if recruiter_email:
                mail.reply_to = Email(recruiter_email)
            response = sg.client.mail.send.post(request_body=mail.get())
            _logger.info(
                "sendgrid_sent to=%s reply_to=%s status=%s",
                redact_for_log(to_email, key="to_email"),
                redact_for_log(recruiter_email, key="recruiter_email"),
                response.status_code,
            )
            return response.status_code in (200, 201, 202)
        except Exception as e:
            _logger.error("sendgrid_failed to=%s error=%s", redact_for_log(to_email, key="to_email"), e)

    # Fallback to SMTP
    smtp_host = os.environ.get("SMTP_HOST", "")
    if smtp_host:
        try:
            from email.mime.text import MIMEText

            smtp_port = int(os.environ.get("SMTP_PORT", "587"))
            smtp_user = os.environ.get("SMTP_USER", "")
            smtp_pass = os.environ.get("SMTP_PASS", "")
            platform_from = (os.environ.get("SMTP_FROM") or default_from).strip()

            if recruiter_email and recruiter_email != platform_from:
                from_display = formataddr((recruiter_email, platform_from))
            else:
                from_display = platform_from

            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = from_display
            msg["To"] = to_email
            if recruiter_email:
                msg["Reply-To"] = recruiter_email

            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.starttls()
                if smtp_user:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(platform_from, [to_email], msg.as_string())

            _logger.info(
                "smtp_sent to=%s reply_to=%s",
                redact_for_log(to_email, key="to_email"),
                redact_for_log(recruiter_email, key="recruiter_email"),
            )
            return True
        except Exception as e:
            _logger.error("smtp_failed to=%s error=%s", redact_for_log(to_email, key="to_email"), e)

    _logger.warning("no_email_backend configured, email not sent to=%s", redact_for_log(to_email, key="to_email"))
    return False


# ── Reminders ────────────────────────────────────────────────────────────

def _validate_reminder_email(email: str) -> str:
    candidate_email = (email or "").strip()
    if "@" not in candidate_email or "." not in candidate_email:
        raise HTTPException(status_code=400, detail="target_email must be a valid email address")
    return candidate_email


def _reminder_type_label(value: str) -> str:
    labels = {
        "interview": "Mülakat",
        "deadline": "Son Başvuru Tarihi",
        "follow_up": "Takip",
        "offer": "Teklif Değerlendirme",
        "other": "Hatırlatma",
    }
    return labels.get((value or "").strip().lower(), "Hatırlatma")


def _render_reminder_subject(reminder: Reminder, days_left: int) -> str:
    label = _reminder_type_label(reminder.reminder_type)
    day_text = "1 gün kaldı" if int(days_left) <= 1 else f"{int(days_left)} gün kaldı"
    return f"[CV Analyzer] {label}: {reminder.title} - {day_text}"


def _render_reminder_body(reminder: Reminder, days_left: int) -> str:
    event_date = reminder.event_date.strftime("%Y-%m-%d %H:%M")
    label = _reminder_type_label(reminder.reminder_type)
    day_text = "1 gün kaldı" if int(days_left) <= 1 else f"{int(days_left)} gün kaldı"
    body_lines = [
        "Merhaba,",
        "",
        "CV Analyzer hatırlatması:",
        f"Etkinlik: {label}",
        f"Başlık: {reminder.title}",
        f"Tarih: {event_date}",
        f"Kalan süre: {day_text}.",
    ]
    if reminder.description:
        body_lines.extend(["", "Notlar:", reminder.description.strip()])
    body_lines.extend([
        "",
        "Kısa kontrol listesi:",
        "- CV ve iş ilanını tekrar gözden geçir.",
        "- Görüşme linkini, adresi veya son teklif tarihini kontrol et.",
        "- Sorularını ve takip notlarını hazırla.",
        "",
        "Bu hatırlatma otomatik olarak gönderildi."
    ])
    return "\n".join(body_lines)


def _send_reminder_email(reminder: Reminder, days_left: int, recipient: str) -> bool:
    subject = _render_reminder_subject(reminder, days_left)
    body = _render_reminder_body(reminder, days_left)
    return _do_send_email(
        to_email=recipient,
        subject=subject,
        body=body,
        recruiter_email="",
    )


def _process_due_reminders(db):
    now = datetime.utcnow()
    today = now.date()
    window_end = datetime.combine(today + timedelta(days=3), datetime.max.time())
    reminders = (
        db.query(Reminder)
        .filter(
            Reminder.is_active == True,
            Reminder.event_date > now,
            Reminder.event_date <= window_end,
            or_(Reminder.notified_3d_at.is_(None), Reminder.notified_1d_at.is_(None)),
        )
        .all()
    )
    for reminder in reminders:
        if reminder.event_date <= now:
            continue
        days_left = (reminder.event_date.date() - today).days
        recipient = reminder.target_email or ""
        if not recipient:
            continue
        if reminder.notified_1d_at is None and days_left <= 1:
            if _send_reminder_email(reminder, 1, recipient):
                reminder.notified_1d_at = now
                db.add(reminder)
                db.commit()
            continue
        if (
            reminder.notified_3d_at is None
            and reminder.notified_1d_at is None
            and days_left == 3
        ):
            if _send_reminder_email(reminder, 3, recipient):
                reminder.notified_3d_at = now
                db.add(reminder)
                db.commit()


def _start_reminder_worker():
    interval = int(os.getenv("REMINDER_CHECK_INTERVAL_SECONDS", "3600"))

    def _loop():
        while True:
            try:
                db = SessionLocal()
                _process_due_reminders(db)
            except Exception as exc:
                logger.exception("reminder_worker: failed to process due reminders: %s", exc)
            finally:
                try:
                    db.close()
                except Exception:
                    pass
            time.sleep(interval)

    thread = _threading.Thread(target=_loop, daemon=True, name="reminder-worker")
    thread.start()

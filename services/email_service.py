"""Email sending (SMTP + SendGrid) and reminder worker.

Extracted from ``main.py`` to reduce monolith size.
"""

from __future__ import annotations
from core.timeutils import utcnow

import json
import logging
import os
import smtplib
import time
import threading as _threading
from datetime import datetime, timedelta

from fastapi import HTTPException

from database import SessionLocal
from models import Reminder
from security.redaction import redact_for_log
from sqlalchemy import or_

logger = logging.getLogger("app.email")
DEFAULT_SUPPORT_EMAIL = "sikayet.cvanalizor@gmail.com"


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


def _feedback_email_recipients() -> list[str]:
    raw = str(os.getenv("FEEDBACK_EMAIL_TO") or os.getenv("SUPPORT_EMAIL") or DEFAULT_SUPPORT_EMAIL or "").strip()
    return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip() and "@" in item]


def _feedback_email_body(record: dict) -> str:
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
    return "\n".join(body)


def _send_feedback_email(record: dict) -> bool:
    """Send feedback notification mail through the configured transactional email backend."""
    recipients = _feedback_email_recipients()
    if not recipients:
        logger.warning("feedback email skipped: no recipient configured")
        return False

    if not os.getenv("SENDGRID_API_KEY") and not os.getenv("SMTP_HOST"):
        logger.warning(
            "feedback email skipped: no email backend configured for to=%s",
            redact_for_log(",".join(recipients), key="to_email"),
        )
        return False

    try:
        subject = f"[CV Analyzer][Feedback] {record.get('category', 'other')} - {record.get('email', 'unknown')}"
        body = _feedback_email_body(record)
        reply_to = str(record.get("email") or "").strip()
        sent_results = [
            _do_send_email(
                recipient,
                subject,
                body,
                recruiter_email=reply_to if "@" in reply_to else "",
            )
            for recipient in recipients
        ]
        return bool(sent_results) and all(sent_results)
    except Exception:
        logger.exception("feedback email send failed")
        return False


# ── General email ────────────────────────────────────────────────────────


def _do_send_email(to_email: str, subject: str, body: str, recruiter_email: str = "") -> bool:
    """Send email via SMTP or SendGrid with retry support (3 attempts, exponential backoff)."""
    from email.utils import formataddr

    _logger = logging.getLogger("app.recruiter.email")
    default_from = (
        os.environ.get("REMINDER_EMAIL_FROM")
        or os.environ.get("FEEDBACK_EMAIL_FROM")
        or os.environ.get("SMTP_FROM")
        or DEFAULT_SUPPORT_EMAIL
    ).strip()

    max_attempts = 3
    backoff = 2.0

    for attempt in range(1, max_attempts + 1):
        try:
            # Try SendGrid first
            sendgrid_key = os.environ.get("SENDGRID_API_KEY", "")
            if sendgrid_key:
                try:
                    import sendgrid
                    from sendgrid.helpers.mail import Mail, Email, To, Content

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

                    if response.status_code in (200, 201, 202):
                        _logger.info(
                            "sendgrid_sent to=%s reply_to=%s status=%s attempt=%d",
                            redact_for_log(to_email, key="to_email"),
                            redact_for_log(recruiter_email, key="recruiter_email"),
                            response.status_code,
                            attempt,
                        )
                        return True
                    else:
                        raise RuntimeError(f"SendGrid responded with status {response.status_code}")
                except Exception as e:
                    _logger.error(
                        "sendgrid_failed to=%s error=%s attempt=%d",
                        redact_for_log(to_email, key="to_email"),
                        e,
                        attempt,
                    )
                    if not os.environ.get("SMTP_HOST", ""):
                        raise e

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

                    use_ssl = _env_bool("SMTP_USE_SSL", default=False)
                    use_tls = _env_bool("SMTP_USE_TLS", default=True)
                    if use_ssl:
                        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
                    else:
                        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                    with server:
                        if not use_ssl and use_tls:
                            server.starttls()
                        if smtp_user:
                            server.login(smtp_user, smtp_pass)
                        server.sendmail(platform_from, [to_email], msg.as_string())

                    _logger.info(
                        "smtp_sent to=%s reply_to=%s attempt=%d",
                        redact_for_log(to_email, key="to_email"),
                        redact_for_log(recruiter_email, key="recruiter_email"),
                        attempt,
                    )
                    return True
                except Exception as e:
                    _logger.error(
                        "smtp_failed to=%s error=%s attempt=%d", redact_for_log(to_email, key="to_email"), e, attempt
                    )
                    raise e

            _logger.warning(
                "no_email_backend configured, email not sent to=%s", redact_for_log(to_email, key="to_email")
            )
            return False

        except Exception as exc:
            if attempt == max_attempts:
                _logger.error(
                    "all_email_attempts_failed to=%s final_error=%s", redact_for_log(to_email, key="to_email"), exc
                )
                return False
            _logger.info("email_retry_pending to=%s backoff=%.1fs", redact_for_log(to_email, key="to_email"), backoff)
            time.sleep(backoff)
            backoff *= 2.0

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
    body_lines.extend(
        [
            "",
            "Kısa kontrol listesi:",
            "- CV ve iş ilanını tekrar gözden geçir.",
            "- Görüşme linkini, adresi veya son teklif tarihini kontrol et.",
            "- Sorularını ve takip notlarını hazırla.",
            "",
            "Bu hatırlatma otomatik olarak gönderildi.",
        ]
    )
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
    now = utcnow()
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
        if reminder.notified_3d_at is None and reminder.notified_1d_at is None and days_left == 3:
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

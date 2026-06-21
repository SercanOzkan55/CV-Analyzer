import io
import json
import logging
import os
from datetime import datetime, timedelta
from email.utils import formataddr

from fastapi import HTTPException, UploadFile
from sqlalchemy import or_

from config.aws import MAX_PDF_OBJECTS, MAX_PDF_PAGES, MAX_UPLOAD_BYTES
from database import engine
from models import Reminder
from security.redaction import redact_for_log

_MAX_SEARCH_QUERY_LEN = int(os.getenv("MAX_SEARCH_QUERY_LEN", "500"))
_MAX_PDF_PAGES = MAX_PDF_PAGES
_MAX_PDF_OBJECTS = MAX_PDF_OBJECTS
_MAX_PDF_EXTRACTED_CHARS = 60_000


def _format_bytes(value: int) -> str:
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.0f} MB"
    if value >= 1024:
        return f"{value / 1024:.0f} KB"
    return f"{value} bytes"


def _is_postgres_engine() -> bool:
    try:
        url = getattr(engine, "url", None)
        if not url:
            return False
        return str(url.get_backend_name()).startswith("postgres")
    except Exception:
        return False


def _validate_pdf_upload(contents: bytes, content_type: str | None) -> None:
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")
    if content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large (max {_format_bytes(MAX_UPLOAD_BYTES)})",
        )
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    obj_count = contents.count(b" obj")
    if obj_count > _MAX_PDF_OBJECTS:
        logging.getLogger("app.security").warning("pdf_rejected: too many objects %d > %d", obj_count, _MAX_PDF_OBJECTS)
        raise HTTPException(status_code=400, detail="PDF too complex (too many objects)")

    page_count = contents.count(b"/Type /Page") - contents.count(b"/Type /Pages")
    if page_count > _MAX_PDF_PAGES:
        logging.getLogger("app.security").warning("pdf_rejected: too many pages %d > %d", page_count, _MAX_PDF_PAGES)
        raise HTTPException(status_code=400, detail=f"PDF too large (max {_MAX_PDF_PAGES} pages)")

    try:
        from services.pdf_runtime import _scan_upload_for_viruses

        _scan_upload_for_viruses(contents)
    except HTTPException:
        raise
    except Exception:
        if os.getenv("CLAMAV_ENABLED", "0").lower() in ("1", "true", "yes"):
            raise HTTPException(status_code=500, detail="Virus scanner error")


def _extract_pdf_text(contents: bytes) -> tuple[str, bool]:
    """Extract plain text from PDF bytes using coordinate-based layout analysis.

    Uses pdfplumber word positions to detect and properly reconstruct
    multi-column layouts. Falls back to PyPDF2 if pdfplumber fails.

    Returns (text, truncated) where truncated is True if content was capped.
    """
    from services.pdf_text_extractor import extract_pdf_text

    return extract_pdf_text(
        contents,
        max_pages=_MAX_PDF_PAGES,
        max_chars=_MAX_PDF_EXTRACTED_CHARS,
    )

    from renderers.blocks import fix_decomposed_diacritics

    # ── Primary: pdfplumber with coordinate-based column detection ──
    try:
        import pdfplumber

        left_lines: list[str] = []
        right_lines: list[str] = []
        is_multi_col = False
        col_boundary = 0.0

        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            # ── Security: reject PDFs with too many pages ──
            if len(pdf.pages) > _MAX_PDF_PAGES:
                logging.getLogger("app.security").warning("pdf_pages_limit: %d > %d", len(pdf.pages), _MAX_PDF_PAGES)
                raise HTTPException(
                    status_code=400,
                    detail=f"PDF too large (max {_MAX_PDF_PAGES} pages)",
                )
            # ── First pass: detect column layout across ALL pages ──
            all_page_gaps: list[float] = []
            total_both = 0
            total_content = 0
            page_widths: list[float] = []

            for page in pdf.pages:
                words = page.extract_words()
                if not words:
                    continue
                page_w = page.width
                page_widths.append(page_w)

                rows: dict[float, list] = {}
                for w in words:
                    row_key = round(w["top"] / 3) * 3
                    rows.setdefault(row_key, []).append(w)

                for row_words in rows.values():
                    sorted_rw = sorted(row_words, key=lambda w: w["x0"])
                    row_span = sorted_rw[-1]["x1"] - sorted_rw[0]["x0"] if len(sorted_rw) > 1 else 0
                    # Skip rows that span less than 30% — likely single-column header rows
                    if row_span < page_w * 0.30:
                        continue
                    total_content += 1
                    max_gap = 0
                    max_gap_pos = page_w / 2
                    for i in range(len(sorted_rw) - 1):
                        gap = sorted_rw[i + 1]["x0"] - sorted_rw[i]["x1"]
                        if gap > max_gap:
                            max_gap = gap
                            max_gap_pos = (sorted_rw[i]["x1"] + sorted_rw[i + 1]["x0"]) / 2
                    if max_gap > 20:
                        all_page_gaps.append(max_gap_pos)
                        total_both += 1

            total_content = max(total_content, 1)
            # Relax thresholds: 2 gap rows and >15% of content rows
            if total_both >= 2 and total_both > total_content * 0.15:
                is_multi_col = True
                all_page_gaps.sort()
                col_boundary = all_page_gaps[len(all_page_gaps) // 2]

            # ── Second pass: extract text using detected layout ──
            for page in pdf.pages:
                words = page.extract_words()
                if not words:
                    continue

                page_w = page.width
                mid = col_boundary if is_multi_col else page_w / 2

                if is_multi_col:
                    # Separate wide-header rows (span both columns) from column rows
                    header_rows_lines: list[str] = []
                    page_left: list[str] = []
                    page_right: list[str] = []

                    rows_by_top: dict[float, list] = {}
                    for w in words:
                        row_key = round(w["top"] / 3) * 3
                        rows_by_top.setdefault(row_key, []).append(w)

                    for row_key in sorted(rows_by_top.keys()):
                        row_words = sorted(rows_by_top[row_key], key=lambda w: w["x0"])
                        # Check if row spans both columns (wide header)
                        has_left = any(w["x0"] < mid - 5 for w in row_words)
                        has_right = any(w["x1"] > mid + 5 for w in row_words)
                        # Measure gap at column boundary
                        max_gap_at_mid = 0
                        for i in range(len(row_words) - 1):
                            gap = row_words[i + 1]["x0"] - row_words[i]["x1"]
                            gap_pos = (row_words[i]["x1"] + row_words[i + 1]["x0"]) / 2
                            if abs(gap_pos - mid) < page_w * 0.15 and gap > max_gap_at_mid:
                                max_gap_at_mid = gap

                        if has_left and has_right and max_gap_at_mid < 15:
                            # Wide row spanning both columns — treat as header/full-width
                            header_rows_lines.append(" ".join(w["text"] for w in row_words))
                        else:
                            # Split into left/right columns
                            left_words = [w for w in row_words if w["x0"] < mid]
                            right_words = [w for w in row_words if w["x0"] >= mid]
                            if left_words:
                                page_left.append(" ".join(w["text"] for w in left_words))
                            if right_words:
                                page_right.append(" ".join(w["text"] for w in right_words))

                    # Prepend wide-header lines (name, contact) before columns
                    if header_rows_lines:
                        left_lines.extend(header_rows_lines)
                        left_lines.append("")

                    # Accumulate column lines per page
                    if page_left:
                        left_lines.extend(page_left)
                    if page_right:
                        right_lines.extend(page_right)

                    # Blank line as page separator
                    left_lines.append("")
                else:
                    # Single column: extract normally
                    all_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
                    cur_top = all_words[0]["top"]
                    cur_line: list[str] = []
                    for w in all_words:
                        if w["top"] - cur_top > 3:
                            if cur_line:
                                left_lines.append(" ".join(cur_line))
                            cur_line = [w["text"]]
                            cur_top = w["top"]
                        else:
                            cur_line.append(w["text"])
                    if cur_line:
                        left_lines.append(" ".join(cur_line))

        if is_multi_col:
            # Determine sidebar vs main: the column with more content is "main" and goes first.
            # This ensures experience/education (main) appear before skills/languages (sidebar).
            left_text = "\n".join(left_lines).strip()
            right_text = "\n".join(right_lines).strip()
            left_len = len(left_text.replace("\n", "").replace(" ", ""))
            right_len = len(right_text.replace("\n", "").replace(" ", ""))

            if left_len >= right_len:
                raw = left_text + "\n\n" + right_text
            else:
                raw = right_text + "\n\n" + left_text
            raw = "multi_col_fixed\n" + raw
        else:
            raw = "\n".join(left_lines)

        raw = raw.strip()
        if raw:
            # Security: cap extracted text length
            truncated = len(raw) > _MAX_PDF_EXTRACTED_CHARS
            if truncated:
                raw = raw[:_MAX_PDF_EXTRACTED_CHARS]
            return fix_decomposed_diacritics(raw), truncated

    except Exception:
        pass  # Fall through to PyPDF2

    # ── Fallback: PyPDF2 ──
    try:
        import PyPDF2

        pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    # Security: cap page count in fallback path
    pages = pdf_reader.pages
    if len(pages) > _MAX_PDF_PAGES:
        pages = pages[:_MAX_PDF_PAGES]

    text_parts = []
    for page in pages:
        extracted = page.extract_text()
        if extracted:
            text_parts.append(extracted)
    raw = "\n".join(text_parts).strip()
    # Security: cap extracted text length
    truncated = len(raw) > _MAX_PDF_EXTRACTED_CHARS
    if truncated:
        logging.getLogger("app.security").warning("pdf_text_truncated: %d > %d", len(raw), _MAX_PDF_EXTRACTED_CHARS)
        raw = raw[:_MAX_PDF_EXTRACTED_CHARS]
    return fix_decomposed_diacritics(raw), truncated


async def _resolve_job_description_text(
    job_description: str = "",
    jd_file: UploadFile | None = None,
) -> str:
    direct = (job_description or "").strip()
    if direct:
        return direct

    if jd_file is None:
        raise HTTPException(status_code=400, detail="Job description is required")

    contents = await jd_file.read()
    if len(contents) > 1_000_000:
        raise HTTPException(status_code=400, detail="Job description file too large")

    ctype = (jd_file.content_type or "").lower()
    if ctype == "application/pdf":
        if not contents.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Invalid JD PDF file")
        text, _ = _extract_pdf_text(contents)
        return text

    if ctype in ("text/plain", "application/octet-stream", ""):
        return contents.decode("utf-8", errors="ignore").strip()

    raise HTTPException(
        status_code=400,
        detail="Unsupported JD file type (use text/plain or application/pdf)",
    )


def _do_send_email(
    to_email: str,
    subject: str,
    body: str,
    recruiter_email: str = "",
) -> bool:
    _logger = logging.getLogger("app.recruiter.email")
    default_from = (os.environ.get("REMINDER_EMAIL_FROM") or "sikayet.cvanalizor@gmail.com").strip()

    sendgrid_key = os.environ.get("SENDGRID_API_KEY", "")
    if sendgrid_key:
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content

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
            response = sendgrid.SendGridAPIClient(api_key=sendgrid_key).client.mail.send.post(request_body=mail.get())
            _logger.info(
                "sendgrid_sent to=%s reply_to=%s status=%s",
                redact_for_log(to_email, key="to_email"),
                redact_for_log(recruiter_email, key="recruiter_email"),
                response.status_code,
            )
            return response.status_code in (200, 201, 202)
        except Exception as e:
            _logger.error("sendgrid_failed to=%s error=%s", redact_for_log(to_email, key="to_email"), e)

    smtp_host = os.environ.get("SMTP_HOST", "")
    if smtp_host:
        try:
            import smtplib
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


def _validate_reminder_email(email: str) -> str:
    candidate_email = (email or "").strip()
    if "@" not in candidate_email or "." not in candidate_email:
        raise HTTPException(status_code=400, detail="target_email must be a valid email address")
    return candidate_email


def _reminder_type_label(value: str) -> str:
    labels = {
        "interview": "Mülakat",
        "offer": "Teklif",
        "deadline": "Son tarih",
        "follow_up": "Takip",
        "other": "Hatırlatma",
    }
    return labels.get(str(value or "").strip().lower(), "Hatırlatma")


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
        if reminder.notified_3d_at is None and reminder.notified_1d_at is None and days_left == 3:
            if _send_reminder_email(reminder, 3, recipient):
                reminder.notified_3d_at = now
                db.add(reminder)
                db.commit()


def _ensure_not_expired(user_payload: dict):
    if isinstance(user_payload, dict) and user_payload.get("signature"):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    payload = user_payload.get("payload") if isinstance(user_payload, dict) else None
    exp = payload.get("exp") if isinstance(payload, dict) else None
    if exp is None:
        return
    try:
        exp_ts = int(exp)
    except (TypeError, ValueError):
        return
    if exp_ts <= int(datetime.utcnow().timestamp()):
        raise HTTPException(status_code=401, detail="Token expired")

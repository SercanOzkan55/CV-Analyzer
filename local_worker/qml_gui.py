import csv
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import traceback
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger("local_worker.gui")

try:
    from PySide6.QtCore import (
        QAbstractListModel,
        QByteArray,
        QModelIndex,
        QObject,
        Property,
        QCoreApplication,
        QThread,
        QUrl,
        Qt,
        Signal,
        Slot,
    )
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle
except ImportError:
    from ctypes import windll

    message = (
        "PySide6 with Qt Quick is required for the Local Worker app.\n\n"
        "Run install_windows.cmd or start_here.cmd again so dependencies are installed."
    )
    try:
        windll.user32.MessageBoxW(None, message, "CV Analyzer Local Worker", 0x10)
    except Exception:
        print(message, file=sys.stderr)
    sys.exit(1)

import worker as worker_module
from credentials import load_worker_api_key, save_worker_api_key
from worker import (
    API_BASE_URL,
    MAX_FILE_BYTES,
    LocalWorker,
    csv_safe,
    extract_text,
    iter_supported_local_files,
    maybe_apply_ai_review,
    score_cv,
)
from workspace import WorkspaceStore


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def resource_path(relative_path: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    path = Path(base) / "CV Analyzer Local Worker"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_crash_log(detail: str) -> Path:
    path = app_data_dir() / "crash.log"
    path.write_text(detail, encoding="utf-8")
    return path


def load_mail_templates() -> dict:
    path = app_data_dir() / "mail_templates.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "accept_subject": "Update regarding your application at CV Analyzer",
        "accept_body": (
            "Hi {name},\n\n"
            "Thank you for your application. We reviewed your CV and would like to move forward. "
            "Our team will contact you soon with the next steps.\n\n"
            "Best regards,\nRecruiting Team"
        ),
        "reject_subject": "Update regarding your application at CV Analyzer",
        "reject_body": (
            "Hi {name},\n\n"
            "Thank you for your interest. After reviewing your CV, we will not be moving forward with your application for this opening.\n\n"
            "Best regards,\nRecruiting Team"
        ),
    }


def save_mail_templates(data: dict):
    path = app_data_dir() / "mail_templates.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def decision_label(decision: str) -> str:
    return {
        "recommended_accept": "Accept",
        "recommended_review": "Review",
        "recommended_reject": "Reject",
        "accepted": "Accepted",
        "rejected": "Rejected",
        "pending": "Pending",
    }.get(decision or "", decision or "Pending")


def decision_rank(decision: str) -> int:
    return {"recommended_accept": 0, "recommended_review": 1, "recommended_reject": 2}.get(decision, 3)


def decision_accent(decision: str) -> str:
    if decision in {"recommended_accept", "accepted"}:
        return "#38d39f"
    if decision == "recommended_review":
        return "#f2c572"
    if decision in {"recommended_reject", "rejected"}:
        return "#ff647c"
    return "#8ea0ff"


def list_to_text(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    return str(value or "")


def permission_summary(permissions: dict | None) -> str:
    if not isinstance(permissions, dict) or not permissions:
        return "Default access: claim CVs and submit local results."
    claim = bool(permissions.get("claim", True))
    submit = bool(permissions.get("submit_results", True))
    labels = [
        f"Claim CVs: {'allowed' if claim else 'blocked'}",
        f"Submit results: {'allowed' if submit else 'blocked'}",
    ]
    extra = [
        f"{key}: {'allowed' if value else 'blocked'}"
        for key, value in sorted(permissions.items())
        if key not in {"claim", "submit_results"}
    ]
    return " | ".join(labels + extra[:4])


def average_score(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    return sum(float(row.get("score") or 0) for row in rows) / len(rows)


def candidate_name_from_row(row: dict | None) -> str:
    if not row:
        return "Sercan Ozkan"
    email = (row.get("email") or "").strip()
    if email and "@" in email:
        return email.split("@", 1)[0].replace(".", " ").replace("_", " ").title()
    stem = Path(row.get("file", "")).stem
    return stem.replace("_", " ").replace("-", " ").strip().title() or "Candidate"


class AnalysisWorker(QObject):
    progress_max = Signal(int)
    progress = Signal(int)
    status = Signal(str)
    row = Signal(dict)
    run_created = Signal(int)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, folder: Path, output: Path, config: dict, ai_mode: str, job_name: str):
        super().__init__()
        self.folder = folder
        self.output = output
        self.config = config
        self.ai_mode = ai_mode
        self.job_name = job_name
        self.cancelled = False
        self.store = WorkspaceStore()

    def cancel(self):
        self.cancelled = True

    def run(self):
        try:
            self._run()
        except Exception:
            detail = traceback.format_exc()
            log_path = write_crash_log(detail)
            self.failed.emit(f"Analysis stopped. Details were written to {log_path}")

    def _run(self):
        files = iter_supported_local_files(self.folder, self.output)
        if not files:
            self.done.emit("No PDF, DOCX, or TXT files found.")
            return

        self.output.mkdir(parents=True, exist_ok=True)
        run_id = self.store.create_run(None, self.job_name, str(self.folder), str(self.output), len(files))
        self.run_created.emit(run_id)
        self.progress_max.emit(len(files))

        results: list[dict] = []
        failed_files: list[str] = []
        seen_hashes: dict[str, str] = {}

        for index, path in enumerate(files, start=1):
            if self.cancelled:
                self.status.emit("Cancelled. Writing partial results...")
                break

            self.status.emit(f"Processing {index}/{len(files)}: {path.name}")
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    raise ValueError(f"File exceeds max size: {MAX_FILE_BYTES} bytes")
                data = path.read_bytes()
                file_hash = hashlib.sha256(data).hexdigest()
                duplicate_of = seen_hashes.get(file_hash)
                if not duplicate_of:
                    seen_hashes[file_hash] = str(path)

                text = extract_text(data, path.suffix.lstrip("."), path.name)
                result = score_cv(text, self.config)
                result = maybe_apply_ai_review(text, self.config, result, self.ai_mode)

                email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
                email = email_match.group(0) if email_match else ""
                row = {
                    **result,
                    "rank": 0,
                    "file": str(path),
                    "file_hash": file_hash,
                    "is_duplicate": bool(duplicate_of),
                    "duplicate_of": duplicate_of or "",
                    "email": email,
                    "sync_status": "offline_ready",
                    "analyzed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                }
                self.store.add_result(run_id, row)
                results.append(row)
                self.row.emit(row)
            except Exception as exc:
                failed_files.append(str(path))
                self.row.emit(
                    {
                        "rank": 0,
                        "file": str(path),
                        "score": 0,
                        "decision": "recommended_reject",
                        "confidence": "low",
                        "matched_skills": [],
                        "missing_skills": [],
                        "risk_flags": ["processing_failed"],
                        "summary": "Processing failed.",
                        "explanation": str(exc),
                        "is_duplicate": False,
                        "sync_status": "failed",
                        "analyzed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    }
                )
            finally:
                self.progress.emit(index)

        ranked = sorted(results, key=lambda row: (-float(row.get("score") or 0), decision_rank(row.get("decision"))))
        for rank, row in enumerate(ranked, start=1):
            row["rank"] = rank

        json_path = self.output / "local_worker_results.json"
        csv_path = self.output / "local_worker_results.csv"
        html_path = self.output / "local_worker_report.html"
        failed_path = self.output / "failed_files.txt"
        manifest_path = self.output / "sync_manifest.json"

        json_path.write_text(json.dumps(ranked, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, ranked)
        try:
            worker_module._generate_html_report(ranked, self.config, html_path)
        except Exception:
            pass
        if failed_files:
            failed_path.write_text("\n".join(failed_files), encoding="utf-8")
        elif failed_path.exists():
            failed_path.unlink()
        manifest_path.write_text(
            json.dumps(
                {
                    "schema": "cv_analyzer.local_worker.sync_manifest.v1",
                    "job": {"id": None, "name": self.job_name, "config": self.config},
                    "run": {
                        "cv_folder": str(self.folder),
                        "output_folder": str(self.output),
                        "total_files": len(files),
                        "processed": len(results),
                        "failed": len(failed_files),
                        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    },
                    "results_file": str(json_path),
                    "csv_file": str(csv_path),
                    "html_report": str(html_path),
                    "failed_files": failed_files,
                    "sync_status": "offline_ready",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.done.emit(f"Done. {len(results)} processed, {len(failed_files)} failed. Output: {self.output}")

    def _write_csv(self, path: Path, rows: list[dict]):
        with path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "rank",
                    "file",
                    "score",
                    "decision",
                    "confidence",
                    "is_duplicate",
                    "duplicate_of",
                    "summary",
                    "matched_skills",
                    "missing_skills",
                    "risk_flags",
                    "explanation",
                    "analyzed_at",
                ],
                extrasaction="ignore",
            )
            writer.writeheader()
            for row in rows:
                csv_row = {
                    **row,
                    "matched_skills": list_to_text(row.get("matched_skills")),
                    "missing_skills": list_to_text(row.get("missing_skills")),
                    "risk_flags": list_to_text(row.get("risk_flags")),
                }
                writer.writerow({key: csv_safe(value) for key, value in csv_row.items()})


class ResultListModel(QAbstractListModel):
    FileNameRole = Qt.UserRole + 1
    FilePathRole = Qt.UserRole + 2
    EmailRole = Qt.UserRole + 3
    ScoreRole = Qt.UserRole + 4
    DecisionRole = Qt.UserRole + 5
    DecisionLabelRole = Qt.UserRole + 6
    ConfidenceRole = Qt.UserRole + 7
    MatchedRole = Qt.UserRole + 8
    MissingRole = Qt.UserRole + 9
    RiskRole = Qt.UserRole + 10
    SummaryRole = Qt.UserRole + 11
    ExplanationRole = Qt.UserRole + 12
    AccentRole = Qt.UserRole + 13
    SyncRole = Qt.UserRole + 14

    def __init__(self):
        super().__init__()
        self._rows: list[dict] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        row = self._rows[index.row()]
        if role == self.FileNameRole:
            return Path(row.get("file", "")).name or "Unknown CV"
        if role == self.FilePathRole:
            return row.get("file", "")
        if role == self.EmailRole:
            return row.get("email", "") or "No email"
        if role == self.ScoreRole:
            return int(float(row.get("score") or 0))
        if role == self.DecisionRole:
            return row.get("decision", "")
        if role == self.DecisionLabelRole:
            return decision_label(row.get("decision", ""))
        if role == self.ConfidenceRole:
            return row.get("confidence", "medium")
        if role == self.MatchedRole:
            return list_to_text(row.get("matched_skills"))
        if role == self.MissingRole:
            return list_to_text(row.get("missing_skills"))
        if role == self.RiskRole:
            return list_to_text(row.get("risk_flags"))
        if role == self.SummaryRole:
            return row.get("summary", "")
        if role == self.ExplanationRole:
            return row.get("explanation", "")
        if role == self.AccentRole:
            return decision_accent(row.get("decision", ""))
        if role == self.SyncRole:
            return row.get("sync_status", "offline_ready")
        return None

    def roleNames(self):
        return {
            self.FileNameRole: QByteArray(b"fileName"),
            self.FilePathRole: QByteArray(b"filePath"),
            self.EmailRole: QByteArray(b"email"),
            self.ScoreRole: QByteArray(b"score"),
            self.DecisionRole: QByteArray(b"decision"),
            self.DecisionLabelRole: QByteArray(b"decisionLabel"),
            self.ConfidenceRole: QByteArray(b"confidence"),
            self.MatchedRole: QByteArray(b"matchedSkills"),
            self.MissingRole: QByteArray(b"missingSkills"),
            self.RiskRole: QByteArray(b"riskFlags"),
            self.SummaryRole: QByteArray(b"summary"),
            self.ExplanationRole: QByteArray(b"explanation"),
            self.AccentRole: QByteArray(b"accent"),
            self.SyncRole: QByteArray(b"syncStatus"),
        }

    def rows(self) -> list[dict]:
        return self._rows

    def clear(self):
        self.beginResetModel()
        self._rows = []
        self.endResetModel()

    def set_rows(self, rows: list[dict]):
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def add_row(self, row: dict):
        pos = len(self._rows)
        self.beginInsertRows(QModelIndex(), pos, pos)
        self._rows.append(row)
        self.endInsertRows()

    def update_decision(self, row_index: int, decision: str):
        if 0 <= row_index < len(self._rows):
            self._rows[row_index]["decision"] = decision
            model_index = self.index(row_index, 0)
            self.dataChanged.emit(
                model_index, model_index, [self.DecisionRole, self.DecisionLabelRole, self.AccentRole]
            )


class HistoryListModel(QAbstractListModel):
    IdRole = Qt.UserRole + 1
    JobNameRole = Qt.UserRole + 2
    CreatedRole = Qt.UserRole + 3
    CountRole = Qt.UserRole + 4
    CvFolderRole = Qt.UserRole + 5
    OutputFolderRole = Qt.UserRole + 6

    def __init__(self):
        super().__init__()
        self._rows: list[dict] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        row = self._rows[index.row()]
        if role == self.IdRole:
            return int(row.get("id") or 0)
        if role == self.JobNameRole:
            return row.get("job_name", "Local job")
        if role == self.CreatedRole:
            return row.get("created_at", "")
        if role == self.CountRole:
            return int(row.get("total_files") or 0)
        if role == self.CvFolderRole:
            return row.get("cv_folder", "")
        if role == self.OutputFolderRole:
            return row.get("output_folder", "")
        return None

    def roleNames(self):
        return {
            self.IdRole: QByteArray(b"runId"),
            self.JobNameRole: QByteArray(b"jobName"),
            self.CreatedRole: QByteArray(b"createdAt"),
            self.CountRole: QByteArray(b"totalFiles"),
            self.CvFolderRole: QByteArray(b"cvFolder"),
            self.OutputFolderRole: QByteArray(b"outputFolder"),
        }

    def set_rows(self, rows: list[dict]):
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()


class NotificationListModel(QAbstractListModel):
    IdRole = Qt.UserRole + 1
    TitleRole = Qt.UserRole + 2
    MessageRole = Qt.UserRole + 3
    CandidateRole = Qt.UserRole + 4
    TypeRole = Qt.UserRole + 5
    IsReadRole = Qt.UserRole + 6
    CreatedRole = Qt.UserRole + 7

    def __init__(self):
        super().__init__()
        self._rows: list[dict] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        row = self._rows[index.row()]
        if role == self.IdRole:
            return int(row.get("id") or 0)
        if role == self.TitleRole:
            return row.get("title", "")
        if role == self.MessageRole:
            return row.get("message", "")
        if role == self.CandidateRole:
            return row.get("candidate_name", "")
        if role == self.TypeRole:
            return row.get("type", "info")
        if role == self.IsReadRole:
            return bool(row.get("is_read"))
        if role == self.CreatedRole:
            return row.get("created_at", "")
        return None

    def roleNames(self):
        return {
            self.IdRole: QByteArray(b"notificationId"),
            self.TitleRole: QByteArray(b"title"),
            self.MessageRole: QByteArray(b"message"),
            self.CandidateRole: QByteArray(b"candidateName"),
            self.TypeRole: QByteArray(b"type"),
            self.IsReadRole: QByteArray(b"isRead"),
            self.CreatedRole: QByteArray(b"createdAt"),
        }

    def set_rows(self, rows: list[dict]):
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()


class AuditListModel(QAbstractListModel):
    IdRole = Qt.UserRole + 1
    ActionRole = Qt.UserRole + 2
    ModuleRole = Qt.UserRole + 3
    DescriptionRole = Qt.UserRole + 4
    StatusRole = Qt.UserRole + 5
    CreatedRole = Qt.UserRole + 6

    def __init__(self):
        super().__init__()
        self._rows: list[dict] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        row = self._rows[index.row()]
        if role == self.IdRole:
            return int(row.get("id") or 0)
        if role == self.ActionRole:
            return row.get("action_type", "")
        if role == self.ModuleRole:
            return row.get("module", "")
        if role == self.DescriptionRole:
            return row.get("description", "")
        if role == self.StatusRole:
            return row.get("status", "")
        if role == self.CreatedRole:
            return row.get("created_at", "")
        return None

    def roleNames(self):
        return {
            self.IdRole: QByteArray(b"auditId"),
            self.ActionRole: QByteArray(b"action"),
            self.ModuleRole: QByteArray(b"module"),
            self.DescriptionRole: QByteArray(b"description"),
            self.StatusRole: QByteArray(b"status"),
            self.CreatedRole: QByteArray(b"createdAt"),
        }

    def set_rows(self, rows: list[dict]):
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()


class WebsiteSyncWorker(QObject):
    status = Signal(str)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, mode: str, api_url: str, api_key: str, job_id: str, pending_results: list[dict]):
        super().__init__()
        self.mode = mode
        self.api_url = (api_url or API_BASE_URL).strip().rstrip("/")
        self.api_key = api_key.strip()
        self.job_id = (job_id or "").strip()
        self.pending_results = list(pending_results or [])

    def run(self):
        try:
            if not self.api_key:
                raise RuntimeError("Paste a worker key before connecting.")
            self.status.emit("Connecting to website worker API...")
            worker = LocalWorker(
                self.api_key,
                "server_files",
                "none",
                os.environ.get("COMPUTERNAME", "QML Local Worker"),
                api_base_url=self.api_url or API_BASE_URL,
            )
            worker.login()

            self.status.emit("Fetching allowed website jobs...")
            jobs_resp = worker._request("GET", "/jobs")
            if jobs_resp.status_code != 200:
                raise RuntimeError(f"Connected, but job list failed: {jobs_resp.text}")
            jobs = jobs_resp.json().get("jobs", [])
            if self.mode == "test":
                self.done.emit(
                    {
                        "mode": "test",
                        "company_id": str(worker.company_id or ""),
                        "quota_remaining": int(worker.quota_remaining or 0),
                        "allowed_jobs": jobs,
                        "permissions": worker.permissions,
                    }
                )
                return

            if not self.pending_results:
                self.done.emit(
                    {
                        "mode": "sync",
                        "synced_count": 0,
                        "synced_files": [],
                        "company_id": str(worker.company_id or ""),
                        "quota_remaining": int(worker.quota_remaining or 0),
                        "allowed_jobs": jobs,
                        "permissions": worker.permissions,
                    }
                )
                return

            target_job_id = int(self.job_id) if self.job_id else (int(jobs[0]) if len(jobs) == 1 else 0)
            if not target_job_id:
                raise RuntimeError("Enter a Website job id or use a worker key scoped to one job.")
            if jobs and target_job_id not in [int(job) for job in jobs]:
                raise RuntimeError(f"Worker key is not allowed for Website job #{target_job_id}.")

            results_payload = []
            synced_files = []
            synced_ids = []
            for row in self.pending_results:
                file_path = row.get("file", "")
                results_payload.append(
                    {
                        "file_name": Path(file_path).name,
                        "file_type": Path(file_path).suffix.lstrip("."),
                        "file_hash": row.get("file_hash"),
                        "duplicate_of": Path(row["duplicate_of"]).name if row.get("duplicate_of") else None,
                        "score": float(row.get("score") or 0),
                        "decision": row.get("decision", "recommended_review"),
                        "confidence": row.get("confidence", "medium"),
                        "summary": row.get("summary", ""),
                        "matched_skills": row.get("matched_skills") or [],
                        "missing_skills": row.get("missing_skills") or [],
                        "risk_flags": row.get("risk_flags") or [],
                        "explanation": row.get("explanation", ""),
                        "candidate_name": candidate_name_from_row(row),
                        "candidate_email": row.get("email") or None,
                        "worker_version": row.get("worker_version", "1.0.0"),
                        "engine_version": row.get("engine_version", "1.0.0"),
                    }
                )
                synced_files.append(file_path)
                if row.get("local_result_id"):
                    synced_ids.append(int(row["local_result_id"]))

            self.status.emit(f"Uploading {len(results_payload)} local result(s) to Website job #{target_job_id}...")
            payload = {"job_id": target_job_id, "results": results_payload}
            resp = worker._request("POST", "/offline-sync", json=payload)
            if resp.status_code == 404:
                resp = worker._request("POST", "/worker/offline-sync", json=payload)
            if resp.status_code not in {200, 201}:
                raise RuntimeError(f"Sync failed: {resp.status_code} - {resp.text}")

            data = resp.json() if resp.content else {}
            self.done.emit(
                {
                    "mode": "sync",
                    "synced_count": int(data.get("synced_count") or len(results_payload)),
                    "synced_files": synced_files,
                    "synced_ids": synced_ids,
                    "company_id": str(worker.company_id or ""),
                    "quota_remaining": int(worker.quota_remaining or 0),
                    "allowed_jobs": jobs,
                    "job_id": target_job_id,
                    "permissions": worker.permissions,
                }
            )
        except Exception as exc:
            self.failed.emit(str(exc))


class LocalWorkerBackend(QObject):
    stateChanged = Signal()
    metricsChanged = Signal()
    selectedChanged = Signal()
    templateChanged = Signal()
    reportChanged = Signal()
    syncChanged = Signal()
    inboxChanged = Signal()
    toast = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.store = WorkspaceStore()
        self._results_model = ResultListModel()
        self._history_model = HistoryListModel()
        self._notification_model = NotificationListModel()
        self._audit_model = AuditListModel()
        self._unread_count = 0
        self._thread: QThread | None = None
        self._worker: AnalysisWorker | None = None
        self._sync_thread: QThread | None = None
        self._sync_worker: WebsiteSyncWorker | None = None
        self._current_run_id: int | None = None
        self._selected_index = -1
        self._job_name = "New local job"
        self._cv_folder = ""
        self._output_folder = str(Path.cwd() / "local_results")
        self._job_description = ""
        self._required_skills = ""
        self._nice_to_have_skills = ""
        self._hard_reject_criteria = ""
        self._accept_threshold = 75
        self._review_threshold = 50
        self._ai_mode = "none"
        self._status = "Ready to analyze"
        self._is_running = False
        self._progress_value = 0
        self._progress_maximum = 1
        self._motion_enabled = os.environ.get("CV_WORKER_DISABLE_MOTION", "").lower() not in {"1", "true", "yes"}
        self._sync_api_url = os.environ.get("CV_ANALYZER_API_URL", API_BASE_URL)
        self._sync_api_key = load_worker_api_key() or os.environ.get("CV_WORKER_API_KEY", "")
        self._sync_job_id = ""
        self._sync_status = "Website sync not tested"
        self._sync_detail = "Connect a worker key to upload selected local results back to the website."
        self._sync_connected = False
        self._sync_running = False
        self._sync_company_id = ""
        self._sync_quota_remaining = 0
        self._sync_allowed_jobs: list[int] = []
        self._sync_permissions: dict = {}
        self._sync_permission_summary = "Test connection to inspect this worker key's local access scope."
        self._sync_last_synced_count = 0
        self._mail_templates = load_mail_templates()
        self._template_mode = "accept"
        self._template_subject = ""
        self._template_body = ""
        self._report_preview = "No report yet. Run a local analysis to generate JSON and CSV outputs."
        self._load_template_fields()
        self.refreshHistory()
        self.refreshSyncQueue()
        self.refreshInbox()

    @Property(QObject, constant=True)
    def resultsModel(self):
        return self._results_model

    @Property(QObject, constant=True)
    def historyModel(self):
        return self._history_model

    @Property(QObject, constant=True)
    def notificationsModel(self):
        return self._notification_model

    @Property(QObject, constant=True)
    def auditModel(self):
        return self._audit_model

    @Property(int, notify=inboxChanged)
    def unreadNotificationCount(self):
        return self._unread_count

    @Property(int, notify=inboxChanged)
    def notificationCount(self):
        return self._notification_model.rowCount()

    @Property(int, notify=inboxChanged)
    def auditCount(self):
        return self._audit_model.rowCount()

    @Property(str, notify=inboxChanged)
    def inboxBadge(self):
        return str(self._unread_count) if self._unread_count else ""

    @Property(str, notify=stateChanged)
    def jobName(self):
        return self._job_name

    @jobName.setter
    def jobName(self, value: str):
        self._job_name = value
        self.stateChanged.emit()

    @Property(str, notify=stateChanged)
    def cvFolder(self):
        return self._cv_folder

    @cvFolder.setter
    def cvFolder(self, value: str):
        self._cv_folder = value
        if value and not self._output_folder:
            self._output_folder = str(Path(value) / "cv_analyzer_results")
        self.stateChanged.emit()

    @Property(str, notify=stateChanged)
    def outputFolder(self):
        return self._output_folder

    @outputFolder.setter
    def outputFolder(self, value: str):
        self._output_folder = value
        self.stateChanged.emit()

    @Property(int, notify=stateChanged)
    def cvFileCount(self):
        """Number of supported CV files in the selected folder.

        Returns -1 when no folder is selected so the UI can distinguish
        "nothing picked yet" from "folder picked but empty" (0).
        """
        if not self._cv_folder:
            return -1
        try:
            folder = Path(self._cv_folder)
            out = Path(self._output_folder) if self._output_folder else folder / "_cv_out"
            return len(iter_supported_local_files(folder, out))
        except Exception as exc:
            logger.warning("cvFileCount scan failed: %s", exc)
            return 0

    @Property(str, notify=stateChanged)
    def jobDescription(self):
        return self._job_description

    @jobDescription.setter
    def jobDescription(self, value: str):
        self._job_description = value
        self.stateChanged.emit()

    @Property(str, notify=stateChanged)
    def requiredSkills(self):
        return self._required_skills

    @requiredSkills.setter
    def requiredSkills(self, value: str):
        self._required_skills = value
        self.stateChanged.emit()

    @Property(str, notify=stateChanged)
    def niceToHaveSkills(self):
        return self._nice_to_have_skills

    @niceToHaveSkills.setter
    def niceToHaveSkills(self, value: str):
        self._nice_to_have_skills = value
        self.stateChanged.emit()

    @Property(str, notify=stateChanged)
    def hardRejectCriteria(self):
        return self._hard_reject_criteria

    @hardRejectCriteria.setter
    def hardRejectCriteria(self, value: str):
        self._hard_reject_criteria = value
        self.stateChanged.emit()

    @Property(int, notify=stateChanged)
    def acceptThreshold(self):
        return self._accept_threshold

    @acceptThreshold.setter
    def acceptThreshold(self, value: int):
        self._accept_threshold = int(value)
        self.stateChanged.emit()

    @Property(int, notify=stateChanged)
    def reviewThreshold(self):
        return self._review_threshold

    @reviewThreshold.setter
    def reviewThreshold(self, value: int):
        self._review_threshold = int(value)
        self.stateChanged.emit()

    @Property(str, notify=stateChanged)
    def aiMode(self):
        return self._ai_mode

    @aiMode.setter
    def aiMode(self, value: str):
        self._ai_mode = value or "none"
        self.stateChanged.emit()

    @Property(str, notify=stateChanged)
    def status(self):
        return self._status

    @Property(bool, notify=stateChanged)
    def isRunning(self):
        return self._is_running

    @Property(int, notify=stateChanged)
    def progressValue(self):
        return self._progress_value

    @Property(int, notify=stateChanged)
    def progressMaximum(self):
        return self._progress_maximum

    @Property(bool, notify=stateChanged)
    def motionEnabled(self):
        return self._motion_enabled

    @motionEnabled.setter
    def motionEnabled(self, value: bool):
        self._motion_enabled = bool(value)
        self.stateChanged.emit()

    @Property(str, notify=syncChanged)
    def syncApiUrl(self):
        return self._sync_api_url

    @syncApiUrl.setter
    def syncApiUrl(self, value: str):
        self._sync_api_url = value
        self._sync_connected = False
        self._sync_status = "Website sync changed"
        self._sync_permissions = {}
        self._sync_permission_summary = "Test connection to inspect this worker key's local access scope."
        self.syncChanged.emit()

    @Property(str, notify=syncChanged)
    def syncApiKey(self):
        return self._sync_api_key

    @syncApiKey.setter
    def syncApiKey(self, value: str):
        self._sync_api_key = value
        self._sync_connected = False
        self._sync_status = "Worker key changed"
        self._sync_permissions = {}
        self._sync_permission_summary = "Test connection to inspect this worker key's local access scope."
        self.syncChanged.emit()

    @Property(str, notify=syncChanged)
    def syncJobId(self):
        return self._sync_job_id

    @syncJobId.setter
    def syncJobId(self, value: str):
        self._sync_job_id = value
        self.syncChanged.emit()

    @Property(str, notify=syncChanged)
    def syncStatus(self):
        return self._sync_status

    @Property(str, notify=syncChanged)
    def syncDetail(self):
        return self._sync_detail

    @Property(bool, notify=syncChanged)
    def syncConnected(self):
        return self._sync_connected

    @Property(bool, notify=syncChanged)
    def syncRunning(self):
        return self._sync_running

    @Property(str, notify=syncChanged)
    def syncCompanyId(self):
        return self._sync_company_id or "-"

    @Property(int, notify=syncChanged)
    def syncQuotaRemaining(self):
        return self._sync_quota_remaining

    @Property(str, notify=syncChanged)
    def syncAllowedJobs(self):
        return ", ".join(str(job) for job in self._sync_allowed_jobs) if self._sync_allowed_jobs else "-"

    @Property(str, notify=syncChanged)
    def syncPermissionSummary(self):
        return self._sync_permission_summary

    @Property(int, notify=syncChanged)
    def syncPendingCount(self):
        return len(self.store.list_pending_sync_results(limit=500))

    @Property(int, notify=syncChanged)
    def syncLastSyncedCount(self):
        return self._sync_last_synced_count

    @Property(str, notify=syncChanged)
    def syncBadge(self):
        if self._sync_running:
            return "SYNCING"
        if self._sync_connected:
            return "SYNC READY"
        return "SYNC NEEDED"

    @Property(int, notify=metricsChanged)
    def totalCandidates(self):
        return len(self._results_model.rows())

    @Property(int, notify=metricsChanged)
    def averageScoreValue(self):
        return int(round(average_score(self._results_model.rows())))

    @Property(str, notify=metricsChanged)
    def averageScore(self):
        rows = self._results_model.rows()
        if not rows:
            return "--"
        return f"{average_score(rows):.1f}%"

    @Property(int, notify=metricsChanged)
    def topScoreCount(self):
        return sum(1 for row in self._results_model.rows() if float(row.get("score") or 0) >= self._accept_threshold)

    @Property(int, notify=metricsChanged)
    def reviewScoreCount(self):
        return sum(
            1
            for row in self._results_model.rows()
            if self._review_threshold <= float(row.get("score") or 0) < self._accept_threshold
        )

    @Property(int, notify=metricsChanged)
    def lowScoreCount(self):
        return sum(1 for row in self._results_model.rows() if float(row.get("score") or 0) < self._review_threshold)

    @Property(int, notify=metricsChanged)
    def duplicateCount(self):
        return sum(1 for row in self._results_model.rows() if row.get("is_duplicate"))

    @Property(int, notify=metricsChanged)
    def historyRunCount(self):
        return self._history_model.rowCount()

    @Property(str, notify=metricsChanged)
    def currentRunSummary(self):
        rows = self._results_model.rows()
        if not rows:
            return "No current run loaded"
        return f"{len(rows)} candidates | avg {average_score(rows):.1f}% | {self.shortlistedCount} shortlisted"

    @Property(str, notify=metricsChanged)
    def previousRunSummary(self):
        runs = self.store.list_runs(limit=2)
        if not runs:
            return "No previous runs yet"
        current_id = self._current_run_id
        previous = None
        for run in runs:
            if run.get("id") != current_id:
                previous = run
                break
        if previous is None and runs:
            previous = runs[-1]
        if not previous:
            return "No previous run to compare"
        rows = self.store.get_run_results(int(previous.get("id") or 0))
        return f"Run #{previous.get('id')} | {len(rows)} candidates | avg {average_score(rows):.1f}%"

    @Property(str, notify=metricsChanged)
    def runDeltaSummary(self):
        rows = self._results_model.rows()
        if not rows:
            return "Load or run an analysis to compare changes."
        current_avg = average_score(rows)
        runs = self.store.list_runs(limit=3)
        previous_rows = []
        for run in runs:
            if run.get("id") != self._current_run_id:
                previous_rows = self.store.get_run_results(int(run.get("id") or 0))
                break
        if not previous_rows:
            return "No earlier scored run available for comparison."
        delta = current_avg - average_score(previous_rows)
        direction = "+" if delta >= 0 else ""
        return f"{direction}{delta:.1f}% average score vs previous run"

    @Property(int, notify=metricsChanged)
    def shortlistedCount(self):
        return sum(1 for row in self._results_model.rows() if row.get("decision") == "recommended_accept")

    @Property(int, notify=metricsChanged)
    def reviewCount(self):
        return sum(1 for row in self._results_model.rows() if row.get("decision") == "recommended_review")

    @Property(int, notify=metricsChanged)
    def rejectCount(self):
        return sum(1 for row in self._results_model.rows() if row.get("decision") == "recommended_reject")

    @Property(int, notify=selectedChanged)
    def selectedIndex(self):
        return self._selected_index

    @Property(int, notify=stateChanged)
    def setupCompletion(self):
        checks = [
            bool(self._cv_folder),
            bool(self._output_folder),
            bool(self._job_description.strip() or self._required_skills.strip()),
            bool(self._accept_threshold > self._review_threshold),
        ]
        return int(sum(1 for item in checks if item) / len(checks) * 100)

    @Property(str, notify=stateChanged)
    def setupStepLabel(self):
        if not self._cv_folder:
            return "Choose a local CV folder"
        if not (self._job_description.strip() or self._required_skills.strip()):
            return "Add role criteria"
        if not self._output_folder:
            return "Choose an output folder"
        if self._accept_threshold <= self._review_threshold:
            return "Adjust scoring thresholds"
        return "Ready to run local analysis"

    @Property(int, notify=stateChanged)
    def pipelineStep(self):
        if self._is_running:
            if self._progress_value <= 0:
                return 1
            if self._progress_value < self._progress_maximum:
                return 2
            return 3
        if self._results_model.rows():
            return 4
        return 0

    @Property(str, notify=selectedChanged)
    def selectedFileName(self):
        row = self._selected_row()
        return Path(row.get("file", "")).name if row else "Select a candidate"

    @Property(str, notify=selectedChanged)
    def selectedEmail(self):
        row = self._selected_row()
        return (row.get("email") or "No email") if row else "Candidate details will appear here."

    @Property(str, notify=selectedChanged)
    def selectedCandidateName(self):
        return candidate_name_from_row(self._selected_row())

    @Property(str, notify=selectedChanged)
    def selectedFilePath(self):
        row = self._selected_row()
        return row.get("file", "") if row else ""

    @Property(str, notify=selectedChanged)
    def selectedScore(self):
        row = self._selected_row()
        return str(int(float(row.get("score") or 0))) if row else "--"

    @Property(int, notify=selectedChanged)
    def selectedScoreValue(self):
        row = self._selected_row()
        return int(float(row.get("score") or 0)) if row else 0

    @Property(str, notify=selectedChanged)
    def selectedDecisionLabel(self):
        row = self._selected_row()
        return decision_label(row.get("decision", "")) if row else "Waiting"

    @Property(str, notify=selectedChanged)
    def selectedConfidence(self):
        row = self._selected_row()
        return (row.get("confidence") or "medium").title() if row else "-"

    @Property(str, notify=selectedChanged)
    def selectedSyncStatus(self):
        row = self._selected_row()
        return (row.get("sync_status") or "offline_ready").replace("_", " ").title() if row else "Offline Ready"

    @Property(str, notify=selectedChanged)
    def selectedDuplicateStatus(self):
        row = self._selected_row()
        if not row:
            return "-"
        return "Duplicate" if row.get("is_duplicate") else "Unique"

    @Property(str, notify=selectedChanged)
    def selectedSummary(self):
        row = self._selected_row()
        return (
            row.get("summary") or "Select a result to inspect summary, skills, and risk flags."
            if row
            else "Select a result to inspect summary, skills, and risk flags."
        )

    @Property(str, notify=selectedChanged)
    def selectedExplanation(self):
        row = self._selected_row()
        return row.get("explanation") or "No explanation yet." if row else "No candidate selected."

    @Property(str, notify=selectedChanged)
    def selectedMatchedSkills(self):
        row = self._selected_row()
        return list_to_text(row.get("matched_skills")) if row else "-"

    @Property(str, notify=selectedChanged)
    def selectedMissingSkills(self):
        row = self._selected_row()
        return list_to_text(row.get("missing_skills")) if row else "-"

    @Property(str, notify=selectedChanged)
    def selectedRiskFlags(self):
        row = self._selected_row()
        return list_to_text(row.get("risk_flags")) if row else "-"

    @Property(str, notify=reportChanged)
    def reportPreview(self):
        return self._report_preview

    @Property(str, notify=templateChanged)
    def templateMode(self):
        return self._template_mode

    @Property(str, notify=templateChanged)
    def templateSubject(self):
        return self._template_subject

    @templateSubject.setter
    def templateSubject(self, value: str):
        self._template_subject = value
        self.templateChanged.emit()

    @Property(str, notify=templateChanged)
    def templateBody(self):
        return self._template_body

    @templateBody.setter
    def templateBody(self, value: str):
        self._template_body = value
        self.templateChanged.emit()

    @Property(str, notify=templateChanged)
    def templatePreviewSubject(self):
        return self._render_template(self._template_subject)

    @Property(str, notify=templateChanged)
    def templatePreviewBody(self):
        return self._render_template(self._template_body)

    def _selected_row(self) -> dict | None:
        rows = self._results_model.rows()
        if 0 <= self._selected_index < len(rows):
            return rows[self._selected_index]
        return None

    def _set_status(self, value: str):
        self._status = value
        self.stateChanged.emit()

    def _load_template_fields(self):
        if self._template_mode == "reject":
            self._template_subject = self._mail_templates.get("reject_subject", "")
            self._template_body = self._mail_templates.get("reject_body", "")
        else:
            self._template_subject = self._mail_templates.get("accept_subject", "")
            self._template_body = self._mail_templates.get("accept_body", "")
        self.templateChanged.emit()

    def _sync_template_fields(self):
        if self._template_mode == "reject":
            self._mail_templates["reject_subject"] = self._template_subject.strip()
            self._mail_templates["reject_body"] = self._template_body
        else:
            self._mail_templates["accept_subject"] = self._template_subject.strip()
            self._mail_templates["accept_body"] = self._template_body

    def _render_template(self, value: str) -> str:
        row = self._selected_row()
        score = str(int(float(row.get("score") or 0))) if row else "85"
        replacements = {
            "{name}": candidate_name_from_row(row),
            "{email}": (row.get("email") if row else "") or "candidate@example.com",
            "{role}": self._job_name.strip() or "Software Engineer",
            "{position}": self._job_name.strip() or "Software Engineer",
            "{score}": score,
            "{company}": "CV Analyzer",
        }
        rendered = value or ""
        for key, replacement in replacements.items():
            rendered = rendered.replace(key, replacement)
        return rendered

    def _refresh_report_preview(self):
        rows = self._results_model.rows()
        if not rows:
            self._report_preview = "No report yet. Run a local analysis to generate JSON and CSV outputs."
            self.reportChanged.emit()
            return
        top = sorted(rows, key=lambda row: float(row.get("score") or 0), reverse=True)[:5]
        lines = [
            f"Output folder: {self._output_folder}",
            f"Total candidates: {len(rows)}",
            f"Average score: {self.averageScore}",
            f"Accept / Review / Reject: {self.shortlistedCount} / {self.reviewCount} / {self.rejectCount}",
            "",
            "Top candidates:",
        ]
        for index, row in enumerate(top, 1):
            lines.append(
                f"{index}. {Path(row.get('file', '')).name} - {row.get('score', 0)}% - {decision_label(row.get('decision', ''))}"
            )
        self._report_preview = "\n".join(lines)
        self.reportChanged.emit()

    def _config(self) -> dict:
        return {
            "title": self._job_name.strip() or "New local job",
            "description": self._job_description.strip(),
            "required_skills": [item.strip() for item in self._required_skills.split(",") if item.strip()],
            "nice_to_have_skills": [item.strip() for item in self._nice_to_have_skills.split(",") if item.strip()],
            "hard_reject_criteria": [item.strip() for item in self._hard_reject_criteria.split(",") if item.strip()],
            "accept_threshold": self._accept_threshold,
            "review_threshold": self._review_threshold,
            "reject_threshold": 30,
        }

    @Slot(QUrl)
    def setCvFolderFromUrl(self, url: QUrl):
        self.cvFolder = url.toLocalFile()
        if self._cv_folder and self._output_folder == str(Path.cwd() / "local_results"):
            self.outputFolder = str(Path(self._cv_folder) / "cv_analyzer_results")

    @Slot(QUrl)
    def setOutputFolderFromUrl(self, url: QUrl):
        self.outputFolder = url.toLocalFile()

    @Slot()
    def startAnalysis(self):
        if self._is_running:
            return
        folder = Path(self._cv_folder).expanduser()
        output = Path(self._output_folder or (folder / "cv_analyzer_results")).expanduser()
        config = self._config()
        if not folder.is_dir():
            self.toast.emit("Choose a valid CV folder.", "warning")
            return
        if not config["description"] and not config["required_skills"]:
            self.toast.emit("Add a job description or at least one required skill.", "warning")
            return
        file_count = len(iter_supported_local_files(folder, output))
        if file_count <= 0:
            self.toast.emit("No PDF, DOCX, or TXT files found in that folder.", "warning")
            return

        self._results_model.clear()
        self._selected_index = -1
        self.selectedChanged.emit()
        self.metricsChanged.emit()
        self._refresh_report_preview()
        self._progress_value = 0
        self._progress_maximum = max(1, file_count)
        self._is_running = True
        self._set_status("Starting analysis...")

        self._thread = QThread()
        self._worker = AnalysisWorker(folder, output, config, self._ai_mode, config["title"])
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress_max.connect(self._on_progress_max)
        self._worker.progress.connect(self._on_progress)
        self._worker.status.connect(self._set_status)
        self._worker.row.connect(self._on_row)
        self._worker.run_created.connect(self._on_run_created)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.done.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    @Slot()
    def cancelAnalysis(self):
        if self._worker:
            self._worker.cancel()
            self._set_status("Cancelling...")

    @Slot()
    def openOutputFolder(self):
        target = Path(self._output_folder or Path.cwd()).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(target))
        except Exception as exc:
            self.toast.emit(f"Could not open output folder: {exc}", "error")

    @Slot()
    def refreshHistory(self):
        rows = self.store.list_runs(limit=12)
        self._history_model.set_rows(rows)
        self.metricsChanged.emit()
        self.syncChanged.emit()
        self.toast.emit(f"History refreshed — {len(rows)} run(s).", "info")

    @Slot()
    def refreshInbox(self):
        try:
            self._notification_model.set_rows(self.store.list_notifications(limit=200))
            self._audit_model.set_rows(self.store.list_audit_logs(limit=200))
            self._unread_count = self.store.count_unread_notifications()
        except Exception as exc:
            logger.warning("refreshInbox failed: %s", exc)
        self.inboxChanged.emit()

    @Slot()
    def manualRefreshInbox(self):
        self.refreshInbox()
        self.toast.emit(f"Inbox refreshed — {self.notificationCount} notification(s).", "info")

    @Slot()
    def markAllNotificationsRead(self):
        try:
            self.store.mark_notifications_read()
        except Exception as exc:
            self.toast.emit(f"Could not mark notifications read: {exc}", "error")
            return
        self.refreshInbox()

    @Slot(int)
    def deleteNotification(self, notification_id: int):
        try:
            self.store.delete_notification(int(notification_id))
        except Exception as exc:
            self.toast.emit(f"Could not delete notification: {exc}", "error")
            return
        self.refreshInbox()

    @Slot()
    def clearAllNotifications(self):
        try:
            removed = self.store.clear_all_notifications()
        except Exception as exc:
            self.toast.emit(f"Could not clear notifications: {exc}", "error")
            return
        if removed:
            self.toast.emit(f"Cleared {removed} notification(s).", "success")
        self.refreshInbox()

    @Slot()
    def refreshSyncQueue(self):
        count = self.syncPendingCount
        self._sync_detail = f"{count} local result(s) ready for Website sync."
        self.syncChanged.emit()
        self.toast.emit(f"Sync queue refreshed — {count} pending.", "info")

    @Slot()
    def saveWorkerKey(self):
        if not self._sync_api_key.strip():
            self.toast.emit("Paste a worker key first.", "warning")
            return
        if save_worker_api_key(self._sync_api_key.strip()):
            self.toast.emit("Worker key saved to the OS credential store.", "success")
        else:
            self.toast.emit("Worker key could not be saved by the OS credential store.", "warning")

    @Slot()
    def testWebsiteSync(self):
        self._start_website_sync("test")

    @Slot()
    def syncPendingResults(self):
        self._start_website_sync("sync")

    def _start_website_sync(self, mode: str):
        if self._sync_running:
            return
        if not self._sync_api_url.strip():
            self.toast.emit("Enter the Website worker API URL.", "warning")
            return
        if not self._sync_api_key.strip():
            self.toast.emit("Paste a worker key first.", "warning")
            return
        pending = self.store.list_pending_sync_results(limit=500)
        if mode == "sync" and not pending:
            self._sync_status = "Nothing to sync"
            self._sync_detail = "All local results are already synced."
            self.syncChanged.emit()
            self.toast.emit("All local results are already synced.", "info")
            return

        self._sync_running = True
        self._sync_status = "Connecting..."
        self._sync_detail = "Website sync worker is running in the background."
        self.syncChanged.emit()

        self._sync_thread = QThread()
        self._sync_worker = WebsiteSyncWorker(mode, self._sync_api_url, self._sync_api_key, self._sync_job_id, pending)
        self._sync_worker.moveToThread(self._sync_thread)
        self._sync_thread.started.connect(self._sync_worker.run)
        self._sync_worker.status.connect(self._on_sync_status)
        self._sync_worker.done.connect(self._on_sync_done)
        self._sync_worker.failed.connect(self._on_sync_failed)
        self._sync_worker.done.connect(self._sync_thread.quit)
        self._sync_worker.failed.connect(self._sync_thread.quit)
        self._sync_thread.finished.connect(self._sync_worker.deleteLater)
        self._sync_thread.finished.connect(self._sync_thread.deleteLater)
        self._sync_thread.start()

    def _on_sync_status(self, message: str):
        self._sync_status = message
        self._sync_detail = message
        self.syncChanged.emit()

    def _on_sync_done(self, payload: dict):
        mode = payload.get("mode", "test")
        self._sync_running = False
        self._sync_connected = True
        self._sync_company_id = str(payload.get("company_id") or "")
        self._sync_quota_remaining = int(payload.get("quota_remaining") or 0)
        self._sync_allowed_jobs = [int(job) for job in (payload.get("allowed_jobs") or [])]
        self._sync_permissions = payload.get("permissions") or {}
        self._sync_permission_summary = permission_summary(self._sync_permissions)
        if len(self._sync_allowed_jobs) == 1 and not self._sync_job_id:
            self._sync_job_id = str(self._sync_allowed_jobs[0])

        if mode == "sync":
            synced_ids = payload.get("synced_ids") or []
            synced_files = set(payload.get("synced_files") or [])
            for result_id in synced_ids:
                self.store.update_result_sync_status(int(result_id), "synced")
            rows = self._results_model.rows()
            if rows and synced_files:
                for row in rows:
                    if row.get("file") in synced_files:
                        row["sync_status"] = "synced"
                self._results_model.set_rows(rows)
                self.selectedChanged.emit()
            self._sync_last_synced_count = int(payload.get("synced_count") or 0)
            self._sync_status = "Website sync complete"
            self._sync_detail = (
                f"{self._sync_last_synced_count} local result(s) uploaded to Website job #{payload.get('job_id')}."
            )
            self.toast.emit(self._sync_detail, "success")
        else:
            self._sync_status = "Website sync active"
            self._sync_detail = (
                f"Connected. Quota remaining: {self._sync_quota_remaining}. Allowed jobs: {self.syncAllowedJobs}."
            )
            self.toast.emit("Website sync connection verified.", "success")

        self.metricsChanged.emit()
        self.syncChanged.emit()

    def _on_sync_failed(self, message: str):
        self._sync_running = False
        self._sync_connected = False
        self._sync_status = "Website sync failed"
        self._sync_detail = message
        self.syncChanged.emit()
        self.toast.emit(message, "error")

    @Slot(int)
    def loadRun(self, run_id: int):
        rows = self.store.get_run_results(run_id)
        self._results_model.set_rows(rows)
        self._selected_index = 0 if rows else -1
        self._current_run_id = run_id
        self.metricsChanged.emit()
        self.selectedChanged.emit()
        self.templateChanged.emit()
        self._refresh_report_preview()
        self.toast.emit(f"Loaded run #{run_id}", "info")

    @Slot(int)
    def selectResult(self, index: int):
        self._selected_index = index
        self.selectedChanged.emit()
        self.templateChanged.emit()

    @Slot(int, str)
    def setDecision(self, index: int, decision: str):
        rows = self._results_model.rows()
        if not (0 <= index < len(rows)):
            return
        rows[index]["decision"] = decision
        self._results_model.update_decision(index, decision)
        if self._current_run_id:
            self.store.update_result_decision_by_file(self._current_run_id, rows[index].get("file", ""), decision)
        if rows[index].get("local_result_id"):
            rows[index]["sync_status"] = "pending"
            self.store.update_result_sync_status(int(rows[index]["local_result_id"]), "pending")
        self.metricsChanged.emit()
        self.selectedChanged.emit()
        self.templateChanged.emit()
        self.syncChanged.emit()
        self._refresh_report_preview()

    @Slot(str)
    def setSelectedDecision(self, decision: str):
        self.setDecision(self._selected_index, decision)

    @Slot(str)
    def setTemplateMode(self, mode: str):
        mode = "reject" if mode == "reject" else "accept"
        if mode == self._template_mode:
            return
        self._sync_template_fields()
        self._template_mode = mode
        self._load_template_fields()

    @Slot(str)
    def insertTemplateVariable(self, variable: str):
        self._template_body = (self._template_body or "") + variable
        self.templateChanged.emit()

    @Slot()
    def saveTemplates(self):
        self._sync_template_fields()
        save_mail_templates(self._mail_templates)
        self.toast.emit("Email templates saved locally.", "success")

    @Slot()
    def exportCurrentCsv(self):
        rows = self._results_model.rows()
        if not rows:
            self.toast.emit("No local results to export.", "warning")
            return
        target = Path(self._output_folder or Path.cwd()).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        path = target / "local_worker_current_results.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                [
                    "Candidate",
                    "Email",
                    "Score",
                    "Decision",
                    "Confidence",
                    "Duplicate",
                    "Matched Skills",
                    "Missing Skills",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        csv_safe(value)
                        for value in [
                            Path(row.get("file", "")).name,
                            row.get("email", ""),
                            row.get("score", 0),
                            decision_label(row.get("decision", "")),
                            row.get("confidence", ""),
                            "yes" if row.get("is_duplicate") else "no",
                            list_to_text(row.get("matched_skills")),
                            list_to_text(row.get("missing_skills")),
                        ]
                    ]
                )
        self.toast.emit(f"CSV exported: {path.name}", "success")

    @Slot()
    def showAppStatus(self):
        self.toast.emit(
            "QML desktop app is active. Local analysis, reports, templates, and sync are maintained here.", "info"
        )

    def _on_progress_max(self, value: int):
        self._progress_maximum = max(1, value)
        self.stateChanged.emit()

    def _on_progress(self, value: int):
        self._progress_value = value
        self.stateChanged.emit()

    def _on_row(self, row: dict):
        self._results_model.add_row(row)
        if self._selected_index < 0:
            self._selected_index = 0
            self.selectedChanged.emit()
            self.templateChanged.emit()
        self.metricsChanged.emit()
        self._refresh_report_preview()

    def _on_run_created(self, run_id: int):
        self._current_run_id = run_id

    def _on_done(self, message: str):
        self._is_running = False
        self._set_status(message)
        self.refreshHistory()
        self.refreshInbox()
        self._refresh_report_preview()
        self.syncChanged.emit()
        self.toast.emit("Local analysis completed.", "success")

    def _on_failed(self, message: str):
        self._is_running = False
        self._set_status("Failed")
        self.toast.emit(message, "error")


def main() -> int:
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    QCoreApplication.setOrganizationName("CV Analyzer")
    QCoreApplication.setOrganizationDomain("cvanalyzer.local")
    QCoreApplication.setApplicationName("CV Analyzer Local Worker")
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    icon_path = resource_path("assets/cv_analyzer_worker.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    backend = LocalWorkerBackend()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(resource_path("qml/Main.qml"))))
    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

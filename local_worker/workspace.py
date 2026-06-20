import json
import os
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path


def _app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    path = Path(base) / "CV Analyzer Local Worker"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _default_workspace_db() -> Path:
    configured = os.environ.get("CV_WORKER_WORKSPACE_DB")
    if configured:
        return Path(configured).expanduser()

    target = _app_data_dir() / "local_worker_workspace.sqlite3"
    legacy = Path("local_worker_workspace.sqlite3")
    if legacy.exists() and not target.exists():
        try:
            shutil.copy2(legacy, target)
        except Exception:
            return legacy
    return target


WORKSPACE_DB = _default_workspace_db()
SENSITIVE_RESULT_FIELDS = {"cv_text"}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _strip_sensitive_result_fields(value):
    if isinstance(value, dict):
        return {
            key: _strip_sensitive_result_fields(item)
            for key, item in value.items()
            if key not in SENSITIVE_RESULT_FIELDS
        }
    if isinstance(value, list):
        return [_strip_sensitive_result_fields(item) for item in value]
    return value


class WorkspaceStore:
    def __init__(self, db_path: Path | str = WORKSPACE_DB):
        self.db_path = Path(db_path)
        self._ensure()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _ensure(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS local_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    config_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER,
                    job_name TEXT NOT NULL,
                    cv_folder TEXT NOT NULL,
                    output_folder TEXT NOT NULL,
                    total_files INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT,
                    duplicate_of TEXT,
                    sync_status TEXT NOT NULL DEFAULT 'pending',
                    sync_error TEXT,
                    candidate_status TEXT NOT NULL DEFAULT 'pending_review',
                    score REAL NOT NULL,
                    decision TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "analysis_results", "file_hash", "file_hash TEXT")
            self._ensure_column(conn, "analysis_results", "duplicate_of", "duplicate_of TEXT")
            self._ensure_column(conn, "analysis_results", "sync_status", "sync_status TEXT NOT NULL DEFAULT 'pending'")
            self._ensure_column(conn, "analysis_results", "sync_error", "sync_error TEXT")
            self._ensure_column(conn, "analysis_results", "candidate_status", "candidate_status TEXT NOT NULL DEFAULT 'pending_review'")
            self._purge_sensitive_result_json(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    result_id INTEGER,
                    owner_id TEXT,
                    actor_user_id TEXT,
                    actor_role TEXT,
                    action_type TEXT NOT NULL,
                    module TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    description TEXT NOT NULL,
                    before_data TEXT,
                    after_data TEXT,
                    status TEXT NOT NULL DEFAULT 'success',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    result_id INTEGER,
                    owner_id TEXT,
                    actor_user_id TEXT,
                    candidate_name TEXT,
                    file_path TEXT,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    type TEXT NOT NULL,
                    channel TEXT NOT NULL DEFAULT 'in_app',
                    is_read INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )

    def _ensure_column(self, conn, table_name: str, column_name: str, column_sql: str):
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
        if column_name not in columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")

    def _purge_sensitive_result_json(self, conn):
        rows = conn.execute(
            "SELECT id, result_json FROM analysis_results WHERE result_json LIKE '%cv_text%'"
        ).fetchall()
        for row_id, raw_payload in rows:
            try:
                payload = json.loads(raw_payload)
            except (TypeError, json.JSONDecodeError):
                continue
            cleaned = _strip_sensitive_result_fields(payload)
            if cleaned != payload:
                conn.execute(
                    "UPDATE analysis_results SET result_json = ? WHERE id = ?",
                    (json.dumps(cleaned, ensure_ascii=False), row_id),
                )

    def list_jobs(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, config_json, updated_at FROM local_jobs ORDER BY updated_at DESC, name ASC"
            ).fetchall()
        return [
            {"id": row[0], "name": row[1], "config": json.loads(row[2]), "updated_at": row[3]}
            for row in rows
        ]

    def save_job(self, name: str, config: dict) -> int:
        clean_name = (name or "").strip() or "Untitled local job"
        payload = json.dumps(config, ensure_ascii=False)
        timestamp = _now()
        with self._connect() as conn:
            existing = conn.execute("SELECT id FROM local_jobs WHERE name = ?", (clean_name,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE local_jobs SET config_json = ?, updated_at = ? WHERE id = ?",
                    (payload, timestamp, existing[0]),
                )
                return int(existing[0])
            cursor = conn.execute(
                "INSERT INTO local_jobs (name, config_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (clean_name, payload, timestamp, timestamp),
            )
            return int(cursor.lastrowid)

    def create_run(self, job_id: int | None, job_name: str, cv_folder: str, output_folder: str, total_files: int) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analysis_runs (job_id, job_name, cv_folder, output_folder, total_files, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, job_name, cv_folder, output_folder, total_files, _now()),
            )
            return int(cursor.lastrowid)

    def add_result(self, run_id: int, row: dict):
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analysis_results
                    (run_id, file_path, file_hash, duplicate_of, sync_status, sync_error, candidate_status, score, decision, confidence, result_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    row.get("file", ""),
                    row.get("file_hash", ""),
                    row.get("duplicate_of", ""),
                    row.get("sync_status", "pending"),
                    row.get("sync_error", ""),
                    row.get("candidate_status", "pending_review"),
                    float(row.get("score") or 0),
                    row.get("decision", ""),
                    row.get("confidence", ""),
                    json.dumps(_strip_sensitive_result_fields(row), ensure_ascii=False),
                    _now(),
                ),
            )
            return int(cursor.lastrowid)

    def create_audit_log(
        self,
        *,
        run_id: int | None,
        result_id: int | None,
        action_type: str,
        module: str,
        resource_type: str,
        description: str,
        owner_id: str = "local-owner",
        actor_user_id: str = "local-worker",
        actor_role: str = "local_worker",
        resource_id: str = "",
        before_data: dict | None = None,
        after_data: dict | None = None,
        status: str = "success",
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_logs
                    (run_id, result_id, owner_id, actor_user_id, actor_role, action_type, module,
                     resource_type, resource_id, description, before_data, after_data, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    result_id,
                    owner_id,
                    actor_user_id,
                    actor_role,
                    action_type,
                    module,
                    resource_type,
                    resource_id,
                    description,
                    json.dumps(before_data or {}, ensure_ascii=False),
                    json.dumps(after_data or {}, ensure_ascii=False),
                    status,
                    _now(),
                ),
            )
            return int(cursor.lastrowid)

    def create_notification(
        self,
        *,
        run_id: int | None,
        result_id: int | None,
        title: str,
        message: str,
        type: str,
        channel: str = "in_app",
        owner_id: str = "local-owner",
        actor_user_id: str = "local-worker",
        candidate_name: str = "",
        file_path: str = "",
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO notifications
                    (run_id, result_id, owner_id, actor_user_id, candidate_name, file_path,
                     title, message, type, channel, is_read, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    run_id,
                    result_id,
                    owner_id,
                    actor_user_id,
                    candidate_name,
                    file_path,
                    title,
                    message,
                    type,
                    channel,
                    _now(),
                ),
            )
            return int(cursor.lastrowid)

    def update_result_sync_status(self, result_id: int, status: str, error: str = ""):
        with self._connect() as conn:
            conn.execute(
                "UPDATE analysis_results SET sync_status = ?, sync_error = ? WHERE id = ?",
                (status, error, result_id),
            )

    def update_result_decision_by_file(self, run_id: int, file_path: str, decision: str):
        with self._connect() as conn:
            existing_row = conn.execute(
                "SELECT decision, candidate_status, result_json, id FROM analysis_results WHERE run_id = ? AND file_path = ?",
                (run_id, file_path)
            ).fetchone()
            conn.execute(
                "UPDATE analysis_results SET decision = ? WHERE run_id = ? AND file_path = ?",
                (decision, run_id, file_path),
            )
            row = conn.execute(
                "SELECT result_json FROM analysis_results WHERE run_id = ? AND file_path = ?",
                (run_id, file_path)
            ).fetchone()
            if row:
                payload = _strip_sensitive_result_fields(json.loads(row[0]))
                payload["decision"] = decision
                conn.execute(
                    "UPDATE analysis_results SET result_json = ? WHERE run_id = ? AND file_path = ?",
                    (json.dumps(payload, ensure_ascii=False), run_id, file_path)
                )
        if existing_row:
            self.create_audit_log(
                run_id=run_id,
                result_id=existing_row[3],
                action_type="candidate_decision_changed",
                module="local_worker",
                resource_type="analysis_result",
                resource_id=file_path,
                description=f"Local candidate decision changed for {file_path}",
                before_data={"decision": existing_row[0], "candidate_status": existing_row[1]},
                after_data={"decision": decision},
            )

    def list_runs(self, job_id: int | None = None, limit: int = 25) -> list[dict]:
        sql = """
            SELECT id, job_id, job_name, cv_folder, output_folder, total_files, created_at
            FROM analysis_runs
        """
        params: tuple = ()
        if job_id:
            sql += " WHERE job_id = ?"
            params = (job_id,)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params = (*params, limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "id": row[0],
                "job_id": row[1],
                "job_name": row[2],
                "cv_folder": row[3],
                "output_folder": row[4],
                "total_files": row[5],
                "created_at": row[6],
            }
            for row in rows
        ]

    def get_run_results(self, run_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT result_json, sync_status, id
                FROM analysis_results
                WHERE run_id = ?
                ORDER BY score DESC, id ASC
                """,
                (run_id,),
            ).fetchall()
        results = []
        for row in rows:
            payload = json.loads(row[0])
            payload["sync_status"] = row[1]
            payload["local_result_id"] = row[2]
            results.append(payload)
        return results

    def list_audit_logs(self, run_id: int | None = None, limit: int = 100) -> list[dict]:
        sql = """
            SELECT id, run_id, result_id, action_type, module, resource_type, resource_id,
                   description, before_data, after_data, status, created_at
            FROM audit_logs
        """
        params: tuple = ()
        if run_id:
            sql += " WHERE run_id = ?"
            params = (run_id,)
        sql += " ORDER BY id DESC LIMIT ?"
        params = (*params, limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "id": row[0],
                "run_id": row[1],
                "result_id": row[2],
                "action_type": row[3],
                "module": row[4],
                "resource_type": row[5],
                "resource_id": row[6],
                "description": row[7],
                "before_data": json.loads(row[8] or "{}"),
                "after_data": json.loads(row[9] or "{}"),
                "status": row[10],
                "created_at": row[11],
            }
            for row in rows
        ]

    def list_notifications(self, unread_only: bool = False, limit: int = 100) -> list[dict]:
        sql = """
            SELECT id, run_id, result_id, candidate_name, file_path, title, message,
                   type, channel, is_read, created_at
            FROM notifications
        """
        params: tuple = ()
        if unread_only:
            sql += " WHERE is_read = 0"
        sql += " ORDER BY id DESC LIMIT ?"
        params = (*params, limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "id": row[0],
                "run_id": row[1],
                "result_id": row[2],
                "candidate_name": row[3],
                "file_path": row[4],
                "title": row[5],
                "message": row[6],
                "type": row[7],
                "channel": row[8],
                "is_read": bool(row[9]),
                "created_at": row[10],
            }
            for row in rows
        ]

    def list_pending_sync_results(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, result_json, sync_status, sync_error
                FROM analysis_results
                WHERE sync_status IN ('pending', 'failed', 'offline_ready')
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        results = []
        for row in rows:
            payload = json.loads(row[1])
            payload["local_result_id"] = row[0]
            payload["sync_status"] = row[2]
            payload["sync_error"] = row[3]
            results.append(payload)
        return results

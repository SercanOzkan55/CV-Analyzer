import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


WORKSPACE_DB = Path("local_worker_workspace.sqlite3")


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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

    def _ensure_column(self, conn, table_name: str, column_name: str, column_sql: str):
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
        if column_name not in columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")

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
            conn.execute(
                """
                INSERT INTO analysis_results
                    (run_id, file_path, file_hash, duplicate_of, sync_status, sync_error, score, decision, confidence, result_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    row.get("file", ""),
                    row.get("file_hash", ""),
                    row.get("duplicate_of", ""),
                    row.get("sync_status", "pending"),
                    row.get("sync_error", ""),
                    float(row.get("score") or 0),
                    row.get("decision", ""),
                    row.get("confidence", ""),
                    json.dumps(row, ensure_ascii=False),
                    _now(),
                ),
            )

    def update_result_sync_status(self, result_id: int, status: str, error: str = ""):
        with self._connect() as conn:
            conn.execute(
                "UPDATE analysis_results SET sync_status = ?, sync_error = ? WHERE id = ?",
                (status, error, result_id),
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
                SELECT result_json
                FROM analysis_results
                WHERE run_id = ?
                ORDER BY score DESC, id ASC
                """,
                (run_id,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def list_pending_sync_results(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, result_json, sync_status, sync_error
                FROM analysis_results
                WHERE sync_status IN ('pending', 'failed')
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

import csv
import hashlib
import json
import os
import sys
import tempfile
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

try:
    from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPoint, QPropertyAnimation, QObject, Qt, QThread, QTimer, Signal
    from PySide6.QtGui import QAction, QIcon
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QGraphicsOpacityEffect,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QSizePolicy,
        QSpinBox,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    from ctypes import windll

    message = (
        "PySide6 is required for the modern Local Worker app.\n\n"
        "Run install_windows.cmd or start_here.cmd again so dependencies are installed."
    )
    try:
        windll.user32.MessageBoxW(None, message, "CV Analyzer Local Worker", 0x10)
    except Exception:
        print(message, file=sys.stderr)
    sys.exit(1)

import worker as worker_module
from credentials import load_worker_api_key, save_worker_api_key
from worker import API_BASE_URL, MAX_FILE_BYTES, LocalWorker, extract_text, maybe_apply_ai_review, score_cv
from workspace import WorkspaceStore


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MOTION_ENABLED = os.environ.get("CV_WORKER_DISABLE_MOTION", "").lower() not in {"1", "true", "yes"}


def resource_path(relative_path: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    path = Path(base) / "CV Analyzer Local Worker"
    path.mkdir(parents=True, exist_ok=True)
    return path


def crash_log_path() -> Path:
    return app_data_dir() / "crash.log"


def write_crash_log(message: str) -> Path:
    path = crash_log_path()
    path.write_text(
        f"CV Analyzer Local Worker crash\n{datetime.now(UTC).isoformat().replace('+00:00', 'Z')}\n\n{message}\n",
        encoding="utf-8",
    )
    return path


def split_terms(value: str) -> list[str]:
    return [item.strip() for item in (value or "").replace("\n", ",").split(",") if item.strip()]


def decision_label(decision: str) -> str:
    return {
        "recommended_accept": "Accept",
        "recommended_review": "Review",
        "recommended_reject": "Reject",
    }.get(decision, decision or "Unknown")


def decision_rank(decision: str) -> int:
    return {"recommended_accept": 0, "recommended_review": 1, "recommended_reject": 2}.get(decision, 3)


class AnalysisWorker(QObject):
    progress_max = Signal(int)
    progress = Signal(int)
    status = Signal(str)
    row = Signal(dict)
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
        files = [
            path
            for path in self.folder.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        files.sort(key=lambda p: str(p).lower())
        if not files:
            self.done.emit("No PDF, DOCX, or TXT files found.")
            return

        self.output.mkdir(parents=True, exist_ok=True)
        run_id = self.store.create_run(None, self.job_name, str(self.folder), str(self.output), len(files))
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
                row = {
                    **result,
                    "rank": 0,
                    "file": str(path),
                    "file_hash": file_hash,
                    "is_duplicate": bool(duplicate_of),
                    "duplicate_of": duplicate_of or "",
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
                writer.writerow(
                    {
                        **row,
                        "matched_skills": ", ".join(row.get("matched_skills") or []),
                        "missing_skills": ", ".join(row.get("missing_skills") or []),
                        "risk_flags": ", ".join(row.get("risk_flags") or []),
                    }
                )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CV Analyzer Local Worker")
        self.resize(1280, 820)
        icon_path = resource_path("assets/cv_analyzer_worker.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.thread: QThread | None = None
        self.worker: AnalysisWorker | None = None
        self.rows: list[dict] = []
        self.store = WorkspaceStore()
        self._animations: list[QPropertyAnimation] = []
        self._progress_animation: QPropertyAnimation | None = None
        self._status_pulse: QPropertyAnimation | None = None
        self.nav_buttons: list[QPushButton] = []
        self.analysis_started_at: float | None = None
        self.analysis_total_files = 0

        self._build()
        self._apply_style()
        self._refresh_history()
        if MOTION_ENABLED:
            self.setWindowOpacity(0.0)
            QTimer.singleShot(90, self._animate_startup)

    def _build(self):
        root = QWidget()
        root.setObjectName("Root")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        root_layout.addWidget(sidebar)

        main_panel = QWidget()
        main_panel.setObjectName("MainPanel")
        root_layout.addWidget(main_panel, 1)

        outer = QVBoxLayout(main_panel)
        outer.setContentsMargins(28, 20, 28, 22)
        outer.setSpacing(20)

        header = QHBoxLayout()
        header.setSpacing(16)
        header_icon = QLabel("✦")
        header_icon.setObjectName("HeaderIcon")
        header.addWidget(header_icon)
        title_box = QVBoxLayout()
        title = QLabel("CV Analyzer Local Worker")
        title.setObjectName("Title")
        subtitle = QLabel("Private desktop ranking for large CV folders. No site-side job required.")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("StatusPill")
        header.addWidget(self.status_label)
        sync_label = QLabel("↻  Last sync: local")
        sync_label.setObjectName("SyncMeta")
        header.addWidget(sync_label)
        sync_button = QPushButton("↻  Sync now")
        sync_button.setObjectName("PrimaryButton")
        sync_button.setMinimumWidth(136)
        header.addWidget(sync_button)
        outer.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()
        self.tabs.addTab(self._build_analyze_tab(), "Analyze")
        self.tabs.addTab(self._build_results_tab(), "Results")
        self.tabs.addTab(self._build_history_tab(), "History")
        self.tabs.addTab(self._build_server_tab(), "Website Sync")
        self.tabs.addTab(self._build_dashboard_tab(), "Dashboard")
        self.tabs.addTab(self._build_reports_tab(), "Reports")
        self.tabs.addTab(self._build_preferences_tab(), "Preferences")
        self.tabs.addTab(self._build_ai_models_tab(), "AI Models")
        self.tabs.currentChanged.connect(self._animate_tab_change)
        self.tabs.currentChanged.connect(self._update_nav_state)
        sync_button.clicked.connect(lambda: self.tabs.setCurrentIndex(3))
        outer.addWidget(self.tabs, 1)
        self.setCentralWidget(root)

        open_output = QAction("Open output folder", self)
        open_output.triggered.connect(self._open_output)
        self.addAction(open_output)
        self._update_nav_state(0)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(228)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 18)
        layout.setSpacing(18)

        brand = QHBoxLayout()
        logo = QLabel("✧")
        logo.setObjectName("LogoMark")
        brand_text = QVBoxLayout()
        brand_title = QLabel("CV Analyzer")
        brand_title.setObjectName("SidebarBrand")
        brand_sub = QLabel("Local Worker")
        brand_sub.setObjectName("SidebarSub")
        brand_text.addWidget(brand_title)
        brand_text.addWidget(brand_sub)
        brand.addWidget(logo)
        brand.addLayout(brand_text, 1)
        layout.addLayout(brand)
        layout.addSpacing(18)

        layout.addWidget(self._nav_button("⌁  Analyze", 0))
        layout.addWidget(self._nav_button("▥  Results", 1))
        layout.addWidget(self._nav_button("↺  History", 2))
        layout.addWidget(self._nav_button("⟳  Sync", 3, has_dot=True))
        layout.addSpacing(18)

        insights = QLabel("INSIGHTS")
        insights.setObjectName("SidebarSection")
        layout.addWidget(insights)
        layout.addWidget(self._passive_nav_button("▥  Dashboard"))
        layout.addWidget(self._passive_nav_button("□  Reports"))
        layout.addSpacing(12)

        settings = QLabel("SETTINGS")
        settings.setObjectName("SidebarSection")
        layout.addWidget(settings)
        layout.addWidget(self._passive_nav_button("⚙  Preferences"))
        layout.addWidget(self._passive_nav_button("⚙  AI Models"))
        layout.addStretch(1)

        user_row = QHBoxLayout()
        avatar = QLabel("AW")
        avatar.setObjectName("Avatar")
        user_text = QVBoxLayout()
        user = QLabel("Admin User")
        user.setObjectName("SidebarUser")
        role = QLabel("Administrator")
        role.setObjectName("SidebarSub")
        user_text.addWidget(user)
        user_text.addWidget(role)
        user_row.addWidget(avatar)
        user_row.addLayout(user_text, 1)
        layout.addLayout(user_row)
        return sidebar

    def _nav_button(self, text: str, index: int, has_dot: bool = False) -> QPushButton:
        button = QPushButton(text + ("      ●" if has_dot else ""))
        button.setObjectName("SidebarNav")
        button.setCheckable(True)
        button.clicked.connect(lambda: self.tabs.setCurrentIndex(index))
        self.nav_buttons.append(button)
        return button

    def _passive_nav_button(self, text: str) -> QPushButton:
        route_map = {
            "Dashboard": 4,
            "Reports": 5,
            "Preferences": 6,
            "AI Models": 7,
        }
        for label, index in route_map.items():
            if label in text:
                return self._nav_button(text, index)
        button = QPushButton(text)
        button.setObjectName("SidebarPassive")
        button.setEnabled(False)
        return button

    def _update_nav_state(self, index: int):
        for idx, button in enumerate(self.nav_buttons):
            button.setChecked(idx == index)

    def _build_analyze_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("AnalyzePage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(22)

        metrics = QHBoxLayout()
        metrics.setSpacing(20)
        self.metric_candidates = QLabel("0")
        self.metric_avg_score = QLabel("--")
        self.metric_shortlisted = QLabel("0")
        self.metric_hard_rejects = QLabel("0")
        metrics.addWidget(self._metric_card("Candidates", self.metric_candidates, "Ready to analyze", "👥", "PurpleBadge"))
        metrics.addWidget(self._metric_card("Avg. Match Score", self.metric_avg_score, "Across all candidates", "↗", "GreenBadge"))
        metrics.addWidget(self._metric_card("Shortlisted", self.metric_shortlisted, "Above review threshold", "★", "BlueBadge"))
        metrics.addWidget(self._metric_card("Hard Rejects", self.metric_hard_rejects, "Filtered out", "✕", "RedBadge"))
        layout.addLayout(metrics)

        setup_grid = QGridLayout()
        setup_grid.setHorizontalSpacing(20)
        setup_grid.setColumnStretch(0, 1)
        setup_grid.setColumnStretch(1, 1)

        job_group = QFrame()
        job_group.setObjectName("ContentCard")
        form = QVBoxLayout(job_group)
        form.setContentsMargins(24, 22, 24, 24)
        form.setSpacing(14)
        form.addLayout(self._step_header("1", "Local job setup", "Select folders and configure analysis settings."))
        self.job_name = QLineEdit("New local job")
        self.cv_folder = QLineEdit()
        self.output_folder = QLineEdit(str(Path.cwd() / "local_results"))
        self.accept_threshold = QSpinBox()
        self.accept_threshold.setRange(1, 100)
        self.accept_threshold.setValue(75)
        self.review_threshold = QSpinBox()
        self.review_threshold.setRange(1, 100)
        self.review_threshold.setValue(50)
        self.ai_mode = QComboBox()
        self.ai_mode.addItems(["none", "customer_openai_key"])
        self.cv_folder.setPlaceholderText("Select CV folder...")
        form.addLayout(self._labeled_control("Job name", self.job_name))
        form.addLayout(self._labeled_control("CV folder", self._path_row(self.cv_folder, self._choose_cv_folder)))
        form.addLayout(self._labeled_control("Output folder", self._path_row(self.output_folder, self._choose_output_folder)))

        threshold_row = QHBoxLayout()
        threshold_row.setSpacing(16)
        threshold_row.addLayout(self._labeled_control("Accept threshold", self.accept_threshold), 1)
        threshold_row.addLayout(self._labeled_control("Review threshold", self.review_threshold), 1)
        form.addLayout(threshold_row)
        form.addLayout(self._labeled_control("AI review", self.ai_mode))

        terms_group = QFrame()
        terms_group.setObjectName("ContentCard")
        terms = QVBoxLayout(terms_group)
        terms.setContentsMargins(24, 22, 24, 24)
        terms.setSpacing(13)
        terms.addLayout(self._step_header("2", "Scoring criteria", "Define how candidates will be evaluated."))
        self.required_skills = QPlainTextEdit()
        self.required_skills.setPlaceholderText("Enter required skills...")
        self.nice_skills = QPlainTextEdit()
        self.nice_skills.setPlaceholderText("Enter nice to have skills...")
        self.hard_reject = QPlainTextEdit()
        self.hard_reject.setPlaceholderText("Enter hard reject criteria...")
        for field in (self.required_skills, self.nice_skills, self.hard_reject):
            field.setMinimumHeight(72)
            field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        terms.addLayout(self._labeled_control("Required skills", self.required_skills))
        terms.addLayout(self._labeled_control("Nice to have", self.nice_skills))
        terms.addLayout(self._labeled_control("Hard reject criteria", self.hard_reject))

        setup_grid.addWidget(job_group, 0, 0)
        setup_grid.addWidget(terms_group, 0, 1)
        layout.addLayout(setup_grid)

        self.description = QPlainTextEdit()
        self.description.setPlaceholderText("Paste the job description here. This stays local unless you explicitly sync later.")
        self.description.setMinimumHeight(126)
        description_group = QFrame()
        description_group.setObjectName("ContentCard")
        description_layout = QVBoxLayout(description_group)
        description_layout.setContentsMargins(24, 22, 24, 24)
        description_layout.setSpacing(14)
        description_layout.addLayout(self._step_header("3", "Job description", "Paste the full job description. More context leads to better matching."))
        description_layout.addWidget(self.description)
        layout.addWidget(description_group)

        actions = QHBoxLayout()
        actions.setSpacing(16)
        self.run_button = QPushButton("▷  Analyze local folder")
        self.run_button.setObjectName("PrimaryButton")
        self.run_button.setMinimumWidth(230)
        self.cancel_button = QPushButton("×  Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.setMinimumWidth(136)
        self.cancel_button.setEnabled(False)
        self.open_output_button = QPushButton("↗  Open output")
        self.open_output_button.setObjectName("SecondaryButton")
        self.open_output_button.setMinimumWidth(182)
        self.run_button.clicked.connect(self._start_analysis)
        self.cancel_button.clicked.connect(self._cancel_analysis)
        self.open_output_button.clicked.connect(self._open_output)
        actions.addWidget(self.run_button)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.open_output_button)
        actions.addStretch(1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

        footer = QFrame()
        footer.setObjectName("FooterBar")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.setSpacing(18)
        footer_layout.addLayout(actions)
        footer_layout.addStretch(1)
        self.queue_status_label = QLabel("Queue: idle")
        self.queue_status_label.setObjectName("FooterMeta")
        self.eta_status_label = QLabel("ETA: --")
        self.eta_status_label.setObjectName("FooterMeta")
        footer_layout.addWidget(self.queue_status_label)
        footer_layout.addWidget(self.eta_status_label)
        ready = QLabel("✓  Ready to analyze")
        ready.setObjectName("FooterReady")
        footer_layout.addWidget(ready)
        self.progress.setFixedWidth(360)
        footer_layout.addWidget(self.progress)
        layout.addWidget(footer)
        return page

    def _build_results_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        stats = QHBoxLayout()
        self.total_label = QLabel("Total: 0")
        self.accept_label = QLabel("Accept: 0")
        self.review_label = QLabel("Review: 0")
        self.reject_label = QLabel("Reject: 0")
        for label in (self.total_label, self.accept_label, self.review_label, self.reject_label):
            label.setObjectName("Metric")
            stats.addWidget(label)
        stats.addStretch(1)
        layout.addLayout(stats)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["File", "Score", "Decision", "Confidence", "Duplicate", "Matched", "Missing", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for index in range(1, 8):
            self.table.horizontalHeader().setSectionResizeMode(index, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._show_selected_detail)
        layout.addWidget(self.table, 1)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(170)
        layout.addWidget(self.detail)
        return page

    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        self.history_combo = QComboBox()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_history)
        load = QPushButton("Load selected run")
        load.clicked.connect(self._load_history_run)
        top.addWidget(self.history_combo, 1)
        top.addWidget(refresh)
        top.addWidget(load)
        layout.addLayout(top)
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        layout.addWidget(self.history_text, 1)
        return page

    def _build_server_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        box = QGroupBox("Optional website connection")
        form = QFormLayout(box)
        self.api_url = QLineEdit(os.environ.get("CV_ANALYZER_API_URL", API_BASE_URL))
        self.api_key = QLineEdit(load_worker_api_key() or os.environ.get("CV_WORKER_API_KEY", ""))
        self.api_key.setEchoMode(QLineEdit.Password)
        form.addRow("API URL", self.api_url)
        form.addRow("Worker key", self.api_key)
        buttons = QHBoxLayout()
        save = QPushButton("Save key locally")
        test = QPushButton("Test connection")
        test.setObjectName("PrimaryButton")
        save.clicked.connect(self._save_key)
        test.clicked.connect(self._test_connection)
        buttons.addWidget(save)
        buttons.addWidget(test)
        buttons.addStretch(1)
        form.addRow("", buttons)
        layout.addWidget(box)
        note = QLabel("Server sync is optional. Local folder analysis works without a website job or API key.")
        note.setObjectName("Subtitle")
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _build_dashboard_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        top = QHBoxLayout()
        self.dashboard_total = QLabel("0 candidates")
        self.dashboard_queue = QLabel("No active queue")
        self.dashboard_eta = QLabel("ETA: --")
        top.addWidget(self._summary_card("Run volume", self.dashboard_total, "Processed in the current run"))
        top.addWidget(self._summary_card("Live queue", self.dashboard_queue, "Current local processing state"))
        top.addWidget(self._summary_card("Estimated finish", self.dashboard_eta, "Calculated while analysis is running"))
        layout.addLayout(top)

        trust = QFrame()
        trust.setObjectName("ContentCard")
        trust_layout = QVBoxLayout(trust)
        trust_layout.setContentsMargins(24, 22, 24, 24)
        trust_layout.setSpacing(10)
        trust_layout.addLayout(self._step_header("✓", "Enterprise trust controls", "Local analysis is designed for large employer folders."))
        for text in (
            "CV files stay on this computer unless you explicitly sync results.",
            "Website API keys are stored in the OS credential store when available.",
            "Only scores, decisions, explanations, and optional sync payloads are sent back.",
            "Duplicate files are detected locally to avoid noisy ranking output.",
        ):
            label = QLabel("•  " + text)
            label.setObjectName("TrustLine")
            trust_layout.addWidget(label)
        layout.addWidget(trust)
        layout.addStretch(1)
        return page

    def _build_reports_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        self.report_preview = QTextEdit()
        self.report_preview.setReadOnly(True)
        self.report_preview.setPlainText("No report yet. Run a local analysis to generate JSON and CSV outputs.")
        self.report_preview.setMinimumHeight(240)
        layout.addWidget(self._panel_with_title("Report preview", self.report_preview))
        actions = QHBoxLayout()
        open_output = QPushButton("Open output folder")
        open_output.setObjectName("PrimaryButton")
        open_output.clicked.connect(self._open_output)
        actions.addWidget(open_output)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)
        return page

    def _build_preferences_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        prefs = QFrame()
        prefs.setObjectName("ContentCard")
        form = QFormLayout(prefs)
        form.setContentsMargins(24, 24, 24, 24)
        theme = QComboBox()
        theme.addItems(["Professional light", "System managed"])
        max_size = QLabel(f"{MAX_FILE_BYTES // (1024 * 1024)} MB per file")
        motion = QLabel("Enabled, respects CV_WORKER_DISABLE_MOTION=1")
        form.addRow("Theme", theme)
        form.addRow("Max file guard", max_size)
        form.addRow("Motion", motion)
        layout.addWidget(prefs)
        layout.addWidget(self._info_block("Operational defaults", [
            "Use SSD-backed folders for 4,000+ CV batches.",
            "Keep output folders outside the input CV folder to avoid reprocessing reports.",
            "Use the Website Sync tab only when you want to upload results back to the SaaS account.",
        ]))
        layout.addStretch(1)
        return page

    def _build_ai_models_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        layout.addWidget(self._info_block("AI review modes", [
            "none: fastest and cheapest; uses deterministic rule-based scoring.",
            "customer_openai_key: reserved for local customer-owned review in a later package.",
            "No platform OpenAI key is embedded in the desktop app.",
        ]))
        layout.addWidget(self._info_block("Current MVP scoring", [
            "Required skills, nice-to-have skills, hard reject rules, job description overlap, and text quality.",
            "PDF, DOCX, and TXT extraction run locally.",
            "A low-confidence result is still explainable and can be reviewed before sync.",
        ]))
        layout.addStretch(1)
        return page

    def _path_row(self, field: QLineEdit, callback) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        button = QPushButton("Browse")
        button.setObjectName("SecondaryButton")
        button.setMinimumWidth(110)
        button.clicked.connect(callback)
        layout.addWidget(field, 1)
        layout.addWidget(button)
        return row

    def _metric_card(self, title: str, value_label: QLabel, subtitle: str, icon: str, badge_name: str) -> QWidget:
        card = QFrame()
        card.setObjectName("MetricCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(16)
        copy = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("MetricTitle")
        value_label.setObjectName("MetricValue")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("MetricSub")
        copy.addWidget(title_label)
        copy.addWidget(value_label)
        copy.addWidget(subtitle_label)
        layout.addLayout(copy, 1)
        badge = QLabel(icon)
        badge.setObjectName(badge_name)
        badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(badge)
        return card

    def _summary_card(self, title: str, value_label: QLabel, subtitle: str) -> QWidget:
        card = QFrame()
        card.setObjectName("MetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 18, 22, 18)
        title_label = QLabel(title)
        title_label.setObjectName("MetricTitle")
        value_label.setObjectName("MetricValue")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("MetricSub")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(subtitle_label)
        return card

    def _panel_with_title(self, title: str, widget: QWidget) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ContentCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 24)
        heading = QLabel(title)
        heading.setObjectName("StepTitle")
        layout.addWidget(heading)
        layout.addWidget(widget)
        return panel

    def _info_block(self, title: str, lines: list[str]) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ContentCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("StepTitle")
        layout.addWidget(heading)
        for line in lines:
            label = QLabel("•  " + line)
            label.setObjectName("TrustLine")
            label.setWordWrap(True)
            layout.addWidget(label)
        return panel

    def _step_header(self, number: str, title: str, subtitle: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        badge = QLabel(number)
        badge.setObjectName("StepBadge")
        badge.setAlignment(Qt.AlignCenter)
        text_box = QVBoxLayout()
        heading = QLabel(title)
        heading.setObjectName("StepTitle")
        sub = QLabel(subtitle)
        sub.setObjectName("StepSubtitle")
        text_box.addWidget(heading)
        text_box.addWidget(sub)
        row.addWidget(badge)
        row.addLayout(text_box, 1)
        return row

    def _labeled_control(self, label_text: str, widget_or_layout) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = QLabel(label_text)
        label.setObjectName("FieldLabel")
        layout.addWidget(label)
        if isinstance(widget_or_layout, QWidget):
            layout.addWidget(widget_or_layout)
        else:
            layout.addLayout(widget_or_layout)
        return layout

    def _run_animation(self, animation: QPropertyAnimation):
        if not MOTION_ENABLED:
            return
        self._animations.append(animation)

        def cleanup():
            if animation in self._animations:
                self._animations.remove(animation)

        animation.finished.connect(cleanup)
        animation.start(QAbstractAnimation.DeleteWhenStopped)

    def _animate_startup(self):
        if not MOTION_ENABLED:
            self.setWindowOpacity(1.0)
            return
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(320)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        self._run_animation(fade)
        self._slide_widget(self.tabs, offset=14, duration=360)

    def _slide_widget(self, widget: QWidget, offset: int = 10, duration: int = 240):
        if not MOTION_ENABLED:
            return
        end = widget.pos()
        start = QPoint(end.x(), end.y() + offset)
        widget.move(start)
        animation = QPropertyAnimation(widget, b"pos", self)
        animation.setDuration(duration)
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        self._run_animation(animation)

    def _animate_tab_change(self):
        if not MOTION_ENABLED:
            return
        effect = self.tabs.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(self.tabs)
            self.tabs.setGraphicsEffect(effect)
        effect.setOpacity(0.78)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(180)
        animation.setStartValue(0.78)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        self._run_animation(animation)

    def _start_status_pulse(self):
        if not MOTION_ENABLED:
            return
        effect = self.status_label.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(self.status_label)
            self.status_label.setGraphicsEffect(effect)
        effect.setOpacity(1.0)
        pulse = QPropertyAnimation(effect, b"opacity", self)
        pulse.setDuration(780)
        pulse.setStartValue(0.72)
        pulse.setEndValue(1.0)
        pulse.setEasingCurve(QEasingCurve.InOutSine)
        pulse.setLoopCount(-1)
        self._status_pulse = pulse
        pulse.start()

    def _stop_status_pulse(self):
        if self._status_pulse:
            self._status_pulse.stop()
            self._status_pulse = None
        effect = self.status_label.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            effect.setOpacity(1.0)

    def _set_progress_value(self, value: int):
        if not MOTION_ENABLED:
            self.progress.setValue(value)
            return
        if self._progress_animation:
            self._progress_animation.stop()
        animation = QPropertyAnimation(self.progress, b"value", self)
        animation.setDuration(120)
        animation.setStartValue(self.progress.value())
        animation.setEndValue(value)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        self._progress_animation = animation

        def clear_progress_animation():
            if self._progress_animation is animation:
                self._progress_animation = None

        animation.finished.connect(clear_progress_animation)
        animation.start(QAbstractAnimation.DeleteWhenStopped)

    def _on_progress_max(self, value: int):
        total = max(1, int(value or 1))
        self.analysis_total_files = total
        self.progress.setRange(0, total)
        self._update_live_status(0, total)

    def _on_progress(self, value: int):
        current = int(value or 0)
        total = max(1, self.analysis_total_files or self.progress.maximum() or 1)
        self._set_progress_value(current)
        self._update_live_status(current, total)

    def _update_live_status(self, current: int, total: int):
        remaining = max(0, total - current)
        queue_text = f"Queue: {current}/{total}"
        if hasattr(self, "queue_status_label"):
            self.queue_status_label.setText(queue_text)
        if hasattr(self, "dashboard_queue"):
            self.dashboard_queue.setText(f"{remaining} remaining")

        eta_text = "ETA: --"
        if self.analysis_started_at and current > 0:
            elapsed = max(0.1, time.monotonic() - self.analysis_started_at)
            seconds = int((elapsed / current) * remaining)
            if seconds >= 60:
                eta_text = f"ETA: {seconds // 60}m {seconds % 60}s"
            else:
                eta_text = f"ETA: {seconds}s"
        if hasattr(self, "eta_status_label"):
            self.eta_status_label.setText(eta_text)
        if hasattr(self, "dashboard_eta"):
            self.dashboard_eta.setText(eta_text.replace("ETA: ", "") or "--")

    def _apply_style(self):
        self.setStyleSheet(
            """
            QWidget#Root, QMainWindow {
                background: #111c2e;
            }
            QWidget {
                background: transparent;
                color: #f3f7fb;
                font-family: "Segoe UI";
                font-size: 10pt;
            }
            QWidget#MainPanel {
                background: #fbfcff;
                border-top-left-radius: 18px;
                border-bottom-left-radius: 18px;
            }
            QFrame#Sidebar {
                background: #041534;
                border: none;
            }
            QLabel#LogoMark {
                min-width: 54px;
                min-height: 54px;
                max-width: 54px;
                max-height: 54px;
                border-radius: 15px;
                background: #4b4cff;
                color: #ffffff;
                font-size: 24px;
                font-weight: 900;
                qproperty-alignment: AlignCenter;
            }
            QLabel#SidebarBrand {
                color: #ffffff;
                font-size: 12pt;
                font-weight: 900;
            }
            QLabel#SidebarSub, QLabel#SidebarSection {
                color: #a9b8cf;
                font-size: 9.5pt;
            }
            QLabel#SidebarSection {
                font-size: 8.5pt;
                letter-spacing: 1px;
            }
            QLabel#SidebarUser {
                color: #ffffff;
                font-weight: 800;
            }
            QLabel#Avatar {
                min-width: 44px;
                min-height: 44px;
                max-width: 44px;
                max-height: 44px;
                border-radius: 22px;
                background: #5a4cff;
                color: #ffffff;
                font-weight: 900;
                qproperty-alignment: AlignCenter;
            }
            QPushButton#SidebarNav, QPushButton#SidebarPassive {
                background: transparent;
                border: none;
                border-radius: 8px;
                color: #c5d2e5;
                padding: 14px 14px;
                text-align: left;
                font-size: 11pt;
                font-weight: 750;
            }
            QPushButton#SidebarNav:hover {
                background: #0c244a;
                color: #ffffff;
            }
            QPushButton#SidebarNav:checked {
                background: #2639e8;
                color: #ffffff;
            }
            QPushButton#SidebarPassive:disabled {
                color: #c5d2e5;
                background: transparent;
            }
            QLabel#Title {
                color: #10172a;
                font-size: 26px;
                font-weight: 800;
            }
            QLabel#Subtitle {
                color: #5f6b80;
            }
            QLabel#HeaderIcon {
                min-width: 52px;
                min-height: 52px;
                max-width: 52px;
                max-height: 52px;
                border-radius: 12px;
                background: #eef5ff;
                color: #2f86ff;
                font-size: 24px;
                font-weight: 900;
                qproperty-alignment: AlignCenter;
            }
            QLabel#StatusPill, QLabel#Metric {
                padding: 8px 18px;
                border: 1px solid #ccefe1;
                border-radius: 18px;
                background: #effdf6;
                color: #0f8d4f;
                font-weight: 800;
            }
            QLabel#SyncMeta {
                color: #4f5c70;
                font-weight: 750;
            }
            QTabWidget::pane {
                border: none;
                background: transparent;
                top: 0;
            }
            QTabBar::tab {
                padding: 14px 18px 13px;
                margin-right: 8px;
                border: none;
                border-bottom: 2px solid transparent;
                background: transparent;
                color: #9faec0;
                font-size: 11pt;
                font-weight: 750;
            }
            QTabBar::tab:selected {
                color: #48a2ff;
                border-bottom: 2px solid #2f86ff;
            }
            QTabBar::tab:hover {
                color: #d7e7f8;
            }
            QGroupBox {
                border: 1px solid #d8dfeb;
                border-radius: 14px;
                margin-top: 14px;
                padding: 22px 18px 18px;
                background: #ffffff;
                font-size: 12pt;
                font-weight: 800;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 8px;
                color: #10172a;
            }
            QFrame#MetricCard, QFrame#ContentCard, QFrame#FooterBar {
                background: #ffffff;
                border: 1px solid #dfe5ef;
                border-radius: 14px;
            }
            QFrame#MetricCard {
                min-height: 102px;
            }
            QLabel#MetricTitle {
                color: #344057;
                font-weight: 800;
            }
            QLabel#MetricValue {
                color: #111827;
                font-size: 24pt;
                font-weight: 900;
            }
            QLabel#MetricSub {
                color: #657287;
                font-size: 9.5pt;
            }
            QLabel#PurpleBadge, QLabel#GreenBadge, QLabel#BlueBadge, QLabel#RedBadge {
                min-width: 56px;
                min-height: 56px;
                max-width: 56px;
                max-height: 56px;
                border-radius: 12px;
                font-size: 22px;
                font-weight: 900;
            }
            QLabel#PurpleBadge { background: #eee4ff; color: #6a35df; }
            QLabel#GreenBadge { background: #dcfbef; color: #21b981; }
            QLabel#BlueBadge { background: #e8f0ff; color: #2c7ddd; }
            QLabel#RedBadge { background: #ffe7ea; color: #c4364a; }
            QLabel#StepBadge {
                min-width: 30px;
                min-height: 30px;
                max-width: 30px;
                max-height: 30px;
                border-radius: 15px;
                background: #4b55ff;
                color: #ffffff;
                font-weight: 900;
            }
            QLabel#StepTitle {
                color: #111827;
                font-size: 12.5pt;
                font-weight: 900;
            }
            QLabel#StepSubtitle {
                color: #657287;
                font-size: 9.5pt;
            }
            QLabel#FooterReady {
                color: #111827;
                font-weight: 900;
            }
            QLabel#FooterMeta, QLabel#TrustLine {
                color: #516074;
                font-weight: 700;
            }
            QLabel#FieldLabel {
                color: #4a5568;
                font-size: 9.5pt;
                font-weight: 800;
            }
            QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {
                background: #ffffff;
                color: #111827;
                border: 1px solid #d7deea;
                border-radius: 9px;
                padding: 11px 14px;
                selection-background-color: #245fd6;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
                border-color: #3f82ff;
                background: #ffffff;
            }
            QLineEdit::placeholder, QPlainTextEdit::placeholder {
                color: #93a2b5;
            }
            QPlainTextEdit, QTextEdit {
                line-height: 1.5;
            }
            QComboBox::drop-down {
                width: 28px;
                border: none;
            }
            QPushButton {
                background: #f8fafc;
                color: #263348;
                border: 1px solid #d8dfeb;
                border-radius: 9px;
                padding: 11px 18px;
                font-size: 10.5pt;
                font-weight: 800;
            }
            QPushButton:hover {
                background: #eef4ff;
                border-color: #a9c5ff;
            }
            QPushButton:pressed {
                background: #dfeaff;
            }
            QPushButton:disabled {
                color: #8d99aa;
                background: #eef2f6;
                border-color: #d8dfeb;
            }
            QPushButton#PrimaryButton {
                background: #2367ff;
                border-color: #2f7dff;
                color: #ffffff;
            }
            QPushButton#PrimaryButton:hover {
                background: #2f7cff;
                border-color: #63a3ff;
            }
            QPushButton#SecondaryButton {
                background: #f8fafc;
                border-color: #d8dfeb;
                color: #263348;
            }
            QProgressBar {
                border: none;
                border-radius: 8px;
                background: #eef2f6;
                text-align: right;
                color: #1e293b;
                height: 18px;
            }
            QProgressBar::chunk {
                border-radius: 8px;
                background: #2367ff;
            }
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #f8fafc;
                border: 1px solid #dfe5ef;
                border-radius: 10px;
                gridline-color: #e7edf5;
                selection-background-color: #235ed0;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background: #f3f6fa;
                color: #344057;
                border: none;
                border-right: 1px solid #dfe5ef;
                padding: 10px;
                font-weight: 800;
            }
            QScrollBar:vertical {
                background: #edf2f7;
                width: 12px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #b9c4d3;
                border-radius: 6px;
                min-height: 28px;
            }
            QScrollBar::handle:vertical:hover {
                background: #95a3b5;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            """
        )

    def _choose_cv_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose CV folder", self.cv_folder.text() or str(Path.home()))
        if folder:
            self.cv_folder.setText(folder)

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_folder.text() or str(Path.cwd()))
        if folder:
            self.output_folder.setText(folder)

    def _config(self) -> dict:
        return {
            "job_id": "local",
            "title": self.job_name.text().strip() or "Local job",
            "description": self.description.toPlainText().strip(),
            "required_skills": split_terms(self.required_skills.toPlainText()),
            "nice_to_have_skills": split_terms(self.nice_skills.toPlainText()),
            "hard_reject_criteria": split_terms(self.hard_reject.toPlainText()),
            "accept_threshold": self.accept_threshold.value(),
            "review_threshold": self.review_threshold.value(),
            "reject_threshold": 0,
            "scoring_weights": {"required_skills": 70, "nice_to_have_skills": 20, "content_quality": 10},
        }

    def _start_analysis(self):
        folder = Path(self.cv_folder.text().strip())
        output = Path(self.output_folder.text().strip())
        config = self._config()
        if not folder.is_dir():
            QMessageBox.warning(self, "Missing folder", "Choose a valid CV folder.")
            return
        if not config["description"] and not config["required_skills"]:
            QMessageBox.warning(self, "Missing criteria", "Add a job description or at least one required skill.")
            return

        self.rows = []
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.detail.clear()
        self._update_metrics()
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status_label.setText("Starting...")
        self._start_status_pulse()
        self.tabs.setCurrentIndex(1)

        self.thread = QThread()
        self.worker = AnalysisWorker(folder, output, config, self.ai_mode.currentText(), config["title"])
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.analysis_started_at = time.monotonic()
        self.analysis_total_files = 0
        self.worker.progress_max.connect(self._on_progress_max)
        self.worker.progress.connect(self._on_progress)
        self.worker.status.connect(self.status_label.setText)
        self.worker.row.connect(self._add_result_row)
        self.worker.done.connect(self._analysis_done)
        self.worker.failed.connect(self._analysis_failed)
        self.worker.done.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _cancel_analysis(self):
        if self.worker:
            self.worker.cancel()
            self.status_label.setText("Cancelling...")

    def _analysis_done(self, message: str):
        self._stop_status_pulse()
        self.table.setSortingEnabled(True)
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.status_label.setText(message)
        if hasattr(self, "queue_status_label"):
            self.queue_status_label.setText("Queue: complete")
        if hasattr(self, "eta_status_label"):
            self.eta_status_label.setText("ETA: done")
        self._refresh_live_panels()
        self._refresh_history()

    def _analysis_failed(self, message: str):
        self._stop_status_pulse()
        self.table.setSortingEnabled(True)
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.status_label.setText("Failed")
        if hasattr(self, "queue_status_label"):
            self.queue_status_label.setText("Queue: failed")
        QMessageBox.critical(self, "Analysis failed", message)

    def _add_result_row(self, row: dict):
        self.rows.append(row)
        index = self.table.rowCount()
        self.table.insertRow(index)
        values = [
            Path(row.get("file", "")).name,
            str(row.get("score", 0)),
            decision_label(row.get("decision", "")),
            row.get("confidence", ""),
            "yes" if row.get("is_duplicate") else "no",
            ", ".join(row.get("matched_skills") or [])[:120],
            ", ".join(row.get("missing_skills") or [])[:120],
            row.get("sync_status", ""),
        ]
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col == 1:
                item.setData(Qt.UserRole, float(row.get("score") or 0))
            item.setData(Qt.UserRole + 1, len(self.rows) - 1)
            self.table.setItem(index, col, item)
        self._update_metrics()

    def _update_metrics(self):
        total = len(self.rows)
        accept = sum(1 for row in self.rows if row.get("decision") == "recommended_accept")
        review = sum(1 for row in self.rows if row.get("decision") == "recommended_review")
        reject = sum(1 for row in self.rows if row.get("decision") == "recommended_reject")
        avg_score = round(sum(float(row.get("score") or 0) for row in self.rows) / total, 1) if total else 0
        self.total_label.setText(f"Total: {total}")
        self.accept_label.setText(f"Accept: {accept}")
        self.review_label.setText(f"Review: {review}")
        self.reject_label.setText(f"Reject: {reject}")
        self.metric_candidates.setText(str(total))
        self.metric_avg_score.setText(f"{avg_score}%" if total else "--")
        self.metric_shortlisted.setText(str(accept))
        self.metric_hard_rejects.setText(str(reject))
        if hasattr(self, "dashboard_total"):
            self.dashboard_total.setText(f"{total} candidates")
        self._refresh_live_panels()

    def _refresh_live_panels(self):
        if hasattr(self, "report_preview"):
            if not self.rows:
                self.report_preview.setPlainText("No report yet. Run a local analysis to generate JSON and CSV outputs.")
                return
            top = sorted(self.rows, key=lambda row: float(row.get("score") or 0), reverse=True)[:5]
            lines = [
                f"Output folder: {self.output_folder.text().strip()}",
                f"Total candidates: {len(self.rows)}",
                "",
                "Top candidates:",
            ]
            for index, row in enumerate(top, 1):
                lines.append(
                    f"{index}. {Path(row.get('file', '')).name} - {row.get('score')} - {decision_label(row.get('decision', ''))}"
                )
            self.report_preview.setPlainText("\n".join(lines))

    def _show_selected_detail(self):
        items = self.table.selectedItems()
        if not items:
            return
        row_index = items[0].data(Qt.UserRole + 1)
        if row_index is None or row_index >= len(self.rows):
            return
        row = self.rows[row_index]
        self.detail.setPlainText(
            "\n".join(
                [
                    f"File: {row.get('file')}",
                    f"Score: {row.get('score')} | Decision: {decision_label(row.get('decision'))} | Confidence: {row.get('confidence')}",
                    f"Duplicate: {'yes' if row.get('is_duplicate') else 'no'}",
                    f"Matched: {', '.join(row.get('matched_skills') or [])}",
                    f"Missing: {', '.join(row.get('missing_skills') or [])}",
                    f"Risks: {', '.join(row.get('risk_flags') or [])}",
                    "",
                    row.get("explanation", ""),
                ]
            )
        )

    def _refresh_history(self):
        self.history_combo.clear()
        runs = self.store.list_runs(limit=100)
        for run in runs:
            self.history_combo.addItem(
                f"#{run['id']} - {run['job_name']} - {run['created_at']} ({run['total_files']} files)",
                run["id"],
            )
        self.history_text.setPlainText(f"{len(runs)} saved local run(s).")

    def _load_history_run(self):
        run_id = self.history_combo.currentData()
        if not run_id:
            return
        rows = self.store.get_run_results(run_id)
        self.rows = []
        self.table.setRowCount(0)
        for row in rows:
            self._add_result_row(row)
        self.tabs.setCurrentIndex(1)

    def _save_key(self):
        api_key = self.api_key.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Missing key", "Paste the worker key first.")
            return
        if save_worker_api_key(api_key):
            QMessageBox.information(self, "Saved", "Worker key saved to the OS credential store.")
        else:
            QMessageBox.warning(self, "Not saved", "The OS credential store rejected the key.")

    def _test_connection(self):
        api_key = self.api_key.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Missing key", "Paste the worker key first.")
            return
        old_base = worker_module.API_BASE_URL
        try:
            worker_module.API_BASE_URL = self.api_url.text().strip().rstrip("/") or API_BASE_URL
            worker = LocalWorker(api_key, "server_files", "none", os.environ.get("COMPUTERNAME", "Local Worker"))
            worker.login()
            jobs_resp = worker._request("GET", "/jobs")
            if jobs_resp.status_code != 200:
                raise RuntimeError(f"Connected, but job list failed: {jobs_resp.text}")
            jobs = jobs_resp.json().get("jobs", [])
            QMessageBox.information(self, "Connected", f"Connected. Allowed jobs: {jobs or 'none'}")
        except Exception as exc:
            QMessageBox.critical(self, "Connection failed", str(exc))
        finally:
            worker_module.API_BASE_URL = old_base

    def _open_output(self):
        path = Path(self.output_folder.text().strip() or ".")
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("CV Analyzer Local Worker")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        detail = traceback.format_exc()
        path = write_crash_log(detail)
        try:
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "CV Analyzer Local Worker", f"Startup failed.\n\nDetails were written to:\n{path}")
        except Exception:
            print(detail, file=sys.stderr)
        raise

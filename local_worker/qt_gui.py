import csv
import hashlib
import json
import os
import sys
import tempfile
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

        self._build()
        self._apply_style()
        self._refresh_history()
        if MOTION_ENABLED:
            self.setWindowOpacity(0.0)
            QTimer.singleShot(90, self._animate_startup)

    def _build(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(16)

        header = QHBoxLayout()
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
        outer.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_analyze_tab(), "Analyze")
        self.tabs.addTab(self._build_results_tab(), "Results")
        self.tabs.addTab(self._build_history_tab(), "History")
        self.tabs.addTab(self._build_server_tab(), "Website Sync")
        self.tabs.currentChanged.connect(self._animate_tab_change)
        outer.addWidget(self.tabs, 1)
        self.setCentralWidget(root)

        open_output = QAction("Open output folder", self)
        open_output.triggered.connect(self._open_output)
        self.addAction(open_output)

    def _build_analyze_tab(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        job_group = QGroupBox("Local job")
        form = QFormLayout(job_group)
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
        form.addRow("Job name", self.job_name)
        form.addRow("CV folder", self._path_row(self.cv_folder, self._choose_cv_folder))
        form.addRow("Output folder", self._path_row(self.output_folder, self._choose_output_folder))
        form.addRow("Accept threshold", self.accept_threshold)
        form.addRow("Review threshold", self.review_threshold)
        form.addRow("AI review", self.ai_mode)

        terms_group = QGroupBox("Scoring criteria")
        terms = QFormLayout(terms_group)
        self.required_skills = QLineEdit()
        self.nice_skills = QLineEdit()
        self.hard_reject = QLineEdit()
        terms.addRow("Required skills", self.required_skills)
        terms.addRow("Nice to have", self.nice_skills)
        terms.addRow("Hard reject criteria", self.hard_reject)

        self.description = QPlainTextEdit()
        self.description.setPlaceholderText("Paste the job description here. This stays local unless you explicitly sync later.")

        actions = QHBoxLayout()
        self.run_button = QPushButton("Analyze local folder")
        self.run_button.setObjectName("PrimaryButton")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.setEnabled(False)
        self.open_output_button = QPushButton("Open output")
        self.open_output_button.setObjectName("SecondaryButton")
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

        layout.addWidget(job_group, 0, 0)
        layout.addWidget(terms_group, 0, 1)
        layout.addWidget(QLabel("Job description"), 1, 0, 1, 2)
        layout.addWidget(self.description, 2, 0, 1, 2)
        layout.addLayout(actions, 3, 0, 1, 2)
        layout.addWidget(self.progress, 4, 0, 1, 2)
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

    def _path_row(self, field: QLineEdit, callback) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("Browse")
        button.setObjectName("SecondaryButton")
        button.clicked.connect(callback)
        layout.addWidget(field, 1)
        layout.addWidget(button)
        return row

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

    def _apply_style(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #101419;
                color: #eef1f4;
                font-family: "Segoe UI";
                font-size: 10pt;
            }
            QLabel#Title {
                color: #f7f8fa;
                font-size: 26px;
                font-weight: 800;
            }
            QLabel#Subtitle {
                color: #9aa6b2;
            }
            QLabel#StatusPill, QLabel#Metric {
                padding: 7px 12px;
                border: 1px solid #303943;
                border-radius: 9px;
                background: #171d24;
                color: #c8d0d8;
            }
            QTabWidget::pane {
                border: 1px solid #2b333d;
                border-radius: 10px;
                background: #151a20;
                top: -1px;
            }
            QTabBar::tab {
                padding: 10px 18px;
                margin-right: 4px;
                border: 1px solid #2b333d;
                border-bottom: none;
                border-top-left-radius: 9px;
                border-top-right-radius: 9px;
                background: #171d24;
                color: #a5adb6;
                font-weight: 650;
            }
            QTabBar::tab:selected {
                background: #202832;
                color: #ffffff;
                border-color: #56616f;
            }
            QTabBar::tab:hover {
                color: #eef1f4;
                background: #1d242c;
            }
            QGroupBox {
                border: 1px solid #2b333d;
                border-radius: 10px;
                margin-top: 14px;
                padding: 18px 14px 14px;
                background: #171d24;
                font-weight: 750;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #e1e7ed;
            }
            QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {
                background: #11161c;
                color: #eef1f4;
                border: 1px solid #333d49;
                border-radius: 7px;
                padding: 8px 10px;
                selection-background-color: #41546a;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
                border-color: #788391;
                background: #131922;
            }
            QPlainTextEdit, QTextEdit { line-height: 1.5; }
            QPushButton {
                background: #202832;
                color: #eef1f4;
                border: 1px solid #3a4654;
                border-radius: 8px;
                padding: 9px 14px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #28313d;
                border-color: #576575;
            }
            QPushButton:pressed {
                background: #1a212a;
            }
            QPushButton:disabled {
                color: #707a85;
                background: #171c22;
                border-color: #29313a;
            }
            QPushButton#PrimaryButton {
                background: #27415c;
                border-color: #4f6b86;
                color: #f7fafc;
            }
            QPushButton#PrimaryButton:hover {
                background: #31506f;
                border-color: #7089a3;
            }
            QPushButton#SecondaryButton {
                background: #1d242d;
                border-color: #37424e;
                color: #d8e0e8;
            }
            QProgressBar {
                border: 1px solid #333d49;
                border-radius: 7px;
                background: #11161c;
                text-align: center;
                color: #dbe2ea;
                height: 17px;
            }
            QProgressBar::chunk {
                border-radius: 7px;
                background: #5f7f72;
            }
            QTableWidget {
                background: #12171d;
                alternate-background-color: #171d24;
                border: 1px solid #2b333d;
                border-radius: 8px;
                gridline-color: #242c35;
                selection-background-color: #34465a;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background: #1e2630;
                color: #d8e0e8;
                border: none;
                border-right: 1px solid #2b333d;
                padding: 8px;
                font-weight: 800;
            }
            QScrollBar:vertical {
                background: #11161c;
                width: 12px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #3a4654;
                border-radius: 6px;
                min-height: 28px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4a5665;
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
            "required_skills": split_terms(self.required_skills.text()),
            "nice_to_have_skills": split_terms(self.nice_skills.text()),
            "hard_reject_criteria": split_terms(self.hard_reject.text()),
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
        self.worker.progress_max.connect(lambda value: self.progress.setRange(0, max(1, value)))
        self.worker.progress.connect(self._set_progress_value)
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
        self._refresh_history()

    def _analysis_failed(self, message: str):
        self._stop_status_pulse()
        self.table.setSortingEnabled(True)
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.status_label.setText("Failed")
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
        self.total_label.setText(f"Total: {total}")
        self.accept_label.setText(f"Accept: {accept}")
        self.review_label.setText(f"Review: {review}")
        self.reject_label.setText(f"Reject: {reject}")

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

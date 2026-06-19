import csv
import hashlib
import json
import queue
import sys
import threading
import os
import tempfile
import traceback
from datetime import UTC, datetime
from pathlib import Path


def _app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    path = Path(base) / "CV Analyzer Local Worker"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _crash_log_path() -> Path:
    return _app_data_dir() / "crash.log"


def _write_crash_log(message: str) -> Path:
    log_path = _crash_log_path()
    log_path.write_text(
        f"CV Analyzer Local Worker crash\n{datetime.now(UTC).isoformat().replace('+00:00', 'Z')}\n\n{message}\n",
        encoding="utf-8",
    )
    return log_path


def _show_fatal_error(message: str):
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "CV Analyzer Local Worker", 0x10)
    except Exception:
        print(message, file=sys.stderr)


try:
    from tkinter import BOTH, DISABLED, END, NORMAL, Button, Entry, Frame, Label, StringVar, Text, Tk, Toplevel, filedialog, messagebox, ttk
except ImportError:
    detail = traceback.format_exc()
    log_path = _write_crash_log(detail)
    _show_fatal_error(
        "The graphical app cannot start because Python was installed without Tkinter support.\n\n"
        "Install Python from python.org with the Tcl/Tk option enabled, then run start_here.cmd again.\n\n"
        f"Details were written to:\n{log_path}"
    )
    sys.exit(1)

import worker as worker_module
try:
    import windnd
except ImportError:
    windnd = None
from credentials import save_worker_api_key, load_worker_api_key
from worker import API_BASE_URL, MAX_FILE_BYTES, LocalWorker, extract_text, maybe_apply_ai_review, score_cv
from workspace import WorkspaceStore


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _resource_path(relative_path: str) -> Path:
    """Resolve bundled assets in source and PyInstaller one-file builds."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


THEMES = {
    "dark": {
        "bg": "#0b0f14",
        "panel": "#121820",
        "panel_2": "#19222d",
        "panel_3": "#202b38",
        "text": "#eef4f8",
        "muted": "#9aa8b4",
        "accent": "#58a6ff",
        "accent_2": "#2dd4bf",
        "warning": "#f2c14e",
        "danger": "#fb7185",
        "border": "#2b3645",
        "field": "#0e141b",
        "field_text": "#f7fbff",
    },
    "light": {
        "bg": "#f5f7fb",
        "panel": "#ffffff",
        "panel_2": "#eef3f8",
        "panel_3": "#e5edf6",
        "text": "#17202a",
        "muted": "#607080",
        "accent": "#2563eb",
        "accent_2": "#0f766e",
        "warning": "#9a6a00",
        "danger": "#be123c",
        "border": "#d7e0ea",
        "field": "#ffffff",
        "field_text": "#17202a",
    },
}


def _split_terms(value: str) -> list[str]:
    return [item.strip() for item in (value or "").replace("\n", ",").split(",") if item.strip()]


def _decision_label(decision: str) -> str:
    return {
        "recommended_accept": "Accept",
        "recommended_review": "Review",
        "recommended_reject": "Reject",
    }.get(decision, decision or "Unknown")


class LocalWorkerApp:
    def __init__(self):
        self.root = Tk()
        self.root.title("CV Analyzer Local Worker")
        self.root.geometry("1180x820")
        self.root.minsize(980, 680)
        icon_path = _resource_path("assets/cv_analyzer_worker.ico")
        if icon_path.exists():
            try:
                self.root.iconbitmap(default=str(icon_path))
            except Exception:
                pass

        self.store = WorkspaceStore()
        self.local_jobs: list[dict] = []
        self.local_runs: list[dict] = []
        self.theme_name = StringVar(value="dark")
        self.job_name_var = StringVar(value="New local job")
        self.saved_job_var = StringVar()
        self.saved_run_var = StringVar()
        self.folder_var = StringVar()
        self.output_var = StringVar(value=str(Path.cwd() / "local_results"))
        self.required_var = StringVar()
        self.nice_var = StringVar()
        self.hard_reject_var = StringVar()
        self.accept_var = StringVar(value="75")
        self.review_var = StringVar(value="50")
        self.ai_mode_var = StringVar(value="none")
        self.api_url_var = StringVar(value=os.environ.get("CV_ANALYZER_API_URL", API_BASE_URL))
        saved_key = load_worker_api_key() or os.environ.get("CV_WORKER_API_KEY", "")
        self.api_key_var = StringVar(value=saved_key)
        self.status_var = StringVar(value="Ready")
        self.server_status_var = StringVar(value="Server mode not connected")
        self.summary_var = StringVar(value="No run yet")
        self.work_queue: queue.Queue = queue.Queue()
        self.results: list[dict] = []
        self.result_by_iid: dict[str, dict] = {}
        self.failed_files: list[str] = []
        self.is_running = False

        self._build()
        self._apply_theme()
        self._refresh_jobs()
        self.root.after(150, self._drain_queue)

        if windnd:
            try:
                windnd.hook_dropfiles(self.root, self._on_drag_drop)
            except Exception as e:
                print(f"Failed to hook drag and drop: {e}")

    def _build(self):
        shell = Frame(self.root, padx=20, pady=18)
        shell.pack(fill=BOTH, expand=True)
        self.shell = shell

        header = Frame(shell, padx=4, pady=6)
        header.pack(fill="x", pady=(0, 14))
        self.header = header
        title_box = Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        self.title_box = title_box
        self.title_label = Label(title_box, text="CV Analyzer Local Worker", font=("Segoe UI", 23, "bold"))
        self.title_label.pack(anchor="w")
        self.subtitle_label = Label(
            title_box,
            text="Local, private CV ranking workspace with exportable results and optional website sync.",
            font=("Segoe UI", 10, "normal"),
        )
        self.subtitle_label.pack(anchor="w", pady=(2, 0))
        self.theme_button = Button(header, text="Light theme", command=self._toggle_theme)
        self.theme_button.pack(side="right")

        server_box = Frame(shell, padx=14, pady=12)
        server_box.pack(fill="x", pady=(0, 14))
        self.server_box = server_box
        self.server_title_label = Label(server_box, text="Optional website connection", font=("Segoe UI", 11, "bold"), anchor="w")
        self.server_title_label.pack(fill="x")
        server_url_row = Frame(server_box)
        server_url_row.pack(fill="x", pady=(6, 3))
        Label(server_url_row, text="API URL", width=18, anchor="w").pack(side="left")
        Entry(server_url_row, textvariable=self.api_url_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        Button(server_url_row, text="Test connection", command=self._test_server_connection).pack(side="left")
        server_key_row = Frame(server_box)
        server_key_row.pack(fill="x", pady=3)
        Label(server_key_row, text="Worker key", width=18, anchor="w").pack(side="left")
        Entry(server_key_row, textvariable=self.api_key_var, show="*").pack(side="left", fill="x", expand=True, padx=(0, 8))
        Button(server_key_row, text="Save key locally", command=self._save_server_key).pack(side="left")
        self.server_status_label = Label(server_box, textvariable=self.server_status_var, anchor="w")
        self.server_status_label.pack(fill="x", pady=(5, 0))

        job_row = Frame(shell, padx=4, pady=2)
        job_row.pack(fill="x", pady=4)
        Label(job_row, text="Local job name", width=18, anchor="w").pack(side="left")
        Entry(job_row, textvariable=self.job_name_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        Button(job_row, text="Save job", command=self._save_current_job).pack(side="left", padx=(0, 8))

        saved_row = Frame(shell, padx=4, pady=2)
        saved_row.pack(fill="x", pady=4)
        Label(saved_row, text="Saved jobs", width=18, anchor="w").pack(side="left")
        self.saved_jobs_combo = ttk.Combobox(saved_row, textvariable=self.saved_job_var, state="readonly")
        self.saved_jobs_combo.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.saved_jobs_combo.bind("<<ComboboxSelected>>", lambda _event: self._load_selected_job())
        Button(saved_row, text="Load", command=self._load_selected_job).pack(side="left")

        run_row = Frame(shell, padx=4, pady=2)
        run_row.pack(fill="x", pady=4)
        Label(run_row, text="Run history", width=18, anchor="w").pack(side="left")
        self.saved_runs_combo = ttk.Combobox(run_row, textvariable=self.saved_run_var, state="readonly")
        self.saved_runs_combo.pack(side="left", fill="x", expand=True, padx=(0, 8))
        Button(run_row, text="Open run", command=self._load_selected_run).pack(side="left", padx=(0, 8))
        Button(run_row, text="Compare Runs", command=self._compare_runs).pack(side="left")

        file_row = Frame(shell, padx=4, pady=2)
        file_row.pack(fill="x", pady=4)
        self.file_label = Label(file_row, text="CV folder", width=18, anchor="w")
        self.file_label.pack(side="left")
        Entry(file_row, textvariable=self.folder_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        Button(file_row, text="Choose folder", command=self._choose_folder).pack(side="left")

        output_row = Frame(shell, padx=4, pady=2)
        output_row.pack(fill="x", pady=4)
        self.output_label = Label(output_row, text="Output folder", width=18, anchor="w")
        self.output_label.pack(side="left")
        Entry(output_row, textvariable=self.output_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        Button(output_row, text="Choose output", command=self._choose_output).pack(side="left")

        self.jd_label = Label(shell, text="Job description", font=("Segoe UI", 11, "bold"))
        self.jd_label.pack(anchor="w", pady=(14, 4))
        self.jd_text = Text(shell, height=7, wrap="word", padx=10, pady=8, font=("Segoe UI", 10))
        self.jd_text.pack(fill="x")

        terms = Frame(shell, padx=4, pady=2)
        terms.pack(fill="x", pady=(12, 4))
        for label, var in (
            ("Required skills", self.required_var),
            ("Nice to have", self.nice_var),
            ("Hard reject criteria", self.hard_reject_var),
        ):
            box = Frame(terms)
            box.pack(side="left", fill="x", expand=True, padx=(0, 8))
            Label(box, text=label, anchor="w").pack(fill="x")
            Entry(box, textvariable=var).pack(fill="x")

        thresholds = Frame(shell, padx=4, pady=7)
        thresholds.pack(fill="x", pady=4)
        self.accept_label = Label(thresholds, text="Accept threshold")
        self.accept_label.pack(side="left")
        Entry(thresholds, textvariable=self.accept_var, width=8).pack(side="left", padx=(6, 18))
        self.review_label = Label(thresholds, text="Review threshold")
        self.review_label.pack(side="left")
        Entry(thresholds, textvariable=self.review_var, width=8).pack(side="left", padx=(6, 18))
        Label(thresholds, text="AI review").pack(side="left")
        self.ai_combo = ttk.Combobox(thresholds, textvariable=self.ai_mode_var, state="readonly", width=20)
        self.ai_combo["values"] = ["none", "customer_openai_key"]
        self.ai_combo.pack(side="left", padx=(6, 0))

        actions = Frame(shell, padx=4, pady=8)
        actions.pack(fill="x", pady=(12, 8))
        self.run_button = Button(actions, text="Analyze local folder", command=self._start_analysis)
        self.run_button.pack(side="left")
        self.retry_button = Button(actions, text="Retry failed files", command=self._retry_failed_files)
        self.retry_button.pack(side="left", padx=(8, 0))
        Button(actions, text="Open output folder", command=self._open_output).pack(side="left", padx=8)
        self.sync_button = Button(actions, text="Sync to Server", command=self._sync_to_server)
        self.sync_button.pack(side="left", padx=(0, 8))
        self.status_label = Label(actions, textvariable=self.status_var)
        self.status_label.pack(side="left", padx=12)

        self.progress = ttk.Progressbar(shell, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 6))
        self.summary_label = Label(shell, textvariable=self.summary_var, anchor="w")
        self.summary_label.pack(fill="x", pady=(0, 6))

        columns = ("file", "score", "decision", "confidence", "duplicate", "sync", "matched", "missing")
        self.table = ttk.Treeview(shell, columns=columns, show="headings", height=12)
        for col, width in (("file", 260), ("score", 70), ("decision", 110), ("confidence", 100), ("duplicate", 80), ("sync", 80), ("matched", 180), ("missing", 180)):
            self.table.heading(col, text=col.title())
            self.table.column(col, width=width, anchor="w")
        self.table.pack(fill=BOTH, expand=True, pady=(4, 8))
        self.table.bind("<<TreeviewSelect>>", self._show_selected_result)

        self.detail_label = Label(shell, text="Selected result detail", font=("Segoe UI", 10, "bold"))
        self.detail_label.pack(anchor="w")
        self.detail_text = Text(shell, height=6, wrap="word", state=DISABLED, padx=10, pady=8, font=("Segoe UI", 10))
        self.detail_text.pack(fill="x")

    def _all_frames(self):
        frames = [self.root]
        def collect(widget):
            for child in widget.winfo_children():
                if isinstance(child, Frame):
                    frames.append(child)
                    collect(child)
        collect(self.root)
        return frames

    def _all_labels(self):
        labels = [
            self.title_label,
            self.subtitle_label,
            self.file_label,
            self.output_label,
            self.jd_label,
            self.accept_label,
            self.review_label,
            self.status_label,
            self.server_status_label,
            self.summary_label,
            self.detail_label,
        ]
        def collect(widget):
            for child in widget.winfo_children():
                if isinstance(child, Label):
                    labels.append(child)
                collect(child)
        collect(self.root)
        return list(dict.fromkeys(labels))

    def _all_entries(self):
        entries = []
        def collect(widget):
            for child in widget.winfo_children():
                if isinstance(child, Entry) and not isinstance(child, ttk.Combobox):
                    entries.append(child)
                collect(child)
        collect(self.root)
        return entries

    def _all_buttons(self):
        buttons = []
        def collect(widget):
            for child in widget.winfo_children():
                if isinstance(child, Button):
                    buttons.append(child)
                collect(child)
        collect(self.root)
        return buttons

    def _all_text_widgets(self):
        texts = []
        def collect(widget):
            for child in widget.winfo_children():
                if isinstance(child, Text):
                    texts.append(child)
                collect(child)
        collect(self.root)
        return texts

    def _apply_theme(self):
        colors = THEMES[self.theme_name.get()]
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Treeview",
            background=colors["panel"],
            fieldbackground=colors["panel"],
            foreground=colors["text"],
            rowheight=30,
            bordercolor=colors["border"],
            borderwidth=0,
            font=("Segoe UI", 9),
        )
        style.configure("Treeview.Heading", background=colors["panel_3"], foreground=colors["text"], font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", colors["accent"])], foreground=[("selected", "#ffffff")])
        style.configure("TCombobox", fieldbackground=colors["field"], background=colors["panel_2"], foreground=colors["field_text"], arrowcolor=colors["text"], bordercolor=colors["border"], lightcolor=colors["border"], darkcolor=colors["border"], padding=(8, 5))
        style.map("TCombobox", fieldbackground=[("readonly", colors["field"])], foreground=[("readonly", colors["field_text"])])
        style.configure("Horizontal.TProgressbar", troughcolor=colors["panel_2"], background=colors["accent"], bordercolor=colors["border"], lightcolor=colors["accent"], darkcolor=colors["accent"])
        for frame in self._all_frames():
            frame.configure(bg=colors["bg"] if frame in {self.root, self.shell, self.header, self.title_box} else colors["panel"])
        self.server_box.configure(highlightbackground=colors["border"], highlightcolor=colors["border"], highlightthickness=1, bd=0)
        for label in self._all_labels():
            label.configure(bg=label.master.cget("bg"), fg=colors["text"])
        self.subtitle_label.configure(fg=colors["muted"])
        self.status_label.configure(fg=colors["accent"])
        self.server_status_label.configure(fg=colors["muted"])
        self.summary_label.configure(fg=colors["warning"])
        for entry in self._all_entries():
            entry.configure(
                bg=colors["field"],
                fg=colors["field_text"],
                insertbackground=colors["field_text"],
                relief="flat",
                highlightthickness=1,
                highlightbackground=colors["border"],
                highlightcolor=colors["accent"],
                font=("Segoe UI", 9),
            )
        for button in self._all_buttons():
            is_primary = button in {self.run_button, self.sync_button}
            button.configure(
                bg=colors["accent"] if is_primary else colors["panel_2"],
                fg="#ffffff" if is_primary else colors["text"],
                activebackground=colors["accent_2"] if is_primary else colors["panel_3"],
                activeforeground="#ffffff" if is_primary else colors["text"],
                relief="flat",
                bd=0,
                padx=12,
                pady=6,
                font=("Segoe UI", 9, "bold" if is_primary else "normal"),
                cursor="hand2",
            )
        for text_widget in self._all_text_widgets():
            text_widget.configure(
                bg=colors["field"],
                fg=colors["field_text"],
                insertbackground=colors["field_text"],
                relief="flat",
                highlightthickness=1,
                highlightbackground=colors["border"],
                highlightcolor=colors["accent"],
            )
        self.theme_button.configure(text="Light theme" if self.theme_name.get() == "dark" else "Dark theme")
        self.table.tag_configure("accept", foreground=colors["accent_2"])
        self.table.tag_configure("review", foreground=colors["warning"])
        self.table.tag_configure("reject", foreground=colors["danger"])
        self.table.tag_configure("duplicate", foreground=colors["muted"])

    def _toggle_theme(self):
        self.theme_name.set("light" if self.theme_name.get() == "dark" else "dark")
        self._apply_theme()

    def run(self):
        self.root.mainloop()

    def _choose_folder(self):
        folder = filedialog.askdirectory(title="Choose CV folder")
        if folder:
            self.folder_var.set(folder)

    def _on_drag_drop(self, files):
        if not files:
            return
        try:
            path_str = os.fsdecode(files[0])
            path = Path(path_str)
            if path.is_dir():
                self.folder_var.set(str(path))
                self.status_var.set(f"Dragged folder: {path.name}")
            else:
                self.folder_var.set(str(path.parent))
                self.status_var.set(f"Dragged file: {path.name} (Using parent folder)")
        except Exception as e:
            self.status_var.set(f"Drag drop error: {e}")

    def _save_server_key(self):
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror("Missing worker key", "Paste the worker key created in the website Settings page.")
            return
        saved = save_worker_api_key(api_key)
        if saved:
            self.api_key_var.set("")
            self.server_status_var.set("Worker key saved to the operating system credential store.")
        else:
            messagebox.showwarning("Key not saved", "The operating system credential store rejected the key. You can still use environment variables or paste it for testing.")

    def _test_server_connection(self):
        api_url = self.api_url_var.get().strip()
        api_key = self.api_key_var.get().strip()
        if not api_url:
            messagebox.showerror("Missing API URL", "Enter the website worker API URL.")
            return
        if not api_key:
            messagebox.showerror("Missing worker key", "Paste a worker key to test the connection.")
            return
        self.server_status_var.set("Testing website connection...")
        threading.Thread(target=self._test_server_connection_worker, args=(api_url, api_key), daemon=True).start()

    def _test_server_connection_worker(self, api_url: str, api_key: str):
        original_url = worker_module.API_BASE_URL
        try:
            worker_module.API_BASE_URL = api_url.rstrip("/")
            worker = LocalWorker(api_key, "server_files", "none", "desktop-gui")
            worker.login()
            self.work_queue.put((
                "server_status",
                f"Connected. Company={worker.company_id} | Quota remaining={worker.quota_remaining}",
            ))
        except Exception as exc:
            self.work_queue.put(("server_status", f"Connection failed: {exc}"))
        finally:
            worker_module.API_BASE_URL = original_url

    def _sync_to_server(self):
        api_url = self.api_url_var.get().strip()
        api_key = self.api_key_var.get().strip()
        if not api_url:
            messagebox.showerror("Missing API URL", "Enter the website worker API URL.")
            return
        if not api_key:
            messagebox.showerror("Missing worker key", "Please paste or save a worker key to sync.")
            return

        pending_results = self.store.list_pending_sync_results()
        if not pending_results:
            messagebox.showinfo("Sync complete", "All local analyses are already synced!")
            return

        self.status_var.set("Connecting to server to fetch jobs...")
        threading.Thread(target=self._run_sync_worker, args=(api_url, api_key, pending_results), daemon=True).start()

    def _run_sync_worker(self, api_url: str, api_key: str, pending_results: list):
        original_url = worker_module.API_BASE_URL
        try:
            worker_module.API_BASE_URL = api_url.rstrip("/")
            worker = LocalWorker(api_key, "server_files", "none", "desktop-gui")
            worker.login()

            resp = worker._request("GET", "/jobs")
            if resp.status_code != 200:
                raise Exception(f"Failed to fetch jobs: {resp.text}")

            server_jobs = resp.json().get("jobs", [])
            if not server_jobs:
                self.work_queue.put(("status", "No jobs found on server. Create a job description first."))
                return

            self.work_queue.put(("prompt_sync_job", (server_jobs, pending_results, worker)))
        except Exception as exc:
            self.work_queue.put(("status", f"Sync connection failed: {exc}"))
        finally:
            worker_module.API_BASE_URL = original_url

    def _sync_candidates_worker(self, job_id: int, pending_results: list, worker: LocalWorker):
        original_url = worker_module.API_BASE_URL
        try:
            worker_module.API_BASE_URL = self.api_url_var.get().strip().rstrip("/")

            results_payload = []
            for r in pending_results:
                results_payload.append({
                    "file_name": Path(r["file"]).name,
                    "file_type": Path(r["file"]).suffix.lstrip("."),
                    "file_hash": r.get("file_hash"),
                    "duplicate_of": Path(r["duplicate_of"]).name if r.get("duplicate_of") else None,
                    "score": float(r.get("score") or 0),
                    "decision": r.get("decision", "recommended_review"),
                    "confidence": r.get("confidence", "medium"),
                    "summary": r.get("summary", ""),
                    "matched_skills": r.get("matched_skills") or [],
                    "missing_skills": r.get("missing_skills") or [],
                    "risk_flags": r.get("risk_flags") or [],
                    "explanation": r.get("explanation", ""),
                    "candidate_name": Path(r["file"]).stem,
                    "candidate_email": None,
                    "worker_version": r.get("worker_version", "1.0.0"),
                    "engine_version": r.get("engine_version", "1.0.0"),
                })

            resp = worker._request("POST", "/worker/offline-sync", json={
                "job_id": job_id,
                "results": results_payload
            })

            if resp.status_code == 200:
                for r in pending_results:
                    self.store.update_result_sync_status(r["local_result_id"], "synced")
                self.work_queue.put(("status", "Sync successful! All candidates uploaded."))
                self.work_queue.put(("sync_success_dialog", len(pending_results)))
            else:
                error_msg = resp.text
                for r in pending_results:
                    self.store.update_result_sync_status(r["local_result_id"], "failed", error_msg)
                self.work_queue.put(("status", f"Sync failed: {resp.status_code} - {error_msg}"))
        except Exception as exc:
            self.work_queue.put(("status", f"Sync error: {exc}"))
        finally:
            worker_module.API_BASE_URL = original_url

    def _compare_runs(self):
        compare_win = Toplevel(self.root)
        compare_win.title("Compare Analysis Runs")
        compare_win.geometry("900x600")
        compare_win.transient(self.root)

        shell = Frame(compare_win, padx=14, pady=14)
        shell.pack(fill=BOTH, expand=True)

        Label(shell, text="Compare Analysis Runs", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))

        selector_frame = Frame(shell)
        selector_frame.pack(fill="x", pady=6)

        Label(selector_frame, text="Run A (Base):").pack(side="left")
        run_a_var = StringVar()
        run_a_combo = ttk.Combobox(selector_frame, textvariable=run_a_var, state="readonly", width=40)
        run_a_combo.pack(side="left", padx=(6, 18))

        Label(selector_frame, text="Run B (Compare):").pack(side="left")
        run_b_var = StringVar()
        run_b_combo = ttk.Combobox(selector_frame, textvariable=run_b_var, state="readonly", width=40)
        run_b_combo.pack(side="left", padx=6)

        run_values = [
            f"#{run['id']} | {run['job_name']} | {run['total_files']} files | {run['created_at']}"
            for run in self.local_runs
        ]
        run_a_combo["values"] = run_values
        run_b_combo["values"] = run_values

        if self.saved_run_var.get():
            run_a_var.set(self.saved_run_var.get())
            if len(run_values) > 1:
                if run_values[0] == self.saved_run_var.get():
                    run_b_var.set(run_values[1])
                else:
                    run_b_var.set(run_values[0])
            else:
                run_b_var.set(self.saved_run_var.get())
        else:
            if run_values:
                run_a_var.set(run_values[0])
                if len(run_values) > 1:
                    run_b_var.set(run_values[1])
                else:
                    run_b_var.set(run_values[0])

        columns = ("candidate", "score_a", "score_b", "diff", "decision_a", "decision_b")
        compare_table = ttk.Treeview(shell, columns=columns, show="headings", height=15)
        for col, width in (("candidate", 250), ("score_a", 100), ("score_b", 100), ("diff", 100), ("decision_a", 150), ("decision_b", 150)):
            compare_table.heading(col, text=col.replace("_", " ").title())
            compare_table.column(col, width=width, anchor="w")
        compare_table.pack(fill=BOTH, expand=True, pady=(10, 10))

        def do_compare(*args):
            compare_table.delete(*compare_table.get_children())
            val_a = run_a_var.get()
            val_b = run_b_var.get()
            if not val_a or not val_b:
                return

            try:
                run_id_a = int(val_a.split("|", 1)[0].strip().lstrip("#"))
                run_id_b = int(val_b.split("|", 1)[0].strip().lstrip("#"))
            except ValueError:
                return

            results_a = self.store.get_run_results(run_id_a)
            results_b = self.store.get_run_results(run_id_b)

            map_a = {Path(r["file"]).name: r for r in results_a}
            map_b = {Path(r["file"]).name: r for r in results_b}

            all_files = sorted(list(set(map_a.keys()) | set(map_b.keys())))

            for f in all_files:
                ra = map_a.get(f)
                rb = map_b.get(f)

                name = Path(f).stem

                score_a = ra["score"] if ra else "-"
                score_b = rb["score"] if rb else "-"
                dec_a = _decision_label(ra["decision"]) if ra else "-"
                dec_b = _decision_label(rb["decision"]) if rb else "-"

                if ra and rb:
                    diff_val = rb["score"] - ra["score"]
                    diff_str = f"{diff_val:+.1f}" if diff_val != 0 else "0.0"
                elif ra:
                    diff_str = "Missing"
                else:
                    diff_str = "New"

                compare_table.insert(
                    "",
                    END,
                    values=(name, score_a, score_b, diff_str, dec_a, dec_b)
                )

        run_a_combo.bind("<<ComboboxSelected>>", do_compare)
        run_b_combo.bind("<<ComboboxSelected>>", do_compare)
        do_compare()

    def _choose_output(self):
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder:
            self.output_var.set(folder)

    def _open_output(self):
        output = Path(self.output_var.get()).expanduser()
        output.mkdir(parents=True, exist_ok=True)
        try:
            import os
            os.startfile(str(output))
        except Exception as exc:
            messagebox.showerror("Could not open folder", str(exc))

    def _refresh_jobs(self):
        self.local_jobs = self.store.list_jobs()
        self.saved_jobs_combo["values"] = [job["name"] for job in self.local_jobs]
        self._refresh_runs()

    def _refresh_runs(self, job_id: int | None = None):
        self.local_runs = self.store.list_runs(job_id=job_id)
        self.saved_runs_combo["values"] = [
            f"#{run['id']} | {run['job_name']} | {run['total_files']} files | {run['created_at']}"
            for run in self.local_runs
        ]

    def _save_current_job(self):
        try:
            config = self._config()
            job_id = self.store.save_job(self.job_name_var.get(), config)
            self._refresh_jobs()
            self.saved_job_var.set(self.job_name_var.get().strip() or "Untitled local job")
            self.status_var.set(f"Saved local job #{job_id}.")
        except Exception as exc:
            messagebox.showerror("Could not save job", str(exc))

    def _load_selected_job(self):
        name = self.saved_job_var.get()
        job = next((item for item in self.local_jobs if item["name"] == name), None)
        if not job:
            return
        config = job["config"]
        self._refresh_runs(job["id"])
        self.job_name_var.set(job["name"])
        self.jd_text.delete("1.0", END)
        self.jd_text.insert("1.0", config.get("description", ""))
        self.required_var.set(", ".join(config.get("required_skills") or []))
        self.nice_var.set(", ".join(config.get("nice_to_have_skills") or []))
        self.hard_reject_var.set(", ".join(config.get("hard_reject_criteria") or []))
        self.accept_var.set(str(config.get("accept_threshold") or 75))
        self.review_var.set(str(config.get("review_threshold") or 50))
        self.ai_mode_var.set(config.get("ai_mode") or "none")
        self.status_var.set(f"Loaded {job['name']}.")

    def _load_selected_run(self):
        selected = self.saved_run_var.get()
        if not selected:
            return
        run_id_text = selected.split("|", 1)[0].strip().lstrip("#")
        try:
            run_id = int(run_id_text)
        except ValueError:
            return
        rows = self.store.get_run_results(run_id)
        self.results = []
        self.result_by_iid = {}
        self.failed_files = []
        self.table.delete(*self.table.get_children())
        for row in rows:
            self.work_queue.put(("row", row))
        self.progress.configure(value=len(rows), maximum=max(1, len(rows)))
        self.summary_var.set(f"Loaded historical run #{run_id} with {len(rows)} result(s).")
        self.status_var.set("Historical run loaded.")

    def _config(self) -> dict:
        try:
            accept = int(self.accept_var.get() or "75")
            review = int(self.review_var.get() or "50")
        except ValueError as exc:
            raise ValueError("Threshold values must be numbers.") from exc
        return {
            "title": self.job_name_var.get().strip() or "Local job",
            "description": self.jd_text.get("1.0", END).strip(),
            "required_skills": _split_terms(self.required_var.get()),
            "nice_to_have_skills": _split_terms(self.nice_var.get()),
            "hard_reject_criteria": _split_terms(self.hard_reject_var.get()),
            "accept_threshold": accept,
            "review_threshold": review,
            "reject_threshold": 30,
            "ai_mode": self.ai_mode_var.get(),
        }

    def _start_analysis(self):
        if self.is_running:
            return
        folder = Path(self.folder_var.get()).expanduser()
        if not folder.exists() or not folder.is_dir():
            messagebox.showerror("Missing folder", "Choose a valid CV folder.")
            return
        try:
            config = self._config()
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return
        if not config["description"] and not config["required_skills"]:
            messagebox.showerror("Missing job details", "Add a job description or required skills.")
            return

        output = Path(self.output_var.get()).expanduser()
        job_name = self.job_name_var.get().strip() or "Untitled local job"
        job_id = self.store.save_job(job_name, config)
        self._refresh_jobs()
        self.saved_job_var.set(job_name)
        self.results = []
        self.result_by_iid = {}
        self.table.delete(*self.table.get_children())
        self._set_detail("")
        self.progress.configure(value=0, maximum=1)
        self.summary_var.set("Starting analysis...")
        self.is_running = True
        self.run_button.configure(state=DISABLED)
        self.status_var.set("Analyzing...")
        threading.Thread(target=self._analyze_folder, args=(folder, output, config, job_id, job_name, None), daemon=True).start()

    def _retry_failed_files(self):
        if self.is_running or not self.failed_files:
            return
        try:
            config = self._config()
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return
        output = Path(self.output_var.get()).expanduser()
        job_name = self.job_name_var.get().strip() or "Untitled local job"
        job_id = self.store.save_job(job_name, config)
        retry_paths = [Path(path) for path in self.failed_files if Path(path).exists()]
        if not retry_paths:
            messagebox.showinfo("No failed files", "There are no existing failed files to retry.")
            return
        self.is_running = True
        self.run_button.configure(state=DISABLED)
        self.status_var.set("Retrying failed files...")
        self.failed_files = []
        threading.Thread(target=self._analyze_folder, args=(Path("."), output, config, job_id, job_name, retry_paths), daemon=True).start()

    def _analyze_folder(self, folder: Path, output: Path, config: dict, job_id: int | None, job_name: str, explicit_files: list[Path] | None):
        files = explicit_files or [path for path in folder.rglob("*") if path.suffix.lower() in SUPPORTED_EXTENSIONS and path.is_file()]
        run_id = self.store.create_run(job_id, job_name, str(folder), str(output), len(files))
        rows: list[dict] = []
        seen_hashes: dict[str, str] = {}
        counts = {"accept": 0, "review": 0, "reject": 0, "failed": 0, "duplicates": 0}
        self.work_queue.put(("progress_max", max(1, len(files))))
        self.work_queue.put(("status", f"Found {len(files)} CV file(s)."))
        for index, path in enumerate(files, start=1):
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    raise ValueError(f"File is larger than {MAX_FILE_BYTES} bytes.")
                data = path.read_bytes()
                file_hash = hashlib.sha256(data).hexdigest()
                duplicate_of = seen_hashes.get(file_hash)
                if duplicate_of:
                    counts["duplicates"] += 1
                else:
                    seen_hashes[file_hash] = str(path)
                text = extract_text(data, path.suffix.lstrip("."), path.name)
                result = maybe_apply_ai_review(text, config, score_cv(text, config), config.get("ai_mode") or "none")
                row = {
                    "file": str(path),
                    "file_hash": file_hash,
                    "duplicate_of": duplicate_of or "",
                    "is_duplicate": bool(duplicate_of),
                    "score": result["score"],
                    "decision": result["decision"],
                    "confidence": result["confidence"],
                    "summary": result["summary"],
                    "matched_skills": result["matched_skills"],
                    "missing_skills": result["missing_skills"],
                    "risk_flags": result["risk_flags"],
                    "explanation": result["explanation"],
                    "analyzed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                }
            except Exception as exc:
                counts["failed"] += 1
                self.failed_files.append(str(path))
                row = {
                    "file": str(path),
                    "file_hash": "",
                    "duplicate_of": "",
                    "is_duplicate": False,
                    "score": 0,
                    "decision": "recommended_reject",
                    "confidence": "low",
                    "summary": f"Could not process file: {exc}",
                    "matched_skills": [],
                    "missing_skills": [],
                    "risk_flags": ["extraction_failed"],
                    "explanation": str(exc),
                    "analyzed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                }
            rows.append(row)
            if row["decision"] == "recommended_accept":
                counts["accept"] += 1
            elif row["decision"] == "recommended_review":
                counts["review"] += 1
            else:
                counts["reject"] += 1
            self.store.add_result(run_id, row)
            self.work_queue.put(("row", row))
            self.work_queue.put(("summary", self._summary_text(index, len(files), counts)))
            self.work_queue.put(("progress", index))
            self.work_queue.put(("status", f"Analyzed {index}/{len(files)}"))

        output.mkdir(parents=True, exist_ok=True)
        json_path = output / "local_worker_results.json"
        csv_path = output / "local_worker_results.csv"
        html_path = output / "local_worker_results.html"
        failed_path = output / "failed_files.txt"
        sync_path = output / "sync_manifest.json"
        ranked_rows = sorted(rows, key=lambda item: float(item.get("score") or 0), reverse=True)
        for rank, row in enumerate(ranked_rows, start=1):
            row["rank"] = rank
        json_path.write_text(json.dumps(ranked_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            worker_module._generate_html_report(ranked_rows, config, html_path)
        except Exception:
            pass
        with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["rank", "file", "score", "decision", "confidence", "is_duplicate", "duplicate_of", "summary", "matched_skills", "missing_skills", "risk_flags", "explanation", "analyzed_at"],
                extrasaction="ignore"
            )
            writer.writeheader()
            for row in ranked_rows:
                writer.writerow({
                    **row,
                    "matched_skills": ", ".join(row.get("matched_skills") or []),
                    "missing_skills": ", ".join(row.get("missing_skills") or []),
                    "risk_flags": ", ".join(row.get("risk_flags") or []),
                })
        if self.failed_files:
            failed_path.write_text("\n".join(self.failed_files), encoding="utf-8")
        elif failed_path.exists():
            failed_path.unlink()
        sync_path.write_text(
            json.dumps(
                {
                    "schema": "cv_analyzer.local_worker.sync_manifest.v1",
                    "job": {
                        "id": job_id,
                        "name": job_name,
                        "config": config,
                    },
                    "run": {
                        "cv_folder": str(folder),
                        "output_folder": str(output),
                        "total_files": len(files),
                        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    },
                    "results_file": str(json_path),
                    "csv_file": str(csv_path),
                    "failed_files": list(self.failed_files),
                    "sync_status": "offline_ready",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.work_queue.put(("done", f"Done. Results saved to {output}"))
        self.work_queue.put(("runs_refresh", job_id))

    def _summary_text(self, processed: int, total: int, counts: dict) -> str:
        return (
            f"Processed {processed}/{total} | "
            f"Accept {counts['accept']} | Review {counts['review']} | Reject {counts['reject']} | "
            f"Failed {counts['failed']} | Duplicates {counts['duplicates']}"
        )

    def _set_detail(self, text: str):
        self.detail_text.configure(state=NORMAL)
        self.detail_text.delete("1.0", END)
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state=DISABLED)

    def _show_selected_result(self, _event=None):
        selection = self.table.selection()
        if not selection:
            return
        row = self.result_by_iid.get(selection[0])
        if not row:
            return
        detail = [
            f"File: {row.get('file')}",
            f"Score: {row.get('score')} | Decision: {_decision_label(row.get('decision'))} | Confidence: {row.get('confidence')}",
            f"Duplicate: {'yes' if row.get('is_duplicate') else 'no'}",
            f"Sync Status: {row.get('sync_status') or 'pending'}" + (f" (Error: {row['sync_error']})" if row.get("sync_error") else ""),
            f"Breakdown: {json.dumps(row.get('score_breakdown') or {}, ensure_ascii=False)}",
            f"AI review: {row.get('ai_review_status') or 'not_used'}",
            f"Matched: {', '.join(row.get('matched_skills') or [])}",
            f"Missing: {', '.join(row.get('missing_skills') or [])}",
            f"Risks: {', '.join(row.get('risk_flags') or [])}",
            "",
            row.get("explanation", ""),
        ]
        self._set_detail("\n".join(detail))

    def _drain_queue(self):
        try:
            while True:
                kind, payload = self.work_queue.get_nowait()
                if kind == "row":
                    self.results.append(payload)
                    iid = self.table.insert(
                        "",
                        END,
                        values=(
                            Path(payload["file"]).name,
                            payload["score"],
                            _decision_label(payload["decision"]),
                            payload["confidence"],
                            "yes" if payload.get("is_duplicate") else "no",
                            payload.get("sync_status", "pending"),
                            ", ".join(payload.get("matched_skills") or [])[:80],
                            ", ".join(payload.get("missing_skills") or [])[:80],
                        ),
                        tags=self._row_tags(payload),
                    )
                    self.result_by_iid[iid] = payload
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "server_status":
                    self.server_status_var.set(payload)
                elif kind == "summary":
                    self.summary_var.set(payload)
                elif kind == "progress_max":
                    self.progress.configure(maximum=payload, value=0)
                elif kind == "progress":
                    self.progress.configure(value=payload)
                elif kind == "runs_refresh":
                    self._refresh_runs(payload)
                elif kind == "prompt_sync_job":
                    server_jobs, pending_results, worker = payload
                    from tkinter import simpledialog
                    selected_job_id = simpledialog.askinteger("Sync to Server", f"Available Server Job IDs:\n{', '.join(str(j) for j in server_jobs)}\n\nEnter the Job ID to sync {len(pending_results)} candidates to:")
                    if not selected_job_id:
                        self.status_var.set("Sync cancelled.")
                        continue
                    if selected_job_id not in server_jobs:
                        messagebox.showerror("Invalid Job ID", f"Job ID {selected_job_id} is not associated with this worker key.")
                        self.status_var.set("Sync failed: invalid Job ID.")
                        continue
                    self.status_var.set(f"Syncing {len(pending_results)} candidates to job #{selected_job_id}...")
                    threading.Thread(target=self._sync_candidates_worker, args=(selected_job_id, pending_results, worker), daemon=True).start()
                elif kind == "sync_success_dialog":
                    messagebox.showinfo("Sync complete", f"Successfully synced {payload} candidates to the server!")
                    self._load_selected_run()
                elif kind == "done":
                    self.status_var.set(payload)
                    self.is_running = False
                    self.run_button.configure(state=NORMAL)
        except queue.Empty:
            pass
        self.root.after(150, self._drain_queue)

    def _row_tags(self, row: dict) -> tuple[str, ...]:
        tags = []
        if row.get("is_duplicate"):
            tags.append("duplicate")
        decision = row.get("decision")
        if decision == "recommended_accept":
            tags.append("accept")
        elif decision == "recommended_review":
            tags.append("review")
        elif decision == "recommended_reject":
            tags.append("reject")
        return tuple(tags)


if __name__ == "__main__":
    try:
        LocalWorkerApp().run()
    except Exception:
        detail = traceback.format_exc()
        log_path = _write_crash_log(detail)
        _show_fatal_error(
            "The Local Worker app hit a startup error and closed.\n\n"
            f"Details were written to:\n{log_path}\n\n"
            "Open that file and send the last lines if this keeps happening."
        )
        sys.exit(1)

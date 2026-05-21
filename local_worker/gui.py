import csv
import hashlib
import json
import queue
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

try:
    from tkinter import BOTH, DISABLED, END, NORMAL, Button, Entry, Frame, Label, StringVar, Text, Tk, filedialog, messagebox, ttk
except ImportError:
    print("\n[ERROR] The 'tkinter' package is required for the Graphical User Interface but is not installed or available on your system.")
    print("Please install tkinter (e.g., 'sudo apt-get install python3-tk' on Debian/Ubuntu, or ensure Python is installed with Tk support on your OS).")
    print("You can also run the CLI-based worker instead.\n")
    sys.exit(1)

from worker import MAX_FILE_BYTES, extract_text, maybe_apply_ai_review, score_cv
from workspace import WorkspaceStore


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}

THEMES = {
    "dark": {
        "bg": "#0d1110",
        "panel": "#121918",
        "panel_2": "#18211f",
        "text": "#e8efec",
        "muted": "#98a8a2",
        "accent": "#39c6a3",
        "accent_2": "#d7b85b",
        "border": "#263330",
        "field": "#0f1514",
    },
    "light": {
        "bg": "#f4f7f5",
        "panel": "#ffffff",
        "panel_2": "#eef4f1",
        "text": "#17211e",
        "muted": "#5d6b66",
        "accent": "#12846f",
        "accent_2": "#a37920",
        "border": "#d9e4df",
        "field": "#ffffff",
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
        self.root.geometry("1080x760")
        self.root.minsize(900, 620)

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
        self.status_var = StringVar(value="Ready")
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

    def _build(self):
        shell = Frame(self.root, padx=18, pady=18)
        shell.pack(fill=BOTH, expand=True)
        self.shell = shell

        header = Frame(shell)
        header.pack(fill="x", pady=(0, 14))
        self.header = header
        title_box = Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        self.title_box = title_box
        self.title_label = Label(title_box, text="CV Analyzer Local Worker", font=("Segoe UI", 20, "bold"))
        self.title_label.pack(anchor="w")
        self.subtitle_label = Label(
            title_box,
            text="Offline-first CV ranking workspace for local employer folders.",
            font=("Segoe UI", 10),
        )
        self.subtitle_label.pack(anchor="w", pady=(2, 0))
        self.theme_button = Button(header, text="Light theme", command=self._toggle_theme)
        self.theme_button.pack(side="right")

        job_row = Frame(shell)
        job_row.pack(fill="x", pady=4)
        Label(job_row, text="Local job name", width=18, anchor="w").pack(side="left")
        Entry(job_row, textvariable=self.job_name_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        Button(job_row, text="Save job", command=self._save_current_job).pack(side="left", padx=(0, 8))

        saved_row = Frame(shell)
        saved_row.pack(fill="x", pady=4)
        Label(saved_row, text="Saved jobs", width=18, anchor="w").pack(side="left")
        self.saved_jobs_combo = ttk.Combobox(saved_row, textvariable=self.saved_job_var, state="readonly")
        self.saved_jobs_combo.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.saved_jobs_combo.bind("<<ComboboxSelected>>", lambda _event: self._load_selected_job())
        Button(saved_row, text="Load", command=self._load_selected_job).pack(side="left")

        run_row = Frame(shell)
        run_row.pack(fill="x", pady=4)
        Label(run_row, text="Run history", width=18, anchor="w").pack(side="left")
        self.saved_runs_combo = ttk.Combobox(run_row, textvariable=self.saved_run_var, state="readonly")
        self.saved_runs_combo.pack(side="left", fill="x", expand=True, padx=(0, 8))
        Button(run_row, text="Open run", command=self._load_selected_run).pack(side="left")

        file_row = Frame(shell)
        file_row.pack(fill="x", pady=4)
        self.file_label = Label(file_row, text="CV folder", width=18, anchor="w")
        self.file_label.pack(side="left")
        Entry(file_row, textvariable=self.folder_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        Button(file_row, text="Choose folder", command=self._choose_folder).pack(side="left")

        output_row = Frame(shell)
        output_row.pack(fill="x", pady=4)
        self.output_label = Label(output_row, text="Output folder", width=18, anchor="w")
        self.output_label.pack(side="left")
        Entry(output_row, textvariable=self.output_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        Button(output_row, text="Choose output", command=self._choose_output).pack(side="left")

        self.jd_label = Label(shell, text="Job description", font=("Segoe UI", 10, "bold"))
        self.jd_label.pack(anchor="w", pady=(14, 4))
        self.jd_text = Text(shell, height=7, wrap="word")
        self.jd_text.pack(fill="x")

        terms = Frame(shell)
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

        thresholds = Frame(shell)
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

        actions = Frame(shell)
        actions.pack(fill="x", pady=(12, 8))
        self.run_button = Button(actions, text="Analyze local folder", command=self._start_analysis)
        self.run_button.pack(side="left")
        self.retry_button = Button(actions, text="Retry failed files", command=self._retry_failed_files)
        self.retry_button.pack(side="left", padx=(8, 0))
        Button(actions, text="Open output folder", command=self._open_output).pack(side="left", padx=8)
        self.status_label = Label(actions, textvariable=self.status_var)
        self.status_label.pack(side="left", padx=12)

        self.progress = ttk.Progressbar(shell, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 6))
        self.summary_label = Label(shell, textvariable=self.summary_var, anchor="w")
        self.summary_label.pack(fill="x", pady=(0, 6))

        columns = ("file", "score", "decision", "confidence", "duplicate", "matched", "missing")
        self.table = ttk.Treeview(shell, columns=columns, show="headings", height=12)
        for col, width in (("file", 260), ("score", 70), ("decision", 110), ("confidence", 100), ("duplicate", 90), ("matched", 180), ("missing", 180)):
            self.table.heading(col, text=col.title())
            self.table.column(col, width=width, anchor="w")
        self.table.pack(fill=BOTH, expand=True, pady=(4, 8))
        self.table.bind("<<TreeviewSelect>>", self._show_selected_result)

        self.detail_label = Label(shell, text="Selected result detail", font=("Segoe UI", 10, "bold"))
        self.detail_label.pack(anchor="w")
        self.detail_text = Text(shell, height=6, wrap="word", state=DISABLED)
        self.detail_text.pack(fill="x")

    def _all_frames(self):
        frames = [self.root, self.shell, self.header, self.title_box]
        for child in self.shell.winfo_children():
            if isinstance(child, Frame):
                frames.append(child)
                frames.extend([nested for nested in child.winfo_children() if isinstance(nested, Frame)])
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
            self.summary_label,
            self.detail_label,
        ]
        for child in self.shell.winfo_children():
            if isinstance(child, Frame):
                labels.extend([nested for nested in child.winfo_children() if isinstance(nested, Label)])
        return list(dict.fromkeys(labels))

    def _apply_theme(self):
        colors = THEMES[self.theme_name.get()]
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", background=colors["panel"], fieldbackground=colors["panel"], foreground=colors["text"], rowheight=28, bordercolor=colors["border"])
        style.configure("Treeview.Heading", background=colors["panel_2"], foreground=colors["text"], font=("Segoe UI", 9, "bold"))
        style.configure("TCombobox", fieldbackground=colors["field"], background=colors["panel"], foreground=colors["text"])
        style.configure("Horizontal.TProgressbar", troughcolor=colors["panel_2"], background=colors["accent"])
        for frame in self._all_frames():
            frame.configure(bg=colors["bg"] if frame in {self.root, self.shell} else colors["panel"])
        for label in self._all_labels():
            label.configure(bg=label.master.cget("bg"), fg=colors["text"])
        self.subtitle_label.configure(fg=colors["muted"])
        self.status_label.configure(fg=colors["accent"])
        self.summary_label.configure(fg=colors["accent_2"])
        self.jd_text.configure(bg=colors["field"], fg=colors["text"], insertbackground=colors["text"], relief="flat", highlightthickness=1, highlightbackground=colors["border"])
        self.detail_text.configure(bg=colors["field"], fg=colors["text"], insertbackground=colors["text"], relief="flat", highlightthickness=1, highlightbackground=colors["border"])
        self.theme_button.configure(text="Light theme" if self.theme_name.get() == "dark" else "Dark theme")

    def _toggle_theme(self):
        self.theme_name.set("light" if self.theme_name.get() == "dark" else "dark")
        self._apply_theme()

    def run(self):
        self.root.mainloop()

    def _choose_folder(self):
        folder = filedialog.askdirectory(title="Choose CV folder")
        if folder:
            self.folder_var.set(folder)

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
        failed_path = output / "failed_files.txt"
        sync_path = output / "sync_manifest.json"
        ranked_rows = sorted(rows, key=lambda item: float(item.get("score") or 0), reverse=True)
        for rank, row in enumerate(ranked_rows, start=1):
            row["rank"] = rank
        json_path.write_text(json.dumps(ranked_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=["rank", "file", "score", "decision", "confidence", "is_duplicate", "duplicate_of", "summary", "matched_skills", "missing_skills", "risk_flags", "explanation", "analyzed_at"])
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
                            ", ".join(payload.get("matched_skills") or [])[:80],
                            ", ".join(payload.get("missing_skills") or [])[:80],
                        ),
                    )
                    self.result_by_iid[iid] = payload
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "summary":
                    self.summary_var.set(payload)
                elif kind == "progress_max":
                    self.progress.configure(maximum=payload, value=0)
                elif kind == "progress":
                    self.progress.configure(value=payload)
                elif kind == "runs_refresh":
                    self._refresh_runs(payload)
                elif kind == "done":
                    self.status_var.set(payload)
                    self.is_running = False
                    self.run_button.configure(state=NORMAL)
        except queue.Empty:
            pass
        self.root.after(150, self._drain_queue)


if __name__ == "__main__":
    LocalWorkerApp().run()

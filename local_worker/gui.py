import csv
import hashlib
import json
import queue
import threading
from datetime import UTC, datetime
from pathlib import Path
from tkinter import BOTH, DISABLED, END, NORMAL, Button, Entry, Frame, Label, StringVar, Text, Tk, filedialog, messagebox, ttk

from worker import extract_text, score_cv
from workspace import WorkspaceStore


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


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
        self.job_name_var = StringVar(value="New local job")
        self.saved_job_var = StringVar()
        self.folder_var = StringVar()
        self.output_var = StringVar(value=str(Path.cwd() / "local_results"))
        self.required_var = StringVar()
        self.nice_var = StringVar()
        self.hard_reject_var = StringVar()
        self.accept_var = StringVar(value="75")
        self.review_var = StringVar(value="50")
        self.status_var = StringVar(value="Ready")
        self.summary_var = StringVar(value="No run yet")
        self.work_queue: queue.Queue = queue.Queue()
        self.results: list[dict] = []
        self.result_by_iid: dict[str, dict] = {}
        self.is_running = False

        self._build()
        self._refresh_jobs()
        self.root.after(150, self._drain_queue)

    def _build(self):
        shell = Frame(self.root, padx=18, pady=18)
        shell.pack(fill=BOTH, expand=True)

        Label(shell, text="CV Analyzer Local Worker", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        Label(
            shell,
            text="Analyze a local CV folder without creating site-side jobs. Results stay on this device unless you export them.",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 14))

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

        file_row = Frame(shell)
        file_row.pack(fill="x", pady=4)
        Label(file_row, text="CV folder", width=18, anchor="w").pack(side="left")
        Entry(file_row, textvariable=self.folder_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        Button(file_row, text="Choose folder", command=self._choose_folder).pack(side="left")

        output_row = Frame(shell)
        output_row.pack(fill="x", pady=4)
        Label(output_row, text="Output folder", width=18, anchor="w").pack(side="left")
        Entry(output_row, textvariable=self.output_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        Button(output_row, text="Choose output", command=self._choose_output).pack(side="left")

        Label(shell, text="Job description", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(14, 4))
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
        Label(thresholds, text="Accept threshold").pack(side="left")
        Entry(thresholds, textvariable=self.accept_var, width=8).pack(side="left", padx=(6, 18))
        Label(thresholds, text="Review threshold").pack(side="left")
        Entry(thresholds, textvariable=self.review_var, width=8).pack(side="left", padx=(6, 18))

        actions = Frame(shell)
        actions.pack(fill="x", pady=(12, 8))
        self.run_button = Button(actions, text="Analyze local folder", command=self._start_analysis)
        self.run_button.pack(side="left")
        Button(actions, text="Open output folder", command=self._open_output).pack(side="left", padx=8)
        Label(actions, textvariable=self.status_var).pack(side="left", padx=12)

        self.progress = ttk.Progressbar(shell, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 6))
        Label(shell, textvariable=self.summary_var, anchor="w").pack(fill="x", pady=(0, 6))

        columns = ("file", "score", "decision", "confidence", "duplicate", "matched", "missing")
        self.table = ttk.Treeview(shell, columns=columns, show="headings", height=12)
        for col, width in (("file", 260), ("score", 70), ("decision", 110), ("confidence", 100), ("duplicate", 90), ("matched", 180), ("missing", 180)):
            self.table.heading(col, text=col.title())
            self.table.column(col, width=width, anchor="w")
        self.table.pack(fill=BOTH, expand=True, pady=(4, 8))
        self.table.bind("<<TreeviewSelect>>", self._show_selected_result)

        Label(shell, text="Selected result detail", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.detail_text = Text(shell, height=6, wrap="word", state=DISABLED)
        self.detail_text.pack(fill="x")

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
        self.job_name_var.set(job["name"])
        self.jd_text.delete("1.0", END)
        self.jd_text.insert("1.0", config.get("description", ""))
        self.required_var.set(", ".join(config.get("required_skills") or []))
        self.nice_var.set(", ".join(config.get("nice_to_have_skills") or []))
        self.hard_reject_var.set(", ".join(config.get("hard_reject_criteria") or []))
        self.accept_var.set(str(config.get("accept_threshold") or 75))
        self.review_var.set(str(config.get("review_threshold") or 50))
        self.status_var.set(f"Loaded {job['name']}.")

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
        threading.Thread(target=self._analyze_folder, args=(folder, output, config, job_id, job_name), daemon=True).start()

    def _analyze_folder(self, folder: Path, output: Path, config: dict, job_id: int | None, job_name: str):
        files = [path for path in folder.rglob("*") if path.suffix.lower() in SUPPORTED_EXTENSIONS and path.is_file()]
        run_id = self.store.create_run(job_id, job_name, str(folder), str(output), len(files))
        rows: list[dict] = []
        seen_hashes: dict[str, str] = {}
        counts = {"accept": 0, "review": 0, "reject": 0, "failed": 0, "duplicates": 0}
        self.work_queue.put(("progress_max", max(1, len(files))))
        self.work_queue.put(("status", f"Found {len(files)} CV file(s)."))
        for index, path in enumerate(files, start=1):
            try:
                data = path.read_bytes()
                file_hash = hashlib.sha256(data).hexdigest()
                duplicate_of = seen_hashes.get(file_hash)
                if duplicate_of:
                    counts["duplicates"] += 1
                else:
                    seen_hashes[file_hash] = str(path)
                text = extract_text(data, path.suffix.lstrip("."), path.name)
                result = score_cv(text, config)
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
        self.work_queue.put(("done", f"Done. Results saved to {output}"))

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
                elif kind == "done":
                    self.status_var.set(payload)
                    self.is_running = False
                    self.run_button.configure(state=NORMAL)
        except queue.Empty:
            pass
        self.root.after(150, self._drain_queue)


if __name__ == "__main__":
    LocalWorkerApp().run()

from __future__ import annotations

import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from renderers.template_engine import fill_template, load_template_file
from schemas.cv_model import CVModel


def render_typst(
    cv_model: CVModel, template: str = "classic", compile_pdf: bool = False, font_override: str = ""
) -> tuple[BytesIO, dict]:
    template_file = load_template_file(template, "template.typ")
    typst_code = fill_template(template_file, cv_model, template, font_override=font_override)

    metadata: dict = {"compiled": False, "compiler": "typst", "template": template}

    if compile_pdf:
        typst_bin = shutil.which("typst")
        if typst_bin:
            with tempfile.TemporaryDirectory(prefix="cv_typst_") as tmp:
                tmp_path = Path(tmp)
                in_file = tmp_path / "cv.typ"
                out_file = tmp_path / "cv.pdf"
                in_file.write_text(typst_code, encoding="utf-8")
                proc = subprocess.run(
                    [typst_bin, "compile", str(in_file), str(out_file)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                metadata["returncode"] = proc.returncode
                metadata["compiled"] = proc.returncode == 0 and out_file.exists()
                metadata["stderr"] = proc.stderr[-2000:] if proc.stderr else ""
                if metadata["compiled"]:
                    pdf_buf = BytesIO(out_file.read_bytes())
                    pdf_buf.seek(0)
                    return pdf_buf, metadata
                else:
                    metadata["stdout"] = proc.stdout[-1000:] if proc.stdout else ""
        else:
            metadata["error"] = "typst binary not found in PATH"

    out = BytesIO(typst_code.encode("utf-8"))
    out.seek(0)
    return out, metadata

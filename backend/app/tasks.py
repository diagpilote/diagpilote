# coding: utf-8
import os
import time
from datetime import datetime

BASE_DIR = os.getenv("TASKS_OUTPUT_DIR", "/app/tmp/tasks")

def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def generate_pdf(*, source: str = "api", n: int = 1) -> dict:
    """Placeholder PDF: écrit un .txt pour la démo."""
    _ensure_dir(BASE_DIR)
    ts = int(time.time())
    filename = f"pdf_{ts}_{n}.txt"
    out_path = os.path.join(BASE_DIR, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"[{datetime.utcnow().isoformat()}Z] fake-PDF from={source} n={n}\n")
    return {
        "status": "ok",
        "action": "generate_pdf",
        "source": source,
        "n": n,
        "output": out_path,
        "ts": ts,
    }

def ocr_process(*, source: str = "api", file: str | None = None) -> dict:
    """Placeholder OCR: écrit un .txt pour la démo."""
    _ensure_dir(BASE_DIR)
    ts = int(time.time())
    out_path = os.path.join(BASE_DIR, f"ocr_{ts}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"[{datetime.utcnow().isoformat()}Z] fake-OCR source={source} file={file}\n")
    return {
        "status": "ok",
        "action": "ocr_process",
        "source": source,
        "file": file,
        "output": out_path,
        "ts": ts,
    }

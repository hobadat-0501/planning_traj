"""Chạy toàn bộ tái lập Mục 4.1 (SPEC §10, TASKS T27).

Chạy: python -m num41.run_all --seed 2026  (từ thư mục ws)
Thứ tự: N0 (hình mẫu) → N1 → N2 → N3 (kèm độ nhạy) → báo cáo → pytest tests/test_num41.py.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from num41.gen import SEED
from num41.logio import LOG_DIR, ROOT

# Tiến trình con in tiếng Việt; trên Windows stdout chuyển hướng mặc định là cp1252.
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}

STEPS = [
    ["num41.plot_samples"],
    ["num41.run_n1"],
    ["num41.run_n2"],
    ["num41.run_n3", "--sensitivity"],
]


def run(mod_args: list[str]) -> None:
    cmd = [sys.executable, "-m", *mod_args]
    print("\n>>>", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, env=ENV, check=True)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--no-docx", action="store_true")
    ap.add_argument("--no-tests", action="store_true")
    args = ap.parse_args()

    for step in STEPS:
        extra = [] if step[0] == "num41.plot_samples" else ["--seed", str(args.seed)]
        run(step + extra)
    run(["num41.report_41"] + ([] if args.no_docx else ["--docx"]))

    if not args.no_tests:
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_num41.py"]
        print("\n>>>", " ".join(cmd), flush=True)
        res = subprocess.run(cmd, cwd=ROOT, env=ENV, capture_output=True, text=True, encoding="utf-8")
        (LOG_DIR / "tests.txt").write_text(res.stdout + res.stderr, encoding="utf-8")
        print(res.stdout[-500:])
        if res.returncode:
            sys.exit(res.returncode)


if __name__ == "__main__":
    main()

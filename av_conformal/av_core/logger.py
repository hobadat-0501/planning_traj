"""Ghi log một lượt: cycles (mỗi dòng một cặp (τ, tác nhân)), steps (20 Hz), meta (hướng dẫn §7.2).

Dùng CSV (parquet nếu có pyarrow và chọn fmt='parquet')."""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

import pandas as pd


def cfg_hash(cfg) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:16]


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=5).stdout.strip() or "none"
    except Exception:
        return "none"


class EpisodeLogger:
    def __init__(self, out_dir, run_id, meta, fmt="csv"):
        self.dir = Path(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.run_id, self.fmt = run_id, fmt
        self.meta = dict(run_id=run_id, **meta, git_commit=git_commit(), t_start=time.time(), status="running")
        self.cycles: list[dict] = []
        self.cycle_summary: list[dict] = []
        self.steps: list[dict] = []

    def write(self, res):
        for r in res["rows"]:
            self.cycles.append(dict(run_id=self.run_id, **r))
        self.cycle_summary.append(dict(run_id=self.run_id, t=res["t"], R=res["R"], **res["meta"]))

    def step(self, **kw):
        self.steps.append(kw)

    def _save(self, df, name):
        p = self.dir / f"{self.run_id}_{name}.{'parquet' if self.fmt == 'parquet' else 'csv'}"
        (df.to_parquet(p) if self.fmt == "parquet" else df.to_csv(p, index=False))

    def close(self, status="goal", **extra):
        self.meta.update(status=status, t_end=time.time(), n_cycles=len(self.cycle_summary), **extra)
        self._save(pd.DataFrame(self.cycles), "cycles")
        self._save(pd.DataFrame(self.cycle_summary), "cyclesummary")
        self._save(pd.DataFrame(self.steps), "steps")
        tmp = self.dir / f"{self.run_id}_meta.json.tmp"
        tmp.write_text(json.dumps(self.meta, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.dir / f"{self.run_id}_meta.json")   # meta ghi cuối cùng = lượt đã xong

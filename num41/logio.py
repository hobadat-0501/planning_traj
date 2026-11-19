"""Ghi log chung cho các thí nghiệm Mục 4.1 (SPEC §10.7)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs" / "num41"
FIG_DIR = ROOT / "figs"


def update_json(name: str, key: str, value) -> Path:
    """Gộp value vào mục key của logs/num41/<name> (giữ các mục của thí nghiệm khác)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / name
    data = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    data[key] = value
    text = json.dumps(data, ensure_ascii=False, indent=2, default=_np_default)  # tuần tự hóa trước, rồi mới ghi
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return path


def _np_default(o):
    """Đổi kiểu numpy sang kiểu Python cho json."""
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"Không tuần tự hóa được {type(o).__name__}")


def stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def save_fig(fig, stem: str) -> Path:
    FIG_DIR.mkdir(exist_ok=True)
    # Bỏ dấu thời gian trong siêu dữ liệu để chạy lại cho file giống hệt.
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=150, metadata={"Software": None})
    fig.savefig(FIG_DIR / f"{stem}.pdf", metadata={"CreationDate": None, "ModDate": None})
    return FIG_DIR / f"{stem}.png"

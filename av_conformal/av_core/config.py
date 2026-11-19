"""Nạp cấu hình từ configs/*.yaml thành một dict."""
from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


def load_cfg(config_dir: Path | str | None = None) -> dict:
    d = Path(config_dir) if config_dir else CONFIG_DIR
    def _l(name):
        with open(d / name, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return dict(
        vehicle=_l("tesla_model3.yaml"),
        noise=_l("noise.yaml"),
        conditions=_l("conditions.yaml"),
        scenarios=_l("scenarios.yaml"),
        experiments=_l("experiments.yaml"),
        run=_l("run.yaml"),
    )

"""Chạy hàng loạt S × D × phương pháp × hạt giống (hướng dẫn §7.3).

- Bỏ qua lượt đã có *_meta.json hoàn thành (chạy lại được sau khi bị ngắt).
- Mỗi lượt bắt lỗi riêng: lượt lỗi ghi status='error', không làm dừng cả mẻ.
- --shard i/n chia đều tổ hợp cho nhiều máy/tiến trình (chia theo chỉ số tổ hợp, tất định)."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from ..av_core.config import load_cfg
from .sim_runner import run_episode


def combos(scenarios, conditions, methods, seeds):
    return [dict(scenario=s, condition=d, method=m, seed=k)
            for s, d, m, k in itertools.product(scenarios, conditions, methods, seeds)]


def shard(items, i, n):
    return [c for j, c in enumerate(items) if j % n == i]


def meta_path(out_dir, exp, c):
    return Path(out_dir) / f"{exp}_{c['scenario']}_{c['condition']}_{c['method']}_{c['seed']}_meta.json"


def is_done(out_dir, exp, c):
    p = meta_path(out_dir, exp, c)
    if not p.exists():
        return False
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("status") in ("goal", "collision", "timeout")
    except Exception:
        return False


def run_batch(cfg, exp, out_dir, scenarios, conditions, methods, seeds, backend="fake", shard_spec=(0, 1),
              q_table=None, sigma_tau=None, backend_args=None, T_max=None, log_steps=True, verbose=True):
    items = shard(combos(scenarios, conditions, methods, seeds), *shard_spec)
    n_run = n_skip = n_err = 0
    for c in items:
        if is_done(out_dir, exp, c):
            n_skip += 1
            continue
        m = run_episode(cfg, c["seed"], c["method"], c["scenario"], c["condition"], out_dir, backend=backend,
                        q_table=q_table, sigma_tau=sigma_tau, exp=exp, backend_args=backend_args, T_max=T_max,
                        log_steps=log_steps)
        n_run += 1
        n_err += int(m["status"] == "error")
        if verbose:
            print(f"[{n_run + n_skip}/{len(items)}] {m['run_id']}: {m['status']}", flush=True)
    return dict(total=len(items), run=n_run, skipped=n_skip, errors=n_err)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", default="smoke", help="khóa trong configs/experiments.yaml")
    ap.add_argument("--out", default=None)
    ap.add_argument("--backend", default="fake", choices=["fake", "carla"])
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--seeds", default=None, help="ghi đè dải hạt giống trong experiments.yaml, dạng LO-HI (gồm cả hai đầu)")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--tm-port", type=int, default=8000)
    a = ap.parse_args()
    cfg = load_cfg()
    e = cfg["experiments"][a.exp]
    i, n = (int(x) for x in a.shard.split("/"))
    out = a.out or f"av_conformal/data/raw/{a.exp}"
    lo, hi = (int(x) for x in a.seeds.split("-")) if a.seeds else (e["seeds"][0], e["seeds"][1])
    r = run_batch(cfg, a.exp, out, e["scenarios"], e["conditions"], e["methods"], range(lo, hi + 1),
                  backend=a.backend, shard_spec=(i, n),
                  backend_args=dict(host=a.host, port=a.port, tm_port=a.tm_port))
    print(json.dumps(r))


if __name__ == "__main__":
    main()

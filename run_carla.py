"""Giao diện dòng lệnh chạy quy trình chuyển mô phỏng Phương án B sang CARLA (G13–G19).

Ví dụ:
    python run_carla.py env
    python run_carla.py latency --host 127.0.0.1 --port 2000
    python run_carla.py smoke --backend carla --out logs/carla_smoke
    python run_carla.py bench --backend carla
    python run_carla.py params --out logs/carla_params
    python run_carla.py run --level M1 --backend carla --out logs/carla_m1
    python run_carla.py report
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from carla_sim.config import CarlaConfig
from carla_sim.infra import CarlaSession, check_carla_env, measure_actuator_latency
from carla_sim.params import build_carla_param_spec, export_param_spec
from carla_sim.report_carla import generate_carla_report
from carla_sim.runner import benchmark_s_x_d, run_carla_suite, run_smoke_s1_d0
from sim.core import CONDITIONS, SCENARIOS


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Chạy mô phỏng Phương án B trên CARLA (PLAN §9, T15–T21).")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_env = sub.add_parser("env", help="Kiểm tra môi trường Python, gói carla và GPU (T15).")
    p_env.add_argument("--connect", action="store_true", help="Kết nối server để so phiên bản client/server.")
    p_env.add_argument("--host", default="127.0.0.1")
    p_env.add_argument("--port", type=int, default=2000)

    p_lat = sub.add_parser("latency", help="Đo trễ chấp hành thực của xe CARLA (T15).")
    p_lat.add_argument("--host", default="127.0.0.1")
    p_lat.add_argument("--port", type=int, default=2000)
    p_lat.add_argument("--town", default="Town04")
    p_lat.add_argument("--trials", type=int, default=3)

    p_sm = sub.add_parser("smoke", help="Chạy S1 + D0 và ghi log chuẩn analyze.py (T16).")
    p_sm.add_argument("--backend", choices=("carla", "fake"), default="carla")
    p_sm.add_argument("--level", choices=("M1", "M2", "M3"), default="M1")
    p_sm.add_argument("--host", default="127.0.0.1")
    p_sm.add_argument("--port", type=int, default=2000)
    p_sm.add_argument("--seed", type=int, default=500)
    p_sm.add_argument("--out", default="logs/carla_smoke")

    p_bn = sub.add_parser("bench", help="Chạy đủ S1–S4 × D0–D5 kiểm tra không lỗi và P95 < 100 ms (T17).")
    p_bn.add_argument("--backend", choices=("carla", "fake"), default="carla")
    p_bn.add_argument("--level", choices=("M1", "M2", "M3"), default="M1")
    p_bn.add_argument("--dense-v", action="store_true")
    p_bn.add_argument("--host", default="127.0.0.1")
    p_bn.add_argument("--port", type=int, default=2000)

    p_pr = sub.add_parser("params", help="Chốt bảng tham số §4.2, cỡ mẫu E3 và lưới vận tốc (T18).")
    p_pr.add_argument("--tcomp-p95", type=float, default=None)
    p_pr.add_argument("--latency-ms", type=float, default=None)
    p_pr.add_argument("--alpha", type=float, default=0.10)
    p_pr.add_argument("--out", default="logs/carla_params")

    p_run = sub.add_parser("run", help="Chạy đầy đủ M1 / M2 / M3 theo Phương án B (T19–T20).")
    p_run.add_argument("--level", choices=("M1", "M2", "M3"), default="M1")
    p_run.add_argument("--backend", choices=("carla", "fake"), default="carla")
    p_run.add_argument("--host", default="127.0.0.1")
    p_run.add_argument("--port", type=int, default=2000)
    p_run.add_argument("--town", default="Town04")
    p_run.add_argument("--agent-mode", choices=("replay", "physics"), default="replay")
    p_run.add_argument("--predictor", choices=("cv", "trajectron", "learned"), default=None)
    p_run.add_argument("--model-dir", default=None)
    p_run.add_argument("--dense-v", action="store_true")
    p_run.add_argument("--alpha", type=float, default=0.10)
    p_run.add_argument("--seed-base", type=int, default=0)
    p_run.add_argument("--scenarios", nargs="+", default=None, metavar="S",
                       help="Chỉ chạy các kịch bản này, vd. --scenarios S1 (mặc định S1–S4).")
    p_run.add_argument("--conditions", nargs="+", default=None, metavar="D",
                       help="Chỉ chạy các điều kiện này, vd. --conditions D0 D1 (mặc định D0–D5).")
    p_run.add_argument("--out", default=None)

    p_rep = sub.add_parser("report", help="Sinh hình H12–H13 và báo cáo CARLA so với 2D (T21).")
    p_rep.add_argument("--ws", default=".")

    return p


def main() -> None:
    args = _build_parser().parse_args()
    ws_dir = Path(__file__).resolve().parent

    if args.cmd == "env":
        env_cfg = CarlaConfig(host=args.host, port=args.port)
        print(json.dumps(check_carla_env(env_cfg, connect=args.connect), ensure_ascii=False, indent=2))
        return

    if args.cmd == "latency":
        cfg = CarlaConfig(host=args.host, port=args.port, town=args.town)
        with CarlaSession(cfg) as sess:
            res = measure_actuator_latency(sess, cfg, n_trials=args.trials)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if args.cmd == "smoke":
        cfg = CarlaConfig(host=args.host, port=args.port, level=args.level).level_defaults()
        res = run_smoke_s1_d0(ws_dir / args.out, cfg=cfg, backend=args.backend, seed=args.seed)
        print(json.dumps(res["episode"], ensure_ascii=False, indent=2))
        return

    if args.cmd == "bench":
        cfg = CarlaConfig(host=args.host, port=args.port, level=args.level).level_defaults()
        res = benchmark_s_x_d(cfg=cfg, backend=args.backend, dense_v_grid=args.dense_v)
        print(json.dumps({k: v for k, v in res.items() if k != "cells"}, ensure_ascii=False, indent=2))
        return

    if args.cmd == "params":
        pac_csv = ws_dir / "logs" / "ext" / "pac_power.csv"
        spec = build_carla_param_spec(
            measured_tcomp_p95_ms=args.tcomp_p95,
            measured_latency_ms=args.latency_ms,
            pac_power_csv=pac_csv if pac_csv.exists() else None,
            alpha=args.alpha,
        )
        jp, mp = export_param_spec(spec, ws_dir / args.out)
        print(f"Đã xuất bảng tham số: {jp} và {mp}")
        return

    if args.cmd == "run":
        out_rel = args.out or f"logs/carla_{args.level.lower()}"
        cfg = CarlaConfig(
            host=args.host,
            port=args.port,
            town=args.town,
            level=args.level,
            agent_mode=args.agent_mode,
            predictor_model_dir=args.model_dir,
        ).level_defaults()
        if args.predictor is not None:
            cfg.predictor = args.predictor
        sel: dict = {}
        if args.scenarios:
            bad = [s for s in args.scenarios if s not in SCENARIOS]
            if bad:
                raise SystemExit(f"Kịch bản không hợp lệ: {bad} (chọn trong {list(SCENARIOS)})")
            sel["scenarios"] = tuple(args.scenarios)
        if args.conditions:
            bad = [c for c in args.conditions if c not in CONDITIONS]
            if bad:
                raise SystemExit(f"Điều kiện không hợp lệ: {bad} (chọn trong {list(CONDITIONS)})")
            sel["conditions"] = tuple(args.conditions)
        res = run_carla_suite(
            **sel,
            out_dir=ws_dir / out_rel,
            cfg=cfg,
            backend=args.backend,
            seed_base=args.seed_base,
            alpha=args.alpha,
            dense_v_grid=args.dense_v,
        )
        print(f"Hoàn tất {args.level} -> {ws_dir / out_rel}")
        print(json.dumps(res["summary"]["by_method"], ensure_ascii=False, indent=2))
        return

    if args.cmd == "report":
        md_path = generate_carla_report(Path(args.ws).resolve())
        print(f"Đã sinh báo cáo CARLA: {md_path}")


if __name__ == "__main__":
    main()

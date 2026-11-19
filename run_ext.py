"""Chạy toàn bộ giai đoạn mở rộng v0.2: OOD/RECAL, thí nghiệm E1–E9, phân tích H7–H11 và báo cáo v0.2.

Cách dùng:
    python run_ext.py --seed-base 0
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

from sim.analyze_ext import run_analysis_ext
from sim.experiments_ext import run_all_experiments_ext
from sim.report_ext import generate_report_ext
from sim.run_ext import run_ood_and_recal


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy mở rộng v0.2 (OOD, RECAL, E1–E9, H7–H11, báo cáo).")
    parser.add_argument("--seed-base", type=int, default=0, help="Hạt giống gốc (mặc định: 0).")
    parser.add_argument(
        "--workers",
        type=int,
        default=min(10, os.cpu_count() or 2),
        help="Số tiến trình song song (mặc định: tối đa 10 tiến trình).",
    )
    parser.add_argument("--alpha", type=float, default=0.1, help="Mức rủi ro danh định (mặc định: 0.1).")
    parser.add_argument("--skip-ood", action="store_true", help="Bỏ qua bước T10 (chỉ chạy E1–E9 + phân tích + báo cáo).")
    parser.add_argument("--skip-sim", action="store_true", help="Bỏ qua toàn bộ mô phỏng, chỉ chạy phân tích + vẽ hình + báo cáo.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    t_start = time.perf_counter()

    if not args.skip_sim:
        if not args.skip_ood:
            print(f"[1/4] Chạy OOD-S/D/SD, RECAL và IN mở rộng (seed_base={args.seed_base}, workers={args.workers})...", flush=True)
            t0 = time.perf_counter()
            ood_res = run_ood_and_recal(root, seed_base=args.seed_base, workers=args.workers, alpha=args.alpha)
            sigma_tau = ood_res["sigma_tau"]
            v01_params = ood_res["v01_params"]
            print(f"      Xong T10 sau {time.perf_counter() - t0:.1f}s.", flush=True)
        else:
            with open(root / "logs" / "new" / "calibration.json", encoding="utf-8") as f:
                cal_v01 = json.load(f)
            sigma_tau = np.array(cal_v01["sigma_tau"], dtype=float)
            from sim.common import CALIB_BLOCK_SEEDS, run_parallel_episodes
            from sim.core import DEFAULT_SIGMA_OLD, condition_for_seed, scenario_for_seed
            from sim.run_ext import _compute_baselines_from_b0_thinned, _extract_b0_thinned

            b0_tasks = [
                (s, scenario_for_seed(s), condition_for_seed(s, args.seed_base), "B0",
                 (0.0, 0.0), DEFAULT_SIGMA_OLD, "const", args.seed_base,
                 {"keep_tau_arrays": True, "compute_open_loop": False})
                for blk in CALIB_BLOCK_SEEDS for s in blk
            ]
            b0_res = run_parallel_episodes(b0_tasks, workers=args.workers)
            _, _, b0_th = _extract_b0_thinned(b0_res, sigma_tau)
            v01_base = _compute_baselines_from_b0_thinned(b0_th, sigma_tau, args.alpha)
            v01_params = {
                **v01_base,
                "q_b1": float(cal_v01["baselines"]["q_B1"]),
                "q_b3": float(cal_v01["baselines"]["q_B3_sum"]),
                "q_b3p": float(cal_v01["baselines"]["q_B3p_sum"]),
                "max_e_calib": float(cal_v01["baselines"]["B4_max_E_m"]),
                "q_dx1": float(cal_v01["DX-1"]["q_final"]),
                "q_dx2": {g: float(v) for g, v in cal_v01["DX-2"]["q_final_by_group"].items()},
            }

        print("[2/4] Chạy thí nghiệm bổ sung E1–E9 -> logs/ext/...", flush=True)
        t0 = time.perf_counter()
        run_all_experiments_ext(
            root, sigma_tau=sigma_tau, v01_params=v01_params,
            seed_base=args.seed_base, workers=args.workers, alpha=args.alpha,
        )
        print(f"      Xong E1–E9 sau {time.perf_counter() - t0:.1f}s.", flush=True)

    print("[3/4] Chạy phân tích thống kê và vẽ hình H7–H11 -> figs/...", flush=True)
    t0 = time.perf_counter()
    run_analysis_ext(root)
    print(f"      Xong H7–H11 sau {time.perf_counter() - t0:.1f}s.", flush=True)

    print("[4/4] Sinh báo cáo mở rộng v0.2 (.md và .docx) -> report/...", flush=True)
    t0 = time.perf_counter()
    md_path, docx_path = generate_report_ext(root)
    print(f"      Đã tạo {md_path} và {docx_path} sau {time.perf_counter() - t0:.1f}s.", flush=True)
    print(f"HOÀN TẤT MỞ RỘNG v0.2 SAU {time.perf_counter() - t_start:.1f}s.", flush=True)


if __name__ == "__main__":
    main()

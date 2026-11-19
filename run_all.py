"""Chạy toàn bộ mô phỏng phương án cũ (A) và phương án mới (B), phân tích và vẽ hình.

Cách dùng:
    python run_all.py --seed-base 0
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from sim.analyze import run_analysis
from sim.common import run_shared_b0_all
from sim.run_new import run_new
from sim.run_old import run_old


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy toàn bộ mô phỏng so sánh phương án cũ (A) và mới (B).")
    parser.add_argument("--seed-base", type=int, default=0, help="Hạt giống gốc (mặc định: 0).")
    parser.add_argument(
        "--workers",
        type=int,
        default=min(8, os.cpu_count() or 2),
        help="Số tiến trình song song (mặc định: tối đa 8 tiến trình).",
    )
    parser.add_argument("--alpha", type=float, default=0.1, help="Mức rủi ro danh định alpha (mặc định: 0.1).")
    parser.add_argument("--skip-sim", action="store_true", help="Bỏ qua mô phỏng, chỉ chạy lại phân tích và vẽ hình.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    logs_old = root / "logs" / "A"
    logs_new = root / "logs" / "B"
    figs_dir = root / "figs"

    t_start = time.perf_counter()

    if not args.skip_sim:
        print(f"[1/4] Chạy B0 dùng chung (seed_base={args.seed_base}, workers={args.workers})...", flush=True)
        t0 = time.perf_counter()
        shared_b0 = run_shared_b0_all(seed_base=args.seed_base, workers=args.workers)
        print(f"      Xong B0 dùng chung sau {time.perf_counter() - t0:.1f}s.", flush=True)

        print("[2/4] Chạy Phương án A (cũ) -> logs/A/...", flush=True)
        t0 = time.perf_counter()
        run_old(logs_old, seed_base=args.seed_base, workers=args.workers, shared_b0=shared_b0, alpha=args.alpha)
        print(f"      Xong Phương án A sau {time.perf_counter() - t0:.1f}s.", flush=True)

        print("[3/4] Chạy Phương án B (mới) + quét alpha -> logs/B/...", flush=True)
        t0 = time.perf_counter()
        run_new(logs_new, seed_base=args.seed_base, workers=args.workers, shared_b0=shared_b0, alpha=args.alpha)
        print(f"      Xong Phương án B sau {time.perf_counter() - t0:.1f}s.", flush=True)

    print("[4/4] Chạy phân tích thống kê và vẽ 6 hình H1–H6 -> figs/...", flush=True)
    t0 = time.perf_counter()
    run_analysis(logs_old, logs_new, figs_dir)
    print(f"      Xong phân tích và vẽ hình sau {time.perf_counter() - t0:.1f}s.", flush=True)

    # Nếu có module báo cáo thì sinh báo cáo luôn từ log mới nhất
    try:
        from sim.report import generate_report
        generate_report(root)
        print("      Đã cập nhật báo cáo tại report/.", flush=True)
    except ImportError:
        pass

    print(f"HOÀN TẤT TOÀN BỘ SAU {time.perf_counter() - t_start:.1f}s.", flush=True)


if __name__ == "__main__":
    main()

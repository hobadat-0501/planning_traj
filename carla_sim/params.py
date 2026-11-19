"""Chốt tham số CARLA cho Bảng §4.2, cỡ mẫu chứng nhận theo E3 và lưới vận tốc (T18 / G16)."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from sim.common import pac_order_index
from sim.core import D_S, DELTA_MAX, DT_PLAN, DT_SIM, H_STEPS, V_MAX, WHEELBASE

# Các giá trị chốt điền vào ô [X] của Bảng §4.2 bản thảo (có căn cứ từ SPEC §1 và E3/E7)
TABLE_4_2_PARAMS: dict[str, Any] = {
    "scheme": "B",
    "scheme_justification": (
        "Phương án B loại mẫu -inf, lấy thưa 3,0 s không chồng cửa sổ, dùng cận Hausdorff A_h, "
        "sigma_tau ước lượng tách biệt và chứng nhận PAC Bonferroni — khắc phục toàn bộ sai lệch "
        "thống kê đã phát hiện ở Phương án A."
    ),
    "vehicle": {
        "blueprint": "vehicle.tesla.model3",
        "wheelbase_m": WHEELBASE,
        "v_max_mps": V_MAX,
        "delta_max_rad": DELTA_MAX,
        "dt_sim_s": DT_SIM,
        "dt_plan_s": DT_PLAN,
        "horizon_steps": H_STEPS,
    },
    "localization_error_model": {
        "fix": {
            "label": "fix",
            "sigma_xy_m": 0.03,
            "sigma_psi_rad": 0.003,
            "sigma_v_mps": 0.03,
            "model": "Gaussian độc lập (RTK cố định chuẩn đô thị)",
        },
        "float": {
            "label": "float",
            "sigma_xy_m": 0.30,
            "sigma_psi_rad": 0.02,
            "tau_ar1_s": 5.0,
            "sigma_v_mps": 0.08,
            "model": "AR(1) hằng số thời gian 5,0 s (RTK thả nổi / đa đường đô thị)",
        },
        "loss": {
            "label": "loss",
            "outage_duration_s": [5.0, 10.0],
            "yaw_bias_radps": [0.004, 0.009],
            "yaw_rw_rad_sqrt_s": 0.008,
            "pos_rw_m_sqrt_s": 0.08,
            "recovery_tau_s": 1.5,
            "model": "Trôi tích lũy IMU/odometry khi mất GNSS, hội tụ hàm mũ tau=1,5 s",
        },
    },
    "safety_margin_ds_m": D_S,
    "safety_margin_ds_justification": (
        "Giữ d_s = 0,50 m làm cấu hình chính (khớp SPEC §1); E7 cho thấy d_s = 1,00 m hữu ích "
        "khi muốn kiểm tra bão hòa độ phủ vật lý ở làn hẹp."
    ),
}


def select_cert_sample_size(
    alpha: float = 0.10,
    delta: float = 0.05,
    max_tries: int = 3,
    max_excess_cov: float = 0.02,
    cycles_per_episode: float = 3.6,
    pac_power_csv: Path | None = None,
) -> dict[str, Any]:
    """Chọn cỡ mẫu chứng nhận PAC tối thiểu `n_cert` theo kết quả E3 (hoặc công thức nhị thức).

    Mục tiêu (SPEC §9.4 E3): tìm n_cert nhỏ nhất sao cho phần dư độ phủ yêu cầu
    `(k_pac / n_cert) - (1 - alpha) <= max_excess_cov` với Bonferroni `delta / max_tries`.
    """
    delta_per_try = float(delta) / max(1, int(max_tries))
    target_cov = 1.0 - float(alpha)

    # Ưu tiên kiểm tra lưới E3 nếu file tồn tại
    e3_rows: list[dict[str, Any]] = []
    if pac_power_csv is not None and pac_power_csv.exists():
        with open(pac_power_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("source") == "mc_binom":
                    e3_rows.append(row)

    chosen_n = None
    chosen_k = None
    for n in range(50, 2001, 10):
        k = pac_order_index(n, alpha, delta_per_try)
        if k <= n:
            excess = (k / n) - target_cov
            if excess <= max_excess_cov:
                chosen_n = n
                chosen_k = k
                break

    if chosen_n is None:
        chosen_n = 800
        chosen_k = pac_order_index(chosen_n, alpha, delta_per_try)

    n_episodes_cert = int(math.ceil(chosen_n / max(cycles_per_episode, 0.5)))
    # Đảm bảo đủ mẫu tối thiểu cho nhóm 'loss' (n_min >= 39) khi D2 chiếm ~1/6 lượt
    n_episodes_d2_dedicated = int(math.ceil(45.0 / max(cycles_per_episode * 0.6, 0.5)))

    return {
        "alpha": float(alpha),
        "delta_total": float(delta),
        "max_tries": int(max_tries),
        "delta_per_try": float(delta_per_try),
        "max_excess_cov_target": float(max_excess_cov),
        "recommended_n_cert_cycles": int(chosen_n),
        "k_pac": int(chosen_k),
        "required_emp_cov": float(chosen_k / chosen_n),
        "excess_cov": float((chosen_k / chosen_n) - target_cov),
        "recommended_cert_episodes_per_try": int(n_episodes_cert),
        "recommended_d2_dedicated_episodes": int(n_episodes_d2_dedicated),
        "checkpoint_block_size_episodes": 25,
        "e3_rows_loaded": len(e3_rows),
    }


def select_velocity_grid(
    measured_tcomp_p95_ms: float | None = None,
    budget_ms: float = 100.0,
) -> dict[str, Any]:
    """Chọn lưới vận tốc 0,5 m/s (663 ứng viên) hay 1,0 m/s (351 ứng viên) theo benchmark T17."""
    # Nếu đo trên 351 ứng viên < 45% ngân sách (45 ms), có thể nâng lên lưới dày 0,5 m/s (663 ứng viên)
    if measured_tcomp_p95_ms is not None and measured_tcomp_p95_ms <= 0.45 * budget_ms:
        return {
            "v_step_mps": 0.5,
            "dense_v_grid": True,
            "n_candidates": 663,
            "measured_tcomp_p95_ms": float(measured_tcomp_p95_ms),
            "budget_ms": float(budget_ms),
            "reason": "Thời gian tính đo ở T17 đủ nhỏ (<= 45% ngân sách 100 ms), cho phép dùng lưới 0,5 m/s khớp bản thảo.",
        }
    return {
        "v_step_mps": 1.0,
        "dense_v_grid": False,
        "n_candidates": 351,
        "measured_tcomp_p95_ms": float(measured_tcomp_p95_ms) if measured_tcomp_p95_ms is not None else None,
        "budget_ms": float(budget_ms),
        "reason": "Dùng lưới 1,0 m/s (351 ứng viên) để bảo đảm thời gian lập kế hoạch + tính biên < 0,1 s theo yêu cầu T17.",
    }


def build_carla_param_spec(
    measured_tcomp_p95_ms: float | None = None,
    measured_latency_ms: float | None = None,
    pac_power_csv: Path | None = None,
    alpha: float = 0.10,
) -> dict[str, Any]:
    """Tổng hợp toàn bộ bảng tham số chốt cho T18 (G16)."""
    spec = {
        "table_4_2": TABLE_4_2_PARAMS,
        "sample_size_e3": select_cert_sample_size(alpha=alpha, pac_power_csv=pac_power_csv),
        "velocity_grid": select_velocity_grid(measured_tcomp_p95_ms=measured_tcomp_p95_ms),
        "measured_actuator_latency_ms": float(measured_latency_ms) if measured_latency_ms is not None else None,
    }
    return spec


def export_param_spec(spec: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    """Lưu bảng tham số chốt ra JSON và Markdown (phục vụ duyệt T18 và điền Bảng §4.2)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "params_table_4_2.json"
    md_path = out_dir / "params_table_4_2.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    loc = spec["table_4_2"]["localization_error_model"]
    ss = spec["sample_size_e3"]
    vg = spec["velocity_grid"]
    lines = [
        "# Bảng tham số chốt cho mô phỏng CARLA (T18 / Bảng §4.2)",
        "",
        f"- **Phương án áp dụng:** Phương án **{spec['table_4_2']['scheme']}**",
        f"- **Khoảng cách an toàn $d_s$:** {spec['table_4_2']['safety_margin_ds_m']:.2f} m",
        f"- **Lưới vận tốc Frenet:** bước {vg['v_step_mps']} m/s ({vg['n_candidates']} ứng viên) — {vg['reason']}",
        f"- **Cỡ mẫu chứng nhận PAC (E3):** $n_{{\\text{{cert}}}} \\ge {ss['recommended_n_cert_cycles']}$ chu kỳ "
        f"($k_{{\\text{{PAC}}}} = {ss['k_pac']}$, độ phủ yêu cầu {ss['required_emp_cov']:.3f}, "
        f"dư $\\le {ss['excess_cov']:.3f}$, tương đương ~{ss['recommended_cert_episodes_per_try']} lượt/lần thử)",
        f"- **Khối checkpoint:** mỗi {ss['checkpoint_block_size_episodes']} lượt lưu điểm phục hồi.",
        "",
        "## Mô hình sai số định vị điền vào Bảng §4.2",
        "",
        "| Trạng thái định vị | Nhãn $g$ | $\\sigma_{xy}$ (m) | $\\sigma_\\psi$ (rad) | Đặc trưng động học |",
        "|---|---|---|---|---|",
        f"| RTK cố định | `fix` | {loc['fix']['sigma_xy_m']:.2f} | {loc['fix']['sigma_psi_rad']:.3f} | {loc['fix']['model']} |",
        f"| RTK thả nổi | `float` | {loc['float']['sigma_xy_m']:.2f} | {loc['float']['sigma_psi_rad']:.3f} | {loc['float']['model']} |",
        f"| Mất GNSS | `loss` | RW {loc['loss']['pos_rw_m_sqrt_s']:.2f} m/$\\sqrt{{\\text{{s}}}}$ | bias {loc['loss']['yaw_bias_radps'][0]:.3f}–{loc['loss']['yaw_bias_radps'][1]:.3f} rad/s | {loc['loss']['model']} |",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path

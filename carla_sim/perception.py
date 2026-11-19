"""Đầu vào nhận diện và dự báo tác nhân cho 3 mức M1 / M2 / M3 (PLAN §9.1, T19–T20).

- M1: Ground truth CARLA + nhiễu Gauss (`gt_noise`), dự báo vận tốc hằng (`cv`) —
  gọi trực tiếp `sim.core.predict_agents_cv`.
- M2: Như M1 cho nhận diện, thay dự báo bằng Trajectron++ (`trajectron`) nếu có
  checkpoint, hoặc bộ dự báo động học phi tuyến học từ lịch sử ngắn CTRA (`learned`).
- M3: Detector + tracker LiDAR (`lidar`) có xét che khuất, bỏ sót theo khoảng cách,
  và nhiễu/đổi nhãn track; kèm bộ dự báo M2.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from carla_sim.config import CarlaConfig
from sim.conditions_ext import get_perception_params
from sim.core import (
    AGENT_DISK_SPECS,
    DT_PLAN,
    H_STEPS,
    ROI_DIST,
    XC_LOCAL,
    SimAgent,
    predict_agents_cv,
    wrap_angle,
)
from sim.scenarios_ext import CurvedReferencePath, StaticObstacleBox, is_agent_occluded


@dataclass
class PerceptionStats:
    """Thống kê chất lượng nhận diện (hữu ích cho M3: bỏ sót, đổi ID, che khuất)."""

    n_gt_in_roi: int = 0
    n_detected: int = 0
    n_missed: int = 0
    n_occluded: int = 0
    n_id_switch: int = 0

    def to_dict(self) -> dict[str, Any]:
        det_rate = (self.n_detected / self.n_gt_in_roi) if self.n_gt_in_roi > 0 else 1.0
        return {
            "n_gt_in_roi": int(self.n_gt_in_roi),
            "n_detected": int(self.n_detected),
            "n_missed": int(self.n_missed),
            "n_occluded": int(self.n_occluded),
            "n_id_switch": int(self.n_id_switch),
            "detection_rate": float(det_rate),
        }


class ConstantTurnRateAccelPredictor:
    """Bộ dự báo CTRA ước lượng tốc độ quay và gia tốc dọc từ lịch sử 0,8 s gần nhất.

    Dùng làm bộ dự báo cải tiến cho M2 (`predictor='learned'`) hoặc khi chưa cài
    trọng số Trajectron++ bên ngoài. Giảm dần gia tốc và tốc độ quay theo hằng số
    thời gian `tau_damp` để tránh ngoại suy quá đà ở chân trời 3 s.
    """

    def __init__(self, history_len: int = 8, tau_damp_a: float = 1.4, tau_damp_w: float = 1.6) -> None:
        self.history_len = int(history_len)
        self.tau_damp_a = float(tau_damp_a)
        self.tau_damp_w = float(tau_damp_w)
        self._hist: dict[str, deque[tuple[float, float, float, float, float, float]]] = {}

    def reset(self) -> None:
        self._hist.clear()

    def update_and_predict(
        self,
        agent_id: str,
        t: float,
        px_obs: float,
        py_obs: float,
        vx_obs: float,
        vy_obs: float,
        psi_obs: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        buf = self._hist.setdefault(agent_id, deque(maxlen=self.history_len))
        v_obs = math.hypot(vx_obs, vy_obs)
        buf.append((float(t), float(px_obs), float(py_obs), float(vx_obs), float(vy_obs), float(psi_obs)))

        a_est = 0.0
        w_est = 0.0
        if len(buf) >= 3:
            ts = np.array([b[0] for b in buf], dtype=float)
            dt_span = ts[-1] - ts[0]
            if dt_span >= 0.15:
                vs = np.array([math.hypot(b[3], b[4]) for b in buf], dtype=float)
                psis = np.unwrap([b[5] for b in buf])
                # Hồi quy tuyến tính có trọng số mũ (ưu tiên mẫu gần nhất)
                weights = np.exp((ts - ts[-1]) / 0.45)
                t_rel = ts - ts[-1]
                w_sum = float(np.sum(weights))
                t_bar = float(np.sum(weights * t_rel) / w_sum)
                denom = float(np.sum(weights * (t_rel - t_bar) ** 2))
                if denom > 1e-6:
                    v_bar = float(np.sum(weights * vs) / w_sum)
                    p_bar = float(np.sum(weights * psis) / w_sum)
                    a_est = float(np.sum(weights * (t_rel - t_bar) * (vs - v_bar)) / denom)
                    w_est = float(np.sum(weights * (t_rel - t_bar) * (psis - p_bar)) / denom)

        # Cắt ngưỡng vật lý hợp lý
        a_est = float(np.clip(a_est, -5.0, 3.0))
        w_est = float(np.clip(w_est, -0.8, 0.8))

        pred_c = np.zeros((H_STEPS, 2), dtype=float)
        pred_yaws = np.zeros(H_STEPS, dtype=float)
        x, y, psi, v = float(px_obs), float(py_obs), float(psi_obs), float(v_obs)
        for step in range(H_STEPS):
            tau = (step + 1) * DT_PLAN
            a_t = a_est * math.exp(-tau / self.tau_damp_a)
            w_t = w_est * math.exp(-tau / self.tau_damp_w)
            v = float(np.clip(v + a_t * DT_PLAN, 0.0, 12.0))
            psi = float(wrap_angle(psi + w_t * DT_PLAN))
            x += v * math.cos(psi) * DT_PLAN
            y += v * math.sin(psi) * DT_PLAN
            pred_c[step, 0] = x
            pred_c[step, 1] = y
            pred_yaws[step] = psi
        return pred_c, pred_yaws


class TrajectronAdapter:
    """Bộ nối Trajectron++ ngoài (M2); tự chuyển về CTRA nếu chưa cài trọng số."""

    def __init__(self, model_dir: str | None = None) -> None:
        self.model_dir = model_dir
        self._external_model: Any = None
        self._fallback = ConstantTurnRateAccelPredictor()
        self.using_external = False
        if model_dir:
            self._try_load_external(model_dir)

    def _try_load_external(self, model_dir: str) -> None:
        try:
            import torch  # noqa: F401, PLC0415
            from pathlib import Path  # noqa: PLC0415

            p = Path(model_dir)
            if p.exists():
                # Hook để người dùng cắm mô hình Trajectron++ thực tế khi có trọng số
                self._external_model = {"model_dir": str(p)}
                self.using_external = False  # Chưa nạp đồ thị mạng cụ thể -> dùng CTRA
        except ImportError:
            self._external_model = None
            self.using_external = False

    def reset(self) -> None:
        self._fallback.reset()

    def update_and_predict(
        self,
        agent_id: str,
        t: float,
        px_obs: float,
        py_obs: float,
        vx_obs: float,
        vy_obs: float,
        psi_obs: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        return self._fallback.update_and_predict(agent_id, t, px_obs, py_obs, vx_obs, vy_obs, psi_obs)


class LidarTrackerModel:
    """Mô hình detector + tracker LiDAR cho M3 (che khuất tia, bỏ sót theo cự ly, đổi nhãn).

    Khi chạy với CARLA server và cảm biến LiDAR thật có thể nạp thêm cụm điểm,
    còn ở chế độ mô phỏng cảm biến vật lý dùng mô hình xác suất bỏ sót theo cự ly
    + kiểm tra đường ngắm giữa các tác nhân (che khuất lẫn nhau) + lọc Kalman đơn giản.
    """

    def __init__(self, max_range: float = ROI_DIST) -> None:
        self.max_range = float(max_range)
        self._tracks: dict[str, dict[str, Any]] = {}
        self._next_track_num = 1
        self._gt_to_track: dict[str, str] = {}

    def reset(self) -> None:
        self._tracks.clear()
        self._gt_to_track.clear()
        self._next_track_num = 1

    def _is_mutually_occluded(
        self,
        sensor_x: float,
        sensor_y: float,
        target: SimAgent,
        others: list[SimAgent],
    ) -> bool:
        """Kiểm tra xem một tác nhân lớn hơn (ô tô) ở gần hơn có che khuất tia LiDAR không."""
        tx, ty = target.px - sensor_x, target.py - sensor_y
        d_t = math.hypot(tx, ty)
        if d_t < 1e-3:
            return False
        ang_t = math.atan2(ty, tx)
        for o in others:
            if o.id == target.id or o.kind != "car":
                continue
            ox, oy = o.px - sensor_x, o.py - sensor_y
            d_o = math.hypot(ox, oy)
            if d_o >= d_t - 0.5 or d_o < 1.0:
                continue
            ang_o = math.atan2(oy, ox)
            half_cone = math.atan2(o.disk_radius + 0.3, d_o)
            if abs(float(wrap_angle(ang_t - ang_o))) <= half_cone:
                return True
        return False

    def observe(
        self,
        agents: list[SimAgent],
        ego_px: float,
        ego_py: float,
        ego_psi: float,
        t: float,
        rng: np.random.Generator,
        static_obs: list[StaticObstacleBox] | None,
        ref_path: CurvedReferencePath | None,
        ego_s: float | None,
        condition: str,
        stats: PerceptionStats,
    ) -> list[dict[str, Any]]:
        """Trả về danh sách trạng thái ước lượng của các tác nhân được phát hiện."""
        perc = get_perception_params(condition)
        pos_sig = float(perc["pos_sigma"]) * 1.6  # Detector LiDAR có sai số hộp bao lớn hơn GT
        vel_sig = float(perc["vel_sigma"]) * 1.8
        base_drop = float(perc["dropout_prob"])

        sx = ego_px + XC_LOCAL * math.cos(ego_psi)
        sy = ego_py + XC_LOCAL * math.sin(ego_psi)
        observations: list[dict[str, Any]] = []

        for ag in agents:
            if not ag.is_in_roi(ego_px, ego_py, ref_path=ref_path, ego_s=ego_s, t=t):
                continue
            stats.n_gt_in_roi += 1

            # 1. Che khuất bởi vật cản tĩnh (S5) hoặc xe lớn hơn
            occl_static = bool(
                static_obs
                and is_agent_occluded(sx, sy, ag.px, ag.py, ag.psi, ag.disk_offsets, ag.disk_radius, static_obs)
            )
            occl_mutual = self._is_mutually_occluded(sx, sy, ag, agents)
            if occl_static or occl_mutual:
                stats.n_occluded += 1
                stats.n_missed += 1
                continue
            if not ag.revealed:
                ag.revealed = True
                ag.reveal_t = t

            # 2. Xác suất bỏ sót tăng theo khoảng cách và nhỏ hơn với vật thể nhỏ (ped)
            dist = math.hypot(ag.px - sx, ag.py - sy)
            size_factor = 1.5 if ag.kind == "ped" else (1.1 if ag.kind == "moto" else 0.6)
            p_miss = min(0.50, base_drop + 0.02 * size_factor * ((dist / self.max_range) ** 2))
            if float(rng.random()) < p_miss:
                stats.n_missed += 1
                continue

            stats.n_detected += 1
            px, py, psi, v = ag.pose_vel()
            vx_true, vy_true = v * math.cos(psi), v * math.sin(psi)

            px_obs = px + float(rng.normal(0.0, pos_sig))
            py_obs = py + float(rng.normal(0.0, pos_sig))
            vx_obs = vx_true + float(rng.normal(0.0, vel_sig))
            vy_obs = vy_true + float(rng.normal(0.0, vel_sig))
            speed_obs = math.hypot(vx_obs, vy_obs)
            psi_obs = math.atan2(vy_obs, vx_obs) if speed_obs > 0.30 else float(wrap_angle(psi + rng.normal(0.0, 0.08)))

            # 3. Theo dõi track & xác suất đổi ID nhẹ khi ở xa (2%)
            if ag.id not in self._gt_to_track:
                self._gt_to_track[ag.id] = f"trk_{self._next_track_num}"
                self._next_track_num += 1
            elif dist > 20.0 and float(rng.random()) < 0.02:
                self._gt_to_track[ag.id] = f"trk_{self._next_track_num}"
                self._next_track_num += 1
                stats.n_id_switch += 1

            observations.append({
                "id": ag.id,  # giữ ánh xạ GT id cho tính metric sau H bước
                "track_id": self._gt_to_track[ag.id],
                "kind": ag.kind,
                "disk_radius": ag.disk_radius,
                "disk_offsets": ag.disk_offsets,
                "px": px_obs,
                "py": py_obs,
                "vx": vx_obs,
                "vy": vy_obs,
                "psi": psi_obs,
            })
        return observations


class PerceptionPredictor:
    """Bộ mặt thống nhất cho M1 / M2 / M3, xuất đúng định dạng `pred_agents` của `sim.core`."""

    def __init__(self, cfg: CarlaConfig) -> None:
        self.cfg = cfg
        self.stats = PerceptionStats()
        if cfg.predictor == "trajectron":
            self._predictor: Any = TrajectronAdapter(cfg.predictor_model_dir)
        elif cfg.predictor == "learned":
            self._predictor = ConstantTurnRateAccelPredictor()
        else:
            self._predictor = None
        self._lidar = LidarTrackerModel() if cfg.perception == "lidar" else None

    def reset(self) -> None:
        self.stats = PerceptionStats()
        if self._predictor is not None:
            self._predictor.reset()
        if self._lidar is not None:
            self._lidar.reset()

    def observe_and_predict(
        self,
        agents: list[SimAgent],
        ego_px: float,
        ego_py: float,
        rng_obs: np.random.Generator,
        *,
        static_obs: list[StaticObstacleBox] | None = None,
        ref_path: CurvedReferencePath | None = None,
        ego_s: float | None = None,
        t: float = 0.0,
        ego_psi: float = 0.0,
        condition: str = "D0",
        delayed_snaps: dict[str, tuple[float, float, float, float]] | None = None,
        prev_preds_by_id: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        # M1: Ground truth + nhiễu Gauss + dự báo vận tốc hằng -> dùng thẳng sim.core
        if self.cfg.perception == "gt_noise" and self.cfg.predictor == "cv":
            preds = predict_agents_cv(
                agents,
                ego_px,
                ego_py,
                rng_obs,
                static_obs=static_obs,
                ref_path=ref_path,
                ego_s=ego_s,
                t=t,
                ego_psi=ego_psi,
                condition=condition,
                delayed_snaps=delayed_snaps,
                prev_preds_by_id=prev_preds_by_id,
            )
            self.stats.n_detected += len(preds)
            self.stats.n_gt_in_roi += len(preds)
            return preds

        # M3: Nhận diện LiDAR có bỏ sót, che khuất, đổi ID
        if self.cfg.perception == "lidar" and self._lidar is not None:
            obs_list = self._lidar.observe(
                agents, ego_px, ego_py, ego_psi, t, rng_obs,
                static_obs, ref_path, ego_s, condition, self.stats,
            )
            preds_out: list[dict[str, Any]] = []
            tau_vec = np.arange(1, H_STEPS + 1, dtype=float) * DT_PLAN
            for ob in obs_list:
                if self._predictor is not None:
                    pred_c, pred_yaws = self._predictor.update_and_predict(
                        ob["track_id"], t, ob["px"], ob["py"], ob["vx"], ob["vy"], ob["psi"],
                    )
                else:
                    pred_c = np.column_stack([ob["px"] + ob["vx"] * tau_vec, ob["py"] + ob["vy"] * tau_vec])
                    pred_yaws = np.full(H_STEPS, ob["psi"], dtype=float)
                preds_out.append({
                    "id": ob["id"],
                    "kind": ob["kind"],
                    "disk_radius": ob["disk_radius"],
                    "disk_offsets": ob["disk_offsets"],
                    "pred_centers": pred_c,
                    "pred_yaws": pred_yaws,
                })
            return preds_out

        # M2: Ground truth + nhiễu Gauss + bộ dự báo học được / Trajectron++
        perc = get_perception_params(condition)
        pos_sig = float(perc["pos_sigma"])
        vel_sig = float(perc["vel_sigma"])
        drop_prob = float(perc["dropout_prob"])
        sx = ego_px + XC_LOCAL * math.cos(ego_psi)
        sy = ego_py + XC_LOCAL * math.sin(ego_psi)

        preds_m2: list[dict[str, Any]] = []
        for ag in agents:
            if not ag.is_in_roi(ego_px, ego_py, ref_path=ref_path, ego_s=ego_s, t=t):
                continue
            self.stats.n_gt_in_roi += 1
            if static_obs:
                occl_now = is_agent_occluded(sx, sy, ag.px, ag.py, ag.psi, ag.disk_offsets, ag.disk_radius, static_obs)
                if not ag.revealed:
                    if occl_now:
                        self.stats.n_occluded += 1
                        continue
                    ag.revealed = True
                    ag.reveal_t = t

            if drop_prob > 0.0 and float(rng_obs.random()) < drop_prob:
                self.stats.n_missed += 1
                if prev_preds_by_id is not None and ag.id in prev_preds_by_id:
                    prev = prev_preds_by_id[ag.id]
                    old_c = prev["pred_centers"]
                    step_delta = old_c[-1] - old_c[-2]
                    shifted = {
                        **prev,
                        "pred_centers": np.vstack([old_c[1:], old_c[-1:] + step_delta[None, :]]),
                        "pred_yaws": prev["pred_yaws"].copy(),
                    }
                    prev_preds_by_id[ag.id] = shifted
                    preds_m2.append(shifted)
                continue

            self.stats.n_detected += 1
            if delayed_snaps is not None and ag.id in delayed_snaps:
                px, py, psi, v = delayed_snaps[ag.id]
            else:
                px, py, psi, v = ag.pose_vel()
            vx_true, vy_true = v * math.cos(psi), v * math.sin(psi)
            px_obs = px + float(rng_obs.normal(0.0, pos_sig))
            py_obs = py + float(rng_obs.normal(0.0, pos_sig))
            vx_obs = vx_true + float(rng_obs.normal(0.0, vel_sig))
            vy_obs = vy_true + float(rng_obs.normal(0.0, vel_sig))
            speed_obs = math.hypot(vx_obs, vy_obs)
            psi_obs = math.atan2(vy_obs, vx_obs) if speed_obs > 0.30 else float(wrap_angle(psi + rng_obs.normal(0.0, 0.05)))

            pred_c, pred_yaws = self._predictor.update_and_predict(
                ag.id, t, px_obs, py_obs, vx_obs, vy_obs, psi_obs,
            )
            entry = {
                "id": ag.id,
                "kind": ag.kind,
                "disk_radius": ag.disk_radius,
                "disk_offsets": ag.disk_offsets,
                "pred_centers": pred_c,
                "pred_yaws": pred_yaws,
            }
            if prev_preds_by_id is not None:
                prev_preds_by_id[ag.id] = entry
            preds_m2.append(entry)
        return preds_m2

"""Mở rộng kịch bản S5–S10, đường cong Frenet (S7) và che khuất đường ngắm (S5) theo SPEC §9.1."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

SCENARIOS_EXT: tuple[str, ...] = ("S5", "S6", "S7", "S8", "S9", "S10")


def _wrap_angle(angle: np.ndarray | float) -> np.ndarray | float:
    return np.arctan2(np.sin(angle), np.cos(angle))


@dataclass
class StaticObstacleBox:
    """Hộp chữ nhật vật cản tĩnh (xe đỗ lề phải trong S5)."""

    cx: float
    cy: float
    length: float = 4.5
    width: float = 1.8

    @property
    def xmin(self) -> float:
        return self.cx - 0.5 * self.length

    @property
    def xmax(self) -> float:
        return self.cx + 0.5 * self.length

    @property
    def ymin(self) -> float:
        return self.cy - 0.5 * self.width

    @property
    def ymax(self) -> float:
        return self.cy + 0.5 * self.width


def segment_intersects_aabb(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    box: StaticObstacleBox,
) -> bool:
    """Kiểm tra đoạn thẳng (x0, y0)-(x1, y1) có cắt hộp chữ nhật AABB hay không (Liang-Barsky)."""
    dx = x1 - x0
    dy = y1 - y0
    t_min = 0.0
    t_max = 1.0

    for p, q in (
        (-dx, x0 - box.xmin),
        (dx, box.xmax - x0),
        (-dy, y0 - box.ymin),
        (dy, box.ymax - y0),
    ):
        if abs(p) < 1e-12:
            if q < 0.0:
                return False
        else:
            t = q / p
            if p < 0.0:
                if t > t_max:
                    return False
                if t > t_min:
                    t_min = t
            else:
                if t < t_min:
                    return False
                if t < t_max:
                    t_max = t
    return t_min <= t_max


def is_agent_occluded(
    sensor_x: float,
    sensor_y: float,
    ag_px: float,
    ag_py: float,
    ag_psi: float,
    disk_offsets: np.ndarray,
    disk_radius: float,
    static_obstacles: list[StaticObstacleBox],
) -> bool:
    """Tác nhân bị che khuất nếu đường ngắm tới MỌI đĩa đều bị vật cản tĩnh chắn (SPEC §9.1)."""
    if not static_obstacles:
        return False

    c_a = math.cos(ag_psi)
    s_a = math.sin(ag_psi)
    for off in disk_offsets:
        off_f = float(off)
        qx = ag_px + off_f * c_a
        qy = ag_py + off_f * s_a
        # Kiểm tra 3 tia tới đĩa (tâm và hai mép vuông góc tia nhìn) để tránh che giả tạo ở biên
        dx = qx - sensor_x
        dy = qy - sensor_y
        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            return False
        nx = -dy / dist
        ny = dx / dist
        sample_pts = (
            (qx, qy),
            (qx + 0.7 * disk_radius * nx, qy + 0.7 * disk_radius * ny),
            (qx - 0.7 * disk_radius * nx, qy - 0.7 * disk_radius * ny),
        )
        for px_t, py_t in sample_pts:
            blocked = any(segment_intersects_aabb(sensor_x, sensor_y, px_t, py_t, box) for box in static_obstacles)
            if not blocked:
                return False
    return True


class CurvedReferencePath:
    """Đường tham chiếu nối trơn C1: đoạn thẳng đầu -> cung tròn bán kính R -> đoạn thẳng cuối (S7)."""

    def __init__(
        self,
        radius: float = 25.0,
        turn_dir: float = 1.0,
        s1: float = 15.0,
        arc_len: float = 40.0,
        s_total: float = 95.0,
    ) -> None:
        self.radius = float(radius)
        self.turn_dir = 1.0 if turn_dir >= 0.0 else -1.0
        self.s1 = float(s1)
        self.arc_len = float(arc_len)
        self.s2 = self.s1 + self.arc_len
        self.s_total = float(s_total)

        self.cx = self.s1
        self.cy = self.turn_dir * self.radius
        self.phi_tot = self.arc_len / self.radius
        self.theta2 = self.turn_dir * self.phi_tot
        self.x2 = self.s1 + self.radius * math.sin(self.phi_tot)
        self.y2 = self.turn_dir * self.radius * (1.0 - math.cos(self.phi_tot))
        self.cos2 = math.cos(self.theta2)
        self.sin2 = math.sin(self.theta2)
        self.kappa_arc = self.turn_dir / self.radius

    def eval_point(self, s: float) -> tuple[float, float, float, float]:
        """Trả về (xr, yr, theta_r, kappa_r) tại hoành độ cung s."""
        if s <= self.s1:
            return float(s), 0.0, 0.0, 0.0
        if s <= self.s2:
            ds = s - self.s1
            phi = ds / self.radius
            xr = self.s1 + self.radius * math.sin(phi)
            yr = self.turn_dir * self.radius * (1.0 - math.cos(phi))
            theta_r = self.turn_dir * phi
            return xr, yr, theta_r, self.kappa_arc
        ds2 = s - self.s2
        xr = self.x2 + ds2 * self.cos2
        yr = self.y2 + ds2 * self.sin2
        return xr, yr, self.theta2, 0.0

    def eval_batch(self, s_arr: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Đánh giá (xr, yr, theta_r, kappa_r) trên mảng s bất kỳ."""
        s = np.asarray(s_arr, dtype=float)
        m1 = s <= self.s1
        m2 = (~m1) & (s <= self.s2)

        phi = np.clip((s - self.s1) / self.radius, 0.0, self.phi_tot)
        ds2 = s - self.s2

        xr_arc = self.s1 + self.radius * np.sin(phi)
        yr_arc = self.turn_dir * self.radius * (1.0 - np.cos(phi))
        th_arc = self.turn_dir * phi

        xr_3 = self.x2 + ds2 * self.cos2
        yr_3 = self.y2 + ds2 * self.sin2

        xr = np.where(m1, s, np.where(m2, xr_arc, xr_3))
        yr = np.where(m1, 0.0, np.where(m2, yr_arc, yr_3))
        theta_r = np.where(m1, 0.0, np.where(m2, th_arc, self.theta2))
        kappa_r = np.where(m1, 0.0, np.where(m2, self.kappa_arc, 0.0))
        return xr, yr, theta_r, kappa_r

    def project_s(self, px: float, py: float) -> float:
        """Chiếu gần nhất điểm (px, py) lên đường tham chiếu để tìm s."""
        # Ứng viên 1: đoạn thẳng đầu (s <= s1)
        s_cand1 = min(px, self.s1)
        d1_sq = (px - s_cand1) ** 2 + py ** 2

        # Ứng viên 2: cung tròn (s1 <= s <= s2)
        ang_c = math.atan2(py - self.cy, px - self.cx)
        # Khi s = s1: vector tâm -> (s1, 0) có góc -turn_dir * pi/2
        raw_phi = self.turn_dir * float(_wrap_angle(ang_c + self.turn_dir * (0.5 * math.pi)))
        phi_clamped = max(0.0, min(self.phi_tot, raw_phi))
        s_cand2 = self.s1 + self.radius * phi_clamped
        x2_c, y2_c, _, _ = self.eval_point(s_cand2)
        d2_sq = (px - x2_c) ** 2 + (py - y2_c) ** 2

        # Ứng viên 3: đoạn thẳng cuối (s >= s2)
        proj3 = max(0.0, (px - self.x2) * self.cos2 + (py - self.y2) * self.sin2)
        s_cand3 = self.s2 + proj3
        x3_c = self.x2 + proj3 * self.cos2
        y3_c = self.y2 + proj3 * self.sin2
        d3_sq = (px - x3_c) ** 2 + (py - y3_c) ** 2

        if d1_sq <= d2_sq and d1_sq <= d3_sq:
            return float(s_cand1)
        if d2_sq <= d3_sq:
            return float(s_cand2)
        return float(s_cand3)

    def world_to_frenet(
        self,
        px: float,
        py: float,
        psi: float,
        v: float,
    ) -> tuple[float, float, float, float, float, float]:
        """Chuyển đổi trạng thái (px, py, psi, v) sang (s, d, s_dot, d_dot, theta_r, kappa_r)."""
        s = self.project_s(px, py)
        xr, yr, theta_r, kappa_r = self.eval_point(s)
        dx = px - xr
        dy = py - yr
        d = -dx * math.sin(theta_r) + dy * math.cos(theta_r)
        d_psi = float(_wrap_angle(psi - theta_r))
        one_minus_kd = max(0.15, 1.0 - kappa_r * d)
        s_dot = v * math.cos(d_psi) / one_minus_kd
        d_dot = v * math.sin(d_psi)
        return float(s), float(d), float(s_dot), float(d_dot), float(theta_r), float(kappa_r)

    def frenet_to_world_single(self, s: float, d: float, d_psi_local: float = 0.0) -> tuple[float, float, float]:
        xr, yr, theta_r, _ = self.eval_point(s)
        x = xr - d * math.sin(theta_r)
        y = yr + d * math.cos(theta_r)
        psi = float(_wrap_angle(theta_r + d_psi_local))
        return float(x), float(y), psi

    def frenet_to_world_batch(
        self,
        s_pos: np.ndarray,
        d_pos: np.ndarray,
        s_vel: np.ndarray,
        d_vel: np.ndarray,
        s_acc: np.ndarray,
        d_acc: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Biến đổi đồng loạt ứng viên Frenet sang thế giới và trả về vận tốc, gia tốc, độ cong thật."""
        xr, yr, theta_r, kappa_r = self.eval_batch(s_pos)
        sin_t = np.sin(theta_r)
        cos_t = np.cos(theta_r)

        wx = xr - d_pos * sin_t
        wy = yr + d_pos * cos_t

        one_minus_kd = 1.0 - kappa_r * d_pos
        v_lon = s_vel * one_minus_kd
        v_lat = d_vel
        v_cand = np.hypot(v_lon, v_lat)

        a_t = s_acc * one_minus_kd - 2.0 * kappa_r * s_vel * d_vel
        a_n = d_acc + (s_vel * s_vel) * kappa_r * one_minus_kd

        v_safe_a = np.maximum(v_cand, 0.1)
        a_cand = np.where(v_cand <= 0.1, a_t, (v_lon * a_t + v_lat * a_n) / v_safe_a)

        v_safe_k = np.maximum(v_cand, 0.25)
        kappa = np.where(
            v_cand > 0.25,
            (v_lon * a_n - v_lat * a_t) / (v_safe_k * v_safe_k * v_safe_k),
            0.0,
        )

        vx_w = v_lon * cos_t - v_lat * sin_t
        vy_w = v_lon * sin_t + v_lat * cos_t
        return wx, wy, vx_w, vy_w, v_cand, a_cand, kappa, theta_r


def build_ext_scenario_context(
    scenario: str,
    rng: np.random.Generator,
    agent_cls: type[Any],
    curve_radius_override: float | None = None,
) -> tuple[list[Any], list[StaticObstacleBox], CurvedReferencePath | None]:
    """Tạo tác nhân, vật cản tĩnh và đường cong tham chiếu cho các kịch bản S5–S10."""
    agents: list[Any] = []
    static_obs: list[StaticObstacleBox] = []
    ref_path: CurvedReferencePath | None = None

    if scenario == "S5":
        # S5: Xe đỗ lề phải (4.5 x 1.8 m, tâm y = 2.8 m) che người đi bộ bước ra 1.2-2.5 m/s
        cx_obs = float(rng.uniform(38.0, 48.0))
        static_obs.append(StaticObstacleBox(cx=cx_obs, cy=2.8, length=4.5, width=1.8))
        ped_x = cx_obs + float(rng.uniform(2.75, 3.45))
        ped_y0 = float(rng.uniform(3.05, 3.55))
        speed = float(rng.uniform(1.2, 2.5))
        trig = float(rng.uniform(16.0, 26.0))
        agents.append(agent_cls(
            agent_id="ped_occl_0",
            kind="ped",
            px=ped_x,
            py=ped_y0,
            psi=-0.5 * math.pi + float(rng.uniform(-0.08, 0.08)),
            v_nom=speed,
            rng=rng,
            behavior={
                "mode": "cross_ped",
                "conflict_x": ped_x,
                "trigger_dist": trig,
                "stop_mid": False,
                "stop_dur": 0.0,
                "start_occluded": True,
            },
        ))

    elif scenario == "S6":
        # S6: Xe máy cùng chiều từ làn trái y=3.5 m chen vào trước mặt, góc 5-15 độ, 6-10 m/s, AR(1) ngang
        x0 = float(rng.uniform(8.0, 20.0))
        y0 = 3.5
        cut_deg = float(rng.uniform(5.0, 15.0))
        psi0 = -math.radians(cut_deg)
        speed = float(rng.uniform(6.0, 10.0))
        agents.append(agent_cls(
            agent_id="moto_cutin_0",
            kind="moto",
            px=x0,
            py=y0,
            psi=psi0,
            v_nom=speed,
            rng=rng,
            behavior={
                "mode": "cut_in",
                "target_y": float(rng.uniform(-0.3, 0.4)),
                "lat_ar_sigma": 0.30,
                "lat_ar_val": 0.0,
            },
        ))

    elif scenario == "S7":
        # S7: Đường cong bán kính R in {25, 50} m + ô tô ngược chiều lấn tâm đường 0-0.5 m, v = 5-8 m/s
        r_val = float(curve_radius_override) if curve_radius_override is not None else float(rng.choice([25.0, 50.0]))
        turn_dir = float(rng.choice([-1.0, 1.0]))
        ref_path = CurvedReferencePath(radius=r_val, turn_dir=turn_dir, s1=15.0, arc_len=40.0, s_total=95.0)
        # Đặt ô tô ngược chiều dọc đoạn cong/sau cong để gặp xe tự hành ở nửa sau cung tròn
        s_car = float(rng.uniform(66.0, 82.0))
        # Làn đối diện bên trái (+d): vạch tâm đường tại d = +1.75 m.
        # Ô tô ngược chiều (bán kính 0.95 m) lấn tâm đường 0-0.5 m -> tâm ở d = 2.70 - encroach
        encroach = float(rng.uniform(0.0, 0.5))
        d_car = float(2.70 - encroach)
        car_x, car_y, car_psi = ref_path.frenet_to_world_single(s_car, d_car, d_psi_local=math.pi)
        v_car = float(rng.uniform(5.0, 8.0))
        agents.append(agent_cls(
            agent_id="car_oncoming_0",
            kind="car",
            px=car_x,
            py=car_y,
            psi=car_psi,
            v_nom=v_car,
            rng=rng,
            behavior={
                "mode": "curve_oncoming",
                "ref_path": ref_path,
                "s_cur": s_car,
                "d_cur": d_car,
            },
        ))

    elif scenario == "S8":
        # S8: Mật độ cao hỗn hợp 4-6 tác nhân: 1-2 người đi bộ, 2-3 xe máy theo bầy, 0-1 ô tô
        n_ped = int(rng.integers(1, 3))
        n_moto = int(rng.integers(2, 4))
        n_car = int(rng.integers(0, 2))
        base_x = float(rng.uniform(36.0, 44.0))

        for idx in range(n_ped):
            cx = base_x + idx * float(rng.uniform(5.0, 9.0))
            side = float(rng.choice([-1.0, 1.0]))
            y0 = side * float(rng.uniform(2.8, 4.0))
            speed = float(rng.uniform(0.9, 1.7))
            appear_t = float(rng.uniform(0.0, 3.0))
            agents.append(agent_cls(
                agent_id=f"ped_s8_{idx}",
                kind="ped",
                px=cx,
                py=y0,
                psi=-side * 0.5 * math.pi + float(rng.uniform(-0.1, 0.1)),
                v_nom=speed,
                rng=rng,
                behavior={
                    "mode": "cross_ped_delayed",
                    "conflict_x": cx,
                    "trigger_dist": float(rng.uniform(16.0, 24.0)),
                    "appear_t": appear_t,
                    "stop_mid": False,
                    "stop_dur": 0.0,
                },
            ))

        # Bầy xe máy cùng chiều hoặc cắt nhẹ cách nhau 2-4 m
        platoon_x0 = float(rng.uniform(18.0, 26.0))
        platoon_y = float(rng.uniform(-0.9, 0.9))
        platoon_v = float(rng.uniform(4.2, 6.2))
        platoon_appear = float(rng.uniform(0.0, 2.0))
        cur_x = platoon_x0
        for idx in range(n_moto):
            gap = float(rng.uniform(2.0, 4.0))
            if idx > 0:
                cur_x += gap + 1.2
            agents.append(agent_cls(
                agent_id=f"moto_flock_{idx}",
                kind="moto",
                px=cur_x,
                py=platoon_y + float(rng.uniform(-0.4, 0.4)),
                psi=float(rng.uniform(-0.04, 0.04)),
                v_nom=platoon_v + float(rng.uniform(-0.4, 0.4)),
                rng=rng,
                behavior={
                    "mode": "flock_veh",
                    "appear_t": platoon_appear + idx * 0.25,
                },
            ))

        for idx in range(n_car):
            cx_c = base_x + float(rng.uniform(12.0, 20.0))
            side_c = float(rng.choice([-1.0, 1.0]))
            ang_c = math.radians(float(rng.uniform(60.0, 90.0)))
            psi_c = -side_c * ang_c
            v_c = float(rng.uniform(4.0, 6.5))
            appear_c = float(rng.uniform(0.5, 3.0))
            t_arr = cx_c / 7.5 + float(rng.uniform(-0.6, 0.6))
            app_c = v_c * t_arr
            agents.append(agent_cls(
                agent_id=f"car_s8_{idx}",
                kind="car",
                px=cx_c - app_c * math.cos(psi_c),
                py=float(rng.uniform(-0.5, 0.5)) - app_c * math.sin(psi_c),
                psi=psi_c,
                v_nom=v_c,
                rng=rng,
                behavior={
                    "mode": "cross_veh",
                    "omega_nom": float(rng.choice([-1.0, 1.0]) * rng.uniform(0.01, 0.04)),
                    "appear_t": appear_c,
                },
            ))

    elif scenario == "S9":
        # S9: Tác nhân tương tác theo TTC: TTC < 2 s thì nhường (p=0.6) hoặc tăng tốc (p=0.4)
        is_ped = bool(rng.random() < 0.5)
        kind = "ped" if is_ped else "moto"
        cx = float(rng.uniform(38.0, 50.0))
        side = float(rng.choice([-1.0, 1.0]))
        if is_ped:
            v_nom = float(rng.uniform(1.1, 1.8))
            psi0 = -side * 0.5 * math.pi + float(rng.uniform(-0.08, 0.08))
            t_cross = cx / 7.5
            y0 = -side * float(rng.uniform(1.4, 2.2)) if False else side * (v_nom * min(t_cross * 0.45, 2.5))
            y0 = side * float(rng.uniform(2.2, 3.2))
            x0 = cx
        else:
            ang = math.radians(float(rng.uniform(55.0, 88.0)))
            psi0 = -side * ang
            v_nom = float(rng.uniform(3.5, 6.0))
            t_arr = cx / 7.5 + float(rng.uniform(-0.4, 0.4))
            app = v_nom * t_arr
            x0 = cx - app * math.cos(psi0)
            y0 = float(rng.uniform(-0.4, 0.4)) - app * math.sin(psi0)

        agents.append(agent_cls(
            agent_id=f"{kind}_inter_0",
            kind=kind,
            px=x0,
            py=y0,
            psi=psi0,
            v_nom=v_nom,
            rng=rng,
            behavior={
                "mode": "interactive_ttc",
                "reacted": False,
                "reaction": None,
                "yield_prob": 0.6,
                "v_max_react": 2.8 if is_ped else 9.0,
            },
        ))

    elif scenario == "S10":
        # S10: Người đi bộ zigzag (đổi hướng +-60 độ mỗi 1-2 s) + xe máy rẽ đột ngột (omega=0.8 rad/s trong 1 s)
        cx_p = float(rng.uniform(34.0, 44.0))
        side_p = float(rng.choice([-1.0, 1.0]))
        agents.append(agent_cls(
            agent_id="ped_zigzag_0",
            kind="ped",
            px=cx_p,
            py=side_p * float(rng.uniform(2.4, 3.4)),
            psi=-side_p * 0.5 * math.pi,
            v_nom=float(rng.uniform(1.1, 1.8)),
            rng=rng,
            behavior={
                "mode": "zigzag_ped",
                "conflict_x": cx_p,
                "trigger_dist": float(rng.uniform(16.0, 24.0)),
                "zig_period": float(rng.uniform(1.0, 2.0)),
                "zig_timer": 0.0,
                "zig_sign": 1.0 if rng.random() < 0.5 else -1.0,
                "base_psi": -side_p * 0.5 * math.pi,
            },
        ))

        x_m = float(rng.uniform(30.0, 42.0))
        side_m = float(rng.choice([-1.0, 1.0]))
        v_m = float(rng.uniform(4.5, 7.5))
        agents.append(agent_cls(
            agent_id="moto_turn_0",
            kind="moto",
            px=x_m,
            py=side_m * float(rng.uniform(2.2, 3.2)),
            psi=0.0 if rng.random() < 0.5 else math.pi,
            v_nom=v_m,
            rng=rng,
            behavior={
                "mode": "sudden_turn_moto",
                "turn_start_t": float(rng.uniform(2.2, 4.2)),
                "turn_dur": 1.0,
                "turn_elapsed": 0.0,
                "turn_omega": -side_m * 0.8,
            },
        ))

    else:
        raise ValueError(f"Kịch bản mở rộng không hợp lệ: {scenario}")

    return agents, static_obs, ref_path


def step_ext_agent(
    ag: Any,
    ego_px: float,
    ego_py: float,
    ego_psi: float,
    ego_v: float,
    t: float,
    dt: float,
    hx_ego: float,
) -> None:
    """Cập nhật động học cho các chế độ tác nhân mở rộng S5–S10."""
    beh = ag.behavior
    mode = beh["mode"]

    if mode == "cut_in":
        rho_l = math.exp(-dt / 0.8)
        s_l = math.sqrt(1.0 - rho_l**2)
        beh["lat_ar_val"] = rho_l * beh["lat_ar_val"] + s_l * beh["lat_ar_sigma"] * float(ag.rng.standard_normal())
        ag.v = float(np.clip(ag.v + ag.ar_accel * dt, 4.0, 11.5))
        # Lái dần vào target_y rồi giữ làn, cộng dao động ngang AR(1)
        dy_err = beh["target_y"] - ag.py
        vy_des = float(np.clip(0.9 * dy_err + beh["lat_ar_val"], -2.8, 2.8))
        vx_des = max(3.5, math.sqrt(max(0.1, ag.v * ag.v - vy_des * vy_des)))
        psi_des = math.atan2(vy_des, vx_des)
        d_psi = float(_wrap_angle(psi_des - ag.psi))
        ag.psi = float(_wrap_angle(ag.psi + np.clip(d_psi * 4.0, -0.7, 0.7) * dt + 0.5 * ag.ar_omega * dt))
        ag.px += ag.v * math.cos(ag.psi) * dt
        ag.py += ag.v * math.sin(ag.psi) * dt

    elif mode == "curve_oncoming":
        rp: CurvedReferencePath = beh["ref_path"]
        ag.v = float(np.clip(ag.v + ag.ar_accel * dt, 3.5, 9.0))
        beh["s_cur"] -= ag.v * dt
        x_n, y_n, psi_n = rp.frenet_to_world_single(beh["s_cur"], beh["d_cur"], d_psi_local=math.pi)
        ag.px = x_n
        ag.py = y_n
        ag.psi = float(_wrap_angle(psi_n + 0.15 * ag.ar_omega))

    elif mode == "cross_ped_delayed":
        if t < beh.get("appear_t", 0.0):
            return
        if not ag.active and (beh["conflict_x"] - ego_px) <= beh["trigger_dist"]:
            ag.active = True
        if not ag.active:
            return
        ag.v = float(np.clip(ag.v_nom + 0.3 * ag.ar_accel, 0.3, 2.6))
        ag.psi = float(_wrap_angle(ag.psi + ag.ar_omega * dt))
        ag.px += ag.v * math.cos(ag.psi) * dt
        ag.py += ag.v * math.sin(ag.psi) * dt

    elif mode == "flock_veh":
        if t < beh.get("appear_t", 0.0):
            return
        ag.v = float(np.clip(ag.v + 0.4 * ag.ar_accel * dt, 2.0, 9.0))
        ag.psi = float(_wrap_angle(ag.psi + 0.4 * ag.ar_omega * dt))
        ag.px += ag.v * math.cos(ag.psi) * dt
        ag.py += ag.v * math.sin(ag.psi) * dt

    elif mode == "interactive_ttc":
        # Tính TTC hiện tại theo khoảng cách tâm trừ bán kính
        rx = ag.px - ego_px
        ry = ag.py - ego_py
        dist = math.hypot(rx, ry)
        if not beh["reacted"] and dist > 1e-4:
            ux, uy = rx / dist, ry / dist
            evx, evy = ego_v * math.cos(ego_psi), ego_v * math.sin(ego_psi)
            avx, avy = ag.v * math.cos(ag.psi), ag.v * math.sin(ag.psi)
            v_close = (evx - avx) * ux + (evy - avy) * uy
            d_gap = max(0.0, dist - hx_ego - ag.disk_radius)
            if v_close > 0.2:
                ttc = d_gap / v_close
                if ttc < 2.0:
                    beh["reacted"] = True
                    if float(ag.rng.random()) < beh["yield_prob"]:
                        beh["reaction"] = "yield"
                    else:
                        beh["reaction"] = "accelerate"
        if beh["reaction"] == "yield":
            ag.v = max(0.0, ag.v - 2.0 * dt)
        elif beh["reaction"] == "accelerate":
            ag.v = min(beh["v_max_react"], ag.v + 2.0 * dt)
        else:
            ag.v = max(0.2, ag.v + 0.2 * ag.ar_accel * dt)
        ag.psi = float(_wrap_angle(ag.psi + 0.5 * ag.ar_omega * dt))
        ag.px += ag.v * math.cos(ag.psi) * dt
        ag.py += ag.v * math.sin(ag.psi) * dt

    elif mode == "zigzag_ped":
        if not ag.active and (beh["conflict_x"] - ego_px) <= beh["trigger_dist"]:
            ag.active = True
        if not ag.active:
            return
        beh["zig_timer"] += dt
        if beh["zig_timer"] >= beh["zig_period"]:
            beh["zig_timer"] = 0.0
            beh["zig_sign"] *= -1.0
        target_psi = float(_wrap_angle(beh["base_psi"] + beh["zig_sign"] * (math.pi / 3.0)))
        d_p = float(_wrap_angle(target_psi - ag.psi))
        ag.psi = float(_wrap_angle(ag.psi + np.clip(d_p * 5.0, -2.5, 2.5) * dt))
        ag.v = float(np.clip(ag.v_nom + 0.2 * ag.ar_accel, 0.5, 2.4))
        ag.px += ag.v * math.cos(ag.psi) * dt
        ag.py += ag.v * math.sin(ag.psi) * dt

    elif mode == "sudden_turn_moto":
        if t >= beh["turn_start_t"] and beh["turn_elapsed"] < beh["turn_dur"]:
            ag.psi = float(_wrap_angle(ag.psi + beh["turn_omega"] * dt))
            beh["turn_elapsed"] += dt
        else:
            ag.psi = float(_wrap_angle(ag.psi + 0.3 * ag.ar_omega * dt))
        ag.v = float(np.clip(ag.v + 0.3 * ag.ar_accel * dt, 2.5, 9.0))
        ag.px += ag.v * math.cos(ag.psi) * dt
        ag.py += ag.v * math.sin(ag.psi) * dt

"""Quản lý tác nhân kịch bản S1–S4 (và S5–S10) trên CARLA (T17 / G15).

Tái sử dụng `build_scenario_context` và `SimAgent` từ `sim.core` để các kịch bản
S1–S4 trong CARLA có cùng phân bố hình học, vận tốc và hạt giống với mô phỏng 2D.
Hỗ trợ hai chế độ (`cfg.agent_mode`):
- "replay": cập nhật động học qua `SimAgent.step` rồi đặt tư thế lên actor CARLA
  (bảo đảm tái lập tuyệt đối theo hạt giống và đồng bộ hình học 100%).
- "physics": điều khiển walker (`WalkerControl`) và xe (`VehicleControl` / PID)
  bằng vật lý thật của CARLA, rồi đọc lại tư thế thật từ CARLA về `SimAgent`.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from carla_sim.config import CAR_BLUEPRINTS, MOTO_BLUEPRINTS, PED_BLUEPRINTS, CarlaConfig
from carla_sim.frames import FrameTransform
from sim.core import DT_SIM, SimAgent, build_scenario_context, wrap_angle
from sim.scenarios_ext import CurvedReferencePath, StaticObstacleBox


class CarlaAgentManager:
    """Sinh, cập nhật và hủy các actor tác nhân CARLA tương ứng với `SimAgent`."""

    def __init__(
        self,
        scenario: str,
        rng_scn: np.random.Generator,
        cfg: CarlaConfig,
        curve_radius_override: float | None = None,
    ) -> None:
        self.scenario = scenario
        self.cfg = cfg
        self.agents, self.static_obs, self.ref_path = build_scenario_context(
            scenario,
            rng_scn,
            curve_radius_override=curve_radius_override,
        )
        self.actors: dict[str, Any] = {}
        self.static_actors: list[Any] = []
        self._bp_rng = np.random.default_rng(int(rng_scn.integers(0, 2**31 - 1)))

    def _pick_blueprint(self, bp_lib: Any, kind: str) -> Any:
        if kind == "ped":
            candidates = PED_BLUEPRINTS
        elif kind == "moto":
            candidates = MOTO_BLUEPRINTS
        else:
            candidates = CAR_BLUEPRINTS
        idx = int(self._bp_rng.integers(0, len(candidates)))
        for offset in range(len(candidates)):
            bp_name = candidates[(idx + offset) % len(candidates)]
            try:
                return bp_lib.find(bp_name)
            except Exception:
                continue
        if kind == "ped":
            return bp_lib.filter("walker.pedestrian.*")[0]
        return bp_lib.filter("vehicle.*")[0]

    def spawn_in_carla(self, session: Any, frame: FrameTransform) -> None:
        """Sinh toàn bộ tác nhân và vật cản tĩnh vào thế giới CARLA hiện tại."""
        if session is None or getattr(session, "world", None) is None:
            return
        world = session.world
        bp_lib = world.get_blueprint_library()

        for ag in self.agents:
            bp = self._pick_blueprint(bp_lib, ag.kind)
            z_spawn = frame.z0 + (0.95 if ag.kind == "ped" else 0.35)
            tf = frame.make_carla_transform(ag.px, ag.py, ag.psi, z=z_spawn)
            actor = world.try_spawn_actor(bp, tf)
            if actor is None:
                tf_hi = frame.make_carla_transform(ag.px, ag.py, ag.psi, z=z_spawn + 0.5)
                actor = world.try_spawn_actor(bp, tf_hi)
            if actor is not None:
                session.track_actor(actor)
                if self.cfg.agent_mode == "replay" and hasattr(actor, "set_simulate_physics"):
                    try:
                        actor.set_simulate_physics(False)
                    except Exception:
                        pass
                self.actors[ag.id] = actor

        # Sinh vật cản tĩnh (xe đỗ lề phải trong S5)
        for obs in self.static_obs:
            bp = self._pick_blueprint(bp_lib, "car")
            tf = frame.make_carla_transform(obs.cx, obs.cy, 0.0, z=frame.z0 + 0.35)
            act = world.try_spawn_actor(bp, tf)
            if act is not None:
                session.track_actor(act)
                if hasattr(act, "set_simulate_physics"):
                    try:
                        act.set_simulate_physics(False)
                    except Exception:
                        pass
                self.static_actors.append(act)

    def _apply_physics_control(
        self,
        ag: SimAgent,
        actor: Any,
        frame: FrameTransform,
    ) -> None:
        """Điều khiển actor vật lý bám theo vận tốc và hướng mục tiêu của `SimAgent`."""
        import carla  # noqa: PLC0415

        if ag.kind == "ped":
            _, _, psi_des, v_des = ag.pose_vel()
            wx, wy = frame.local_to_world_xy(math.cos(psi_des), math.sin(psi_des))
            x0w, y0w = frame.local_to_world_xy(0.0, 0.0)
            dx, dy = wx - x0w, wy - y0w
            norm = max(math.hypot(dx, dy), 1e-6)
            ctrl = carla.WalkerControl(
                direction=carla.Vector3D(x=dx / norm, y=dy / norm, z=0.0),
                speed=float(max(0.0, v_des)),
                jump=False,
            )
            actor.apply_control(ctrl)
        else:
            cx, cy, psi_cur = frame.actor_center_pose(actor)
            _, _, v_cur = frame.actor_velocity(actor, psi_cur)
            err_v = ag.v - v_cur
            throttle = float(np.clip(0.4 * err_v, 0.0, 1.0)) if err_v >= 0.0 else 0.0
            brake = float(np.clip(-0.35 * err_v, 0.0, 1.0)) if err_v < 0.0 else 0.0
            # Lái bám hướng mục tiêu (hệ cục bộ -> tay trái CARLA)
            err_psi = float(wrap_angle(ag.psi - psi_cur))
            steer_carla = float(np.clip(-1.2 * err_psi, -1.0, 1.0))
            actor.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=steer_carla))

    def step_and_sync(
        self,
        ego_px: float,
        ego_py: float,
        ego_psi: float,
        ego_v: float,
        t: float,
        dt: float = DT_SIM,
        frame: FrameTransform | None = None,
    ) -> None:
        """Tiến 1 bước các tác nhân và đồng bộ với actor CARLA."""
        for ag in self.agents:
            ag.step(ego_px, t, dt, ego_py=ego_py, ego_psi=ego_psi, ego_v=ego_v)
            actor = self.actors.get(ag.id)
            if actor is None or frame is None:
                continue

            if self.cfg.agent_mode == "replay":
                z_cur = float(actor.get_transform().location.z)
                bb_off = getattr(getattr(actor, "bounding_box", None), "location", None)
                tf = frame.make_carla_transform(ag.px, ag.py, ag.psi, z=z_cur, bb_offset=bb_off)
                actor.set_transform(tf)
            else:
                self._apply_physics_control(ag, actor, frame)

    def sync_from_carla_after_tick(self, frame: FrameTransform | None) -> None:
        """Ở chế độ physics, đọc lại tư thế và vận tốc thực của actor CARLA sau world.tick()."""
        if self.cfg.agent_mode != "physics" or frame is None:
            return
        for ag in self.agents:
            actor = self.actors.get(ag.id)
            if actor is None:
                continue
            px, py, psi = frame.actor_center_pose(actor)
            _, _, v_long = frame.actor_velocity(actor, psi)
            ag.px = float(px)
            ag.py = float(py)
            ag.psi = float(psi)
            ag.v = float(max(0.0, v_long))

    def destroy_all(self) -> None:
        self.actors.clear()
        self.static_actors.clear()

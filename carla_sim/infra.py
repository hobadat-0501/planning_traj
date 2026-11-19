"""Hạ tầng CARLA (T15 / G13): kiểm tra môi trường, chế độ đồng bộ, chọn đoạn thẳng, sinh xe,
chỉnh tham số xe và đo trễ lệnh thật.

API dùng bởi các module khác:
- `check_carla_env()`
- `CarlaSession(cfg)` (context manager): `.world`, `.tm`, `.tick()`, `.track_actor()`,
  `.destroy_tracked_actors()`, `.set_seed()`, `.close()`
- `find_straight_spawn(world, cfg) -> (carla.Transform, FrameTransform)`
- `spawn_ego(session, spawn_tf, cfg, condition="D0") -> (actor, geometry_info)`
- `measure_actuator_latency(session, cfg, n_trials=5)`
"""

from __future__ import annotations

import math
import platform
import subprocess
import time
from typing import Any

from carla_sim.config import CarlaConfig
from carla_sim.frames import FrameTransform


def _carla():
    try:
        import carla  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - phụ thuộc môi trường
        raise RuntimeError(
            "Chưa cài CARLA Python API. Cài đúng phiên bản với server (vd. `pip install carla==0.9.15`); "
            "CARLA 0.9.15 hỗ trợ Python 3.7–3.10 nên cần môi trường ảo riêng ngoài Python 3.13."
        ) from exc
    return carla


# ==============================================================================
# Kiểm tra môi trường (T15 mục 1)
# ==============================================================================

def check_carla_env(cfg: CarlaConfig | None = None, connect: bool = False) -> dict[str, Any]:
    """Báo phiên bản Python, client API, GPU; nếu `connect=True` thì hỏi thêm server."""
    cfg = cfg or CarlaConfig()
    info: dict[str, Any] = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
    try:
        carla = _carla()
        info["carla_api_installed"] = True
        info["client_api_file"] = getattr(carla, "__file__", None)
    except RuntimeError as exc:
        info["carla_api_installed"] = False
        info["carla_api_error"] = str(exc)
        carla = None

    if connect and carla is not None:
        try:
            client = carla.Client(cfg.host, cfg.port)
            client.set_timeout(cfg.timeout_s)
            info["client_version"] = client.get_client_version()
            info["server_version"] = client.get_server_version()
            info["version_match"] = info["client_version"] == info["server_version"]
            info["maps"] = [m.split("/")[-1] for m in client.get_available_maps()]
        except Exception as exc:  # noqa: BLE001
            info["server_error"] = f"{type(exc).__name__}: {exc}"

    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        info["gpu"] = out.stdout.strip() or out.stderr.strip() or "không tìm thấy"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        info["gpu"] = "không có nvidia-smi"
    return info


# ==============================================================================
# Phiên làm việc đồng bộ (T15 mục 2)
# ==============================================================================

class CarlaSession:
    """Client/world ở chế độ đồng bộ (dt = cfg.dt_sim), có Traffic Manager đồng bộ.

    Khi thoát: hủy mọi actor đã `track_actor`, trả lại cài đặt world ban đầu.
    """

    is_fake = False

    def __init__(self, cfg: CarlaConfig) -> None:
        self.cfg = cfg
        self.client: Any = None
        self.world: Any = None
        self.tm: Any = None
        self.frame: int = 0
        self._orig_settings: Any = None
        self._actors: list[Any] = []

    def __enter__(self) -> "CarlaSession":
        carla = _carla()
        self.client = carla.Client(self.cfg.host, self.cfg.port)
        self.client.set_timeout(self.cfg.timeout_s)
        world = self.client.get_world()
        cur_map = world.get_map().name.split("/")[-1]
        if self.cfg.reload_world or cur_map != self.cfg.town:
            world = self.client.load_world(self.cfg.town)
        self.world = world
        self._orig_settings = world.get_settings()

        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = self.cfg.dt_sim
        settings.no_rendering_mode = self.cfg.no_rendering
        settings.substepping = True
        settings.max_substep_delta_time = self.cfg.max_substep_delta
        settings.max_substeps = self.cfg.max_substeps
        world.apply_settings(settings)

        self.tm = self.client.get_trafficmanager(self.cfg.tm_port)
        self.tm.set_synchronous_mode(True)
        self.tm.set_hybrid_physics_mode(False)
        self.frame = world.tick()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        try:
            self.destroy_tracked_actors()
        finally:
            if self.world is not None and self._orig_settings is not None:
                if self.tm is not None:
                    self.tm.set_synchronous_mode(False)
                self.world.apply_settings(self._orig_settings)
                self._orig_settings = None

    def tick(self) -> int:
        self.frame = self.world.tick()
        return self.frame

    def track_actor(self, actor: Any) -> Any:
        if actor is not None:
            self._actors.append(actor)
        return actor

    def destroy_tracked_actors(self) -> None:
        if not self._actors or self.client is None:
            self._actors = []
            return
        carla = _carla()
        for a in self._actors:
            tid = getattr(a, "type_id", "")
            if tid.startswith("sensor."):
                try:
                    a.stop()
                except RuntimeError:
                    pass
            elif tid.startswith("controller.ai.walker"):
                try:
                    a.stop()
                except RuntimeError:
                    pass
        # do_tick=False rồi tự tick một lần (tránh tick kép ở chế độ đồng bộ)
        self.client.apply_batch_sync([carla.command.DestroyActor(a.id) for a in reversed(self._actors)], False)
        self._actors = []
        self.tick()

    def set_seed(self, seed: int) -> None:
        """Gắn hạt giống cho Traffic Manager và người đi bộ (tăng tính tái lập)."""
        s = int(seed) % (2**31 - 1)
        self.tm.set_random_device_seed(s)
        if hasattr(self.world, "set_pedestrians_seed"):
            self.world.set_pedestrians_seed(s)


# ==============================================================================
# Chọn đoạn đường thẳng
# ==============================================================================

_SPAWN_CACHE: dict[tuple[str, int | None, float], Any] = {}


def find_straight_spawn(world: Any, cfg: CarlaConfig) -> tuple[Any, FrameTransform]:
    """Chọn điểm xuất phát có >= cfg.straight_len_m đường thẳng phía trước (không qua giao lộ).

    Kết quả được cache theo (bản đồ, spawn_index, chiều dài) để mọi lượt dùng cùng một đoạn đường.
    Trả về (transform của waypoint tâm làn, FrameTransform gốc tại đó).
    """
    carla_map = world.get_map()
    key = (carla_map.name, cfg.spawn_index, float(cfg.straight_len_m))
    if key in _SPAWN_CACHE:
        tf = _SPAWN_CACHE[key]
        return tf, FrameTransform.from_carla_transform(tf)

    spawns = carla_map.get_spawn_points()
    candidates = [spawns[cfg.spawn_index]] if cfg.spawn_index is not None else spawns
    for sp in candidates:
        wp = carla_map.get_waypoint(sp.location, project_to_road=True)
        if wp is None or wp.is_junction:
            continue
        yaw0 = wp.transform.rotation.yaw
        ok, dist, cur = True, 0.0, wp
        while dist < cfg.straight_len_m:
            nxt = cur.next(2.0)
            if not nxt:
                ok = False
                break
            cur = nxt[0]
            dist += 2.0
            dyaw = abs((cur.transform.rotation.yaw - yaw0 + 180.0) % 360.0 - 180.0)
            if dyaw > cfg.straight_yaw_tol_deg or cur.is_junction:
                ok = False
                break
        if ok:
            _SPAWN_CACHE[key] = wp.transform
            return wp.transform, FrameTransform.from_carla_transform(wp.transform)
    raise RuntimeError(
        f"Không tìm được đoạn thẳng >= {cfg.straight_len_m} m trên {cfg.town}; hãy đặt spawn_index thủ công."
    )


# ==============================================================================
# Sinh xe và chỉnh tham số (T15 mục 3)
# ==============================================================================

def spawn_ego(session: CarlaSession, spawn_tf: Any, cfg: CarlaConfig, condition: str = "D0") -> tuple[Any, dict[str, Any]]:
    """Sinh Model 3 tại điểm xuất phát, đặt góc lái tối đa; D9 giảm hệ số bám lốp."""
    carla = _carla()
    bp = session.world.get_blueprint_library().find(cfg.ego_blueprint)
    if bp.has_attribute("role_name"):
        bp.set_attribute("role_name", "ego")
    tf = carla.Transform(
        carla.Location(spawn_tf.location.x, spawn_tf.location.y, spawn_tf.location.z + 0.3),
        spawn_tf.rotation,
    )
    ego = session.world.try_spawn_actor(bp, tf)
    if ego is None:
        raise RuntimeError("Không sinh được xe tự hành tại điểm đã chọn (bị chiếm chỗ?).")
    session.track_actor(ego)
    friction = cfg.d9_tire_friction_scale if condition == "D9" else 1.0
    tune_vehicle_physics(ego, cfg, tire_friction_scale=friction)
    session.tick()  # cần 1 tick để physics control có hiệu lực và vị trí bánh được cập nhật
    info = measure_vehicle_geometry(ego)
    info["wheelbase_target_m"] = cfg.wheelbase_target
    info["wheelbase_error_m"] = info["wheelbase_m"] - cfg.wheelbase_target
    return ego, info


def tune_vehicle_physics(vehicle: Any, cfg: CarlaConfig, tire_friction_scale: float = 1.0) -> None:
    """Đặt góc lái tối đa bánh trước = DELTA_MAX và nhân hệ số bám lốp.

    Chiều dài cơ sở không chỉnh được qua API (do mô hình 3D); chỉ đo và báo lệch ở `spawn_ego`.
    V_MAX áp ở bộ điều khiển (`LongitudinalPID.v_max`).
    """
    pc = vehicle.get_physics_control()
    wheels = pc.wheels
    max_steer_deg = math.degrees(cfg.delta_max_rad)
    for i, w in enumerate(wheels):
        if i < 2:
            w.max_steer_angle = max_steer_deg
        w.tire_friction = w.tire_friction * tire_friction_scale
    pc.wheels = wheels
    vehicle.apply_physics_control(pc)


def measure_vehicle_geometry(vehicle: Any) -> dict[str, Any]:
    """Đo chiều dài cơ sở từ vị trí bánh (cm, hệ thế giới) và kích thước hộp bao."""
    pc = vehicle.get_physics_control()
    w = pc.wheels
    fx, fy = (w[0].position.x + w[1].position.x) / 2.0, (w[0].position.y + w[1].position.y) / 2.0
    rx, ry = (w[2].position.x + w[3].position.x) / 2.0, (w[2].position.y + w[3].position.y) / 2.0
    ext = vehicle.bounding_box.extent
    return {
        "wheelbase_m": math.hypot(fx - rx, fy - ry) / 100.0,
        "length_m": 2.0 * ext.x,
        "width_m": 2.0 * ext.y,
        "max_steer_deg_front": float(w[0].max_steer_angle),
        "tire_friction": float(w[0].tire_friction),
        "mass_kg": float(pc.mass),
    }


# ==============================================================================
# Đo trễ lệnh thật (T15 mục 4)
# ==============================================================================

def measure_actuator_latency(
    session: CarlaSession,
    cfg: CarlaConfig,
    n_trials: int = 5,
    v_cruise: float = 5.0,
    steer_step: float = 0.3,
    yaw_rate_thresh_deg: float = 2.0,
    decel_thresh: float = 0.5,
) -> dict[str, Any]:
    """Đo trễ từ lúc gửi bước lệnh tới khi phản hồi vượt ngưỡng, tính theo thời gian mô phỏng.

    - Lái: tốc độ quay thân xe |ω_z| (độ/s) >= ngưỡng.
    - Phanh: độ giảm tốc >= ngưỡng (m/s²).
    Kết quả so với BASE_DELAY = 50 ms và gợi ý `emulated_base_delay`.
    """
    carla = _carla()
    spawn_tf, _ = find_straight_spawn(session.world, cfg)
    dt = cfg.dt_sim
    steer_lat: list[float] = []
    brake_lat: list[float] = []

    for _ in range(n_trials):
        ego, _info = spawn_ego(session, spawn_tf, cfg)
        # Tăng tốc rồi giữ tốc độ ổn định
        for _k in range(120):
            v = ego.get_velocity().length()
            thr = max(0.0, min(1.0, 0.35 + 0.25 * (v_cruise - v)))
            ego.apply_control(carla.VehicleControl(throttle=thr, steer=0.0, brake=0.0))
            session.tick()

        # Bước lệnh lái
        for k in range(1, 60):
            ego.apply_control(carla.VehicleControl(throttle=0.3, steer=steer_step))
            session.tick()
            if abs(ego.get_angular_velocity().z) >= yaw_rate_thresh_deg:
                steer_lat.append(k * dt * 1000.0)
                break

        # Bước lệnh phanh
        v_prev = ego.get_velocity().length()
        for k in range(1, 60):
            ego.apply_control(carla.VehicleControl(throttle=0.0, steer=0.0, brake=1.0))
            session.tick()
            v_now = ego.get_velocity().length()
            if (v_prev - v_now) / dt >= decel_thresh:
                brake_lat.append(k * dt * 1000.0)
                break
            v_prev = v_now
        session.destroy_tracked_actors()

    def _mean(xs: list[float]) -> float | None:
        return float(sum(xs) / len(xs)) if xs else None

    steer_ms, brake_ms = _mean(steer_lat), _mean(brake_lat)
    both = [x for x in (steer_ms, brake_ms) if x is not None]
    overall = float(sum(both) / len(both)) if both else None
    return {
        "steer_latency_ms": steer_ms,
        "brake_latency_ms": brake_ms,
        "overall_latency_ms": overall,
        "steer_samples_ms": steer_lat,
        "brake_samples_ms": brake_lat,
        "trials": n_trials,
        "resolution_ms": dt * 1000.0,
        "base_delay_2d_ms": 50.0,
        "suggested_emulated_base_delay_s": max(0.0, 0.05 - (overall or 0.0) / 1000.0),
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

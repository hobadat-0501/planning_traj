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
        self.ego: Any = None              # Xe tự hành hiện tại (đặt bởi spawn_ego), dùng cho hiển thị
        self._last_wall = time.perf_counter()
        self._n_ticks = 0
        self._trail_prev: Any = None
        self._trail_ego_id: int | None = None
        self.trail_life_s = 17.0          # > T_MAX để vết đường còn tới hết lượt
        self._hidden_env_ids: list[int] = []   # Vật thể môi trường đã ẩn (khôi phục khi đóng)
        self._cleared_key: Any = None

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
            if self.world is not None and self._hidden_env_ids:
                try:
                    self.world.enable_environment_objects(set(self._hidden_env_ids), True)
                except Exception:  # noqa: BLE001
                    pass
                self._hidden_env_ids = []
                self._cleared_key = None
            if self.world is not None and self._orig_settings is not None:
                if self.tm is not None:
                    self.tm.set_synchronous_mode(False)
                self.world.apply_settings(self._orig_settings)
                self._orig_settings = None

    def tick(self) -> int:
        cfg = self.cfg
        if cfg.realtime:
            wait = cfg.dt_sim - (time.perf_counter() - self._last_wall)
            if wait > 0.0:
                time.sleep(wait)
        self.frame = self.world.tick()
        self._last_wall = time.perf_counter()
        self._n_ticks += 1
        if self.ego is not None and (cfg.camera != "none" or cfg.debug_draw or cfg.status_every_s > 0.0):
            try:
                self._display_hooks()
            except RuntimeError:  # actor vừa bị hủy
                self.ego = None
        return self.frame

    def _display_hooks(self) -> None:
        """Camera bám xe, khung đánh dấu tác nhân, dòng trạng thái (chỉ phục vụ hiển thị)."""
        carla = _carla()
        cfg, ego = self.cfg, self.ego
        tf = ego.get_transform()
        vel = ego.get_velocity()

        if cfg.camera != "none":
            # Lệnh đặt camera có hiệu lực ở tick sau -> đặt theo vị trí dự đoán để không bị giật
            loc = tf.location + carla.Location(x=vel.x * cfg.dt_sim, y=vel.y * cfg.dt_sim, z=0.0)
            yaw = math.radians(tf.rotation.yaw)
            fx, fy = math.cos(yaw), math.sin(yaw)
            if cfg.camera == "top":
                cam = carla.Transform(
                    carla.Location(x=loc.x + 15.0 * fx, y=loc.y + 15.0 * fy, z=loc.z + 35.0),
                    carla.Rotation(pitch=-80.0, yaw=tf.rotation.yaw),
                )
            else:
                cam = carla.Transform(
                    carla.Location(x=loc.x - 9.0 * fx, y=loc.y - 9.0 * fy, z=loc.z + 5.0),
                    carla.Rotation(pitch=-18.0, yaw=tf.rotation.yaw),
                )
            self.world.get_spectator().set_transform(cam)

        if cfg.debug_draw:
            dbg, life = self.world.debug, cfg.dt_sim * 1.5
            # Vết đường xe tự hành đã đi (giữ hết lượt)
            cur = tf.location + carla.Location(z=0.25)
            if self._trail_prev is not None and self._trail_ego_id == ego.id:
                dbg.draw_line(self._trail_prev, cur, thickness=0.08, color=carla.Color(0, 120, 255),
                              life_time=self.trail_life_s)
            self._trail_prev, self._trail_ego_id = cur, ego.id
            for a in self._actors:
                tid = getattr(a, "type_id", "")
                if not (tid.startswith("vehicle.") or tid.startswith("walker.")) or not a.is_alive:
                    continue
                atf = a.get_transform()
                bb = a.bounding_box
                box = carla.BoundingBox(atf.transform(bb.location), bb.extent)
                color = carla.Color(0, 200, 0) if a.id == ego.id else carla.Color(230, 0, 0)
                dbg.draw_box(box, atf.rotation, thickness=0.12, color=color, life_time=life)

        n_status = int(round(cfg.status_every_s / cfg.dt_sim)) if cfg.status_every_s > 0.0 else 0
        if n_status > 0 and self._n_ticks % n_status == 0:
            c = ego.get_control()
            print(
                f"  frame={self.frame} v={vel.length():5.2f} m/s thr={c.throttle:.2f} brk={c.brake:.2f} "
                f"steer={c.steer:+.2f} gear={c.gear}",
                flush=True,
            )

    def draw_plan(self, frame: FrameTransform, plan: Any, pred_agents: list[dict[str, Any]] | None = None) -> None:
        """Vẽ quỹ đạo kế hoạch 3 s (vàng; đỏ nếu dừng dự phòng) kèm mũi tên hướng ở cuối,
        và quỹ đạo dự báo của tác nhân (cam). Tồn tại tới chu kỳ lập kế hoạch kế tiếp."""
        if not self.cfg.debug_draw or self.ego is None:
            return
        carla = _carla()
        dbg = self.world.debug
        life = self.cfg.dt_plan * 1.2
        z = self.ego.get_location().z + 0.35

        def _loc(px: float, py: float) -> Any:
            X, Y = frame.local_to_world_xy(float(px), float(py))
            return carla.Location(x=X, y=Y, z=z)

        poses = plan.poses
        color = carla.Color(255, 40, 40) if plan.fallback else carla.Color(255, 210, 0)
        pts = [_loc(p[0], p[1]) for p in poses]
        for a, b in zip(pts[:-1], pts[1:]):
            dbg.draw_line(a, b, thickness=0.12, color=color, life_time=life)
        if len(pts) >= 2:
            dbg.draw_arrow(pts[-2], pts[-1], thickness=0.15, arrow_size=0.6, color=color, life_time=life)

        for ag in pred_agents or []:
            pc = ag.get("pred_centers")
            if pc is None or len(pc) < 2:
                continue
            apts = [_loc(c[0], c[1]) for c in pc]
            for a, b in zip(apts[:-1], apts[1:]):
                dbg.draw_line(a, b, thickness=0.08, color=carla.Color(255, 130, 0), life_time=life)
            dbg.draw_arrow(apts[-2], apts[-1], thickness=0.1, arrow_size=0.4,
                           color=carla.Color(255, 130, 0), life_time=life)

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
        self.ego = None
        self.tick()

    def set_seed(self, seed: int) -> None:
        """Gắn hạt giống cho Traffic Manager và người đi bộ (tăng tính tái lập)."""
        s = int(seed) % (2**31 - 1)
        self.tm.set_random_device_seed(s)
        if hasattr(self.world, "set_pedestrians_seed"):
            self.world.set_pedestrians_seed(s)

    def clear_corridor(self, frame: FrameTransform) -> int:
        """Ẩn (tắt hiển thị + va chạm) rào, hộ lan, tường, cột, biển, cây... trong hành lang thử nghiệm.

        Chỉ làm một lần cho mỗi gốc tọa độ; khôi phục khi `close()`. Trả về số vật thể đã ẩn.
        """
        cfg = self.cfg
        key = (round(frame.x0, 2), round(frame.y0, 2), round(frame.psi0, 4))
        if not cfg.clear_corridor or self._cleared_key == key:
            return 0
        carla = _carla()
        ids: set[int] = set()
        for name in _BLOCKER_LABELS:
            label = getattr(carla.CityObjectLabel, name, None)
            if label is None:
                continue
            for obj in self.world.get_environment_objects(label):
                if _bbox_in_corridor(obj.bounding_box, frame, cfg.corridor_half_width):
                    ids.add(int(obj.id))
        if ids:
            self.world.enable_environment_objects(ids, False)
            self._hidden_env_ids.extend(sorted(ids))
        self._cleared_key = key
        return len(ids)


# Nhãn vật thể môi trường cản đường tác nhân (ẩn trong hành lang); không ẩn Roads/Sidewalks/Buildings/Bridge
_BLOCKER_LABELS: tuple[str, ...] = (
    "Fences", "GuardRail", "Walls", "Poles", "TrafficSigns", "TrafficLight", "Vegetation", "Static", "Dynamic",
)
# Nhãn mặt đất dùng để đặt cao độ tác nhân
_GROUND_LABELS: frozenset[str] = frozenset({"Roads", "Sidewalks", "Ground", "Terrain", "RoadLines", "Bridge"})
CORRIDOR_X_RANGE: tuple[float, float] = (-10.0, 105.0)   # theo trục x cục bộ (đích GOAL_X = 75 m)


def _bbox_in_corridor(bb: Any, frame: FrameTransform, half_width: float) -> bool:
    """Hộp bao (hệ thế giới) có chạm hành lang x ∈ CORRIDOR_X_RANGE, |y| <= half_width (hệ cục bộ) không."""
    yaw = math.radians(float(bb.rotation.yaw))
    c, s = math.cos(yaw), math.sin(yaw)
    ex, ey = float(bb.extent.x), float(bb.extent.y)
    xs, ys = [], []
    for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        X = bb.location.x + sx * ex * c - sy * ey * s
        Y = bb.location.y + sx * ex * s + sy * ey * c
        px, py = frame.world_to_local_xy(X, Y)
        xs.append(px)
        ys.append(py)
    return (
        max(xs) >= CORRIDOR_X_RANGE[0] and min(xs) <= CORRIDOR_X_RANGE[1]
        and max(ys) >= -half_width and min(ys) <= half_width
    )


def ground_z(world: Any, X: float, Y: float, z_ref: float, span: float = 3.0) -> float | None:
    """Cao độ mặt đất (đường / vỉa hè / nền) tại (X, Y) thế giới, bỏ qua actor; None nếu không thấy."""
    carla = _carla()
    try:
        hits = world.cast_ray(carla.Location(x=X, y=Y, z=z_ref + span), carla.Location(x=X, y=Y, z=z_ref - span))
    except Exception:  # noqa: BLE001
        return None
    zs = [float(h.location.z) for h in hits if str(h.label).split(".")[-1] in _GROUND_LABELS]
    return max(zs) if zs else None   # mặt trên cùng (vd. vỉa hè cao hơn lòng đường)


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
    # Nhà cửa không ẩn được -> ưu tiên đoạn thẳng có ít nhà nhất trong hành lang (xét tối đa 80 đoạn)
    try:
        buildings = [o.bounding_box for o in world.get_environment_objects(_carla().CityObjectLabel.Buildings)]
    except Exception:  # noqa: BLE001
        buildings = []
    best: tuple[int, Any] | None = None
    n_ok = 0
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
        if not ok:
            continue
        fr = FrameTransform.from_carla_transform(wp.transform)
        n_bld = sum(_bbox_in_corridor(bb, fr, cfg.corridor_half_width) for bb in buildings)
        if best is None or n_bld < best[0]:
            best = (n_bld, wp.transform)
        n_ok += 1
        if n_bld == 0 or n_ok >= 80:
            break
    if best is not None:
        _SPAWN_CACHE[key] = best[1]
        return best[1], FrameTransform.from_carla_transform(best[1])
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
    session.ego = ego
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

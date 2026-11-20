"""Sinh Tesla Model 3, trích tham số vật lý, đọc trạng thái tại tâm cầu sau (hướng dẫn §2.2, C2).

Cần gói `carla`. Mọi hàm nhận `sim` (SimWorld). Chưa chạy kiểm chứng ở máy này (không có CARLA):
vehicle_params phải được kiểm tra bằng tay một lần và ghi vào configs/tesla_model3.yaml."""
from __future__ import annotations

import math

import numpy as np

from .coords import from_carla_xyz_yaw


def spawn_tesla(sim, spawn_tf, role="hero"):
    bp = sim.world.get_blueprint_library().find("vehicle.tesla.model3")
    bp.set_attribute("role_name", role)
    ego = sim.spawn(bp, spawn_tf)
    if ego is None:
        raise RuntimeError("không sinh được xe tự hành (điểm sinh bị chiếm?)")
    sim.tick()   # cần 1 tick để vật lý khởi tạo
    return ego


def vehicle_params(ego):
    """Trích L, delta_max, kích thước và khoảng từ tâm actor tới tâm cầu sau (rear_dx, m, dọc theo hướng xe)."""
    pc = ego.get_physics_control()
    w = pc.wheels   # FL, FR, RL, RR; position tính bằng cm, hệ CARLA toàn cục
    front = np.mean([[w[0].position.x, w[0].position.y], [w[1].position.x, w[1].position.y]], 0) / 100.0
    rear = np.mean([[w[2].position.x, w[2].position.y], [w[3].position.x, w[3].position.y]], 0) / 100.0
    L = float(np.linalg.norm(front - rear))
    dmax = math.radians(max(w[0].max_steer_angle, w[1].max_steer_angle))
    ext = ego.bounding_box.extent
    tf = ego.get_transform()
    fwd = np.array([tf.get_forward_vector().x, tf.get_forward_vector().y])
    loc = np.array([tf.location.x, tf.location.y])
    rear_dx = float(np.dot(rear - loc, fwd))                      # âm: cầu sau nằm sau tâm actor
    bb_c = float(ego.bounding_box.location.x)                     # tâm hộp bao so với tâm actor
    rear_overhang = float(rear_dx - (bb_c - ext.x))               # cầu sau -> đuôi hộp bao; KIỂM TRA BẰNG TAY
    return dict(L=L, delta_max=dmax, length=2 * ext.x, width=2 * ext.y, rear_overhang=rear_overhang,
                rear_dx=rear_dx, mass=float(pc.mass))


def read_state(ego, rear_dx, delta_last=0.0):
    """[px,py,psi,v,delta] tại tâm cầu sau, hệ tay phải (hướng dẫn §7.1)."""
    tf = ego.get_transform()
    px, py, psi = from_carla_xyz_yaw(tf.location.x, tf.location.y, tf.rotation.yaw)
    px, py = px + rear_dx * math.cos(psi), py + rear_dx * math.sin(psi)
    vel = ego.get_velocity()
    v = float(vel.x * math.cos(psi) + (-vel.y) * math.sin(psi))
    return np.array([px, py, psi, v, delta_last])


def to_vehicle_control(ctrl):
    import carla
    # av_core: delta > 0 là rẽ trái (tay phải); CARLA: steer > 0 là rẽ phải -> đảo dấu.
    return carla.VehicleControl(throttle=float(ctrl.throttle), steer=-float(ctrl.steer), brake=float(ctrl.brake))

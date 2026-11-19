"""Quy đổi hệ tọa độ ở MỘT chỗ (hướng dẫn §1.6).

CARLA (Unreal): tay trái, x tiến, y sang phải, yaw bằng độ, dương theo chiều kim đồng hồ.
av_core: tay phải (như ROS), y sang trái, góc hướng bằng radian, dương ngược chiều kim đồng hồ.
Phần số học thuần (không import carla) để test ở máy không có CARLA."""
from __future__ import annotations

import math


def to_carla_xyz_yaw(px, py, psi, z=0.0):
    return px, -py, z, -math.degrees(psi)


def from_carla_xyz_yaw(x, y, yaw_deg):
    return x, -y, -math.radians(yaw_deg)


def to_carla(px, py, psi, z=0.0):
    import carla
    x, y, z, yaw = to_carla_xyz_yaw(px, py, psi, z)
    return carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw))


def from_carla(tf):
    return from_carla_xyz_yaw(tf.location.x, tf.location.y, tf.rotation.yaw)


def vec_from_carla(vx, vy):
    return vx, -vy


def vec_to_carla(vx, vy):
    return vx, -vy

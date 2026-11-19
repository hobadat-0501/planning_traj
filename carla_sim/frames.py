"""Chuyển đổi hệ tọa độ CARLA (tay trái, yaw độ, chiều kim đồng hồ) <-> hệ cục bộ 2D.

Hệ cục bộ dùng trong `sim/` là hệ tay phải: x dọc làn theo hướng xe xuất phát, y sang trái,
psi (rad) ngược chiều kim đồng hồ. Gốc tọa độ đặt tại điểm xuất phát của xe tự hành.

CARLA (Unreal) dùng X tới, Y sang phải, yaw dương theo chiều kim đồng hồ khi nhìn từ trên.
Đổi sang tay phải: (X, Y, yaw) -> (X, -Y, -yaw).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sim.core import XC_LOCAL, wrap_angle


@dataclass
class FrameTransform:
    """Phép biến đổi giữa hệ thế giới CARLA và hệ cục bộ 2D."""

    x0: float          # Gốc trong hệ tay phải của thế giới (m)
    y0: float
    psi0: float        # Hướng trục x cục bộ trong hệ tay phải thế giới (rad)
    z0: float = 0.0    # Cao độ mặt đường tại gốc (m)

    @classmethod
    def from_carla_transform(cls, tf) -> "FrameTransform":
        """Tạo từ `carla.Transform` của điểm xuất phát."""
        return cls(
            x0=float(tf.location.x),
            y0=-float(tf.location.y),
            psi0=-math.radians(float(tf.rotation.yaw)),
            z0=float(tf.location.z),
        )

    # ----- Điểm và hướng -------------------------------------------------------
    def world_to_local_xy(self, X: float, Y: float) -> tuple[float, float]:
        xr, yr = X - self.x0, -Y - self.y0
        c, s = math.cos(self.psi0), math.sin(self.psi0)
        return c * xr + s * yr, -s * xr + c * yr

    def local_to_world_xy(self, px: float, py: float) -> tuple[float, float]:
        c, s = math.cos(self.psi0), math.sin(self.psi0)
        xr = c * px - s * py + self.x0
        yr = s * px + c * py + self.y0
        return xr, -yr

    def world_yaw_deg_to_local(self, yaw_deg: float) -> float:
        return float(wrap_angle(-math.radians(yaw_deg) - self.psi0))

    def local_psi_to_world_yaw_deg(self, psi: float) -> float:
        return -math.degrees(float(wrap_angle(psi + self.psi0)))

    def world_vec_to_local(self, vx: float, vy: float) -> tuple[float, float]:
        vyr = -vy
        c, s = math.cos(self.psi0), math.sin(self.psi0)
        return c * vx + s * vyr, -s * vx + c * vyr

    # ----- Actor ---------------------------------------------------------------
    def actor_center_pose(self, actor) -> tuple[float, float, float]:
        """Tâm hộp bao của actor trong hệ cục bộ (px, py, psi)."""
        tf = actor.get_transform()
        bb = actor.bounding_box
        center = tf.transform(bb.location)
        px, py = self.world_to_local_xy(center.x, center.y)
        return px, py, self.world_yaw_deg_to_local(tf.rotation.yaw)

    def ego_rear_axle_pose(self, actor) -> tuple[float, float, float]:
        """Tư thế tâm cầu sau của xe tự hành (quy ước của `sim.core.EgoPlant`)."""
        cx, cy, psi = self.actor_center_pose(actor)
        return cx - XC_LOCAL * math.cos(psi), cy - XC_LOCAL * math.sin(psi), psi

    def actor_velocity(self, actor, psi_local: float) -> tuple[float, float, float]:
        """(vx, vy, v_dọc) trong hệ cục bộ; v_dọc là thành phần theo hướng thân xe."""
        vel = actor.get_velocity()
        vx, vy = self.world_vec_to_local(vel.x, vel.y)
        v_long = vx * math.cos(psi_local) + vy * math.sin(psi_local)
        return vx, vy, v_long

    def actor_accel_long(self, actor, psi_local: float) -> float:
        acc = actor.get_acceleration()
        ax, ay = self.world_vec_to_local(acc.x, acc.y)
        return ax * math.cos(psi_local) + ay * math.sin(psi_local)

    def make_carla_transform(self, px: float, py: float, psi: float, z: float | None = None, bb_offset=None):
        """Tạo `carla.Transform` sao cho tâm hộp bao nằm tại (px, py) cục bộ."""
        import carla  # noqa: PLC0415

        yaw_deg = self.local_psi_to_world_yaw_deg(psi)
        X, Y = self.local_to_world_xy(px, py)
        if bb_offset is not None:
            # Bù độ lệch tâm hộp bao so với gốc actor (theo hệ actor, tay trái)
            yaw_r = math.radians(yaw_deg)
            X -= bb_offset.x * math.cos(yaw_r) - bb_offset.y * math.sin(yaw_r)
            Y -= bb_offset.x * math.sin(yaw_r) + bb_offset.y * math.cos(yaw_r)
        zz = self.z0 if z is None else z
        return carla.Transform(carla.Location(x=X, y=Y, z=zz), carla.Rotation(yaw=yaw_deg))

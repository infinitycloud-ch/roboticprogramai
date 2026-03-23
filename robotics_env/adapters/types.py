"""Dataclasses partagées entre tous les adapters (Sim, Go2, futur VLA).

Ces types forment le contrat de données entre le Cerveau (Couche 1)
et l'Interface Corps (Couche 2). Ils sont indépendants de ROS2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np


class RobotMode(Enum):
    """Modes opérationnels du robot."""
    IDLE = "idle"
    WALKING = "walking"
    STANDING = "standing"
    EMERGENCY_STOP = "emergency_stop"


@dataclass(frozen=True)
class Twist:
    """Commande de vélocité dans le repère robot.

    Conventions:
        linear_x  > 0 : avancer
        linear_y  > 0 : déplacement latéral gauche
        angular_z > 0 : rotation anti-horaire (vue de dessus)
    """
    linear_x: float = 0.0    # m/s
    linear_y: float = 0.0    # m/s
    angular_z: float = 0.0   # rad/s


@dataclass(frozen=True)
class Pose:
    """Position et orientation dans l'espace (repère monde)."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0    # rad
    pitch: float = 0.0   # rad
    yaw: float = 0.0     # rad


@dataclass(frozen=True)
class RobotState:
    """État complet du robot à un instant donné.

    Attributes:
        pose: Position/orientation dans le repère monde.
        velocity: Vélocité courante dans le repère robot.
        joint_positions: Positions des 12 joints (rad). Ordre:
            FL_hip, FL_thigh, FL_calf,
            FR_hip, FR_thigh, FR_calf,
            RL_hip, RL_thigh, RL_calf,
            RR_hip, RR_thigh, RR_calf
        joint_velocities: Vélocités des 12 joints (rad/s).
        mode: Mode opérationnel courant.
        battery_percent: Niveau batterie (None en simulation).
        timestamp: Timestamp ROS2 (secondes depuis epoch).
    """
    pose: Pose = field(default_factory=Pose)
    velocity: Twist = field(default_factory=Twist)
    joint_positions: tuple[float, ...] = ()
    joint_velocities: tuple[float, ...] = ()
    mode: RobotMode = RobotMode.IDLE
    battery_percent: Optional[float] = None
    timestamp: float = 0.0


@dataclass(frozen=True)
class SensorData:
    """Données capteurs brutes.

    Attributes:
        imu_orientation: Quaternion (x, y, z, w).
        imu_angular_velocity: Vitesse angulaire (rad/s).
        imu_linear_acceleration: Accélération linéaire (m/s²).
        foot_contacts: Contact au sol (FL, FR, RL, RR).
        lidar_points: Nuage de points (N, 3) en coordonnées robot.
            None si pas de LiDAR actif.
        timestamp: Timestamp ROS2 (secondes depuis epoch).
    """
    imu_orientation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    imu_angular_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    imu_linear_acceleration: tuple[float, float, float] = (0.0, 0.0, 0.0)
    foot_contacts: tuple[bool, bool, bool, bool] = (False, False, False, False)
    lidar_points: Optional[np.ndarray] = None
    timestamp: float = 0.0

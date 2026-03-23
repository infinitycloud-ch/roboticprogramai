"""Go2Adapter — Stub Phase 2 pour le robot Unitree Go2 EDU réel.

Ce fichier est un squelette. L'implémentation viendra au Sprint 2
quand l'environnement de simulation sera validé.

Utilisera:
    - unitree_sdk2_python (github.com/unitreerobotics/unitree_sdk2_python)
    - unitree_ros2 (github.com/unitreerobotics/unitree_ros2)
    - CycloneDDS via Ethernet (connecté au Jetson Orin du Go2 EDU)
"""

from __future__ import annotations

from adapters.robot_adapter import RobotAdapter
from adapters.types import Twist, RobotState, SensorData, RobotMode


class Go2Adapter(RobotAdapter):
    """Adapter pour le Unitree Go2 EDU réel (Phase 2)."""

    async def connect(self) -> None:
        raise NotImplementedError("Go2Adapter sera implémenté au Sprint 2")

    async def disconnect(self) -> None:
        raise NotImplementedError

    async def move(self, cmd: Twist) -> None:
        raise NotImplementedError

    async def set_mode(self, mode: RobotMode) -> None:
        raise NotImplementedError

    async def emergency_stop(self) -> None:
        raise NotImplementedError

    async def get_state(self) -> RobotState:
        raise NotImplementedError

    async def get_sensors(self) -> SensorData:
        raise NotImplementedError

    @property
    def is_connected(self) -> bool:
        return False

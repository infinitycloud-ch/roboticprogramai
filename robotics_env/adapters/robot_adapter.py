"""Interface abstraite RobotAdapter — Couche 2 du framework.

Contrat unique entre le Cerveau (Agent Jedi) et le Monde (Isaac Sim / Go2 réel).
Chaque implémentation (SimAdapter, Go2Adapter) traduit ces appels
haut niveau en commandes spécifiques à l'environnement cible.

Le RobotAdapter NE gère PAS la cinématique ni la locomotion.
Il publie des intentions de vélocité ; le Noeud Locomoteur (politique RL PPO)
se charge de traduire en torques articulaires.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from adapters.types import Twist, RobotState, SensorData, RobotMode


class RobotAdapter(ABC):
    """Interface abstraite commune pour robot simulé et réel.

    Usage:
        adapter = SimAdapter()       # ou Go2Adapter()
        await adapter.connect()
        state = await adapter.get_state()
        await adapter.move(Twist(linear_x=0.5))
        await adapter.disconnect()
    """

    # --- Lifecycle ---

    @abstractmethod
    async def connect(self) -> None:
        """Établir la connexion avec le robot/simulation.

        Raises:
            ConnectionError: Si le robot ou la simulation est injoignable.
            TimeoutError: Si la connexion dépasse le timeout.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Fermer proprement la connexion.

        Envoie un Twist(0,0,0) de sécurité avant de couper.
        """
        ...

    # --- Commandes ---

    @abstractmethod
    async def move(self, cmd: Twist) -> None:
        """Envoyer une commande de vélocité.

        La commande est publiée sur /cmd_vel. Le Noeud Locomoteur
        la traduit en torques articulaires via la politique RL.

        Args:
            cmd: Commande Twist (linear_x, linear_y, angular_z).
        """
        ...

    @abstractmethod
    async def set_mode(self, mode: RobotMode) -> None:
        """Changer le mode opérationnel du robot.

        Args:
            mode: Mode cible (IDLE, WALKING, STANDING, EMERGENCY_STOP).
        """
        ...

    @abstractmethod
    async def emergency_stop(self) -> None:
        """Arrêt d'urgence immédiat. Priorité maximale.

        Publie Twist(0,0,0) et passe en mode EMERGENCY_STOP.
        """
        ...

    # --- Lecture d'état ---

    @abstractmethod
    async def get_state(self) -> RobotState:
        """Obtenir l'état actuel du robot.

        Returns:
            RobotState avec pose, vélocité, positions articulaires, mode.
        """
        ...

    @abstractmethod
    async def get_sensors(self) -> SensorData:
        """Obtenir les dernières données capteurs.

        Returns:
            SensorData avec IMU, contacts pieds, LiDAR.
        """
        ...

    # --- Propriétés ---

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """True si la connexion est active et les topics reçus."""
        ...

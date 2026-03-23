"""SimAdapter - Pont Python → ROS2 /cmd_vel → Noeud Locomoteur → Isaac Sim.

Le SimAdapter NE calcule PAS la cinématique. Il publie des commandes
de vélocité sur /cmd_vel. Le Noeud Locomoteur (politique RL PPO) traduit
ces vélocités en torques pour les 12 joints du Go2.

Architecture:
    Agent Jedi → SimAdapter.move(Twist)
        → publie /cmd_vel (geometry_msgs/Twist)
        → Noeud Locomoteur (RL PPO) → torques 12 DOF
        → Isaac Sim applique les torques

Threading:
    rclpy.spin() tourne dans un thread daemon séparé.
    Les callbacks ROS2 mettent à jour l'état via un Lock.
    Les méthodes async sont thread-safe.
"""

from __future__ import annotations

import asyncio
import math
import threading
import time
from typing import Optional

from adapters.robot_adapter import RobotAdapter
from adapters.types import (
    Pose,
    RobotMode,
    RobotState,
    SensorData,
    Twist,
)

# Timeouts pour connect()
_CLOCK_TIMEOUT_S = 10.0
_ODOM_TIMEOUT_S = 5.0


def _quaternion_to_euler(x: float, y: float, z: float, w: float):
    """Convertir quaternion (x,y,z,w) → euler (roll, pitch, yaw)."""
    # Roll (x-axis rotation)
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # Pitch (y-axis rotation)
    sinp = 2.0 * (w * y - z * x)
    if abs(sinp) >= 1.0:
        pitch = math.copysign(math.pi / 2, sinp)
    else:
        pitch = math.asin(sinp)

    # Yaw (z-axis rotation)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return roll, pitch, yaw


def _stamp_to_sec(stamp) -> float:
    """Convertir un ROS2 Time stamp en secondes float."""
    return stamp.sec + stamp.nanosec * 1e-9


class SimAdapter(RobotAdapter):
    """Pont Python → ROS2 /cmd_vel → Noeud Locomoteur → Isaac Sim.

    Usage:
        adapter = SimAdapter()
        await adapter.connect()       # init rclpy + vérifie /clock
        await adapter.move(Twist(linear_x=0.5))
        state = await adapter.get_state()
        await adapter.disconnect()
    """

    def __init__(self, node_name: str = "sim_adapter"):
        self._node_name = node_name
        self._node = None
        self._executor = None

        # Publishers
        self._cmd_vel_pub = None

        # Subscribers
        self._odom_sub = None
        self._joint_state_sub = None
        self._imu_sub = None
        self._clock_sub = None

        # État partagé (protégé par _lock)
        self._lock = threading.Lock()
        self._latest_state = RobotState()
        self._latest_sensors = SensorData()
        self._mode = RobotMode.IDLE
        self._clock_received = False
        self._odom_received = False

        # Thread spin
        self._spin_thread: Optional[threading.Thread] = None
        self._connected = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Initialiser le noeud ROS2 et vérifier les topics Isaac Sim.

        Raises:
            ConnectionError: Si rclpy n'est pas disponible.
            TimeoutError: Si /clock ou /odom ne sont pas reçus à temps.
        """
        if self._connected:
            return

        # Import rclpy au moment de la connexion (permet import sur Mac)
        try:
            import rclpy
            from rclpy.executors import MultiThreadedExecutor
        except ImportError as exc:
            raise ConnectionError(
                "rclpy non disponible. Installez ROS2 Jazzy "
                "ou sourcez /opt/ros/jazzy/setup.bash"
            ) from exc

        # Init rclpy si pas déjà fait
        if not rclpy.ok():
            rclpy.init()

        self._node = rclpy.create_node(self._node_name)

        # Créer publisher et subscribers
        self._create_publishers()
        self._create_subscribers()

        # Lancer le spin dans un thread daemon
        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self._node)
        self._spin_thread = threading.Thread(
            target=self._spin_loop,
            daemon=True,
            name="sim_adapter_spin",
        )
        self._spin_thread.start()

        # Attendre /clock (Isaac Sim tourne?)
        await self._wait_for_topic(
            check=lambda: self._clock_received,
            timeout=_CLOCK_TIMEOUT_S,
            topic_name="/clock",
        )

        # Attendre /odom (bridge actif?)
        await self._wait_for_topic(
            check=lambda: self._odom_received,
            timeout=_ODOM_TIMEOUT_S,
            topic_name="/odom",
        )

        self._connected = True
        self._node.get_logger().info("SimAdapter connecté — Isaac Sim actif")

    async def disconnect(self) -> None:
        """Arrêter proprement : envoyer Twist(0) puis shutdown le noeud."""
        if not self._connected:
            return

        # Sécurité : arrêter le robot
        await self.move(Twist())

        self._connected = False

        # Shutdown executor + node
        if self._executor is not None:
            self._executor.shutdown()
            self._executor = None

        if self._node is not None:
            self._node.destroy_node()
            self._node = None

        self._spin_thread = None
        self._clock_received = False
        self._odom_received = False

    # ------------------------------------------------------------------
    # Commandes
    # ------------------------------------------------------------------

    async def move(self, cmd: Twist) -> None:
        """Publier une commande de vélocité sur /cmd_vel.

        Args:
            cmd: Commande Twist (linear_x, linear_y, angular_z).

        Raises:
            ConnectionError: Si pas connecté.
        """
        self._check_connected()

        from geometry_msgs.msg import Twist as TwistMsg

        msg = TwistMsg()
        msg.linear.x = cmd.linear_x
        msg.linear.y = cmd.linear_y
        msg.linear.z = 0.0
        msg.angular.x = 0.0
        msg.angular.y = 0.0
        msg.angular.z = cmd.angular_z

        self._cmd_vel_pub.publish(msg)

    async def set_mode(self, mode: RobotMode) -> None:
        """Changer le mode opérationnel.

        En simulation, le mode est informatif. EMERGENCY_STOP envoie Twist(0).
        """
        with self._lock:
            self._mode = mode

        if mode == RobotMode.EMERGENCY_STOP:
            await self.emergency_stop()

    async def emergency_stop(self) -> None:
        """Arrêt d'urgence : publie Twist(0) et passe en EMERGENCY_STOP."""
        with self._lock:
            self._mode = RobotMode.EMERGENCY_STOP

        if self._connected and self._cmd_vel_pub is not None:
            from geometry_msgs.msg import Twist as TwistMsg

            msg = TwistMsg()  # Tout à zéro
            self._cmd_vel_pub.publish(msg)

    # ------------------------------------------------------------------
    # Lecture d'état
    # ------------------------------------------------------------------

    async def get_state(self) -> RobotState:
        """Retourner le dernier état du robot (mis à jour par callbacks).

        Raises:
            ConnectionError: Si pas connecté.
        """
        self._check_connected()
        with self._lock:
            return self._latest_state

    async def get_sensors(self) -> SensorData:
        """Retourner les dernières données capteurs.

        Raises:
            ConnectionError: Si pas connecté.
        """
        self._check_connected()
        with self._lock:
            return self._latest_sensors

    # ------------------------------------------------------------------
    # Propriétés
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """True si le noeud ROS2 est actif et les topics reçus."""
        return self._connected

    # ------------------------------------------------------------------
    # Publishers / Subscribers (privé)
    # ------------------------------------------------------------------

    def _create_publishers(self) -> None:
        """Créer les publishers ROS2."""
        from geometry_msgs.msg import Twist as TwistMsg
        from rclpy.qos import (
            HistoryPolicy,
            QoSProfile,
            ReliabilityPolicy,
        )

        cmd_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        self._cmd_vel_pub = self._node.create_publisher(
            TwistMsg, "/cmd_vel", cmd_qos,
        )

    def _create_subscribers(self) -> None:
        """Créer les subscribers ROS2 avec QoS BEST_EFFORT."""
        from nav_msgs.msg import Odometry
        from rosgraph_msgs.msg import Clock
        from sensor_msgs.msg import Imu, JointState
        from rclpy.qos import (
            HistoryPolicy,
            QoSProfile,
            ReliabilityPolicy,
        )

        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        self._odom_sub = self._node.create_subscription(
            Odometry, "/odom", self._on_odom, sensor_qos,
        )
        self._joint_state_sub = self._node.create_subscription(
            JointState, "/joint_states", self._on_joint_states, sensor_qos,
        )
        self._imu_sub = self._node.create_subscription(
            Imu, "/imu/data", self._on_imu, sensor_qos,
        )
        self._clock_sub = self._node.create_subscription(
            Clock, "/clock", self._on_clock, sensor_qos,
        )

    # ------------------------------------------------------------------
    # Callbacks ROS2 (appelés depuis le spin thread)
    # ------------------------------------------------------------------

    def _on_odom(self, msg) -> None:
        """Callback /odom → met à jour pose et vélocité dans RobotState."""
        pos = msg.pose.pose.position
        ori = msg.pose.pose.orientation
        lin = msg.twist.twist.linear
        ang = msg.twist.twist.angular

        roll, pitch, yaw = _quaternion_to_euler(ori.x, ori.y, ori.z, ori.w)
        stamp = _stamp_to_sec(msg.header.stamp)

        with self._lock:
            self._odom_received = True
            self._latest_state = RobotState(
                pose=Pose(
                    x=pos.x, y=pos.y, z=pos.z,
                    roll=roll, pitch=pitch, yaw=yaw,
                ),
                velocity=Twist(
                    linear_x=lin.x,
                    linear_y=lin.y,
                    angular_z=ang.z,
                ),
                joint_positions=self._latest_state.joint_positions,
                joint_velocities=self._latest_state.joint_velocities,
                mode=self._mode,
                battery_percent=None,
                timestamp=stamp,
            )

    def _on_joint_states(self, msg) -> None:
        """Callback /joint_states → met à jour positions/vélocités articulaires."""
        stamp = _stamp_to_sec(msg.header.stamp)

        with self._lock:
            self._latest_state = RobotState(
                pose=self._latest_state.pose,
                velocity=self._latest_state.velocity,
                joint_positions=tuple(msg.position),
                joint_velocities=tuple(msg.velocity),
                mode=self._mode,
                battery_percent=None,
                timestamp=stamp,
            )

    def _on_imu(self, msg) -> None:
        """Callback /imu/data → met à jour SensorData."""
        ori = msg.orientation
        gyro = msg.angular_velocity
        accel = msg.linear_acceleration
        stamp = _stamp_to_sec(msg.header.stamp)

        with self._lock:
            self._latest_sensors = SensorData(
                imu_orientation=(ori.x, ori.y, ori.z, ori.w),
                imu_angular_velocity=(gyro.x, gyro.y, gyro.z),
                imu_linear_acceleration=(accel.x, accel.y, accel.z),
                foot_contacts=self._latest_sensors.foot_contacts,
                lidar_points=self._latest_sensors.lidar_points,
                timestamp=stamp,
            )

    def _on_clock(self, msg) -> None:
        """Callback /clock → marque Isaac Sim comme actif."""
        if not self._clock_received:
            self._clock_received = True

    # ------------------------------------------------------------------
    # Helpers (privé)
    # ------------------------------------------------------------------

    def _spin_loop(self) -> None:
        """Boucle de spin rclpy dans un thread séparé."""
        try:
            self._executor.spin()
        except Exception:
            pass  # Shutdown propre

    async def _wait_for_topic(
        self,
        check,
        timeout: float,
        topic_name: str,
    ) -> None:
        """Attendre qu'un topic soit reçu, avec timeout.

        Args:
            check: Callable retournant True quand le topic est reçu.
            timeout: Timeout en secondes.
            topic_name: Nom du topic (pour le message d'erreur).

        Raises:
            TimeoutError: Si le topic n'est pas reçu à temps.
        """
        deadline = time.monotonic() + timeout
        while not check():
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"Timeout ({timeout}s) en attente de {topic_name}. "
                    f"Vérifiez qu'Isaac Sim est lancé et que le bridge "
                    f"isaacsim.ros2.bridge est activé."
                )
            await asyncio.sleep(0.1)

    def _check_connected(self) -> None:
        """Vérifier que le SimAdapter est connecté.

        Raises:
            ConnectionError: Si pas connecté.
        """
        if not self._connected:
            raise ConnectionError(
                "SimAdapter non connecté. Appelez connect() d'abord."
            )

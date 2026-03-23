# Technical Design Document — Sprint 1: Foundation & Simulation
**Projet:** RoboticProgramAI
**Version:** 1.3 (stack aarch64 finale)
**Date:** 2026-02-27
**Auteur:** Agent Développeur
**Statut:** Validé CEO

---

## Table des matières
1. [Architecture Technique](#1-architecture-technique)
2. [Stack Technologique](#2-stack-technologique)
3. [Structure Monorepo](#3-structure-monorepo)
4. [Interface RobotAdapter](#4-interface-robotadapter)
5. [Plan SimAdapter](#5-plan-simadapter)
6. [Séquence Hello Robot](#6-séquence-hello-robot)
7. [Risques et Mitigations](#7-risques-et-mitigations)
8. [Note UnifoLM-VLA-0](#8-note-unifolm-vla-0)

---

## 1. Architecture Technique

### 1.1 Vue d'ensemble — 3 Couches

```
┌─────────────────────────────────────────────────────────────────────┐
│                    COUCHE 1 : CERVEAU                                │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐        │
│  │ Agent Jedi   │  │ Agent        │  │ Mémoire            │        │
│  │ (décision,   │  │ Monocili     │  │ Persistante        │        │
│  │  planning)   │  │ (mono-tâche) │  │ (état, historique) │        │
│  └──────┬───────┘  └──────┬───────┘  └────────────────────┘        │
│         │                 │                                         │
│         └────────┬────────┘                                         │
│                  │ Intentions haut niveau                            │
│                  ▼ (move, get_state, get_sensors)                    │
├─────────────────────────────────────────────────────────────────────┤
│                COUCHE 2 : INTERFACE CORPS                            │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │              RobotAdapter (ABC)                           │       │
│  │  move() | get_state() | get_sensors() | emergency_stop() │       │
│  └──────────────────┬───────────────────────────────────────┘       │
│                     │                                               │
│         ┌───────────┴───────────┐                                   │
│         ▼                       ▼                                   │
│  ┌──────────────┐    ┌──────────────┐                               │
│  │ SimAdapter   │    │ Go2Adapter   │                               │
│  │ (Isaac Sim)  │    │ (Robot réel) │                               │
│  │ Sprint 1 ✓   │    │ Phase 2 stub │                               │
│  └──────┬───────┘    └──────────────┘                               │
│         │ Publie /cmd_vel (vélocités)                               │
│         ▼                                                           │
│  ┌──────────────────────────────────────────────┐                   │
│  │      Noeud Locomoteur (Politique RL PPO)      │                   │
│  │  Traduit vélocités → torques 12 DOF           │                   │
│  │  (issu de isaac-go2-ros2 / Isaac Lab)         │                   │
│  └──────────────────┬───────────────────────────┘                   │
│                     │ Commandes articulaires (torques)              │
│                     ▼                                               │
├─────────────────────────────────────────────────────────────────────┤
│                 COUCHE 3 : MONDE                                     │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │     NVIDIA Isaac Sim 5.1.0 + Isaac Lab 2.3.x              │       │
│  │     (Serveur DGX Spark aarch64 GB10)                      │       │
│  │                                                           │       │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │       │
│  │  │ Go2 URDF    │  │ OmniGraph    │  │ ROS2 Bridge    │  │       │
│  │  │ (12 DOF)    │  │ (pub/sub)    │  │ isaacsim.ros2  │  │       │
│  │  └─────────────┘  └──────────────┘  └────────────────┘  │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                     │
│  Transport: FastDDS UDP (multi-machine, Domain ID: 0)               │
│  Ports: 7400, 7410, 9387                                            │
└─────────────────────────────────────────────────────────────────────┘
```

**Flux de contrôle explicite :**
```
Agent Jedi (Intentions) → SimAdapter (publie /cmd_vel)
  → Noeud Locomoteur (Politique RL PPO, issue de isaac-go2-ros2)
    → Isaac Sim (Torques sur les 12 DOF)
```

Le **SimAdapter NE calcule PAS la cinématique**. Il publie des commandes de vélocité (/cmd_vel). Le **Noeud Locomoteur** (politique RL PPO entraînée via Isaac Lab) traduit ces vélocités en commandes articulaires (torques) pour les 12 joints du Go2.

### 1.2 Flux de données

```
Agent Jedi            SimAdapter            Noeud Locomoteur       Isaac Sim
    │                     │                      │                     │
    │ move(vx, vy, ωz)   │                      │                     │
    │────────────────────>│                      │                     │
    │                     │ publish /cmd_vel     │                     │
    │                     │ (Twist)              │                     │
    │                     │─────────────────────>│                     │
    │                     │                      │ Politique RL PPO    │
    │                     │                      │ vélocité → torques  │
    │                     │                      │ 12 DOF              │
    │                     │                      │────────────────────>│
    │                     │                      │                     │
    │                     │                      │  Publish /odom      │
    │                     │                      │  /joint_states      │
    │                     │                      │  /tf, /clock        │
    │                     │                      │<────────────────────│
    │                     │ subscribe /odom      │                     │
    │                     │<─────────────────────│                     │
    │ RobotState          │                      │                     │
    │<────────────────────│                      │                     │
    │                     │                      │                     │
```

---

## 2. Stack Technologique

| Composant | Version | Notes |
|-----------|---------|-------|
| **OS Serveur (Spark)** | Ubuntu 24.04.3 LTS (Noble) | aarch64 GB10 Grace-Blackwell |
| **Architecture** | aarch64 (ARM64) | NVIDIA DGX Spark, 128GB RAM unifiée |
| **NVIDIA Isaac Sim** | 5.1.0 | Première version stable aarch64 (pip + pypi.nvidia.com) |
| **NVIDIA Isaac Lab** | 2.3.x | Compatible Isaac Sim 5.1.0 (branche release/2.3.0) |
| **ROS2** | Jazzy Jalisco | LTS pour Ubuntu 24.04, apt arm64 natif |
| **Python** | 3.11 | Requis par Isaac Sim 5.x |
| **DDS Middleware** | FastDDS (eProsima) | rmw_fastrtps_cpp |
| **Transport multi-machine** | FastDDS UDP | fichier fastdds.xml custom |
| **Extension Isaac Sim** | isaacsim.ros2.bridge | Extension v5.x (renommée depuis omni.isaac.ros2_bridge) |
| **CUDA** | 13.0 | Driver 580.126 |
| **PyTorch** | 2.9.0 (cu130) | Wheels aarch64 officiels |
| **Politique Locomotion** | RL PPO (Isaac Lab) | Entraînée via isaac-go2-ros2 |
| **URDF Go2** | go2_description | Apache 2.0, 12 DOF, meshes DAE |
| **SDK Unitree (futur)** | unitree_sdk2 v2.0.2 | C++, CycloneDDS (Phase 2) |
| **SDK Python Unitree (futur)** | unitree_sdk2_python | Bindings Python (Phase 2) |
| **ROS2 Unitree (futur)** | unitree_ros2 | Messages DDS natifs (Phase 2) |

### Repos officiels Unitree (OBLIGATOIRES)
- **SDK C++:** github.com/unitreerobotics/unitree_sdk2
- **SDK Python:** github.com/unitreerobotics/unitree_sdk2_python
- **ROS2:** github.com/unitreerobotics/unitree_ros2
- **URDF:** github.com/Unitree-Go2-Robot/go2_description
- **VLA:** github.com/unitreerobotics/unifolm-vla
- **Doc:** support.unitree.com/main

### Projet de référence (architecture + politique RL)
- **isaac-go2-ros2** (Zhefan-Xu) : Originalement Isaac Sim 4.5 + Isaac Lab 2.1 + ROS2 Jazzy
- Utilisé comme référence d'architecture ET source de la politique locomotion RL PPO
- **IMPORTANT :** Les imports `omni.isaac.ros2_bridge` doivent être patchés en `isaacsim.ros2.bridge` pour compatibilité Isaac Sim 5.x
- Implémentation basée sur repos officiels Unitree

---

## 3. Structure Monorepo

**IMPORTANT :** Le code Sprint 1 est isolé dans `/robotics_env/` à la racine du projet parent, séparé de l'infrastructure agents existante.

```
RoboticProgramAI/                          ← Projet parent
├── CLAUDE.md                             # Config stratégiste
├── agent_tools/                          # Infrastructure agents (ne pas toucher)
├── agent_logs/                           # Logs conversations
├── RoboticProgramAI APP/                 # Config agent DEV (ne pas toucher)
│   └── CLAUDE.md
│
└── robotics_env/                         ← TOUT LE CODE SPRINT 1 ICI
    ├── pyproject.toml                    # Config projet Python (PEP 621)
    ├── README.md
    ├── .env.example                      # Variables d'environnement template
    │
    ├── agent/                            # COUCHE 1 : CERVEAU
    │   ├── __init__.py
    │   ├── jedi_agent.py                 # Agent principal (décision, planning)
    │   ├── monocili_agent.py             # Agent mono-tâche
    │   └── memory/
    │       ├── __init__.py
    │       └── persistent_store.py       # Mémoire persistante
    │
    ├── adapters/                         # COUCHE 2 : INTERFACE CORPS
    │   ├── __init__.py
    │   ├── robot_adapter.py              # ABC — interface commune
    │   ├── sim_adapter.py                # SimAdapter (publie /cmd_vel via ROS2)
    │   ├── go2_adapter.py                # Go2Adapter (stub Phase 2)
    │   └── types.py                      # Dataclasses partagées
    │
    ├── locomotion/                       # NOEUD LOCOMOTEUR
    │   ├── __init__.py
    │   ├── locomotion_controller.py      # Noeud ROS2 : /cmd_vel → torques 12 DOF
    │   └── policies/                     # Politiques RL PPO pré-entraînées
    │       └── go2_flat.pt               # Poids du modèle (Isaac Lab PPO)
    │
    ├── ros/                              # Config & launch ROS2
    │   ├── config/
    │   │   ├── fastdds.xml               # Config FastDDS UDP multi-machine
    │   │   └── sim_bridge.yaml           # Paramètres ROS2 nodes
    │   └── launch/
    │       └── sim_bridge_launch.py      # Launch file ROS2
    │
    ├── sim/                              # COUCHE 3 : Assets & config Isaac Sim
    │   ├── urdf/
    │   │   └── go2_description/          # Clone officiel go2_description
    │   ├── omnigraph/
    │   │   └── go2_ros2_bridge.json      # Config OmniGraph exportée
    │   └── scenes/
    │       └── go2_flat_ground.usd       # Scène par défaut
    │
    ├── scripts/                          # Scripts utilitaires
    │   ├── hello_robot.py                # Test E2E Sprint 1
    │   └── setup_spark.sh                # Script installation Spark
    │
    ├── tests/                            # Tests unitaires & intégration
    │   ├── test_robot_adapter.py
    │   ├── test_sim_adapter.py
    │   ├── test_locomotion.py
    │   └── test_hello_robot.py
    │
    └── docs/                             # Documentation technique
        ├── technical_design_document.md   # CE DOCUMENT
        └── architecture_diagram.md
```

---

## 4. Interface RobotAdapter

### 4.1 Dataclasses partagées (adapters/types.py)

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import numpy as np


class RobotMode(Enum):
    IDLE = "idle"
    WALKING = "walking"
    STANDING = "standing"
    EMERGENCY_STOP = "emergency_stop"


@dataclass(frozen=True)
class Twist:
    """Commande de vélocité (repère robot)."""
    linear_x: float = 0.0   # m/s avant/arrière
    linear_y: float = 0.0   # m/s latéral
    angular_z: float = 0.0  # rad/s rotation


@dataclass(frozen=True)
class Pose:
    """Position dans l'espace."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


@dataclass(frozen=True)
class RobotState:
    """État complet du robot."""
    pose: Pose = field(default_factory=Pose)
    velocity: Twist = field(default_factory=Twist)
    joint_positions: tuple[float, ...] = ()  # 12 DOF
    joint_velocities: tuple[float, ...] = ()
    mode: RobotMode = RobotMode.IDLE
    battery_percent: Optional[float] = None
    timestamp: float = 0.0


@dataclass(frozen=True)
class SensorData:
    """Données capteurs."""
    imu_orientation: tuple[float, float, float, float] = (0, 0, 0, 1)  # quaternion
    imu_angular_velocity: tuple[float, float, float] = (0, 0, 0)
    imu_linear_acceleration: tuple[float, float, float] = (0, 0, 0)
    foot_contacts: tuple[bool, bool, bool, bool] = (False, False, False, False)
    lidar_points: Optional[np.ndarray] = None  # (N, 3) point cloud
    timestamp: float = 0.0
```

### 4.2 Interface ABC (adapters/robot_adapter.py)

```python
from abc import ABC, abstractmethod
from adapters.types import Twist, RobotState, SensorData, RobotMode


class RobotAdapter(ABC):
    """Interface abstraite commune pour robot simulé et réel."""

    @abstractmethod
    async def connect(self) -> None:
        """Établir la connexion avec le robot/simulation."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Fermer proprement la connexion."""
        ...

    @abstractmethod
    async def move(self, cmd: Twist) -> None:
        """Envoyer une commande de vélocité.

        Args:
            cmd: Commande Twist (linear_x, linear_y, angular_z)
        """
        ...

    @abstractmethod
    async def get_state(self) -> RobotState:
        """Obtenir l'état actuel du robot.

        Returns:
            RobotState avec pose, vélocité, joints, mode
        """
        ...

    @abstractmethod
    async def get_sensors(self) -> SensorData:
        """Obtenir les dernières données capteurs.

        Returns:
            SensorData avec IMU, contacts pieds, LiDAR
        """
        ...

    @abstractmethod
    async def set_mode(self, mode: RobotMode) -> None:
        """Changer le mode du robot (idle, walking, standing)."""
        ...

    @abstractmethod
    async def emergency_stop(self) -> None:
        """Arrêt d'urgence immédiat. Priorité maximale."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """True si la connexion est active."""
        ...
```

---

## 5. Plan SimAdapter

### 5.1 Implémentation SimAdapter (adapters/sim_adapter.py)

SimAdapter implémente RobotAdapter en communiquant avec le Noeud Locomoteur via ROS2. **Le SimAdapter NE calcule PAS la cinématique.** Il publie des commandes de vélocité sur /cmd_vel. Le Noeud Locomoteur (politique RL PPO) se charge de traduire ces vélocités en torques pour les 12 joints.

```python
class SimAdapter(RobotAdapter):
    """Pont Python → ROS2 /cmd_vel → Noeud Locomoteur → Isaac Sim."""

    def __init__(self, node_name: str = "sim_adapter"):
        self._node: Optional[rclpy.node.Node] = None
        self._cmd_vel_pub = None      # Publisher /cmd_vel → Noeud Locomoteur
        self._odom_sub = None         # Subscriber /odom
        self._joint_state_sub = None  # Subscriber /joint_states
        self._imu_sub = None          # Subscriber /imu/data
        self._latest_state = RobotState()
        self._latest_sensors = SensorData()
        self._connected = False
```

### 5.2 Topics ROS2

| Topic | Message Type | Direction | QoS Profile | Producteur → Consommateur |
|-------|-------------|-----------|-------------|--------------------------|
| `/cmd_vel` | geometry_msgs/msg/Twist | Publish | RELIABLE, depth=10 | SimAdapter → Noeud Locomoteur |
| `/joint_commands` | std_msgs/msg/Float64MultiArray | Interne | RELIABLE, depth=10 | Noeud Locomoteur → Isaac Sim |
| `/odom` | nav_msgs/msg/Odometry | Subscribe | BEST_EFFORT, depth=10 | Isaac Sim → SimAdapter |
| `/joint_states` | sensor_msgs/msg/JointState | Subscribe | BEST_EFFORT, depth=10 | Isaac Sim → SimAdapter + Noeud Locomoteur |
| `/tf` | tf2_msgs/msg/TFMessage | Subscribe | BEST_EFFORT, depth=100 | Isaac Sim → SimAdapter |
| `/clock` | rosgraph_msgs/msg/Clock | Subscribe | BEST_EFFORT, depth=10 | Isaac Sim → Tous |
| `/imu/data` | sensor_msgs/msg/Imu | Subscribe | BEST_EFFORT, depth=10 | Isaac Sim → SimAdapter + Noeud Locomoteur |

### 5.3 Noeud Locomoteur (locomotion/locomotion_controller.py)

Le Noeud Locomoteur est un noeud ROS2 autonome qui :
1. **Subscribe** /cmd_vel (vélocités désirées du SimAdapter)
2. **Subscribe** /joint_states + /imu/data (état courant du robot)
3. **Exécute** la politique RL PPO (réseau de neurones PyTorch)
4. **Publish** /joint_commands (torques 12 DOF vers Isaac Sim)

```python
class LocomotionController(Node):
    """Noeud ROS2 : politique RL PPO pour locomotion Go2."""

    def __init__(self):
        super().__init__("locomotion_controller")
        self._policy = None  # Modèle PyTorch (PPO, chargé depuis go2_flat.pt)

        # Subscribers
        self._cmd_vel_sub = ...   # /cmd_vel (consigne vélocité)
        self._joint_sub = ...     # /joint_states (positions/vélocités courantes)
        self._imu_sub = ...       # /imu/data (orientation, gyro)

        # Publisher
        self._joint_cmd_pub = ... # /joint_commands (torques 12 DOF)

        # Boucle de contrôle à 50 Hz
        self._timer = self.create_timer(0.02, self._control_loop)
```

### 5.4 QoS Profiles

```python
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

# Pour les commandes (fiabilité requise)
CMD_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=10
)

# Pour les données capteurs (temps réel, tolérance perte)
SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=10
)
```

### 5.5 Cycle de vie

```
connect()
    │
    ├── rclpy.init()
    ├── Créer Node("sim_adapter")
    ├── Créer Publisher /cmd_vel (CMD_QOS)
    ├── Créer Subscribers /odom, /joint_states, /imu/data (SENSOR_QOS)
    ├── Attendre /clock (timeout 10s → Isaac Sim non démarré)
    ├── Vérifier réception /odom (timeout 5s → bridge non configuré)
    ├── Vérifier Noeud Locomoteur actif (topic /joint_commands publié)
    └── self._connected = True

move(cmd)
    │
    ├── Vérifier is_connected
    ├── Construire geometry_msgs.Twist depuis adapters.Twist
    └── self._cmd_vel_pub.publish(twist_msg)
    └── NOTE: le Noeud Locomoteur traduit en torques automatiquement

get_state() → RobotState
    │
    └── Retourner self._latest_state (mis à jour par callbacks)

disconnect()
    │
    ├── Publier Twist(0,0,0) → arrêt robot
    ├── Détruire subscribers/publishers
    ├── Détruire node
    └── rclpy.shutdown()
```

---

## 6. Séquence Hello Robot

### 6.1 Prérequis
1. Isaac Sim 5.1.0 + Isaac Lab 2.3.x lancé sur Spark (headless, aarch64) avec scène go2_flat_ground.usd
2. Extension isaacsim.ros2.bridge activée (namespace v5.x)
3. OmniGraph configuré (publish /tf, /odom, /joint_states, /clock)
4. **Noeud Locomoteur lancé** (politique RL PPO go2_flat.pt chargée)
5. ROS2 Jazzy actif, FastDDS UDP configuré
6. Simulation en mode Play

### 6.2 Séquence d'exécution (scripts/hello_robot.py)

```
Étape 1 : Lancement du Noeud Locomoteur
    ros2 run robotics_env locomotion_controller
        → Charge la politique RL PPO (go2_flat.pt)
        → Subscribe /cmd_vel, /joint_states, /imu/data
        → Publish /joint_commands à 50 Hz
    ✓ Noeud Locomoteur prêt

Étape 2 : Initialisation SimAdapter
    Agent Jedi crée SimAdapter()
    SimAdapter.connect()
        → Init ROS2 node
        → Vérifie /clock (Isaac Sim tourne?)
        → Vérifie /odom (bridge actif?)
        → Vérifie /joint_commands (Noeud Locomoteur actif?)
    ✓ Connexion établie

Étape 3 : Lecture état initial
    state = SimAdapter.get_state()
    → Log: "Go2 position initiale: x=0, y=0, yaw=0"
    → Log: "Mode: IDLE"

Étape 4 : Commande de mouvement
    Agent Jedi décide: "avancer 1m"
    SimAdapter.move(Twist(linear_x=0.5))
        → Publie /cmd_vel {linear: {x: 0.5}, angular: {z: 0.0}}
        → Noeud Locomoteur reçoit /cmd_vel
        → Politique RL PPO calcule les torques 12 DOF
        → Publie /joint_commands vers Isaac Sim
        → Isaac Sim applique les torques via Articulation Controller
        → Le Go2 virtuel avance dans la simulation

    sleep(2.0)  # Avance pendant 2 secondes

Étape 5 : Arrêt
    SimAdapter.move(Twist())  # Vitesse zéro
    state = SimAdapter.get_state()
    → Log: "Go2 position finale: x≈1.0, y≈0, yaw≈0"

Étape 6 : Rotation
    SimAdapter.move(Twist(angular_z=0.5))
        → Le Noeud Locomoteur traduit en pattern de marche rotatif
        → Le Go2 tourne sur place
    sleep(2.0)
    SimAdapter.move(Twist())

Étape 7 : Vérification
    final_state = SimAdapter.get_state()
    → Assert: position a changé vs position initiale
    → Log: "✅ Hello Robot réussi! Le Go2 a bougé dans Isaac Sim."

Étape 8 : Déconnexion
    SimAdapter.disconnect()
    → Publie Twist(0,0,0) de sécurité
    → Shutdown ROS2 node
```

### 6.3 Critère de succès Sprint 1
Le script hello_robot.py s'exécute sans erreur et le Go2 virtuel se déplace visiblement dans Isaac Sim. Les logs confirment un changement de position entre l'état initial et l'état final. Le Noeud Locomoteur traduit correctement les vélocités en mouvements articulés.

---

## 7. Risques et Mitigations

| # | Risque | Impact | Probabilité | Mitigation |
|---|--------|--------|-------------|------------|
| R1 | PhysX GPU = CPU-only sur DGX Spark aarch64 | Performance | Confirmé | Bug connu NVIDIA (forum actif). Simulations physiques plus lentes. Acceptable pour Sprint 1. Monitorer les fix NVIDIA |
| R2 | Latence FastDDS UDP multi-machine > 50ms | Performance | Moyen | Tester shared memory d'abord (même machine). Profiler avec ros2 topic hz. Ajuster QoS si besoin |
| R3 | OmniGraph config complexe pour Go2 12 DOF | Retard | Moyen | Utiliser l'asset Go2 natif d'Isaac Sim (pré-configuré). Patcher namespace omni.isaac → isaacsim pour v5.x |
| R4 | URDF meshes .obj non supportés sur aarch64 | Retard | Moyen | go2_description utilise des meshes DAE (supportés). Vérifier à l'import. Convertir .obj → .usd si besoin |
| R5 | Conflit DDS : FastDDS (ROS2) vs CycloneDDS (unitree_sdk2) | Bloquant Phase 2 | Moyen | Phase 1 = FastDDS uniquement. Phase 2 : bridge DDS ou Domain ID séparé |
| R6 | Python async + rclpy spin conflict | Bug | Moyen | Utiliser MultiThreadedExecutor de rclpy. Spin dans thread séparé. Callbacks thread-safe |
| R7 | Pas de livestreaming Isaac Sim sur aarch64 | Workflow | Confirmé | Limitation connue. Utiliser headless + logs/screenshots. Visualisation via RViz2 sur machine distante |
| R8 | Politique RL PPO isaac-go2-ros2 (v4.5) à adapter pour Isaac Sim 5.1 | Retard | Moyen | Réentraîner via Isaac Lab 2.3.x si incompatible. Formats poids PyTorch portables entre versions |
| R9 | Import OBJ non supporté sur aarch64 (impact URDF) | Retard | Faible | go2_description = meshes DAE. Pas d'impact sauf assets tiers. Convertir via usd_converter si besoin |

---

## 8. Note UnifoLM-VLA-0

### 8.1 Présentation
**UnifoLM-VLA-0** (Vision-Language-Action) est un modèle de fondation open-source développé par Unitree (github.com/unitreerobotics/unifolm-vla). Il permet à un robot de comprendre des instructions en langage naturel et de les traduire en actions motrices à partir de la vision.

### 8.2 Architecture VLA
```
Entrée: Image caméra + Instruction texte ("avance vers la porte")
   │
   ▼
┌──────────────────────┐
│  Vision Encoder      │  ← Perception visuelle
│  (ViT ou similaire)  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Language Model       │  ← Compréhension instruction
│  (LLM fine-tuné)     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Action Head          │  ← Génération commandes motrices
│  (MLP → joint cmds)  │
└──────────────────────┘
           │
           ▼
Sortie: Actions bas niveau (joint velocities / positions)
```

### 8.3 Intégration future avec Agent Jedi
Dans notre architecture 3 couches, UnifoLM-VLA-0 pourrait s'intégrer de deux manières :

**Option A — VLA comme module du Cerveau (recommandée)**
```
Agent Jedi (planning haut niveau)
    │
    ├── Décision stratégique: "va chercher l'objet rouge"
    │
    ▼
UnifoLM-VLA-0 (Couche 1, sous-module)
    │
    ├── Entrée: image caméra + instruction Jedi
    ├── Sortie: séquence de Twist commands
    │
    ▼
RobotAdapter.move() (Couche 2) → Noeud Locomoteur → Isaac Sim
```
L'agent Jedi reste le décideur stratégique. VLA agit comme un "réflexe" visuomoteur pour les tâches de manipulation et navigation fine.

**Option B — VLA comme Adapter alternatif**
```
Agent Jedi → VLAAdapter(RobotAdapter) → Robot directement (bypass Noeud Locomoteur)
```
Le VLA bypass le SimAdapter et le Noeud Locomoteur pour contrôler directement les joints. Moins modulaire mais plus performant pour les tâches end-to-end.

### 8.4 Prérequis pour intégration VLA
- Caméra ROS2 fonctionnelle (/camera/color/image_raw)
- GPU suffisant pour inférence (Orin NX sur Go2 EDU Plus, ou Spark)
- Dataset de fine-tuning si tâches spécifiques
- Phase 3 minimum (après validation sim + réel)

---

## Annexe : Dépendances d'installation Sprint 1

### Sur serveur DGX Spark (aarch64 GB10)
```bash
# 1. ROS2 Jazzy (tarball arm64 officiel, install locale)
# Voir script: scripts/install_ros2_humble.sh
# Installe dans /home/panda/robotics/ros2/
source /home/panda/robotics/ros2/ros2-linux/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# 2. Isaac Sim 5.1.0 (pip aarch64 depuis pypi.nvidia.com)
python3.11 -m venv /home/panda/robotics/isaac/venv
source /home/panda/robotics/isaac/venv/bin/activate
pip install "isaacsim[all]==5.1.0" --extra-index-url https://pypi.nvidia.com

# 3. PyTorch 2.9.0 aarch64 + CUDA 13.0
pip install torch==2.9.0 --index-url https://download.pytorch.org/whl/cu130

# 4. Isaac Lab 2.3.x (depuis source, branche release/2.3.0)
cd /home/panda/robotics/isaac/
git clone https://github.com/isaac-sim/IsaacLab.git
cd IsaacLab && git checkout origin/release/2.3.0
./isaaclab.sh --install

# 5. Fix aarch64 OpenMP (requis)
export LD_PRELOAD="$LD_PRELOAD:/lib/aarch64-linux-gnu/libgomp.so.1"

# 6. Extension ROS2 bridge (namespace v5.x)
# isaacsim.ros2.bridge (activée par défaut avec isaacsim[all])

# 7. URDF Go2 (meshes DAE, compatibles aarch64)
git clone https://github.com/Unitree-Go2-Robot/go2_description.git robotics_env/sim/urdf/go2_description

# 8. Politique RL PPO (depuis isaac-go2-ros2, à adapter pour 5.1)
# Copier/réentraîner dans robotics_env/locomotion/policies/go2_flat.pt
```

### Mode headless (obligatoire sur Spark aarch64)
Isaac Sim tourne exclusivement en **headless** sur DGX Spark.
- Pas de livestreaming (limitation aarch64 connue)
- Visualisation via RViz2 sur machine distante ou Vision Pro (topics ROS2)
- `isaacsim --headless` pour lancer la simulation

### Config FastDDS multi-machine (ros/config/fastdds.xml)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<dds>
  <profiles>
    <transport_descriptors>
      <transport_descriptor>
        <transport_id>udp_transport</transport_id>
        <type>UDPv4</type>
      </transport_descriptor>
    </transport_descriptors>
    <participant profile_name="default_participant" is_default_profile="true">
      <rtps>
        <userTransports>
          <transport_id>udp_transport</transport_id>
        </userTransports>
        <useBuiltinTransports>false</useBuiltinTransports>
      </rtps>
    </participant>
  </profiles>
</dds>
```

---

## Changelog
- **v1.0** (2026-02-26) : Version initiale
- **v1.1** (2026-02-27) : Revue CEO — 3 modifications :
  - MODIF 1 : Isaac Sim 5.1 → 4.5.0 + Isaac Lab 2.1.0 (compatibilité garantie)
  - MODIF 2 : Ajout Noeud Locomoteur (politique RL PPO) entre SimAdapter et Isaac Sim
  - MODIF 3 : Monorepo isolé dans /robotics_env/ (séparé de l'infra agents)
- **v1.2** (2026-02-27) : Correction aarch64 — Stack DGX Spark :
  - Isaac Sim 4.5.0 → **5.1.0** (4.5 n'existe pas en aarch64)
  - Isaac Lab 2.1.0 → **2.3.x** (compatible 5.1.0)
  - Python 3.10 → **3.11** (requis par Isaac Sim 5.x)
  - Extension omni.isaac.ros2_bridge → **isaacsim.ros2.bridge** (namespace v5.x)
  - Ajout PyTorch 2.9.0 cu130 + CUDA 13.0 + Driver 580.126
  - 9 risques mis à jour (PhysX CPU-only, headless, meshes OBJ, politique RL portage)
  - Mode headless obligatoire documenté
- **v1.3** (2026-02-27) : Stack aarch64 finale :
  - Spark = **Ubuntu 24.04.3 Noble** (confirmé SSH) → **ROS2 Jazzy** (pas Humble)
  - Humble incompatible Ubuntu 24.04 — Jazzy = LTS natif pour Noble
  - Meshes Go2 = **100% DAE** (confirmé), aucun .obj, pas de conversion nécessaire
  - Python Spark = **3.12.3** (natif Ubuntu 24.04)

---

*Document validé par le CEO — Phase STRIPING (code) autorisée.*

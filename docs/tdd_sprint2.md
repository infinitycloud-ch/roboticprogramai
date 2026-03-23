# Technical Design Document — Sprint 2 : Cognitive Awakening
## Couches 2 & 3 — SimAdapter + Noeud Locomoteur

**Version** : 2.0
**Date** : 2026-02-27
**Auteur** : DEV (Agent Développeur)
**Validé par** : CEO
**Périmètre** : Couches 2 (Interface Corps) et 3 (Monde) UNIQUEMENT

---

## 1. Objectif Sprint 2

Rendre le Go2 physiquement opérationnel dans Isaac Sim sur le DGX Spark :
- Lancer la scène Isaac Sim headless sur le Spark (<SPARK_IP>)
- Valider la communication ROS2 FastDDS Mac↔Spark en réseau
- Implémenter le Noeud Locomoteur (RL PPO) qui traduit /cmd_vel en mouvements articulaires
- Fournir une API Contract claire pour que les agents MonoCLI puissent piloter le robot

**Livrable final** : `hello_robot.py` exécuté depuis le Mac, le Go2 marche fluidement dans Isaac Sim sur le Spark.

---

## 2. Périmètre strict (Directive CEO)

| NOUS (RoboticProgramAI) | MonoCLI (ses propres agents) |
|---|---|
| SimAdapter (code + API) | Skills mono_read_sensors / mono_move_robot |
| Noeud Locomoteur RL | Profil Jedi Go2 Robotics |
| launch_scene.py sur Spark | Playbooks YAML |
| FastDDS config réseau | Config Groq API |
| hello_robot.py E2E | Cluster Simulation_Memory |
| API Contract (documentation) | Intégration tool_executor |

**INTERDIT** : Modifier code MonoCLI, SQLite, tools.json, profils, clusters.

---

## 3. Architecture cible fin Sprint 2

```
Mac (développement)                         DGX Spark (<SPARK_IP>)
┌─────────────────────┐    FastDDS/UDP     ┌──────────────────────────────────────┐
│                     │    ←───────────→   │                                      │
│  hello_robot.py     │                    │  Isaac Sim 5.1.0 (headless)          │
│  ou MonoCLI agents  │                    │  ├─ launch_scene.py                  │
│       │             │                    │  ├─ Go2 URDF + Ground Plane          │
│       ▼             │                    │  └─ OmniGraph ROS2 Bridge            │
│  SimAdapter         │                    │      publie: /clock /tf /odom        │
│  (publie /cmd_vel)  │                    │              /joint_states /imu/data  │
│       │             │                    │      souscrit: /joint_commands        │
│       │ ROS2        │                    │                    ▲                  │
│       ▼             │                    │                    │                  │
│  ───────────────────┼──── /cmd_vel ────→ │  Noeud Locomoteur                    │
│                     │                    │  ├─ sub /cmd_vel (3D velocity)        │
│                     │                    │  ├─ sub /joint_states (12 DOF)        │
│                     │                    │  ├─ sub /imu/data (orientation)       │
│                     │                    │  ├─ RL Policy: go2_flat.pt (PPO)      │
│                     │                    │  └─ pub /joint_commands (12 DOF pos)  │
└─────────────────────┘                    └──────────────────────────────────────┘
```

**Flux de données** :
1. SimAdapter (Mac) publie `geometry_msgs/Twist` sur `/cmd_vel`
2. Noeud Locomoteur (Spark) reçoit `/cmd_vel` + `/joint_states` + `/imu/data`
3. Noeud Locomoteur assemble le vecteur d'observation (48 dim) et exécute `go2_flat.pt`
4. Noeud Locomoteur publie `std_msgs/Float64MultiArray` sur `/joint_commands` (12 positions articulaires)
5. OmniGraph ArticulationController applique les positions au Go2 dans Isaac Sim

---

## 4. Phase 1 — Spark Ignition (Tickets #2094-#2097)

### 4.1 Lancer launch_scene.py sur Spark (#2094)

**Procédure** :
```bash
# Sur Spark (<SPARK_IP>)
ssh panda@<SPARK_IP>
source /home/panda/robotics/isaac_sim/activate.sh
cd /home/panda/robotics/robotics_env/sim/
python3 launch_scene.py --headless
```

**Critères de succès** :
- Isaac Sim démarre sans erreur
- URDF Go2 importé à position (0, 0, 0.4)
- OmniGraph ROS2 bridge initialisé
- Pas de crash pendant 30s de simulation

**Risques** :
- PhysX GPU = CPU-only sur aarch64 (performance réduite mais fonctionnel)
- LD_PRELOAD libgomp nécessaire (déjà dans activate.sh)

### 4.2 Valider topics ROS2 sur Spark (#2095)

**Commandes de validation** :
```bash
# Sur Spark (autre terminal)
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# Vérifier les topics publiés
ros2 topic list
# Attendu : /clock /tf /odom /joint_states /imu/data /joint_commands

# Vérifier la fréquence
ros2 topic hz /clock        # ~30 Hz (rendering_dt)
ros2 topic hz /odom         # ~200 Hz (physics_dt)
ros2 topic hz /joint_states # ~200 Hz

# Vérifier le contenu
ros2 topic echo /odom --once
ros2 topic echo /joint_states --once
```

**Critères de succès** :
- 6 topics listés
- /clock publie régulièrement (Isaac Sim tourne)
- /odom contient pose (x,y,z) et twist (vx,vy,wz)
- /joint_states contient 12 positions et 12 velocités

### 4.3 Valider FastDDS Mac↔Spark (#2096)

**Prérequis** :
- Mac et Spark sur le même sous-réseau (<LAN_SUBNET>)
- ROS2 Jazzy installé sur le Mac (ou Docker)
- Même `ROS_DOMAIN_ID` (défaut: 0)

**Configuration FastDDS** (déjà dans `ros/config/fastdds.xml`) :
```xml
<transport_descriptors>
  <transport_descriptor>
    <transport_id>udpv4</transport_id>
    <type>UDPv4</type>
  </transport_descriptor>
</transport_descriptors>
```

**Validation depuis le Mac** :
```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE=/path/to/robotics_env/ros/config/fastdds.xml

ros2 topic list           # Doit voir les topics du Spark
ros2 topic echo /odom --once  # Doit recevoir des données
```

**Si les topics ne sont pas visibles** :
1. Vérifier firewall : `sudo ufw allow 7400:7500/udp` (ports DDS)
2. Vérifier multicast : `ping -c 1 239.255.0.1`
3. Fallback : configurer FastDDS en unicast avec IP explicite du Spark

### 4.4 hello_robot.py E2E réseau (#2097)

**Exécution** :
```bash
# Mac
cd ~//RoboticProgramAI/robotics_env/
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
python3 scripts/hello_robot.py
```

**Séquence attendue** :
1. SimAdapter.connect() → détecte /clock (Spark alive) + /odom (bridge actif)
2. get_state() → lit position initiale du Go2
3. move(Twist(linear_x=0.5)) → publie /cmd_vel
4. Attente 2s
5. move(Twist()) → stop
6. get_state() → lit position finale
7. Assert déplacement >= 0.1m

**NOTE IMPORTANTE** : Sans le Noeud Locomoteur (Phase 4), /cmd_vel n'est pas traduit en mouvements articulaires. Le Go2 ne bougera PAS à cette étape. hello_robot.py FAIL attendu à ce stade.

**Validation Phase 1 (sans locomotion)** :
- connect() réussit (détecte /clock et /odom)
- get_state() retourne des données valides
- move() publie sans erreur sur /cmd_vel
- Le test peut FAIL sur le déplacement — c'est NORMAL

---

## 5. Phase 2 — API Contract SimAdapter (#2099, #2106)

### 5.1 API Contract (STRAT le rédige, #2099)

Document décrivant comment importer et utiliser SimAdapter depuis n'importe quel agent Python (y compris MonoCLI).

**API publique** :
```python
from adapters.sim_adapter import SimAdapter
from adapters.types import Twist, RobotState, SensorData, RobotMode

# Lifecycle
adapter = SimAdapter(node_name="my_agent")
await adapter.connect()       # → ConnectionError | TimeoutError
await adapter.disconnect()    # → envoie Twist(0) avant shutdown

# Commandes
await adapter.move(Twist(linear_x=0.5, linear_y=0.0, angular_z=0.0))
await adapter.set_mode(RobotMode.WALKING)
await adapter.emergency_stop()  # → Twist(0) + mode EMERGENCY_STOP

# Lecture
state: RobotState = await adapter.get_state()
sensors: SensorData = await adapter.get_sensors()
connected: bool = adapter.is_connected

# Dataclasses retournées
state.pose        # Pose(x, y, z, roll, pitch, yaw)
state.velocity    # Twist(linear_x, linear_y, angular_z)
state.joint_positions   # tuple(12 floats) — FL_hip..RR_calf
state.joint_velocities  # tuple(12 floats)
state.mode        # RobotMode enum
state.timestamp   # float (secondes)
sensors.imu_orientation          # (qx, qy, qz, qw)
sensors.imu_angular_velocity     # (wx, wy, wz)
sensors.imu_linear_acceleration  # (ax, ay, az)
sensors.foot_contacts            # (FL, FR, RL, RR) booleans
```

**Prérequis pour l'import** :
```python
import sys
sys.path.insert(0, "/path/to/robotics_env")
# OU
# pip install -e /path/to/robotics_env  (via pyproject.toml)
```

**Prérequis ROS2** :
```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

### 5.2 Valider SimAdapter importable standalone (#2106)

**Test** :
```python
# test_api_contract.py
import asyncio
from adapters.sim_adapter import SimAdapter
from adapters.types import Twist, RobotState, SensorData

async def test():
    adapter = SimAdapter(node_name="api_test")
    assert not adapter.is_connected
    # connect() testé seulement si Isaac Sim tourne
    # Sinon vérifier que TimeoutError est levée proprement
```

**Actions DEV** :
- Vérifier que `pyproject.toml` expose le bon entry point
- Vérifier que `sys.path` n'est pas nécessaire si installé avec `pip install -e .`
- Ajouter `__init__.py` exports propres si manquants

---

## 6. Phase 4 — Noeud Locomoteur (Tickets #2107-#2110)

### 6.1 Recherche go2_flat.pt (#2107)

**Source** : Projet isaac-go2-ros2 (Zhefan-Xu), déjà cloné sur Spark.

```bash
# Sur Spark
ls /home/panda/robotics/isaac_sim/references/isaac-go2-ros2/ckpts/unitree_go2/
```

**Fichier attendu** : checkpoint TorchScript (.pt) exporté par RSL-RL.

**Architecture du modèle RL PPO (Isaac Lab Go2 Flat)** :

| Composant | Valeur |
|---|---|
| Algorithme | PPO (Proximal Policy Optimization) via RSL-RL |
| Réseau Actor | MLP 48 → 128 → 128 → 128 → 12 (ELU) |
| Observations | 48 dimensions (flat, sans height_scan) |
| Actions | 12 dimensions (offsets position articulaire) |
| Scale action | 0.25 (target = default_pos + 0.25 * action) |
| Fréquence | 50 Hz |

**Vecteur d'observation (48 dim)** :

| Terme | Dim | Source ROS2 |
|---|---|---|
| base_ang_vel | 3 | /imu/data → angular_velocity (body frame) |
| projected_gravity | 3 | /imu/data → orientation → projection gravité |
| velocity_commands | 3 | /cmd_vel → (linear.x, linear.y, angular.z) |
| joint_pos (relatif) | 12 | /joint_states → position - default_pos |
| joint_vel | 12 | /joint_states → velocity |
| last_action | 12 | action précédente (buffer interne) |

**Ordre des joints (12 DOF)** :
```
FL_hip, FL_thigh, FL_calf,
FR_hip, FR_thigh, FR_calf,
RL_hip, RL_thigh, RL_calf,
RR_hip, RR_thigh, RR_calf
```

**Positions par défaut Go2 (radians)** :
```python
DEFAULT_JOINT_POS = [
    0.1,  0.8, -1.5,   # FL: hip, thigh, calf
    -0.1, 0.8, -1.5,   # FR
    0.1,  1.0, -1.5,   # RL
    -0.1, 1.0, -1.5,   # RR
]
```

**Si go2_flat.pt introuvable dans isaac-go2-ros2** :
1. Alternative : go2_omniverse (abizovnuralem) — même architecture RSL-RL
2. Dernier recours : entraîner depuis zéro via Isaac Lab env `Isaac-Velocity-Flat-Unitree-Go2-v0`

### 6.2 Coder le Noeud Locomoteur (#2108)

**Fichier** : `robotics_env/locomotion/locomotion_controller.py`

**Architecture** :
```python
class LocomotionController:
    """Noeud ROS2 : /cmd_vel → RL policy (go2_flat.pt) → /joint_commands."""

    CONTROL_FREQ_HZ = 50
    NUM_JOINTS = 12
    ACTION_SCALE = 0.25

    def __init__(self, policy_path, node_name="locomotion_controller"):
        # ROS2 node
        # Subscribers: /cmd_vel, /joint_states, /imu/data
        # Publisher: /joint_commands (Float64MultiArray)
        # Timer: 50 Hz control loop
        # Policy: torch.jit.load(policy_path)
        # State buffers: cmd_vel, joint_pos, joint_vel, imu_ori, imu_gyro, last_action

    def start(self):
        """Init rclpy, create node, load policy, start spin."""
        import rclpy
        import torch
        self._policy = torch.jit.load(self._policy_path)
        self._policy.eval()
        # Create subs/pub
        # Create timer (1/50 Hz = 20ms)
        # Start spin in daemon thread

    def stop(self):
        """Shutdown: publish zero torques, destroy node."""

    def _on_cmd_vel(self, msg):
        """Callback /cmd_vel → update velocity commands buffer."""

    def _on_joint_states(self, msg):
        """Callback /joint_states → update joint positions/velocities."""

    def _on_imu(self, msg):
        """Callback /imu/data → update orientation + angular velocity."""

    def _control_loop(self):
        """50 Hz: assemble obs → policy forward → publish joint commands."""
        # 1. Assembler observation (48 dim)
        obs = self._build_observation()

        # 2. Inférence policy
        with torch.no_grad():
            obs_tensor = torch.tensor(obs, dtype=torch.float32).unsqueeze(0)
            action = self._policy(obs_tensor).squeeze(0).numpy()

        # 3. Calculer positions cibles
        target_pos = DEFAULT_JOINT_POS + ACTION_SCALE * action

        # 4. Publier sur /joint_commands
        msg = Float64MultiArray()
        msg.data = target_pos.tolist()
        self._joint_cmd_pub.publish(msg)

        # 5. Sauvegarder last_action
        self._last_action = action

    def _build_observation(self) -> list:
        """Assembler le vecteur 48-dim depuis les buffers ROS2."""
        # projected_gravity = quaternion → rotation matrix → [0,0,-9.81] en body frame
        # joint_pos_rel = joint_pos - DEFAULT_JOINT_POS
        # joint_vel_scaled = joint_vel * 0.05
        # ang_vel_scaled = ang_vel * 0.2
        obs = []
        obs.extend(self._ang_vel_scaled)        # 3
        obs.extend(self._projected_gravity)      # 3
        obs.extend(self._cmd_vel)                # 3
        obs.extend(self._joint_pos_rel)          # 12
        obs.extend(self._joint_vel_scaled)       # 12
        obs.extend(self._last_action)            # 12  -- hint: init zeros
        return obs  # 45 ou 48 selon la policy
```

**QoS Profiles** :
- `/cmd_vel` subscriber : RELIABLE, depth=10 (même QoS que SimAdapter publisher)
- `/joint_states`, `/imu/data` subscribers : BEST_EFFORT, depth=1 (dernière valeur seulement)
- `/joint_commands` publisher : RELIABLE, depth=10

**Threading** : Même pattern que SimAdapter — `MultiThreadedExecutor` dans un thread daemon. Timer ROS2 pour le contrôle à 50 Hz.

**Sécurité** :
- Si aucun /cmd_vel reçu depuis >500ms → publier positions par défaut (robot debout, pas de mouvement)
- Clamp des actions : limiter les positions articulaires aux limites physiques du Go2
- Vérifier que le policy output a bien 12 dimensions

### 6.3 Script de lancement Spark (#2109)

**Fichier** : `robotics_env/scripts/launch_locomotion.py`

```bash
# Sur Spark — Terminal 1 : Isaac Sim
source /home/panda/robotics/isaac_sim/activate.sh
python3 /home/panda/robotics/robotics_env/sim/launch_scene.py --headless

# Sur Spark — Terminal 2 : Noeud Locomoteur
source /home/panda/robotics/isaac_sim/activate.sh
python3 /home/panda/robotics/robotics_env/scripts/launch_locomotion.py
```

**Validation** :
```bash
# Terminal 3 Spark
ros2 topic hz /joint_commands   # ~50 Hz
ros2 topic echo /joint_commands --once  # 12 valeurs float
```

### 6.4 Test E2E final Sprint 2 (#2110)

**Scénario complet** :
1. Spark Terminal 1 : `launch_scene.py --headless` (Isaac Sim + OmniGraph)
2. Spark Terminal 2 : `launch_locomotion.py` (Noeud Locomoteur RL)
3. Mac : `hello_robot.py` (SimAdapter → /cmd_vel)

**Critères de succès** :
- hello_robot.py PASS (déplacement >= 0.1m)
- Le Go2 se déplace fluidement (pas de jitter, pas de chute)
- Pas de messages d'erreur ROS2
- Latence /cmd_vel → mouvement < 100ms

---

## 7. Dépendances Python à ajouter

### pyproject.toml (mise à jour)

```toml
[project]
requires-python = ">=3.10"
dependencies = [
    "numpy",
    "torch",
]

[project.optional-dependencies]
ros = []  # rclpy via system ROS2 packages
sim = [
    "isaacsim[all]==5.1.0",
]
dev = [
    "pytest",
    "pytest-asyncio",
]
```

**Note** : `torch` est la seule dépendance critique pour le Noeud Locomoteur. Sur le Spark aarch64, PyTorch 2.9.0+cu130 est déjà installé dans le venv Isaac Sim.

### Packages ROS2 nécessaires (apt, pas pip)

```
ros-jazzy-geometry-msgs    # Twist
ros-jazzy-sensor-msgs      # JointState, Imu
ros-jazzy-nav-msgs         # Odometry
ros-jazzy-std-msgs         # Float64MultiArray
ros-jazzy-rosgraph-msgs    # Clock
```

Déjà inclus dans `ros-jazzy-desktop` (installé Sprint 1).

---

## 8. Risques et mitigations

| # | Risque | Impact | Mitigation |
|---|---|---|---|
| R1 | go2_flat.pt introuvable dans isaac-go2-ros2 | Bloquant Phase 4 | Chercher dans go2_omniverse, ou entraîner via Isaac Lab |
| R2 | Dimensions obs policy ≠ 48 | Crash runtime | Inspecter policy input shape avec torch.jit.load, adapter build_observation |
| R3 | FastDDS multicast bloqué par le routeur | Bloquant Phase 1 | Config unicast explicite dans fastdds.xml |
| R4 | PhysX CPU-only trop lent sur Spark | Sim instable | Réduire physics_dt à 1/100 si nécessaire |
| R5 | Latence réseau Mac↔Spark > 100ms | Mouvement saccadé | Mesurer latence, ajuster buffer sizes |
| R6 | OmniGraph /joint_commands utilise effortCommand | Actions = positions, pas torques | Vérifier et ajuster le mapping OmniGraph (positionCommand vs effortCommand) |
| R7 | Ordre des joints Isaac Sim ≠ policy | Go2 fait n'importe quoi | Log joint_names du /joint_states, mapper l'ordre |
| R8 | ROS2 Jazzy non installé sur Mac | Bloquant Phase 1 | Docker ros:jazzy ou install native via brew/apt |

### R6 — Point critique OmniGraph

Dans `launch_scene.py`, l'OmniGraph connecte `/joint_commands` à `ArticulationController.inputs:effortCommand`. Or la policy RL produit des **positions articulaires** (pas des torques/efforts).

**Action requise** : Modifier la connexion OmniGraph pour utiliser `positionCommand` au lieu de `effortCommand` :
```python
# AVANT (Sprint 1)
("SubscribeJointCmd.outputs:data", "ArticulationController.inputs:effortCommand"),

# APRES (Sprint 2)
("SubscribeJointCmd.outputs:data", "ArticulationController.inputs:positionCommand"),
```

---

## 9. Ordre d'exécution des tickets

```
Phase 1 (séquentiel) :
  #2094 → #2095 → #2096 → #2097

Phase 2 (parallélisable avec Phase 1) :
  #2099 (STRAT) + #2106 (DEV)

Phase 4 (après Phase 1) :
  #2107 → #2108 → #2109 → #2110
```

**Estimation** :
- Phase 1 : Nécessite accès SSH au Spark + ROS2 sur Mac
- Phase 2 : Peut commencer immédiatement
- Phase 4 : Le gros morceau — recherche policy + implémentation + debug

---

## 10. Fichiers à créer / modifier

| Fichier | Action | Ticket |
|---|---|---|
| `locomotion/locomotion_controller.py` | Réécriture complète (stub → réel) | #2108 |
| `locomotion/policies/go2_flat.pt` | Copier depuis isaac-go2-ros2 | #2107 |
| `scripts/launch_locomotion.py` | Nouveau fichier | #2109 |
| `sim/launch_scene.py` | Patch effortCommand → positionCommand | #2108 |
| `pyproject.toml` | Mettre à jour versions (5.1.0) | #2106 |
| `tests/test_locomotion.py` | Adapter aux vrais tests | #2109 |
| `ros/config/fastdds.xml` | Éventuellement unicast si multicast KO | #2096 |

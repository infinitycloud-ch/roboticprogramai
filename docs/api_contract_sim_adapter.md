# API Contract — SimAdapter
## Pour agents externes (MonoCLI, scripts, tests)

**Version** : 1.0
**Date** : 2026-02-27
**Auteur** : STRAT (RoboticProgramAI)

---

## 1. Qu'est-ce que SimAdapter ?

SimAdapter est le pont Python ↔ ROS2 qui contrôle un Unitree Go2 virtuel dans NVIDIA Isaac Sim.
Il expose une API async simple : `move()`, `get_state()`, `get_sensors()`, `emergency_stop()`.

Le SimAdapter **ne calcule pas** la cinématique. Il publie des commandes de vélocité sur `/cmd_vel` via ROS2. Le Noeud Locomoteur (RL PPO) traduit ces vélocités en mouvements articulaires.

---

## 2. Prérequis

### Environnement ROS2
```bash
source /opt/ros/jazzy/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

### Isaac Sim doit tourner
Sur le DGX Spark (<SPARK_IP>) :
```bash
source /home/panda/robotics/isaac_sim/activate.sh
python3 /home/panda/robotics/robotics_env/sim/launch_scene.py --headless
```

### Import Python
```python
import sys
sys.path.insert(0, '/path/to/robotics_env')

from adapters.sim_adapter import SimAdapter
from adapters.types import Twist, Pose, RobotState, SensorData, RobotMode
```

Alternativement, si installé avec pip :
```bash
pip install -e /path/to/robotics_env
```

---

## 3. API Publique

### Lifecycle

```python
adapter = SimAdapter(node_name='mon_agent')
await adapter.connect()       # Lève ConnectionError ou TimeoutError
await adapter.disconnect()    # Envoie Twist(0) puis shutdown
```

- `connect()` attend que `/clock` et `/odom` soient reçus (timeout: 10s et 5s)
- `disconnect()` envoie automatiquement un Twist nul (sécurité)

### Commandes de mouvement

```python
# Avancer à 0.5 m/s
await adapter.move(Twist(linear_x=0.5))

# Tourner à gauche
await adapter.move(Twist(angular_z=0.3))

# Déplacement latéral
await adapter.move(Twist(linear_y=0.2))

# Combiné : avancer + tourner
await adapter.move(Twist(linear_x=0.5, angular_z=0.1))

# Arrêter
await adapter.move(Twist())  # Tout à zéro
```

**Unités** :
- `linear_x`, `linear_y` : mètres/seconde
- `angular_z` : radians/seconde

**Limites recommandées** :
- linear_x : [-1.0, 1.0] m/s
- linear_y : [-0.5, 0.5] m/s
- angular_z : [-1.0, 1.0] rad/s

### Arrêt d'urgence

```python
await adapter.emergency_stop()  # Twist(0) + mode EMERGENCY_STOP
await adapter.set_mode(RobotMode.WALKING)  # Reprendre
```

### Lecture d'état

```python
state: RobotState = await adapter.get_state()

# Position 3D + orientation
state.pose.x, state.pose.y, state.pose.z     # mètres
state.pose.roll, state.pose.pitch, state.pose.yaw  # radians

# Vélocité actuelle
state.velocity.linear_x   # m/s
state.velocity.linear_y   # m/s
state.velocity.angular_z  # rad/s

# Articulations (12 DOF)
state.joint_positions      # tuple de 12 floats (radians)
state.joint_velocities     # tuple de 12 floats (rad/s)

# Métadonnées
state.mode                 # RobotMode enum
state.timestamp            # float (secondes sim)
```

### Lecture capteurs

```python
sensors: SensorData = await adapter.get_sensors()

sensors.imu_orientation           # (qx, qy, qz, qw) quaternion
sensors.imu_angular_velocity      # (wx, wy, wz) rad/s
sensors.imu_linear_acceleration   # (ax, ay, az) m/s²
sensors.foot_contacts             # (FL, FR, RL, RR) booleans
sensors.timestamp                 # float
```

### Propriétés

```python
adapter.is_connected  # bool — True si ROS2 actif et topics reçus
```

---

## 4. Dataclasses de référence

```python
@dataclass(frozen=True)
class Twist:
    linear_x: float = 0.0    # m/s
    linear_y: float = 0.0    # m/s
    angular_z: float = 0.0   # rad/s

@dataclass(frozen=True)
class Pose:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

class RobotMode(Enum):
    IDLE = 'idle'
    WALKING = 'walking'
    STANDING = 'standing'
    EMERGENCY_STOP = 'emergency_stop'

@dataclass(frozen=True)
class RobotState:
    pose: Pose
    velocity: Twist
    joint_positions: tuple[float, ...] = ()
    joint_velocities: tuple[float, ...] = ()
    mode: RobotMode = RobotMode.IDLE
    battery_percent: float | None = None
    timestamp: float = 0.0

@dataclass(frozen=True)
class SensorData:
    imu_orientation: tuple[float, float, float, float] = (0,0,0,1)
    imu_angular_velocity: tuple[float, float, float] = (0,0,0)
    imu_linear_acceleration: tuple[float, float, float] = (0,0,0)
    foot_contacts: tuple[bool, bool, bool, bool] = (False,False,False,False)
    lidar_points: np.ndarray | None = None
    timestamp: float = 0.0
```

---

## 5. Exemple complet

```python
import asyncio
from adapters.sim_adapter import SimAdapter
from adapters.types import Twist

async def main():
    adapter = SimAdapter(node_name='monocli_go2')
    
    try:
        await adapter.connect()
        print('Connecté à Isaac Sim')
        
        # Lire position initiale
        state = await adapter.get_state()
        print(f'Position: ({state.pose.x:.2f}, {state.pose.y:.2f})')
        
        # Avancer 2 secondes
        await adapter.move(Twist(linear_x=0.5))
        await asyncio.sleep(2.0)
        
        # Arrêter
        await adapter.move(Twist())
        
        # Lire position finale
        state = await adapter.get_state()
        print(f'Position finale: ({state.pose.x:.2f}, {state.pose.y:.2f})')
        
    finally:
        await adapter.disconnect()

asyncio.run(main())
```

---

## 6. Erreurs possibles

| Exception | Cause | Solution |
|---|---|---|
| `ConnectionError('rclpy non disponible')` | ROS2 pas sourcé | `source /opt/ros/jazzy/setup.bash` |
| `TimeoutError('Timeout en attente de /clock')` | Isaac Sim pas lancé | Lancer `launch_scene.py` sur Spark |
| `TimeoutError('Timeout en attente de /odom')` | Bridge ROS2 pas actif | Vérifier extension isaacsim.ros2.bridge |
| `ConnectionError('SimAdapter non connecté')` | Appel avant connect() | Appeler `await adapter.connect()` d'abord |

---

## 7. Topics ROS2 utilisés

| Topic | Type | Direction | QoS |
|---|---|---|---|
| `/cmd_vel` | geometry_msgs/Twist | SimAdapter → ROS2 | RELIABLE, depth=10 |
| `/odom` | nav_msgs/Odometry | Isaac Sim → SimAdapter | BEST_EFFORT, depth=10 |
| `/joint_states` | sensor_msgs/JointState | Isaac Sim → SimAdapter | BEST_EFFORT, depth=10 |
| `/imu/data` | sensor_msgs/Imu | Isaac Sim → SimAdapter | BEST_EFFORT, depth=10 |
| `/clock` | rosgraph_msgs/Clock | Isaac Sim → SimAdapter | BEST_EFFORT, depth=10 |

---

## 8. Notes pour les agents MonoCLI

- SimAdapter est **thread-safe** : les callbacks ROS2 tournent dans un thread daemon séparé
- Toutes les méthodes sont **async** : utiliser `await` obligatoirement
- Le `connect()` bloque jusqu'à réception de `/clock` et `/odom` (max ~15s)
- Après `move(Twist(...))`, le robot continue à cette vitesse. Il faut envoyer `move(Twist())` pour arrêter.
- `get_state()` retourne le DERNIER état reçu (pas de requête ROS2 supplémentaire)
- Pour un skill `mono_read_sensors` : appeler `get_state()` + `get_sensors()` et sérialiser en JSON
- Pour un skill `mono_move_robot` : parser les paramètres JSON et appeler `move(Twist(...))`

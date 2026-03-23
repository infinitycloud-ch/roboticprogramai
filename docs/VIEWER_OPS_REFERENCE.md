# Tactical Viewer — Document de Référence Opérationnel

## 1. Coordonnées & Rotations

### Systèmes de coordonnées
| Système | X | Y | Z |
|---------|---|---|---|
| **Isaac Sim** | Avant (+) | Gauche (+) | Haut (+) |
| **Three.js** | Droite (+) | Haut (+) | Arrière (-) |

### Mapping Isaac → Three.js
```
Three.js X = Isaac X
Three.js Y = Isaac Z
Three.js Z = -Isaac Y
```

### Rotations (yaw)
| Objet face à | Isaac yaw | Three.js rotationY |
|--------------|-----------|-------------------|
| +X (avant) | 0 | 0 |
| -X (arrière) | pi (180°) | pi |
| +Y (gauche) | pi/2 (90°) | pi/2 |
| -Y (droite) | -pi/2 | -pi/2 |

**REGLE** : Le Go2 spawn face +X (yaw=0). Pour qu'un objet fasse face au robot, mettre yaw=pi.

## 2. Positions Définitives — Use Case 01

| Objet | Isaac (X, Y, Z) | Description |
|-------|-----------------|-------------|
| Go2 | (0, 0, 0) | Entrée, face +X |
| Docteur | (5, 0, 0) | Face robot (yaw=pi), 5m |
| Lit | (7, -2.5, 0) | Droite du docteur |
| Monitor | (9, -2.5, 0) | Près du lit, 2m gap |
| BestFriend | (5, 2.5, 0) | Gauche du docteur |
| Chaise | (10, 4, 0) | Coin arrière-gauche |

Chambre : 12x10m (X: 0→12, Y: -5→+5)
Trajectoire libre : (0,0) → (5,0), axe X

## 3. Comment Relancer le Viewer

**IMPORTANT** : Le HTML est généré UNE FOIS au démarrage du serveur Python. Un simple refresh Chrome ne suffit PAS pour voir les changements de code. Il faut TUER et RELANCER le processus.

### Commande de relance (via agent Spark)
```bash
# 1. Tuer le viewer actuel
lsof -ti :8080 | xargs -r kill -9
lsof -ti :9872 | xargs -r kill -9
sleep 2

# 2. Relancer (depuis /tmp pour éviter shadow types.py)
cd /tmp && nohup python3 -u /home/panda/robotics/robotics_env/sim/web_viewer.py > /tmp/web_viewer.log 2>&1 &

# 3. Vérifier
sleep 3 && curl -s http://localhost:8080/state | python3 -m json.tool
```

### Commande de relance Isaac Sim
```bash
# 1. Tuer la scène
pkill -f launch_hospital_scene.py
sleep 3

# 2. Relancer avec venv Isaac Sim (OBLIGATOIRE)
nohup bash -c 'export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1 && \
  source /home/panda/robotics/isaac_sim/activate.sh && \
  cd /tmp && python3 -u /home/panda/robotics/robotics_env/sim/launch_hospital_scene.py --headless' \
  > /tmp/hospital.log 2>&1 &

# 3. Attendre 40s puis vérifier
sleep 40 && tail -5 /tmp/hospital.log
```

### Vérification rapide
```bash
# État des processus
ps aux | grep -E 'launch_hospital|web_viewer' | grep -v grep

# État du viewer
curl -s http://localhost:8080/state | python3 -m json.tool

# Logs
tail -20 /tmp/hospital.log
tail -10 /tmp/web_viewer.log
```

## 4. Checklist Intégration Asset GLB

Chaque nouvel asset GLB dans le viewer DOIT suivre ces 9 points :

1. **METALNESS=0** : Traverser TOUS meshes, gérer `Array.isArray(material)` pour multi-material
2. **POSITION Y (pieds au sol)** : Recalculer bounding box → `model.position.y += -box.min.y`
3. **AUTO-SCALE** : `targetHeight / currentBBoxHeight` (humain=1.7m, animal=0.55m)
4. **LUMIERES** : AmbientLight(0xffffff, 2.0) + DirectionalLight(0xffffff, 1.5) + HemisphereLight
5. **Go2 = MeshBasicMaterial** : JAMAIS MeshStandardMaterial sur le stick-figure
6. **FALLBACK** : Primitive placeholder si GLB absent
7. **ROUTE HTTP** : `GET /assets/nom.glb`, Content-Type octet-stream, cache 1h
8. **STATE JSON** : Champ dans `/state` : `{pos:[x,y,z], active:true}`
9. **CLI ARGS** : `--nom-pos X Y Z` + `--nom-asset PATH`

## 5. Pipeline Assets 3D

### Source A — Apple USDZ (Mac)
```
USDZ → Blender CLI Mac → GLB → SCP Spark → /assets/custom/
```
```bash
# Conversion sur Mac
/opt/homebrew/bin/blender --background --python convert.py
# bpy.ops.wm.usd_import() + bpy.ops.export_scene.gltf(export_format='GLB')
```

### Source B — Flux+Hunyuan3D (Spark)
```
Génération IA sur Spark → GLB → /assets/custom/
```

### Stockage
```
/home/panda/robotics/assets/custom/
├── BestFriend.usdz    (8.2MB, original Apple)
├── BestFriend.glb     (7.9MB, converti Blender)
├── Doctor.glb         (8.9MB, Flux+Hunyuan3D)
├── hospital_bed.glb   (8.5MB, Flux+Hunyuan3D)
├── heart_monitor.glb  (9.1MB, Flux+Hunyuan3D)
└── visitor_chair.glb  (11MB, Flux+Hunyuan3D)
```

## 6. Erreurs Connues & Solutions

| Erreur | Cause | Solution |
|--------|-------|----------|
| Mesh GLB noir | metalness=1.0 par défaut | Force metalness=0, roughness=0.8 via traverse |
| Mesh multi-material noir | material est un Array | `Array.isArray(mat) ? mat : [mat]` puis forEach |
| Modèle enfoncé dans le sol | Origine au centre du mesh | Bounding box + offset Y |
| Go2 trop bright | MeshStandardMaterial affecté par lumières | Utiliser MeshBasicMaterial |
| ModuleNotFoundError: isaaclab | venv pas activé | `source activate.sh` avant lancement |
| omni.client bloque | Nucleus pas running | Utiliser S3 URLs ou --skip-assets |
| Refresh Chrome pas de changement | HTML généré au démarrage | RELANCER le processus Python |
| usd-core install fail Spark | Pas de wheel aarch64 | Convertir sur Mac avec Blender |

## 7. URLs & Ports

| Service | URL/Port | Direction |
|---------|----------|-----------|
| Tactical Viewer | http://<SPARK_IP>:8080 | Browser → Spark |
| Viewer state JSON | http://<SPARK_IP>:8080/state | Browser → Spark |
| Isaac Sim UDP state (viewer) | localhost:9870 | Isaac → Viewer |
| Isaac Sim UDP cmd_vel | localhost:9871 | Viewer → Isaac |
| Isaac Sim UDP state (ROS2) | localhost:9872 | Isaac → ROS2 bridge |
| Isaac Sim UDP reset | localhost:9873 | Reset script → Isaac |
| Isaac Sim UDP camera (ROS2) | localhost:9874 | Isaac → Camera bridge |
| Isaac Sim UDP camera (viewer) | localhost:9875 | Isaac → Web viewer |
| Camera frame HTTP | http://<SPARK_IP>:8080/camera/latest.jpg | Browser → Spark |
| Kanban API | http://<MAC_IP>:3010 | Mac → NAS |

## 8. Camera Pipeline (VISION-01)

### Prérequis
- `--enable_cameras` dans la commande de lancement Isaac Sim
- Extensions activées : `omni.replicator.core` + `omni.syntheticdata`

### Architecture
```
launch_isaaclab.py (Python 3.11)
  └── CameraCapture class
      ├── Camera prim: /World/envs/env_0/Go2/base/front_camera
      ├── Resolution: 640x480, FOV 90°
      ├── Capture: toutes les 10 steps (~2.5 Hz)
      ├── Encode JPEG (quality 80)
      └── UDP send → localhost:9874

camera_bridge.py (Python 3.12, ROS2 Jazzy)
  ├── Receive UDP 9874: header 4B (uint32 size) + JPEG
  ├── Decode JPEG → numpy → sensor_msgs/Image (rgb8)
  ├── Publish /camera/color/image_raw
  └── Publish /camera/camera_info (640x480, plumb_bob)
```

### Commande de lancement avec caméra
```bash
source /home/panda/robotics/isaac_sim/activate.sh
cd /home/panda/robotics/isaac_sim/references/isaac-go2-ros2
python3 -u /home/panda/robotics/robotics_env/sim/launch_isaaclab.py \
  --headless --enable_cameras --camera-port 9874 --camera-fps 2.5
```

### Lancement du bridge caméra
```bash
source /opt/ros/jazzy/setup.bash
cd /tmp && python3 -u /home/panda/robotics/robotics_env/sim/camera_bridge.py
```

### Vérification caméra
```bash
# Topics
ros2 topic list | grep camera

# Frame live
ls -la /tmp/camera_frame.jpg

# Test subscriber
python3 /home/panda/robotics/robotics_env/sim/validate_camera.py
ls -la /tmp/camera_test_ros2.png
```

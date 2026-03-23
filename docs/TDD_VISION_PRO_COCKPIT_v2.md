# TDD — Vision Pro Robotics Cockpit
## Plan de Conception Technique v2.0

**Version** : 2.0
**Date** : 28 Février 2026
**Auteur** : STRAT (RoboticProgramAI)
**Statut** : En attente validation CEO
**Remplace** : TDD_VISION_PRO_COCKPIT.md v1.0 (27 février 2026)
**Sprint** : 4 — Vision Pro Cockpit

---

## Changelog v1.0 → v2.0

| Aspect | v1.0 | v2.0 |
|--------|------|------|
| Transport principal | gRPC streaming (custom) | **Foxglove WebSocket** (standard ROS2) |
| Protocole binaire | Protobuf custom | **CDR (ROS2 natif)** via Foxglove |
| Streaming Isaac Sim | Non traité | **WebRTC** (pattern VisionProTeleop) |
| LLM Thoughts | gRPC AIIntention | **Topic ROS2 custom** /jedi/thoughts |
| Point cloud | gRPC PointCloud | **sensor_msgs/PointCloud2** via Foxglove |
| Teleop | Non traité | **Hand tracking → cmd_vel** (Phase 4) |
| APIs entreprise | Non traitées | **visionOS 26** SharedCoordinateSpaceProvider |
| Références | 5 projets | VisionProTeleop v2.50 + ARMADA + metal-spatial-dynamic-mesh |

---

## 1. Vue d'Ensemble

### 1.1 Vision

Le **Robotics Cockpit** est une application Apple Vision Pro qui transforme l'espace physique de l'utilisateur en poste de pilotage pour le robot Go2. En enfilant le casque, l'opérateur voit :

1. Le **jumeau numérique** du Go2 ancré dans l'espace réel, ses 12 joints animés en temps réel
2. Les **pensées du robot** flottant au-dessus de lui — les intentions, raisonnements et plans générés par MonoCLI/Groq
3. Un **nuage de points LiDAR** superposé sur l'environnement, révélant ce que le robot "perçoit"
4. Un **tableau de bord** flottant : vitesse, orientation, stabilité, temps simulation
5. Des **contrôles de téléopération** par gestes naturels (regard + pinch → déplacement)

### 1.2 Cas d'usage prioritaire

Un ingénieur supervise le Go2 dans Isaac Sim depuis son Mac avec le Vision Pro. Il voit le robot évoluer dans un espace virtuel superposé à son bureau. Au-dessus du robot, une bulle affiche "Je planifie un chemin vers la cuisine — obstacle détecté à 1.2m". L'ingénieur peut prendre le contrôle en tendant la main et en "guidant" le robot par des gestes.

### 1.3 Ce que le porteur voit

```
┌──────────────────────────────────────────────────────────────────────┐
│  PASSTHROUGH : Bureau réel de l'opérateur                            │
│                                                                      │
│     ┌──────────────────────────────────────────┐                     │
│     │  "Je planifie un chemin vers la cuisine.  │  ← Bulle LLM      │
│     │   Obstacle détecté à 1.2m, contournement  │    (SwiftUI 3D)   │
│     │   par la droite. Confiance: 89%"          │                    │
│     └────────────────┬─────────────────────────┘                     │
│                      │                                               │
│               ┌──────▼──────┐                                        │
│               │   Go2 3D    │  ← Modèle USDZ, joints animés 25Hz    │
│               │  (jumeau)   │    ancré au sol (spatial anchor)       │
│               └──────┬──────┘                                        │
│                      │                                               │
│    - - - - - - - - - ▼ - - - - - - - → →                             │
│    - - - - - trajectoire planifiée - - →  ← Tube vert = sûr         │
│    - - - - - - - - - - - - - - - - - →     Rouge = obstacle          │
│                                                                      │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ← Nuage de points       │
│  ░░ BUREAU ░░░░░ MUR ░░░░░░ ÉTAGÈRE ░░░░     LiDAR (coloré)        │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░                           │
│                                                                      │
│  ┌── Dashboard ──────────────────────────────┐  ┌── Sim View ─────┐ │
│  │ ● Connecté  │  vx=0.30 m/s  │  Z=0.273   │  │ Isaac Sim       │ │
│  │ Stable      │  yaw=12.4°    │  12/12 DOF  │  │ (WebRTC stream) │ │
│  │ Sim: t=1842s│  Wi-Fi: 3ms   │  25Hz       │  │ 720p @ 30fps    │ │
│  └────────────────────────────────────────────┘  └─────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture Système

### 2.1 Diagramme de flux de données

```
┌──────────────────────────────────────────────────────────────────────┐
│                    DGX Spark (<SPARK_IP>)                           │
│                                                                      │
│  ┌──────────────┐   UDP 9872   ┌─────────────────────────────────┐  │
│  │ Isaac Lab     │ ──────────→ │        Foxglove Bridge          │  │
│  │ (physique RL) │             │     (C++, ros2 pkg)             │  │
│  │               │  ROS2 topics│                                 │  │
│  │  /cmd_vel ◄───┤────────────│  Port 8765 (WebSocket)          │  │
│  │  /odom    ────┤────────────│                                 │  │
│  │  /tf      ────┤────────────│  Protocole : Foxglove WS        │  │
│  │  /joint_states┤────────────│  Encodage  : CDR (ROS2 natif)   │  │
│  │  /clock   ────┤────────────│  Schémas   : ros2msg            │  │
│  └──────────────┘             │                                 │  │
│                                │  Topics exposés :              │  │
│  ┌──────────────┐   topic     │   /odom (nav_msgs/Odometry)    │  │
│  │ MonoCLI      │ ────────────│   /joint_states (JointState)   │  │
│  │ (Jedi/Groq)  │             │   /tf (tf2_msgs/TFMessage)     │  │
│  │              │  publish    │   /cmd_vel (Twist) ← bidirect. │  │
│  │  /jedi/      │─────────────│   /jedi/thoughts (String)      │  │
│  │  thoughts    │             │   /jedi/plan (Path)            │  │
│  └──────────────┘             │   /lidar/points (PointCloud2)  │  │
│                                └──────────────┬──────────────────┘  │
│  ┌──────────────┐                             │                     │
│  │ web_viewer.py│  HTTP :8080/state           │                     │
│  │ (fallback)   │─────────────────────────────┼─ ─ ─ ─ ─ ─ ─ ─ ┐  │
│  └──────────────┘                             │                 │  │
│                                                │                 │  │
│  ┌──────────────┐   WebRTC (futur)            │                 │  │
│  │ Isaac Sim    │─────────────────────────────┼─ ─ ─ ─ ─ ─ ┐│  │
│  │ Viewport     │                             │             ││  │
│  └──────────────┘                             │             ││  │
└───────────────────────────────────────────────┼─────────────┼┼──┘
                                                │             ││
                     WiFi 6 LAN (<LAN_SUBNET>)   │             ││
                                                │             ││
┌───────────────────────────────────────────────┼─────────────┼┼──┐
│                  Apple Vision Pro              │             ││  │
│                                                │             ││  │
│  ┌─────────────────────────────────────────────▼─────────┐  ││  │
│  │               FoxgloveClient.swift                     │  ││  │
│  │   WebSocket binaire (CDR) ← topics ROS2 souscrits     │  ││  │
│  │   Désérialise CDR → structs Swift natifs               │  ││  │
│  │   Publie cmd_vel (téléop) → topic ROS2 via WS         │  ││  │
│  └────────┬──────────┬──────────┬──────────┬─────────────┘  ││  │
│           │          │          │          │                 ││  │
│     ┌─────▼───┐ ┌────▼────┐ ┌──▼───┐ ┌───▼──────────┐     ││  │
│     │ Robot   │ │ Thought │ │Point │ │ Teleop       │     ││  │
│     │ State   │ │ Overlay │ │Cloud │ │ Controls     │     ││  │
│     │ Panel   │ │ (LLM)  │ │(Mesh)│ │ (Hands)      │     ││  │
│     └─────────┘ └─────────┘ └──────┘ └──────────────┘     ││  │
│                                                      ┌─────▼┼┐ │
│  ┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐  │HTTP  ││ │
│  │ SimViewport.swift (Phase 5 — futur)           │  │Poll  ││ │
│  │ WebRTC stream Isaac Sim → fenêtre visionOS    │  └──────┘│ │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘  ┌──────▼┐ │
│                                                      │WebRTC │ │
│                                                      │(futur)│ │
│                                                      └───────┘ │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 Changement architectural majeur : Foxglove remplace gRPC

La v1.0 proposait un bridge gRPC custom (Python) comme transport principal. La v2.0 adopte le **Foxglove WebSocket Bridge** pour les raisons suivantes :

| Critère | gRPC custom (v1.0) | Foxglove WebSocket (v2.0) |
|---------|-------------------|--------------------------|
| Code serveur à écrire | ~500 lignes Python + .proto | **0 ligne** — pkg ROS2 standard |
| Format données | Protobuf custom | **CDR natif ROS2** — zero conversion |
| Nouveaux topics | Modifier le .proto + regenerer | **Zéro config** — tous les topics exposés automatiquement |
| Bidirectionnel | Oui (gRPC stream) | **Oui** — le client peut publier sur des topics (cmd_vel) |
| Communauté | Aucune | **Foxglove Studio** + écosystème (debugging, recording, replay) |
| Performance | Bonne (HTTP/2 + protobuf) | **Excellente** (WebSocket binaire + CDR sans sérialisation intermédiaire) |
| Maintenance | Nous seuls | **Communauté open-source** + Foxglove Inc. |
| Latence | 5-15ms (gRPC stream) | **3-8ms** (WebSocket direct, pas de marshalling proto) |

**Conclusion** : Foxglove nous offre un bridge production-ready, standard ROS2, sans une seule ligne de code serveur. Le temps économisé est réinvesti dans l'expérience utilisateur côté Vision Pro.

### 2.3 Conservation de l'UDP pour la télémétrie critique

L'UDP custom (port 9872, le pattern existant de web_viewer.py) est **conservé comme fallback** :
- Si le Foxglove bridge n'est pas démarré, l'app peut lire l'état via HTTP GET /state (web_viewer.py)
- L'UDP reste disponible si on veut une latence sub-2ms pour un cas d'usage critique futur
- Mais en fonctionnement normal, Foxglove est le transport unique (simplification)

---

## 3. Stack Technique

### 3.1 Côté Vision Pro (client)

| Composant | Technologie | Justification |
|-----------|-------------|---------------|
| UI framework | **SwiftUI** | Natif visionOS, fenêtres volumétriques, ornaments |
| Rendu 3D | **RealityKit** | Seul moteur 3D natif visionOS avec passthrough AR |
| Réseau (WebSocket) | **URLSessionWebSocketTask** | Natif Foundation, zero dépendance |
| Réseau (UDP fallback) | **NWConnection** (Network.framework) | Natif, supporté visionOS 1.0+ |
| Réseau (WebRTC futur) | **WebRTC.framework** | Streaming Isaac Sim viewport |
| Point cloud GPU | **LowLevelMesh + Metal** | Vertex buffers GPU, compute shaders |
| Hand tracking | **ARKit HandTrackingProvider** | 27 joints par main, natif |
| Spatial anchoring | **WorldAnchor** (ARKit) | Persistance inter-sessions |
| Enterprise APIs | **SharedCoordinateSpaceProvider** | Multi-casque alignment (visionOS 26) |
| Concurrence | **Swift Concurrency** (async/await) | Structured concurrency, actors |

### 3.2 Côté Spark (serveur)

| Composant | Technologie | Statut |
|-----------|-------------|--------|
| Simulation physique | **Isaac Lab** (gym env) | Opérationnel |
| Bridge ROS2 → WebSocket | **foxglove_bridge** (C++, pkg ROS2) | A installer |
| State HTTP | **web_viewer.py** (port 8080) | Opérationnel |
| LLM / Cognition | **MonoCLI** (Groq API) | Externe |
| Streaming viewport | **WebRTC** (futur) | Non commencé |

### 3.3 Pourquoi PAS Unity PolySpatial

Cette décision, déjà prise en v1.0, est renforcée par la recherche v2.0 :

1. **LowLevelMesh impossible en PolySpatial** — le point cloud renderer nécessite des vertex buffers GPU directs et des Metal compute shaders. PolySpatial ne supporte ni les shaders custom, ni VFXGraph, ni l'accès GPU bas niveau. C'est un deal-breaker.

2. **ViewAttachmentComponent non supporté** — les bulles LLM (SwiftUI attaché à une entité 3D) sont une feature RealityKit native. PolySpatial ne peut pas reproduire ce pattern.

3. **Overhead de traduction** — chaque frame Unity est traduite vers RealityKit par la couche PolySpatial. Pour un rendu temps réel à 25Hz (point cloud + joints), cet overhead est inacceptable.

4. **Surcoût licence** — Unity Pro requis (2 409 $/an) vs Apple Developer seul (99 $/an).

5. **Aucun projet robotique MR de référence** en Unity PolySpatial. Les deux références majeures (VisionProTeleop et ARMADA) sont en natif.

### 3.4 Pourquoi Foxglove WebSocket et PAS rosbridge

| Critère | rosbridge (JSON) | Foxglove Bridge (CDR binaire) |
|---------|------------------|-------------------------------|
| Format | JSON texte (gros, lent à parser) | **CDR binaire** (compact, zero-copy possible) |
| Performances | ~100 msg/s max | **Milliers de msg/s** (C++ natif) |
| Point cloud | Inenvisageable en JSON (60KB binaire → ~500KB JSON) | **CDR natif** — bytes directs |
| Langage bridge | Python (rosbridge_suite) | **C++** (compilé, performant) |
| Schéma discovery | Non standard | **Automatique** (advertise avec schémas ROS2) |
| Écosystème | Vieillissant | **Actif** — Foxglove Studio, recording, replay |
| ROS2 Jazzy | Supporté | **Supporté** (pkg binaire : `ros-jazzy-foxglove-bridge`) |

---

## 4. Modules Applicatifs

### 4.a — Robot State Panel (Dashboard flottant)

**Description** : Fenêtre SwiftUI volumétrique affichant l'état du robot en temps réel. Flotte à côté du jumeau 3D ou est épinglée dans l'espace utilisateur.

**Source des données** :
- Phase 1 : HTTP GET `http://<SPARK_IP>:8080/state` (polling 5Hz)
- Phase 2+ : Topic `/odom` + `/joint_states` via Foxglove WebSocket (push 25Hz)

**Contenu affiché** :

```
┌─────────────────────────────────────────────┐
│  ROBOTICS COCKPIT          ● Connecté 3ms   │
│─────────────────────────────────────────────│
│  Position   X: -0.04   Y: -0.01   Z: 0.273 │
│  Vitesse    vx: 0.30 m/s    vy: 0.00 m/s   │
│  Orientation   yaw: 12.4°                    │
│  Stabilité     ████████████ Stable           │
│─────────────────────────────────────────────│
│  Joints (12 DOF)                             │
│  FL: ■■■■□□  FR: ■■■□□□  RL: ■■■■□□  RR: ■■■□□□ │
│  Hip / Thigh / Calf × 4 pattes              │
│─────────────────────────────────────────────│
│  Simulation   t = 1842.3s    25Hz ✓         │
│  Foxglove     ws://<SPARK_IP>:8765        │
└─────────────────────────────────────────────┘
```

**Données ROS2 consommées** :

| Topic | Type | Fréquence | Données extraites |
|-------|------|-----------|-------------------|
| `/odom` | `nav_msgs/Odometry` | 25 Hz | position.x/y/z, orientation quaternion, twist linear/angular |
| `/joint_states` | `sensor_msgs/JointState` | 25 Hz | 12 positions articulaires (rad) |
| `/clock` | `rosgraph_msgs/Clock` | 25 Hz | Temps simulation |

**Interactions** :
- Regard + pinch pour déplacer/redimensionner la fenêtre
- Tap pour basculer entre vue compacte (1 ligne) et vue détaillée
- Ornament SwiftUI avec indicateur connexion

### 4.b — LLM Thoughts Overlay (Bulles de pensées 3D)

**Description** : Les "pensées" du robot (intentions, raisonnements, observations de MonoCLI/Groq) s'affichent comme des bulles translucides flottant au-dessus du jumeau numérique dans l'espace 3D.

**Architecture de la donnée** :

MonoCLI publie sur un topic ROS2 custom :

```
Topic     : /jedi/thoughts
Type      : std_msgs/String
Format    : JSON encodé dans le champ data
Fréquence : événementiel (1-5 Hz, quand le LLM produit une pensée)
```

**Format JSON du champ `data`** :

```json
{
  "type": "intention",
  "text": "Je planifie un chemin vers la cuisine",
  "reasoning": "Le patient a demandé de l'eau il y a 2 minutes",
  "confidence": 0.89,
  "timestamp": 1709123456.789
}
```

Types de pensées :
- `intention` — ce que le robot veut faire (bulle bleue)
- `observation` — ce que le robot perçoit (bulle verte)
- `warning` — alerte ou risque détecté (bulle orange)
- `error` — problème critique (bulle rouge)

**Rendu RealityKit** :

```swift
// ViewAttachmentComponent : SwiftUI complet attaché à une entité 3D
// Se déplace avec le robot, toujours face à l'utilisateur (billboard)

struct ThoughtBubbleView: View {
    let thought: JediThought

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(thought.text)
                .font(.headline)
            if let reasoning = thought.reasoning {
                Text(reasoning)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            ProgressView(value: thought.confidence)
                .tint(thought.type.color)
        }
        .padding()
        .glassBackgroundEffect()  // Effet verre visionOS natif
    }
}
```

**Positionnement** :
- Offset Y = +0.5m au-dessus du robot
- Billboard : toujours face à l'utilisateur (utilise `BillboardComponent`)
- Empilement : les pensées récentes empilent verticalement (max 3 visibles)
- Fondu : une pensée disparaît après 10 secondes (configurable)

### 4.c — LiDAR Point Cloud (Rendu GPU natif)

**Description** : Le nuage de points provenant du LiDAR (simulé dans Isaac Sim ou physique futur) est rendu en temps réel dans l'espace passthrough, superposé à l'environnement réel.

**Source des données** :

```
Topic     : /lidar/points
Type      : sensor_msgs/PointCloud2
Fréquence : 10 Hz
Taille    : 5000 points × (XYZ float32 + RGB uint8) = ~75 KB/frame
```

**Pipeline de rendu** :

```
Foxglove WS → CDR deserialize → PointCloud2 → extract XYZ + RGB
    │
    ▼
Metal Compute Shader (GPU)
    │  - Transforme les coordonnées ROS (X-forward) → RealityKit (Z-forward)
    │  - Applique la matrice de pose du robot
    │  - Culling : élimine les points hors frustum
    │  - Écrit directement dans le vertex buffer LowLevelMesh
    │
    ▼
LowLevelMesh (RealityKit)
    │  - Topology : .point
    │  - Vertex layout : position (float3) + color (half4)
    │  - Bounding box mis à jour dynamiquement
    │
    ▼
MeshResource → ModelEntity → ancré dans la scène RealityKit
```

**Descripteur LowLevelMesh** :

```swift
var descriptor = LowLevelMesh.Descriptor()
descriptor.vertexCapacity = 5000
descriptor.indexCapacity = 5000

// Layout vertex : position (float3) + color (half4)
descriptor.vertexAttributes = [
    .init(semantic: .position, format: .float3, layoutIndex: 0, offset: 0),
    .init(semantic: .color,    format: .half4,  layoutIndex: 0, offset: 12)
]
descriptor.vertexLayouts = [
    .init(bufferStride: 20)  // 12 (float3) + 8 (half4) = 20 bytes/vertex
]

let mesh = try LowLevelMesh(descriptor: descriptor)
```

**Performance** :
- 5000 points = 100 KB vertex buffer — trivial pour le GPU
- Metal compute shader update = <0.5ms par frame
- Budget total : <2ms GPU par frame de point cloud à 10Hz

**Référence** : metal-spatial-dynamic-mesh (github.com/metal-by-example) démontre ce pattern exact avec LowLevelMesh + Metal compute à 60fps.

### 4.d — Teleop Controls (Contrôle par gestes)

**Description** : L'opérateur contrôle le Go2 par des gestes naturels détectés via le hand tracking ARKit du Vision Pro. Les commandes sont publiées sur le topic `/cmd_vel` via le Foxglove WebSocket (bidirectionnel).

**Gestes de contrôle** :

| Geste | Action | Topic / Donnée |
|-------|--------|-----------------|
| Regard + Pinch sur le robot | Activer/désactiver le mode téléop | Toggle local |
| Main droite — paume vers le bas, glisser avant/arrière | Avancer / reculer (vx) | `/cmd_vel` linear.x |
| Main droite — paume vers le bas, glisser gauche/droite | Strafe (vy) — limité | `/cmd_vel` linear.y |
| Main gauche — rotation poignet | Rotation yaw (wz) | `/cmd_vel` angular.z |
| Double pinch (deux mains) | **STOP immédiat** (sécurité) | `/cmd_vel` tout à zéro |
| Poing fermé (main droite) | Reset position (si tombé) | UDP 9873 signal RESET |

**Publication cmd_vel via Foxglove** :

Le protocole Foxglove WebSocket permet au client de **publier** sur des topics, pas seulement souscrire. L'app Vision Pro publie directement sur `/cmd_vel` :

```
Message type : geometry_msgs/Twist
Encodage     : CDR binaire
Fréquence    : 25 Hz (pendant téléop actif)
Latence      : WebSocket → Foxglove Bridge → topic ROS2 → Isaac Lab
Estimée      : 5-15ms end-to-end
```

**Sécurités** :
- Dead man's switch : si le hand tracking perd la main pendant >500ms, cmd_vel = zéro
- Vitesse maximale bridée : vx = [-0.5, 0.5] m/s, vy = [-0.2, 0.2] m/s
- Indicateur visuel : halo autour du robot (vert = téléop actif, gris = autonome)
- Limitation connue : le strafe (vy) déstabilise le robot (policy RL non entraînée latéral)

**Référence** : VisionProTeleop v2.50 valide ce pattern — hand tracking → commandes robot via WebRTC. Notre approche utilise Foxglove WebSocket au lieu de WebRTC pour la commande, ce qui est plus simple et suffisant pour cmd_vel (petits messages, pas de vidéo).

### 4.e — Sim Viewport Window (Stream Isaac Sim)

**Description** : Une fenêtre flottante dans l'espace Vision Pro affichant le viewport d'Isaac Sim en temps réel. L'opérateur voit simultanément le jumeau 3D RealityKit et la "caméra" du simulateur.

**Architecture** : WebRTC (pattern VisionProTeleop v2.50)

```
Isaac Sim (Spark)                    Vision Pro
┌──────────────┐                    ┌──────────────────┐
│ Viewport     │  WebRTC H.264     │ WKWebView ou     │
│ Headless     │ ────────────────→ │ WebRTC.framework  │
│ 720p @30fps  │  ~500 KB/s        │                  │
│              │                    │ Fenêtre SwiftUI  │
│ signaling    │  WebSocket        │ volumétrique     │
│ server       │ ←───────────────→ │ redimensionnable │
└──────────────┘                    └──────────────────┘
```

**Statut** : Phase 5 (futur). Le web_viewer.py actuel (Three.js stick-figure sur port 8080) peut servir de prototype intermédiaire en l'affichant dans un WKWebView visionOS.

---

## 5. Protocoles de Communication

### 5.a — Foxglove WebSocket (Transport principal)

**Rôle** : Transport bidirectionnel de tous les topics ROS2 entre le Spark et le Vision Pro.

**Installation sur Spark** :
```bash
sudo apt install ros-jazzy-foxglove-bridge
```

**Lancement** :
```bash
ros2 launch foxglove_bridge foxglove_bridge_launch.xml \
    port:=8765 \
    max_qos_depth:=1 \
    num_threads:=2 \
    send_buffer_limit:=10000000
```

**Protocole** :
- Transport : WebSocket (ws:// ou wss://)
- Messages texte : JSON avec champ "op" (advertise, subscribe, publish, etc.)
- Messages binaires : opcode 1 byte + payload CDR
- Encodage données : CDR (Common Data Representation) — format natif ROS2
- Encodage schéma : ros2msg (schéma .msg lisible)

**Flux d'initialisation client** :

```
Vision Pro                          Foxglove Bridge (Spark)
    │                                       │
    │──── WebSocket connect ──────────────→│
    │                                       │
    │◄─── serverInfo (name, capabilities) ──│
    │                                       │
    │◄─── advertise (liste des topics       │
    │     avec schémas ros2msg + CDR)  ─────│
    │                                       │
    │──── subscribe (channelId: /odom) ───→│
    │──── subscribe (channelId: /joint_s.) →│
    │──── subscribe (channelId: /jedi/th.) →│
    │                                       │
    │◄─── messageData (binary CDR) @25Hz ───│
    │                                       │
    │──── advertise (/cmd_vel, Twist) ────→│  ← Client publie aussi
    │──── messageData (cmd_vel CDR) ──────→│
    │                                       │
```

**Topics souscrits par l'app** :

| Topic | Type ROS2 | Fréquence | Module consommateur |
|-------|-----------|-----------|---------------------|
| `/odom` | `nav_msgs/msg/Odometry` | 25 Hz | Robot State Panel + Robot Entity pose |
| `/joint_states` | `sensor_msgs/msg/JointState` | 25 Hz | Robot State Panel + joints animation |
| `/tf` | `tf2_msgs/msg/TFMessage` | 25 Hz | Transform tree (futur multi-frame) |
| `/clock` | `rosgraph_msgs/msg/Clock` | 25 Hz | Temps simulation |
| `/jedi/thoughts` | `std_msgs/msg/String` | 1-5 Hz | LLM Thoughts Overlay |
| `/jedi/plan` | `nav_msgs/msg/Path` | 1 Hz | Trajectoire planifiée (futur) |
| `/lidar/points` | `sensor_msgs/msg/PointCloud2` | 10 Hz | Point Cloud Renderer |

**Topic publié par l'app** :

| Topic | Type ROS2 | Fréquence | Module source |
|-------|-----------|-----------|---------------|
| `/cmd_vel` | `geometry_msgs/msg/Twist` | 25 Hz | Teleop Controls (hand tracking) |

### 5.b — HTTP REST (Fallback Phase 1)

**Rôle** : Source de données initiale avant l'installation du Foxglove bridge. Réutilise l'infrastructure existante (web_viewer.py).

**Endpoint** :
```
GET http://<SPARK_IP>:8080/state
```

**Réponse JSON** (existante, validée Sprint 2) :
```json
{
    "pos": [-0.04, -0.01, 0.273],
    "quat": [0.0, 0.0, 0.019, 0.999],
    "lin_vel": [0.30, 0.00, 0.01],
    "ang_vel": [0.00, 0.00, 0.02],
    "joint_pos": [0.1, -0.8, 1.5, ...],  // 12 valeurs
    "joint_vel": [0.0, 0.01, -0.02, ...], // 12 valeurs
    "sim_time": 1842.3
}
```

**Polling** : 5 Hz (URLSession async, timer SwiftUI)

**Avantages Phase 1** : Zero installation supplémentaire sur le Spark, fonctionne immédiatement.

### 5.c — WebRTC (Futur : viewport Isaac Sim)

**Rôle** : Streamer le viewport graphique d'Isaac Sim vers une fenêtre dans l'espace Vision Pro.

**Architecture cible** (pattern VisionProTeleop v2.50) :
- Isaac Sim expose un viewport headless (720p, 30fps)
- Un serveur WebRTC sur le Spark encode en H.264 et streame
- Le Vision Pro reçoit via WebRTC.framework et affiche dans une fenêtre SwiftUI

**Bande passante estimée** : ~500 KB/s (H.264 720p@30fps, qualité moyenne)

**Innovation VisionProTeleop** : Au lieu de streamer des pixels, convertir la scène MuJoCo/Isaac en USD et envoyer les poses via WebRTC. Le rendu est fait nativement en RealityKit. Avantage : bande passante réduite (poses = quelques KB vs pixels = centaines de KB). Nous évaluerons cette approche si le Go2 USDZ est de qualité suffisante.

**Statut** : Phase 5. Non prioritaire car le web_viewer.py (Three.js stick-figure) couvre le besoin immédiat.

### 5.d — UDP Custom (Latence minimale — héritage)

**Rôle** : Canal de communication hérité du Sprint 2, conservé comme option pour les cas exigeant une latence sub-2ms.

| Port | Direction | Format | Usage |
|------|-----------|--------|-------|
| 9871 | App → Spark | struct pack (Twist) | cmd_vel direct (bypass ROS2) |
| 9872 | Spark → App | struct pack (38 doubles = 304 bytes) | État robot brut |
| 9873 | App → Spark | `b'RESETGO2'` / `b'RESET_OK'` | Signal reset |

**Quand utiliser l'UDP plutôt que Foxglove** :
- Fallback si Foxglove bridge est down
- Téléop critique nécessitant <5ms de latence (Foxglove ajoute ~3-5ms de overhead WebSocket)
- Debug : on peut tester l'app sans aucune infrastructure ROS2

En fonctionnement normal, Foxglove est suffisant (latence WebSocket ~5-10ms sur LAN = acceptable pour nos 25Hz).

---

## 6. Plan de Développement en 4 Phases

### Phase 1 — Static Cockpit (Semaines 1-2)

**Objectif** : Application visionOS minimale qui se connecte au Spark et affiche l'état du robot.

**Livrables** :
- [ ] Projet Xcode visionOS configuré (SwiftUI + RealityKit)
- [ ] `HTTPStateClient.swift` : polling GET /state à 5Hz
- [ ] `DashboardView.swift` : fenêtre SwiftUI volumétrique avec position, orientation, joints, stabilité
- [ ] `RobotEntity.swift` : cube 3D (placeholder) positionné selon /state dans un ImmersiveSpace
- [ ] Test sur simulateur visionOS : données live du Spark affichées

**Transport** : HTTP uniquement (web_viewer.py existant)

**Ce qu'on voit** : Une fenêtre flottante avec les données du robot, et un cube qui se déplace dans l'espace selon la position du Go2.

**Critères de validation** :
- L'app se connecte au Spark et affiche la position du robot
- Le cube se déplace en temps réel quand on lance `mono_robot_move.py 0.3 0.0 2.0` sur le Spark
- Latence < 300ms (HTTP polling 5Hz)
- Fonctionne dans le simulateur visionOS (Xcode)

### Phase 2 — Live State (Semaines 3-4)

**Objectif** : Passer au transport Foxglove WebSocket pour des données temps réel à 25Hz. Remplacer le cube par le modèle Go2 USDZ avec animation des joints.

**Livrables** :
- [ ] Installer `ros-jazzy-foxglove-bridge` sur le Spark
- [ ] `FoxgloveClient.swift` : client WebSocket avec décodage CDR → structs Swift
- [ ] Souscription aux topics : `/odom`, `/joint_states`, `/clock`
- [ ] `Go2Entity.swift` : modèle USDZ avec 12 joints animés depuis `/joint_states`
- [ ] Conversion URDF Go2 → USDZ via Reality Converter (ou export Isaac Sim)
- [ ] Dashboard mis à jour à 25Hz (au lieu de 5Hz)
- [ ] Indicateur de latence réseau dans le dashboard

**Transport** : Foxglove WebSocket (principal) + HTTP (fallback)

**Ce qu'on voit** : Le Go2 en 3D avec ses pattes qui bougent en temps réel, un dashboard fluide à 25Hz.

**Critères de validation** :
- Foxglove bridge opérationnel sur le Spark (`ros2 topic list` = topics visibles via WS)
- L'app souscrit et reçoit /odom + /joint_states à 25Hz
- Les 12 joints du Go2 USDZ s'animent correctement
- Latence mesurée < 30ms (Foxglove WS)

### Phase 3 — Point Cloud + LLM Overlay (Semaines 5-7)

**Objectif** : Ajouter le rendu du nuage de points LiDAR et les bulles de pensées MonoCLI.

**Livrables** :
- [ ] `PointCloudRenderer.swift` : LowLevelMesh + Metal compute shader
- [ ] `PointCloudShader.metal` : transformation coordonnées ROS → RealityKit, écriture vertex buffer
- [ ] Souscription au topic `/lidar/points` (sensor_msgs/PointCloud2)
- [ ] `ThoughtBubble.swift` : ViewAttachmentComponent avec SwiftUI glassBackground
- [ ] Souscription au topic `/jedi/thoughts` (std_msgs/String, JSON encodé)
- [ ] Topic `/jedi/thoughts` publié par MonoCLI (coordination avec équipe MonoCLI)
- [ ] Empilement vertical des bulles (max 3), fondu après 10s
- [ ] Code couleur par type de pensée (intention=bleu, observation=vert, warning=orange, error=rouge)

**Transport** : Foxglove WebSocket

**Ce qu'on voit** : Le Go2 3D entouré d'un nuage de points coloré, avec des bulles de texte au-dessus montrant ce que le LLM pense.

**Dépendances** :
- Topic `/lidar/points` : nécessite un publisher LiDAR dans Isaac Lab (ou simulé)
- Topic `/jedi/thoughts` : nécessite que MonoCLI publie ses pensées sur ROS2

**Critères de validation** :
- 5000 points rendus à 10Hz sans drop de framerate (90fps maintenu)
- Les bulles affichent les pensées correctement avec le bon code couleur
- Metal compute shader valide (pas de corruption vertex buffer)

### Phase 4 — Enterprise Features + Teleop (Semaines 8-10)

**Objectif** : Contrôle du robot par gestes, alignement multi-casque, et polish production.

**Livrables** :
- [ ] `TeleopController.swift` : hand tracking → cmd_vel via Foxglove publish
- [ ] Publication bidirectionnelle `/cmd_vel` via Foxglove WebSocket
- [ ] Dead man's switch : arrêt si perte hand tracking > 500ms
- [ ] Indicateur visuel mode téléop (halo autour du robot)
- [ ] `SpatialCalibration.swift` : placement robot par pinch + WorldAnchor persistant
- [ ] Option QR code pour calibration automatique
- [ ] Intégration `SharedCoordinateSpaceProvider` (visionOS 26) pour alignement multi-casque
- [ ] Demande d'entitlement entreprise Apple si nécessaire
- [ ] Reconnexion automatique WebSocket (exponential backoff)
- [ ] Settings UI : adresse Spark, topics souscrits, fréquences, thème

**Transport** : Foxglove WebSocket bidirectionnel + UDP 9873 (reset)

**Ce qu'on voit** : L'opérateur guide le robot par gestes naturels. Plusieurs casques peuvent observer le même robot aligné dans l'espace.

**Critères de validation** :
- L'opérateur déplace le robot dans Isaac Sim par gestes (hand tracking → cmd_vel → mouvement)
- Latence geste → mouvement < 100ms
- STOP immédiat fonctionnel (double pinch → cmd_vel zéro < 50ms)
- WorldAnchor persiste entre les sessions (le robot réapparaît au même endroit)

---

## 7. Dépendances et Risques

### 7.1 Dépendances critiques

| Dépendance | Responsable | Statut | Impact si absent |
|------------|-------------|--------|------------------|
| `ros-jazzy-foxglove-bridge` sur Spark | DEV/Spark | A installer | Bloque Phase 2 — fallback HTTP en Phase 1 |
| Modèle Go2 USDZ (avec joints nommés) | DEV | A créer | Bloque Phase 2 — cube placeholder en Phase 1 |
| Topic `/jedi/thoughts` publié par MonoCLI | Equipe MonoCLI | Non commencé | Bloque Phase 3 — données simulées en attendant |
| Topic `/lidar/points` depuis Isaac Lab | DEV/Spark | Non commencé | Bloque Phase 3 — point cloud synthétique en attendant |
| Apple Developer Program + Xcode 16 | CEO | A vérifier | Bloque tout — essentiel dès Phase 1 |
| Vision Pro physique | CEO | A vérifier | Ne bloque pas — simulateur pour Phase 1-2, device pour Phase 3-4 |
| Entitlement entreprise Apple | CEO | Non demandé | Bloque SharedCoordinateSpaceProvider (Phase 4 seulement) |

### 7.2 Risques et mitigations

| # | Risque | Probabilité | Impact | Mitigation |
|---|--------|-------------|--------|------------|
| R1 | **Pas de Vision Pro physique** — impossible de tester passthrough, hand tracking, spatial anchors | Moyenne | Élevé | Phase 1-2 fonctionnent en simulateur. Emprunter/louer un device pour Phase 3-4. Le simulateur visionOS gère le réseau, RealityKit, SwiftUI — seuls les capteurs physiques manquent. |
| R2 | **Foxglove bridge instable sur Jazzy/aarch64** — le Spark est ARM64, les builds binaires sont rares | Faible | Moyen | Build from source (`colcon build`). Le bridge est C++ pur, pas de dépendance x86. Fallback : web_viewer.py HTTP fonctionne toujours. |
| R3 | **CDR parsing en Swift n'existe pas** — il faudra écrire un désérialiseur CDR | Élevée | Moyen | CDR est un format simple (little-endian, aligné). Un parseur Swift minimal pour nos 5-6 types ROS2 = ~200 lignes. Alternative : utiliser l'encodage JSON du Foxglove bridge (option `use_json_encoding:=true`) — moins performant mais zéro parser custom. |
| R4 | **LowLevelMesh incompatible simulateur** — le compute shader Metal peut ne pas fonctionner dans le simulateur visionOS | Moyenne | Faible | Fallback : rendu CPU avec MeshResource classique (moins performant mais fonctionnel). Le simulateur supporte Metal via le GPU du Mac. |
| R5 | **MonoCLI ne publie pas sur ROS2** — l'équipe MonoCLI utilise des scripts CLI, pas ROS2 | Élevée | Moyen | Créer un petit bridge : `jedi_thoughts_publisher.py` qui lit les outputs MonoCLI (fichier, pipe, ou API) et publie sur `/jedi/thoughts`. L'équipe Robotics peut fournir ce script. |
| R6 | **WiFi instable (pertes paquets)** — le Vision Pro est en WiFi, pas ethernet | Faible | Moyen | Foxglove WebSocket gère les reconnexions. Interpolation côté client pour lisser les gaps. QoS best_effort (pas reliable) pour /odom et /joint_states — les paquets perdus sont remplacés par le suivant. |
| R7 | **Latence WebSocket trop élevée pour téléop** — si > 100ms, le contrôle devient dangereux | Faible | Élevé | Mesurer la latence réelle. Si > 50ms, basculer la téléop sur UDP direct (port 9871) — canal hérité, <5ms. Foxglove reste pour les données read-only. |

### 7.3 Risques acceptés (hors mitigation)

- **Strafe (vy) déstabilise le robot** : limitation connue de la policy RL. Sera corrigé quand la policy sera ré-entraînée. En attendant, la téléop bride vy à [-0.2, 0.2] m/s.
- **Pas de LiDAR physique sur le Go2** : en Phase 3, le point cloud sera synthétique (Isaac Sim). Le renderer est conçu pour accepter des données réelles quand un LiDAR sera monté.

---

## 8. Critères de Validation Phase 1 (MVP)

### 8.1 Critères fonctionnels

| # | Critère | Mesure | Seuil |
|---|---------|--------|-------|
| F1 | L'app se connecte au Spark via HTTP | GET /state retourne 200 | Succès 100% sur 100 requêtes |
| F2 | Le dashboard affiche la position du robot | Valeurs X/Y/Z visibles et cohérentes | Delta < 0.01m vs valeur réelle |
| F3 | Le dashboard affiche les 12 joints | 12 valeurs affichées en radians | Cohérent avec /joint_states |
| F4 | Le dashboard affiche le temps simulation | Valeur croissante | Mis à jour toutes les 200ms |
| F5 | Le cube 3D se déplace dans l'espace | Position du cube = position du robot | Mouvement visible quand `mono_robot_move.py` tourne |
| F6 | Le cube s'affiche dans un ImmersiveSpace | RealityKit ImmersiveSpace avec passthrough | Visible dans le simulateur visionOS |

### 8.2 Critères techniques

| # | Critère | Mesure | Seuil |
|---|---------|--------|-------|
| T1 | Fréquence de polling | Requêtes HTTP par seconde | 5 Hz stable |
| T2 | Latence data → affichage | Timestamp requête → render | < 300ms |
| T3 | Stabilité | Durée sans crash | > 30 minutes |
| T4 | Mémoire | Empreinte mémoire de l'app | < 100 MB |
| T5 | Build | Compile et run dans simulateur visionOS | Xcode 16, visionOS 2.0 SDK |

### 8.3 Ce qui est hors scope Phase 1

- Foxglove WebSocket (Phase 2)
- Modèle Go2 USDZ (Phase 2)
- Point cloud LiDAR (Phase 3)
- Bulles LLM thoughts (Phase 3)
- Hand tracking téléop (Phase 4)
- SharedCoordinateSpaceProvider (Phase 4)
- WebRTC Isaac Sim viewport (Phase 5)

---

## 9. Références Architecturales

| Projet | Licence | Contribution à notre architecture |
|--------|---------|----------------------------------|
| **VisionProTeleop v2.50** (Improbable AI, MIT) | MIT | Pattern MuJoCo→USD + RealityKit natif. Preuve que le hand tracking → robot fonctionne en production. Architecture WebRTC pour streaming simulation. Room code system pour NAT traversal. |
| **ARMADA** (Apple ML Research, Dec 2024) | Research | Validation scientifique du concept robot-overlay-en-MR. QR code calibration. Feedback visuel (couleurs, zones). 30Hz loop proprioceptive. |
| **metal-spatial-dynamic-mesh** (metal-by-example) | MIT | Référence LowLevelMesh + Metal compute shader pour mesh dynamiques à 60fps sur visionOS. |
| **Foxglove Bridge** (Foxglove Inc.) | MIT | Bridge C++ ROS2 → WebSocket standard. Protocole binaire CDR. Zero code serveur. |
| **Foxglove Studio** | BSL + MIT | Outil de debugging pour valider les données ROS2 avant de les consommer dans l'app. |

---

## 10. Glossaire

| Terme | Définition |
|-------|-----------|
| **CDR** | Common Data Representation — format de sérialisation binaire natif de ROS2 (DDS). Little-endian, aligné. |
| **Foxglove Bridge** | Noeud ROS2 C++ qui expose tous les topics via WebSocket avec le protocole Foxglove. |
| **LowLevelMesh** | API RealityKit (visionOS 2+) permettant de spécifier des vertex buffers custom et de les mettre à jour via Metal. |
| **ViewAttachmentComponent** | API RealityKit qui attache une vue SwiftUI à une entité 3D dans l'espace. |
| **ImmersiveSpace** | Type de scène visionOS qui occupe tout l'espace autour de l'utilisateur (passthrough ou non). |
| **SharedCoordinateSpaceProvider** | API enterprise visionOS 26 permettant à plusieurs casques d'aligner leurs systèmes de coordonnées. |
| **MonoCLI** | Moteur cognitif propriétaire (Infinity Cloud) — mémoire persistante + LLM (Groq) pour piloter le robot. |
| **Jedi** | Profil d'agent MonoCLI dédié à la robotique Go2. |
| **Dead man's switch** | Sécurité : si l'opérateur lâche le contrôle, le robot s'arrête automatiquement. |

---

*Ce document est une stratégie architecturale. Aucun code ne sera écrit avant validation CEO.*
*"Ne code rien, je veux la stratégie" — CEO*

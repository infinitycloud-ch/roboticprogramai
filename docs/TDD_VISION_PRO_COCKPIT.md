# TDD — Vision Pro Clinical Cockpit
## Plan d'Architecture pour l'Application visionOS

**Version** : 1.0
**Date** : 27 Février 2026
**Auteur** : STRAT (RoboticProgramAI)
**Statut** : En attente validation CEO
**Sprint** : 4 — Hospital Digital Twin & Vision Pro Cockpit

---

## 1. Résumé Exécutif

Le Clinical Cockpit est une application Apple Vision Pro native qui superpose en réalité mixte les "pensées" du robot Go2 dans l'espace physique de l'utilisateur. Le personnel soignant, la famille ou l'ingénieur voit en temps réel : la position du robot, ses intentions IA (MonoCLI), son nuage de points LiDAR, et sa trajectoire planifiée — le tout superposé dans leur salon ou la chambre du patient.

**Décision architecturale clé** : Application **native visionOS** (Swift + RealityKit + SwiftUI), PAS Unity PolySpatial.

---

## 2. Pourquoi Native visionOS (et PAS Unity PolySpatial)

| Critère | Native (RealityKit) | Unity PolySpatial |
|---------|---------------------|-------------------|
| **Performance 25Hz temps réel** | `LowLevelMesh` + Metal compute shaders, zero overhead | Chaque frame traduite via couche PolySpatial → overhead significatif |
| **Nuage de points LiDAR** | Vertex buffers GPU directs, 60fps | VFXGraph NON supporté, baking mesh par frame = lent |
| **Bulles d'intentions IA** | `ViewAttachmentComponent` = SwiftUI complet attaché à une entité 3D | TextMesh Pro "partiel, SDF only, pas de shaders custom" |
| **Shaders custom** | ShaderGraph + MaterialX complet | Shaders custom NON supportés en mode PolySpatial |
| **Coût licence** | 99$/an (Apple Developer) | 2 409$/an (Unity Pro requis + Apple Developer) |
| **Référence robotique** | VisionProTeleop (MIT) prouve l'architecture | Aucun projet robotique MR de référence |

---

## 3. Architecture Globale

```
┌─────────────────────────────────────────────────────────────────┐
│                     DGX Spark (<SPARK_IP>)                    │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Isaac Lab     │  │ ROS2 Bridge  │  │ MonoCLI (Jedi)        │  │
│  │ (physique)    │  │ (topics)     │  │ (cognition)           │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬───────────┘  │
│         │                 │                       │              │
│  ┌──────▼─────────────────▼───────────────────────▼──────────┐  │
│  │              Bridge Server (Python)                        │  │
│  │                                                            │  │
│  │  Tier 1 — UDP unicast (port 9873)                         │  │
│  │  → Telemetrie : position, joints, orientation @ 25Hz      │  │
│  │  → Format : struct.pack STATE_FMT (320 bytes/frame)       │  │
│  │                                                            │  │
│  │  Tier 2 — gRPC streaming (port 50051)                     │  │
│  │  → Point cloud LiDAR (downsampled 5K pts) @ 10Hz          │  │
│  │  → Intentions MonoCLI (texte + trajectoire) @ 5Hz         │  │
│  │  → Caméra RGB (JPEG compressé) @ 15Hz                     │  │
│  └────────────────────────┬───────────────────────────────────┘  │
└───────────────────────────┼──────────────────────────────────────┘
                            │ WiFi 6 local (~1.6 MB/s)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Apple Vision Pro                              │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │          ClinicalCockpit.app (visionOS natif)             │  │
│  │                                                           │  │
│  │  ┌─────────────────┐  ┌────────────────────────────────┐  │  │
│  │  │  NetworkManager  │  │  SceneManager (RealityKit)     │  │  │
│  │  │                 │  │                                │  │  │
│  │  │  NWConnection   │  │  RobotEntity                   │  │  │
│  │  │  (UDP tier 1)   │──▶  ├─ Corps Go2 (USDZ)          │  │  │
│  │  │                 │  │  ├─ 12 joints animés            │  │  │
│  │  │  GRPCClient     │  │  ├─ Flèche heading             │  │  │
│  │  │  (gRPC tier 2)  │──▶  │                              │  │  │
│  │  └─────────────────┘  │  PointCloudEntity               │  │  │
│  │                       │  ├─ LowLevelMesh (Metal)        │  │  │
│  │  ┌─────────────────┐  │  ├─ 5000 points colorés         │  │  │
│  │  │  SwiftUI Layer  │  │  │                              │  │  │
│  │  │                 │  │  TrajectoryEntity                │  │  │
│  │  │  Status bar     │  │  ├─ LowLevelMesh tube/ligne     │  │  │
│  │  │  Connexion      │  │  ├─ Couleur : vert=sûr/rouge    │  │  │
│  │  │  Paramètres     │  │  │                              │  │  │
│  │  │  Logs MonoCLI   │  │  IntentionBubble                │  │  │
│  │  └─────────────────┘  │  ├─ ViewAttachmentComponent     │  │  │
│  │                       │  ├─ SwiftUI : texte + icônes     │  │  │
│  │                       │  └─ "Je vais chercher l'eau..."  │  │  │
│  │                       └────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Streaming — Architecture Hybride 2 Tiers

### Tier 1 : UDP Custom (Telemetrie — 2-8ms latence)

Étend directement le pattern existant de `web_viewer.py` / `ros2_state_bridge.py`.

**Côté Spark (Python) :**
```python
# Extension de ros2_state_bridge.py
# Envoie aussi vers le Vision Pro en plus de localhost
VISION_PRO_IP = "<VISION_PRO_IP>"  # découvert via mDNS/Bonjour
VISION_PRO_PORT = 9873

STATE_FMT = "!d3d4d3d3d12d12d"  # 320 bytes
# timestamp + pos(3) + quat(4) + lin_vel(3) + ang_vel(3) + joints_pos(12) + joints_vel(12)
```

**Côté Vision Pro (Swift) :**
```swift
import Network

let connection = NWConnection(
    host: NWEndpoint.Host("<SPARK_IP>"),
    port: NWEndpoint.Port(rawValue: 9873)!,
    using: .udp
)
// NWConnection est supporté sur visionOS 1.0+
```

**Pourquoi UDP en Tier 1 :**
- Latence la plus basse possible (2-8ms sur WiFi local)
- Extend le code existant (web_viewer.py pattern)
- 320 bytes/frame = bien sous le MTU (1500 bytes)
- Perte de paquets acceptable (25Hz = données vite remplacées)

### Tier 2 : gRPC Streaming (Données lourdes — 5-15ms latence)

Pour les données volumineuses et structurées.

**Proto definition :**
```protobuf
syntax = "proto3";

service ClinicalCockpit {
  // Telemetrie robot (backup si UDP indisponible)
  rpc StreamTelemetry(TelemetryRequest) returns (stream RobotState);
  // Nuage de points LiDAR
  rpc StreamPointCloud(PointCloudRequest) returns (stream PointCloud);
  // Intentions MonoCLI
  rpc StreamIntentions(IntentionRequest) returns (stream AIIntention);
  // Commandes du cockpit vers le robot
  rpc SendCommand(stream CockpitCommand) returns (CommandAck);
}

message RobotState {
  double timestamp = 1;
  Vec3 position = 2;
  Quaternion orientation = 3;
  repeated double joint_positions = 4;  // 12 DOF
  string stability = 5;  // "stable" | "unstable" | "fallen"
}

message AIIntention {
  double timestamp = 1;
  string current_task = 2;      // "Je vais chercher un verre d'eau"
  string reasoning = 3;         // "Le patient a demandé de l'eau il y a 2 min"
  repeated Vec3 planned_path = 4;  // Points de la trajectoire planifiée
  float confidence = 5;         // 0.0 - 1.0
}

message PointCloud {
  double timestamp = 1;
  bytes points = 2;     // Packed float32 XYZ (5000 * 12 bytes = 60KB)
  bytes colors = 3;     // Packed uint8 RGB (5000 * 3 bytes = 15KB)
  int32 num_points = 4;
}
```

**Côté Vision Pro** : [grpc-swift](https://github.com/grpc/grpc-swift) (confirmé compatible visionOS via VisionProTeleop MIT).

### Budget bande passante estimé

| Canal | Taille/msg | Fréquence | Débit |
|-------|-----------|-----------|-------|
| UDP telemetrie | 320 bytes | 25 Hz | 8 KB/s |
| gRPC point cloud (5K pts) | ~75 KB | 10 Hz | 750 KB/s |
| gRPC intentions | ~2 KB | 5 Hz | 10 KB/s |
| gRPC caméra JPEG | ~50 KB | 15 Hz | 750 KB/s |
| **Total** | | | **~1.5 MB/s** |

Confortable pour WiFi 6 (bande passante typique > 100 MB/s).

---

## 5. Application visionOS — Structure

### 5.1 Projet Xcode

```
ClinicalCockpit/
├── ClinicalCockpitApp.swift          ← Point d'entrée visionOS
├── Views/
│   ├── ImmersiveView.swift           ← Vue RealityKit (espace immersif)
│   ├── DashboardView.swift           ← SwiftUI HUD (status, logs)
│   └── SettingsView.swift            ← Connexion Spark, calibration
├── Networking/
│   ├── UDPReceiver.swift             ← NWConnection UDP tier 1
│   ├── GRPCClient.swift              ← grpc-swift tier 2
│   └── ConnectionManager.swift       ← État connexion, reconnexion auto
├── Scene/
│   ├── RobotEntity.swift             ← Modèle Go2 USDZ + animation joints
│   ├── PointCloudRenderer.swift      ← LowLevelMesh + Metal compute
│   ├── TrajectoryRenderer.swift      ← LowLevelMesh lignes/tubes
│   └── IntentionBubble.swift         ← ViewAttachmentComponent SwiftUI
├── Proto/
│   ├── clinical_cockpit.proto        ← Définitions Protobuf
│   └── Generated/                    ← Code Swift généré
├── Metal/
│   └── PointCloudShader.metal        ← Compute shader mise à jour vertices
└── Resources/
    └── Go2.usdz                      ← Modèle 3D Unitree Go2
```

### 5.2 Modes d'affichage

**Mode 1 — Shared Space (par défaut)**
- Le robot apparaît comme une fenêtre volumétrique dans l'espace
- Dashboard SwiftUI flottant à côté
- Interactions : regard + pinch pour sélectionner, déplacer

**Mode 2 — Full Immersive Space (cockpit complet)**
- Passthrough activé : l'utilisateur voit son environnement réel
- Le robot 3D est ancré au sol (spatial anchor)
- Nuage de points LiDAR superposé dans l'espace réel
- Trajectoire planifiée dessinée au sol
- Bulle d'intention flottant au-dessus du robot
- Hand tracking pour commander le robot (gestes)

### 5.3 Entités RealityKit clés

**RobotEntity** : Modèle Go2 en USDZ, joints animés à 25Hz depuis les données UDP.
```swift
// Animation des joints depuis les données telemetrie
func updateJoints(_ positions: [Double]) {
    for (index, joint) in jointEntities.enumerated() {
        joint.transform.rotation = simd_quatf(
            angle: Float(positions[index]),
            axis: jointAxes[index]
        )
    }
}
```

**PointCloudRenderer** : `LowLevelMesh` avec Metal compute shader.
```swift
// LowLevelMesh pour nuage de points GPU-driven
let mesh = try LowLevelMesh(descriptor: pointCloudDescriptor)
// Metal compute shader met à jour les vertex buffers directement sur GPU
// Pas de CPU-side mesh baking → performance maximale
```

**IntentionBubble** : SwiftUI attaché à une entité 3D via `ViewAttachmentComponent`.
```swift
// Bulle d'intention MonoCLI flottant au-dessus du robot
let bubble = ViewAttachmentComponent(rootView: IntentionView(
    task: "Je vais chercher un verre d'eau",
    confidence: 0.92,
    reasoning: "Patient a demandé de l'eau"
))
robotEntity.components.set(bubble)
```

---

## 6. Données superposées dans l'espace réel

### Ce que le soignant voit dans Vision Pro :

```
┌─────────────────────────────────────────────────────────┐
│  PASSTHROUGH : Chambre réelle du patient                │
│                                                         │
│     ┌─────────────────────────────────┐                 │
│     │ "Je vérifie la température      │  ← Bulle IA    │
│     │  de la chambre. RAS."           │     (SwiftUI)   │
│     │  Confiance: 94%                 │                 │
│     └────────────┬────────────────────┘                 │
│                  │                                      │
│            ┌─────▼─────┐                                │
│            │  🐕 Go2   │  ← Modèle 3D ancré au sol     │
│            │  (USDZ)   │     Joints animés temps réel   │
│            └─────┬─────┘                                │
│                  │                                      │
│     ·············▼·····················                  │
│     · · · · · · · · · · · · · · · · ·  ← Trajectoire   │
│     · · · · · · · · · · · · · · · · ·     planifiée     │
│     ···································     (vert=sûr)   │
│                                                         │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ← Point cloud   │
│  ░░░ MEUBLES ░░░░ MUR ░░░░ PORTE ░░░     LiDAR         │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░     (coloré)     │
│                                                         │
│  ┌─── HUD Status ────────────────────┐                  │
│  │ ● Connecté | Z=0.254 | 12 DOF    │  ← Dashboard     │
│  │ Batterie: 82% | Sim: t=7234s     │     SwiftUI      │
│  └───────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
```

---

## 7. Calibration Spatiale

Pour que le robot 3D s'affiche au bon endroit dans l'espace réel, deux options :

**Option A — Ancre manuelle (MVP)**
L'utilisateur pointe et "pinch" pour placer le robot dans l'espace. Simple, immédiat.

**Option B — Ancre automatique via QR code**
Un QR code physique posé au sol à côté du vrai robot (ou dans la pièce de référence). Vision Pro le détecte automatiquement et calibre la position du jumeau numérique.

**Option C — Ancre persistante (production)**
`WorldAnchor` de ARKit : Vision Pro mémorise la position du robot entre les sessions. Le soignant calibre une fois, le robot réapparaît au même endroit.

---

## 8. Latence End-to-End Estimée

| Étape | Durée |
|-------|-------|
| Callback ROS2 + sérialisation | 2-5 ms |
| Transmission UDP WiFi local | 1-2 ms |
| Désérialisation Swift | 1-2 ms |
| Update scène RealityKit + rendu | 11-16 ms (@ 90Hz) |
| **Total** | **~15-25 ms** |

Cible acceptable : < 100ms. Nous sommes 4x sous la limite.

---

## 9. Dépendances et Prérequis

| Composant | Version | Notes |
|-----------|---------|-------|
| Xcode | 16+ | visionOS SDK intégré |
| visionOS | 2.0+ | LowLevelMesh disponible depuis visionOS 1.0 |
| Swift | 5.9+ | Async/await, structured concurrency |
| grpc-swift | 1.x ou 2.x | Basé sur SwiftNIO |
| Apple Developer Program | $99/an | Requis pour deployer sur device |
| Vision Pro | Hardware | Simulateur dispo pour dev initial |
| Modèle Go2 USDZ | À créer | Conversion URDF → USDZ via Reality Converter |

**Développement sans Vision Pro physique** : Le simulateur visionOS dans Xcode permet de tester toute l'app sauf les spatial anchors réels. Les données de streaming UDP/gRPC fonctionnent normalement dans le simulateur.

---

## 10. Projets de Référence

| Projet | Lien | Pertinence |
|--------|------|------------|
| **VisionProTeleop** (MIT) | github.com/Improbable-AI/VisionProTeleop | Architecture gRPC + WebRTC pour robotique visionOS. Référence principale. |
| **Droid Vision** | App Store | App visionOS utilisant rosbridge WebSocket pour contrôler des robots ROS2. Preuve que ça marche en production. |
| **metal-spatial-dynamic-mesh** | github.com/metal-by-example | Démo LowLevelMesh + Metal compute pour mesh dynamiques 60fps. Référence pour le point cloud renderer. |
| **RBSManager** | github.com/wesgood/RBSManager | Client Swift pour rosbridge WebSocket. Alternative à gRPC pour le prototypage. |
| **PHNTM Bridge** | github.com/PhantomCybernetics | WebRTC ROS2 bridge, 5-10ms RTT. Serveur-side potentiel. |

---

## 11. Roadmap de Développement

| Semaine | Livrable | Détail |
|---------|----------|--------|
| **S1** | Bridge server + app basique | Python bridge sur Spark (UDP + gRPC). App visionOS qui connecte, reçoit telemetrie, affiche un cube 3D à la position du robot + texte SwiftUI joints/position. |
| **S2** | Modèle Go2 + trajectoire | Import USDZ Go2, animation des 12 joints temps réel. Rendu trajectoire planifiée comme tube coloré au sol. |
| **S3** | Point cloud + intentions IA | LowLevelMesh point cloud renderer avec Metal compute. ViewAttachmentComponent pour bulles d'intentions MonoCLI. |
| **S4** | Polish + calibration | Spatial anchoring (QR code ou manuel). Reconnexion automatique. Settings UI. Performance optimization. |

---

## 12. Risques et Mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Pas de Vision Pro physique pour tester | Retarde la calibration spatiale | Développer d'abord dans le simulateur Xcode. Calibration spatiale en Phase 2. |
| WiFi instable (pertes UDP) | Robot "saute" dans l'espace | Interpolation côté client. gRPC comme fallback si trop de pertes UDP. |
| LiDAR pas encore sur le Go2 | Pas de point cloud à afficher | Phase 1 sans LiDAR. Préparer le renderer pour quand le LiDAR sera intégré. |
| Performance LowLevelMesh sur VP | Lag si trop de points | Limiter à 5000 points, LOD dynamique. Metal compute pour culling. |
| CloudXR non compatible Spark | Pas de streaming vidéo natif NVIDIA | Notre architecture hybride UDP+gRPC est indépendante de CloudXR. |

---

## 13. Ce qui est hors périmètre (pour plus tard)

- Commandes vocales Siri vers le robot
- Multi-utilisateur SharePlay (plusieurs Vision Pro observent le même robot)
- Haptic feedback via hand tracking
- Enregistrement/replay de sessions pour formation
- Intégration dossier médical patient

---

## 14. Compatibilités et Incompatibilités

### Compatible (à explorer)

| Technologie | Statut | Notes |
|------------|--------|-------|
| **NVIDIA CloudXR (visionOS 26.4)** | NOUVEAU — Streaming fovéalisé supporté | Nécessite serveur x86_64 avec GPU RTX. Notre Spark est aarch64, MAIS un serveur x86 dédié pourrait servir de relais. Sample client Apple officiel : `isaac-xr-teleop-sample-client-apple`. Hybride possible : CloudXR pour rendu lourd + RealityKit natif pour UI. |
| **ARMADA (Apple Research)** | Référence architecturale | Système quasi-identique au Clinical Cockpit : robot overlaid en MR, QR code calibration, ROS + WebSocket, 30Hz. Paper : arxiv.org/abs/2412.10631 |

### Incompatible

| Technologie | Raison | Alternative |
|------------|--------|-------------|
| CloudXR **sur Spark** | Spark = aarch64, CloudXR Runtime = x86_64 only | UDP + gRPC custom (notre architecture) |
| Unity PolySpatial | Coût 2409$/an, overhead traduction, pas de shaders custom, VFXGraph non supporté | Native visionOS (Swift + RealityKit) |
| WebXR Safari | Pas d'AR passthrough sur visionOS, VR only, limité | App native |
| FastDDS direct | Aucun port iOS/visionOS existant | gRPC bridge ou rosbridge WebSocket |
| Unreal Engine | Support visionOS "Experimental", pas production-ready | Native visionOS |

---

## 15. Projets de Recherche Apple — ARMADA

**ARMADA** (Apple ML Research, Décembre 2024) est le système le plus proche de notre Clinical Cockpit :
- Robot overlaid en MR dans l'espace réel
- Calibration via QR code physique
- ROS + WebSocket pour communication
- 30Hz loop pour données proprioceptives
- Feedback visuel : zones de singularité (jaune), limites workspace (murs rouges), alertes vitesse
- Architecture plug-and-play : changer le modèle 3D + pipe les données au bon format

Notre Clinical Cockpit va plus loin qu'ARMADA :
- Intentions IA (MonoCLI) superposées, pas juste de la téleopération
- Point cloud LiDAR en temps réel
- Mémoire persistante du robot (contexte patient)
- Optimisé Silver Economy (interface soignant, pas chercheur)

---

## 16. Découverte : CloudXR Foveated Streaming (visionOS 26.4)

**Février 2026** : Apple a intégré le streaming fovéalisé CloudXR dans visionOS 26.4.

Cela ouvre une **architecture hybride avancée** pour le futur :
- **CloudXR** : rend les visualisations lourdes (point cloud dense, scène hospital) sur un serveur GPU x86
- **RealityKit natif** : overlay local pour UI, bulles d'intentions, trajectoire
- **Streaming fovéalisé** : haute résolution uniquement où le soignant regarde → bande passante réduite

**Prérequis** : un serveur x86_64 avec GPU RTX (Ada/Blackwell discrete, PAS le Spark aarch64).
**Action** : si Infinity Cloud acquiert un serveur x86 RTX à l'avenir, CloudXR hybride devient l'option premium.

Pour le MVP, notre architecture UDP + gRPC est la bonne approche.

---

*Document en attente de validation CEO avant coding.*

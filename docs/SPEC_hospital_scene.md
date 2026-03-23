# SPEC : Scene Hospital Isaac Sim

**Version :** 1.0
**Date :** 2026-02-28
**Auteur :** Agent STRATÉGISTE
**Destinataire :** Agent DEV (Spark)
**Statut :** A IMPLÉMENTER

---

## 1. Objectif

Créer un script `launch_hospital_scene.py` qui lance le Go2 dans un environnement hospitalier visuellement réaliste dans Isaac Sim 5.1.

La scene contient :
- Le Go2 debout au centre, controlé par la policy RL `flat_model_6800.pt`
- Un décor hospital (murs, sol carrelé, mobilier) chargé depuis un USD Nucleus
- Un lit d'hôpital avec collision box simplifiée (obstacle physique)
- Un personnage humain (docteur) statique (obstacle visuel + collision)

Le but est de tester la **navigation en environnement intérieur** : le Go2 doit pouvoir se déplacer avec `mono_robot_move.py` tout en évitant les obstacles.

Le pipeline existant (UDP bridge, web_viewer, mono_robot_sense/move) reste **100% inchangé**. Seul le script de lancement change.

---

## 2. Assets USD

### 2.1 Environnement Hospital

| Asset | Chemin Nucleus | Rôle |
|-------|---------------|------|
| Hospital | `{ISAAC_NUCLEUS_DIR}/Environments/Hospital/hospital.usd` | Décor : murs, sol, portes, mobilier |

> **Note :** `{ISAAC_NUCLEUS_DIR}` est résolu par Isaac Sim automatiquement. En pratique, souvent `omniverse://localhost/NVIDIA/Assets/Isaac/4.2/Isaac/Environments/Hospital/hospital.usd` ou accessible via le Nucleus local du Spark.
>
> **Fallback :** Si le Nucleus n'est pas accessible en headless, on peut utiliser le chemin local du cache Nucleus ou un asset simple (4 murs + sol). Le DEV doit tester l'accès au Nucleus en premier et documenter le chemin résolu.

### 2.2 Personnage Humain (Docteur)

| Asset | Chemin Nucleus | Rôle |
|-------|---------------|------|
| Docteur | `{ISAAC_NUCLEUS_DIR}/People/Characters/original_male_adult_medical_01/male_adult_medical_01.usd` | Obstacle statique visuel |

> **Fallback :** Si cet asset n'est pas disponible, utiliser n'importe quel personnage humain du Nucleus, ou un cylindre primitif (r=0.25m, h=1.8m) coloré en blanc comme placeholder.

### 2.3 Lit d'Hôpital

Pas d'asset USD dédié requis. Utiliser une **primitive box** Isaac Sim :
- Dimensions : 2.0m (longueur X) x 0.9m (largeur Y) x 0.6m (hauteur Z)
- Couleur : blanc/gris clair
- Avec collision activée

> **Alternative :** Si un asset lit est trouvé dans le Nucleus Hospital, l'utiliser a la place de la box. Mais la collision doit rester une box simplifiée, pas un mesh collider.

### 2.4 Go2 (déjà configuré)

Le Go2 est chargé par Isaac Lab via `Go2RSLEnvCfg` exactement comme dans `launch_isaaclab.py`. Aucune modification.

---

## 3. Layout Scene

### 3.1 Système de coordonnées

Isaac Sim utilise : **X = avant, Y = gauche, Z = haut**

### 3.2 Dimensions de la pièce

La zone navigable est d'environ **6m x 5m** (largeur X x profondeur Y). Le décor Hospital USD peut être plus grand — seule cette zone est pertinente pour la navigation.

### 3.3 Positions des objets

```
          Y (gauche)
          ^
          |
     +----+----+----+----+----+----+
     |                              |  5m
     |         [Docteur]            |
     |         (3.0, 1.0, 0.0)     |
     |         face -X             |
     |                              |
     |  [Go2]                       |
     |  (0.0, 0.0, 0.35)           |
     |  face +X                     |
     |                              |
     |         [Lit]                |
     |         (2.0, -1.5, 0.0)    |
     |         parallèle X         |
     |                              |
     +----+----+----+----+----+----+ --> X (avant)
                   6m
```

| Objet | Position (X, Y, Z) | Orientation | Notes |
|-------|---------------------|-------------|-------|
| Go2 | (0.0, 0.0, 0.35) | Face +X (yaw=0) | Spawn par Isaac Lab, Z=0.35 = hauteur debout |
| Lit | (2.0, -1.5, 0.0) | Parallèle a X (yaw=0) | Z=0.0 = base au sol, centre du mesh a Z=0.3 |
| Docteur | (3.0, 1.0, 0.0) | Face -X (yaw=pi) | Z=0.0 = pieds au sol |
| Hospital USD | (0.0, 0.0, 0.0) | Défaut | Peut nécessiter offset/scale selon asset |

### 3.4 Ajustements attendus

Le DEV devra probablement ajuster :
1. **Scale du Hospital USD** — certains assets Nucleus sont a des échelles différentes (cm vs m). Vérifier que les murs font ~2.5-3m de haut.
2. **Offset Z du Hospital USD** — le sol du décor doit s'aligner avec Z=0 (le plan physique).
3. **Position du Hospital USD** — centrer la piece navigable autour de l'origine.

---

## 4. Physique

### 4.1 Sol (Ground Plane)

Le sol physique est le **GroundPlaneCfg** d'Isaac Lab, configuré par `Go2RSLEnvCfg`. Il reste **identique** a la config actuelle :

```python
# Déjà dans go2_env.py — NE PAS MODIFIER
terrain = TerrainImporterCfg(...)  # ou GroundPlaneCfg selon la config
# Friction: static=1.0, dynamic=1.0, restitution=0.0
```

**CRITIQUE :** La policy RL `flat_model_6800.pt` a été entrainée sur un sol PLAT a Z=0. Le Hospital USD est **purement décoratif** — il ne doit PAS remplacer le ground plane physique.

### 4.2 Collision du Lit

Le lit utilise une **collision box simplifiée** (pas un mesh collider) :

```
Type: Box Collider
Dimensions: 2.0m x 0.9m x 0.6m
Position: (2.0, -1.5, 0.3)  ← centre de la box, pas la base
Friction: static=0.5, dynamic=0.5
```

> Un mesh collider serait trop lourd en calcul pour un simple obstacle rectangulaire.

### 4.3 Collision du Docteur

Le personnage humain a une **collision capsule simplifiée** :

```
Type: Capsule Collider (ou Cylinder)
Rayon: 0.25m
Hauteur: 1.8m
Position: (3.0, 1.0, 0.9)  ← centre de la capsule
Friction: static=0.5, dynamic=0.5
```

> Le mesh USD du docteur est visuel uniquement. La capsule est ajoutée programmatiquement comme collider séparé.

### 4.4 Hospital USD

Le décor Hospital est chargé en mode **visuel uniquement** :
- Pas de collision sur les murs (le Go2 reste dans la zone 6x5m de toute facon)
- Pas de rigid body
- Juste un Xform avec les meshes visuels

> **Exception :** Si le DEV souhaite ajouter des collisions sur les murs pour plus de réalisme, il peut le faire avec des box colliders simples sur les murs principaux. Mais ce n'est PAS requis pour le MVP.

---

## 5. Intégration Pipeline

### 5.1 Architecture actuelle (inchangée)

```
launch_isaaclab.py (Isaac Lab gym env + RL policy + UDP bridge)
       |
       |  UDP :9870 (state)     UDP :9871 (cmd_vel)     UDP :9872 (viewer state)
       v                              ^                        v
ros2_state_bridge.py            mono_robot_move.py        web_viewer.py
       |                                                       |
       v                                                       v
  /odom, /cmd_vel (ROS2)                              http://<SPARK_IP>:8080
```

### 5.2 Nouveau script : launch_hospital_scene.py

Le nouveau script **remplace** `launch_isaaclab.py` comme point d'entrée. Il :

1. Réutilise **exactement** le meme code de `launch_isaaclab.py` (env creation, policy loading, UDP bridge, main loop)
2. Ajoute le chargement des assets hospital **APRÈS** la création de l'environnement Isaac Lab
3. N'affecte PAS la physique du Go2 (meme ground plane, meme policy)

### 5.3 Commande de lancement

```bash
# Sur Spark
source /home/panda/robotics/isaac_sim/activate.sh
cd /home/panda/robotics/isaac_sim/references/isaac-go2-ros2
python3 -u /home/panda/robotics/robotics_env/sim/launch_hospital_scene.py --headless
```

### 5.4 Ports UDP (identiques)

| Port | Direction | Contenu |
|------|-----------|---------|
| 9870 | OUT | Robot state (pos, quat, joints) → ros2_state_bridge |
| 9871 | IN | cmd_vel (vx, vy, wz) ← mono_robot_move.py |
| 9872 | OUT | Robot state → web_viewer.py |

### 5.5 Compatibilité

- `mono_robot_move.py` fonctionne sans modification
- `mono_robot_sense.py` fonctionne sans modification
- `web_viewer.py` fonctionne sans modification (le stick-figure Three.js ne montre pas le décor, mais le Go2 se déplace correctement)
- `ros2_state_bridge.py` fonctionne sans modification

---

## 6. Structure du Script

### 6.1 Fichier : `/home/panda/robotics/robotics_env/sim/launch_hospital_scene.py`

```python
#!/usr/bin/env python3
"""Launch Go2 in hospital environment with USD overlays.

Extends launch_isaaclab.py with hospital decor, bed obstacle,
and static human character.

Usage:
    source /home/panda/robotics/isaac_sim/activate.sh
    cd /home/panda/robotics/isaac_sim/references/isaac-go2-ros2
    python3 -u /home/panda/robotics/robotics_env/sim/launch_hospital_scene.py --headless
"""

# ============================================================
# PHASE 1 : Setup identique a launch_isaaclab.py
# ============================================================
# - argparse + AppLauncher
# - import torch, gymnasium, numpy
# - import Go2RSLEnvCfg, go2_ctrl
# - Memes arguments CLI (--headless, --freq, --udp-port, --cmd-port, --viewer-port)

# ============================================================
# PHASE 2 : Création de l'environnement Isaac Lab
# ============================================================
# cfg = Go2RSLEnvCfg()
# cfg.scene.num_envs = 1
# cfg.sim.device = "cpu"
# ... (identique a launch_isaaclab.py)
# env = gym.make("Isaac-Velocity-Flat-Unitree-Go2-v0", cfg=cfg)

# ============================================================
# PHASE 3 : Ajout des assets hospital (NOUVEAU)
# ============================================================
# Accéder au stage USD via Isaac Sim API

import omni.usd
from pxr import UsdGeom, UsdPhysics, Gf, Sdf
# ou: from isaacsim.core.utils.stage import add_reference_to_stage

stage = omni.usd.get_context().get_stage()

# 3a. Charger le décor Hospital (visuel uniquement)
hospital_prim_path = "/World/Hospital"
# add_reference_to_stage(
#     usd_path="omniverse://localhost/NVIDIA/Assets/.../Hospital/hospital.usd",
#     prim_path=hospital_prim_path,
# )
# Ajuster scale et position si nécessaire :
# xform = UsdGeom.Xformable(stage.GetPrimAtPath(hospital_prim_path))
# xform.AddTranslateOp().Set(Gf.Vec3d(offset_x, offset_y, offset_z))
# xform.AddScaleOp().Set(Gf.Vec3d(scale, scale, scale))

# 3b. Créer le lit (box primitive + collision)
bed_prim_path = "/World/Hospital/Bed"
# Créer un Cube prim
# UsdGeom.Cube.Define(stage, bed_prim_path)
# Appliquer scale (1.0, 0.45, 0.3) pour obtenir 2.0 x 0.9 x 0.6
# Appliquer translate (2.0, -1.5, 0.3)
# Appliquer UsdPhysics.CollisionAPI
# Appliquer UsdPhysics.MeshCollisionAPI avec approximation "boundingCube" ou "convexHull"
# Appliquer material visuel blanc/gris

# 3c. Charger le personnage humain (statique)
human_prim_path = "/World/Hospital/Doctor"
# add_reference_to_stage(
#     usd_path="omniverse://localhost/NVIDIA/Assets/.../male_adult_medical_01.usd",
#     prim_path=human_prim_path,
# )
# Positionner a (3.0, 1.0, 0.0)
# Rotation yaw=pi (face -X)
# NE PAS ajouter de RigidBodyAPI (il doit rester statique/kinematic)

# 3d. Ajouter collision capsule pour le docteur
human_collider_path = "/World/Hospital/DoctorCollider"
# UsdGeom.Capsule.Define(stage, human_collider_path)
# Rayon 0.25, hauteur 1.8
# Position (3.0, 1.0, 0.9)
# UsdPhysics.CollisionAPI
# Invisible (purpose = "guide" ou visibility = "invisible")

# ============================================================
# PHASE 4 : Policy + UDP Bridge (identique a launch_isaaclab.py)
# ============================================================
# - Charger flat_model_6800.pt
# - Créer UDPBridge
# - Reset env
# - Main loop (recv cmd_vel → policy → step → send state)

# ============================================================
# PHASE 5 : Cleanup (identique)
# ============================================================
# bridge.close(), env.close(), simulation_app.close()
```

### 6.2 Ordre de chargement (résumé)

1. `AppLauncher` + `simulation_app`
2. `Go2RSLEnvCfg` + `gym.make()` → crée le ground plane + spawne le Go2
3. **Hospital USD** → ajouté par-dessus le ground plane (décor visuel)
4. **Lit** → box primitive avec collision
5. **Docteur** → USD référence + capsule collision séparée
6. **Policy** → `flat_model_6800.pt`
7. **UDPBridge** → ports 9870/9871/9872
8. **Main loop** → identique

### 6.3 Points d'attention pour le DEV

1. **Timing du stage access** — Le stage USD n'est accessible qu'APRÈS `gym.make()`. Les ajouts d'assets doivent se faire entre la création de l'env et le `env.reset()`.

2. **Chemin Nucleus** — En mode headless, le Nucleus local peut ne pas etre démarré. Le DEV doit :
   - Tester `omni.client.list("omniverse://localhost/NVIDIA/Assets/Isaac/")` pour vérifier l'accès
   - Si echec, utiliser le cache local ou un fallback (primitives simples)
   - Documenter le chemin résolu dans les logs

3. **Performance headless** — Les meshes USD du hospital sont lourds. Si le framerate chute sous 20 FPS, réduire la complexité (ne charger qu'une piece, pas tout l'étage).

4. **Pas de TerrainImporterCfg** — Ne PAS utiliser TerrainImporterCfg pour le sol hospital. Il y a des régressions connues en Isaac Sim 5.x. Le GroundPlaneCfg existant suffit.

---

## 7. Critères d'Acceptation

### 7.1 MUST HAVE (MVP)

- [ ] `launch_hospital_scene.py` démarre sans erreur sur Spark en mode `--headless`
- [ ] Le Go2 est debout (pos_z entre 0.28 et 0.40) après 5 secondes
- [ ] `mono_robot_move.py 0.5 0.0 2.0` fait avancer le Go2 d'environ 1m (meme comportement que la scene vide)
- [ ] Le lit a un collider : si le Go2 marche vers (2.0, -1.5) il est bloqué (ne traverse pas)
- [ ] Le docteur a un collider : si le Go2 marche vers (3.0, 1.0) il est bloqué
- [ ] Les logs affichent la confirmation du chargement de chaque asset (Hospital, Bed, Doctor)
- [ ] La pipeline UDP fonctionne : web_viewer.py affiche le Go2 qui se déplace
- [ ] Le script ne modifie PAS `launch_isaaclab.py` (fichier séparé)

### 7.2 NICE TO HAVE

- [ ] Le décor Hospital USD est visible dans le web viewer (si le DEV met a jour le Three.js — optionnel)
- [ ] Les murs du hospital ont des colliders (box simples)
- [ ] Le lit utilise un asset USD du Nucleus plutot qu'une box primitive
- [ ] Reset (`mono_robot_sense.py` state reset) remet le Go2 a l'origine sans devoir relancer

### 7.3 Critères de REJET

- Le Go2 tombe ou ne tient pas debout → le ground plane physique est cassé
- `mono_robot_move.py` ne fonctionne plus → le pipeline UDP est cassé
- Le script nécessite des dépendances non installées sur Spark
- Le script modifie `go2_env.py` ou `launch_isaaclab.py`

---

## Annexe A : Référence code existant

### launch_isaaclab.py (lignes clés)

```python
# Lignes 146-156 : Creation env
cfg = Go2RSLEnvCfg()
cfg.scene.num_envs = 1
cfg.sim.device = "cpu"
cfg.decimation = max(1, math.ceil(1.0 / cfg.sim.dt / args.freq))
cfg.sim.render_interval = cfg.decimation
go2_ctrl.init_base_vel_cmd(1)
cfg.observations.policy.height_scan = None
env = gym.make("Isaac-Velocity-Flat-Unitree-Go2-v0", cfg=cfg)

# Lignes 159-163 : Policy
ckpt = torch.load(POLICY_PATH, map_location="cpu", weights_only=False)
actor_state = {k: v for k, v in ckpt["model_state_dict"].items() if k.startswith("actor.")}
policy = ActorMLP()
policy.load_state_dict(actor_state)
policy.eval()

# Lignes 167-171 : UDP Bridge
bridge = UDPBridge(state_port=args.udp_port, cmd_port=args.cmd_port, viewer_port=args.viewer_port)
```

### Fichier source complet

`/home/panda/robotics/robotics_env/sim/launch_isaaclab.py` (239 lignes)

Le DEV doit copier ce fichier comme base et ajouter la Phase 3 (assets hospital) entre `gym.make()` et `env.reset()`.

---

## Annexe B : API Isaac Sim 5.1 utiles

```python
# Ajouter une référence USD au stage
from isaacsim.core.utils.stage import add_reference_to_stage
add_reference_to_stage(usd_path="omniverse://...", prim_path="/World/MyAsset")

# Créer une primitive avec collision
from pxr import UsdGeom, UsdPhysics, Gf
cube = UsdGeom.Cube.Define(stage, "/World/Bed")
cube.GetSizeAttr().Set(1.0)  # unit cube, scale after
UsdPhysics.CollisionAPI.Apply(cube.GetPrim())

# Transformer un prim
xformable = UsdGeom.Xformable(prim)
xformable.AddTranslateOp().Set(Gf.Vec3d(x, y, z))
xformable.AddScaleOp().Set(Gf.Vec3d(sx, sy, sz))
xformable.AddRotateYOp().Set(180.0)  # yaw 180° = face -X

# Vérifier accès Nucleus
import omni.client
result, entries = omni.client.list("omniverse://localhost/NVIDIA/Assets/Isaac/")
if result == omni.client.Result.OK:
    print("Nucleus accessible")
```

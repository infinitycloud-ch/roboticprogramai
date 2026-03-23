# Insights & Règles du Projet RoboticProgramAI

## Règles de doctrine

### Repos officiels UNIQUEMENT
- **OBLIGATOIRE** : Utiliser les repos github.com/unitreerobotics pour tout code lié au Go2
- Repos de référence communautaires (isaac-go2-ros2, go2_omniverse) utilisés pour l'architecture SEULEMENT
- Pas de forks tiers en production

### Verrouillage des versions Sprint 1
- Isaac Sim **5.1.0** (PAS 5.1 — risque de compatibilité)
- Isaac Lab **2.3.x**
- ROS2 **Jazzy** sur Ubuntu 24.04
- Extension bridge : **isaacsim.ros2.bridge** (nomenclature v5.x)
- FastDDS (rmw_fastrtps_cpp) pour multi-machine

### Ségrégation du code
- Tout le code robotique vit dans `/robotics_env/` à la racine
- L'infra agents (STRAT/DEV, tmux, logs) reste dans la racine projet
- `RoboticProgramAI APP/` = application existante, ne pas polluer

### Architecture 3 couches
- Cerveau (Agent Jedi) → Interface Corps (RobotAdapter) → Monde (Isaac Sim)
- Le **Noeud Locomoteur** (RL PPO) est entre le SimAdapter et Isaac Sim
- SimAdapter NE calcule PAS la cinématique
- RobotAdapter est une ABC async Python

### Workflow Striping
- STRAT : interfaces haut niveau, documentation, Kanban, recherche
- DEV : code lourd, ROS2 nodes, Isaac Sim, installation serveur
- Aucun code avant validation CEO du TDD

## Leçons apprises

### 2026-02-27 — Session initiale
- Les 3 recherches (Isaac Sim, Go2 SDK, Vision Pro) ont pris ~4 min chacune en parallèle
- Le Go2 EDU est le SEUL modèle avec accès développeur complet (SDK natif, ROS2, low-level)
- UnifoLM-VLA-0 (Unitree) est pertinent pour Phase 3+ (agent multimodal)
- VisionProTeleop (MIT) et CloudXR (NVIDIA) sont les 2 options Vision Pro
- Le DEV a besoin d'accès SSH au Spark pour continuer (bloquant)

## Contacts & Ressources
- Kanban API : http://<MAC_IP>:3010 (Project 42)
- GitHub Unitree : https://github.com/unitreerobotics
- Doc Unitree : https://support.unitree.com/main
- UnifoLM VLA : https://github.com/unitreerobotics/unifolm-vla
- Communauté : www.unifolm.com

## Serveur DGX Spark — Specs confirmées
- **Architecture** : aarch64 (ARM) — Grace-Blackwell GB10
- **GPU** : NVIDIA GB10, Driver 580.126, CUDA 13.0
- **Mémoire** : 128GB unifiée (~90GB disponibles avec services actifs)
- **Disque** : 3.7TB total, 2.3TB libre
- **IP** : <SPARK_IP>
- **User** : panda
- **Services actifs** : ComfyUI (4.8GB) + llama-server (32.4GB)
- **ROS2** : Jazzy installe (356 packages)
- **Path robotique** : /home/panda/robotics/ (isolé de spark-apps/)
- **Communication tmux** : session spark_agents, pane 1 = STRAT
- **IMPORTANT** : Isaac Sim 5.0+ supporte aarch64 (5.1.0 = premier support DGX Spark) officiellement pour DGX Spark
- **IMPORTANT** : Toujours cibler les packages Linux aarch64, PAS x86_64

## Versions confirmées sur Spark (2026-02-27)
- ROS2 Jazzy : 356 packages installés
- Isaac Sim : 5.1.0.0 (pip, aarch64)
- Isaac Lab : 2.3.2.post1
- Python venv : 3.11.14 (deadsnakes PPA, requis par Isaac Sim)
- URDF Go2 : cloné (5 fichiers xacro/urdf)
- isaac-go2-ros2 : cloné (référence)
- LD_PRELOAD libgomp fix : intégré dans activate.sh
- Activation : source /home/panda/robotics/isaac_sim/activate.sh
- ROS2 seul : source /home/panda/robotics/ros2/env.sh
- Aucun impact sur spark-apps/

## Sprint 1 : TERMINE (2026-02-27)
- 16/16 tâches complétées en une session
- 4 agents coordonnés : CEO, STRAT, DEV, SPARK
- Stack finale : Ubuntu 24.04 + ROS2 Jazzy + Isaac Sim 5.1.0 + Isaac Lab 2.3.2 + Python 3.11
- Serveur : DGX Spark (<SPARK_IP>, aarch64 GB10, 128GB)
- Isolation : /home/panda/robotics/ (spark-apps/ intact)
- Code : /robotics_env/ (adapters, sim, ros, locomotion, agent, scripts, tests)
- Fichiers clés livrés : sim_adapter.py (440L), launch_scene.py (253L), hello_robot.py (145L)
- TDD v1.3 sur API Kanban
- Dashboard HTML : /dashboard.html
- Prêt pour Sprint 2 : Go2Adapter réel, Noeud Locomoteur RL, intégration agent Jedi

## Sprint 2 : Cognitive Awakening (TERMINE 2026-02-27)
- Objectif : SimAdapter opérationnel sur Spark + Noeud Locomoteur RL + API Contract
- Directive CEO : périmètre strict Couches 2+3, ZERO modification MonoCLI
- 10 tâches actives (6 supprimées → responsabilité agents MonoCLI)
- TDD Sprint 2 v2.0 livré par DEV
- API Contract SimAdapter v1.0 rédigé par STRAT

### Bug critique découvert (R6)
- launch_scene.py utilisait `effortCommand` (torques) pour /joint_commands
- La policy RL (go2_flat.pt) produit des POSITIONS articulaires, pas des torques
- PATCH : effortCommand → positionCommand dans OmniGraph (1 ligne)
- CORRIGÉ le 2026-02-27

### Leçons Sprint 2
- Séparation des responsabilités : chaque système (MonoCLI, RoboticProgramAI) a ses propres agents
- API Contract = le pont entre systèmes : documenter import, méthodes, dataclasses, erreurs
- Policy RL PPO Isaac Lab : obs 48-dim, actions 12-dim (position offsets, scale 0.25, 50Hz)
- Positions par défaut Go2 : FL(0.1,0.8,-1.5) FR(-0.1,0.8,-1.5) RL(0.1,1.0,-1.5) RR(-0.1,1.0,-1.5)

### Migration Isaac Sim 4.x → 5.x (CRITIQUE)
Regles apprises lors du premier lancement sur Spark :
1. **URDF Importer** : `omni.importer.urdf` → `isaacsim.asset.importer.urdf`
2. **parse_urdf API** : prend 3 args (root_dir, filename, config) au lieu de 2 (path, config)
3. **import_robot API** : prend 5 args (root_dir, filename, parsed, config, dest_path)
4. **OGN nodes** : `omni.isaac.core_nodes` → `isaacsim.core.nodes`
5. **ROS2Context obligatoire** : TOUS les publishers/subscribers doivent recevoir Context.outputs:context
6. **ReadSimTime** : n a PAS d execIn en 5.x
7. **SubscribeFloat64MultiArray** : n existe plus → utiliser `ROS2SubscribeJointState`
8. **Odometry** : pas de topic /odom direct. Nécessite 2 noeuds chaînés :
   - `isaacsim.core.nodes.IsaacComputeOdometry` (calcul depuis chassisPrim)
   - `isaacsim.ros2.bridge.ROS2PublishOdometry` (publication sur /odom)
9. **ArticulationRootAPI** : vérifier que le URDF importe bien comme articulation.
   Si absent : `UsdPhysics.ArticulationRootAPI.Apply(prim)` manuellement.
10. **ImportConfig** : ajouter `create_physics_scene=True` et `import_inertia_tensor=True`

### Separation of Concerns (Directive CEO Sprint 2)
- RoboticProgramAI = Couches 2 (Interface Corps) et 3 (Monde) UNIQUEMENT
- MonoCLI = ses propres agents. JAMAIS modifier son code, SQLite, tools, playbooks, clusters
- Le PONT entre les systemes = API Contract (doc qui explique comment importer SimAdapter)
- API Contract livre : api_contract_sim_adapter.md sur API Kanban

### Politique RL PPO — Règles d integration
- Le modèle go2_flat.pt produit des POSITIONS articulaires (offsets), PAS des torques
- OmniGraph doit utiliser positionCommand (PAS effortCommand)
- Observation 48-dim : lin_vel(3) + ang_vel(3) + gravity(3) + cmd_vel(3) + joint_pos_rel(12) + joint_vel_rel(12) + last_action(12)
- Actions 12-dim : offsets * scale(0.25) + default_pos → positions cibles
- Frequence controle : 25 Hz (timer ROS2, decimation=8)
- Timeout securite : si pas de /cmd_vel depuis 500ms → positions par defaut (robot debout)

### Phase 1 Spark Ignition — Résultats (2026-02-27)
- Isaac Sim 5.1.0 headless : 1000+ steps stables sur Spark aarch64
- ArticulationRootAPI auto-détecté sur /go2_description/base_link
- Tous topics à ~37 Hz : /clock, /tf, /joint_states (12 DOF), /odom, /joint_commands (sub)
- Fix critique : timeline.play() + render=True nécessaires pour que OmniGraph execute
- PYTHONUNBUFFERED requis pour logs nohup
- 8 itérations (v1→v8) pour arriver à la stabilité
- launch_scene.py final = version v8b sur Spark

### Policy RL — Specs reelles (flat_model_6800.pt)
- Checkpoint : /home/panda/robotics/isaac_sim/references/isaac-go2-ros2/ckpts/unitree_go2/flat_model_6800.pt
- MLP : 48 → 128 → 128 → 128 → 12, ELU
- Frequence : 25 Hz (PAS 50Hz — decimation=8, sim.dt=0.005)
- Action scale : 0.25
- Observations (48 dim, dans l ordre) : base_lin_vel(3) + base_ang_vel(3) + projected_gravity(3) + cmd_vel(3) + joint_pos_rel(12) + joint_vel_rel(12) + last_action(12)
- ATTENTION : base_lin_vel inclus (pas dans le TDD initial)
- ATTENTION : Joint order /joint_states = par TYPE (hips, thighs, calves), policy attend par PATTE — remapping necessaire (R7 confirme)

### Noeud Locomoteur — Architecture finale (#2109 VALIDE)
**Root cause resolu** : la policy RL fonctionne UNIQUEMENT avec Isaac Lab gym env.
Notre custom URDF + DriveAPI ne peut pas repliquer le DCMotor actuator model d Isaac Lab.

**Architecture deployee** :
1. `launch_isaaclab.py` (Python 3.11, Isaac Sim) :
   - Utilise `gym.make("Isaac-Velocity-Flat-Unitree-Go2-v0")` pour la physique
   - Policy MLP tourne dans le meme process
   - Publie l etat robot via UDP (port 9870)
   - Recoit cmd_vel via UDP (port 9871)
2. `ros2_state_bridge.py` (Python 3.12, ROS2 Jazzy) :
   - Recoit etat robot via UDP
   - Publie /odom, /joint_states, /clock, /tf
   - Souscrit /cmd_vel et forward via UDP

**Pourquoi cette architecture** :
- Isaac Lab DCMotor model (effort_limit=23.5, saturation_effort=23.5, velocity_limit=30.0)
  ne peut pas etre replique avec DriveAPI position targets ou meme explicit torque control
- rclpy incompatible : Isaac Sim Python 3.11 vs ROS2 Jazzy Python 3.12
- OmniGraph ROS2 bridge ne charge pas en mode headless (extension bloque)
- UDP bridge = solution propre, zero dependance croisee

**Resultats valides** :
- Robot debout stable : pos_z=0.254, gz=-0.9927 (2000+ steps)
- Topics ROS2 a ~25 Hz : /odom, /joint_states, /clock, /tf
- cmd_vel fonctionnel : vx=0.5 → robot avance sans tomber
- Latence UDP negligeable (localhost)

### Isaac Lab DCMotor vs DriveAPI (lecon critique)
- UNITREE_GO2_CFG utilise `DCMotorCfg` (PAS ImplicitActuatorCfg)
- DCMotor : calcule torques explicitement τ = kp*(q_des-q) + kd*(0-v), clip via speed-torque curve
- DriveAPI : PD implicite sans torque limiting → forces explosives → robot tombe
- Notre test d observation a prouve que obs sont PARFAITES (max_diff=0.000000)
- Le probleme etait 100% dans le modele d actuateur, pas dans les observations

### Architecture finale Noeud Locomoteur (ROOT CAUSE)
La policy RL fonctionne UNIQUEMENT avec Isaac Lab gym env.
Le DCMotor actuator model (effort_limit, speed-torque curve) ne peut pas etre replique avec raw DriveAPI.

Solution deployee — 2 processus sur Spark :
1. launch_isaaclab.py (Python 3.11) : Isaac Lab gym env + RL policy + UDP state publisher
2. ros2_state_bridge.py (Python 3.12) : UDP receiver + ROS2 publisher (/odom /joint_states /clock /tf /cmd_vel)

Communication interne : UDP loopback (rapide, decouple les Python versions)
Robot debout stable : pos_z=0.254, gravity_z=-0.9927, 2000+ steps
Locomotion validee : cmd_vel vx=0.5 → robot avance sans tomber

### Test E2E Sprint 2 — HELLO ROBOT REUSSI (#2110)
Chaine complete validee :
  hello_robot.py → SimAdapter → /cmd_vel → ros2_state_bridge → UDP → launch_isaaclab.py → Isaac Lab → policy RL → mouvement

Resultats :
- connect() OK : /clock + /odom detectes en < 5s
- get_state() : z=0.258 (robot debout), 12 DOF
- move(Twist(0.5)) pendant 2s : deplacement = 0.985m (seuil 0.1m) = PASS
- Pas de chute : z=0.267 final
- Sprint 2 Cognitive Awakening : TERMINE

## Sprint 2 : TERMINE (2026-02-27)
- 16/16 taches (10 actives + 6 transferees MonoCLI)
- 4 agents coordonnes : CEO, STRAT, DEV, SPARK
- Resultat E2E : Go2 avance 0.985m dans Isaac Sim (seuil 0.1m = PASS)
- Robot stable : z=0.258 initial → z=0.267 final (pas de chute)
- Architecture finale : 2 processus (Isaac Lab gym + UDP ROS2 bridge)
- Policy RL : flat_model_6800.pt (PPO, 48→128→128→128→12, 25Hz)
- 8 iterations launch_scene.py (v1→v8b) pour la migration 4.x→5.x
- Decouverte critique : policy RL necessite Isaac Lab gym env (DCMotor actuator)
- Joint order remapping : /joint_states by-type → policy by-leg (R7 resolu)
- Chaine validee : hello_robot.py → SimAdapter → /cmd_vel → UDP → Isaac Lab → policy RL → robot avance
- Pret pour Sprint 3 : MonoCLI integration, Go2Adapter reel, Vision Pro

### Streaming visuel aarch64 (Directive CEO post-Sprint 2) — RESOLU
- **WebRTC NON SUPPORTE** sur aarch64/DGX Spark (pas de NVENC sur Grace ARM)
- **MJPEG Omniverse IMPOSSIBLE** : use_fabric=True requis pour camera rendering,
  mais casse la physique Isaac Lab sur CPU (robot tombe). use_fabric=False = camera vide.
  Torch CUDA non disponible sur ARM (torch 2.7.0+cpu). 8 tentatives, meme probleme.
- **SOLUTION DEPLOYEE** : Three.js Web Viewer (3 processus)
  1. launch_isaaclab.py → physique CPU stable → UDP ports 9870+9872
  2. web_viewer.py → HTTP server → recoit UDP, sert HTML + /state JSON
  3. Browser Mac → Three.js stick-figure robot 3D, 25Hz, OrbitControls
- **URL** : http://<SPARK_IP>:8080/
- Fichier viewer : /robotics_env/sim/web_viewer.py

### Documents projet (API Kanban)
- vision_strategique.md : Vision CEO Infinity Cloud (Compagnons Evolutifs, Silver Economy)
- api_contract_sim_adapter.md : API Contract SimAdapter v1.0
- tdd_sprint2.md : TDD Sprint 2 v2.0
- technical_design_document.md : TDD Sprint 1 v1.3
- architecture_3_couches.md, insights.md, research_A/B

### Observabilite visuelle — Web Viewer 3D (#2111 RESOLU)
Le MJPEG via Omniverse rendering est IMPOSSIBLE sur aarch64+CPU :
- Camera Omniverse fonctionne avec use_fabric=True mais casse la physique
- use_fabric=False : physique OK mais camera vide
- Torch CUDA non disponible (torch 2.7.0+cpu sur ARM)
- 8 iterations testees, toutes echouent au meme probleme fondamental

**Solution deployee** : Three.js Web Viewer (3eme processus)
- web_viewer.py : serveur HTTP Python, recoit etat UDP, sert HTML+JSON
- Browser : Three.js stick-figure 3D, 12 joints, camera follow, telemetrie live, 25Hz
- URL : http://<SPARK_IP>:8080/
- Architecture = 3 processus : launch_isaaclab.py + ros2_state_bridge.py + web_viewer.py
- Amelioration possible : charger meshes Go2 via urdf-loader Three.js

## Sprint 3 : Le Pont Cognitif (TERMINE 2026-02-27)
- 5/5 taches, 2 phases (Sprint ID 160, Blocks 459-460)
- Objectif : creer les wrappers CLI pour que MonoCLI pilote le Go2 via Playbooks
- Directive CEO respectee : ZERO touche MonoCLI, scripts CLI autonomes

### Wrappers CLI livres
- `mono_robot_sense.py` : lecture etat robot → texte LLM-readable sur stdout
  - Position, orientation, stabilite, nombre joints, temps simulation
  - Detecte robot tombe (Z < 0.15)
  - Communication : UDP port 9872 (meme que web_viewer)
  - Exit code 0 = succes, 1 = erreur (message sur stderr)
- `mono_robot_move.py <vx> <vy> <duration>` : commande mouvement CLI
  - Envoie Twist pendant X secondes, stop automatique
  - Securites : vitesse max 1.0 m/s, duree max 10s
  - Retourne position finale sur stdout
  - Exit code 0 = succes, 1 = erreur

### API Contract v2.0
- Document frontiere absolue entre equipe Robotics et equipe MonoCLI
- Publie sur API Kanban : API_CONTRACT_v2.md
- Fichier local : docs/API_CONTRACT.md
- Contient : usage CLI, arguments, sorties stdout, codes retour, exemple Playbook YAML, integration mono_shell + SSH

### Limitation connue — Strafe laterale
- mono_robot_move.py avec vy != 0 peut faire tomber le robot
- Policy RL (flat_model_6800.pt) entrainee principalement pour marche avant
- Le strafe (mouvement lateral) est hors distribution d entrainement
- mono_robot_sense.py detecte correctement la chute (Z=0.057 → "au sol")

### Resultats E2E Sprint 3
- SENSE : "stable (debout), X=-0.04, Y=-0.01, Z=0.254, yaw=-6.4°, 12 joints actifs"
- MOVE vx=0.5 2s : deplacement 0.842m (OK)
- SENSE apres move : "stable (debout), X=0.81, Z=0.240" (position changee)
- MOVE strafe vy=0.3 1.5s : deplacement 0.220m mais robot tombe (limite RL)
- SENSE apres chute : detecte correctement "au sol (tombe), Z=0.057"

### Integration MonoCLI — Feu Vert CEO (2026-02-27)
- API_CONTRACT.md v2.0 valide par equipe MonoCLI
- Equipe MonoCLI en cours de :
  1. Creation profil "Jedi Go2 Robotics" dans jedi_profiles
  2. Configuration Groq API (Llama-3 70b)
  3. Coding wrappers SSH vers mono_robot_sense.py et mono_robot_move.py
- Premier Playbook autonome imminent
- Equipe Robotics en STANDBY ACTIF (monitoring Spark)

### Web Viewer — Fix ThreadingHTTPServer
- HTTPServer Python = single-threaded → bloque si connexion pendante
- Fix : ThreadingHTTPServer (chaque connexion dans son propre thread)
- Fix rotation Three.js : suppression rotation -90° parasite sur axe X


### Session 2026-02-28 — Maintenance & Fix Physique

#### Bug physique : Robot glisse + pieds clipping sol
**Root cause** : `go2_env.py` manquait le `physics_material` sur le ground plane.
Le RL policy (flat_model_6800.pt) a ete entraine avec `static_friction=1.0, dynamic_friction=1.0`
(cf `velocity_env_cfg.py` ligne 53-54), mais notre env custom avait friction par defaut PhysX (~0.5).

**3 fixes appliques** (go2_env.py) :
1. `GroundPlaneCfg` → ajout `physics_material=RigidBodyMaterialCfg(static=1.0, dynamic=1.0, restitution=0.0)`
2. `sim.physics_material` global → memes valeurs (decommenter + adapter)
3. `sim.disable_contact_processing = False` (etait True → causait clipping pieds)

**Resultat** : Robot Z=0.273 (vs 0.254 avant), mouvement 0.3m/s x 2s = 0.582m (97% theorique vs ~30cm avant)

**REGLE** : Toujours matcher friction sol avec les parametres training RL. Verifier velocity_env_cfg.py.

#### mono_robot_reset.py — Script reset a chaud
- Reset le robot via signal UDP port 9873 (b RESETGO2 → b RESET_OK)
- launch_isaaclab.py patche : UDPBridge.check_reset() dans main loop, appelle env.reset()
- Note : env.reset() remet le robot debout mais ne teleporte pas a (0,0) exactement
- Nouveau arg CLI : --reset-port 9873

#### Import collision types.py (PIEGE)
- Le dossier `adapters/` contient `types.py` (RobotState, Twist, etc.)
- Si on execute un script DEPUIS le dossier adapters, Python importe ce types.py au lieu de stdlib types
- **REGLE** : Toujours lancer les scripts avec `cd /tmp &&` en prefixe
- Documente dans API CONTRACT v2.1

#### API CONTRACT v2.1 (2026-02-28)
- 3 scripts documentes : sense, move, reset
- Ajout section ports UDP/HTTP
- Correction : toujours prefixer `cd /tmp &&`
- Publie sur API Kanban : API_CONTRACT_v2.md


#### Bug reset env.reset() ne remet pas le robot debout (CRITIQUE)
**Root cause** : `Articulation.reset()` ne reset que actuators/wrenches, PAS root pose ni joints.
Le reset physique depend du Event Manager (mode=reset). Notre `EventCfg` etait VIDE.
**Fix** : Ajouter dans go2_env.py :
```python
class EventCfg:
    reset_scene = EventTerm(
        func=mdp.reset_scene_to_default,
        mode="reset",
        params={"reset_joint_targets": True},
    )
```
**REGLE** : Toujours definir des events de reset dans EventCfg. Sans eux, env.reset() ne fait rien physiquement.

#### Bug InferenceMode crash sur env.reset()
env.reset() appele hors torch.inference_mode() crash car les tensors internes
(root_link_pose_w) ont ete crees dans inference_mode par env.step().
**Fix** : Wrapper env.reset() dans `with torch.inference_mode():`
**REGLE** : Tout appel env.reset() ou env.step() doit etre dans inference_mode si la policy tourne en inference_mode.

## Sprint 4 : Hospital Digital Twin & Vision Pro Cockpit

### Regles Scene Hospitaliere (Isaac Sim USD)

#### Composition USD overlay
- **APPROCHE** : GroundPlane Isaac Lab (physique) + Hospital USD par-dessus (visuel uniquement)
- **NE PAS** utiliser TerrainImporterCfg pour la scene hospital (regressions 5.x connues)
- Le ground plane physique (Z=0, friction 1.0/1.0) reste IDENTIQUE au training RL
- Hospital USD = decoration, PAS de physique. Ajouter colliders separement (box/capsule)
- **API** : `add_reference_to_stage(usd_path, prim_path)` pour composer la scene

#### Assets Nucleus Isaac Sim
- Hospital : `{ISAAC_NUCLEUS_DIR}/Environments/Hospital/hospital.usd`
- Humain docteur : `{ISAAC_NUCLEUS_DIR}/People/Characters/original_male_adult_medical_01/male_adult_medical_01.usd`
- **Fallback** : Si Nucleus inaccessible en headless, utiliser primitives (box murs, cylindre humain)
- **REGLE** : Toujours tester acces Nucleus avec `omni.client.list()` avant chargement

#### Timing stage access
- Le stage USD n est accessible qu APRES `gym.make()`
- Ajout d assets hospital = ENTRE `gym.make()` et `env.reset()`
- NE PAS modifier go2_env.py ni launch_isaaclab.py

#### Obstacles avec colliders simplifies
- Lit : box collider (2.0 x 0.9 x 0.6m), PAS de mesh collider (trop lourd)
- Humain : capsule collider (r=0.25m, h=1.8m), mesh USD = visuel uniquement
- Friction obstacles : 0.5/0.5 (different du sol 1.0/1.0 — les obstacles ne bougent pas)

### Regles Vision Pro Cockpit (visionOS)

#### Stack technique confirmee
- **SwiftUI + RealityKit natif** — PAS Unity PolySpatial (pas de LowLevelMesh, pas de ViewAttachment, overhead traduction)
- **Foxglove WebSocket Bridge** pour transport ROS2 → Vision Pro (CDR binaire, zero code serveur, pkg ROS2 C++)
- **LowLevelMesh + Metal** pour point cloud GPU-native
- PAS de rosbridge (JSON trop lent pour point cloud, Python trop lent)

#### Foxglove Bridge
- Installation : `sudo apt install ros-jazzy-foxglove-bridge`
- Port : 8765 (WebSocket)
- Protocole : CDR binaire (format natif ROS2), zero serialisation intermediaire
- Bidirectionnel : le client Vision Pro peut publier /cmd_vel
- **REGLE** : Foxglove remplace tout bridge custom (gRPC, Protobuf, etc.)

#### Topics ROS2 pour Vision Pro
- /odom, /joint_states, /tf, /clock → dashboard + animation 3D (25Hz)
- /jedi/thoughts (std_msgs/String, JSON) → bulles LLM (1-5Hz, evenementiel)
- /jedi/plan (nav_msgs/Path) → trajectoire planifiee (futur)
- /lidar/points (PointCloud2) → nuage de points (10Hz)
- /cmd_vel (Twist) → teleop Vision Pro → robot (25Hz, bidirectionnel)

#### References architecturales
- VisionProTeleop v2.50 (MIT) : hand tracking → robot, WebRTC, MuJoCo→USD
- ARMADA (Apple ML Research) : ROS + WebSocket overlay robot en MR
- metal-spatial-dynamic-mesh : LowLevelMesh + Metal compute a 60fps

#### Developpement en 4 phases
- Phase 1 : Static Cockpit (HTTP polling /state, SwiftUI dashboard, cube placeholder)
- Phase 2 : Live State (Foxglove WS 25Hz, Go2 USDZ anime, CDR parser Swift)
- Phase 3 : Point Cloud + LLM Overlay (LowLevelMesh, Metal compute, bulles pensees)
- Phase 4 : Enterprise + Teleop (hand tracking, SharedCoordinateSpaceProvider visionOS 26)

#### VISION-01 Camera Pipeline — VALIDE (2026-03-01)
- **DECOUVERTE** : `--enable_cameras` active le rendu headless (isaaclab.python.headless.rendering.kit)
- Extensions requises : `omni.replicator.core` + `omni.syntheticdata` (activation manuelle via ext_manager)
- CameraCfg Isaac Lab fonctionne sur Spark aarch64 GB10 en headless
- Resolution : 640x480, FOV 90°, attachee au Go2 base/front_camera
- Frequence : 2.5 Hz (capture toutes les 10 steps), JPEG quality 80
- **REGLE** : Toujours ajouter `--enable_cameras` dans la commande de lancement si camera requise
- **REGLE** : NE PAS confondre avec le probleme MJPEG Sprint 2 (use_fabric). CameraCfg est une approche differente qui fonctionne.

##### Architecture Camera Pipeline (3 etapes)
1. **launch_isaaclab.py** : CameraCapture class, warm-up 20x simulation_app.update(), JPEG UDP port 9874
2. **camera_bridge.py** (Python 3.12 ROS2) : recoit UDP 9874, decode JPEG, publie /camera/color/image_raw (rgb8) + /camera/camera_info
3. **Validation** : validate_camera.py subscriber → /tmp/camera_test_ros2.png (122KB)

##### Bug resolu : "zero-size array to reduction operation"
- **Cause** : `data.max()` appele sur array vide (annotator pas pret)
- **Fix A** : check `data.size == 0` AVANT `data.max()` (evite crash)
- **Fix B** : warm-up 20x `simulation_app.update()` dans setup() (pipeline rendu initialise)
- **Fix C** : skip 50 premiers steps (renderer doit etre chaud)
- **REGLE** : Les annotateurs omni.replicator retournent des arrays vides les premieres frames. Toujours verifier `data.size == 0` avant tout traitement.

##### Biais rotation RL (2026-03-02)
- La policy flat_model_6800.pt a un biais de rotation positif (vers la gauche)
- Tourner a droite (yaw negatif) echoue avec wz_max=0.6 (trop faible pour vaincre le biais)
- **REGLE** : wz_max=1.0 minimum pour les rotations. NE PAS descendre en dessous de 0.8
- Les 3 tests (target -83, 0, +90) passent avec wz_max=1.0

##### Heading drift et stabilite (2026-03-02)
- Le robot derive en yaw (~100° apres 3 segments de marche a 0.5 m/s)
- cmd_vel est en ROBOT FRAME : si le yaw derive, vx ne pointe plus vers la cible
- Chaque turn accumule de l instabilite articulaire
- Duree max operation : ~50-60s avant chute (Z<0.22 = danger)
- **STRATEGIE** : turn → stand 2s → move 3s → stand 2s --auto-reset → repeat
- Meilleur resultat approche docteur : X=4.14 (1.4m de la cible a X=5.0)

##### Ports UDP (recapitulatif complet)
| Port  | Direction         | Contenu                  |
|-------|-------------------|--------------------------|
| 9870  | Isaac → Viewer    | Robot state (304 bytes)  |
| 9871  | Viewer → Isaac    | cmd_vel (24 bytes)       |
| 9872  | Isaac → ROS2      | Robot state (304 bytes)  |
| 9873  | Reset → Isaac     | RESETGO2 signal          |
| 9874  | Isaac → ROS2 cam  | JPEG frames (header 4B + data) |

#### LiveStream WebRTC NON SUPPORTE aarch64 (DEFINITIF)
- `omni.kit.livestream.webrtc` n existe que pour lx64 (x86 Linux) et wx64 (Windows)
- AUCUNE version aarch64 dans le registry Omniverse — confirme par NVIDIA
- Le GPU GB10 du Spark fait du compute (PhysX, RL) mais le pipeline de streaming RTX n est pas porte sur ARM
- **REGLE** : Ne JAMAIS retenter le livestream WebRTC sur Spark. Pour du rendu photorealiste temps reel, il faut un serveur x86 avec GPU NVIDIA.
- Alternatives visuelles : Three.js web viewer (upgrade meshes) ou export USD statique vers Mac

#### omni.client bloque sans Nucleus (CRITIQUE)
- `omni.client.stat()` et `omni.client.list()` bloquent INDEFINIMENT si Nucleus n est pas demarre
- Le Spark n a PAS de Nucleus local actif en mode headless
- **REGLE** : Toujours ajouter `--skip-nucleus` flag (default=True sur Spark) ou timeout threading 3s
- Le DEV a patche launch_hospital_scene.py avec ce flag le 2026-02-28

#### Test collision — Geometrie a considerer
- Les obstacles (lit Y=-1.5, docteur Y=1.0) ne sont PAS sur la trajectoire directe du robot (Y≈0)
- Le strafe (vy) destabilise le robot → impossible d atteindre les obstacles lateraux
- Le test de collision physique est INCONCLUS (pas FAIL) — les colliders existent dans le code
- Pour un vrai test : placer un obstacle sur Y=0 devant le robot, ou utiliser une policy entrainee au strafe

#### Stabilite RL sur longue marche — RESOLU (2026-03-03)
- ~~Policy flat_model_6800.pt instable apres ~4-5s de marche continue a 0.5 m/s~~
- **RESOLU** : Swap vers `rough_model_7850.pt` (Isaac-Velocity-Rough-Unitree-Go2-v0)
- Ancien flat model : 983KB, MLP 48→128³→12, obs 48-dim, chute après ~50s (7 cycles)
- Nouveau rough model : 6.8MB, MLP 235→512→256→128→12, obs 235-dim (+ height scan 187-dim via RayCaster)

##### Root cause fatigue PPO (flat model)
- **last_action feedback loop** : obs dims 36-47 = sortie precedente du policy
- En training : episodes de 20s max, reset automatique → last_action remis a zero
- En production : PAS de reset periodique → accumulation erreurs apres ~50s (2.5x episode_length)
- = Distribution shift classique RL deploye
- Solution alternative (non necessaire avec rough) : reset `env.unwrapped.action_manager.action[:] = 0.0` toutes les 15s

##### Resultats comparatifs rough vs flat
| Metrique | flat_model_6800 | rough_model_7850 | Delta |
|----------|----------------|------------------|-------|
| Z stable moyen | 0.270m | 0.380m | +41% |
| Cycles avant chute | 7 (puis fall) | 17+ (no fall) | +143% |
| Duree max | ~50s | 160s+ continu | +220% |
| Distance max | 3.15m | 22.8m (A/R) | +623% |

- **REGLE** : Toujours utiliser rough_model_7850.pt. Le flat model est OBSOLETE.
- **REGLE** : Le rough model utilise Isaac-Velocity-Rough-Unitree-Go2-v0 (PAS Flat)
- **REGLE** : height_scan actif (187 dims via RayCaster) — ne PAS le desactiver
- **REGLE** : launch_hospital_scene.py DOIT aussi utiliser rough model (obs=235, MLP=[512,256,128], env=Rough). Bug 2026-03-05 : flat model charge par erreur → Z=0.255, chute cycle 2.
- **REGLE** : TOUTE copie de la config RL (launch_isaaclab.py OU launch_hospital_scene.py) doit etre synchronisee : policy, obs_dim, hidden_dims, env_id, friction=1.0/1.0
- **REGLE** : Robot GLB rotation.y = -Math.PI/2 obligatoire (front GLB face +Z, Isaac face +X). Sans offset = crab-walk 90°. Meme pattern que Doctor (-PI/2) et BestFriend (PI).

### Workflow multi-agents (Regles de coordination)

#### STRAT ne SSH PAS vers Spark
- **REGLE** : Le STRAT coordonne via tmux, il n execute PAS de commandes sur les serveurs
- Commandes Spark → agent Spark (spark_agents:1.1)
- Instructions DEV → send_to_dev.sh (roboticprogramai_agents:1.2)
- SSH direct = violation de role, meme en urgence

### Documents Sprint 4 (API Kanban)
- SPEC_hospital_scene.md : specs scene hospitaliere pour DEV
- TDD_VISION_PRO_COCKPIT_v2.md : TDD architecture Vision Pro v2.0 (remplace v1.0)

### Resultats Sprint 4 (2026-02-28) — TERMINE 100%
- Mission A Hospital : VALIDEE (MVP)
  - launch_hospital_scene.py : 576 lignes (upgrade avec BestFriend), fallback primitives + S3 USD
  - Tests PASS : move (0.899m/2s), sense (stable 12 DOF), reset (retour origine)
  - Collision : INCONCLUS (geometrie, pas un bug)
  - Robot debout stable : Z=0.257, gravity=-0.9962
- Mission B Vision Pro : TDD v2.0 publie, VALIDE par CEO (#2126 DONE)
  - Stack : SwiftUI + RealityKit + Foxglove WS + LowLevelMesh
  - 4 phases de developpement planifiees

### Tactical Demo Viewer (2026-02-28/03-01)
- web_viewer.py upgrade : 558L → 612L+ avec style radar/LiDAR
- Background noir + scanlines CSS + HUD (TACTICAL VIEW, LIVE, position, velocite)
- 4 murs wireframe cyan, grille sol, lit orange, docteur cyan, labels sprites
- Mapping Isaac→Three.js : (ix, iz, -iy)
- GLTFLoader integre pour meshes 3D reels (BestFriend.glb)
- Route HTTP /assets/bestfriend.glb sert fichier binaire avec cache 1h
- Auto-scale basé sur targetHeight/currentHeight ratio
- Fallback sphere orange si GLB absent

### Pipeline Custom Assets USDZ (2026-03-01)
- **Workflow** : Apple USDZ → Blender CLI (Mac) → GLB → SCP Spark → web_viewer.py sert via HTTP → Three.js GLTFLoader
- **Conversion** : `/opt/homebrew/bin/blender --background --python convert.py`
  - `bpy.ops.wm.usd_import()` (Blender 4.4+) puis `bpy.ops.export_scene.gltf(export_format='GLB')`
- **Stockage Spark** : /home/panda/robotics/assets/custom/ (USDZ + GLB)
- **Isaac Sim** : charge USDZ nativement via `add_reference_to_stage()`, CollisionAPI convexHull auto
- **REGLE** : usd-core n a PAS de wheel aarch64. NE PAS tenter pip install usd-core sur Spark.
- **REGLE** : Toujours convertir USDZ→GLB sur Mac (Blender) avant deploiement web

### BestFriend.usdz — Integration complete (2026-03-01)
- Asset : renard 3D stylise (fox), 8.2MB USDZ, 7.9MB GLB
- Contenu USDZ : BestFriend.usdc (898KB) + Image_0.png (7MB texture)
- Bounding box Isaac Sim : 0.65 x 1.14 x 1.27m
- Position : (1.5, 0.5, 0.0), yaw=180° (face robot)
- CollisionAPI convexHull (statique, pas de RigidBodyAPI)
- CLI args : --custom-asset PATH --bestfriend-pos X Y Z
- State JSON : bestfriend:{pos:[x,y,z], active:true}
- Three.js : vrai mesh 3D via GLTFLoader, auto-scale 0.55m, label BEST FRIEND orange

### Doctor.glb — Integration (2026-03-01)
- Asset : docteur 3D genere par pipeline Flux+Hunyuan3D (100% maison, sur Spark)
- Fichier : /home/panda/robotics/assets/custom/Doctor.glb (8.9MB, 150k faces)
- Position : (3.0, 1.0, 0.0), auto-scale targetHeight=1.7m
- Remplace le cylindre cyan placeholder PATIENT
- CLI args : --doctor-pos X Y Z --doctor-asset PATH
- State JSON : doctor:{pos:[x,y,z], active:true}
- Meme pattern que BestFriend : GLTFLoader + metalness=0 + roughness=0.8 + fallback cylindre
- web_viewer.py : 542 lignes avec BestFriend + Doctor

### CHECKLIST OBLIGATOIRE — Integration asset GLB dans web_viewer.py (2026-03-01)
Chaque nouvel asset GLB DOIT suivre cette checklist. Erreurs deja faites 2+ fois sinon.

1. **METALNESS** : Apres chargement, traverser TOUS les meshes et forcer metalness=0, roughness=0.8.
   ATTENTION : certains meshes ont material en ARRAY (multi-material). Toujours gerer les deux cas :
   ```
   const mats = Array.isArray(child.material) ? child.material : [child.material];
   mats.forEach(m => { m.metalness = 0; m.roughness = 0.8; m.needsUpdate = true; });
   ```
   Sans ce fix → mesh NOIR (metalness=1.0 par defaut sans environment map).

2. **POSITION Y (pieds au sol)** : Les meshes GLB ont souvent leur origine au CENTRE, pas aux pieds.
   Apres scale + position, recalculer bounding box et offset :
   ```
   const box = new THREE.Box3().setFromObject(model);
   model.position.y += -box.min.y;
   ```
   Sans ce fix → modele enfonce dans le sol.

3. **AUTO-SCALE** : Calculer ratio targetHeight / currentBBoxHeight. Appliquer model.scale.setScalar(ratio).
   Heights de reference : humain=1.7m, animal petit=0.55m.

4. **LUMIERES** : Les assets GLB utilisent MeshStandardMaterial (PBR) qui NECESSITE des lumieres.
   Lumieres requises dans la scene :
   - AmbientLight(0xffffff, 2.0)
   - DirectionalLight(0xffffff, 1.5) position (5, 10, 5)
   - HemisphereLight(0xffffff, 0x444444, 1.0)

5. **Go2 MeshBasicMaterial** : Le Go2 (stick-figure ET skin GLB Hunyuan3D) utilise MeshBasicMaterial (unlit, toujours visible). Le skin Hunyuan3D a des normals inversees — MeshStandardMaterial ne fonctionne PAS. MeshBasicMaterial 0x00ccaa = look hologramme TRON.

6. **FALLBACK** : Si GLB absent ou erreur, garder la primitive placeholder (sphere, cylindre, box).

7. **ROUTE HTTP** : Ajouter GET /assets/nom.glb, Content-Type octet-stream, cache 1h.

8. **STATE JSON** : Ajouter champ dans /state : {pos:[x,y,z], active:true}.

9. **CLI ARGS** : --nom-pos X Y Z + --nom-asset PATH.

### Sprint 16 : Evolution Cognitive (2026-03-03) — TERMINE 23/23
- mono_robot_look.py = pont perception entre caméra et cerveau MonoCLI
- Robotics FOURNIT les outils de capture. MonoCLI RAISONNE sur les images.
- **REGLE** : Séparation perception/cognition. NE PAS mettre de logique IA dans les scripts Robotics.
- **REGLE** : Les métriques goto.py METRICS sont ADDITIVES (ne cassent pas l'output existant)
- **REGLE** : goto.py --robot supporte 5 profils : go2 (défaut), spot, h1, anymal_c, g1
  - Humanoïdes (h1, g1) : gains faibles (kp≤1.2), pulses courts, stands longs — bipèdes fragiles
  - Quadrupèdes lourds (spot, anymal_c) : gains modérés, vitesse réduite vs Go2
  - Flags CLI explicites écrasent toujours le profil
- **REGLE** : Port UDP 9875 = camera frames → web_viewer.py (en plus de 9874 → camera_bridge.py)
- rough_model_7850.pt = modèle OFFICIEL depuis 2026-03-03 (flat obsolète)
- **REGLE** : Navigation PERCEPTIVE > AVEUGLE. Toujours verifier avec camera a mi-parcours.
- **REGLE** : Un checkpoint perception a 50% du trajet coute ~3s mais economise 9.3s en cas de perturbation.
- Baseline : 38.2s (3 runs, 100% success). Perturbation : 53.3s (+39.5%). Evolue : 44.0s (-6.7% distance).
- VLM Spark : NO-GO (Nemotron-3-Nano-30B text-only). Perception visuelle = MonoCLI via Groq VLM.

### Sprint 17 : Perturbation Obstacle Niveau 3 (2026-03-03) — TERMINE 7/7
- Obstacle box 1.0x1.0x0.6m avec collider actif a (2.5, 0, 0) sur trajectoire directe
- **REGLE** : Navigation aveugle peut contourner PAR HASARD (drift RL, 64.2s) mais NON REPRODUCTIBLE
- **REGLE** : Navigation cognitive (checkpoint + camera + contournement Y±2m) = SUCCESS 73.2s, PLANIFIE
- **REGLE** : Valeur du cognitif = PREDICTIBILITE + REPRODUCTIBILITE, pas la vitesse
- **REGLE** : Cout contournement obstacle = +91.6% temps, +59.3% distance vs baseline directe
- **REGLE** : 3 niveaux perturbation geres : baseline, cible deplacee, obstacle physique
- Rapport positionnement HTML : rapport_positionnement.html (architecture, resultats, concurrence, roadmap)
- Concurrence analysee : SayCan, RT-2, Helix, pi0, GR00T, UnifoLM — aucun ne combine multi-agent LLM + memoire persistante + distillation + evolution cognitive mesurable

### Sprint 18 : Patrouille Adaptative — Boucle Genetique (2026-03-03) — TERMINE 8/8
- Patrouille 3 waypoints : WP-A(2,2) WP-B(4,-1.5) WP-C(5,0)
- Gen 1 naive (O→A→B→C) : 87.3s, 11.34m, 17 cycles — segment A→B = goulot (virage 120°)
- Gen 1 bis (perception) : 108.7s (+24.5%) — overhead concentre sur recalculations A→B
- Gen 2 evoluee (O→A→C→B) : 71.2s, 10.00m, 14 cycles — **-18.4% temps, -11.8% distance**
- **REGLE** : Boucle genetique = percevoir → decider → agir → apprendre → evoluer
- **REGLE** : Reordonnement topologique des waypoints peut gagner ~18% sur patrouille
- **REGLE** : Virages >90° sont des goulots — les eviter par reordonnement de route
- **REGLE** : dist_stop 0.5 suffit en patrouille (pas besoin de 0.3m)
- **REGLE** : Perception ciblee > perception systematique (evite overhead inutile)
- Chute constatee sur virage 45° initial (WP-A) — le rough model peut tomber sur virages brusques

### Pipeline 3D Assets — Deux sources (2026-03-01)
- **Source A — Apple USDZ** : USDZ → Blender CLI Mac → GLB → SCP Spark (ex: BestFriend)
- **Source B — Flux+Hunyuan3D** : generation IA directement sur Spark → GLB (ex: Doctor)
- Les deux convergent vers le meme format GLB dans /home/panda/robotics/assets/custom/
- web_viewer.py sert via HTTP route /assets/*.glb

### Viewer TRON Redesign — QA Lessons (2026-03-04)
- Esthetique TRON: GridHelper cyan 200x200 100div + fond noir + murs arene mesh solides (BoxGeometry 0.05 epaisseur, 2-3m hauteur) + piliers aux coins
- Robot Go2 skin: go2_skin.glb (14MB Hunyuan3D) = mesh unique organique, MeshBasicMaterial 0x00ccaa + outline BackSide scale 1.06 cyan + halo radial gradient au sol + PointLight tracking 50
- **REGLE** : Hunyuan3D GLB a des normals inversees → MeshStandardMaterial ne fonctionne PAS → utiliser MeshBasicMaterial (unlit)
- **REGLE** : UnrealBloomPass impossible via CDN Three.js 0.128.0 → CSS filter brightness(1.15) contrast(1.2) + box-shadow cyan 40px comme alternative
- **REGLE** : QA visuel OBLIGATOIRE avant livraison (Playwright screenshots wide+medium+close, sub-agent DA 8 criteres, seuil APPROVED ≥7.5/10)
- **REGLE** : TOUJOURS inclure vue zoom close dans le QA — la vue large cache les problemes de position/texture
- Mobilier: emissive cyan 0x00ffff intensity 0.4 pour visibilite sans domination
- Telemetrie: font augmentee 50% pour lisibilite 1920x1080
- Scores QA progression: 5.8→6.5→6.3→7.0→7.5→7.65→6.3→7.25→7.9 (APPROVED v9 en 9 passes)
- Assets GLB sur Spark: /home/panda/robotics/assets/custom/ (go2_skin.glb, go2.glb, Doctor.glb, BestFriend.glb, hospital_bed.glb, heart_monitor.glb, visitor_chair.glb)
- **REGLE** : Pour tronifier un GLB, SUPPRIMER toutes les texture maps (map, normalMap, bumpMap, roughnessMap, metalnessMap, emissiveMap, aoMap = null) AVANT de forcer color/emissive. Sinon les maps overrident les proprietes material.
- **REGLE** : EdgesGeometry avec thresholdAngle bas (1-5) + duplicate a scale 1.005-1.01 = effet circuit lines TRON dense
- **REGLE** : Docteur tronifie = color 0x0a0a0a + emissive teal 0x00aaaa intensity 0.8 + metalness 0.9 + roughness 0.2
- Robot Go2 SKIN2 (default) : robot_tron_final.glb (9.6MB) Geometric Head, EdgesGeometry rouge #ff4400 threshold 1, halo orange
- 4 modes toggle : STICK (wireframe debug) → REAL (go2.glb URDF) → SKIN1 (go2_skin.glb cyan) → SKIN2 (robot_tron_final.glb rouge)
- Tron World decoratif (positions v10 finales, DANS/AUTOUR arene) :
  - recognizer.glb (12MB) : ARCHE au sol (3,0,0), pieds groundes, 12m haut, robot passe DESSOUS. PAS un vaisseau flottant.
  - light_cycle.glb (8.4MB) : moto garee (-2,0,2), taille realiste 2m, au sol
  - identity_disc.glb (9.7MB) : (6,1.5,-2) pres docteur, 1.6m, spin 0.03/frame, orange 0xff6600
  - mcp_tower.glb (4.8MB) : (8,0,0) bordure arene, structure verticale sombre
- **REGLE** : Assets Tron DANS/AUTOUR de l'arene. Positions proportionnelles a la taille arene.
- Arene agrandie 25x15m (2026-03-05) : murs X=[-5,+20] Z=[-7.5,+7.5], camera (8,15,20)→(8,0,0)
- Positions v11 25x15m : Recognizer (10,0,0) scale 12 grounded, Light Cycle (-3,0,6), Identity Disc (15,1.5,-4), MCP Tower (19,0,0)
- Docteur visuel (12,0,-3), Lit (12,0,-4.5), BF (8,0,2), Chaise (11,0,-5) en Three.js
- **REGLE** : Les positions meubles/personnages sont VISUELLES (web_viewer.py). Isaac Sim tourne sur ground plane infini. Pas de restart Isaac necessaire pour changements visuels.
- **REGLE** : Tronifier GLB = supprimer TOUTES texture maps (map/normalMap/etc=null) + color 0x050505 + emissive teal 0x006666 intensity 0.4
- Scores QA v10 final : 5.8→6.5→6.3→7.0→7.5→7.65→6.3→7.25→7.9→7.6 (APPROVED v9+v10)
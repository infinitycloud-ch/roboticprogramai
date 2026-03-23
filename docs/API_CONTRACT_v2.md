# API CONTRACT — Pont Cognitif MonoCLI ↔ Robotics
## Interface CLI pour Agents MonoCLI (Playbooks & Skills)

**Version** : 2.7
**Date** : 3 Mars 2026
**Auteur** : STRAT (RoboticProgramAI)
**Statut** : Frontière absolue entre équipe Robotics et équipe MonoCLI

---

## 1. Principe

L'équipe Robotics fournit **7 scripts Python CLI** exécutables sur le serveur Spark (<SPARK_IP>). L'équipe MonoCLI les appelle via `mono_shell` ou des Playbooks YAML. **Aucun import Python croisé, aucune dépendance partagée.**

```
┌──────────────────┐         SSH / shell          ┌──────────────────────┐
│  MonoCLI (Jedi)  │ ──── mono_shell ────────────→│  Spark (<SPARK_IP>)│
│  Groq / Ollama   │                              │                      │
│                  │  python3 mono_robot_sense.py  │  → stdout: état robot│
│                  │  python3 mono_robot_move.py   │  → stdout: résultat  │
│                  │  python3 mono_robot_turn.py   │  → stdout: résultat  │
│                  │  python3 mono_robot_stand.py  │  → stdout: stabilité │
│                  │  python3 mono_robot_goto.py   │  → stdout: navigation│
│                  │  python3 mono_robot_look.py   │  → stdout: perception│
│                  │  python3 mono_robot_reset.py  │  → stdout: reset     │
└──────────────────┘                              └──────────────────────┘
```

---

## 2. Prérequis

### Sur le Spark (déjà configuré)
Les 3 processus de simulation doivent tourner :
```bash
# Processus 1 : Simulation physique Isaac Lab
cd /home/panda/robotics/robotics_env/sim
python3 launch_isaaclab.py

# Processus 2 : Bridge ROS2
python3 ros2_state_bridge.py

# Processus 3 : Web Viewer (optionnel, pour observation visuelle)
python3 web_viewer.py
```

### Vérification rapide
```bash
curl -s http://<SPARK_IP>:8080/state | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Sim OK: z={d[\"position\"][2]:.3f}')"
```

---

## 3. Script 1 : `mono_robot_sense.py` (Lecture État)

### Emplacement
```
/home/panda/robotics/robotics_env/adapters/mono_robot_sense.py
```

### Usage
```bash
python3 /home/panda/robotics/robotics_env/adapters/mono_robot_sense.py
```

### Pas d'arguments. Lecture seule. Exécution unique (pas de boucle).

### Sortie stdout (texte LLM-readable)
```
Le robot est stable. Position X=-0.04, Y=-0.01, Z=0.254. Orientation: yaw=2.1 deg. 12 joints actifs. Aucun obstacle critique. Simulation t=6795.6s.
```

### Codes retour
| Code | Signification |
|------|--------------|
| 0 | Succès — état lu correctement |
| 1 | Erreur — simulation non accessible (message sur stderr) |

### Ce que le LLM reçoit
Un texte en français, une seule ligne, décrivant :
- Stabilité du robot (stable / instable / tombé)
- Position X, Y, Z en mètres
- Orientation yaw en degrés
- Nombre de joints actifs
- Temps de simulation
- Alertes éventuelles (robot tombé si Z < 0.15)

---

## 4. Script 2 : `mono_robot_move.py` (Commande Mouvement)

### Emplacement
```
/home/panda/robotics/robotics_env/adapters/mono_robot_move.py
```

### Usage
```bash
python3 /home/panda/robotics/robotics_env/adapters/mono_robot_move.py <vx> <vy> <duration> [wz]
```

### Arguments positionnels
| Argument | Type | Description | Exemple |
|----------|------|-------------|---------|
| `vx` | float | Vitesse linéaire X (avant/arrière) en m/s | `0.5` |
| `vy` | float | Vitesse linéaire Y (latéral) en m/s | `0.0` |
| `duration` | float | Durée du mouvement en secondes | `2.0` |
| `wz` | float | (optionnel) Vitesse angulaire en rad/s, positif=gauche | `0.3` |

### Exemples
```bash
# Avancer à 0.5 m/s pendant 2 secondes
python3 mono_robot_move.py 0.5 0.0 2.0

# Reculer à 0.3 m/s pendant 1 seconde
python3 mono_robot_move.py -0.3 0.0 1.0

# Avancer en tournant légèrement à gauche
python3 mono_robot_move.py 0.5 0.0 2.0 0.3
```

### Sortie stdout
```
Mouvement terminé. Durée: 2.0s. Commande: vx=0.50, vy=0.00. Deplacement: 0.950m. Position finale: X=0.95, Y=-0.01, Z=0.254.
```

### Codes retour
| Code | Signification |
|------|--------------|
| 0 | Succès — mouvement exécuté, robot arrêté |
| 1 | Erreur — simulation non accessible ou arguments invalides |

### Sécurités intégrées
- Le robot est **toujours stoppé** (Twist zéro) à la fin, même en cas d'erreur
- Durée max : 30 secondes
- Vitesse max : ±1.0 m/s (clamp automatique)
- Vitesse angulaire max : ±1.0 rad/s (clamp automatique)

---

## 5. Script 3 : `mono_robot_turn.py` (Correction de Cap)

### Emplacement
```
/home/panda/robotics/robotics_env/adapters/mono_robot_turn.py
```

### Usage
```bash
python3 /home/panda/robotics/robotics_env/adapters/mono_robot_turn.py --target_yaw_deg <float> [options]
```

### Arguments (named flags uniquement, AUCUN positional)
| Flag | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `--target_yaw_deg` | float | **OUI** | — | Cap cible en degrés (0=face +X, 90=face +Y gauche) |
| `--tol_deg` | float | non | 5.0 | Tolérance en degrés |
| `--wz_max` | float | non | 1.0 | Vitesse angulaire max en rad/s |
| `--kp` | float | non | 2.0 | Gain proportionnel du P-controller |
| `--timeout_s` | float | non | 10.0 | Timeout en secondes |

### Exemples
```bash
# Tourner face au docteur (+X)
python3 mono_robot_turn.py --target_yaw_deg 0

# Tourner face +Y (gauche)
python3 mono_robot_turn.py --target_yaw_deg 90

# Tourner à droite -83° avec tolérance serrée
python3 mono_robot_turn.py --target_yaw_deg -83 --tol_deg 3 --timeout_s 12
```

### Sortie stdout (format structuré)
```
Rotation terminee. yaw_initial_deg=-2.4 yaw_final_deg=-85.4 error_deg=2.4 target_deg=-83.0 verdict=SUCCESS
```

### Codes retour
| Code | Signification |
|------|--------------|
| 0 | SUCCESS — cap atteint (erreur < tol_deg) |
| 2 | TIMEOUT — cap non atteint dans le délai |
| 3 | INVALID ARGS — affiche usage |

### Comportement
- P-controller : wz = Kp * erreur_rad, clampé à ±wz_max
- Shortest path : tourne toujours par le plus court chemin (-180/+180)
- Toutes les valeurs en **degrés** dans l'interface (conversion interne en rad)
- vx=vy=0 pendant la rotation (pas de déplacement)

### Cas d'usage : Approche Docteur
```bash
# Stratégie recommandée : turn-stand-move-stand (répéter)
python3 mono_robot_turn.py --target_yaw_deg 0
python3 mono_robot_stand.py 2
python3 mono_robot_move.py 0.5 0 3
python3 mono_robot_stand.py 2          # exit 10 = ABORT, reset, restart
# Répéter jusqu'à distance < 1m
```

---

## 6. Script 4 : `mono_robot_stand.py` (Pause Stabilisatrice)

### Emplacement
```
/home/panda/robotics/robotics_env/adapters/mono_robot_stand.py
```

### Usage
```bash
python3 /home/panda/robotics/robotics_env/adapters/mono_robot_stand.py [duration]
```

### Arguments
| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `duration` | float | non | 3.0 | Durée de la pause en secondes (max 10) |

### Comportement
- Envoie cmd_vel=(0,0,0) pendant `duration` secondes
- Monitore Z toutes les 0.5s pendant la pause
- Si Z < 0.20 : **CHUTE DÉTECTÉE** → abort immédiat

### Sortie stdout
```
# Robot stable
Stabilisation OK. Duree: 3.0s. Z stable: 0.258. Pret.

# Robot tombé
AUTO_RESET_TRIGGERED X=4.14 Y=1.13 Z=0.057 yaw_deg=101.3
```

### Codes retour
| Code | Signification | Action caller |
|------|--------------|---------------|
| 0 | Stable — Z >= 0.20 pendant toute la pause | Continuer |
| 1 | Erreur connexion simulateur | Abort |
| **10** | **CHUTE DÉTECTÉE (Z < 0.20)** | **ABORT RUN immédiat** |

### RÈGLE CRITIQUE : Exit 10 = ABORT
**Si exit code 10** : le caller (playbook) DOIT :
1. **STOPPER** toutes les étapes suivantes
2. Marquer le run comme **FAIL**
3. Appeler `mono_robot_reset.py` explicitement
4. Recommencer le run depuis le début

Le script NE fait PAS de reset lui-même. Le reset est TOUJOURS explicite via `mono_robot_reset.py`.

### Note : `--auto-reset` (déprécié)
Le flag `--auto-reset` est accepté pour rétro-compatibilité mais **ignoré**. Le comportement est identique avec ou sans ce flag : chute = exit 10, jamais de reset silencieux.

---

## 7. Script 5 : `mono_robot_goto.py` (Navigation Autonome)

### Emplacement
```
/home/panda/robotics/robotics_env/adapters/mono_robot_goto.py
```

### Usage
```bash
python3 /home/panda/robotics/robotics_env/adapters/mono_robot_goto.py --target_x <float> --target_y <float> --dist_stop <float>
```

### Arguments
| Flag | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `--target_x` | float | **OUI** | — | Position cible X (Isaac Sim) |
| `--target_y` | float | **OUI** | — | Position cible Y (Isaac Sim) |
| `--dist_stop` | float | **OUI** | — | Distance d'arrêt (m) |
| `--vx` | float | non | 0.30 | Vitesse d'avance (m/s) |
| `--pulse_s` | float | non | 2.5 | Durée max du pulse d'avance (s) |
| `--stand_s` | float | non | 2.0 | Durée pause stabilisation (s) |
| `--kp` | float | non | 3.0 | Gain P rotation (fort anti-drift) |
| `--wz_max` | float | non | 1.0 | Vitesse angulaire max (rad/s) |
| `--tol_deg` | float | non | 10.0 | Tolérance cap avant avance |
| `--max_cycles` | int | non | 20 | Max cycles (sécurité) |
| `--timeout_s` | float | non | 120.0 | Timeout global (s) |

### Comportement (boucle interne anti-RL-fatigue)
Chaque cycle :
1. **Sense** : lire position + yaw
2. **Check distance** : si <= dist_stop → SUCCESS
3. **Check chute** : si Z < 0.20 → EXIT 10
4. **Turn** : tourner vers la cible (P-controller inline, Kp=3.0)
5. **Pulse** : avancer vx=0.30 pendant 2.5s max (monitoring Z)
6. **Stand** : pause 2.0s (reset fatigue PPO, monitoring Z)

### Sortie stdout
```
[cycle 1] dist=5.02 bearing=-0.1 yaw=-2.4 err=2.3 pulse=2.5s Z=0.266
[cycle 2] dist=4.50 bearing=0.7 yaw=3.0 err=-2.3 pulse=2.5s Z=0.245
...
GOTO SUCCESS. target=(5.00,0.00) final_pos=(4.92,-0.12) dist=0.14 cycles=7 duration=31.5s
METRICS total_time_s=31.5 total_distance_m=4.88 num_cycles=7 num_recalculations=3 final_dist_m=0.14 verdict=SUCCESS
```

### Ligne METRICS (v2.7)
La **dernière ligne** de stdout contient des métriques machine-parseable :
| Champ | Type | Description |
|-------|------|-------------|
| `total_time_s` | float | Durée totale du run (wall clock) |
| `total_distance_m` | float | Distance cumulée parcourue |
| `num_cycles` | int | Nombre de cycles turn/pulse/stand |
| `num_recalculations` | int | Cycles avec heading error > tol_deg |
| `final_dist_m` | float | Distance euclidienne finale à la cible |
| `verdict` | string | SUCCESS / FAIL / ABORT / TIMEOUT |

Parsing shell : `grep METRICS output.txt | tr ' ' '\n' | grep total_time`

### Codes retour
| Code | Signification |
|------|--------------|
| 0 | SUCCESS — distance atteinte |
| 1 | Erreur connexion |
| 2 | TIMEOUT (cycles ou global) |
| 10 | CHUTE (Z < 0.20) — caller doit reset et relancer |

### Exemple UseCase01 (Approche Docteur)
```bash
cd /tmp
python3 .../mono_robot_reset.py
python3 .../mono_robot_goto.py --target_x 5.0 --target_y 0.0 --dist_stop 0.5
# Si exit 10 : reset et relancer
```

### Performance mesurée (rough_model_7850.pt — depuis v2.6)
- ~0.45m/cycle (pulse 2.5s à 0.30 m/s + overhead turn/stand)
- Heading error < 10° grâce au Kp=3.0
- **17+ cycles sans chute** (160s+ continu)
- Distance max testée : **22.8m aller-retour** (ZERO chutes)
- Z stable moyen : 0.380m (vs 0.270m avec ancien flat model)

| Métrique | Ancien (flat_6800) | Actuel (rough_7850) | Delta |
|----------|-------------------|---------------------|-------|
| Cycles avant chute | 7 | 17+ (no fall) | +143% |
| Durée max | ~50s | 160s+ | +220% |
| Distance max | 3.2m | 22.8m | +623% |
| Z stable | 0.270m | 0.380m | +41% |

---

## 8. Script 6 : `mono_robot_look.py` (Perception Caméra)

### Emplacement
```
/home/panda/robotics/robotics_env/adapters/mono_robot_look.py
```

### Usage
```bash
python3 /home/panda/robotics/robotics_env/adapters/mono_robot_look.py [--describe]
```

### Arguments
| Flag | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `--describe` | flag | non | — | Si VLM disponible sur Spark, ajoute description textuelle de la scène |

### Comportement
1. Fetch le dernier frame caméra depuis `http://127.0.0.1:8080/camera/latest.jpg`
2. Sauvegarde dans `/tmp/camera_frame_latest.jpg`
3. Fetch l'état robot depuis `http://127.0.0.1:8080/state`
4. Retourne métadonnées + URL du frame

### Prérequis
- `launch_hospital_scene.py` avec `--enable_cameras` (caméra active)
- `web_viewer.py` en fonctionnement (sert le frame via HTTP)

### Sortie stdout
```
Frame capturee. timestamp=1234.5 robot_pos=(2.31,0.12,0.38) yaw_deg=-5.2 frame_url=http://<SPARK_IP>:8080/camera/latest.jpg resolution=640x480
```

Avec `--describe` (si VLM disponible) :
```
Frame capturee. timestamp=1234.5 robot_pos=(2.31,0.12,0.38) yaw_deg=-5.2 frame_url=http://<SPARK_IP>:8080/camera/latest.jpg resolution=640x480
Description: Hospital room. A person in medical clothing visible at center-left, approximately 3m ahead. Hospital bed visible to the right. Floor clear ahead.
```

### Codes retour
| Code | Signification |
|------|--------------|
| 0 | Succès — frame capturé et métadonnées retournées |
| 1 | Erreur — caméra non active ou simulation non accessible |
| 2 | VLM non disponible (uniquement avec --describe) |

### Endpoint HTTP associé
```
GET http://<SPARK_IP>:8080/camera/latest.jpg
```
- Retourne le dernier frame JPEG capturé par la caméra du Go2
- Content-Type: image/jpeg
- 503 si aucun frame disponible (caméra pas démarrée)
- Résolution : 640x480, JPEG quality 80

### Cas d'usage : Vérification visuelle
```bash
# MonoCLI workflow cognitif
python3 mono_robot_goto.py --target_x 5.0 --target_y 0.0 --dist_stop 0.5
python3 mono_robot_look.py                    # Capturer ce que le robot voit
# MonoCLI envoie frame_url au VLM (Groq) pour description
# Si docteur absent : adapter la stratégie
```

---

## 9. Script 7 : `mono_robot_reset.py` (Reset Robot)

### Emplacement
```
/home/panda/robotics/robotics_env/adapters/mono_robot_reset.py
```

### Usage
```bash
python3 /home/panda/robotics/robotics_env/adapters/mono_robot_reset.py
```

### Comportement
- Envoie signal RESETGO2 via UDP port 9873
- Le robot revient debout à la position d'origine (~0,0,0)
- Timeout 5 secondes

---

## 8. Intégration MonoCLI — Playbook YAML

Voici un exemple de Playbook complet pour l'équipe MonoCLI :

```yaml
name: 'Go2 First Steps'
description: 'Le Jedi lit l etat du robot puis le fait avancer'
version: '1.0'
difficulty: 'basique'
duration_minutes: 2

tasks:
  - name: 'Lire etat robot'
    action: 'shell'
    command: 'python3 /home/panda/robotics/robotics_env/adapters/mono_robot_sense.py'
    timeout: 10
    description: 'Lire position et stabilite du Go2'
    expected_output: 'stable'

  - name: 'Avancer 2 secondes'
    action: 'shell'
    command: 'python3 /home/panda/robotics/robotics_env/adapters/mono_robot_move.py 0.5 0.0 2.0'
    timeout: 15
    description: 'Faire avancer le robot de ~1m'
    expected_output: 'terminé'

  - name: 'Verifier nouvelle position'
    action: 'shell'
    command: 'python3 /home/panda/robotics/robotics_env/adapters/mono_robot_sense.py'
    timeout: 10
    description: 'Confirmer que le robot a bouge'
    expected_output: 'stable'
```

### Intégration via `mono_shell` (outil MonoCLI)
```
mono_shell python3 /home/panda/robotics/robotics_env/adapters/mono_robot_sense.py
mono_shell python3 /home/panda/robotics/robotics_env/adapters/mono_robot_move.py 0.5 0.0 2.0
```

### Intégration via SSH (si MonoCLI tourne sur une autre machine)
```bash
ssh panda@<SPARK_IP> "python3 /home/panda/robotics/robotics_env/adapters/mono_robot_sense.py"
ssh panda@<SPARK_IP> "python3 /home/panda/robotics/robotics_env/adapters/mono_robot_move.py 0.5 0.0 2.0"
```

---

## 10. Limites et Responsabilités

### L'équipe Robotics fournit :
- Les 7 scripts CLI fonctionnels sur le Spark
- La simulation Isaac Lab + bridge ROS2 + caméra en fonctionnement
- L'endpoint HTTP /camera/latest.jpg pour accès aux frames
- Ce document API CONTRACT comme référence unique

### L'équipe Robotics ne fournit PAS :
- L'intégration dans MonoCLI (profils Jedi, skills, playbooks)
- La configuration Groq/Ollama
- La logique de décision du LLM
- L'interprétation des images (VLM) — responsabilité MonoCLI via Groq

### L'équipe MonoCLI est responsable de :
- Créer le profil "Jedi Go2 Robotics" dans `jedi_profiles`
- Ajouter les skills qui appellent ces scripts
- Créer les Playbooks d'orchestration
- Gérer le cluster "Simulation_Memory" pour logger les expériences
- Interpréter les frames caméra via VLM (Groq Llama Vision ou équivalent)
- Distiller les leçons via Scrib et enrichir la KB

---

## 11. Protocole de Communication

Les scripts communiquent avec la simulation via **UDP** et **HTTP** sur localhost.

```
┌─────────────┐    HTTP :8080     ┌──────────────────┐    UDP 9870-9875    ┌──────────────────┐
│ sense/look  │ ──── GET ────────→│  web_viewer.py   │ ◄────────────────── │ launch_isaaclab  │
│ move/turn   │ ──── UDP 9871 ───→│  (permanent)     │                     │ (permanent)      │
│ goto/stand  │                   │                  │                     │                  │
│ (ponctuel)  │                   │ /state (JSON)    │                     │                  │
│             │                   │ /camera/latest   │                     │                  │
└─────────────┘                   └──────────────────┘                     └──────────────────┘
```

### Ports UDP
| Port | Direction | Contenu |
|------|-----------|---------|
| 9870 | Isaac → Viewer | Robot state (304 bytes) |
| 9871 | Scripts → Isaac | cmd_vel (24 bytes) |
| 9872 | Isaac → ROS2 bridge | Robot state (304 bytes) |
| 9873 | Reset → Isaac | Signal RESETGO2 |
| 9874 | Isaac → camera_bridge | JPEG frames (header 4B + data) |
| 9875 | Isaac → web_viewer | JPEG frames (header 4B + data) |

### Endpoints HTTP (web_viewer.py, port 8080)
| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/state` | GET | JSON état robot (position, joints, velocité) |
| `/camera/latest.jpg` | GET | Dernier frame caméra JPEG (640x480) |
| `/assets/*.glb` | GET | Modèles 3D (BestFriend, Doctor, etc.) |

Aucun processus ROS2 n'est requis pour utiliser les scripts CLI.

---

## 12. Limitations connues

| Limitation | Détail | Workaround |
|-----------|--------|------------|
| Heading drift | Le robot dérive en yaw après ~3s de marche | Utiliser `mono_robot_turn.py 0` entre chaque segment |
| Strafe instable | vy != 0 peut faire tomber le robot | Éviter strafe, utiliser turn + move forward |
| ~~Marche longue~~ | ~~Policy RL instable après ~4s à 0.5 m/s~~ | **RÉSOLU v2.6** : rough_model_7850.pt tient 160s+ |
| Commandes en ROBOT FRAME | vx pousse dans la direction du robot, pas en world frame | Corriger le cap avec turn avant chaque move |

## 13. Changelog

| Version | Date | Changement |
|---------|------|-----------|
| 1.0 | 2026-02-27 | API Contract SimAdapter (import Python, async) |
| 2.0 | 2026-02-27 | Pont Cognitif — wrappers CLI pour MonoCLI (zero import, texte stdout) |
| 2.1 | 2026-02-28 | Ajout mono_robot_reset.py, fix cd /tmp, ports UDP |
| 2.2 | 2026-03-02 | Ajout mono_robot_turn.py (correction cap), wz optionnel dans move, section limitations |
| 2.3 | 2026-03-02 | HOTFIX TURN API: interface unifiée deg-based (--target_yaw_deg), named args only, wz_max=1.0, codes retour 0/2/3 |
| 2.4 | 2026-03-02 | HOTFIX STAND: chute=exit 10 (ABORT), plus de reset silencieux, --auto-reset déprécié, section stand.py ajoutée |
| 2.5 | 2026-03-02 | mono_robot_goto.py: navigation autonome anti-RL-fatigue, boucle interne turn/pulse/stand, 6 scripts total |
| 2.6 | 2026-03-03 | UPGRADE LOCOMOTION: rough_model_7850.pt (MLP 512/256/128, obs 235-dim, height scan). 160s+ sans chute, 22.8m A/R. Limitation marche longue RÉSOLUE |
| 2.7 | 2026-03-03 | PERCEPTION: mono_robot_look.py (capture caméra + metadata), METRICS goto.py, HTTP /camera/latest.jpg, port UDP 9875, 7 scripts total |

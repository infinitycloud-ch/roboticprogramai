# Phase B — Perturbation (Docteur Deplace)
## Sprint 16 : Preuve d'Evolution Cognitive

**Date** : 3 Mars 2026
**Perturbation** : Docteur deplace de (5,0,0) a (5,3,0) — +3m sur axe Y
**Le robot ne le sait pas** : goto.py cible toujours (5,0,0)

---

## Deroulement

### Etape 1 : Run aveugle — goto (5,0)
Le robot navigue vers la position attendue du docteur.

| Metrique | Valeur |
|----------|--------|
| total_time_s | 32.0 |
| total_distance_m | 5.30 |
| num_cycles | 7 |
| num_recalculations | 1 |
| final_dist_m | 0.40 |
| verdict | SUCCESS |

**Resultat** : Le robot arrive a (5,0) — mais le docteur n'est PAS la.

### Etape 2a : Perception — mono_robot_look.py
```
Frame capturee. timestamp=44.960 robot_pos=(5.03,0.52,0.416) yaw_deg=5.0
frame_url=http://<SPARK_IP>:8080/camera/latest.jpg resolution=640x480
```
Le frame capture montre la scene depuis la position (5.03, 0.52). Le docteur a (5,3) est potentiellement visible dans le champ (~30 deg a gauche dans le FOV 90 deg).

### Etape 2b : Etat robot — mono_robot_sense.py
```
Le robot est stable (debout). Position X=4.97, Y=0.68, Z=0.415.
Orientation: yaw=6.5 deg. 12 joints actifs sur 12. Simulation t=49.2s.
```

### Etape 2c : Adaptation — goto (5,3)
Le cerveau (MonoCLI) deduit que le docteur est ailleurs et navigue vers (5,3).

| Metrique | Valeur |
|----------|--------|
| total_time_s | 21.3 |
| total_distance_m | 2.51 |
| num_cycles | 4 |
| num_recalculations | 3 |
| final_dist_m | 0.23 |
| verdict | SUCCESS |

---

## Synthese

| Phase | Temps | Distance | Resultat |
|-------|-------|----------|----------|
| Etape 1 (aveugle) | 32.0s | 5.30m | Arrive a (5,0) — docteur absent |
| Perception + raisonnement | ~5.0s | 0m | look + sense + decision |
| Etape 2 (adapte) | 21.3s | 2.51m | Arrive a (5,3) — docteur trouve |
| **TOTAL** | **53.3s** | **7.81m** | **SUCCESS** |

## Comparaison avec Baseline (Phase A)

| Metrique | Phase A (baseline) | Phase B (perturbation) | Delta |
|----------|-------------------|----------------------|-------|
| Temps total | 38.2s (moy) | 53.3s | **+39.5%** |
| Distance | 5.65m (moy) | 7.81m | +38.2% |
| Cycles | 8.0 (moy) | 11 (7+4) | +37.5% |
| Verdict | SUCCESS | SUCCESS | = |

**Le cout de l'ignorance** : +15.1s et +2.16m de trajet inutile parce que le robot est alle a la mauvaise position d'abord.

## Lecon a distiller (Scrib)

> **REGLE COGNITIVE** : La position du docteur est VARIABLE. Ne JAMAIS assumer que le docteur
> est a la derniere position connue. TOUJOURS verifier avec la camera (mono_robot_look.py)
> PENDANT l'approche ou AVANT de confirmer l'arrivee.
>
> **STRATEGIE OPTIMALE** : Utiliser look.py a mi-chemin (50% du trajet) pour verifier
> visuellement que la cible est bien la. Si la cible n'est pas visible, scanner la zone
> avant de continuer.

---

*Phase B complete. Lecon prete pour distillation Scrib → KB MonoCLI.*

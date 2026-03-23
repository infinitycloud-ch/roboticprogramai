# Phase A — Baseline Cognitive
## Sprint 16 : Preuve d'Evolution Cognitive

**Date** : 3 Mars 2026
**Conditions** : rough_model_7850.pt, doctor at (5,0,0), robot start (0,0,0)
**Commande** : `mono_robot_goto.py --target_x 5.0 --target_y 0.0 --dist_stop 0.5`

---

## Resultats Bruts

| Run | total_time_s | total_distance_m | num_cycles | num_recalculations | final_dist_m | verdict |
|-----|-------------|-----------------|-----------|-------------------|-------------|---------|
| 1 | 43.9 | 6.40 | 9 | 5 | 0.23 | SUCCESS |
| 2 | 37.9 | 5.52 | 8 | 5 | 0.08 | SUCCESS |
| 3 | 32.8 | 5.02 | 7 | 2 | 0.46 | SUCCESS |

## Statistiques

| Metrique | Moyenne | Min | Max | Ecart |
|----------|---------|-----|-----|-------|
| Temps total (s) | **38.2** | 32.8 | 43.9 | 11.1 |
| Distance parcourue (m) | **5.65** | 5.02 | 6.40 | 1.38 |
| Cycles | **8.0** | 7 | 9 | 2 |
| Recalculations | **4.0** | 2 | 5 | 3 |
| Distance finale (m) | **0.26** | 0.08 | 0.46 | 0.38 |

## Analyse

- **Success rate** : 3/3 = **100%**
- **Zero chutes** sur 3 runs (rough_model_7850.pt stable)
- **Efficacite trajectoire** : 5.65m parcourus / 5.0m ligne droite = **88%** (12% overhead turn/drift)
- **Variabilite temps** : 32.8s — 43.9s (ecart 29%), principalement lie aux recalculations
- **Run 3 le plus rapide** : 32.8s avec seulement 2 recalculations (vs 5 pour runs 1-2)

## Metriques de reference pour comparaison Phase B/C

| Metrique cle | Valeur reference |
|-------------|------------------|
| **Temps moyen** | **38.2s** |
| **Temps Run 1** | **43.9s** (comparaison Phase C) |
| **Cycles moyen** | **8.0** |
| **Success rate** | **100%** |

---

*Baseline etabli. Pret pour Phase B (perturbation docteur).*

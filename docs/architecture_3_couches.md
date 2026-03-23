# Architecture 3 Couches — RoboticProgramAI

## Vue d'ensemble

```
┌─────────────────────────────────────────────┐
│  COUCHE 1 : CERVEAU                         │
│  Agent Jedi / Monocili                      │
│  Décisions haut niveau + mémoire            │
│  Intentions: move(), get_state()            │
└──────────────────┬──────────────────────────┘
                   │ Twist, RobotState
                   ▼
┌─────────────────────────────────────────────┐
│  COUCHE 2 : INTERFACE CORPS                 │
│  RobotAdapter (ABC)                         │
│  ├── SimAdapter   (Isaac Sim via ROS2)      │
│  └── Go2Adapter   (Robot réel, Phase 2)     │
│  NE calcule PAS la cinématique              │
└──────────────────┬──────────────────────────┘
                   │ /cmd_vel (ROS2 Topic)
                   ▼
┌─────────────────────────────────────────────┐
│  NOEUD LOCOMOTEUR (RL PPO)                  │
│  Politique entraînée via Isaac Lab 2.1      │
│  /cmd_vel → torques 12 DOF                  │
└──────────────────┬──────────────────────────┘
                   │ /joint_commands
                   ▼
┌─────────────────────────────────────────────┐
│  COUCHE 3 : MONDE                           │
│  Isaac Sim 4.5.0 sur DGX Spark              │
│  Go2 URDF (12 DOF) + OmniGraph              │
│  ROS2 Bridge: omni.isaac.ros2_bridge        │
│  FastDDS UDP (Domain ID: 0)                 │
└─────────────────────────────────────────────┘
```

## Fichiers clés

| Fichier | Rôle |
|---------|------|
| robotics_env/adapters/types.py | Dataclasses partagées (Twist, Pose, RobotState, SensorData) |
| robotics_env/adapters/robot_adapter.py | ABC — contrat unique Cerveau↔Corps |
| robotics_env/adapters/sim_adapter.py | Implémentation SimAdapter (DEV, Sprint 1) |
| robotics_env/adapters/go2_adapter.py | Stub Go2Adapter (Phase 2) |

## Principe directeur
L'agent Jedi ne sait pas s'il parle à un robot simulé ou réel.
Il utilise RobotAdapter.move(Twist) — le reste est géré par l'adapter + le noeud locomoteur.

## Future: UnifoLM-VLA-0
Option A (recommandée): VLA comme sous-module du Cerveau.
L'agent Jedi planifie, VLA traduit vision+langage en séquences de Twist.

#!/usr/bin/env python3
"""Hello Robot — Test E2E Sprint 1.

Valide la chaîne complète :
    Agent Jedi → SimAdapter → /cmd_vel → Noeud Locomoteur → Isaac Sim

Séquence :
    1. Créer SimAdapter
    2. connect() — vérifie /clock et /odom
    3. Lire état initial (get_state)
    4. Avancer : move(Twist(linear_x=0.5)) pendant 2s
    5. Stop : move(Twist())
    6. Lire état final (get_state + get_sensors)
    7. Assert : position a changé
    8. Log succès
    9. disconnect()

Prérequis :
    - Isaac Sim 5.1.0 headless lancé (sim/launch_scene.py)
    - isaacsim.ros2.bridge activé (OmniGraph publie /tf /odom /joint_states /clock)
    - Noeud Locomoteur lancé (locomotion_controller)
    - ROS2 Jazzy actif + FastDDS

Usage :
    source /opt/ros/jazzy/setup.bash
    export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
    python3 hello_robot.py
"""

from __future__ import annotations

import asyncio
import math
import sys
import time


# Ajout du parent au path pour les imports relatifs
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from adapters.sim_adapter import SimAdapter
from adapters.types import Twist


# Paramètres du test
MOVE_SPEED = 0.5        # m/s
MOVE_DURATION = 2.0     # secondes
MIN_DISPLACEMENT = 0.1  # mètres — seuil minimum pour valider le mouvement


async def main() -> int:
    print("=" * 60)
    print("  RoboticProgramAI — Hello Robot (Sprint 1 E2E)")
    print("=" * 60)
    print()

    adapter = SimAdapter(node_name="hello_robot")

    # --- Étape 1 : Connexion ---
    print("[1/7] Connexion à Isaac Sim via ROS2...")
    try:
        await adapter.connect()
    except ConnectionError as e:
        print(f"  ERREUR connexion: {e}")
        return 1
    except TimeoutError as e:
        print(f"  ERREUR timeout: {e}")
        return 1
    print("  OK — Isaac Sim détecté (/clock + /odom reçus)")
    print()

    # --- Étape 2 : État initial ---
    print("[2/7] Lecture état initial...")
    initial_state = await adapter.get_state()
    print(f"  Position: x={initial_state.pose.x:.3f}, "
          f"y={initial_state.pose.y:.3f}, "
          f"z={initial_state.pose.z:.3f}")
    print(f"  Yaw:      {math.degrees(initial_state.pose.yaw):.1f}°")
    print(f"  Joints:   {len(initial_state.joint_positions)} DOF")
    print(f"  Mode:     {initial_state.mode.value}")
    print()

    # --- Étape 3 : Avancer ---
    print(f"[3/7] Commande: avancer à {MOVE_SPEED} m/s pendant {MOVE_DURATION}s...")
    await adapter.move(Twist(linear_x=MOVE_SPEED))
    await asyncio.sleep(MOVE_DURATION)
    print("  Commande envoyée")
    print()

    # --- Étape 4 : Stop ---
    print("[4/7] Arrêt (Twist zéro)...")
    await adapter.move(Twist())
    # Petit délai pour laisser le robot s'arrêter
    await asyncio.sleep(0.5)
    print("  Robot arrêté")
    print()

    # --- Étape 5 : État final ---
    print("[5/7] Lecture état final...")
    final_state = await adapter.get_state()
    sensors = await adapter.get_sensors()
    print(f"  Position: x={final_state.pose.x:.3f}, "
          f"y={final_state.pose.y:.3f}, "
          f"z={final_state.pose.z:.3f}")
    print(f"  Yaw:      {math.degrees(final_state.pose.yaw):.1f}°")
    print(f"  IMU ori:  {sensors.imu_orientation}")
    print()

    # --- Étape 6 : Vérification ---
    print("[6/7] Vérification du déplacement...")
    dx = final_state.pose.x - initial_state.pose.x
    dy = final_state.pose.y - initial_state.pose.y
    displacement = math.sqrt(dx * dx + dy * dy)
    print(f"  Déplacement: {displacement:.3f} m "
          f"(dx={dx:.3f}, dy={dy:.3f})")

    success = displacement >= MIN_DISPLACEMENT
    if success:
        print(f"  PASS — déplacement {displacement:.3f}m >= seuil {MIN_DISPLACEMENT}m")
    else:
        print(f"  FAIL — déplacement {displacement:.3f}m < seuil {MIN_DISPLACEMENT}m")
    print()

    # --- Étape 7 : Déconnexion ---
    print("[7/7] Déconnexion...")
    await adapter.disconnect()
    print("  SimAdapter déconnecté")
    print()

    # --- Résultat ---
    print("=" * 60)
    if success:
        print("  HELLO ROBOT REUSSI — Le Go2 a bougé dans Isaac Sim!")
        print("  Sprint 1 validé.")
    else:
        print("  HELLO ROBOT ECHOUE — Le Go2 n'a pas bougé.")
        print("  Vérifiez le Noeud Locomoteur et l'OmniGraph.")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

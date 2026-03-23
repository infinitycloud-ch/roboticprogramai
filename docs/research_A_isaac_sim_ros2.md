# Recherche A : NVIDIA Isaac Sim + ROS2 Humble Bridge

## Recommandations clés
- **Isaac Sim 5.1.0** (support DGX Spark officiel, jan 2026)
- Extension bridge: `isaacsim.ros2.bridge` (v5.x)
- **Go2 asset natif** dans Isaac Sim (A1, Go1, Go2, B2 inclus)
- ROS2 Humble sur Ubuntu 22.04
- DDS: FastDDS shared memory (local), UDP (multi-machine)

## Projet de référence
- **isaac-go2-ros2** (Zhefan-Xu): Isaac Sim 4.5 + Isaac Lab 2.1 + ROS2 Humble
- Topics: /cmd_vel, /odom, /tf, /camera/*, /lidar/point_cloud
- https://github.com/Zhefan-Xu/isaac-go2-ros2

## Architecture réseau
```
Serveur GPU (Spark) → Isaac Sim headless + ROS2 Bridge
       ↕ FastDDS UDP (Domain ID: 0)
Machines ROS2 distantes (Nav2, Agent, Monitoring)
```

## Config multi-machine
- Fichier fastdds.xml avec transport UDPv4
- Ports UDP: 7400, 7410, 9387
- export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

## OmniGraph pattern
- On Playback Tick → Isaac Read Simulation Time → ROS2 Publish TF/Odom/Clock
- ROS2 Subscribe Twist → Controller → Articulation Controller
- Toujours publier /clock, configurer use_sim_time: true

## Sources principales
- https://docs.isaacsim.omniverse.nvidia.com/5.1.0/
- https://github.com/isaac-sim/IsaacSim-ros_workspaces
- https://isaac-sim.github.io/IsaacLab/
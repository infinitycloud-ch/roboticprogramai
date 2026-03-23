# Recherche B : Unitree Go2 EDU - ROS2 SDK & Simulation

## SDK Officiels (github.com/unitreerobotics)
- **unitree_sdk2** v2.0.2 (C++, CycloneDDS)
- **unitree_sdk2_python** (bindings Python)
- **unitree_ros2** (ROS2 Humble, messages DDS natifs)
- **unitree_mujoco** (simulation MuJoCo, Go2 = robot par défaut)

## URDF Go2
- **go2_description** (Apache 2.0): 12 DOF, meshes DAE
- https://github.com/Unitree-Go2-Robot/go2_description

## Go2 EDU vs AIR/PRO
- EDU = seul modèle avec accès développeur complet
- SDK natif + ROS2 natif via Ethernet/CycloneDDS
- Contrôle bas niveau (LowCmd/LowState) des 12 moteurs
- Jetson Orin Nano 8GB (40 TOPS), EDU Plus: Orin NX (100 TOPS)
- Ports: 1 USB3 Type-A, 2 USB3 Type-C, 2 GigE RJ45

## Topics ROS2 clés
| Topic | Type | Direction |
|-------|------|-----------|
| /cmd_vel | geometry_msgs/Twist | Subscribe |
| /joint_states | sensor_msgs/JointState | Publish |
| /odom | nav_msgs/Odometry | Publish |
| /imu/data | sensor_msgs/Imu | Publish |
| /utlidar/cloud | PointCloud2 | Publish |
| /lowcmd | unitree_go/LowCmd | Subscribe |
| /lowstate | unitree_go/LowState | Publish |

## Simulation Isaac Sim
- **go2_omniverse**: Isaac Lab + RL PPO + ROS2 (Isaac Sim 2023.1.1)
- **isaac-go2-ros2**: Isaac Sim 4.5 + Isaac Lab 2.1 (le + récent)

## UnifoLM-VLA-0 (Vision-Language-Action)
- Modèle de fondation open-source par Unitree
- https://github.com/unitreerobotics/unifolm-vla
- https://unigen-x.github.io/unifolm-vla.github.io/
- À terme: interfacer notre agent Jedi avec ce type d'architecture

## Documentation officielle
- https://support.unitree.com/main
- https://github.com/unitreerobotics
- www.unifolm.com
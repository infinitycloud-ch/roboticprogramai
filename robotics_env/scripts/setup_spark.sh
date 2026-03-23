#!/usr/bin/env bash
# Setup script pour serveur DGX Spark
# Installe ROS2 Humble + Isaac Sim 4.5.0 + Isaac Lab 2.1.0
set -euo pipefail

echo "=== RoboticProgramAI - Setup DGX Spark ==="
echo ""

# 1. ROS2 Humble
echo "[1/5] Installation ROS2 Humble..."
sudo apt update
sudo apt install -y ros-humble-desktop
sudo apt install -y ros-humble-rmw-fastrtps-cpp
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
echo "export RMW_IMPLEMENTATION=rmw_fastrtps_cpp" >> ~/.bashrc

# 2. Isaac Sim 4.5.0
echo "[2/5] Installation Isaac Sim 4.5.0..."
echo "TODO: Via Omniverse Launcher ou pip install isaacsim==4.5.0"

# 3. Isaac Lab 2.1.0
echo "[3/5] Installation Isaac Lab 2.1.0..."
pip install isaaclab==2.1.0

# 4. Extension ROS2 bridge
echo "[4/5] Activation isaacsim.ros2.bridge..."
echo "TODO: Activer dans Isaac Sim UI ou via config"

# 5. URDF Go2
echo "[5/5] Clone URDF Go2..."
if [ ! -d "sim/urdf/go2_description/.git" ]; then
    git clone https://github.com/Unitree-Go2-Robot/go2_description.git sim/urdf/go2_description
fi

echo ""
echo "=== Setup terminé ==="
echo "Redémarrer le terminal pour appliquer les changements bash."

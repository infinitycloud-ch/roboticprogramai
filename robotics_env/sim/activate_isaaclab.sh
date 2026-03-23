#!/usr/bin/env bash
# Activate Isaac Sim + Isaac Lab WITHOUT system ROS2
# Isaac Sim's bundled rclpy is used instead (Python 3.11 compatible)
ROBOTICS_HOME="/home/panda/robotics"
source "${ROBOTICS_HOME}/envs/isaac/bin/activate"

# DO NOT source /opt/ros/jazzy/setup.bash — it conflicts with Isaac Sim's rclpy
# Instead, set only the RMW implementation for DDS communication
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# LD_PRELOAD for aarch64
export LD_PRELOAD="/lib/aarch64-linux-gnu/libgomp.so.1:${ROBOTICS_HOME}/envs/isaac/lib/python3.11/site-packages/torch.libs/libgomp-58a43326.so.1.0.0"

# Set Isaac Sim ROS2 bridge path for rclpy and message types
export ISAAC_ROS2_PATH="${ROBOTICS_HOME}/envs/isaac/lib/python3.11/site-packages/isaacsim/exts/isaacsim.ros2.bridge/jazzy/rclpy"
export PYTHONPATH="${ISAAC_ROS2_PATH}:${PYTHONPATH}"

echo "[Isaac Lab] Environment active (no system ROS2)."
echo "[Isaac Lab] Python: $(python --version)"
echo "[Isaac Lab] ROS2: Isaac Sim bundled rclpy"

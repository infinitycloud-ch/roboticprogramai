#!/usr/bin/env python3
"""Noeud ROS2 Locomoteur : /cmd_vel -> positions 12 DOF via politique RL PPO.

Ce noeud :
1. Subscribe /cmd_vel (velocites desirees du SimAdapter)
2. Subscribe /joint_states (positions/velocites courantes 12 DOF)
3. Subscribe /odom (vitesse lineaire/angulaire, orientation base)
4. Execute la politique RL PPO (MLP 48->128->128->128->12, ELU)
5. Publish /joint_commands (positions 12 DOF vers Isaac Sim)

JOINT ORDERING (R7 Risk):
    Policy trained with Isaac Lab (by-leg, depth-first):
        [FL_hip, FL_thigh, FL_calf, FR_hip, FR_thigh, FR_calf,
         RL_hip, RL_thigh, RL_calf, RR_hip, RR_thigh, RR_calf]

    /joint_states from URDF importer (by-type, breadth-first):
        [FL_hip, FR_hip, RL_hip, RR_hip, FL_thigh, FR_thigh,
         RL_thigh, RR_thigh, FL_calf, FR_calf, RL_calf, RR_calf]

    Mapping is built dynamically from joint names.

Architecture observation (48 dim) :
    [0:3]   base_lin_vel    — vitesse lineaire (base frame, depuis odom)
    [3:6]   base_ang_vel    — vitesse angulaire (base frame, depuis odom)
    [6:9]   projected_gravity — gravite projetee (depuis orientation odom)
    [9:12]  cmd_vel         — commande velocite (vx, vy, wz)
    [12:24] joint_pos_rel   — positions articulaires relatives (policy order)
    [24:36] joint_vel       — vitesses articulaires (policy order)
    [36:48] last_action     — derniere action (policy order)

Usage :
    source /opt/ros/jazzy/setup.bash
    export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
    python3 locomotion_controller.py [--policy PATH] [--freq HZ]
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
from typing import Optional

import numpy as np

try:
    import torch
    import torch.nn as nn
except ImportError:
    print("ERREUR: PyTorch requis. pip install torch")
    sys.exit(1)

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
    from geometry_msgs.msg import Twist
    from sensor_msgs.msg import JointState
    from nav_msgs.msg import Odometry
except ImportError:
    print("ERREUR: rclpy requis. source /opt/ros/jazzy/setup.bash")
    sys.exit(1)


# Policy joint order — likely same as URDF import (by-type, breadth-first)
# since the Nucleus USD was also created from the Go2 URDF
POLICY_JOINT_NAMES = [
    "FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint",
    "FL_thigh_joint", "FR_thigh_joint", "RL_thigh_joint", "RR_thigh_joint",
    "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint",
]

# Default joint positions (radians) in by-type order — Go2 standing pose
DEFAULT_JOINT_POS_POLICY = np.array([
    0.1, -0.1, 0.1, -0.1,       # hip joints (FL, FR, RL, RR)
    0.8, 0.8, 1.0, 1.0,          # thigh joints (FL, FR, RL, RR)
    -1.5, -1.5, -1.5, -1.5,      # calf joints (FL, FR, RL, RR)
], dtype=np.float32)

DEFAULT_POLICY_PATH = os.path.join(
    "/home/panda/robotics/isaac_sim/references/isaac-go2-ros2",
    "ckpts/unitree_go2/flat_model_6800.pt",
)
FALLBACK_POLICY_PATH = os.path.join(
    os.path.dirname(__file__), "policies", "flat_model_6800.pt"
)


class ActorMLP(nn.Module):
    """Actor network matching RSL-RL ActorCritic architecture.

    MLP: input(48) -> 128 -> 128 -> 128 -> 12, ELU activation.
    """

    def __init__(self, obs_dim: int = 48, act_dim: int = 12, hidden: list[int] = None):
        super().__init__()
        if hidden is None:
            hidden = [128, 128, 128]

        layers = []
        prev = obs_dim
        for h in hidden:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.ELU())
            prev = h
        layers.append(nn.Linear(prev, act_dim))

        self.actor = nn.Sequential(*layers)

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.actor(obs)


def load_policy(policy_path: str, device: str = "cpu") -> ActorMLP:
    """Load the actor network from a RSL-RL PPO checkpoint."""
    if not os.path.exists(policy_path):
        raise FileNotFoundError(f"Policy checkpoint introuvable: {policy_path}")

    ckpt = torch.load(policy_path, map_location=device, weights_only=False)
    state_dict = ckpt["model_state_dict"]

    # Extract actor weights only
    actor_state = {}
    for key, val in state_dict.items():
        if key.startswith("actor."):
            actor_state[key] = val

    obs_dim = actor_state["actor.0.weight"].shape[1]
    act_dim = actor_state["actor.6.weight"].shape[0]
    hidden_dims = [
        actor_state["actor.0.weight"].shape[0],
        actor_state["actor.2.weight"].shape[0],
        actor_state["actor.4.weight"].shape[0],
    ]

    model = ActorMLP(obs_dim=obs_dim, act_dim=act_dim, hidden=hidden_dims)
    model.load_state_dict(actor_state)
    model.eval()
    model.to(device)
    return model


def build_joint_mapping(ros_names: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Build index mapping between ROS joint order and policy joint order.

    Returns:
        ros_to_policy: indices to reorder from ROS order -> policy order
        policy_to_ros: indices to reorder from policy order -> ROS order
    """
    ros_to_policy = np.zeros(12, dtype=int)
    policy_to_ros = np.zeros(12, dtype=int)

    for policy_idx, name in enumerate(POLICY_JOINT_NAMES):
        ros_idx = ros_names.index(name)
        ros_to_policy[policy_idx] = ros_idx
        policy_to_ros[ros_idx] = policy_idx

    return ros_to_policy, policy_to_ros


def quat_rotate_inverse(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotate vector v by inverse of quaternion q (w, x, y, z format)."""
    w, x, y, z = q[0], q[1], q[2], q[3]
    q_vec = np.array([x, y, z])
    t = 2.0 * np.cross(q_vec, v)
    return v - w * t + np.cross(q_vec, t)


class LocomotionController(Node):
    """Noeud ROS2 : politique RL PPO pour locomotion Go2.

    Boucle de controle a 25 Hz (matches training: decimation=8, sim.dt=0.005).
    Politique pre-entrainee via Isaac Lab (PPO) depuis isaac-go2-ros2.
    """

    CONTROL_FREQ_HZ = 25
    ACTION_SCALE = 0.25

    def __init__(
        self,
        policy_path: str = DEFAULT_POLICY_PATH,
        freq: float = CONTROL_FREQ_HZ,
        device: str = "cpu",
    ):
        super().__init__("locomotion_controller")

        self._device = device
        self._freq = freq
        self._action_scale = self.ACTION_SCALE

        # --- Load policy ---
        path = policy_path
        if not os.path.exists(path):
            path = FALLBACK_POLICY_PATH
        self.get_logger().info(f"Chargement policy: {path}")
        self._policy = load_policy(path, device=device)
        self.get_logger().info(
            f"Policy chargee: obs=48, act=12, hidden=[128,128,128], device={device}"
        )

        # --- State variables (in POLICY order) ---
        self._cmd_vel = np.zeros(3, dtype=np.float32)
        self._joint_pos_policy = np.zeros(12, dtype=np.float32)
        self._joint_vel_policy = np.zeros(12, dtype=np.float32)
        self._base_lin_vel = np.zeros(3, dtype=np.float32)
        self._base_ang_vel = np.zeros(3, dtype=np.float32)
        self._base_quat = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        self._last_action = np.zeros(12, dtype=np.float32)

        # Joint name mapping (built on first /joint_states message)
        self._ros_joint_names: Optional[list[str]] = None
        self._ros_to_policy: Optional[np.ndarray] = None
        self._policy_to_ros: Optional[np.ndarray] = None

        # Lock for thread safety
        self._lock = threading.Lock()
        self._has_joint_data = False
        self._has_odom_data = False
        self._step_count = 0

        # --- QoS ---
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        # --- Subscribers ---
        self._cmd_vel_sub = self.create_subscription(
            Twist, "/cmd_vel", self._on_cmd_vel, qos
        )
        self._joint_sub = self.create_subscription(
            JointState, "/joint_states", self._on_joint_states, qos
        )
        self._odom_sub = self.create_subscription(
            Odometry, "/odom", self._on_odom, qos
        )

        # --- Publisher ---
        self._joint_cmd_pub = self.create_publisher(JointState, "/joint_commands", qos)

        # --- Control timer ---
        period = 1.0 / self._freq
        self._timer = self.create_timer(period, self._control_loop)

        self.get_logger().info(
            f"Noeud Locomoteur demarre @ {self._freq} Hz. "
            f"Sub: /cmd_vel, /joint_states, /odom. Pub: /joint_commands"
        )

    # --- Callbacks ---

    def _on_cmd_vel(self, msg: Twist) -> None:
        with self._lock:
            self._cmd_vel[0] = float(msg.linear.x)
            self._cmd_vel[1] = float(msg.linear.y)
            self._cmd_vel[2] = float(msg.angular.z)

    def _on_joint_states(self, msg: JointState) -> None:
        if len(msg.position) != 12:
            return

        with self._lock:
            # Build mapping on first valid message
            if self._ros_joint_names is None:
                self._ros_joint_names = list(msg.name)
                try:
                    self._ros_to_policy, self._policy_to_ros = build_joint_mapping(
                        self._ros_joint_names
                    )
                    self.get_logger().info(
                        f"Joint mapping built. ROS order: {self._ros_joint_names}"
                    )
                    self.get_logger().info(
                        f"  ros_to_policy: {self._ros_to_policy.tolist()}"
                    )
                except ValueError as e:
                    self.get_logger().error(f"Joint mapping failed: {e}")
                    return

            if self._ros_to_policy is None:
                return

            # Convert from ROS order to policy order
            ros_pos = np.array(msg.position[:12], dtype=np.float32)
            self._joint_pos_policy[:] = ros_pos[self._ros_to_policy]

            if len(msg.velocity) >= 12:
                ros_vel = np.array(msg.velocity[:12], dtype=np.float32)
                self._joint_vel_policy[:] = ros_vel[self._ros_to_policy]

            self._has_joint_data = True

    def _on_odom(self, msg: Odometry) -> None:
        with self._lock:
            # Orientation quaternion (ROS x,y,z,w -> our w,x,y,z)
            q = msg.pose.pose.orientation
            self._base_quat = np.array(
                [q.w, q.x, q.y, q.z], dtype=np.float32
            )

            # ROS Odometry twist is ALREADY in child_frame_id (base_link)
            # No rotation needed — these are already body-frame velocities
            self._base_lin_vel = np.array([
                msg.twist.twist.linear.x,
                msg.twist.twist.linear.y,
                msg.twist.twist.linear.z,
            ], dtype=np.float32)

            self._base_ang_vel = np.array([
                msg.twist.twist.angular.x,
                msg.twist.twist.angular.y,
                msg.twist.twist.angular.z,
            ], dtype=np.float32)

            self._has_odom_data = True

    # --- Control loop ---

    def _control_loop(self) -> None:
        """Boucle de controle a CONTROL_FREQ_HZ."""
        with self._lock:
            if not self._has_joint_data or not self._has_odom_data:
                return
            if self._ros_to_policy is None:
                return

            # --- Build observation vector (48 dim, policy order) ---
            obs = np.zeros(48, dtype=np.float32)

            # [0:3] base linear velocity (base frame)
            obs[0:3] = self._base_lin_vel

            # [3:6] base angular velocity (base frame)
            obs[3:6] = self._base_ang_vel

            # [6:9] projected gravity (gravity in base frame)
            gravity_world = np.array([0.0, 0.0, -1.0], dtype=np.float32)
            obs[6:9] = quat_rotate_inverse(self._base_quat, gravity_world)

            # [9:12] velocity command
            obs[9:12] = self._cmd_vel

            # [12:24] joint positions relative to default (policy order)
            obs[12:24] = self._joint_pos_policy - DEFAULT_JOINT_POS_POLICY

            # [24:36] joint velocities (policy order)
            obs[24:36] = self._joint_vel_policy

            # [36:48] last action (policy order)
            obs[36:48] = self._last_action

            # Copy ROS joint names for publishing
            ros_names = list(self._ros_joint_names)
            policy_to_ros = self._policy_to_ros.copy()

        # --- Run policy inference ---
        with torch.no_grad():
            obs_tensor = torch.from_numpy(obs).unsqueeze(0).to(self._device)
            action = self._policy(obs_tensor).squeeze(0).cpu().numpy()

        # --- Scale and apply (in policy order) ---
        scaled_action = action * self._action_scale
        target_pos_policy = DEFAULT_JOINT_POS_POLICY + scaled_action

        # Save raw action for next observation
        with self._lock:
            self._last_action[:] = action

        # --- Convert back to ROS order for publishing ---
        target_pos_ros = target_pos_policy[policy_to_ros]

        # --- Publish /joint_commands ---
        cmd_msg = JointState()
        cmd_msg.header.stamp = self.get_clock().now().to_msg()
        cmd_msg.name = ros_names
        cmd_msg.position = target_pos_ros.tolist()
        self._joint_cmd_pub.publish(cmd_msg)

        self._step_count += 1
        if self._step_count <= 5 or self._step_count % 25 == 0 and self._step_count <= 200:
            self.get_logger().info(
                f"Step {self._step_count}: "
                f"lin_vel=[{obs[0]:.3f},{obs[1]:.3f},{obs[2]:.3f}] "
                f"ang_vel=[{obs[3]:.3f},{obs[4]:.3f},{obs[5]:.3f}] "
                f"grav=[{obs[6]:.3f},{obs[7]:.3f},{obs[8]:.3f}] "
                f"cmd=[{obs[9]:.3f},{obs[10]:.3f},{obs[11]:.3f}]"
            )
            self.get_logger().info(
                f"  jpos_rel=[{','.join(f'{v:.2f}' for v in obs[12:24])}]"
            )
            self.get_logger().info(
                f"  action=[{','.join(f'{v:.2f}' for v in action)}] "
                f"target=[{','.join(f'{v:.2f}' for v in target_pos_policy)}]"
            )


def parse_args():
    parser = argparse.ArgumentParser(description="Go2 RL Locomotion Controller")
    parser.add_argument(
        "--policy",
        default=DEFAULT_POLICY_PATH,
        help="Chemin vers le checkpoint .pt",
    )
    parser.add_argument(
        "--freq",
        type=float,
        default=LocomotionController.CONTROL_FREQ_HZ,
        help=f"Frequence de controle en Hz (defaut: {LocomotionController.CONTROL_FREQ_HZ})",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Device PyTorch: cpu ou cuda (defaut: cpu)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60, flush=True)
    print("  RoboticProgramAI -- Noeud Locomoteur RL", flush=True)
    print("=" * 60, flush=True)
    print(f"  Policy:  {args.policy}", flush=True)
    print(f"  Freq:    {args.freq} Hz", flush=True)
    print(f"  Device:  {args.device}", flush=True)
    print(f"  Scale:   {LocomotionController.ACTION_SCALE}", flush=True)
    print("=" * 60, flush=True)

    rclpy.init()

    node = LocomotionController(
        policy_path=args.policy,
        freq=args.freq,
        device=args.device,
    )

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\nArret demande.", flush=True)
    finally:
        node.destroy_node()
        rclpy.shutdown()
        print("Noeud Locomoteur arrete.", flush=True)


if __name__ == "__main__":
    main()

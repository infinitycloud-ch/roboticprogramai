#!/usr/bin/env python3
"""Dump Isaac Lab observations to compare with our custom obs construction.

Runs the policy through Isaac Lab's environment AND computes obs manually,
then compares them.

Usage:
    source /home/panda/robotics/isaac_sim/activate.sh
    cd /home/panda/robotics/isaac_sim/references/isaac-go2-ros2
    python3 -u /home/panda/robotics/robotics_env/sim/test_isaaclab_obs_dump.py --headless --steps 50
"""
from __future__ import annotations
import os, sys, argparse
import numpy as np

os.environ["PYTHONUNBUFFERED"] = "1"

from isaaclab.app import AppLauncher
parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
parser.add_argument("--steps", type=int, default=50)
args = parser.parse_args()
app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

import torch
import torch.nn as nn
import gymnasium as gym

sys.path.insert(0, "/home/panda/robotics/isaac_sim/references/isaac-go2-ros2")
from go2.go2_env import Go2RSLEnvCfg
from go2.go2_ctrl import init_base_vel_cmd

def log(msg):
    print(msg, flush=True)

JOINT_NAMES_POLICY_ORDER = [
    "FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint",
    "FL_thigh_joint", "FR_thigh_joint", "RL_thigh_joint", "RR_thigh_joint",
    "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint",
]

DEFAULT_JOINT_POS = np.array([
    0.1, -0.1, 0.1, -0.1,
    0.8, 0.8, 1.0, 1.0,
    -1.5, -1.5, -1.5, -1.5,
], dtype=np.float32)


def quat_rotate_inverse(q, v):
    """q is (w,x,y,z)"""
    w, x, y, z = q[0], q[1], q[2], q[3]
    q_vec = np.array([x, y, z])
    t = 2.0 * np.cross(q_vec, v)
    return v - w * t + np.cross(q_vec, t)


def main():
    log("=" * 60)
    log("  Observation Comparison: Isaac Lab vs Custom")
    log("=" * 60)

    cfg = Go2RSLEnvCfg()
    cfg.scene.num_envs = 1
    cfg.sim.device = "cpu"
    init_base_vel_cmd(1)
    cfg.observations.policy.height_scan = None
    env = gym.make("Isaac-Velocity-Flat-Unitree-Go2-v0", cfg=cfg)
    log("Environment created")

    # Load policy
    class ActorMLP(nn.Module):
        def __init__(self, obs_dim=48, act_dim=12, hidden=None):
            super().__init__()
            if hidden is None: hidden = [128, 128, 128]
            layers = []
            prev = obs_dim
            for h in hidden:
                layers.append(nn.Linear(prev, h))
                layers.append(nn.ELU())
                prev = h
            layers.append(nn.Linear(prev, act_dim))
            self.actor = nn.Sequential(*layers)
        def forward(self, obs):
            return self.actor(obs)

    policy_path = "/home/panda/robotics/isaac_sim/references/isaac-go2-ros2/ckpts/unitree_go2/flat_model_6800.pt"
    ckpt = torch.load(policy_path, map_location="cpu", weights_only=False)
    actor_state = {k: v for k, v in ckpt["model_state_dict"].items() if k.startswith("actor.")}
    policy = ActorMLP()
    policy.load_state_dict(actor_state)
    policy.eval()
    log("Policy loaded")

    obs_dict, _ = env.reset()
    obs = obs_dict["policy"] if isinstance(obs_dict, dict) else obs_dict
    log(f"Obs shape: {obs.shape}")

    # Get robot reference
    robot_data = env.unwrapped.scene["unitree_go2"].data

    # Get joint names from Isaac Lab
    lab_joint_names = env.unwrapped.scene["unitree_go2"].joint_names
    log(f"Isaac Lab joint names: {lab_joint_names}")

    # Get default joint positions from Isaac Lab
    lab_default_pos = env.unwrapped.scene["unitree_go2"].data.default_joint_pos[0].cpu().numpy()
    log(f"Isaac Lab default_joint_pos: {lab_default_pos}")
    log(f"Our DEFAULT_JOINT_POS:       {DEFAULT_JOINT_POS}")

    last_action_torch = torch.zeros(1, 12)

    log(f"\n{'Step':>4} {'obs_match':>10} {'max_diff':>10} {'action_max':>10} {'pos_z':>8}")
    log(f"{'':>4} {'lin_vel_diff':>12} {'ang_vel_diff':>12} {'grav_diff':>12} {'jpos_diff':>12} {'jvel_diff':>12}")

    for step in range(args.steps):
        # Get Isaac Lab obs
        lab_obs = obs[0].cpu().numpy() if isinstance(obs, torch.Tensor) else obs[0]

        # Manually compute obs from robot data
        root_state = robot_data.root_state_w[0].cpu().numpy()
        root_pos = root_state[:3]
        root_quat = root_state[3:7]  # w,x,y,z
        root_lin_vel = root_state[7:10]
        root_ang_vel = root_state[10:13]

        # Body-frame velocities
        lin_vel_b = robot_data.root_lin_vel_b[0].cpu().numpy()
        ang_vel_b = robot_data.root_ang_vel_b[0].cpu().numpy()
        grav_b = robot_data.projected_gravity_b[0].cpu().numpy()

        # Manual computation
        manual_lin_vel = quat_rotate_inverse(root_quat, root_lin_vel)
        manual_ang_vel = quat_rotate_inverse(root_quat, root_ang_vel)
        manual_grav = quat_rotate_inverse(root_quat, np.array([0, 0, -1], dtype=np.float32))

        joint_pos = robot_data.joint_pos[0].cpu().numpy()
        joint_vel = robot_data.joint_vel[0].cpu().numpy()
        default_pos = robot_data.default_joint_pos[0].cpu().numpy()

        # Build manual obs (48 dim)
        manual_obs = np.zeros(48, dtype=np.float32)
        manual_obs[0:3] = manual_lin_vel
        manual_obs[3:6] = manual_ang_vel
        manual_obs[6:9] = manual_grav
        manual_obs[9:12] = 0.0  # cmd_vel
        manual_obs[12:24] = joint_pos - default_pos
        manual_obs[24:36] = joint_vel
        manual_obs[36:48] = last_action_torch[0].cpu().numpy()

        # Compare
        diff = np.abs(lab_obs - manual_obs)
        max_diff = diff.max()
        match = max_diff < 0.1

        lin_vel_diff = np.abs(lab_obs[0:3] - manual_obs[0:3]).max()
        ang_vel_diff = np.abs(lab_obs[3:6] - manual_obs[3:6]).max()
        grav_diff = np.abs(lab_obs[6:9] - manual_obs[6:9]).max()
        jpos_diff = np.abs(lab_obs[12:24] - manual_obs[12:24]).max()
        jvel_diff = np.abs(lab_obs[24:36] - manual_obs[24:36]).max()

        if step < 10 or step % 10 == 0:
            log(f"{step:4d} {'OK' if match else 'MISMATCH':>10} {max_diff:10.6f} {np.abs(lab_obs[36:48]).max():10.4f} {root_pos[2]:8.4f}")
            log(f"{'':>4} lv={lin_vel_diff:10.6f} av={ang_vel_diff:10.6f} gr={grav_diff:10.6f} jp={jpos_diff:10.6f} jv={jvel_diff:10.6f}")
            if not match:
                log(f"  Lab obs[0:12]: {lab_obs[0:12]}")
                log(f"  Man obs[0:12]: {manual_obs[0:12]}")
                log(f"  Lab obs[12:24]: {lab_obs[12:24]}")
                log(f"  Man obs[12:24]: {manual_obs[12:24]}")
                log(f"  Diff > 0.01: indices={np.where(diff > 0.01)[0].tolist()}")

        # Step
        with torch.inference_mode():
            actions = policy(obs)
            last_action_torch = actions.clone()
            obs_dict, _, _, _, _ = env.step(actions)
            obs = obs_dict["policy"] if isinstance(obs_dict, dict) else obs_dict

    log("\nDone.")
    env.close()
    simulation_app.close()

if __name__ == "__main__":
    main()

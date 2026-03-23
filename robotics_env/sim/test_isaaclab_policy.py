#!/usr/bin/env python3
"""Test policy via Isaac Lab environment — exact same setup as training.

This bypasses ALL our custom code and uses Isaac Lab's built-in environment
and observation computation. If this works, the policy is good and our
custom code needs fixing. If this fails, the checkpoint is bad.

Usage:
    source /home/panda/robotics/isaac_sim/activate.sh
    cd /home/panda/robotics/isaac_sim/references/isaac-go2-ros2
    python3 -u /home/panda/robotics/robotics_env/sim/test_isaaclab_policy.py --headless
"""
from __future__ import annotations
import os, sys, argparse

os.environ["PYTHONUNBUFFERED"] = "1"

# Must parse args before importing Isaac Lab
from isaaclab.app import AppLauncher
parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
parser.add_argument("--steps", type=int, default=300)
args = parser.parse_args()
app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

# Now safe to import
import torch
import gymnasium as gym

# Add reference repo to path for Go2 configs
sys.path.insert(0, "/home/panda/robotics/isaac_sim/references/isaac-go2-ros2")
from go2.go2_env import Go2RSLEnvCfg
from go2.go2_ctrl import get_rsl_flat_policy, init_base_vel_cmd

def log(msg):
    print(msg, flush=True)

def main():
    log("=" * 60)
    log("  Test Isaac Lab Policy (gold standard)")
    log("=" * 60)

    # Create environment with reference repo config
    cfg = Go2RSLEnvCfg()
    cfg.scene.num_envs = 1
    cfg.sim.device = "cpu"
    init_base_vel_cmd(1)

    log("Creating Isaac Lab environment...")
    # Don't use rsl_rl runner (version mismatch). Create env manually.
    import gymnasium as gym_lib

    cfg.observations.policy.height_scan = None  # Remove height scan for flat
    env = gym_lib.make("Isaac-Velocity-Flat-Unitree-Go2-v0", cfg=cfg)
    log("Environment created!")

    # Load policy manually (our ActorMLP that we know works)
    import torch.nn as nn
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
    log(f"Policy loaded from {policy_path}")

    # Reset
    obs_dict, _ = env.reset()
    # Isaac Lab returns obs as dict {"policy": tensor}
    if isinstance(obs_dict, dict):
        obs = obs_dict["policy"]
    else:
        obs = obs_dict
    log(f"Observation shape: {obs.shape}")
    log(f"Obs sample (first 12): {obs[0, :12].tolist()}")

    # Run
    log(f"\nRunning {args.steps} steps...")
    for step in range(args.steps):
        with torch.inference_mode():
            actions = policy(obs)
            obs_dict, _, _, _, _ = env.step(actions)
            if isinstance(obs_dict, dict):
                obs = obs_dict["policy"]
            else:
                obs = obs_dict

        if step < 10 or step % 25 == 0:
            # Get robot state
            root_state = env.unwrapped.scene["unitree_go2"].data.root_state_w[0]
            pos = root_state[:3].cpu().numpy()
            quat = root_state[3:7].cpu().numpy()  # w,x,y,z
            grav = env.unwrapped.scene["unitree_go2"].data.projected_gravity_b[0].cpu().numpy()
            act_max = actions.abs().max().item()
            log(f"Step {step:4d}: pos_z={pos[2]:.3f} w={quat[0]:.4f} x={quat[1]:.4f} y={quat[2]:.4f} gz={grav[2]:.4f} amax={act_max:.3f}")

            # Check if fallen
            if abs(grav[2]) < 0.5:
                log(f"  ROBOT FELL at step {step}!")
                break

    log("\nTest complete.")
    env.close()
    simulation_app.close()

if __name__ == "__main__":
    main()

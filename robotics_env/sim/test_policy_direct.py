#!/usr/bin/env python3
"""Test direct: policy RL dans Isaac Sim SANS ROS2.

Isole le probleme: est-ce la policy+obs qui est fausse, ou le pipeline ROS2?

1. Charge Go2 URDF (meme config que launch_scene.py)
2. Charge la policy flat_model_6800.pt
3. Lit l'etat directement via Articulation API
4. Applique les actions directement (pas de ROS2)
5. Log stabilite

Usage:
    source /home/panda/robotics/isaac_sim/activate.sh
    python3 -u test_policy_direct.py
"""
from __future__ import annotations

import argparse
import math
import os
import sys

os.environ["PYTHONUNBUFFERED"] = "1"

DEFAULT_URDF = "/home/panda/robotics/sim/urdf/go2_description/urdf/go2_description.urdf"
DEFAULT_POLICY = "/home/panda/robotics/isaac_sim/references/isaac-go2-ros2/ckpts/unitree_go2/flat_model_6800.pt"

JOINT_NAMES_POLICY_ORDER = [
    "FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint",
    "FL_thigh_joint", "FR_thigh_joint", "RL_thigh_joint", "RR_thigh_joint",
    "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint",
]

import numpy as np

DEFAULT_JOINT_POS = np.array([
    0.1, -0.1, 0.1, -0.1,
    0.8, 0.8, 1.0, 1.0,
    -1.5, -1.5, -1.5, -1.5,
], dtype=np.float32)

ACTION_SCALE = 0.25
DECIMATION = 4  # Try Isaac Lab built-in decimation (50Hz control at dt=0.005)
PHYSICS_DT = 1.0 / 200.0


def log(msg):
    print(msg, flush=True)


def quat_rotate_inverse(q, v):
    """Rotate vector v by inverse of quaternion q (w,x,y,z)."""
    w, x, y, z = q[0], q[1], q[2], q[3]
    q_vec = np.array([x, y, z])
    t = 2.0 * np.cross(q_vec, v)
    return v - w * t + np.cross(q_vec, t)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--urdf", default=DEFAULT_URDF)
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--decimation", type=int, default=DECIMATION)
    parser.add_argument("--steps", type=int, default=500, help="Number of control steps")
    args = parser.parse_args()

    log("=" * 60)
    log("  Test Direct Policy dans Isaac Sim (sans ROS2)")
    log(f"  Decimation: {args.decimation} (control freq: {1.0/(args.decimation*PHYSICS_DT):.0f} Hz)")
    log("=" * 60)

    # --- Isaac Sim init ---
    from isaacsim import SimulationApp
    simulation_app = SimulationApp({"headless": True, "anti_aliasing": 0})

    import omni.usd
    from pxr import Gf, UsdGeom, UsdPhysics
    from omni.isaac.core import World
    from omni.isaac.core.utils.extensions import enable_extension
    from omni.isaac.core.articulations import Articulation
    import omni.timeline

    # --- Load PyTorch ---
    import torch
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

    # Load policy
    ckpt = torch.load(args.policy, map_location="cpu", weights_only=False)
    actor_state = {k: v for k, v in ckpt["model_state_dict"].items() if k.startswith("actor.")}
    policy = ActorMLP()
    policy.load_state_dict(actor_state)
    policy.eval()
    log(f"Policy loaded: {args.policy}")

    # --- Create world ---
    world = World(physics_dt=PHYSICS_DT, rendering_dt=PHYSICS_DT * args.decimation, stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()

    # --- Load URDF ---
    enable_extension("isaacsim.asset.importer.urdf")
    from isaacsim.asset.importer.urdf import _urdf
    urdf_interface = _urdf.acquire_urdf_interface()

    import_config = _urdf.ImportConfig()
    import_config.merge_fixed_joints = False
    import_config.fix_base = False
    import_config.make_default_prim = True
    import_config.self_collision = False
    import_config.create_physics_scene = True
    import_config.import_inertia_tensor = True
    import_config.default_drive_type = _urdf.UrdfJointTargetType.JOINT_DRIVE_POSITION
    import_config.default_drive_strength = 25.0
    import_config.default_position_drive_damping = 0.5

    urdf_dir = os.path.dirname(os.path.abspath(args.urdf))
    urdf_file = os.path.basename(args.urdf)
    parsed_robot = urdf_interface.parse_urdf(urdf_dir, urdf_file, import_config)
    prim_path = urdf_interface.import_robot(urdf_dir, urdf_file, parsed_robot, import_config, "", True)

    # Articulation root
    stage = omni.usd.get_context().get_stage()
    articulation_root_path = None
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            articulation_root_path = str(prim.GetPath())
            break
    if articulation_root_path is None:
        articulation_root_path = prim_path
        UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath(prim_path))

    # Set height
    go2_prim = stage.GetPrimAtPath(prim_path)
    xformable = UsdGeom.Xformable(go2_prim)
    xformable.ClearXformOpOrder()
    xformable.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 0.4))

    log(f"Go2 loaded at {articulation_root_path}")

    # --- Create articulation ---
    robot = Articulation(prim_path=articulation_root_path, name="go2")
    world.scene.add(robot)
    world.reset()

    # --- Build joint mapping ---
    dof_names = robot.dof_names
    log(f"DOF names: {dof_names}")

    # Map from DOF index to policy index
    dof_to_policy = np.zeros(12, dtype=int)
    policy_to_dof = np.zeros(12, dtype=int)
    for p_idx, name in enumerate(JOINT_NAMES_POLICY_ORDER):
        d_idx = dof_names.index(name)
        dof_to_policy[d_idx] = p_idx
        policy_to_dof[p_idx] = d_idx
    log(f"dof_to_policy: {dof_to_policy.tolist()}")

    # --- Set initial positions ---
    init_pos_dof = np.zeros(len(dof_names), dtype=np.float32)
    for p_idx, name in enumerate(JOINT_NAMES_POLICY_ORDER):
        d_idx = dof_names.index(name)
        init_pos_dof[d_idx] = DEFAULT_JOINT_POS[p_idx]

    robot.set_joint_positions(init_pos_dof)
    robot.set_joint_velocities(np.zeros_like(init_pos_dof))

    # Play timeline
    timeline = omni.timeline.get_timeline_interface()
    timeline.play()

    # Warm-up
    log("Warm-up: 500 steps...")
    for _ in range(500):
        world.step(render=True)
    robot.set_joint_positions(init_pos_dof)
    robot.set_joint_velocities(np.zeros_like(init_pos_dof))
    for _ in range(200):
        world.step(render=True)
    log("Warm-up done. Robot standing.")

    # --- Control loop ---
    last_action = np.zeros(12, dtype=np.float32)
    cmd_vel = np.zeros(3, dtype=np.float32)  # No velocity command

    log(f"\nRunning {args.steps} control steps (decimation={args.decimation})...")
    log(f"{'Step':>5} {'ori_x':>8} {'ori_y':>8} {'ori_z':>8} {'ori_w':>8} {'pos_z':>8} {'grav_z':>8} {'act_max':>8}")

    for step in range(args.steps):
        # --- Read state directly from Articulation API ---
        joint_pos_dof = robot.get_joint_positions()
        joint_vel_dof = robot.get_joint_velocities()

        # Get root state (position, orientation, velocities)
        pos, quat_raw = robot.get_world_pose()
        lin_vel = robot.get_linear_velocity()
        ang_vel = robot.get_angular_velocity()

        # get_world_pose() returns quaternion in (w,x,y,z) format — use directly
        quat_wxyz = quat_raw.astype(np.float32)

        # Velocities are in WORLD frame from Isaac Sim — need to rotate to body frame
        lin_vel_body = quat_rotate_inverse(quat_wxyz, lin_vel.astype(np.float32))
        ang_vel_body = quat_rotate_inverse(quat_wxyz, ang_vel.astype(np.float32))

        # Reorder joints from DOF order to policy order
        joint_pos_policy = joint_pos_dof[policy_to_dof].astype(np.float32)
        joint_vel_policy = joint_vel_dof[policy_to_dof].astype(np.float32)

        # --- Build observation (48 dim) ---
        obs = np.zeros(48, dtype=np.float32)
        obs[0:3] = lin_vel_body
        obs[3:6] = ang_vel_body
        obs[6:9] = quat_rotate_inverse(quat_wxyz, np.array([0, 0, -1], dtype=np.float32))
        obs[9:12] = cmd_vel
        obs[12:24] = joint_pos_policy - DEFAULT_JOINT_POS
        obs[24:36] = joint_vel_policy
        obs[36:48] = last_action

        # --- Policy inference ---
        with torch.no_grad():
            obs_t = torch.from_numpy(obs).unsqueeze(0)
            action = policy(obs_t).squeeze(0).numpy()

        # Clip actions to [-1, 1] (standard RL action space)
        action_clipped = np.clip(action, -1.0, 1.0)
        last_action = action_clipped.copy()

        # --- Apply action ---
        scaled_action = action_clipped * ACTION_SCALE
        target_pos_policy = DEFAULT_JOINT_POS + scaled_action

        # Convert to DOF order
        target_pos_dof = np.zeros(len(dof_names), dtype=np.float32)
        for p_idx in range(12):
            d_idx = policy_to_dof[p_idx]
            target_pos_dof[d_idx] = target_pos_policy[p_idx]

        # Apply joint position targets via ArticulationAction (same as Isaac Lab)
        from omni.isaac.core.utils.types import ArticulationAction
        action_obj = ArticulationAction(joint_positions=target_pos_dof)
        robot.apply_action(action_obj)

        # --- Step physics (decimation steps) ---
        for _ in range(args.decimation):
            world.step(render=True)

        # --- Log ---
        grav = quat_rotate_inverse(quat_wxyz, np.array([0, 0, -1], dtype=np.float32))
        if step < 10 or step % 25 == 0:
            log(f"{step:5d} w={quat_wxyz[0]:7.4f} x={quat_wxyz[1]:7.4f} y={quat_wxyz[2]:7.4f} z={quat_wxyz[3]:7.4f} pz={pos[2]:6.3f} gz={grav[2]:7.4f} amax={np.abs(action).max():6.3f}")

        # Check if robot fell
        if abs(grav[2]) < 0.5:
            log(f"  ROBOT FELL at step {step}! grav_z={grav[2]:.3f}")
            break

    log("\nTest complete.")
    simulation_app.close()


if __name__ == "__main__":
    main()

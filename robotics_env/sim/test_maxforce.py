#!/usr/bin/env python3
"""Test with DriveAPI maxForce limit — simplest fix for effort limiting.

Instead of implementing explicit DCMotor torque control, we keep the
DriveAPI's implicit PD controller (stiffness=25, damping=0.5) but add
a maxForce=23.5 to limit the drive output, matching Isaac Lab's
DCMotor effort_limit.

Also tests with decimation=8 (matching training config).

Usage:
    source /home/panda/robotics/isaac_sim/activate.sh
    python3 -u test_maxforce.py --steps 300
"""
from __future__ import annotations

import argparse
import os
import sys

os.environ["PYTHONUNBUFFERED"] = "1"

DEFAULT_POLICY = "/home/panda/robotics/isaac_sim/references/isaac-go2-ros2/ckpts/unitree_go2/flat_model_6800.pt"
NUCLEUS_GO2_USD = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2/Isaac/IsaacLab/Robots/Unitree/Go2/go2.usd"

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
PHYSICS_DT = 1.0 / 200.0
KP = 25.0
KD = 0.5
MAX_FORCE = 23.5  # DCMotor effort_limit


def log(msg):
    print(msg, flush=True)


def quat_rotate_inverse(q, v):
    w, x, y, z = q[0], q[1], q[2], q[3]
    q_vec = np.array([x, y, z])
    t = 2.0 * np.cross(q_vec, v)
    return v - w * t + np.cross(q_vec, t)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--decimation", type=int, default=4)
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--usd", default=NUCLEUS_GO2_USD)
    parser.add_argument("--max-force", type=float, default=MAX_FORCE)
    args = parser.parse_args()

    log("=" * 60)
    log("  Test DriveAPI with maxForce limit")
    log(f"  USD: {args.usd}")
    log(f"  Decimation: {args.decimation} ({1.0/(args.decimation*PHYSICS_DT):.0f} Hz)")
    log(f"  PD: kp={KP}, kd={KD}, maxForce={args.max_force}")
    log("=" * 60)

    from isaacsim import SimulationApp
    simulation_app = SimulationApp({"headless": True, "anti_aliasing": 0})

    import omni.usd
    from pxr import Gf, UsdGeom, UsdPhysics, PhysxSchema
    from omni.isaac.core import World
    from omni.isaac.core.articulations import Articulation
    from omni.isaac.core.utils.stage import add_reference_to_stage
    import omni.timeline

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

    ckpt = torch.load(args.policy, map_location="cpu", weights_only=False)
    actor_state = {k: v for k, v in ckpt["model_state_dict"].items() if k.startswith("actor.")}
    policy = ActorMLP()
    policy.load_state_dict(actor_state)
    policy.eval()
    log("Policy loaded")

    # Create world
    world = World(physics_dt=PHYSICS_DT, rendering_dt=PHYSICS_DT * args.decimation, stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()

    # Load Go2 from Nucleus USD
    robot_prim_path = "/World/Go2"
    log(f"Loading Go2 USD from: {args.usd}")
    add_reference_to_stage(usd_path=args.usd, prim_path=robot_prim_path)
    log("Go2 USD loaded")

    # Set initial position
    stage = omni.usd.get_context().get_stage()
    go2_prim = stage.GetPrimAtPath(robot_prim_path)
    if go2_prim.IsValid():
        xformable = UsdGeom.Xformable(go2_prim)
        xformable.ClearXformOpOrder()
        xformable.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 0.4))

    # Find articulation root
    articulation_root_path = None
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            articulation_root_path = str(prim.GetPath())
            log(f"ArticulationRootAPI found: {articulation_root_path}")
            break
    if articulation_root_path is None:
        articulation_root_path = robot_prim_path
        UsdPhysics.ArticulationRootAPI.Apply(go2_prim)

    # Configure drives: stiffness=25, damping=0.5, maxForce=23.5
    drive_count = 0
    for prim in stage.Traverse():
        if prim.GetName() in JOINT_NAMES_POLICY_ORDER:
            drive = UsdPhysics.DriveAPI.Get(prim, "angular")
            if drive:
                drive.GetStiffnessAttr().Set(KP)
                drive.GetDampingAttr().Set(KD)
                drive.GetMaxForceAttr().Set(args.max_force)
                drive_count += 1
                log(f"  Drive {prim.GetName()}: kp={KP}, kd={KD}, maxForce={args.max_force}")
    log(f"Configured {drive_count} drives")

    # Also set articulation solver settings to match Isaac Lab
    art_prim = stage.GetPrimAtPath(articulation_root_path)
    if art_prim.IsValid():
        # Apply PhysxArticulationAPI if not already applied
        if not art_prim.HasAPI(PhysxSchema.PhysxArticulationAPI):
            PhysxSchema.PhysxArticulationAPI.Apply(art_prim)
        physx_art = PhysxSchema.PhysxArticulationAPI(art_prim)
        physx_art.GetSolverPositionIterationCountAttr().Set(4)
        physx_art.GetSolverVelocityIterationCountAttr().Set(0)
        log(f"Solver iterations: pos=4, vel=0")

    # Set rigid body properties to match Isaac Lab
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            if prim.HasAPI(PhysxSchema.PhysxRigidBodyAPI):
                physx_rb = PhysxSchema.PhysxRigidBodyAPI(prim)
                physx_rb.GetLinearDampingAttr().Set(0.0)
                physx_rb.GetAngularDampingAttr().Set(0.0)
                physx_rb.GetMaxLinearVelocityAttr().Set(1000.0)
                physx_rb.GetMaxAngularVelocityAttr().Set(1000.0)
                physx_rb.GetMaxDepenetrationVelocityAttr().Set(1.0)

    # Create articulation
    robot = Articulation(prim_path=articulation_root_path, name="go2")
    world.scene.add(robot)
    world.reset()

    dof_names = robot.dof_names
    log(f"DOF names ({len(dof_names)}): {dof_names}")

    # Build joint mapping
    policy_to_dof = np.zeros(12, dtype=int)
    for p_idx, name in enumerate(JOINT_NAMES_POLICY_ORDER):
        if name in dof_names:
            d_idx = dof_names.index(name)
            policy_to_dof[p_idx] = d_idx

    # Set initial positions
    init_pos_dof = np.zeros(len(dof_names), dtype=np.float32)
    for p_idx, name in enumerate(JOINT_NAMES_POLICY_ORDER):
        if name in dof_names:
            d_idx = dof_names.index(name)
            init_pos_dof[d_idx] = DEFAULT_JOINT_POS[p_idx]

    robot.set_joint_positions(init_pos_dof)
    robot.set_joint_velocities(np.zeros_like(init_pos_dof))

    timeline = omni.timeline.get_timeline_interface()
    timeline.play()

    # Warm-up with position targets
    log("Warm-up: 500 steps...")
    from omni.isaac.core.utils.types import ArticulationAction
    for _ in range(500):
        action_obj = ArticulationAction(joint_positions=init_pos_dof)
        robot.apply_action(action_obj)
        world.step(render=True)

    # Reset to initial state
    robot.set_joint_positions(init_pos_dof)
    robot.set_joint_velocities(np.zeros_like(init_pos_dof))
    for _ in range(200):
        action_obj = ArticulationAction(joint_positions=init_pos_dof)
        robot.apply_action(action_obj)
        world.step(render=True)

    pos, quat = robot.get_world_pose()
    log(f"After warm-up: pos_z={pos[2]:.3f}, w={quat[0]:.4f}")

    # Control loop
    last_action = np.zeros(12, dtype=np.float32)
    cmd_vel = np.zeros(3, dtype=np.float32)

    log(f"\nRunning {args.steps} control steps...")
    log(f"{'Step':>5} {'w':>7} {'x':>7} {'y':>7} {'pz':>7} {'gz':>7} {'amax':>7}")

    for step in range(args.steps):
        joint_pos_dof = robot.get_joint_positions()
        joint_vel_dof = robot.get_joint_velocities()
        pos, quat_wxyz = robot.get_world_pose()
        lin_vel = robot.get_linear_velocity()
        ang_vel = robot.get_angular_velocity()

        quat_wxyz = quat_wxyz.astype(np.float32)
        lin_vel_body = quat_rotate_inverse(quat_wxyz, lin_vel.astype(np.float32))
        ang_vel_body = quat_rotate_inverse(quat_wxyz, ang_vel.astype(np.float32))

        joint_pos_policy = joint_pos_dof[policy_to_dof].astype(np.float32)
        joint_vel_policy = joint_vel_dof[policy_to_dof].astype(np.float32)

        obs = np.zeros(48, dtype=np.float32)
        obs[0:3] = lin_vel_body
        obs[3:6] = ang_vel_body
        obs[6:9] = quat_rotate_inverse(quat_wxyz, np.array([0, 0, -1], dtype=np.float32))
        obs[9:12] = cmd_vel
        obs[12:24] = joint_pos_policy - DEFAULT_JOINT_POS
        obs[24:36] = joint_vel_policy
        obs[36:48] = last_action

        with torch.no_grad():
            obs_t = torch.from_numpy(obs).unsqueeze(0)
            action = policy(obs_t).squeeze(0).numpy()

        last_action = action.copy()
        scaled_action = action * ACTION_SCALE
        target_pos_policy = DEFAULT_JOINT_POS + scaled_action

        # Apply position targets (DriveAPI handles PD + maxForce clipping)
        target_pos_dof = np.zeros(len(dof_names), dtype=np.float32)
        for p_idx in range(12):
            d_idx = policy_to_dof[p_idx]
            target_pos_dof[d_idx] = target_pos_policy[p_idx]

        action_obj = ArticulationAction(joint_positions=target_pos_dof)
        robot.apply_action(action_obj)

        for _ in range(args.decimation):
            world.step(render=True)

        grav = quat_rotate_inverse(quat_wxyz, np.array([0, 0, -1], dtype=np.float32))
        if step < 10 or step % 25 == 0:
            log(f"{step:5d} w={quat_wxyz[0]:6.3f} x={quat_wxyz[1]:6.3f} y={quat_wxyz[2]:6.3f} pz={pos[2]:6.3f} gz={grav[2]:6.3f} amax={np.abs(action).max():6.3f}")

        if abs(grav[2]) < 0.5:
            log(f"  ROBOT FELL at step {step}! grav_z={grav[2]:.3f}")
            break

    log("\nTest complete.")
    simulation_app.close()


if __name__ == "__main__":
    main()

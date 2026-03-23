#!/usr/bin/env python3
"""Launch Isaac Lab Go2 environment with UDP state bridge.

Uses Isaac Lab's own gym environment (with correct DCMotor actuators)
for physics. Publishes robot state via UDP for:
  - ros2_state_bridge.py (ROS2 topics)
  - web_viewer.py (3D visualization in browser)

The policy runs directly inside this process.
cmd_vel commands are received via UDP from the ROS2 bridge.

Usage:
    source /home/panda/robotics/isaac_sim/activate.sh
    cd /home/panda/robotics/isaac_sim/references/isaac-go2-ros2
    python3 -u /home/panda/robotics/robotics_env/sim/launch_isaaclab.py --headless
"""
from __future__ import annotations
import os, sys, argparse, time, math, struct, socket

os.environ["PYTHONUNBUFFERED"] = "1"

# Must parse args before importing Isaac Lab
from isaaclab.app import AppLauncher
parser = argparse.ArgumentParser(description="Go2 Isaac Lab + UDP Bridge")
AppLauncher.add_app_launcher_args(parser)
parser.add_argument("--freq", type=float, default=25.0, help="Control frequency (Hz)")
parser.add_argument("--udp-port", type=int, default=9870, help="UDP port for state output")
parser.add_argument("--cmd-port", type=int, default=9871, help="UDP port for cmd_vel input")
parser.add_argument("--viewer-port", type=int, default=9872, help="UDP port for web viewer (0=disabled)")
args = parser.parse_args()
app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

# Now safe to import
import numpy as np
import torch
import torch.nn as nn
import gymnasium as gym

# Add reference repo for Go2 configs
sys.path.insert(0, "/home/panda/robotics/isaac_sim/references/isaac-go2-ros2")
from go2.go2_env import Go2RSLEnvCfg
import go2.go2_ctrl as go2_ctrl


def log(msg):
    print(msg, flush=True)


POLICY_PATH = "/home/panda/robotics/isaac_sim/references/isaac-go2-ros2/ckpts/unitree_go2/flat_model_6800.pt"

JOINT_NAMES = [
    "FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint",
    "FL_thigh_joint", "FR_thigh_joint", "RL_thigh_joint", "RR_thigh_joint",
    "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint",
]


class ActorMLP(nn.Module):
    def __init__(self, obs_dim=48, act_dim=12, hidden=None):
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

    def forward(self, obs):
        return self.actor(obs)


class UDPBridge:
    """Sends robot state via UDP to multiple targets, receives cmd_vel."""

    # State packet: sim_time(d) + pos(3d) + quat(4d) + lin_vel(3d) + ang_vel(3d) +
    #               joint_pos(12d) + joint_vel(12d) = 38 doubles = 304 bytes
    STATE_FMT = "!d3d4d3d3d12d12d"
    STATE_SIZE = struct.calcsize(STATE_FMT)
    # cmd_vel packet: vx(d) + vy(d) + wz(d) = 24 bytes
    CMD_FMT = "!3d"
    CMD_SIZE = struct.calcsize(CMD_FMT)

    def __init__(self, state_port=9870, cmd_port=9871, viewer_port=0):
        self.state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.state_targets = [("127.0.0.1", state_port)]
        if viewer_port > 0:
            self.state_targets.append(("127.0.0.1", viewer_port))

        self.cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cmd_sock.bind(("127.0.0.1", cmd_port))
        self.cmd_sock.setblocking(False)

        self.cmd_vel = np.zeros(3, dtype=np.float64)
        targets_str = ", ".join(f":{p}" for _, p in self.state_targets)
        log(f"UDP Bridge: state->{targets_str}, cmd<-:{cmd_port}")

    def send_state(self, sim_time, pos, quat_wxyz, lin_vel, ang_vel, joint_pos, joint_vel):
        """Pack and send robot state to all targets."""
        data = struct.pack(
            self.STATE_FMT,
            sim_time,
            *pos.tolist(),
            *quat_wxyz.tolist(),
            *lin_vel.tolist(),
            *ang_vel.tolist(),
            *joint_pos.tolist(),
            *joint_vel.tolist(),
        )
        for addr in self.state_targets:
            self.state_sock.sendto(data, addr)

    def recv_cmd_vel(self):
        """Non-blocking receive of cmd_vel. Returns latest cmd_vel."""
        try:
            while True:  # Drain all pending packets, keep last
                data, _ = self.cmd_sock.recvfrom(self.CMD_SIZE)
                if len(data) == self.CMD_SIZE:
                    vx, vy, wz = struct.unpack(self.CMD_FMT, data)
                    self.cmd_vel[0] = vx
                    self.cmd_vel[1] = vy
                    self.cmd_vel[2] = wz
        except BlockingIOError:
            pass
        return self.cmd_vel

    def close(self):
        self.state_sock.close()
        self.cmd_sock.close()


def main():
    log("=" * 60)
    log("  Go2 Isaac Lab + UDP State Bridge")
    log(f"  Control freq: {args.freq} Hz")
    log(f"  UDP state port: {args.udp_port}, cmd port: {args.cmd_port}")
    if args.viewer_port > 0:
        log(f"  Web viewer port: {args.viewer_port}")
    log("=" * 60)

    # Create environment
    cfg = Go2RSLEnvCfg()
    cfg.scene.num_envs = 1
    cfg.sim.device = "cpu"
    cfg.decimation = max(1, math.ceil(1.0 / cfg.sim.dt / args.freq))
    cfg.sim.render_interval = cfg.decimation
    go2_ctrl.init_base_vel_cmd(1)
    cfg.observations.policy.height_scan = None

    log(f"Creating Isaac Lab env (decimation={cfg.decimation}, dt={cfg.sim.dt})...")
    env = gym.make("Isaac-Velocity-Flat-Unitree-Go2-v0", cfg=cfg)
    log("Environment created")

    # Load policy
    ckpt = torch.load(POLICY_PATH, map_location="cpu", weights_only=False)
    actor_state = {k: v for k, v in ckpt["model_state_dict"].items() if k.startswith("actor.")}
    policy = ActorMLP()
    policy.load_state_dict(actor_state)
    policy.eval()
    log(f"Policy loaded from {POLICY_PATH}")

    # Setup UDP bridge
    bridge = UDPBridge(
        state_port=args.udp_port,
        cmd_port=args.cmd_port,
        viewer_port=args.viewer_port,
    )

    # Reset environment
    obs_dict, _ = env.reset()
    obs = obs_dict["policy"] if isinstance(obs_dict, dict) else obs_dict
    log(f"Observation shape: {obs.shape}")

    # Main loop
    sim_step_dt = float(cfg.sim.dt * cfg.decimation)
    step_count = 0
    sim_time = 0.0
    log(f"\nStarting main loop (sim_step_dt={sim_step_dt:.4f}s)...")
    log("Robot should be standing. Send cmd_vel via UDP for movement.")

    while simulation_app.is_running():
        start_time = time.time()

        # Check for cmd_vel updates
        cmd = bridge.recv_cmd_vel()
        go2_ctrl.base_vel_cmd_input[0, 0] = cmd[0]  # vx
        go2_ctrl.base_vel_cmd_input[0, 1] = cmd[1]  # vy
        go2_ctrl.base_vel_cmd_input[0, 2] = cmd[2]  # wz

        with torch.inference_mode():
            # Policy inference
            actions = policy(obs)

            # Step environment
            obs_dict, _, _, _, _ = env.step(actions)
            obs = obs_dict["policy"] if isinstance(obs_dict, dict) else obs_dict

        step_count += 1
        sim_time += sim_step_dt

        # Extract robot state and send via UDP
        robot_data = env.unwrapped.scene["unitree_go2"].data
        root_state = robot_data.root_state_w[0].cpu().numpy()
        joint_pos = robot_data.joint_pos[0].cpu().numpy()
        joint_vel = robot_data.joint_vel[0].cpu().numpy()

        bridge.send_state(
            sim_time=sim_time,
            pos=root_state[:3],
            quat_wxyz=root_state[3:7],
            lin_vel=root_state[7:10],
            ang_vel=root_state[10:13],
            joint_pos=joint_pos,
            joint_vel=joint_vel,
        )

        # Rate limiting
        elapsed = time.time() - start_time
        if elapsed < sim_step_dt:
            time.sleep(sim_step_dt - elapsed)

        if step_count % 250 == 0:
            pos_z = root_state[2]
            grav = robot_data.projected_gravity_b[0].cpu().numpy()
            log(f"Step {step_count}: pos_z={pos_z:.3f} gz={grav[2]:.4f} cmd={cmd.tolist()}")

    bridge.close()
    env.close()
    simulation_app.close()
    log("Shutdown complete.")


if __name__ == "__main__":
    main()

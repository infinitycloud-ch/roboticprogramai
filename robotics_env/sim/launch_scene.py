#!/usr/bin/env python3
"""Lance Isaac Sim 5.1.0 en headless avec Go2 URDF + ROS2 bridge.

Ce script tourne sur le DGX Spark (aarch64). Il :
1. Demarre Isaac Sim en mode headless
2. Cree un ground plane (sol plat)
3. Charge le Go2 depuis son URDF
4. Configure l'OmniGraph ROS2 bridge (isaacsim.ros2.bridge)
   - Publie : /tf, /odom, /joint_states, /clock
   - Souscrit : /joint_commands (positions 12 DOF)
5. Lance la simulation

Prerequis:
    source /home/panda/robotics/isaac_sim/activate.sh
    source /opt/ros/jazzy/setup.bash
    export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

Usage:
    python3 launch_scene.py [--urdf PATH] [--headless]
"""

from __future__ import annotations

import argparse
import os
import sys

# Force unbuffered output for nohup logging
os.environ["PYTHONUNBUFFERED"] = "1"

# Chemins par defaut sur le Spark
DEFAULT_URDF = "/home/panda/robotics/sim/urdf/go2_description/urdf/go2_description.urdf"
FALLBACK_URDF = os.path.join(
    os.path.dirname(__file__), "urdf", "go2_description", "urdf", "go2_description.urdf"
)


def log(msg: str) -> None:
    """Print with flush for nohup compatibility."""
    print(msg, flush=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Isaac Sim Go2 Scene Launcher")
    parser.add_argument(
        "--urdf",
        default=DEFAULT_URDF,
        help="Chemin vers le URDF Go2",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Lancer en mode headless (defaut: True)",
    )
    parser.add_argument(
        "--physics-dt",
        type=float,
        default=1.0 / 200.0,
        help="Pas de temps physique en secondes (defaut: 1/200)",
    )
    parser.add_argument(
        "--rendering-dt",
        type=float,
        default=1.0 / 30.0,
        help="Pas de temps rendu en secondes (defaut: 1/30)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Resoudre le chemin URDF
    urdf_path = args.urdf
    if not os.path.exists(urdf_path):
        urdf_path = FALLBACK_URDF
    if not os.path.exists(urdf_path):
        log(f"ERREUR: URDF Go2 introuvable: {args.urdf}")
        log(f"        Fallback aussi absent: {FALLBACK_URDF}")
        log("        Clonez: git clone https://github.com/Unitree-Go2-Robot/go2_description.git")
        sys.exit(1)

    log("=" * 60)
    log("  RoboticProgramAI -- Isaac Sim Go2 Scene (v8)")
    log("=" * 60)
    log(f"  URDF:       {urdf_path}")
    log(f"  Headless:   {args.headless}")
    log(f"  Physics dt: {args.physics_dt}")
    log(f"  Render dt:  {args.rendering_dt}")
    log("=" * 60)

    # --- Import Isaac Sim (doit etre fait AVANT tout import Omniverse) ---
    try:
        from isaacsim import SimulationApp
    except ImportError:
        log("ERREUR: isaacsim non disponible.")
        log("        pip install 'isaacsim[all]==5.1.0' --extra-index-url https://pypi.nvidia.com")
        sys.exit(1)

    # Lancer SimulationApp
    sim_cfg = {
        "headless": args.headless,
        "width": 1280,
        "height": 720,
        "anti_aliasing": 0,
    }
    simulation_app = SimulationApp(sim_cfg)

    # --- Imports Omniverse (apres SimulationApp) ---
    import omni.usd
    from pxr import Gf, UsdGeom, UsdPhysics

    from omni.isaac.core import World
    from omni.isaac.core.utils.extensions import enable_extension

    # Activer le bridge ROS2 (namespace v5.x)
    enable_extension("isaacsim.ros2.bridge")

    log("[1/6] Isaac Sim demarre")

    # --- Creer le monde ---
    world = World(
        physics_dt=args.physics_dt,
        rendering_dt=args.rendering_dt,
        stage_units_in_meters=1.0,
    )

    log("[2/6] World cree")

    # --- Ground plane ---
    world.scene.add_default_ground_plane()
    log("[3/6] Ground plane ajoute")

    # --- Charger le Go2 URDF ---
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
    # PD gains MUST match Isaac Lab training config (UNITREE_GO2_CFG DCMotorCfg)
    import_config.default_drive_strength = 25.0       # stiffness (Nm/rad) — training: 25.0
    import_config.default_position_drive_damping = 0.5  # damping (Nms/rad) — training: 0.5

    # Isaac Sim 5.x API : parse_urdf(root_path, filename, config)
    urdf_dir = os.path.dirname(os.path.abspath(urdf_path))
    urdf_file = os.path.basename(urdf_path)
    parsed_robot = urdf_interface.parse_urdf(urdf_dir, urdf_file, import_config)
    prim_path = urdf_interface.import_robot(
        urdf_dir,
        urdf_file,
        parsed_robot,
        import_config,
        "",
        True,
    )
    log(f"[4/6] Go2 URDF charge -> {prim_path}")

    robot_prim_path = prim_path if prim_path else "/go2_description"
    log(f"  Robot prim path: {robot_prim_path}")

    # --- Verifier/Forcer ArticulationRootAPI ---
    stage = omni.usd.get_context().get_stage()

    articulation_root_path = None
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            articulation_root_path = str(prim.GetPath())
            log(f"  ArticulationRootAPI trouve: {articulation_root_path}")
            break

    if articulation_root_path is None:
        log("  WARN: Pas d'ArticulationRootAPI detecte, application manuelle...")
        root_prim = stage.GetPrimAtPath(robot_prim_path)
        if root_prim.IsValid():
            UsdPhysics.ArticulationRootAPI.Apply(root_prim)
            articulation_root_path = robot_prim_path
            log(f"  ArticulationRootAPI applique manuellement sur {robot_prim_path}")
        else:
            log(f"  ERREUR: Prim {robot_prim_path} invalide, ArticulationRootAPI non applique")
            articulation_root_path = robot_prim_path

    # Positionner le robot legerement au-dessus du sol
    go2_prim = stage.GetPrimAtPath(robot_prim_path)
    if go2_prim.IsValid():
        xformable = UsdGeom.Xformable(go2_prim)
        xformable.ClearXformOpOrder()
        xformable.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 0.35))
        log("  Position initiale: (0, 0, 0.4)")
    else:
        log(f"  WARN: Prim {robot_prim_path} non trouve, position non ajustee")

    # --- Appliquer les positions articulaires par defaut (Go2 standing pose) ---
    _set_initial_joint_positions(stage, robot_prim_path)

    # --- Configurer OmniGraph ROS2 Bridge ---
    _setup_ros2_bridge(world, robot_prim_path, articulation_root_path)
    log("[5/6] OmniGraph ROS2 bridge configure")

    # --- Ajouter le robot comme articulation pour controler les joints ---
    from omni.isaac.core.articulations import Articulation
    robot_art = Articulation(prim_path=articulation_root_path, name="go2")
    world.scene.add(robot_art)

    # --- Lancer la simulation ---
    log("")
    log("Simulation demarree. Ctrl+C pour arreter.")
    log("Topics ROS2 publies: /tf, /odom, /joint_states, /clock")
    log("Topics ROS2 souscrits: /joint_commands")
    log("")

    world.reset()

    # Appliquer les positions articulaires initiales via l'API Articulation
    import numpy as np_init
    # Ordre des joints tel que retourne par l'articulation
    joint_names = robot_art.dof_names
    log(f"  DOF names ({len(joint_names)}): {joint_names}")

    # Positions par defaut Go2
    default_pos_map = {
        "FL_hip_joint": 0.1, "FR_hip_joint": -0.1,
        "RL_hip_joint": 0.1, "RR_hip_joint": -0.1,
        "FL_thigh_joint": 0.8, "FR_thigh_joint": 0.8,
        "RL_thigh_joint": 1.0, "RR_thigh_joint": 1.0,
        "FL_calf_joint": -1.5, "FR_calf_joint": -1.5,
        "RL_calf_joint": -1.5, "RR_calf_joint": -1.5,
    }
    init_pos = np_init.zeros(len(joint_names), dtype=np_init.float32)
    for i, name in enumerate(joint_names):
        if name in default_pos_map:
            init_pos[i] = default_pos_map[name]

    robot_art.set_joint_positions(init_pos)
    robot_art.set_joint_velocities(np_init.zeros_like(init_pos))
    log(f"  Joint positions initiales appliquees via Articulation API: {init_pos.tolist()}")

    # Forcer le timeline en mode play pour que OnPlaybackTick se declenche
    import omni.timeline
    timeline = omni.timeline.get_timeline_interface()
    timeline.play()

    # Warm-up: laisser le PD controller stabiliser le robot avant de continuer
    log("  Warm-up: 500 steps pour stabilisation PD...")
    for i in range(500):
        world.step(render=True)
    # Re-appliquer les positions si le robot a bouge pendant le warm-up
    robot_art.set_joint_positions(init_pos)
    robot_art.set_joint_velocities(np_init.zeros_like(init_pos))
    for i in range(200):
        world.step(render=True)
    log("[6/6] World reset + warm-up + timeline play, simulation stable")

    try:
        step_count = 0
        while simulation_app.is_running():
            # render=True requis meme en headless pour que OmniGraph s'execute
            world.step(render=True)
            step_count += 1
            if step_count == 1:
                log("  Premier step OK")
            elif step_count == 100:
                log("  100 steps OK")
            elif step_count == 1000:
                log("  1000 steps OK - simulation stable")
    except KeyboardInterrupt:
        log("\nArret demande.")
    finally:
        simulation_app.close()
        log("Isaac Sim ferme.")


def _set_initial_joint_positions(stage, robot_prim_path: str) -> None:
    """Set Go2 initial joint positions to standing pose.

    Without this, all joints default to 0 rad and the robot collapses immediately.
    Default standing pose from Isaac Lab UNITREE_GO2_CFG.
    """
    from pxr import UsdPhysics

    # Go2 standing pose (joint_name -> radians)
    default_positions = {
        "FL_hip_joint": 0.1,
        "FR_hip_joint": -0.1,
        "RL_hip_joint": 0.1,
        "RR_hip_joint": -0.1,
        "FL_thigh_joint": 0.8,
        "FR_thigh_joint": 0.8,
        "RL_thigh_joint": 1.0,
        "RR_thigh_joint": 1.0,
        "FL_calf_joint": -1.5,
        "FR_calf_joint": -1.5,
        "RL_calf_joint": -1.5,
        "RR_calf_joint": -1.5,
    }

    set_count = 0
    for prim in stage.Traverse():
        prim_name = prim.GetName()
        if prim_name in default_positions:
            drive_api = UsdPhysics.DriveAPI.Get(prim, "angular")
            if drive_api:
                import math
                target_deg = math.degrees(default_positions[prim_name])
                drive_api.GetTargetPositionAttr().Set(target_deg)
                set_count += 1

    if set_count > 0:
        log(f"  Positions initiales appliquees: {set_count}/12 joints")
    else:
        log("  WARN: Aucune position initiale appliquee (DriveAPI non trouve)")
        # Fallback: try setting joint states directly via PhysX
        log("  Tentative fallback via joint state attributes...")
        for prim in stage.Traverse():
            prim_name = prim.GetName()
            if prim_name in default_positions:
                joint = UsdPhysics.RevoluteJoint(prim)
                if joint:
                    # Try to set via USD attributes
                    state_attr = prim.GetAttribute("state:angular:physics:position")
                    if state_attr:
                        import math
                        state_attr.Set(math.degrees(default_positions[prim_name]))
                        set_count += 1
        log(f"  Fallback: {set_count} joints configures")


def _setup_ros2_bridge(world, robot_prim_path: str, articulation_root_path: str) -> None:
    """Configurer l'OmniGraph pour le bridge ROS2.

    Cree les noeuds OmniGraph qui publient les topics ROS2 depuis Isaac Sim :
    - /clock (rosgraph_msgs/Clock)
    - /tf (tf2_msgs/TFMessage)
    - /odom (nav_msgs/Odometry) via IsaacComputeOdometry
    - /joint_states (sensor_msgs/JointState)

    Et souscrit a :
    - /joint_commands (sensor_msgs/JointState) -> Articulation Controller

    Args:
        world: Isaac Sim World object.
        robot_prim_path: Chemin du prim robot sur le stage (ex: /go2_description).
        articulation_root_path: Chemin du prim avec ArticulationRootAPI.
    """
    import omni.graph.core as og

    keys = og.Controller.Keys
    (graph, nodes, _, _) = og.Controller.edit(
        {"graph_path": "/World/ROS2Bridge", "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: [
                ("OnPlaybackTick", "omni.graph.action.OnPlaybackTick"),
                ("Context", "isaacsim.ros2.bridge.ROS2Context"),
                ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                # Publishers
                ("PublishClock", "isaacsim.ros2.bridge.ROS2PublishClock"),
                ("PublishTF", "isaacsim.ros2.bridge.ROS2PublishTransformTree"),
                ("PublishJointStates", "isaacsim.ros2.bridge.ROS2PublishJointState"),
                # Odometry: compute then publish
                ("ComputeOdometry", "isaacsim.core.nodes.IsaacComputeOdometry"),
                ("PublishOdom", "isaacsim.ros2.bridge.ROS2PublishOdometry"),
                # Subscriber -> Articulation Controller
                ("SubscribeJointCmd", "isaacsim.ros2.bridge.ROS2SubscribeJointState"),
                ("ArticulationController", "isaacsim.core.nodes.IsaacArticulationController"),
            ],
            keys.SET_VALUES: [
                # Sim time
                ("ReadSimTime.inputs:resetOnStop", False),
                # Clock
                ("PublishClock.inputs:topicName", "/clock"),
                # TF
                ("PublishTF.inputs:topicName", "/tf"),
                ("PublishTF.inputs:targetPrims", [robot_prim_path]),
                # Joint States — use articulation root
                ("PublishJointStates.inputs:topicName", "/joint_states"),
                ("PublishJointStates.inputs:targetPrim", articulation_root_path),
                # Odometry compute — chassis prim
                ("ComputeOdometry.inputs:chassisPrim", [robot_prim_path]),
                # Odometry publish
                ("PublishOdom.inputs:topicName", "/odom"),
                ("PublishOdom.inputs:chassisFrameId", "base_link"),
                ("PublishOdom.inputs:odomFrameId", "odom"),
                # Joint command subscriber
                ("SubscribeJointCmd.inputs:topicName", "/joint_commands"),
                # Articulation controller — use articulation root
                ("ArticulationController.inputs:targetPrim", articulation_root_path),
                ("ArticulationController.inputs:robotPath", articulation_root_path),
            ],
            keys.CONNECT: [
                # Tick -> publishers
                ("OnPlaybackTick.outputs:tick", "PublishClock.inputs:execIn"),
                ("OnPlaybackTick.outputs:tick", "PublishTF.inputs:execIn"),
                ("OnPlaybackTick.outputs:tick", "PublishJointStates.inputs:execIn"),
                # Tick -> odometry compute -> odometry publish
                ("OnPlaybackTick.outputs:tick", "ComputeOdometry.inputs:execIn"),
                ("ComputeOdometry.outputs:execOut", "PublishOdom.inputs:execIn"),
                ("ComputeOdometry.outputs:position", "PublishOdom.inputs:position"),
                ("ComputeOdometry.outputs:orientation", "PublishOdom.inputs:orientation"),
                ("ComputeOdometry.outputs:linearVelocity", "PublishOdom.inputs:linearVelocity"),
                ("ComputeOdometry.outputs:angularVelocity", "PublishOdom.inputs:angularVelocity"),
                # ROS2 Context -> all ROS2 nodes
                ("Context.outputs:context", "PublishClock.inputs:context"),
                ("Context.outputs:context", "PublishTF.inputs:context"),
                ("Context.outputs:context", "PublishJointStates.inputs:context"),
                ("Context.outputs:context", "PublishOdom.inputs:context"),
                ("Context.outputs:context", "SubscribeJointCmd.inputs:context"),
                # Sim time -> Clock + Odom timestamps
                ("ReadSimTime.outputs:simulationTime", "PublishClock.inputs:timeStamp"),
                ("ReadSimTime.outputs:simulationTime", "PublishOdom.inputs:timeStamp"),
                # Subscriber -> Articulation Controller
                ("OnPlaybackTick.outputs:tick", "SubscribeJointCmd.inputs:execIn"),
                ("SubscribeJointCmd.outputs:execOut", "ArticulationController.inputs:execIn"),
                ("SubscribeJointCmd.outputs:positionCommand", "ArticulationController.inputs:positionCommand"),
            ],
        },
    )


if __name__ == "__main__":
    main()

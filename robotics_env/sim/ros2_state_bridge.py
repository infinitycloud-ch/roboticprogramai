#!/usr/bin/env python3
"""ROS2 State Bridge — receives robot state via UDP from Isaac Lab sim,
publishes as ROS2 topics (/odom, /joint_states, /tf, /clock).

Receives cmd_vel from ROS2 and forwards via UDP to the sim.

Runs with system Python 3.12 + ROS2 Jazzy (no Isaac Sim dependency).

Usage:
    source /opt/ros/jazzy/setup.bash
    python3 ros2_state_bridge.py
"""
from __future__ import annotations
import struct, socket, time, threading

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState
from rosgraph_msgs.msg import Clock
from tf2_msgs.msg import TFMessage
from builtin_interfaces.msg import Time
import numpy as np

# Must match launch_isaaclab.py
STATE_FMT = "!d3d4d3d3d12d12d"
STATE_SIZE = struct.calcsize(STATE_FMT)
CMD_FMT = "!3d"

JOINT_NAMES = [
    "FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint",
    "FL_thigh_joint", "FR_thigh_joint", "RL_thigh_joint", "RR_thigh_joint",
    "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint",
]


def quat_wxyz_to_xyzw(q):
    """Convert (w,x,y,z) to (x,y,z,w) for ROS2."""
    return (q[1], q[2], q[3], q[0])


def sim_time_to_msg(sim_time: float) -> Time:
    sec = int(sim_time)
    nanosec = int((sim_time - sec) * 1e9)
    msg = Time()
    msg.sec = sec
    msg.nanosec = nanosec
    return msg


class StateBridge(Node):
    def __init__(self, state_port=9870, cmd_port=9871):
        super().__init__("sim_state_bridge")

        # UDP receiver for state
        self.state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.state_sock.bind(("127.0.0.1", state_port))
        self.state_sock.settimeout(1.0)

        # UDP sender for cmd_vel
        self.cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cmd_addr = ("127.0.0.1", cmd_port)

        # Publishers
        self.odom_pub = self.create_publisher(Odometry, "/odom", 10)
        self.joint_pub = self.create_publisher(JointState, "/joint_states", 10)
        self.clock_pub = self.create_publisher(Clock, "/clock", 10)
        self.tf_pub = self.create_publisher(TFMessage, "/tf", 10)

        # cmd_vel subscriber
        self.cmd_sub = self.create_subscription(Twist, "/cmd_vel", self._cmd_vel_cb, 10)

        self.get_logger().info(f"State bridge: UDP state<-:{state_port}, cmd->:{cmd_port}")
        self.get_logger().info("Publishing: /odom, /joint_states, /clock, /tf")
        self.get_logger().info("Subscribing: /cmd_vel")

        # Start receive thread
        self._running = True
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

    def _cmd_vel_cb(self, msg: Twist):
        """Forward cmd_vel to sim via UDP."""
        data = struct.pack(CMD_FMT, msg.linear.x, msg.linear.y, msg.angular.z)
        self.cmd_sock.sendto(data, self.cmd_addr)

    def _recv_loop(self):
        """Receive robot state from sim via UDP and publish ROS2 topics."""
        msg_count = 0
        while self._running:
            try:
                data, _ = self.state_sock.recvfrom(STATE_SIZE + 64)
            except socket.timeout:
                continue
            except Exception as e:
                self.get_logger().error(f"UDP recv error: {e}")
                continue

            if len(data) != STATE_SIZE:
                continue

            values = struct.unpack(STATE_FMT, data)
            idx = 0
            sim_time = values[idx]; idx += 1
            pos = values[idx:idx+3]; idx += 3
            quat_wxyz = values[idx:idx+4]; idx += 4
            lin_vel = values[idx:idx+3]; idx += 3
            ang_vel = values[idx:idx+3]; idx += 3
            joint_pos = values[idx:idx+12]; idx += 12
            joint_vel = values[idx:idx+12]; idx += 12

            stamp = sim_time_to_msg(sim_time)
            quat_xyzw = quat_wxyz_to_xyzw(quat_wxyz)

            # Publish /clock
            clock_msg = Clock()
            clock_msg.clock = stamp
            self.clock_pub.publish(clock_msg)

            # Publish /odom
            odom = Odometry()
            odom.header.stamp = stamp
            odom.header.frame_id = "odom"
            odom.child_frame_id = "base_link"
            odom.pose.pose.position.x = pos[0]
            odom.pose.pose.position.y = pos[1]
            odom.pose.pose.position.z = pos[2]
            odom.pose.pose.orientation.x = quat_xyzw[0]
            odom.pose.pose.orientation.y = quat_xyzw[1]
            odom.pose.pose.orientation.z = quat_xyzw[2]
            odom.pose.pose.orientation.w = quat_xyzw[3]
            odom.twist.twist.linear.x = lin_vel[0]
            odom.twist.twist.linear.y = lin_vel[1]
            odom.twist.twist.linear.z = lin_vel[2]
            odom.twist.twist.angular.x = ang_vel[0]
            odom.twist.twist.angular.y = ang_vel[1]
            odom.twist.twist.angular.z = ang_vel[2]
            self.odom_pub.publish(odom)

            # Publish /joint_states
            js = JointState()
            js.header.stamp = stamp
            js.name = list(JOINT_NAMES)
            js.position = list(joint_pos)
            js.velocity = list(joint_vel)
            self.joint_pub.publish(js)

            # Publish /tf (odom -> base_link)
            tf = TransformStamped()
            tf.header.stamp = stamp
            tf.header.frame_id = "odom"
            tf.child_frame_id = "base_link"
            tf.transform.translation.x = pos[0]
            tf.transform.translation.y = pos[1]
            tf.transform.translation.z = pos[2]
            tf.transform.rotation.x = quat_xyzw[0]
            tf.transform.rotation.y = quat_xyzw[1]
            tf.transform.rotation.z = quat_xyzw[2]
            tf.transform.rotation.w = quat_xyzw[3]
            tf_msg = TFMessage()
            tf_msg.transforms = [tf]
            self.tf_pub.publish(tf_msg)

            msg_count += 1
            if msg_count % 250 == 0:
                self.get_logger().info(
                    f"Published {msg_count} frames, pos=({pos[0]:.2f},{pos[1]:.2f},{pos[2]:.3f})"
                )

    def destroy_node(self):
        self._running = False
        self.state_sock.close()
        self.cmd_sock.close()
        super().destroy_node()


def main():
    rclpy.init()
    node = StateBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

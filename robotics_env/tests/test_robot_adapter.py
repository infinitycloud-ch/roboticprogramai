"""Tests pour l'interface RobotAdapter et les types."""

import pytest
from adapters.types import Twist, Pose, RobotState, SensorData, RobotMode


class TestTwist:
    def test_default_values(self):
        t = Twist()
        assert t.linear_x == 0.0
        assert t.linear_y == 0.0
        assert t.angular_z == 0.0

    def test_custom_values(self):
        t = Twist(linear_x=0.5, angular_z=1.0)
        assert t.linear_x == 0.5
        assert t.angular_z == 1.0

    def test_frozen(self):
        t = Twist()
        with pytest.raises(AttributeError):
            t.linear_x = 1.0


class TestRobotState:
    def test_default_state(self):
        state = RobotState()
        assert state.mode == RobotMode.IDLE
        assert state.joint_positions == ()

    def test_with_joints(self):
        state = RobotState(joint_positions=(0.0,) * 12)
        assert len(state.joint_positions) == 12


class TestRobotMode:
    def test_modes(self):
        assert RobotMode.IDLE.value == "idle"
        assert RobotMode.WALKING.value == "walking"
        assert RobotMode.EMERGENCY_STOP.value == "emergency_stop"

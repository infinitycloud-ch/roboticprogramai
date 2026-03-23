"""Tests d'intégration pour Hello Robot E2E."""

import pytest


class TestHelloRobot:
    """Tests E2E - nécessitent Isaac Sim + ROS2 actifs."""

    @pytest.mark.skip(reason="Nécessite Isaac Sim 4.5.0 + ROS2 Humble actifs")
    def test_hello_robot_e2e(self):
        pass

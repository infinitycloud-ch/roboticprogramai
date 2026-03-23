"""Tests pour le Noeud Locomoteur."""

import pytest
from locomotion.locomotion_controller import LocomotionController


class TestLocomotionController:
    def test_default_freq(self):
        assert LocomotionController.CONTROL_FREQ_HZ == 50

    def test_init(self):
        ctrl = LocomotionController()
        assert ctrl._policy is None

    def test_not_implemented(self):
        ctrl = LocomotionController()
        with pytest.raises(NotImplementedError):
            ctrl.start()

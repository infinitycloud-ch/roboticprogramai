"""Tests pour SimAdapter."""

import pytest
from adapters.sim_adapter import SimAdapter


class TestSimAdapter:
    def test_initial_state(self):
        adapter = SimAdapter()
        assert adapter.is_connected is False

    def test_not_implemented(self):
        adapter = SimAdapter()
        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(adapter.connect())

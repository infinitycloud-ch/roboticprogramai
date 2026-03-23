"""Agent Monocili - Agent mono-tâche."""


class MonociliAgent:
    """Agent spécialisé pour exécuter une tâche unique."""

    def __init__(self, adapter):
        self._adapter = adapter

    async def execute(self, task):
        """Exécuter une tâche spécifique."""
        raise NotImplementedError

"""Agent Jedi - Agent principal de décision et planning."""


class JediAgent:
    """Agent principal qui prend les décisions haut niveau.

    Utilise RobotAdapter pour interagir avec le robot (simulé ou réel).
    """

    def __init__(self, adapter):
        self._adapter = adapter

    async def run(self):
        """Boucle principale de l'agent."""
        raise NotImplementedError

"""Stockage persistant pour état et historique des agents."""


class PersistentStore:
    """Mémoire persistante : état, historique, contexte."""

    def __init__(self, store_path: str = "memory_store.json"):
        self._store_path = store_path

    def save(self, key: str, value) -> None:
        raise NotImplementedError

    def load(self, key: str):
        raise NotImplementedError

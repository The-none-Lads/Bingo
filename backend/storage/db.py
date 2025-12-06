from typing import Any, Dict


class MemoryDB:
    def __init__(self):
        self.games: Dict[str, Dict[str, Any]] = {}
        self.cards: Dict[str, Dict[str, Any]] = {}


db = MemoryDB()

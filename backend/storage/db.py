import asyncio
from typing import Any, Dict


class MemoryDB:
    """
    In-memory storage for games and cards.
    Designed for single-instance, stateful Bingo sessions with per-game concurrency locks.
    """

    def __init__(self, max_games: int = 100, max_cards: int = 25000):
        self.games: Dict[str, Dict[str, Any]] = {}
        self.cards: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self.max_games = max_games
        self.max_cards = max_cards

    def get_lock(self, game_id: str) -> asyncio.Lock:
        """Get or create an asyncio.Lock for a specific game_id to ensure serialized operations."""
        if game_id not in self._locks:
            self._locks[game_id] = asyncio.Lock()
        return self._locks[game_id]

    def set_game(self, game_id: str, game_data: Dict[str, Any]) -> None:
        """Store game data with resource bound enforcement."""
        if len(self.games) >= self.max_games and game_id not in self.games:
            # Evict oldest game if capacity reached
            oldest_key = next(iter(self.games))
            del self.games[oldest_key]
            if oldest_key in self._locks:
                del self._locks[oldest_key]
        self.games[game_id] = game_data

    def set_card(self, public_id: str, card_data: Dict[str, Any]) -> None:
        """Store card data with resource bound enforcement."""
        if len(self.cards) >= self.max_cards and public_id not in self.cards:
            # Evict oldest card if capacity reached
            oldest_key = next(iter(self.cards))
            del self.cards[oldest_key]
        self.cards[public_id] = card_data

    def clear(self) -> None:
        """Reset all in-memory state."""
        self.games.clear()
        self.cards.clear()
        self._locks.clear()


db = MemoryDB()

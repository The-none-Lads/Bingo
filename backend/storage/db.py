import asyncio
import json
import os
import sqlite3
import threading
from typing import Any, Dict, Optional


class MemoryDB:
    """
    Storage for games and cards.

    Game state (drawn numbers, mode, stage) stays purely in-memory: this
    application runs as a single backend replica, and per the project's
    scope, there is no requirement for a game session to survive a
    restart mid-draw.

    Cards are different: a generated card is a reusable artifact (like a
    physical bingo card), meant to remain valid across a backend restart
    and across multiple different game sessions, not just the one it
    happened to be generated alongside. Card storage is therefore backed
    by a small SQLite file (stdlib-only, no new dependency, no separate
    service to run) using a write-through cache: `self.cards` stays a
    plain dict for every existing read pattern (`.get()`, `in`, `.items()`),
    while `set_card()`/`clear()` also persist to disk, and cards are
    hydrated back into memory once at startup.
    """

    def __init__(
        self,
        max_games: int = 100,
        max_cards: int = 25000,
        card_db_path: Optional[str] = None,
    ):
        self.games: Dict[str, Dict[str, Any]] = {}
        self.cards: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self.max_games = max_games
        self.max_cards = max_cards

        # ":memory:" (used by default in tests, see conftest.py) never
        # touches disk and is fully isolated per-process/per-instance.
        self._card_db_path = (
            card_db_path
            if card_db_path is not None
            else os.getenv("CARD_DB_PATH", "data/cards.db")
        )
        self._card_db_lock = threading.Lock()
        self._card_conn = self._init_card_db()
        self._hydrate_cards_from_disk()

    def _init_card_db(self) -> sqlite3.Connection:
        path = self._card_db_path
        if path != ":memory:":
            dirname = os.path.dirname(path)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
        # check_same_thread=False: FastAPI runs sync `def` path operations
        # in a thread pool, so reads of self.cards (a plain dict) can
        # happen off the main thread even though writes currently only
        # ever come from async endpoints on the event loop thread. The
        # lock below serializes actual SQLite access defensively.
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cards (
                public_id TEXT PRIMARY KEY,
                serial TEXT NOT NULL,
                game_id TEXT,
                grid TEXT NOT NULL
            )
            """
        )
        conn.commit()
        return conn

    def _hydrate_cards_from_disk(self) -> None:
        with self._card_db_lock:
            rows = self._card_conn.execute(
                "SELECT public_id, serial, game_id, grid FROM cards"
            ).fetchall()
        for public_id, serial, game_id, grid_json in rows:
            self.cards[public_id] = {
                "serial": serial,
                "game_id": game_id,
                "grid": json.loads(grid_json),
            }

    def get_lock(self, game_id: str) -> asyncio.Lock:
        """Get or create an asyncio.Lock for a specific game_id to ensure serialized operations."""
        if game_id not in self._locks:
            self._locks[game_id] = asyncio.Lock()
        return self._locks[game_id]

    def set_game(self, game_id: str, game_data: Dict[str, Any]) -> None:
        """Store game data with resource bound enforcement (in-memory only)."""
        if len(self.games) >= self.max_games and game_id not in self.games:
            # Evict oldest game if capacity reached
            oldest_key = next(iter(self.games))
            del self.games[oldest_key]
            if oldest_key in self._locks:
                del self._locks[oldest_key]
        self.games[game_id] = game_data

    def set_card(self, public_id: str, card_data: Dict[str, Any]) -> None:
        """Store card data in memory and persist it to disk (write-through)."""
        if len(self.cards) >= self.max_cards and public_id not in self.cards:
            # Evict oldest card if capacity reached, in memory and on disk.
            oldest_key = next(iter(self.cards))
            del self.cards[oldest_key]
            with self._card_db_lock:
                self._card_conn.execute(
                    "DELETE FROM cards WHERE public_id = ?", (oldest_key,)
                )
                self._card_conn.commit()

        self.cards[public_id] = card_data
        with self._card_db_lock:
            self._card_conn.execute(
                "INSERT OR REPLACE INTO cards (public_id, serial, game_id, grid) VALUES (?, ?, ?, ?)",
                (
                    public_id,
                    card_data["serial"],
                    card_data.get("game_id"),
                    json.dumps(card_data["grid"]),
                ),
            )
            self._card_conn.commit()

    def clear(self) -> None:
        """Reset all state, including the on-disk card store."""
        self.games.clear()
        self.cards.clear()
        self._locks.clear()
        with self._card_db_lock:
            self._card_conn.execute("DELETE FROM cards")
            self._card_conn.commit()

    def close(self) -> None:
        """Close the underlying SQLite connection (mainly for tests)."""
        self._card_conn.close()


db = MemoryDB()

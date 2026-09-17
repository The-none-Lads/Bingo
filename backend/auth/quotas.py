"""
User quota enforcement: max active games and max persistent cards per user.
"""

import os
from typing import Optional

from db_models import User
from fastapi import HTTPException


def get_max_active_games() -> int:
    """Get the per-user active games limit from env."""
    return int(os.getenv("MAX_ACTIVE_GAMES_PER_USER", "10"))


def get_max_persistent_cards_per_user() -> int:
    """Get the per-user persistent cards limit from env."""
    return int(os.getenv("MAX_PERSISTENT_CARDS_PER_USER", "1000"))


async def count_user_active_games(
    user_id: str, exclude_game_id: Optional[str] = None
) -> int:
    """Count active games owned by a user."""
    from storage.db import db as memory_db

    count = 0
    for gid, game in memory_db.games.items():
        if gid == exclude_game_id:
            continue
        if game.get("owner_id") == user_id and game.get("status") == "active":
            count += 1
    return count


async def count_user_persistent_cards(user_id: str) -> int:
    """Count persistent cards owned by a user."""
    from storage.db import db as memory_db

    count = 0
    for public_id, card_data in memory_db.cards.items():
        if card_data.get("owner_id") == user_id:
            if memory_db.cards.is_persistent(public_id):
                count += 1
    return count


async def check_active_games_quota(
    user: User,
    exclude_game_id: Optional[str] = None,
) -> None:
    """Raise HTTPException if user has exceeded their active games quota."""
    if user.role == "ADMIN":
        return  # ADMIN has no quota limit

    current = await count_user_active_games(user.id, exclude_game_id)
    max_games = get_max_active_games()

    if current >= max_games:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Quota exceeded: maximum {max_games} active games per user. "
                f"Please finish or delete an existing game before starting a new one."
            ),
        )


async def check_persistent_cards_quota(
    user: User,
    additional_cards: int = 1,
) -> None:
    """Raise HTTPException if user would exceed their persistent cards quota."""
    if user.role == "ADMIN":
        return  # ADMIN has no quota limit

    current = await count_user_persistent_cards(user.id)
    max_cards = get_max_persistent_cards_per_user()

    if current + additional_cards > max_cards:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Quota exceeded: maximum {max_cards} persistent cards per user. "
                f"You currently have {current} persistent cards."
            ),
        )


async def get_user_quota_info(user: User) -> dict:
    """Get quota usage info for a user."""
    active_games = await count_user_active_games(user.id)
    persistent_cards = await count_user_persistent_cards(user.id)

    return {
        "active_games": active_games,
        "max_games": get_max_active_games() if user.role != "ADMIN" else -1,
        "persistent_cards": persistent_cards,
        "max_persistent_cards": (
            get_max_persistent_cards_per_user() if user.role != "ADMIN" else -1
        ),
    }

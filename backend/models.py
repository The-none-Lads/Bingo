from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class GameMode(str, Enum):
    PROGRESSIVE_ROWS = "progressive_rows"
    FULL_HOUSE = "full_house"
    FOUR_CORNERS = "four_corners"
    DIAGONALS = "diagonals"
    REGULAR = "regular"


# --- Game-related schemas ---


class CreateGameRequest(BaseModel):
    mode: str = Field(
        ...,
        pattern=r"^(progressive_rows|full_house|four_corners|diagonals|regular)$",
        description="Allowed game mode",
    )
    ball_set: int = Field(..., ge=1, le=100, description="Ball set size (1-100)")
    stage: int = Field(..., ge=1, le=5, description="Progressive stage (1-5)")


class GameStateResponse(BaseModel):
    game_id: str
    drawn: List[int]
    mode: str
    stage: int
    status: str


# --- Card-related schemas ---


class CardBatchRequest(BaseModel):
    count: int = Field(..., ge=1, le=500, description="Card count to generate (1-500)")
    game_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Optional game ID associated with the cards",
    )
    persistent: bool = Field(
        default=False,
        description=(
            "If true, generated cards are saved to the persistent card "
            "store and survive a backend restart, reusable across many "
            "games. If false (the default), cards are kept in memory "
            "only and are cleared when the backend restarts."
        ),
    )


class CardResponse(BaseModel):
    exists: bool
    public_id: str
    serial: str
    grid: List[List[Union[str, int]]]
    persistent: bool = False


# --- Validation schemas ---


class ValidateRequest(BaseModel):
    game_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Game ID to validate against",
    )
    serial: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Card public ID / serial",
    )


class ValidateResponse(BaseModel):
    valid: bool
    details: dict
    drawn: List[int]
    grid: List[List[Union[str, int]]]
    public_id: str
    type: Optional[str] = None  # optional, so REST still works

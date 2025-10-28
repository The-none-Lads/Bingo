from pydantic import BaseModel
from typing import List, Optional, Union

# --- Game-related schemas ---


class CreateGameRequest(BaseModel):
    mode: str = (
        "progressive_rows"  # progressive_rows | full_house | four_corners | diagonals
    )
    ball_set: int = 75  # 75-ball or 90-ball
    stage: int = 1  # required rows if progressive


class GameStateResponse(BaseModel):
    game_id: str
    drawn: List[int]
    mode: str
    stage: int
    status: str


# --- Card-related schemas ---


class CardBatchRequest(BaseModel):
    count: int = 50
    game_id: Optional[str] = None


class CardResponse(BaseModel):
    exists: bool
    public_id: str
    serial: str
    grid: List[List[Union[str, int]]]


# --- Validation schemas ---


class ValidateRequest(BaseModel):
    game_id: str
    serial: str  # this will now be the public_id


class ValidateResponse(BaseModel):
    valid: bool
    details: dict
    drawn: List[int]
    grid: List[List[str | int]]
    public_id: str
    type: str | None = None  # optional, so REST still works

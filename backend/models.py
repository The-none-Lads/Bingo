from typing import List, Optional, Union

from pydantic import BaseModel

# --- Game-related schemas ---


class CreateGameRequest(BaseModel):
    mode: str
    ball_set: int
    stage: int


class GameStateResponse(BaseModel):
    game_id: str
    drawn: List[int]
    mode: str
    stage: int
    status: str


# --- Card-related schemas ---


class CardBatchRequest(BaseModel):
    count: int
    game_id: Optional[str]


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

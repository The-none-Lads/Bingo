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
    access_policy: Optional[str] = Field(
        default="LINK_ONLY",
        pattern=r"^(PUBLIC|LINK_ONLY)$",
        description="Game access policy: PUBLIC or LINK_ONLY",
    )


class GameStateResponse(BaseModel):
    game_id: str
    drawn: List[int]
    mode: str
    stage: int
    status: str
    access_policy: Optional[str] = "LINK_ONLY"
    last_activity_at: Optional[str] = None


class GameSettingsRequest(BaseModel):
    max_concurrent_games: int = Field(..., ge=1, le=200)
    inactivity_timeout_minutes: int = Field(..., ge=30, le=60)


class GameSettingsResponse(BaseModel):
    max_concurrent_games: int
    inactivity_timeout_minutes: int
    active_games: int
    available_capacity: int


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


# --- Auth-related schemas ---


class RegisterRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=32,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Username (3-32 alphanumeric characters, underscores, hyphens)",
    )
    email: str = Field(
        ...,
        min_length=5,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        description="Valid email address",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (8-128 characters)",
    )


class LoginRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Username or email address",
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Password",
    )


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class AuthStatusResponse(BaseModel):
    authenticated: bool
    user: Optional[UserResponse] = None


class MessageResponse(BaseModel):
    message: str


# --- Admin schemas ---


class UserAdminResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    auth_providers: List[str] = []
    session_count: int = 0


class UserUpdateRequest(BaseModel):
    role: Optional[str] = Field(None, pattern=r"^(USER|OPERATOR|ADMIN)$")
    is_active: Optional[bool] = None


class UserQuotaInfo(BaseModel):
    active_games: int
    max_games: int
    persistent_cards: int
    max_persistent_cards: int


import hashlib
import random
from typing import List, Union


def generate_75_ball_card() -> List[List[Union[int, str]]]:
    # Each column has its own number range
    columns = {
        0: list(range(1, 16)),  # B
        1: list(range(16, 31)),  # I
        2: list(range(31, 46)),  # N
        3: list(range(46, 61)),  # G
        4: list(range(61, 76)),  # O
    }

    # Build card as a list of columns
    card: List[List[int]] = []
    for col_idx in range(5):
        nums = random.sample(columns[col_idx], 5)
        card.append(nums)

    # Transpose into a 5x5 grid (rows of values)
    grid: List[List[Union[int, str]]] = [
        [card[col][row] for col in range(5)] for row in range(5)
    ]

    # Middle square is always FREE
    grid[2][2] = "FREE"

    return grid


def serialize_card(grid: List[List[Union[int, str]]]) -> str:
    rows: List[str] = []
    for r in grid:
        rows.append(",".join(str(x) for x in r))
    return ";".join(rows)


def deserialize_card(serialized: str) -> List[List[Union[int, str]]]:
    rows = serialized.split(";")
    grid: List[List[Union[int, str]]] = []
    for r in rows:
        vals: List[Union[int, str]] = []
        for v in r.split(","):
            vals.append("FREE" if v == "FREE" else int(v))
        grid.append(vals)
    return grid


def short_id(serial: str, length: int = 8) -> str:
    """Generate a short printable ID from the full serial."""
    h = hashlib.sha256(serial.encode()).hexdigest()
    return h[:length].upper()

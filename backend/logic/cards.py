import hashlib
import random
from typing import List

def generate_75_ball_card() -> List[List[int | str]]:
    card = []
    columns = {
        0: list(range(1, 16)),
        1: list(range(16, 31)),
        2: list(range(31, 46)),
        3: list(range(46, 61)),
        4: list(range(61, 76)),
    }
    for col_idx in range(5):
        nums = random.sample(columns[col_idx], 5)
        card.append(nums)
    grid = [[card[col][row] for col in range(5)] for row in range(5)]
    grid[2][2] = "FREE"
    return grid

def serialize_card(grid: List[List[int | str]]) -> str:
    rows = []
    for r in grid:
        rows.append(",".join(str(x) for x in r))
    return ";".join(rows)

def deserialize_card(serialized: str) -> List[List[int | str]]:
    rows = serialized.split(";")
    grid = []
    for r in rows:
        vals = []
        for v in r.split(","):
            vals.append("FREE" if v == "FREE" else int(v))
        grid.append(vals)
    return grid

def short_id(serial: str, length: int = 8) -> str:
    """Generate a short printable ID from the full serial."""
    h = hashlib.sha256(serial.encode()).hexdigest()
    return h[:length].upper()
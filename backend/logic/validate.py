from typing import Dict, Any, Tuple
from .modes import is_win

def validate_card(game: Dict[str, Any], card: Dict[str, Any]) -> Tuple[bool, Dict]:
    mode = game["mode"]
    stage = game["stage"]
    drawn = game["drawn"]
    grid = card["grid"]
    valid, details = is_win(mode, stage, grid, drawn)
    return valid, details

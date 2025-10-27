from typing import List, Tuple

def rows_completed(grid: List[List[int | str]], drawn: List[int]) -> int:
    completed = 0
    for row in grid:
        if all((x == "FREE") or (x in drawn) for x in row):
            completed += 1
    return completed

def four_corners(grid: List[List[int | str]], drawn: List[int]) -> bool:
    corners = [grid[0][0], grid[0][4], grid[4][0], grid[4][4]]
    return all((c == "FREE") or (c in drawn) for c in corners)

def diagonals(grid: List[List[int | str]], drawn: List[int]) -> bool:
    d1 = all((grid[i][i] == "FREE") or (grid[i][i] in drawn) for i in range(5))
    d2 = all((grid[i][4 - i] == "FREE") or (grid[i][4 - i] in drawn) for i in range(5))
    return d1 or d2

def full_house(grid: List[List[int | str]], drawn: List[int]) -> bool:
    return rows_completed(grid, drawn) == 5

def is_win(mode: str, stage: int, grid: List[List[int | str]], drawn: List[int]) -> Tuple[bool, dict]:
    if mode == "progressive_rows":
        rc = rows_completed(grid, drawn)
        return (rc >= stage, {"rows_completed": rc, "required_rows": stage})
    if mode == "full_house":
        return (full_house(grid, drawn), {"required": "full_house"})
    if mode == "four_corners":
        return (four_corners(grid, drawn), {"required": "four_corners"})
    if mode == "diagonals":
        return (diagonals(grid, drawn), {"required": "diagonals"})
    return (False, {"required": mode})

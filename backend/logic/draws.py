import secrets
from typing import List

class DrawEngine:
    def __init__(self, max_number: int = 75):
        self.max_number = max_number
        self.remaining = list(range(1, max_number + 1))
        for i in range(len(self.remaining) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.remaining[i], self.remaining[j] = self.remaining[j], self.remaining[i]
        self.drawn: List[int] = []

    def draw(self) -> int | None:
        if not self.remaining:
            return None
        num = self.remaining.pop()
        self.drawn.append(num)
        return num

from dataclasses import dataclass
from typing import Generic, Sized, TypeVar

T = TypeVar("T")


def saturating_add(i: int, a: int, max: int) -> int:
    if (sum := i + a) > max:
        return max
    return sum


def saturating_sub(i: int, s: int, min: int) -> int:
    if (sum := i - s) < min:
        return min
    return sum


def max_index(l: Sized) -> int:
    return len(l) - 1


@dataclass
class Select(Generic[T]):
    item: T
    selected: bool = False

    def toggle(self):
        self.selected = not self.selected

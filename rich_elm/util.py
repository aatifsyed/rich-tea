from typing import List, Sized


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

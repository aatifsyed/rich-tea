from dataclasses import dataclass
from queue import Queue
from signal import SIGWINCH
from typing import Generic, Iterable, List, Optional, Set, TypeVar, Union

from fuzzywuzzy.fuzz import ratio  # type: ignore
from prompt_toolkit.key_binding import KeyPress
from prompt_toolkit.keys import Keys
from returns.result import safe
from rich.color import Color
from rich.console import (
    Console,
    ConsoleOptions,
    ConsoleRenderable,
    OverflowMethod,
    RenderResult,
    RichCast,
)
from rich.style import Style
from rich.table import Table, box
from rich.text import Text
from rich_elm import events
from rich_elm.events import Signal
from more_itertools import mark_ends
import logging

logger = logging.getLogger(__name__)


T = TypeVar("T")


def saturating_add(i: int, a: int, max: int) -> int:
    if (sum := i + a) > max:
        return max
    return sum


def saturating_sub(i: int, s: int, min: int) -> int:
    if (sum := i - s) < min:
        return min
    return sum


def ellipsify_end(s: str, max_width: int) -> str:
    if len(s) > max_width:
        s = s[: max_width - 3]
        return f"{s}..."
    else:
        return s


def ellipsify_start(s: str, max_width: int) -> str:
    if len(s) > max_width:
        s = s[-max_width + 3 :]
        return f"...{s}"
    else:
        return s


@dataclass
class Select(Generic[T]):
    inner: T
    selected: bool = False


@dataclass
class ListView:
    candidates: List[Select[str]]
    cursor: int = 0
    """Tracks the currently selected item in the viewport, in the list"""
    offset: int = 0
    """The offset of the cursor from the top of the viewport"""

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        logger.info(self)
        # cursor=0, offset=0
        # >
        # ...

        # cursor=1, offset=1
        # .
        # >
        # ...

        # cursor=N, offset=N
        # ...
        # >

        # cursor=N, offset=N-1
        # ...
        # >
        # .

        candidates = self.candidates[self.cursor :]
        start = self.cursor - self.offset
        candidates = candidates[start : options.max_height]
        for i, candidate in enumerate(candidates):
            if i == self.offset:
                yield Text(
                    text=ellipsify_start(candidate.inner, options.max_width),
                    style=Style(bgcolor="white", color="black"),
                )
            else:
                yield Text(text=ellipsify_end(candidate.inner, options.max_width))


@safe(exceptions=(KeyboardInterrupt,))  # type: ignore
def list_viewer_safe(candidates: Iterable[str]) -> str:
    queue: "Queue[KeyPress | Signal]" = Queue()
    with Console(stderr=True).screen() as ctx, events.for_signals(
        SIGWINCH, queue=queue
    ), events.for_stdin(queue=queue):
        console: Console = ctx.console
        state = ListView(candidates=[Select(c) for c in candidates])

        console.update_screen(state)  # Initial display

        while event := queue.get():
            if isinstance(event, Signal):
                console.update_screen(state)  # Redraw on resize
            elif isinstance(event.key, Keys):
                if event.key == Keys.Up:
                    state.cursor = saturating_sub(state.cursor, 1, 0)
                elif event.key == Keys.Down:
                    state.cursor = saturating_add(
                        state.cursor, 1, len(state.candidates)
                    )
                else:
                    raise NotImplementedError(event)
                console.update_screen(state)


def list_viewer(candidates: Iterable[str]) -> Optional[str]:
    return list_viewer_safe(candidates).value_or(None)


if __name__ == "__main__":
    from logging import FileHandler

    logger.addHandler(FileHandler("list-view.log", mode="w"))
    logger.setLevel(logging.DEBUG)
    print(
        list_viewer(
            [
                "The Zen of Python, by Tim Peters",
                "Beautiful is better than ugly.",
                "Explicit is better than implicit.",
                "Simple is better than complex.",
                "Complex is better than complicated.",
                "Flat is better than nested.",
                "Sparse is better than dense.",
                "Readability counts.",
                "Special cases aren't special enough to break the rules.",
                "Although practicality beats purity.",
                "Errors should never pass silently.",
                "Unless explicitly silenced.",
                "In the face of ambiguity, refuse the temptation to guess.",
                "There should be one-- and preferably only one --obvious way to do it.",
                "Although that way may not be obvious at first unless you're Dutch.",
                "Now is better than never.",
                "Although never is often better than *right* now.",
                "If the implementation is hard to explain, it's a bad idea.",
                "If the implementation is easy to explain, it may be a good idea.",
                "Namespaces are one honking great idea -- let's do more of those!",
            ]
        )
    )

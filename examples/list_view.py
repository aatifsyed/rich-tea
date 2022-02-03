import logging
from dataclasses import dataclass
from itertools import islice
from queue import Queue
from signal import SIGWINCH
from typing import Generic, Iterable, List, Optional, TypeVar

from prompt_toolkit.key_binding import KeyPress
from prompt_toolkit.keys import Keys
from returns.result import safe
from rich.console import (
    Console,
    ConsoleOptions,
    RenderResult,
)
from rich.style import Style
from rich.text import Text
from rich_elm import events
from rich_elm.events import Signal

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


def max_index(l: List):
    return len(l) - 1


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

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        logger.info(f"{len(self.candidates)=}, {self.cursor=}")

        if self.cursor >= options.max_height:
            # v O ...
            # v O ...
            # v O ... max_height = 3
            #   O ...
            #   X ... cursor = 4
            start = (self.cursor - options.max_height) + 1
        else:
            start = 0

        for i, candidate in islice(
            enumerate(self.candidates), start, len(self.candidates)
        ):
            if i == self.cursor:
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
                        state.cursor, 1, max_index(state.candidates)
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

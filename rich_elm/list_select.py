import logging
from dataclasses import dataclass
from itertools import islice
from queue import Queue
from signal import SIGWINCH
from typing import Generic, Iterable, List, Optional, Set, TypeVar

from more_itertools import mark_ends
from prompt_toolkit.key_binding import KeyPress
from prompt_toolkit.keys import Keys
from returns.result import safe
from rich.console import Console, ConsoleOptions, RenderResult, ConsoleRenderable
from rich.style import Style
from rich.table import Column, Table

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


@dataclass
class Select(Generic[T]):
    item: T
    selected: bool = False

    def toggle(self):
        self.selected = not self.selected


@dataclass
class Cursor(Generic[T]):
    items: List[T]
    cursor: int = 0

    @classmethod
    def from_iterable(cls, i: Iterable[T]) -> "Cursor":
        return Cursor(items=list(i))

    def bump_up(self):
        self.cursor = saturating_sub(self.cursor, 1, 0)

    def bump_down(self):
        self.cursor = saturating_add(self.cursor, 1, max_index(self.items))

    def jump_to_top(self):
        self.cursor = 0

    def jump_to_bottom(self):
        self.cursor = max_index(self.items)

    def current(self) -> T:
        return self.items[self.cursor]


def scrollbar_character(
    is_first: bool, is_last: bool, index: int, max_index: int
) -> str:
    if is_first and not is_last:
        if index == 0:
            scrollbar = "■"
        else:
            scrollbar = "▲"
    elif is_first and is_last:
        scrollbar = "■"
    elif is_last:
        if index == max_index:
            scrollbar = "■"
        else:
            scrollbar = "▼"
    else:
        scrollbar = "|"
    return scrollbar


@dataclass
class ListRender(ConsoleRenderable):
    data: Cursor[str]

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        table = Table(
            *(
                Column(header=name, no_wrap=True, min_width=1)
                for name in ["scrollbar", "text"]
            ),
            box=None,
            show_header=False,
        )

        if self.data.cursor >= options.max_height:
            start = (self.data.cursor - options.max_height) + 1
        else:
            start = 0

        for is_first, is_last, (i, s) in mark_ends(
            islice(enumerate(self.data.items), start, start + options.max_height)
        ):
            scrollbar = scrollbar_character(
                is_first, is_last, i, max_index(self.data.items)
            )

            if i == self.data.cursor:
                style = Style(bgcolor="white", color="black")
            else:
                style = None

            table.add_row(scrollbar, s, style=style)

        return table.__rich_console__(console, options)


@dataclass
class ListSelectRender(ConsoleRenderable):
    data: Cursor[Select[str]]

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        logger.info(f"{len(self.data.items)=}, {self.data.cursor=}")
        table = Table(
            *(
                Column(header=name, no_wrap=True, min_width=1)
                for name in ["scrollbar", "toggle", "text"]
            ),
            box=None,
            show_header=False,
        )

        if self.data.cursor >= options.max_height:
            # v O ...
            # v O ...
            # v O ... max_height = 3
            #   O ...
            #   X ... cursor = 4
            start = (self.data.cursor - options.max_height) + 1
        else:
            start = 0

        for is_first, is_last, (i, candidate) in mark_ends(
            islice(enumerate(self.data.items), start, start + options.max_height)
        ):
            scrollbar = scrollbar_character(
                is_first, is_last, i, max_index(self.data.items)
            )

            if candidate.selected:
                toggled = "+"
            else:
                toggled = " "

            if i == self.data.cursor:
                style = Style(bgcolor="white", color="black")
            else:
                style = None

            table.add_row(scrollbar, toggled, candidate.item, style=style)

        return table.__rich_console__(console, options)


if __name__ == "__main__":
    from logging import FileHandler

    logger.addHandler(FileHandler("list-view.log", mode="w"))
    logger.setLevel(logging.DEBUG)

    @safe(exceptions=(KeyboardInterrupt,))  # type: ignore
    def list_viewer_safe(candidates: Iterable[str]) -> Set[str]:
        queue: "Queue[KeyPress | Signal]" = Queue()
        with Console(stderr=True).screen() as ctx, events.for_signals(
            SIGWINCH, queue=queue
        ), events.for_stdin(queue=queue):
            console: Console = ctx.console
            state: Cursor[Select[str]] = Cursor.from_iterable(
                Select(c) for c in candidates
            )

            console.update_screen(ListSelectRender(state))  # Initial display

            while event := queue.get():
                if isinstance(event, Signal):
                    console.update_screen(ListSelectRender(state))  # Redraw on resize
                elif isinstance(event.key, Keys):
                    if event.key == Keys.Up or event.key == Keys.Left:
                        state.bump_up()
                    elif event.key == Keys.Down or event.key == Keys.Right:
                        state.bump_down()
                    elif event.key == Keys.Tab:
                        state.items[state.cursor].toggle()
                    elif event.key == Keys.Home:
                        state.jump_to_top()
                    elif event.key == Keys.End:
                        state.jump_to_bottom()
                    elif event.key == Keys.Enter:
                        return set(
                            candidate.item
                            for candidate in state.items
                            if candidate.selected
                        )
                    else:
                        raise NotImplementedError(event)
                    console.update_screen(ListSelectRender(state))
                elif isinstance(event.key, str):
                    if event.key == "q":
                        return set(
                            candidate.item
                            for candidate in state.items
                            if candidate.selected
                        )

    def list_viewer(candidates: Iterable[str]) -> Optional[Set[str]]:
        return list_viewer_safe(candidates).value_or(None)

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

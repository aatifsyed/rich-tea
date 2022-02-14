from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from queue import Queue
from signal import SIGWINCH
from typing import List, Optional

from prompt_toolkit.key_binding import KeyPress
from prompt_toolkit.keys import Keys
from returns.result import safe
from rich.console import Console, ConsoleOptions, ConsoleRenderable, RenderResult
from rich.style import Style
from rich.text import Span, Text

from rich_tea import events
from rich_tea.events import Signal
from rich_tea.util import saturating_add, saturating_sub

logger = logging.getLogger(__name__)


@dataclass
class TextCursor:
    text: str
    cursor: int

    @classmethod
    def empty(cls) -> TextCursor:
        return TextCursor(text="", cursor=0)

    def bump_left(self):
        self.cursor = saturating_sub(self.cursor, 1, 0)

    def bump_right(self):
        self.cursor = saturating_add(self.cursor, 1, len(self.text))

    def jump_to_left(self):
        self.cursor = 0

    def jump_to_right(self):
        self.cursor = len(self.text)

    @property
    def before_cursor(self) -> str:
        """Excluding cursor"""
        return self.text[: self.cursor]

    @property
    def after_cursor(self) -> str:
        """Including cursor"""
        return self.text[self.cursor :]

    def insert(self, char: str):
        if len(char) != 1:
            raise RuntimeError(f"{char} must have length 1")
        self.text = f"{self.before_cursor}{char}{self.after_cursor}"
        self.cursor += 1

    def remove_left(self):
        self.text = f"{self.before_cursor[:-1]}{self.after_cursor}"
        self.cursor = saturating_sub(self.cursor, 1, 0)

    def remove_right(self):
        self.text = f"{self.before_cursor}{self.after_cursor[1:]}"

    @property
    def word_boundaries(self) -> List[int]:
        matches: List[re.Match] = re.finditer(r"\b", self.text)
        return [match.span()[0] for match in matches]

    def bump_left_by_word(self):
        self.cursor = next(
            filter(lambda i: i < self.cursor, reversed(self.word_boundaries)),
            self.cursor,
        )

    def bump_right_by_word(self):
        self.cursor = next(
            filter(lambda i: i > self.cursor, self.word_boundaries), self.cursor
        )

    def remove_left_word(self):
        cached_after = self.after_cursor
        self.bump_left_by_word()
        self.text = f"{self.before_cursor}{cached_after}"


@dataclass
class TextCursorRender(ConsoleRenderable):
    data: TextCursor

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        yield Text(
            text=f"{self.data.text} ",
            spans=[
                Span(
                    start=self.data.cursor,
                    end=self.data.cursor + 1,
                    style=Style(reverse=True),
                )
            ],
        )


if __name__ == "__main__":
    from logging import FileHandler

    logger.addHandler(FileHandler("text-box.log", mode="w"))
    logger.setLevel(logging.DEBUG)

    @safe(exceptions=(KeyboardInterrupt,))  # type: ignore
    def text_cursor_safe() -> str:
        queue: "Queue[KeyPress | Signal]" = Queue()
        with Console(stderr=True).screen() as ctx, events.for_signals(
            SIGWINCH, queue=queue
        ), events.for_stdin(queue=queue):
            console: Console = ctx.console
            state = TextCursor.empty()

            console.update_screen(TextCursorRender(state))  # Initial display

            while event := queue.get():
                logger.debug(event)
                if isinstance(event, Signal):
                    console.update_screen(TextCursorRender(state))  # Redraw on resize
                elif isinstance(event.key, Keys):
                    if event.key == Keys.Left:
                        state.bump_left()
                    elif event.key == Keys.Right:
                        state.bump_right()
                    elif event.key == Keys.ControlA:
                        state.jump_to_left()
                    elif event.key == Keys.ControlE:
                        state.jump_to_right()
                    elif event.key == Keys.ControlU:
                        state = state.empty()
                    elif event.key == Keys.Enter:
                        return state.text
                    elif event.key == Keys.Backspace:
                        state.remove_left()
                    elif event.key == Keys.Delete:
                        state.remove_right()
                    elif event.key == Keys.ControlW:  # ControlBackspace
                        state.remove_left_word()
                    elif event.key == Keys.ControlLeft:
                        state.bump_left_by_word()
                    elif event.key == Keys.ControlRight:
                        state.bump_right_by_word()
                    else:
                        raise NotImplementedError(event)
                    console.update_screen(TextCursorRender(state))
                elif isinstance(event.key, str):
                    state.insert(event.key)
                    console.update_screen(TextCursorRender(state))

    def text_cursor() -> Optional[str]:
        return text_cursor_safe().value_or(None)

    print(text_cursor())

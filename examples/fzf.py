import logging
from dataclasses import dataclass, field
from logging import FileHandler, Formatter
from queue import Queue
from signal import Signals
from typing import List, Union

from fuzzywuzzy.fuzz import ratio  # type: ignore
from lorem_text.lorem import words  # type: ignore
from prompt_toolkit.key_binding import KeyPress
from prompt_toolkit.keys import Keys
from rich.console import Console, ConsoleRenderable, RichCast
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich_elm import events

logger = logging.getLogger(__name__)


@dataclass
class FuzzyFinder(RichCast):
    haystack: List[str] = field(default_factory=list)
    needle: str = ""

    def __rich__(self) -> Union[ConsoleRenderable, str]:
        layout = Layout()

        table = Table(show_header=False, header_style="none")
        for candidate in sorted(
            self.haystack,
            key=lambda candidate: ratio(candidate, self.needle),
            reverse=True,
        ):
            table.add_row(candidate)

        search_box = Layout(
            renderable=Panel(Text(text=self.needle, style="red")),
            size=3,
        )

        layout.split_column(table, search_box)
        return layout

    @property
    def best_match(self) -> str:
        return sorted(
            self.haystack,
            key=lambda candidate: ratio(candidate, self.needle),
        ).pop()


queue = Queue()

logger.setLevel("INFO")
logger.addHandler(file_handler := FileHandler("fzf.eventlog"))
file_handler.setFormatter(Formatter("%(asctime)s - %(message)s", datefmt="%H:%M:%S"))

with Console(stderr=True).screen() as ctx, events.for_stdin(
    queue=queue
), events.for_signals(Signals.SIGWINCH, queue=queue):
    console: Console = ctx.console
    state = FuzzyFinder(haystack=[words(1) for _ in range(100)])
    console.update_screen(state)

    while event := queue.get():
        logger.info(event)

        if isinstance(event, KeyPress):
            if not isinstance(event.key, Keys):  # Just a str
                state.needle += event.key
            elif event.key == Keys.ControlD:
                break
            elif event.key == Keys.Enter:
                break
            elif event.key == Keys.Backspace:
                state.needle = state.needle[:-1]
            elif event.key == Keys.ControlU:
                state.needle = ""

        console.update_screen(state)
print(state.best_match)

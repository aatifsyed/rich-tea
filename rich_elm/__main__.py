from dataclasses import dataclass, field
from typing import Any, Generator, List, Union

from fuzzywuzzy.fuzz import ratio  # type: ignore
from lorem_text.lorem import sentence  # type: ignore
from prompt_toolkit.input.vt100_parser import Vt100Parser
from prompt_toolkit.key_binding import KeyPress
from prompt_toolkit.keys import Keys
from rich.console import Console, ConsoleRenderable, RichCast
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from . import events


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


with Console(stderr=True).screen() as ctx, events.for_stdin() as key_presses:
    console: Console = ctx.console
    state = FuzzyFinder(haystack=[sentence() for _ in range(100)])
    console.update_screen(state)

    while key_press := key_presses.get():
        print(key_press)
        if key_press.data == "\r":
            break

        console.update_screen(state)

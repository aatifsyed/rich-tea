from dataclasses import dataclass, field
from signal import Signals
from typing import List, Union

from fuzzywuzzy.fuzz import ratio  # type: ignore
from lorem_text.lorem import sentence  # type: ignore
from rich.console import Console, ConsoleRenderable, RichCast
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich_elm import events
from returns.result import safe


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


with Console(
    stderr=True
).screen() as ctx, events.for_stdin() as key_presses, events.for_signals(
    Signals.SIGWINCH
) as received_signals:
    console: Console = ctx.console
    state = FuzzyFinder(haystack=[sentence() for _ in range(100)])
    console.update_screen(state)

    while event := safe(key_presses.get_nowait)().alt():
        print(event)

        console.update_screen(state)

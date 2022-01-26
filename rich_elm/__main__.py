import os
import selectors
import sys
import termios
import tty
from contextlib import closing, contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue
from threading import Condition, Thread
from time import sleep
from typing import Any, Generator, List, Union

from fuzzywuzzy.fuzz import ratio
from lorem_text.lorem import sentence
from rich.console import Console, ConsoleRenderable, RichCast
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text


@contextmanager
def stdin_events() -> Generator["Queue[bytes]", None, None]:
    queue: "Queue[bytes]" = Queue()
    die = False
    fileno = sys.stdin.fileno()
    selector = selectors.DefaultSelector()
    selector.register(fileno, selectors.EVENT_READ)

    def enqueue():
        while not die:
            for selector_key, mask in selector.select(timeout=0.002):
                if mask | selectors.EVENT_READ:
                    queue.put(os.read(fileno, 1))

    event_thread = Thread(target=enqueue, name="event_thread")
    event_thread.start()

    old = termios.tcgetattr(fileno)
    new = deepcopy(old)

    # Reference: https://smlfamily.github.io/Basis/posix-tty.html
    # Copied from Textualize https://github.com/Textualize/textual/blob/6f7981/src/textual/_linux_driver.py#L100

    # Local control modes
    new[tty.LFLAG] &= ~(  # Turn off the following...
        0
        | termios.ECHO  # Show the user what they're typing in. Without this, the screen will flicker
        | termios.ICANON  # Canonical mode. Without this, vmin is ignored, and nothing works
        | termios.IEXTEN  # Extended functionality
        # | termios.ISIG  # Mapping input characters to signals. Without this, ^C will raise a KeyboardInterrupt
    )

    # Input control
    new[tty.IFLAG] &= ~(  # Turn off the following...
        0
        | termios.IXON  # Output control
        | termios.IXOFF  # Input control
        | termios.ICRNL  # Mapping CR to NL on input
        | termios.INLCR  # Mapping NL to CR on input
        | termios.IGNCR  # Ignore CR
    )

    # The number of characters read at a time in non-canonical mode
    new[tty.CC][termios.VMIN] = 1

    termios.tcsetattr(fileno, termios.TCSANOW, new)

    try:
        with closing(selector):
            yield queue
            die = True  # Tell the thread to die
            event_thread.join()  # Join it, avoiding a read from an invalid file descriptor
    finally:
        # Reset the terminal's settings
        termios.tcsetattr(fileno, termios.TCSANOW, old)


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


with Console().screen() as ctx, stdin_events() as events:
    console: Console = ctx.console
    state = FuzzyFinder(haystack=[sentence() for _ in range(100)])
    console.update_screen(state)

    while event := events.get():
        s = event.decode("utf-8", errors="strict")
        if s == "q":
            break
        else:
            state.needle += s

        console.update_screen(state)

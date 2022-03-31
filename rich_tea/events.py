from datetime import datetime, timedelta
import os
import selectors
import signal
import sys
import termios
import tty
from contextlib import closing, contextmanager
from copy import deepcopy
from dataclasses import dataclass
from queue import Queue
from signal import Signals
from threading import Thread
from types import FrameType
from typing import Generator, Optional
from prompt_toolkit.key_binding import KeyPress
from prompt_toolkit.keys import Keys
from prompt_toolkit.input.vt100_parser import Vt100Parser
from rich.console import Console


@contextmanager
def for_stdin(*, queue: Queue) -> Generator[None, None, None]:
    die = False
    fileno = sys.stdin.fileno()
    selector = selectors.DefaultSelector()
    selector.register(fileno, selectors.EVENT_READ)
    parser = Vt100Parser(feed_key_callback=lambda key_press: queue.put(key_press))

    def parse():
        while not die:
            try:
                for selector_key, mask in selector.select(timeout=0.002):
                    if mask | selectors.EVENT_READ:
                        parser.feed(os.read(fileno, 1).decode("utf-8"))
            except ValueError as e:
                if e.args == ("I/O operation on closed epoll object",):
                    # Another thread has closed stdin
                    break
                else:
                    raise

    event_thread = Thread(target=parse, name="event_thread")
    event_thread.start()

    old = termios.tcgetattr(fileno)
    new = deepcopy(old)

    # Reference: https://smlfamily.github.io/Basis/posix-tty.html
    #            https://viewsourcecode.org/snaptoken/kilo/02.enteringRawMode.html
    # Copied from Prompt Toolkit: https://github.com/prompt-toolkit/python-prompt-toolkit/blob/e9eac2eb/prompt_toolkit/input/vt100.py#L216

    # Local control modes
    new[tty.LFLAG] &= ~(  # Turn off the following...
        0
        | termios.ECHO  # Show the user what they're typing in. Without this, the screen will flicker
        | termios.ICANON  # Canonical mode. In canonical mode, input is only fed in on newlines from the user
        | termios.IEXTEN  # Extended functionality. ^V will allow the next character to be sent literally
        # | termios.ISIG  # Mapping input characters to signals. Without this, ^C will raise a KeyboardInterrupt. Note this doesn't include SIGWINCH
    )

    # Input control
    new[tty.IFLAG] &= ~(  # Turn off the following...
        0
        | termios.IXON  # Have ^S stop data transmission to the program, and ^Q resume it
        | termios.IXOFF  # Input control
        | termios.ICRNL  # Mapping CR to NL on input
        | termios.INLCR  # Mapping NL to CR on input
        | termios.IGNCR  # Ignore CR
        | termios.BRKINT
        | termios.ICRNL
        | termios.INPCK
        | termios.ISTRIP  # Tradition
    )

    new[tty.OFLAG] &= ~(  # Turn off the following...
        0 | termios.OPOST  # Output processing. E.g mapping \n -> \r\n
    )

    # The number of characters read at a time in non-canonical mode
    new[tty.CC][termios.VMIN] = 1

    termios.tcsetattr(fileno, termios.TCSANOW, new)  # Apply the change immediately

    with closing(selector):
        try:
            yield

            # We've exited the parent context
            die = True  # Tell the thread to die
            event_thread.join()  # Join it, avoiding a read from an invalid file descriptor
        finally:
            # Reset the terminal's settings, after current input is flushed
            termios.tcsetattr(fileno, termios.TCSAFLUSH, old)


@dataclass
class Signal:
    signum: int


@contextmanager
def for_signals(*sig: Signals, queue: Queue) -> Generator[None, None, None]:
    def enqueue_signal(signum: int, frame: Optional[FrameType]):
        queue.put(Signal(signum))

    old_handlers = {s: signal.signal(s, enqueue_signal) for s in sig}
    try:
        yield
    finally:
        for s, old_handler in old_handlers.items():
            signal.signal(s, old_handler)


if __name__ == "__main__":
    queue: "Queue[KeyPress]" = Queue()
    with Console(stderr=True).screen() as ctx, for_stdin(queue=queue):
        console: Console = ctx.console
        while event := queue.get():
            console.log(event)

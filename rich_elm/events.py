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

from prompt_toolkit.input.vt100_parser import Vt100Parser


@contextmanager
def for_stdin(*, queue: Queue) -> Generator[None, None, None]:
    die = False
    fileno = sys.stdin.fileno()
    selector = selectors.DefaultSelector()
    selector.register(fileno, selectors.EVENT_READ)
    parser = Vt100Parser(feed_key_callback=lambda key_press: queue.put(key_press))

    def parse():
        while not die:
            for selector_key, mask in selector.select(timeout=0.002):
                if mask | selectors.EVENT_READ:
                    parser.feed(os.read(fileno, 1).decode("utf-8"))

    event_thread = Thread(target=parse, name="event_thread")
    event_thread.start()

    old = termios.tcgetattr(fileno)
    new = deepcopy(old)

    # Reference: https://smlfamily.github.io/Basis/posix-tty.html
    # Copied from Prompt Toolkit: https://github.com/prompt-toolkit/python-prompt-toolkit/blob/e9eac2eb/prompt_toolkit/input/vt100.py#L216

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

    with closing(selector):
        try:
            yield

            # We've exited the parent context
            die = True  # Tell the thread to die
            event_thread.join()  # Join it, avoiding a read from an invalid file descriptor
        finally:
            # Reset the terminal's settings
            termios.tcsetattr(fileno, termios.TCSANOW, old)


@dataclass
class Signal:
    signum: int


@contextmanager
def for_signals(*sig: Signals, queue=Queue) -> Generator[None, None, None]:
    def enqueue_signal(signum: int, frame: Optional[FrameType]):
        queue.put(Signal(signum))

    old_handlers = {s: signal.signal(s, enqueue_signal) for s in sig}
    try:
        yield
    finally:
        for s, old_handler in old_handlers.items():
            signal.signal(s, old_handler)

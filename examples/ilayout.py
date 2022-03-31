from queue import Queue
from signal import SIGINT, SIGWINCH

from prompt_toolkit.key_binding import KeyPress
from prompt_toolkit.keys import Keys
from rich.console import Console, ConsoleOptions, ConsoleRenderable, RenderResult
from rich.layout import Layout
from rich_tea.events import Signal
from rich_tea import events


def right(layout: Layout) -> Layout:
    if len(layout.children) == 0:
        return layout
    else:
        return right(layout.children[-1])


def left(layout: Layout) -> Layout:
    if len(layout.children) == 0:
        return layout
    else:
        return left(layout.children[0])


queue: "Queue[KeyPress | Signal]" = Queue()
with Console(stderr=True).screen() as ctx, events.for_signals(
    SIGWINCH, SIGINT, queue=queue
), events.for_stdin(queue=queue):
    console: Console = ctx.console
    state = Layout()

    console.update_screen(state)

    while event := queue.get():
        if isinstance(event, KeyPress):
            if event.key == Keys.Right:
                right(state).split_row(Layout(), Layout())
            elif event.key == Keys.Down:
                right(state).split_column(Layout(), Layout())
            elif event.key == Keys.Left:
                left(state).split_row(Layout(), Layout())
            elif event.key == Keys.Up:
                left(state).split_column(Layout(), Layout())
            elif event.key == "r" or event.key == " ":
                state = Layout()
            elif event.key == "q":
                break
        if isinstance(event, Signal):
            if event.signum == SIGINT:
                break

        console.update_screen(state)

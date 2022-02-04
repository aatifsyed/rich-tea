from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from signal import SIGWINCH
from typing import Optional

from prompt_toolkit.key_binding import KeyPress
from prompt_toolkit.keys import Keys
from returns.result import safe
from rich.console import Console, ConsoleOptions, ConsoleRenderable, RenderResult
from rich.layout import Layout
from rich.text import Text
from rich_elm import events
from rich_elm.events import Signal
from rich_elm.list_select import Cursor, ListRender


@dataclass
class IPathState:
    current_dir: Path
    listing: Cursor[str]


@dataclass
class PathRender(ConsoleRenderable):
    data: IPathState

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        layout = Layout()
        header = Layout(
            Text(text=f"{self.data.current_dir.as_posix()}"), ratio=0, minimum_size=1
        )
        select = Layout(ListRender(data=self.data.listing))
        layout.split_column(header, select)
        yield layout


@safe(exceptions=(KeyboardInterrupt,))  # type: ignore
def ipath_safe(start_dir: Path = Path.cwd()) -> Path:
    queue: "Queue[KeyPress | Signal]" = Queue()
    with Console(stderr=True).screen() as ctx, events.for_signals(
        SIGWINCH, queue=queue
    ), events.for_stdin(queue=queue):
        console: Console = ctx.console
        state = IPathState(
            current_dir=start_dir,
            listing=Cursor.from_iterable(
                str(d) for d in start_dir.iterdir() if d.is_dir()
            ),
        )

        console.update_screen(PathRender(state))  # Initial display

        while event := queue.get():
            if isinstance(event, Signal):
                console.update_screen(PathRender(state))  # Redraw on resize
            elif isinstance(event.key, Keys):  # Control character
                if event.key == Keys.Left:
                    state.current_dir = state.current_dir.parent
                    state.listing = Cursor.from_iterable(
                        str(d) for d in state.current_dir.iterdir() if d.is_dir()
                    )
                elif event.key == Keys.Right:
                    if len(state.listing.items) > 0:
                        state.current_dir = state.current_dir.joinpath(
                            state.listing.current()
                        )
                        state.listing = Cursor.from_iterable(
                            str(d) for d in state.current_dir.iterdir() if d.is_dir()
                        )
                elif event.key == Keys.Up:
                    state.listing.bump_up()
                elif event.key == Keys.Down:
                    state.listing.bump_down()
                elif event.key == Keys.Enter:
                    return state.current_dir
                elif event.key == Keys.Home:
                    state.listing.jump_to_top()
                elif event.key == Keys.End:
                    state.listing.jump_to_bottom()
                else:
                    raise NotImplementedError(event)
            else:
                raise NotImplementedError(event)
            console.update_screen(PathRender(state))


def ipath(start_dir: Path = Path.cwd()) -> Optional[Path]:
    return ipath_safe(start_dir).value_or(None)


if __name__ == "__main__":
    p = ipath()
    print(p)

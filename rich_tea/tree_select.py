from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue
from signal import SIGWINCH
from typing import Dict, Generic, Iterable, List, Optional, Set, TypeVar, Union

from more_itertools import one
from prompt_toolkit.key_binding import KeyPress
from prompt_toolkit.keys import Keys
from returns.result import safe
from rich.console import Console, ConsoleOptions, ConsoleRenderable, RenderResult
from rich.style import Style
from rich.text import Text
from rich.tree import Tree

from rich_tea import events
from rich_tea.events import Signal
from rich_tea.util import max_index, saturating_add, saturating_sub

logger = logging.getLogger(__name__)


T = TypeVar("T")


@dataclass
class TreeData(Generic[T]):
    item: T
    children: List[TreeData[T]]
    collapsed: bool = False

    @classmethod
    def leaf(cls, this: T) -> TreeData[T]:
        return TreeData(item=this, children=[])

    def toggle(self):
        self.collapsed = not self.collapsed


@dataclass
class TreeCursor:
    tree: TreeData[str]
    cursor: List[int] = field(default_factory=list)

    def at(self, cursor: List[int]) -> TreeData[str]:
        current = self.tree
        for index in cursor:
            current = current.children[index]
        return current

    @property
    def pointee_parent(self) -> Optional[TreeData[str]]:
        if len(self.cursor) == 0:
            return None
        else:
            return self.at(self.cursor[:-1])

    def bump_up(self):
        if self.pointee_parent is not None:
            self.cursor[-1] = saturating_sub(self.cursor[-1], 1, 0)

    def bump_down(self):
        if self.pointee_parent is not None:
            self.cursor[-1] = saturating_add(
                self.cursor[-1], 1, max_index(self.pointee_parent.children)
            )

    def bump_deeper(self):
        if len(self.at(self.cursor).children) >= 1:
            self.cursor.append(0)

    def bump_shallower(self):
        if len(self.cursor) > 1:
            self.cursor.pop()


@dataclass
class TreeRender(
    ConsoleRenderable,
):
    data: TreeCursor

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        def to_rich_tree(tree: TreeData[str]) -> Tree:
            rich_tree = Tree(
                label=Text(
                    text=f"{tree.item}..." if tree.collapsed else tree.item,
                ),
                expanded=not tree.collapsed,
                style=Style(underline=True if tree.collapsed else None),
            )
            for child in tree.children:
                rich_tree.add(to_rich_tree(tree=child))
            return rich_tree

        tree = to_rich_tree(self.data.tree)

        current = tree
        for index in self.data.cursor:
            current = current.children[index]
        text: Text = current.label
        text.style = Style(reverse=True)
        yield tree


if __name__ == "__main__":
    from logging import FileHandler

    logger.addHandler(FileHandler("tree-select.log", mode="w"))
    logger.setLevel(logging.DEBUG)

    @safe(exceptions=(KeyboardInterrupt,))  # type: ignore
    def tree_viewer_safe(tree: TreeData[str]) -> Set[str]:
        queue: "Queue[KeyPress | Signal]" = Queue()
        with Console(stderr=True).screen() as ctx, events.for_signals(
            SIGWINCH, queue=queue
        ), events.for_stdin(queue=queue):
            console: Console = ctx.console
            state = TreeCursor(tree=tree)

            console.update_screen(TreeRender(state))  # Initial display
            logger.debug(state)

            while event := queue.get():
                logger.debug(event)
                if isinstance(event, Signal):
                    console.update_screen(TreeRender(state))  # Redraw on resize
                elif isinstance(event.key, Keys):
                    if event.key == Keys.Down:
                        state.bump_down()
                    elif event.key == Keys.Up:
                        state.bump_up()
                    elif event.key == Keys.Left:
                        state.bump_shallower()
                    elif event.key == Keys.Right:
                        state.bump_deeper()
                    else:
                        raise NotImplementedError(event)
                    console.update_screen(TreeRender(state))
                elif isinstance(event.key, str):
                    if False:
                        pass
                    else:
                        raise NotImplementedError(event)
                logger.debug(state)

    def tree_viewer(tree: TreeData[str]) -> Optional[Set[str]]:
        return tree_viewer_safe(tree).value_or(None)

    print(
        tree_viewer(
            TreeData(
                item="The Zen of Python, by Tim Peters",
                children=[
                    TreeData(
                        item="Flat is better than nested.",
                        children=[
                            TreeData.leaf(c)
                            for c in [
                                "Beautiful is better than ugly.",
                                "Explicit is better than implicit.",
                                "Simple is better than complex.",
                                "Complex is better than complicated.",
                            ]
                        ],
                        collapsed=False,
                    ),
                    *[
                        TreeData.leaf(c)
                        for c in [
                            "Sparse is better than dense.",
                            "Readability counts.",
                            "Special cases aren't special enough to break the rules.",
                            "Although practicality beats purity.",
                            "In the face of ambiguity, refuse the temptation to guess.",
                            "There should be one-- and preferably only one --obvious way to do it.",
                            "Although that way may not be obvious at first unless you're Dutch.",
                            "Namespaces are one honking great idea -- let's do more of those!",
                        ]
                    ],
                    TreeData(
                        item="Errors should never pass silently.",
                        children=[TreeData.leaf("Unless explicitly silenced.")],
                    ),
                    TreeData(
                        item="Now is better than never.",
                        children=[
                            TreeData(
                                item="Although never is often better than *right* now.",
                                children=[
                                    TreeData.leaf(t)
                                    for t in [
                                        "If the implementation is hard to explain, it's a bad idea.",
                                        "If the implementation is easy to explain, it may be a good idea.",
                                    ]
                                ],
                            )
                        ],
                    ),
                ],
            )
        )
    )

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from signal import SIGWINCH
from typing import Dict, Generic, Iterable, List, Optional, Set, TypeVar, Union
from more_itertools import one

from prompt_toolkit.key_binding import KeyPress
from prompt_toolkit.keys import Keys
from returns.result import safe
from rich.console import Console, ConsoleOptions, ConsoleRenderable, RenderResult
from rich.text import Text
from rich.tree import Tree

from rich_tea import events
from rich_tea.events import Signal
from rich.style import Style

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
    cursor: List[str]

    @property
    def selected(self) -> str:
        current = self.tree
        for key in self.cursor:
            current = one(
                filter(
                    lambda child: child.item == key,
                    current.children,
                )
            )


@dataclass
class TreeRender(
    ConsoleRenderable,
):
    data: TreeCursor

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        def to_rich_tree(parent_location: List[str], tree: TreeData[str]) -> Tree:
            current_location = parent_location + [tree.item]
            rich_tree = Tree(
                label=Text(
                    text=f"{tree.item}..." if tree.collapsed else tree.item,
                    style=Style(reverse=True)
                    if current_location == self.data.cursor
                    else "",
                ),
                expanded=not tree.collapsed,
                style=Style(underline=True if tree.collapsed else None),
            )
            for child in tree.children:
                rich_tree.add(
                    to_rich_tree(parent_location=current_location, tree=child)
                )
            return rich_tree

        yield to_rich_tree(parent_location=[], tree=self.data.tree)


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
            state = TreeCursor(
                tree=tree,
                cursor=[tree.item],
            )

            console.update_screen(TreeRender(state))  # Initial display

            while event := queue.get():
                if isinstance(event, Signal):
                    console.update_screen(TreeRender(state))  # Redraw on resize
                elif isinstance(event.key, Keys):
                    if False:
                        pass
                    else:
                        raise NotImplementedError(event)
                    console.update_screen(TreeRender(state))
                elif isinstance(event.key, str):
                    if False:
                        pass
                    else:
                        raise NotImplementedError(event)

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
                        collapsed=True,
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

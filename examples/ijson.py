from dataclasses import dataclass, field
from typing import Any, Dict, List, Union

from rich.console import Console, ConsoleOptions, ConsoleRenderable, RenderResult
from rich.json import JSON

JSONType = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]
JSONPath = List[Union[str, int]]


@dataclass
class JSONCursor:
    data: JSONType
    cursor: JSONPath = field(default_factory=list)


class JSONCursorRender(ConsoleRenderable):
    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        return super().__rich_console__(console, options)


if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("json", type=argparse.FileType("r"))
    args = parser.parse_args()

    try:
        json_data: JSONType = json.load(args.json)
    except Exception as e:
        print(f"Couldn't load json from file: {type(e).__name__}: {e}")
        sys.exit(1)

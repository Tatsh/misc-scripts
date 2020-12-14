#!/usr/bin/env python
from typing import Any, Mapping
import sys

from typing_extensions import Final

from ..utils import json2yaml

__all__ = ('main', )

YD_ARGS: Final[Mapping[str, Any]] = dict(default_flow_style=False, indent=2)


def main() -> int:
    # argv mode
    if len(sys.argv) >= 2:
        for arg in sys.argv[1:]:
            try:
                with open(arg, 'r') as f:
                    print(json2yaml(f.read()))
            except FileNotFoundError:
                return 1
        return 0
    # stdin mode
    print('\n'.join(json2yaml(x) for x in sys.stdin.readlines()))
    return 0


if __name__ == '__main__':
    sys.exit(main())

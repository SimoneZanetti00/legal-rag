"""Command-line entry point:

    python -m src.cli ask "Quando è obbligatorio notificare un data breach al Garante?"

It runs the commands of src.provision_cli (build, build-anchors, link, lookup, search and
ask); see that module for their options and exit codes.
"""

from __future__ import annotations

import sys

from src import provision_cli


def main(argv: list[str] | None = None) -> int:
    return provision_cli.main(argv, prog="python -m src.cli")


if __name__ == "__main__":
    sys.exit(main())

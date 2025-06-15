"""
Logging utility for deckfs daemon.

- DEBUG: Only shown when DEBUG=1 environment variable is set
- INFO, WARN: General information
- ERROR: Print to STDERR
"""

import os
import sys
from typing import Any


def debug(message: str, *args: Any) -> None:
    if os.environ.get('DEBUG', '0') == '1':
        formatted_message = message % args if args else message
        print(formatted_message, file=sys.stdout)


def info(message: str, *args: Any) -> None:
    formatted_message = message % args if args else message
    print(formatted_message, file=sys.stdout)


def warn(message: str, *args: Any) -> None:
    formatted_message = message % args if args else message
    print(f"⚠️  {formatted_message}", file=sys.stdout)


def error(message: str, *args: Any) -> None:
    formatted_message = message % args if args else message
    print(f"❌  {formatted_message}", file=sys.stderr)
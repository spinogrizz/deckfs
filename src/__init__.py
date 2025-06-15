"""deckfs - control Stream Deck through filesystem."""

__version__ = "0.1.0"
__author__ = "Denis Gryzlov"
__email__ = "gryzlov@gmail.com"
__description__ = "Linux daemon for Stream Deck control without GUI through filesystem"

from .core.daemon import StreamDeckDaemon

__all__ = ["StreamDeckDaemon"]
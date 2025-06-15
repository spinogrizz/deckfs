"""Daemon runner for deckfs service."""

import sys
import argparse
from .core.daemon import StreamDeckDaemon
from .utils import logger
from .utils.config import CONFIG_DIR


def main():
    """Main entry point for daemon runner."""
    parser = argparse.ArgumentParser(
        description="deckfs daemon runner"
    )
    
    parser.add_argument(
        "--config-dir", 
        default=CONFIG_DIR,
        help="Path to configuration directory"
    )
    
    args = parser.parse_args()
    
    try:
        daemon = StreamDeckDaemon(config_dir=args.config_dir)
        daemon.run()
    except RuntimeError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received termination signal")
        sys.exit(0)


if __name__ == "__main__":
    main()
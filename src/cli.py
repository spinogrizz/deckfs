"""Command line interface for stream-deck-fs."""

import argparse
import sys
import os
from .core.daemon import StreamDeckDaemon


def create_config_structure():
    """Create basic configuration structure."""
    config_dir = os.path.expanduser("~/.local/streamdeck")
    
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
        print(f"Created configuration directory: {config_dir}")
    
    # Create example folders for first three buttons
    for i in range(1, 4):
        button_dir = os.path.join(config_dir, f"{i:02d}")
        if not os.path.exists(button_dir):
            os.makedirs(button_dir)
            print(f"Created folder for button {i}: {button_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="stream-deck-fs - manage Stream Deck through filesystem"
    )
    
    parser.add_argument(
        "--config-dir", 
        default=None,
        help="Path to configuration directory (default: ~/.local/streamdeck)"
    )
    
    parser.add_argument(
        "--init", 
        action="store_true",
        help="Create basic configuration structure"
    )
    
    parser.add_argument(
        "--version", 
        action="version",
        version="stream-deck-fs 0.1.0"
    )
    
    args = parser.parse_args()
    
    if args.init:
        create_config_structure()
        print("\nBasic structure created. Now you can:")
        print("1. Place images in folders (e.g.: ~/.local/streamdeck/01/image.png)")
        print("2. Create action scripts (e.g.: ~/.local/streamdeck/01/action.sh)")
        print("3. Run daemon: stream-deck-fs")
        return
    
    try:
        daemon = StreamDeckDaemon(config_dir=args.config_dir)
        daemon.run()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Received termination signal")
        sys.exit(0)


if __name__ == "__main__":
    main()
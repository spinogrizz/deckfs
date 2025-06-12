#!/usr/bin/env python3
"""Debug entry point."""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from cli import main

if __name__ == "__main__":
    main()
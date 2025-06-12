#!/usr/bin/env python3

"""
Launch Firefox browser.
"""

import subprocess
import sys

try:
    # Launch Firefox in background
    subprocess.Popen(['firefox'], 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL)
    print("Firefox launched")
    
except FileNotFoundError:
    print("Error: Firefox not found", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
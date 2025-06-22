#!/usr/bin/env python3

# Background script that triggers clock updates every minute

import time
import os

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    draw_script = os.path.join(script_dir, "draw.py")
    
    while True:
        time.sleep(60)
        
        # Touch the draw script to trigger a file change event
        # This will cause the daemon to detect the change and redraw the button
        os.utime(draw_script, None)

if __name__ == "__main__":
    main()
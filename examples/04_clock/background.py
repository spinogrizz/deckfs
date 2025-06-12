#!/usr/bin/env python3

# Update scripts that redraw the clock image every minute

import time
from update import draw_clock

def main():
    while True:
        draw_clock()
        time.sleep(60)

if __name__ == "__main__":
    main()
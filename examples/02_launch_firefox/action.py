#!/usr/bin/env python3

"""
Launch Firefox browser and focus window.
"""

import subprocess
import sys
import os

def focus_firefox():
    """Try to focus existing Firefox window or launch new instance."""
    try:
        # First try to focus existing Firefox window using dbus
        result = subprocess.run(['dbus-send', '--session', '--type=method_call',
                               '--dest=org.mozilla.firefox.ZGVmYXVsdA==',
                               '/org/mozilla/firefox/Remote',
                               'org.mozilla.firefox.focus'],
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Firefox window focused")
            return True
            
    except FileNotFoundError:
        pass
    
    # Try using GNOME's gdbus if available
    try:
        # Check if Firefox is running
        result = subprocess.run(['pgrep', 'firefox'], capture_output=True)
        
        if result.returncode == 0:
            # Firefox is running, try to activate it
            subprocess.run(['gdbus', 'call', '--session',
                          '--dest=org.gnome.Shell',
                          '--object-path=/org/gnome/Shell',
                          '--method=org.gnome.Shell.Eval',
                          "global.get_window_actors().filter(w => w.get_meta_window().get_wm_class() == 'firefox')[0]?.get_meta_window().activate(global.get_current_time())"])
            print("Firefox activated")
            return True
            
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    
    # Launch new Firefox instance
    try:
        subprocess.Popen(['firefox'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        print("Firefox launched")
        return True
        
    except FileNotFoundError:
        print("Error: Firefox not found", file=sys.stderr)
        return False

if __name__ == "__main__":
    try:
        if not focus_firefox():
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
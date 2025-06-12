"""Background and update script manager."""

import os
import subprocess
import threading
import time
from typing import Dict, Optional, Set
from collections import defaultdict

from .config import SUPPORTED_SCRIPTS


class ScriptManager:
    """Manager for background and update scripts."""
    
    def __init__(self, config_dir: str, device_manager=None):
        """Initialize script manager.
        
        Args:
            config_dir: Path to configuration directory
            device_manager: Device manager for image updates
        """
        self.config_dir = config_dir
        self.device_manager = device_manager
        self.background_processes: Dict[str, subprocess.Popen] = {}
        self.crash_counts: Dict[str, int] = defaultdict(int)
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.restart_limits = 5  # Max restarts before giving up
        self.restart_window = 300  # 5 minutes
        self.crash_timestamps: Dict[str, list] = defaultdict(list)
        
    def start(self):
        """Start script manager."""
        if self.running:
            return
            
        self.running = True
        print("Starting script manager...")
        
        # Execute update scripts for all buttons
        self._execute_update_scripts()
        
        # Start background scripts
        self._start_background_scripts()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitor_processes, daemon=True)
        self.monitor_thread.start()
        
        print("Script manager started")
        
    def stop(self):
        """Stop script manager."""
        if not self.running:
            return
            
        print("Stopping script manager...")
        self.running = False
        
        # Terminate all background processes
        for button_dir, process in self.background_processes.items():
            print(f"Terminating background script for {button_dir}")
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"Force killing background script for {button_dir}")
                process.kill()
                process.wait()
            except Exception as e:
                print(f"Error stopping background script for {button_dir}: {e}")
                
        self.background_processes.clear()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
            
        print("Script manager stopped")
        
    def execute_update_script(self, button_dir: str):
        """Execute update script for specific button.
        
        Args:
            button_dir: Button directory name (e.g., "01_toggle_mute")
        """
        folder_path = os.path.join(self.config_dir, button_dir)
        if not os.path.isdir(folder_path):
            return
            
        # Find and execute update script
        for ext, cmd in SUPPORTED_SCRIPTS.items():
            script_path = os.path.join(folder_path, f"update.{ext}")
            if os.path.isfile(script_path):
                print(f"Executing update script for {button_dir}")
                try:
                    result = subprocess.run(
                        cmd + [script_path], 
                        cwd=folder_path,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode != 0:
                        print(f"Update script for {button_dir} failed with code {result.returncode}")
                        if result.stderr:
                            print(f"Error output: {result.stderr}")
                    else:
                        print(f"Update script for {button_dir} completed successfully")
                        # Trigger image update after successful update script
                        self._trigger_image_update(button_dir)
                except subprocess.TimeoutExpired:
                    print(f"Update script for {button_dir} timed out")
                except Exception as e:
                    print(f"Error executing update script for {button_dir}: {e}")
                break
                
    def start_background_script(self, button_dir: str):
        """Start background script for specific button.
        
        Args:
            button_dir: Button directory name (e.g., "01_toggle_mute")
        """
        folder_path = os.path.join(self.config_dir, button_dir)
        if not os.path.isdir(folder_path):
            return
            
        # Stop existing process if any
        self.stop_background_script(button_dir)
        
        # Find and start background script
        for ext, cmd in SUPPORTED_SCRIPTS.items():
            script_path = os.path.join(folder_path, f"background.{ext}")
            if os.path.isfile(script_path):
                print(f"Starting background script for {button_dir}")
                try:
                    process = subprocess.Popen(
                        cmd + [script_path],
                        cwd=folder_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    self.background_processes[button_dir] = process
                    print(f"Background script for {button_dir} started with PID {process.pid}")
                except Exception as e:
                    print(f"Error starting background script for {button_dir}: {e}")
                break
                
    def stop_background_script(self, button_dir: str):
        """Stop background script for specific button.
        
        Args:
            button_dir: Button directory name
        """
        if button_dir in self.background_processes:
            process = self.background_processes[button_dir]
            print(f"Stopping background script for {button_dir}")
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"Force killing background script for {button_dir}")
                process.kill()
                process.wait()
            except Exception as e:
                print(f"Error stopping background script for {button_dir}: {e}")
            finally:
                del self.background_processes[button_dir]
                
    def restart_background_script(self, button_dir: str):
        """Restart background script with crash protection.
        
        Args:
            button_dir: Button directory name
        """
        current_time = time.time()
        
        # Clean old crash timestamps (outside restart window)
        self.crash_timestamps[button_dir] = [
            ts for ts in self.crash_timestamps[button_dir] 
            if current_time - ts < self.restart_window
        ]
        
        # Add current crash timestamp
        self.crash_timestamps[button_dir].append(current_time)
        
        # Check if we've exceeded restart limits
        if len(self.crash_timestamps[button_dir]) > self.restart_limits:
            print(f"Background script for {button_dir} crashed too many times "
                  f"({len(self.crash_timestamps[button_dir])} times in {self.restart_window}s). "
                  f"Giving up.")
            return
            
        print(f"Restarting background script for {button_dir} "
              f"(crash #{len(self.crash_timestamps[button_dir])})")
        
        # Wait a bit before restarting
        time.sleep(2)
        self.start_background_script(button_dir)
        
    def _execute_update_scripts(self):
        """Execute update scripts for all buttons."""
        if not os.path.isdir(self.config_dir):
            return
            
        for item in os.listdir(self.config_dir):
            item_path = os.path.join(self.config_dir, item)
            if os.path.isdir(item_path) and len(item) >= 2 and item[:2].isdigit():
                self.execute_update_script(item)
                
    def _start_background_scripts(self):
        """Start background scripts for all buttons."""
        if not os.path.isdir(self.config_dir):
            return
            
        for item in os.listdir(self.config_dir):
            item_path = os.path.join(self.config_dir, item)
            if os.path.isdir(item_path) and len(item) >= 2 and item[:2].isdigit():
                self.start_background_script(item)
                
    def _monitor_processes(self):
        """Monitor background processes for crashes."""
        while self.running:
            crashed_processes = []
            
            for button_dir, process in list(self.background_processes.items()):
                if process.poll() is not None:  # Process has terminated
                    exit_code = process.returncode
                    print(f"Background script for {button_dir} exited with code {exit_code}")
                    
                    # Capture any remaining output
                    try:
                        stdout, stderr = process.communicate(timeout=1)
                        if stdout:
                            print(f"stdout: {stdout}")
                        if stderr:
                            print(f"stderr: {stderr}")
                    except subprocess.TimeoutExpired:
                        pass
                    except Exception as e:
                        print(f"Error reading output from {button_dir}: {e}")
                    
                    crashed_processes.append(button_dir)
                    
            # Restart crashed processes
            for button_dir in crashed_processes:
                if button_dir in self.background_processes:
                    del self.background_processes[button_dir]
                self.restart_background_script(button_dir)
                
            time.sleep(1)  # Check every second
            
    def handle_script_change(self, button_dir: str, script_type: str):
        """Handle script file changes.
        
        Args:
            button_dir: Button directory name
            script_type: Type of script ('background' or 'update')
        """
        if script_type == 'background':
            print(f"Background script changed for {button_dir}, restarting...")
            self.stop_background_script(button_dir)
            # Reset crash count on manual restart
            self.crash_timestamps[button_dir] = []
            self.start_background_script(button_dir)
        elif script_type == 'update':
            print(f"Update script changed for {button_dir}, executing...")
            self.execute_update_script(button_dir)
            
    def _trigger_image_update(self, button_dir: str):
        """Trigger image update for button.
        
        Args:
            button_dir: Button directory name
        """
        if not self.device_manager:
            return
            
        # Extract button index from directory name
        try:
            if len(button_dir) >= 2 and button_dir[:2].isdigit():
                key_index = int(button_dir[:2]) - 1
                self.device_manager.update_key_image(key_index, button_dir)
            else:
                print(f"Cannot determine button index from directory: {button_dir}")
        except ValueError as e:
            print(f"Error parsing button index from {button_dir}: {e}")
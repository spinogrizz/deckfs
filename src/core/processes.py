"""Process manager for script lifecycle."""

import subprocess
import threading
import time
from typing import Dict, Optional, List
from collections import defaultdict

from ..utils.config import SUPPORTED_SCRIPTS


class ProcessManager:
    """Manages script processes with crash protection."""
    
    def __init__(self, working_dir: str):
        """Initialize process manager.
        
        Args:
            working_dir: Working directory for scripts
        """
        self.working_dir = working_dir
        self.processes: Dict[str, subprocess.Popen] = {}
        self.crash_timestamps: Dict[str, List[float]] = defaultdict(list)
        self.restart_limits = 5
        self.restart_window = 300  # 5 minutes
        self.lock = threading.RLock()
        
    def start_script(self, script_type: str, script_name: str) -> bool:
        """Start script of given type.
        
        Args:
            script_type: Type of script (action, update, background)
            script_name: Name of script file without extension
            
        Returns:
            bool: True if script started successfully
        """
        # Check if already running for background scripts
        if script_type == "background" and self.is_running(script_type):
            return True
            
        # Stop existing process
        self.stop_script(script_type)
        
        # Find script file
        script_path = self._find_script_file(script_name)
        if not script_path:
            return False
            
        # Get command for script extension
        ext = script_path.split('.')[-1]
        cmd = SUPPORTED_SCRIPTS.get(ext)
        if not cmd:
            print(f"Unsupported script type: {ext}")
            return False
            
        try:
            with self.lock:
                if script_type == "action":
                    # Action scripts run once and exit
                    process = subprocess.Popen(
                        cmd + [script_path],
                        cwd=self.working_dir
                    )
                elif script_type == "update":
                    # Update scripts run synchronously
                    result = subprocess.run(
                        cmd + [script_path],
                        cwd=self.working_dir,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    return result.returncode == 0
                elif script_type == "background":
                    # Background scripts run continuously
                    process = subprocess.Popen(
                        cmd + [script_path],
                        cwd=self.working_dir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    self.processes[script_type] = process
                    
            return True
            
        except Exception as e:
            print(f"Error starting {script_type} script {script_name}: {e}")
            return False
            
    def stop_script(self, script_type: str):
        """Stop script of given type.
        
        Args:
            script_type: Type of script to stop
        """
        with self.lock:
            if script_type in self.processes:
                process = self.processes[script_type]
                try:
                    if process.poll() is None:  # Still running
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                except Exception as e:
                    print(f"Error stopping {script_type} script: {e}")
                finally:
                    del self.processes[script_type]
                    
    def restart_script(self, script_type: str, script_name: str) -> bool:
        """Restart script with crash protection.
        
        Args:
            script_type: Type of script to restart
            script_name: Name of script file
            
        Returns:
            bool: True if restart allowed and successful
        """
        current_time = time.time()
        key = f"{script_type}:{script_name}"
        
        with self.lock:
            # Clean old crash timestamps
            self.crash_timestamps[key] = [
                ts for ts in self.crash_timestamps[key]
                if current_time - ts < self.restart_window
            ]
            
            # Add current crash
            self.crash_timestamps[key].append(current_time)
            
            # Check restart limits
            if len(self.crash_timestamps[key]) > self.restart_limits:
                print(f"Script {script_name} crashed too many times. Giving up.")
                return False
                
        # Wait before restart
        time.sleep(2)
        return self.start_script(script_type, script_name)
        
    def is_running(self, script_type: str) -> bool:
        """Check if script is running.
        
        Args:
            script_type: Type of script to check
            
        Returns:
            bool: True if script is running
        """
        with self.lock:
            if script_type not in self.processes:
                return False
            return self.processes[script_type].poll() is None
            
    def get_exit_code(self, script_type: str) -> Optional[int]:
        """Get exit code of script if terminated.
        
        Args:
            script_type: Type of script
            
        Returns:
            Optional[int]: Exit code or None if still running
        """
        with self.lock:
            if script_type not in self.processes:
                return None
            return self.processes[script_type].poll()
            
    def cleanup(self):
        """Stop all running processes."""
        with self.lock:
            for script_type in list(self.processes.keys()):
                self.stop_script(script_type)
                
    def _find_script_file(self, script_name: str) -> Optional[str]:
        """Find script file by name.
        
        Args:
            script_name: Name of script without extension
            
        Returns:
            Optional[str]: Full path to script file or None
        """
        import os
        
        for ext in SUPPORTED_SCRIPTS.keys():
            script_path = os.path.join(self.working_dir, f"{script_name}.{ext}")
            if os.path.isfile(script_path):
                return script_path
        return None
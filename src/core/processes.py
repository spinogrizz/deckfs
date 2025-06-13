"""Process manager for script lifecycle."""

import subprocess
import threading
import time
import os
import signal
from typing import Dict, Optional, List
from collections import defaultdict

from ..utils.config import SUPPORTED_SCRIPTS
from ..utils.file_utils import find_file
from ..utils import logger


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
        self.script_executors = {
            "action": self._execute_action,
            "update": self._execute_update,
            "background": self._execute_background
        }
        
        # Find config directory from working_dir (go up one level from button directory)
        self.config_dir = os.path.dirname(working_dir)
        
    def start_script(self, script_type: str) -> bool:
        """Start script of given type.
        
        Args:
            script_type: Type of script (action, update, background)
            
        Returns:
            bool: True if script started successfully
        """
        if script_type == "background" and self.is_running(script_type):
            return True
            
        self.stop_script(script_type)
        
        script_path = self._find_script_file(script_type)
        if not script_path:
            return False
            
        ext = script_path.split('.')[-1]
        cmd = SUPPORTED_SCRIPTS.get(ext)
        if not cmd:
            logger.error(f"Unsupported script type: {ext}")
            return False
            
        try:
            executor = self.script_executors.get(script_type)
            if not executor:
                logger.error(f"Unknown script type: {script_type}")
                return False
                
            return executor(cmd, script_path)
                
        except Exception as e:
            logger.error(f"Error starting {script_type} script {script_name}: {e}")
            return False
            
    def stop_script(self, script_type: str):
        """Stop script of given type and all child processes.
        
        Args:
            script_type: Type of script to stop
        """
        with self.lock:
            if script_type in self.processes:
                process = self.processes[script_type]
                try:
                    if process.poll() is None:  # Still running
                        try:
                            pgid = os.getpgid(process.pid)
                            logger.debug(f"Stopping {script_type} script (PID: {process.pid}, PGID: {pgid})")
                            
                            # Kill entire process group to catch child processes
                            try:
                                # First try SIGTERM to entire process group
                                os.killpg(pgid, signal.SIGTERM)
                                try:
                                    process.wait(timeout=5)
                                except subprocess.TimeoutExpired:
                                    # Force kill if processes don't terminate gracefully
                                    logger.warn(f"Force killing process group {pgid}")
                                    os.killpg(pgid, signal.SIGKILL)
                                    process.wait()
                            except ProcessLookupError:
                                # Process group already terminated
                                pass
                                
                        except OSError as e:
                            # Fallback to single process termination if process group operations fail
                            logger.warn(f"Process group termination failed: {e}, falling back to single process")
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait()
                                
                except Exception as e:
                    logger.error(f"Error stopping {script_type} script: {e}")
                finally:
                    del self.processes[script_type]
                    
    def restart_script(self, script_type: str) -> bool:
        """Restart script with crash protection.
        
        Args:
            script_type: Type of script to restart
            
        Returns:
            bool: True if restart allowed and successful
        """
        current_time = time.time()
        key = script_type
        
        with self.lock:
            # Sliding window crash protection: only count crashes within time window
            # Prevents infinite restart loops for fundamentally broken scripts
            self.crash_timestamps[key] = [
                ts for ts in self.crash_timestamps[key]
                if current_time - ts < self.restart_window
            ]
            
            self.crash_timestamps[key].append(current_time)
            
            if len(self.crash_timestamps[key]) > self.restart_limits:
                logger.warn(f"Script {script_type} crashed too many times. Giving up.")
                return False
                
        time.sleep(2)
        return self.start_script(script_type)
        
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
            
    def wait_for_action_completion(self) -> Optional[int]:
        """Wait for action script to complete and return exit code.
        
        Returns:
            Optional[int]: Exit code or None if no action process
        """
        with self.lock:
            if "action" not in self.processes:
                return None
                
            process = self.processes["action"]
            
        try:
            # Wait for process to complete with 10 second timeout
            exit_code = process.wait(timeout=10)
            return exit_code
        except subprocess.TimeoutExpired:
            # Action script is taking too long, kill it
            logger.warning("Action script timeout, killing process")
            try:
                pgid = os.getpgid(process.pid)
                os.killpg(pgid, signal.SIGTERM)
                exit_code = process.wait(timeout=2)
            except:
                exit_code = -1  # Force kill failed
            return exit_code
        except Exception as e:
            logger.error(f"Error waiting for action completion: {e}")
            return None
        finally:
            # Clean up process from tracking
            with self.lock:
                if "action" in self.processes:
                    del self.processes["action"]

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
            
            process = self.processes[script_type]
            exit_code = process.poll()
            if exit_code is not None:
                # Process terminated, remove from tracking
                del self.processes[script_type]
            return exit_code
            
    def cleanup(self):
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
        return find_file(self.working_dir, script_name, list(SUPPORTED_SCRIPTS.keys()))
        
    def _load_env_vars(self) -> Dict[str, str]:
        """Load environment variables from env.local file.
        
        Returns:
            Dict[str, str]: Environment variables as key-value pairs
        """
        env_vars = {}
        env_file_path = os.path.join(self.config_dir, "env.local")
        
        if not os.path.exists(env_file_path):
            return env_vars
            
        try:
            with open(env_file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                        
                    # Parse KEY=VALUE pairs
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Skip if key is empty
                        if not key:
                            logger.debug(f"Invalid line in env.local:{line_num}: {line}")
                            continue
                        
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                            
                        env_vars[key] = value
                    else:
                        logger.debug(f"Invalid line in env.local:{line_num}: {line}")
                        
        except Exception as e:
            logger.error(f"Error reading env.local file: {e}")
            
        return env_vars
        
    def _execute_action(self, cmd: List[str], script_path: str) -> bool:
        """Execute action script - run once and exit."""
        env = os.environ.copy()
        env.update(self._load_env_vars())
        
        # Execute action script synchronously with timeout to catch exit code
        try:
            process = subprocess.Popen(
                cmd + [script_path], 
                cwd=self.working_dir, 
                env=env,
                preexec_fn=os.setsid  # Create new session for child isolation
            )
            
            with self.lock:
                self.processes["action"] = process
                
            return True
            
        except Exception as e:
            logger.error(f"Error starting action script: {e}")
            return False
        
    def _execute_update(self, cmd: List[str], script_path: str) -> bool:
        """Execute update script - run synchronously."""
        # Synchronous execution: update scripts must complete before button starts
        # 30-second timeout prevents hanging on unresponsive scripts
        env = os.environ.copy()
        env.update(self._load_env_vars())
        result = subprocess.run(
            cmd + [script_path],
            cwd=self.working_dir,
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        return result.returncode == 0
        
    def _execute_background(self, cmd: List[str], script_path: str) -> bool:
        """Execute background script - run continuously."""
        # Store process handle for monitoring and lifecycle management
        with self.lock:
            env = os.environ.copy()
            env.update(self._load_env_vars())
            
            # Create new process group to isolate child processes
            process = subprocess.Popen(
                cmd + [script_path],
                cwd=self.working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                preexec_fn=os.setsid  # Create new session and process group
            )
            self.processes["background"] = process
            try:
                pgid = os.getpgid(process.pid)
                logger.debug(f"Started background script (PID: {process.pid}, PGID: {pgid})")
            except OSError:
                logger.debug(f"Started background script (PID: {process.pid})")
        return True
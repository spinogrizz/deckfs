"""Process manager for script lifecycle."""

import subprocess
import threading
import time
import os
import signal
from typing import Dict, Optional, List
from collections import defaultdict

from ..utils.config import SUPPORTED_SCRIPTS, get_config
from ..utils.file_utils import find_file
from ..utils import logger


class ProcessManager:
    """Manages script processes with crash protection."""
    
    def __init__(self, working_dir: str, on_script_completed=None):
        """Initialize process manager.
        
        Args:
            working_dir: Working directory for scripts
            on_script_completed: Callback when any script completes (called with script_type: str, exit_code: int)
        """
        self.working_dir = working_dir
        self.processes: Dict[str, subprocess.Popen] = {}
        self.lock = threading.RLock()
        
        # Unified callback
        self.on_script_completed = on_script_completed
        
        # Background monitoring
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitoring = False
        
    def start_script(self, script_name: str, sync: bool = False) -> bool:
        """Start script with specified execution mode.
        
        Args:
            script_name: Name of the script to start
            sync: If True, run synchronously and wait for completion.
                  If False, run asynchronously and track process.
            
        Returns:
            bool: True if script started/completed successfully
        """
        script_path = self._find_script_file(script_name)
        if not script_path:
            return False
            
        ext = script_path.split('.')[-1]
        cmd = SUPPORTED_SCRIPTS.get(ext)
        if not cmd:
            logger.error(f"Unsupported script extension: {ext}")
            return False
            
        return self._execute_script(cmd, script_path, script_name, sync=sync)
    
    def start_script_async(self, script_name: str) -> bool:
        """Start script asynchronously and track it."""
        return self.start_script(script_name, sync=False)
        
    def start_script_sync(self, script_name: str) -> bool:
        """Start script synchronously and wait for completion."""
        return self.start_script(script_name, sync=True)
            
    def stop_script(self, script_name: str):
        """Stop script and all child processes.
        
        Args:
            script_name: Name of script to stop
        """
        with self.lock:
            if script_name in self.processes:
                process = self.processes[script_name]
                try:
                    if process.poll() is None:  # Still running
                        try:
                            pgid = os.getpgid(process.pid)
                            logger.debug(f"Stopping {script_name} script (PID: {process.pid}, PGID: {pgid})")
                            
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
                    logger.error(f"Error stopping {script_name} script: {e}")
                finally:
                    del self.processes[script_name]
                    
        
    def is_running(self, script_name: str) -> bool:
        """Check if script is running.
        
        Args:
            script_name: Name of script to check
            
        Returns:
            bool: True if script is running
        """
        with self.lock:
            if script_name not in self.processes:
                return False
            return self.processes[script_name].poll() is None
            

            
    def start_monitoring(self):
        """Start background process monitoring."""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_all_processes, daemon=True)
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """Stop background process monitoring."""
        if not self.monitoring:
            return
            
        self.monitoring = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
    
    def cleanup(self):
        self.stop_monitoring()
        
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
        
        
    def _execute_script(self, cmd: List[str], script_path: str, script_name: str, sync: bool) -> bool:
        """Execute script with specified execution mode.
        
        Args:
            cmd: Command list to execute
            script_path: Path to script file
            script_name: Name of script for tracking
            sync: If True, run synchronously. If False, run asynchronously.
            
        Returns:
            bool: True if script started/completed successfully
        """
        env = os.environ.copy()
        config = get_config()
        if config is not None:
            env_vars = config.load_env_vars()
            env.update(env_vars)
        
        if sync:
            # Synchronous execution with 30-second timeout
            try:
                result = subprocess.run(
                    cmd + [script_path],
                    cwd=self.working_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env
                )
                logger.debug(f"Completed {script_name} script with exit code {result.returncode}")
                return result.returncode == 0
            except Exception as e:
                logger.error(f"Error executing {script_name} script: {e}")
                return False
        else:
            # Asynchronous execution - stop any existing script first
            self.stop_script(script_name)
            
            try:
                process = subprocess.Popen(
                    cmd + [script_path], 
                    cwd=self.working_dir, 
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    preexec_fn=os.setsid  # Create new session for child isolation
                )
                
                with self.lock:
                    self.processes[script_name] = process
                    
                logger.debug(f"Started {script_name} script (PID: {process.pid})")
                return True
                
            except Exception as e:
                logger.error(f"Error starting {script_name} script: {e}")
                return False
            
    def _monitor_all_processes(self):
        """Monitor all running processes and notify about completions.
        
        Universal monitoring loop that checks all active processes.
        """
        while self.monitoring:
            with self.lock:
                # Check all running processes for completion
                completed_processes = []
                for script_name, process in list(self.processes.items()):
                    exit_code = process.poll()
                    if exit_code is not None:
                        # Process completed
                        completed_processes.append((script_name, exit_code))
                        del self.processes[script_name]
                        
                # Notify about completed processes
                for script_name, exit_code in completed_processes:
                    if self.on_script_completed:
                        self.on_script_completed(script_name, exit_code)
                        
            # Use threading.Event().wait() instead of time.sleep() for better thread responsiveness
            threading.Event().wait(1)  # Check every second

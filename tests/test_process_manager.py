"""Tests for ProcessManager class."""

import os
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch, MagicMock

from src.core.processes import ProcessManager


class TestProcessManager(unittest.TestCase):
    """Test cases for ProcessManager."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.process_manager = ProcessManager(self.temp_dir)
        
    def tearDown(self):
        """Clean up test environment."""
        self.process_manager.cleanup()
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def _create_test_script(self, name: str, content: str):
        """Create a test script file."""
        script_path = os.path.join(self.temp_dir, name)
        with open(script_path, 'w') as f:
            f.write(content)
        os.chmod(script_path, 0o755)
        return script_path
        
        
    def test_find_script_file_python(self):
        """Test finding Python script files."""
        # Create test script
        script_path = self._create_test_script("action.py", "#!/usr/bin/env python3\nprint('test')")
        
        # Test finding the script
        found_path = self.process_manager._find_script_file("action")
        self.assertEqual(found_path, script_path)
        
    def test_find_script_file_bash(self):
        """Test finding bash script files."""
        script_path = self._create_test_script("action.sh", "#!/bin/bash\necho 'test'")
        
        found_path = self.process_manager._find_script_file("action")
        self.assertEqual(found_path, script_path)
        
        
    @patch('subprocess.run')
    def test_execute_update_script_success(self, mock_run):
        """Test successful update script execution."""
        # Setup mock
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Create test script
        self._create_test_script("update.py", "print('update')")
        
        # Test execution
        success = self.process_manager.start_script("update", "update")
        self.assertTrue(success)
        
        # Verify subprocess.run was called
        mock_run.assert_called_once()
        
    @patch('subprocess.run')
    def test_execute_update_script_failure(self, mock_run):
        """Test failed update script execution."""
        # Setup mock to return error
        mock_result = Mock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        
        # Create test script
        self._create_test_script("update.py", "exit(1)")
        
        # Test execution
        success = self.process_manager.start_script("update", "update")
        self.assertFalse(success)
        
    @patch('subprocess.Popen')
    def test_execute_action_script(self, mock_popen):
        """Test action script execution."""
        # Create test script
        self._create_test_script("action.sh", "echo 'action'")
        
        # Test execution
        success = self.process_manager.start_script("action", "action")
        self.assertTrue(success)
        
        # Verify Popen was called
        mock_popen.assert_called_once()
        
    @patch('subprocess.Popen')
    def test_execute_background_script(self, mock_popen):
        """Test background script execution."""
        # Setup mock process
        mock_process = Mock()
        mock_popen.return_value = mock_process
        
        # Create test script
        self._create_test_script("background.py", "while True: time.sleep(1)")
        
        # Test execution
        success = self.process_manager.start_script("background", "background")
        self.assertTrue(success)
        
        # Verify process is stored
        self.assertIn("background", self.process_manager.processes)
        self.assertEqual(self.process_manager.processes["background"], mock_process)
        
        
    @patch('subprocess.Popen')
    def test_is_running_true(self, mock_popen):
        """Test is_running returns True for running process."""
        # Setup mock process
        mock_process = Mock()
        mock_process.poll.return_value = None  # Still running
        mock_popen.return_value = mock_process
        
        # Create and start background script
        self._create_test_script("background.py", "import time; time.sleep(10)")
        self.process_manager.start_script("background", "background")
        
        # Test is_running
        self.assertTrue(self.process_manager.is_running("background"))
        
    @patch('subprocess.Popen')
    def test_is_running_false_terminated(self, mock_popen):
        """Test is_running returns False for terminated process."""
        # Setup mock process
        mock_process = Mock()
        mock_process.poll.return_value = 0  # Terminated
        mock_popen.return_value = mock_process
        
        # Create and start background script
        self._create_test_script("background.py", "print('done')")
        self.process_manager.start_script("background", "background")
        
        # Test is_running
        self.assertFalse(self.process_manager.is_running("background"))
        
    @patch('subprocess.Popen')
    def test_get_exit_code(self, mock_popen):
        """Test getting exit code from terminated process."""
        # Setup mock process
        mock_process = Mock()
        mock_process.poll.return_value = 42
        mock_popen.return_value = mock_process
        
        # Create and start background script
        self._create_test_script("background.py", "exit(42)")
        self.process_manager.start_script("background", "background")
        
        # Test get_exit_code
        exit_code = self.process_manager.get_exit_code("background")
        self.assertEqual(exit_code, 42)
        
        
    @patch('subprocess.Popen')
    def test_stop_script(self, mock_popen):
        """Test stopping a running script."""
        # Setup mock process
        mock_process = Mock()
        mock_process.poll.return_value = None  # Running
        mock_popen.return_value = mock_process
        
        # Start background script
        self._create_test_script("background.py", "import time; time.sleep(10)")
        self.process_manager.start_script("background", "background")
        
        # Stop the script
        self.process_manager.stop_script("background")
        
        # Verify process was terminated
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
        
        # Verify process was removed from tracking
        self.assertNotIn("background", self.process_manager.processes)
        
    @patch('subprocess.Popen')
    def test_stop_script_force_kill(self, mock_popen):
        """Test force killing script that doesn't terminate gracefully."""
        # Setup mock process that doesn't terminate gracefully
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = subprocess.TimeoutExpired("test", 5)
        mock_popen.return_value = mock_process
        
        # Start background script
        self._create_test_script("background.py", "import time; time.sleep(10)")
        self.process_manager.start_script("background", "background")
        
        # Stop the script
        self.process_manager.stop_script("background")
        
        # Verify terminate was called, then kill
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        
    @patch('time.time')
    @patch('time.sleep')
    def test_restart_script_crash_protection(self, mock_sleep, mock_time):
        """Test restart script with crash protection."""
        # Mock time to simulate rapid crashes
        mock_time.side_effect = [100, 101, 102, 103, 104, 105, 106]  # 6 crashes in rapid succession
        
        # Create test script
        self._create_test_script("background.py", "exit(1)")
        
        # Mock start_script to fail for first few attempts
        with patch.object(self.process_manager, 'start_script', return_value=True) as mock_start:
            # Test multiple rapid restarts
            for i in range(6):
                result = self.process_manager.restart_script("background", "background")
                if i < 5:  # First 5 should succeed
                    self.assertTrue(result)
                else:  # 6th should fail due to crash protection
                    self.assertFalse(result)
                    
        # Verify sleep was called (restart delay) - only for successful restarts
        self.assertEqual(mock_sleep.call_count, 5)
        
    def test_cleanup(self):
        """Test cleanup stops all processes."""
        with patch.object(self.process_manager, 'stop_script') as mock_stop:
            # Add some fake processes
            self.process_manager.processes = {"bg1": Mock(), "bg2": Mock()}
            
            # Call cleanup
            self.process_manager.cleanup()
            
            # Verify all processes were stopped
            mock_stop.assert_any_call("bg1")
            mock_stop.assert_any_call("bg2")
            self.assertEqual(mock_stop.call_count, 2)
            
    def test_unsupported_script_extension(self):
        """Test handling unsupported script extensions."""
        # Create script with unsupported extension
        self._create_test_script("action.rb", "puts 'ruby script'")
        
        # Try to start it
        success = self.process_manager.start_script("action", "action")
        self.assertFalse(success)
        
    def test_script_execution_exception_handling(self):
        """Test exception handling during script execution."""
        # Create test script
        self._create_test_script("action.py", "print('test')")
        
        # Mock subprocess to raise exception
        with patch('subprocess.Popen', side_effect=Exception("Test error")):
            success = self.process_manager.start_script("action", "action")
            self.assertFalse(success)
            
    @patch('subprocess.Popen')
    def test_background_script_already_running(self, mock_popen):
        """Test starting background script when already running."""
        # Setup mock process
        mock_process = Mock()
        mock_process.poll.return_value = None  # Still running
        mock_popen.return_value = mock_process
        
        # Create and start background script
        self._create_test_script("background.py", "import time; time.sleep(10)")
        
        # Start script first time
        success1 = self.process_manager.start_script("background", "background")
        self.assertTrue(success1)
        
        # Try to start again - should return True without creating new process
        success2 = self.process_manager.start_script("background", "background")
        self.assertTrue(success2)
        
        # Verify Popen was only called once
        self.assertEqual(mock_popen.call_count, 1)


if __name__ == '__main__':
    unittest.main()
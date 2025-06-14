"""Tests for ProcessManager class."""

import os
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch, MagicMock

from src.core.processes import ProcessManager
from src.utils.config import reset_config


class TestProcessManager(unittest.TestCase):
    """Test cases for ProcessManager."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        # Reset global config for clean test state
        reset_config()
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
        success = self.process_manager.start_script_sync("update")
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
        success = self.process_manager.start_script_sync("update")
        self.assertFalse(success)
        
    @patch('subprocess.Popen')
    def test_execute_action_script(self, mock_popen):
        """Test action script execution."""
        # Create test script
        self._create_test_script("action.sh", "echo 'action'")
        
        # Test execution
        success = self.process_manager.start_script_async("action")
        self.assertTrue(success)
        
        # Verify Popen was called
        mock_popen.assert_called_once()
        
    @patch('os.getpgid')
    @patch('subprocess.Popen')
    def test_execute_background_script(self, mock_popen, mock_getpgid):
        """Test background script execution."""
        # Setup mock process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        mock_getpgid.return_value = 12345
        
        # Create test script
        self._create_test_script("background.py", "while True: time.sleep(1)")
        
        # Test execution
        success = self.process_manager.start_script_async("background")
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
        self.process_manager.start_script_async("background")
        
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
        self.process_manager.start_script_async("background")
        
        # Test is_running
        self.assertFalse(self.process_manager.is_running("background"))
        
    @patch('subprocess.Popen')
    def test_process_completion_monitoring(self, mock_popen):
        """Test that completed processes are properly detected."""
        # Setup mock process that completes
        mock_process = Mock()
        mock_process.poll.return_value = 42  # Process completed with exit code 42
        mock_popen.return_value = mock_process
        
        # Setup callback to capture completion
        completed_scripts = []
        def on_completion(script_type, exit_code):
            completed_scripts.append((script_type, exit_code))
        
        self.process_manager.on_script_completed = on_completion
        
        # Create and start script
        self._create_test_script("action.py", "exit(42)")
        self.process_manager.start_script_async("action")
        
        # Manually trigger monitoring check (simulating what the monitoring thread does)
        with self.process_manager.lock:
            for script_type, process in list(self.process_manager.processes.items()):
                exit_code = process.poll()
                if exit_code is not None:
                    del self.process_manager.processes[script_type]
                    if self.process_manager.on_script_completed:
                        self.process_manager.on_script_completed(script_type, exit_code)
        
        # Verify completion was detected
        self.assertEqual(len(completed_scripts), 1)
        self.assertEqual(completed_scripts[0], ("action", 42))
        
        
    @patch('os.killpg')
    @patch('os.getpgid')
    @patch('subprocess.Popen')
    def test_stop_script(self, mock_popen, mock_getpgid, mock_killpg):
        """Test stopping a running script."""
        # Setup mock process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Running
        mock_popen.return_value = mock_process
        mock_getpgid.return_value = 12345
        
        # Start background script
        self._create_test_script("background.py", "import time; time.sleep(10)")
        self.process_manager.start_script_async("background")
        
        # Stop the script
        self.process_manager.stop_script("background")
        
        # Verify process group was killed
        mock_killpg.assert_called()
        mock_process.wait.assert_called()
        
        # Verify process was removed from tracking
        self.assertNotIn("background", self.process_manager.processes)
        
    @patch('os.killpg')
    @patch('os.getpgid')
    @patch('subprocess.Popen')
    def test_stop_script_force_kill(self, mock_popen, mock_getpgid, mock_killpg):
        """Test force killing script that doesn't terminate gracefully."""
        # Setup mock process that doesn't terminate gracefully
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = subprocess.TimeoutExpired("test", 5)
        mock_popen.return_value = mock_process
        mock_getpgid.return_value = 12345
        
        # Start background script
        self._create_test_script("background.py", "import time; time.sleep(10)")
        self.process_manager.start_script_async("background")
        
        # Stop the script
        self.process_manager.stop_script("background")
        
        # Verify process group operations were called
        mock_killpg.assert_called()
        mock_process.wait.assert_called()
        
    def test_process_tracking(self):
        """Test that processes are properly tracked in the processes dict."""
        # Create test script
        self._create_test_script("action.py", "print('test')")
        
        # Start script
        success = self.process_manager.start_script_async("action")
        self.assertTrue(success)
        
        # Verify it's tracked
        self.assertIn("action", self.process_manager.processes)
        
        # Stop script
        self.process_manager.stop_script("action")
        
        # Verify it's no longer tracked
        self.assertNotIn("action", self.process_manager.processes)
        
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
        success = self.process_manager.start_script_async("action")
        self.assertFalse(success)
        
    def test_script_execution_exception_handling(self):
        """Test exception handling during script execution."""
        # Create test script
        self._create_test_script("action.py", "print('test')")
        
        # Mock subprocess to raise exception
        with patch('subprocess.Popen', side_effect=Exception("Test error")):
            success = self.process_manager.start_script_async("action")
            self.assertFalse(success)
            
    @patch('os.getpgid')
    @patch('subprocess.Popen')
    def test_background_script_already_running(self, mock_popen, mock_getpgid):
        """Test starting background script when already running."""
        # Setup mock process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Still running
        mock_popen.return_value = mock_process
        mock_getpgid.return_value = 12345
        
        # Create and start background script
        self._create_test_script("background.py", "import time; time.sleep(10)")
        
        # Start script first time
        success1 = self.process_manager.start_script_async("background")
        self.assertTrue(success1)
        
        # Try to start again - should stop the old one and start a new one
        success2 = self.process_manager.start_script_async("background")
        self.assertTrue(success2)
        
        # Verify Popen was called twice (original start + restart)
        self.assertEqual(mock_popen.call_count, 2)




    @patch('src.core.processes.get_config')
    @patch('subprocess.Popen')
    def test_script_execution_with_env_vars(self, mock_popen, mock_get_config):
        """Test that scripts are executed with environment variables."""
        # Mock global config to return custom env vars
        mock_config = Mock()
        mock_config.load_env_vars.return_value = {
            'API_KEY': 'test_key_123',
            'DEBUG_MODE': 'true'
        }
        mock_get_config.return_value = mock_config
        
        process_manager = ProcessManager(self.temp_dir)
        
        # Create test script
        self._create_test_script("action.sh", "echo 'test'")
        
        # Execute script
        process_manager.start_script_async("action")
        
        # Verify Popen was called with env parameter
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        
        # Check that env parameter was passed and contains our variables
        self.assertIn('env', call_args.kwargs)
        passed_env_vars = call_args.kwargs['env']
        
        # Check that our custom environment variables are present
        self.assertIn('API_KEY', passed_env_vars)
        self.assertIn('DEBUG_MODE', passed_env_vars)
        self.assertEqual(passed_env_vars['API_KEY'], 'test_key_123')
        self.assertEqual(passed_env_vars['DEBUG_MODE'], 'true')
        
        # Check that system environment variables are also present
        self.assertIn('PATH', passed_env_vars)

    @patch('src.core.processes.get_config')
    @patch('subprocess.run')
    def test_update_script_execution_with_env_vars(self, mock_run, mock_get_config):
        """Test that update scripts are executed with environment variables."""
        # Mock global config to return custom env vars
        mock_config = Mock()
        mock_config.load_env_vars.return_value = {
            'CONFIG_VAR': 'config_value',
            'SYNC_MODE': 'true'
        }
        mock_get_config.return_value = mock_config
        
        process_manager = ProcessManager(self.temp_dir)
        
        # Setup mock
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Create test script
        self._create_test_script("update.py", "print('updating')")
        
        # Execute update script synchronously
        process_manager.start_script_sync("update")
        
        # Verify subprocess.run was called with env parameter
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        
        # Check that env parameter was passed and contains our variables
        self.assertIn('env', call_args.kwargs)
        passed_env_vars = call_args.kwargs['env']
        
        # Check that our custom environment variables are present
        self.assertIn('CONFIG_VAR', passed_env_vars)
        self.assertIn('SYNC_MODE', passed_env_vars)
        self.assertEqual(passed_env_vars['CONFIG_VAR'], 'config_value')
        self.assertEqual(passed_env_vars['SYNC_MODE'], 'true')
        
        # Check that system environment variables are also present (like PATH)
        # Note: The actual system env vars might vary, but PATH should be there
        self.assertGreater(len(passed_env_vars), 2)  # Should have more than just our 2 vars


if __name__ == '__main__':
    unittest.main()
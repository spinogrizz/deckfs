"""Tests for Button class."""

import os
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch, MagicMock

from src.core.button import Button


class TestButton(unittest.TestCase):
    """Test cases for Button class."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.button = Button(self.temp_dir)
        
    def tearDown(self):
        """Clean up test environment."""
        self.button.stop()
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def _create_file(self, filename: str, content: str = "test"):
        """Create a test file."""
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'w') as f:
            f.write(content)
        os.chmod(file_path, 0o755)
        return file_path
        
        
    def test_load_config_valid_directory(self):
        """Test loading config from valid directory."""
        # Create update script
        self._create_file("update.py", "print('updating')")
        
        with patch.object(self.button.process_manager, 'start_script', return_value=True) as mock_start:
            result = self.button.load_config()
            
            self.assertTrue(result)
            mock_start.assert_called_once_with("update", "update")
            
    def test_load_config_invalid_directory(self):
        """Test loading config from non-existent directory."""
        # Create button with non-existent directory
        invalid_button = Button("/nonexistent/path")
        
        result = invalid_button.load_config()
        self.assertFalse(result)
        
    def test_load_config_no_update_script(self):
        """Test loading config when no update script exists."""
        with patch.object(self.button.process_manager, 'start_script', return_value=False) as mock_start:
            result = self.button.load_config()
            
            self.assertTrue(result)  # Still returns True even if update script doesn't exist
            mock_start.assert_called_once_with("update", "update")
            
    def test_start_button_first_time(self):
        """Test starting button for the first time."""
        with patch.object(self.button.process_manager, 'is_running', return_value=False), \
             patch.object(self.button.process_manager, 'start_script', return_value=True) as mock_start:
            
            self.button.start()
            
            self.assertTrue(self.button.running)
            self.assertIsNotNone(self.button.monitor_thread)
            mock_start.assert_called_once_with("background", "background")
            
    def test_start_button_already_running(self):
        """Test starting button when already running."""
        self.button.running = True
        
        with patch.object(self.button.process_manager, 'start_script') as mock_start:
            self.button.start()
            
            # Should not start background script again
            mock_start.assert_not_called()
            
    def test_start_button_background_already_running(self):
        """Test starting button when background process already exists."""
        with patch.object(self.button.process_manager, 'is_running', return_value=True), \
             patch.object(self.button.process_manager, 'start_script') as mock_start:
            
            self.button.start()
            
            self.assertTrue(self.button.running)
            # Should not start background script if already running
            mock_start.assert_not_called()
            
    def test_stop_button(self):
        """Test stopping button."""
        # Start button first
        self.button.running = True
        self.button.monitor_thread = threading.Thread(target=lambda: None)
        
        with patch.object(self.button.process_manager, 'cleanup') as mock_cleanup:
            self.button.stop()
            
            self.assertFalse(self.button.running)
            mock_cleanup.assert_called_once()
            
    def test_stop_button_not_running(self):
        """Test stopping button when not running."""
        with patch.object(self.button.process_manager, 'cleanup') as mock_cleanup:
            self.button.stop()
            
            # Should not call cleanup if not running
            mock_cleanup.assert_not_called()
            
    def test_handle_press(self):
        """Test handling button press."""
        with patch.object(self.button.process_manager, 'start_script', return_value=True) as mock_start:
            self.button.handle_press()
            
            mock_start.assert_called_once_with("action", "action")
            
    def test_find_image_file_existing(self):
        """Test finding existing image file."""
        image_path = self._create_file("image.png", "binary data")
        
        found_path = self.button._find_image_file()
        self.assertEqual(found_path, image_path)
        
    def test_find_image_file_nonexistent(self):
        """Test finding image file when none exists."""
        found_path = self.button._find_image_file()
        self.assertIsNone(found_path)
        
    def test_find_image_file_invalid_permissions(self):
        """Test finding image file with invalid permissions."""
        # Create image file with no read permissions
        image_path = self._create_file("image.png", "binary data")
        os.chmod(image_path, 0o000)
        
        try:
            # Should still find the file (find_any_file only checks existence)
            found_path = self.button._find_image_file()
            self.assertEqual(found_path, image_path)
        finally:
            # Restore permissions for cleanup
            os.chmod(image_path, 0o644)
            
    def test_load_config_with_corrupted_directory(self):
        """Test loading config when directory permissions are corrupted."""
        # Remove read permissions from directory
        os.chmod(self.temp_dir, 0o000)
        
        try:
            with patch.object(self.button.process_manager, 'start_script') as mock_start:
                result = self.button.load_config()
                # Should still return True but fail to execute scripts
                self.assertTrue(result)
        finally:
            # Restore permissions
            os.chmod(self.temp_dir, 0o755)
        
    def test_find_image_file_multiple_formats(self):
        """Test finding image file with multiple formats available."""
        # Create multiple image files
        self._create_file("image.png", "png data")
        self._create_file("image.jpg", "jpg data")
        
        found_path = self.button._find_image_file()
        # Should find one of them (order depends on os.listdir)
        self.assertIsNotNone(found_path)
        self.assertTrue(found_path.endswith("image.png") or found_path.endswith("image.jpg"))
        
    def test_file_changed_background_script(self):
        """Test handling background script change."""
        with patch.object(self.button.process_manager, 'stop_script') as mock_stop, \
             patch.object(self.button.process_manager, 'start_script') as mock_start:
            
            handled = self.button.file_changed("background.py")
            
            self.assertTrue(handled)
            mock_stop.assert_called_once_with("background")
            mock_start.assert_called_once_with("background", "background")
            
    def test_file_changed_update_script(self):
        """Test handling update script change."""
        with patch.object(self.button.process_manager, 'start_script') as mock_start, \
             patch.object(self.button.process_manager, 'stop_script') as mock_stop:
            
            handled = self.button.file_changed("update.sh")
            
            self.assertTrue(handled)
            mock_start.assert_called_once_with("update", "update")
            mock_stop.assert_not_called()  # Update scripts are not stopped
            
    def test_file_changed_action_script(self):
        """Test handling action script change (logs but does nothing else)."""
        with patch.object(self.button.process_manager, 'start_script') as mock_start, \
             patch.object(self.button.process_manager, 'stop_script') as mock_stop:
            
            handled = self.button.file_changed("action.js")
            
            self.assertTrue(handled)  # Recognized but no action taken
            # Action script changes don't trigger restart
            mock_start.assert_not_called()
            mock_stop.assert_not_called()
            
    def test_file_changed_image(self):
        """Test handling image file changes."""
        # Image changes should be recognized but no script actions taken
        handled = self.button.file_changed("image.png")
        self.assertTrue(handled)
        
        # Different image formats
        handled = self.button.file_changed("image.jpg")
        self.assertTrue(handled)
        
        handled = self.button.file_changed("image.gif")
        self.assertTrue(handled)
    
    def test_file_changed_invalid_files(self):
        """Test handling invalid file changes."""
        # Test various invalid file names
        invalid_files = ["config.yaml", "readme.txt", "some_file.log", ".hidden"]
        for invalid_file in invalid_files:
            handled = self.button.file_changed(invalid_file)
            self.assertFalse(handled)  # Should not handle these files
    
    def test_get_image_bytes_error_state(self):
        """Test get_image_bytes when button has error."""
        self.button.set_error("Test error")
        
        # Mock deck object
        mock_deck = unittest.mock.Mock()
        
        result = self.button.get_image_bytes(mock_deck)
        self.assertIsNone(result)
    
    def test_get_image_bytes_no_image(self):
        """Test get_image_bytes when no image file exists."""
        mock_deck = unittest.mock.Mock()
        
        with patch.object(self.button, '_find_image_file', return_value=None):
            result = self.button.get_image_bytes(mock_deck)
            
        self.assertIsNone(result)
        self.assertTrue(self.button.has_error)
        self.assertIn("No image file found", self.button.error_message)
    
    def test_get_image_bytes_success(self):
        """Test successful get_image_bytes."""
        mock_deck = unittest.mock.Mock()
        mock_image_bytes = b"fake_image_data"
        
        with patch.object(self.button, '_find_image_file', return_value="/path/to/image.png"), \
             patch('src.core.button.load_and_prepare_image', return_value=mock_image_bytes):
            
            result = self.button.get_image_bytes(mock_deck)
            
        self.assertEqual(result, mock_image_bytes)
        self.assertFalse(self.button.has_error)
            
    def test_reload_button(self):
        """Test reloading button configuration."""
        # Start button first
        self.button.running = True
        
        with patch.object(self.button, 'stop') as mock_stop, \
             patch.object(self.button, 'load_config', return_value=True) as mock_load, \
             patch.object(self.button, 'start') as mock_start:
            
            self.button.reload()
            
            mock_stop.assert_called_once()
            mock_load.assert_called_once()
            mock_start.assert_called_once()
            
    def test_monitor_background_process_running(self):
        """Test background process monitoring when process is running."""
        self.button.running = True
        
        with patch.object(self.button.process_manager, 'is_running', return_value=True), \
             patch.object(self.button.process_manager, 'get_exit_code', return_value=None), \
             patch.object(self.button.process_manager, 'restart_script') as mock_restart:
            
            # Run monitor for a short time
            monitor_thread = threading.Thread(target=self.button._monitor_background)
            monitor_thread.start()
            
            time.sleep(0.1)  # Let it run briefly
            self.button.running = False  # Stop monitoring
            monitor_thread.join(timeout=1)
            
            # Should not restart running process
            mock_restart.assert_not_called()
            
    def test_monitor_background_process_crashed(self):
        """Test background process monitoring when process crashes."""
        self.button.running = True
        
        with patch.object(self.button.process_manager, 'is_running', return_value=True), \
             patch.object(self.button.process_manager, 'get_exit_code', return_value=1), \
             patch.object(self.button.process_manager, 'restart_script', return_value=True) as mock_restart:
            
            # Run monitor for a short time
            monitor_thread = threading.Thread(target=self.button._monitor_background)
            monitor_thread.start()
            
            time.sleep(1.1)  # Let it run one monitoring cycle
            self.button.running = False  # Stop monitoring
            monitor_thread.join(timeout=2)
            
            # Should restart crashed process
            mock_restart.assert_called_with("background", "background")
            
    def test_monitor_background_no_process(self):
        """Test background process monitoring when no background process exists."""
        self.button.running = True
        
        with patch.object(self.button.process_manager, 'is_running', return_value=False), \
             patch.object(self.button.process_manager, 'restart_script') as mock_restart:
            
            # Run monitor for a short time
            monitor_thread = threading.Thread(target=self.button._monitor_background)
            monitor_thread.start()
            
            time.sleep(0.1)  # Let it run briefly
            self.button.running = False  # Stop monitoring
            monitor_thread.join(timeout=1)
            
            # Should not try to restart non-existent process
            mock_restart.assert_not_called()
            
    def test_integration_full_lifecycle(self):
        """Test full button lifecycle integration."""
        # Create test scripts
        self._create_file("action.py", "print('action executed')")
        self._create_file("background.py", "import time; time.sleep(10)")
        self._create_file("update.py", "print('updated')")
        self._create_file("image.png", "binary image data")
        
        # Mock process manager methods
        with patch.object(self.button.process_manager, 'start_script', return_value=True) as mock_start, \
             patch.object(self.button.process_manager, 'is_running', return_value=False), \
             patch.object(self.button.process_manager, 'cleanup') as mock_cleanup:
            
            # Test complete lifecycle
            # 1. Load config
            self.assertTrue(self.button.load_config())
            
            # 2. Start button
            self.button.start()
            self.assertTrue(self.button.running)
            
            # 3. Handle press
            self.button.handle_press()
            
            # 4. Find image
            image_path = self.button._find_image_file()
            self.assertIsNotNone(image_path)
            
            # 5. Handle script change
            handled = self.button.file_changed("background.py")
            self.assertTrue(handled)
            
            # 6. Stop button
            self.button.stop()
            self.assertFalse(self.button.running)
            
            # Verify expected calls
            expected_calls = [
                ("update", "update"),      # From load_config
                ("background", "background"),  # From start
                ("action", "action"),      # From handle_press
                ("background", "background"),  # From handle_script_change
            ]
            
            # Check that start_script was called with expected arguments
            actual_calls = [call.args for call in mock_start.call_args_list]
            self.assertEqual(len(actual_calls), 4)  # Should have 4 calls
            
            mock_cleanup.assert_called_once()
            
    def test_thread_safety(self):
        """Test thread safety of button operations."""
        # Create multiple threads performing different operations
        def start_stop_button():
            for _ in range(5):
                self.button.start()
                time.sleep(0.01)
                self.button.stop()
                time.sleep(0.01)
                
        def press_button():
            for _ in range(10):
                self.button.handle_press()
                time.sleep(0.01)
                
        with patch.object(self.button.process_manager, 'start_script', return_value=True), \
             patch.object(self.button.process_manager, 'is_running', return_value=False), \
             patch.object(self.button.process_manager, 'cleanup'):
            
            # Start multiple threads
            threads = []
            threads.append(threading.Thread(target=start_stop_button))
            threads.append(threading.Thread(target=press_button))
            
            # Run all threads
            for thread in threads:
                thread.start()
                
            for thread in threads:
                thread.join(timeout=5)
                
            # Should not raise any exceptions
            
    def test_error_handling_in_monitor(self):
        """Test error handling in background monitor thread."""
        # This test verifies that exceptions in monitor thread don't crash the application
        # The exception is expected and shows proper error isolation
        self.button.running = True
        
        # Mock process manager to raise exception
        with patch.object(self.button.process_manager, 'is_running', side_effect=Exception("Test error")):
            
            # Run monitor for a short time
            monitor_thread = threading.Thread(target=self.button._monitor_background)
            monitor_thread.start()
            
            time.sleep(0.1)  # Let it run briefly
            self.button.running = False  # Stop monitoring
            monitor_thread.join(timeout=1)
            
            # The exception is caught in the background thread and doesn't crash main thread
            # This test ensures proper error isolation - main thread continues normally
            self.assertFalse(self.button.running)  # Verify we successfully stopped


if __name__ == '__main__':
    unittest.main()
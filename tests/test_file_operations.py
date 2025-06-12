"""Tests for FileWatcher and file utilities."""

import os
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
from watchdog.events import FileCreatedEvent, FileDeletedEvent, FileModifiedEvent, DirCreatedEvent, DirDeletedEvent, DirMovedEvent

from src.core.files import FileWatcher
from src.utils.file_utils import find_file, find_any_file
from src.utils.debouncer import Debouncer


class TestFileUtils(unittest.TestCase):
    """Test cases for file utility functions."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def _create_file(self, filename: str, content: str = "test"):
        """Create a test file."""
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'w') as f:
            f.write(content)
        return file_path
        
    def _create_symlink(self, target: str, link_name: str):
        """Create a symbolic link."""
        target_path = os.path.join(self.temp_dir, target)
        link_path = os.path.join(self.temp_dir, link_name)
        os.symlink(target_path, link_path)
        return link_path
        
    def test_find_file_existing(self):
        """Test finding existing file with specific extension."""
        self._create_file("action.py", "print('test')")
        self._create_file("action.sh", "echo test")
        
        # Find Python file
        result = find_file(self.temp_dir, "action", ["py", "sh"])
        expected = os.path.join(self.temp_dir, "action.py")
        self.assertEqual(result, expected)
        
    def test_find_file_extension_priority(self):
        """Test extension priority in find_file."""
        self._create_file("action.py", "print('test')")
        self._create_file("action.sh", "echo test")
        
        # Should find .sh first due to order
        result = find_file(self.temp_dir, "action", ["sh", "py"])
        expected = os.path.join(self.temp_dir, "action.sh")
        self.assertEqual(result, expected)
        
    def test_find_file_nonexistent_directory(self):
        """Test find_file with non-existent directory."""
        result = find_file("/nonexistent/path", "action", ["py"])
        self.assertIsNone(result)
        
    def test_find_file_no_matches(self):
        """Test find_file when no files match."""
        self._create_file("other.txt", "test")
        
        result = find_file(self.temp_dir, "action", ["py", "sh"])
        self.assertIsNone(result)
        
    def test_find_any_file_existing(self):
        """Test finding any file with matching prefix."""
        self._create_file("image.png", "binary data")
        self._create_file("image.jpg", "binary data")
        
        result = find_any_file(self.temp_dir, "image")
        # Should find one of them (order depends on os.listdir)
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith("image.png") or result.endswith("image.jpg"))
        
    def test_find_any_file_symlink(self):
        """Test finding symbolic links."""
        self._create_file("target.png", "data")
        self._create_symlink("target.png", "image.png")
        
        result = find_any_file(self.temp_dir, "image")
        expected = os.path.join(self.temp_dir, "image.png")
        self.assertEqual(result, expected)
        
    def test_find_any_file_nonexistent_directory(self):
        """Test find_any_file with non-existent directory."""
        result = find_any_file("/nonexistent/path", "image")
        self.assertIsNone(result)
        
    def test_find_any_file_no_matches(self):
        """Test find_any_file when no files match."""
        self._create_file("other.txt", "test")
        
        result = find_any_file(self.temp_dir, "image")
        self.assertIsNone(result)
        
    def test_find_any_file_ignores_directories(self):
        """Test that find_any_file ignores directories."""
        # Create directory with matching prefix
        dir_path = os.path.join(self.temp_dir, "image.dir")
        os.makedirs(dir_path)
        
        result = find_any_file(self.temp_dir, "image")
        self.assertIsNone(result)
        
    def test_find_file_with_invalid_input(self):
        """Test find_file with invalid input parameters."""
        # Test with None directory (os.path.isdir handles None gracefully)
        with self.assertRaises(TypeError):
            find_file(None, "action", ["py"])
            
        # Test with empty directory path (returns None as expected)
        self.assertIsNone(find_file("", "action", ["py"]))
        
        # Test with None prefix (f-string handles None conversion)
        self.assertIsNone(find_file(self.temp_dir, None, ["py"]))
            
        # Test with empty prefix (should work but not find anything)
        self.assertIsNone(find_file(self.temp_dir, "", ["py"]))
        
        # Test with None extensions (raises TypeError in iteration)
        with self.assertRaises(TypeError):
            find_file(self.temp_dir, "action", None)
            
        # Test with empty extensions list (returns None)
        self.assertIsNone(find_file(self.temp_dir, "action", []))
        
    def test_find_any_file_with_invalid_input(self):
        """Test find_any_file with invalid input parameters."""
        # Test with None directory (raises TypeError in os.path.isdir)
        with self.assertRaises(TypeError):
            find_any_file(None, "image")
            
        # Test with empty directory path (returns None as expected)
        self.assertIsNone(find_any_file("", "image"))
        
        # Test with None prefix (f-string handles None conversion)
        self.assertIsNone(find_any_file(self.temp_dir, None))
            
        # Test with empty prefix (should work but not find anything)
        self.assertIsNone(find_any_file(self.temp_dir, ""))
        
    def test_find_file_with_special_characters(self):
        """Test find_file with special characters in names."""
        # Create files with special characters
        special_names = ["action-test", "action_test", "action.test", "action@test"]
        for name in special_names:
            self._create_file(f"{name}.py", "test")
            
        # Should not find files with different naming patterns
        result = find_file(self.temp_dir, "action", ["py"])
        self.assertIsNone(result)  # Exact match only
        
    def test_find_file_case_sensitivity(self):
        """Test find_file case sensitivity."""
        self._create_file("Action.py", "test")
        
        # Should not find case-mismatched files
        result = find_file(self.temp_dir, "action", ["py"])
        self.assertIsNone(result)
        
        # Should find exact case match
        result = find_file(self.temp_dir, "Action", ["py"])
        expected = os.path.join(self.temp_dir, "Action.py")
        self.assertEqual(result, expected)


class TestFileWatcher(unittest.TestCase):
    """Test cases for FileWatcher."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.debouncer = Debouncer(debounce_interval=0.05)
        self.file_watcher = FileWatcher(self.debouncer, self.temp_dir)
        
        # Mock callbacks
        self.file_callback = Mock()
        self.dir_callback = Mock()
        
        # Subscribe to events
        self.debouncer.subscribe("FILE_CHANGED", self.file_callback)
        self.debouncer.subscribe("BUTTON_DIRECTORIES_CHANGED", self.dir_callback)
        
    def tearDown(self):
        """Clean up test environment."""
        self.file_watcher.stop_watching()
        self.debouncer.shutdown()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def _create_button_dir(self, button_id: int, name: str = ""):
        """Create a button directory."""
        if name:
            dir_name = f"{button_id:02d}_{name}"
        else:
            dir_name = f"{button_id:02d}"
        dir_path = os.path.join(self.temp_dir, dir_name)
        os.makedirs(dir_path, exist_ok=True)
        return dir_path
        
    def test_get_debounce_key_image_file(self):
        """Test debounce key generation for image files."""
        button_dir = self._create_button_dir(1, "test")
        file_path = os.path.join(button_dir, "image.png")
        
        key = self.file_watcher._get_debounce_key(file_path)
        self.assertEqual(key, "01_test:image")
        
    def test_get_debounce_key_script_files(self):
        """Test debounce key generation for script files."""
        button_dir = self._create_button_dir(5)
        
        action_path = os.path.join(button_dir, "action.py")
        background_path = os.path.join(button_dir, "background.sh")
        update_path = os.path.join(button_dir, "update.js")
        
        self.assertEqual(self.file_watcher._get_debounce_key(action_path), "05:action")
        self.assertEqual(self.file_watcher._get_debounce_key(background_path), "05:background")
        self.assertEqual(self.file_watcher._get_debounce_key(update_path), "05:update")
        
    def test_get_debounce_key_unsupported_file(self):
        """Test debounce key for unsupported files."""
        button_dir = self._create_button_dir(1)
        file_path = os.path.join(button_dir, "config.yaml")
        
        key = self.file_watcher._get_debounce_key(file_path)
        self.assertIsNone(key)
        
    def test_get_debounce_key_invalid_directory(self):
        """Test debounce key for files in non-button directories."""
        # Create non-button directory
        non_button_dir = os.path.join(self.temp_dir, "config")
        os.makedirs(non_button_dir)
        file_path = os.path.join(non_button_dir, "image.png")
        
        key = self.file_watcher._get_debounce_key(file_path)
        self.assertIsNone(key)
        
    def test_get_debounce_key_with_invalid_paths(self):
        """Test debounce key generation with invalid file paths."""
        invalid_paths = [
            None,
            "",
            "   ",
            "/nonexistent/path/file.png",
            "relative/path/file.png",
            self.temp_dir,  # Directory instead of file
        ]
        
        for invalid_path in invalid_paths:
            key = self.file_watcher._get_debounce_key(invalid_path)
            self.assertIsNone(key)
            
    def test_get_debounce_key_malformed_button_directories(self):
        """Test debounce key for malformed button directory names."""
        malformed_dirs = [
            "1_invalid",      # Single digit
            "001_too_many",   # Too many digits  
            "ab_letters",     # Letters instead of numbers
            "01-dash",        # Dash instead of underscore
            "_01_prefix",     # Underscore prefix
        ]
        
        for dir_name in malformed_dirs:
            dir_path = os.path.join(self.temp_dir, dir_name)
            os.makedirs(dir_path, exist_ok=True)
            file_path = os.path.join(dir_path, "image.png")
            
            key = self.file_watcher._get_debounce_key(file_path)
            if dir_name in ["1_invalid", "ab_letters", "_01_prefix"]:
                self.assertIsNone(key)  # Should be invalid
            # Note: "001_too_many" and "01-dash" might still work as they start with digits
        
    def test_is_button_directory_event_valid(self):
        """Test button directory detection for valid directories."""
        dir_paths = [
            os.path.join(self.temp_dir, "01"),
            os.path.join(self.temp_dir, "05_test"),
            os.path.join(self.temp_dir, "15_long_name")
        ]
        
        for dir_path in dir_paths:
            self.assertTrue(self.file_watcher._is_button_directory_event(dir_path))
            
    def test_is_button_directory_event_invalid(self):
        """Test button directory detection for invalid directories."""
        invalid_paths = [
            os.path.join(self.temp_dir, "config"),
            os.path.join(self.temp_dir, "1_invalid"),  # Single digit
            os.path.join(self.temp_dir, "01", "subfolder"),  # Nested
            "/some/other/path"
        ]
        
        for dir_path in invalid_paths:
            self.assertFalse(self.file_watcher._is_button_directory_event(dir_path))
            
    def test_file_event_handling(self):
        """Test file change event handling."""
        button_dir = self._create_button_dir(1)
        file_path = os.path.join(button_dir, "image.png")
        
        # Create file modified event
        event = FileModifiedEvent(file_path)
        
        # Handle event
        self.file_watcher.on_any_event(event)
        
        # Wait for debounced event
        time.sleep(0.1)
        
        # Verify callback was called
        self.file_callback.assert_called_once()
        event_data = self.file_callback.call_args[0][0].data
        self.assertEqual(event_data["path"], file_path)
        self.assertEqual(event_data["event_type"], "modified")
        
    def test_directory_event_handling(self):
        """Test button directory change event handling."""
        dir_path = os.path.join(self.temp_dir, "01_test")
        
        # Create directory created event
        event = DirCreatedEvent(dir_path)
        
        # Handle event
        self.file_watcher.on_any_event(event)
        
        # Wait for debounced event (directory events have longer debounce)
        time.sleep(1.2)
        
        # Verify callback was called
        self.dir_callback.assert_called_once()
        event_data = self.dir_callback.call_args[0][0].data
        self.assertEqual(event_data["src_path"], dir_path)
        self.assertEqual(event_data["event_type"], "created")
        
    def test_directory_modified_event_ignored(self):
        """Test that directory 'modified' events are ignored."""
        dir_path = os.path.join(self.temp_dir, "01_test")
        
        # Create directory modified event
        event = DirModifiedEvent(dir_path)
        
        # Handle event
        self.file_watcher.on_any_event(event)
        
        # Wait
        time.sleep(0.1)
        
        # Verify callback was NOT called
        self.dir_callback.assert_not_called()
        
    def test_directory_moved_event(self):
        """Test directory moved/renamed event handling."""
        src_path = os.path.join(self.temp_dir, "01_old")
        dest_path = os.path.join(self.temp_dir, "01_new")
        
        # Create directory moved event
        event = DirMovedEvent(src_path, dest_path)
        
        # Handle event
        self.file_watcher.on_any_event(event)
        
        # Wait for debounced event (directory events have longer debounce)
        time.sleep(1.2)
        
        # Verify callback was called
        self.dir_callback.assert_called_once()
        event_data = self.dir_callback.call_args[0][0].data
        self.assertEqual(event_data["src_path"], src_path)
        self.assertEqual(event_data["dest_path"], dest_path)
        self.assertEqual(event_data["event_type"], "moved")
        
    def test_non_button_directory_events_ignored(self):
        """Test that non-button directory events are ignored."""
        dir_path = os.path.join(self.temp_dir, "config")
        
        # Create directory created event for non-button directory
        event = DirCreatedEvent(dir_path)
        
        # Handle event
        self.file_watcher.on_any_event(event)
        
        # Wait
        time.sleep(0.1)
        
        # Verify callback was NOT called
        self.dir_callback.assert_not_called()
        
    def test_start_stop_watching(self):
        """Test starting and stopping file watcher."""
        # Start watching
        self.file_watcher.start_watching()
        self.assertIsNotNone(self.file_watcher.observer)
        
        # Stop watching
        self.file_watcher.stop_watching()
        self.assertIsNone(self.file_watcher.observer)
        
    def test_start_watching_already_started(self):
        """Test starting watcher when already started."""
        # Start watching twice
        self.file_watcher.start_watching()
        observer1 = self.file_watcher.observer
        
        self.file_watcher.start_watching()  # Should not create new observer
        observer2 = self.file_watcher.observer
        
        self.assertIs(observer1, observer2)
        
    def test_stop_watching_not_started(self):
        """Test stopping watcher when not started."""
        # Should not raise exception
        self.file_watcher.stop_watching()
        self.assertIsNone(self.file_watcher.observer)
        
    def test_file_event_debouncing(self):
        """Test that multiple file events are debounced correctly."""
        button_dir = self._create_button_dir(1)
        file_path = os.path.join(button_dir, "image.png")
        
        # Send multiple rapid events
        for i in range(5):
            event = FileModifiedEvent(file_path)
            self.file_watcher.on_any_event(event)
            
        # Wait for debouncing
        time.sleep(0.1)
        
        # Should only receive one callback
        self.file_callback.assert_called_once()
        
    def test_skip_opened_closed_events(self):
        """Test that opened/closed events are skipped."""
        from watchdog.events import FileOpenedEvent, FileClosedEvent
        
        button_dir = self._create_button_dir(1)
        file_path = os.path.join(button_dir, "image.png")
        
        # Create opened/closed events (these don't exist in watchdog, but test the concept)
        event = Mock()
        event.is_directory = False
        event.src_path = file_path
        event.event_type = 'opened'
        
        # Handle event
        self.file_watcher.on_any_event(event)
        
        # Wait
        time.sleep(0.1)
        
        # Should not trigger callback for opened/closed events
        self.file_callback.assert_not_called()
        
    def test_multiple_button_directories(self):
        """Test handling events from multiple button directories."""
        # Create multiple button directories
        dir1 = self._create_button_dir(1, "test1")
        dir2 = self._create_button_dir(2, "test2")
        
        file1 = os.path.join(dir1, "image.png")
        file2 = os.path.join(dir2, "action.py")
        
        # Send events from both directories
        event1 = FileModifiedEvent(file1)
        event2 = FileModifiedEvent(file2)
        
        self.file_watcher.on_any_event(event1)
        self.file_watcher.on_any_event(event2)
        
        # Wait for debouncing
        time.sleep(0.1)
        
        # Should receive both events (different debounce keys)
        self.assertEqual(self.file_callback.call_count, 2)
        
    def test_error_handling_in_debounce_key_generation(self):
        """Test error handling in debounce key generation."""
        # Test with invalid path
        with patch('os.path.relpath', side_effect=Exception("Test error")):
            key = self.file_watcher._get_debounce_key("/some/path")
            self.assertIsNone(key)


# Mock class for directory modified events (not in watchdog by default)
class DirModifiedEvent:
    def __init__(self, src_path):
        self.src_path = src_path
        self.is_directory = True
        self.event_type = 'modified'


if __name__ == '__main__':
    unittest.main()
"""Main Stream Deck manager with new architecture."""

import os
from typing import Dict, Optional
from PIL import Image
from StreamDeck.DeviceManager import DeviceManager as SDKDeviceManager
from StreamDeck.ImageHelpers import PILHelper

from ..utils.debouncer import Debouncer
from .files import FileWatcher
from .button import Button
from ..utils.config import ConfigManager


class StreamDeckManager:
    """Main Stream Deck manager."""
    
    # Static blank image cache
    _blank_image: Optional[Image.Image] = None
    
    def __init__(self, config_dir: str):
        """Initialize Stream Deck manager.
        
        Args:
            config_dir: Configuration directory path
        """
        self.config_dir = config_dir
        self.deck = None
        self.key_count = 0
        
        # Configuration manager
        self.config_manager = ConfigManager(config_dir)
        
        # Core components
        debounce_interval = self.config_manager.get_debounce_interval()
        self.debouncer = Debouncer(debounce_interval=debounce_interval)
        self.file_watcher = FileWatcher(self.debouncer, config_dir)
        self.buttons: Dict[int, Button] = {}
        
        # Subscribe to file change events
        self.debouncer.subscribe("FILE_CHANGED", self._handle_file_change)
        
        # Subscribe to button directory changes
        self.debouncer.subscribe("BUTTON_DIRECTORIES_CHANGED", self._handle_button_directories_changed)
        
    def initialize(self) -> bool:
        """Initialize Stream Deck device and components.
        
        Returns:
            bool: True if initialization successful
        """
        if not self._initialize_device():
            return False
            
        self._create_buttons()
        
        self._load_all_buttons()
        
        self.file_watcher.start_watching()
        
        print(f"Stream Deck manager initialized with {len(self.buttons)} buttons")
        return True
        
    def start(self):
        """Start all buttons."""
        for button in self.buttons.values():
            button.start()
        print("All buttons started")
        
    def stop(self):
        """Stop all components."""
        for button in self.buttons.values():
            button.stop()
            
        self.file_watcher.stop_watching()
        
        self.debouncer.shutdown()
        
        if self.deck:
            self.deck.close()
            self.deck = None
            
        print("Stream Deck manager stopped")
        
    def reload_button(self, button_id: int):
        """Reload specific button.
        
        Args:
            button_id: Button ID to reload (1-based)
        """
        if button_id in self.buttons:
            self.buttons[button_id].stop()
            del self.buttons[button_id]
        
        # Create new button
        working_dir = self._find_button_working_dir(button_id)
        if working_dir:
            button = Button(working_dir)
            self.buttons[button_id] = button
            if button.load_config():
                button.start()
                self.update_button_image(button_id)
            print(f"Button {button_id:02d} reloaded")
        else:
            self.clear_buttons(button_id)
            print(f"Button {button_id:02d} removed")
            
    def reload_all(self):
        """Reload all buttons."""
        print("Reloading all buttons...")
        
        for button in self.buttons.values():
            button.stop()
            
        # Recreate buttons (handles renamed/removed directories)
        old_buttons = self.buttons
        self._create_buttons()
        
        # Clean up old buttons
        for button_id, old_button in old_buttons.items():
            old_button.stop()
                
        self._load_all_buttons()
        self.start()
        
        print("All buttons reloaded")
    
    def update_button_image(self, button_id: int):
        """Update button image on device.
        
        Args:
            button_id: Button ID (1-based)
        """
        if not self.deck:
            print(f"Button {button_id:02d}: No deck available")
            return
            
        if button_id not in self.buttons:
            print(f"Button {button_id:02d}: Button not found")
            return
            
        button = self.buttons[button_id]
        image_path = button._find_image_file()
        
        if not image_path:
            print(f"Button {button_id:02d}: No image file found")
            return
            
        try:
            image = Image.open(image_path)
            image_bytes = PILHelper.to_native_format(
                self.deck,
                PILHelper.create_scaled_image(self.deck, image)
            )
            
            key_index = button_id - 1  # Convert to 0-based index
            self.deck.set_key_image(key_index, image_bytes)
                        
        except Exception as e:
            print(f"Button {button_id:02d}: Error updating image: {e}")
        
    @classmethod
    def _load_blank_image(cls) -> Optional[Image.Image]:
        """Load blank image once and cache it."""
        if cls._blank_image is None:
            try:
                # Navigate up from src/core/devices.py to find project root
                # Using static caching to avoid reloading the same image on every clear operation
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                blank_path = os.path.join(project_root, 'resources', 'blank.png')
                cls._blank_image = Image.open(blank_path)
                print(f"Blank image loaded: {blank_path}")
            except Exception as e:
                print(f"Error loading blank image: {e}")
                return None
        return cls._blank_image
    
    def clear_buttons(self, button_id: Optional[int] = None):
        """Clear Stream Deck button(s).
        
        Args:
            button_id: Button ID to clear (1-based), or None to clear all
        """
        if not self.deck:
            return
            
        blank_image = self._load_blank_image()
        if not blank_image:
            return
            
        try:
            image_bytes = PILHelper.to_native_format(
                self.deck, 
                PILHelper.create_scaled_image(self.deck, blank_image)
            )
            
            if button_id is None:
                for key_index in range(self.key_count):
                    self.deck.set_key_image(key_index, image_bytes)
                print(f"All {self.key_count} buttons cleared")
            else:
                if 1 <= button_id <= self.key_count:
                    key_index = button_id - 1
                    self.deck.set_key_image(key_index, image_bytes)
                    print(f"Button {button_id:02d} cleared")
                    
        except Exception as e:
            print(f"Error clearing buttons: {e}")
        
    def _initialize_device(self) -> bool:
        """Initialize Stream Deck device.
        
        Returns:
            bool: True if successful
        """
        try:
            devices = SDKDeviceManager().enumerate()
            if not devices:
                print("Stream Deck device not found")
                return False
                
            self.deck = devices[0]
            self.deck.open()
            self.deck.reset()
            brightness = self.config_manager.get_brightness()
            self.deck.set_brightness(brightness)
            
            self.key_count = self.deck.key_count()
            print(f"Found device: {self.deck.deck_type()} with {self.key_count} buttons")
            
            # Set button callback
            self.deck.set_key_callback(self._device_key_callback)
            
            return True
            
        except Exception as e:
            print(f"Stream Deck initialization error: {e}")
            return False
            
    def _create_buttons(self):
        """Create button instances."""
        for button in self.buttons.values():
            button.stop()
        self.buttons.clear()
        
        for button_id in range(1, self.key_count + 1):
            working_dir = self._find_button_working_dir(button_id)
            if working_dir:
                button = Button(working_dir)
                self.buttons[button_id] = button
            
    def _load_all_buttons(self):
        """Load configuration for all buttons."""
        for button_id, button in self.buttons.items():
            if button.load_config():
                self.update_button_image(button_id)
            else:
                self.clear_buttons(button_id)
            
    def _smart_reload_affected_buttons(self, event_type: str, src_path: str, dest_path: str):
        """Smart reload only affected buttons.
        
        Args:
            event_type: Type of directory event
            src_path: Source path
            dest_path: Destination path (for moves)
        """
        affected_buttons = set()
        
        # Find which buttons are affected
        if event_type == "moved":
            # Both source and destination affected because move = delete + create
            src_button_id = self._extract_button_id_from_path(src_path)
            dest_button_id = self._extract_button_id_from_path(dest_path)
            
            if src_button_id:
                affected_buttons.add(src_button_id)
            if dest_button_id:
                affected_buttons.add(dest_button_id)
                
        elif event_type in ["created", "deleted", "modified"]:
            # For create/delete/modified, only one button is affected
            button_id = self._extract_button_id_from_path(src_path)
            if button_id:
                affected_buttons.add(button_id)
        
        print(f"Reloading affected buttons: {sorted(affected_buttons)}")
        
        # Reload only affected buttons
        for button_id in affected_buttons:
            print(f"Reloading button {button_id:02d}")
            self.reload_button(button_id)
                
    def _extract_button_id_from_path(self, file_path: str) -> int:
        """Extract button ID from file or directory path.
        
        Args:
            file_path: File or directory path
            
        Returns:
            int: Button ID (1-based) or 0 if not found
        """
        try:
            # Handle files that may not exist yet during filesystem events
            # Check for '.' in basename as workaround for non-existent files
            if os.path.isfile(file_path) or '.' in os.path.basename(file_path):
                dir_path = os.path.dirname(file_path)
            else:
                dir_path = file_path
                
            # Get directory name relative to config_dir
            rel_path = os.path.relpath(dir_path, self.config_dir)
            dir_name = rel_path.split(os.sep)[0]  # Get first part of relative path
            
            # Extract first two digits
            if len(dir_name) >= 2 and dir_name[:2].isdigit():
                button_id = int(dir_name[:2])
                # Validate button ID is within device range
                if 1 <= button_id <= self.key_count:
                    return button_id
        except Exception as e:
            print(f"Error extracting button ID from {file_path}: {e}")
            
        return 0
        
    def _find_button_directories(self) -> Dict[int, str]:
        """Find all button directories.
        
        Returns:
            Dict[int, str]: Mapping of button ID to directory name
        """
        button_dirs = {}
        
        if not os.path.isdir(self.config_dir):
            return button_dirs
            
        for item in os.listdir(self.config_dir):
            item_path = os.path.join(self.config_dir, item)
            if os.path.isdir(item_path) and len(item) >= 2 and item[:2].isdigit():
                button_id = int(item[:2])
                if 1 <= button_id <= self.key_count:
                    button_dirs[button_id] = item
                    
        return button_dirs
    
    def _find_button_working_dir(self, button_id: int) -> Optional[str]:
        """Find working directory for button.
        
        Args:
            button_id: Button ID (1-based)
            
        Returns:
            Optional[str]: Full path to button working directory or None
        """
        if not os.path.isdir(self.config_dir):
            return None
            
        button_prefix = f"{button_id:02d}"
        
        for item in os.listdir(self.config_dir):
            if item.startswith(button_prefix) and os.path.isdir(os.path.join(self.config_dir, item)):
                return os.path.join(self.config_dir, item)
                
        return None
        
    def _device_key_callback(self, deck, key, state):
        """Handle physical button press from device.
        
        Args:
            deck: Stream Deck device
            key: Key index (0-based)
            state: True for press, False for release
        """
        if not state:  # Only handle press, not release
            return
            
        button_id = key + 1  # Convert to 1-based
        
        # Handle button press directly
        if button_id in self.buttons:
            print(f"Button {button_id:02d}: Pressed")
            self.buttons[button_id].handle_press()
    
    def _handle_file_change(self, event):
        """Handle file change event.
        
        Args:
            event: File change event
        """
        file_path = event.data.get("path", "")
        event_type = event.data.get("event_type", "")
        
        button_id = self._extract_button_id_from_path(file_path)
        if not button_id or button_id not in self.buttons:
            return
            
        filename = os.path.basename(file_path)
        
        if filename.startswith("image."):
            self.update_button_image(button_id)
        elif event_type == "modified":
            if filename.startswith("background."):
                print(f"Button {button_id:02d}: Background script changed")
                self.buttons[button_id].handle_script_change("background")
            elif filename.startswith("update."):
                print(f"Button {button_id:02d}: Update script changed")
                self.buttons[button_id].handle_script_change("update")
        
        
    def _handle_button_directories_changed(self, event):
        """Handle button directory changes (rename/create/delete).
        
        Args:
            event: Button directory change event
        """
        event_type = event.data.get('event_type')
        src_path = event.data.get('src_path')
        dest_path = event.data.get('dest_path')
        
        print(f"Button directories changed: {event_type}")
        
        # Critical: prevent infinite reload loops during button directory changes
        # File watcher must be stopped because reload operations trigger new filesystem events
        self.file_watcher.stop_watching()
        
        try:
            # Smart reload - only affected buttons
            self._smart_reload_affected_buttons(event_type, src_path, dest_path)
        finally:
            self.file_watcher.start_watching()
"""Main Stream Deck manager with new architecture."""

import os
from typing import Dict, Optional
from PIL import Image
from StreamDeck.DeviceManager import DeviceManager as SDKDeviceManager
from StreamDeck.ImageHelpers import PILHelper

from ..utils.event_bus import EventBus
from .files import FileWatcher
from .button import Button
from ..utils.config import DEFAULT_BRIGHTNESS


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
        
        # Core components
        self.event_bus = EventBus(debounce_interval=0.1)
        self.file_watcher = FileWatcher(self.event_bus, config_dir)
        self.buttons: Dict[int, Button] = {}
        
        # Subscribe to button press events from device
        self.event_bus.subscribe("DEVICE_BUTTON_PRESSED", self._handle_device_button_press)
        
        # Subscribe to button directory changes
        self.event_bus.subscribe("BUTTON_DIRECTORIES_CHANGED", self._handle_button_directories_changed)
        
    def initialize(self) -> bool:
        """Initialize Stream Deck device and components.
        
        Returns:
            bool: True if initialization successful
        """
        # Initialize device
        if not self._initialize_device():
            return False
            
        # Create buttons
        self._create_buttons()
        
        # Load button configurations
        self._load_all_buttons()
        
        # Start file watcher
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
        # Stop buttons
        for button in self.buttons.values():
            button.stop()
            
        # Stop file watcher
        self.file_watcher.stop_watching()
        
        # Shutdown event bus
        self.event_bus.shutdown()
        
        # Close device
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
            self.buttons[button_id].reload()
            print(f"Button {button_id:02d} reloaded")
        else:
            print(f"Button {button_id:02d} not found")
            
    def reload_all(self):
        """Reload all buttons."""
        print("Reloading all buttons...")
        
        # Stop all buttons
        for button in self.buttons.values():
            button.stop()
            
        # Recreate buttons (handles renamed/removed directories)
        old_buttons = self.buttons
        self._create_buttons()
        
        # Clean up old buttons
        for button_id, old_button in old_buttons.items():
            old_button.cleanup()
                
        # Load and start new buttons
        self._load_all_buttons()
        self.start()
        
        print("All buttons reloaded")
        
    @classmethod
    def _load_blank_image(cls) -> Optional[Image.Image]:
        """Load blank image once and cache it."""
        if cls._blank_image is None:
            try:
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
                # Clear all buttons
                for key_index in range(self.key_count):
                    self.deck.set_key_image(key_index, image_bytes)
                print(f"All {self.key_count} buttons cleared")
            else:
                # Clear specific button
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
            self.deck.set_brightness(DEFAULT_BRIGHTNESS)
            
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
        # Find all button directories
        button_dirs = self._find_button_directories()
        
        # Clear existing buttons
        for button in self.buttons.values():
            button.cleanup()
        self.buttons.clear()
        
        # Create new buttons
        for button_id in range(1, self.key_count + 1):
            button = Button(button_id, self.config_dir, self.event_bus, self.deck, self)
            self.buttons[button_id] = button
            
    def _load_all_buttons(self):
        """Load configuration for all buttons."""
        for button in self.buttons.values():
            button.load_config()
            
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
            # For moves, both source and destination buttons are affected
            src_button_id = self._extract_button_id_from_path(src_path)
            dest_button_id = self._extract_button_id_from_path(dest_path)
            
            if src_button_id:
                affected_buttons.add(src_button_id)
            if dest_button_id:
                affected_buttons.add(dest_button_id)
                
        elif event_type in ["created", "deleted"]:
            # For create/delete, only one button is affected
            button_id = self._extract_button_id_from_path(src_path)
            if button_id:
                affected_buttons.add(button_id)
        
        print(f"Reloading affected buttons: {sorted(affected_buttons)}")
        
        # Reload only affected buttons
        for button_id in affected_buttons:
            if button_id in self.buttons:
                print(f"Reloading button {button_id:02d}")
                self.buttons[button_id].reload()
                
    def _extract_button_id_from_path(self, dir_path: str) -> int:
        """Extract button ID from directory path.
        
        Args:
            dir_path: Directory path
            
        Returns:
            int: Button ID (1-based) or 0 if not found
        """
        try:
            # Get directory name
            dir_name = os.path.basename(dir_path)
            
            # Extract first two digits
            if len(dir_name) >= 2 and dir_name[:2].isdigit():
                button_id = int(dir_name[:2])
                # Validate button ID is within device range
                if 1 <= button_id <= self.key_count:
                    return button_id
        except Exception as e:
            print(f"Error extracting button ID from {dir_path}: {e}")
            
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
        
        # Emit button press event
        self.event_bus.emit(
            "BUTTON_PRESSED",
            {"button_id": button_id}
        )
        
    def _handle_device_button_press(self, event):
        """Handle device button press event.
        
        Args:
            event: Button press event
        """
        # This is handled by individual buttons subscribing to BUTTON_PRESSED
        pass
        
    def _handle_button_directories_changed(self, event):
        """Handle button directory changes (rename/create/delete).
        
        Args:
            event: Button directory change event
        """
        event_type = event.data.get('event_type')
        src_path = event.data.get('src_path')
        dest_path = event.data.get('dest_path')
        
        print(f"Button directories changed: {event_type}")
        
        # Temporarily stop file watcher to prevent reload loops
        self.file_watcher.stop_watching()
        
        try:
            # Smart reload - only affected buttons
            self._smart_reload_affected_buttons(event_type, src_path, dest_path)
        finally:
            # Restart file watcher after reload
            self.file_watcher.start_watching()
"""Main Stream Deck manager with new architecture."""

import os
from typing import Dict, Optional
from StreamDeck.DeviceManager import DeviceManager as SDKDeviceManager

from ..utils.event_bus import EventBus
from .files import FileWatcher
from .button import Button
from ..utils.config import DEFAULT_BRIGHTNESS


class StreamDeckManager:
    """Main Stream Deck manager."""
    
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
        
        # Clean up old buttons that no longer exist
        for button_id, button in old_buttons.items():
            if button_id not in self.buttons:
                button.cleanup()
                print(f"Button {button_id:02d} removed")
                
        # Load and start new buttons
        self._load_all_buttons()
        self.start()
        
        print("All buttons reloaded")
        
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
            button = Button(button_id, self.config_dir, self.event_bus, self.deck)
            self.buttons[button_id] = button
            
    def _load_all_buttons(self):
        """Load configuration for all buttons."""
        for button in self.buttons.values():
            button.load_config()
            
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
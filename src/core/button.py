"""Stream Deck button implementation."""

import os
import threading
from typing import Optional, Dict, Any
from PIL import Image
from StreamDeck.ImageHelpers import PILHelper

from ..utils.event_bus import EventBus, Event
from .processes import ProcessManager


class Button:
    """Encapsulates a single Stream Deck button."""
    
    def __init__(self, button_id: int, config_dir: str, event_bus: EventBus, deck=None):
        """Initialize button.
        
        Args:
            button_id: Button index (1-based)
            config_dir: Base configuration directory
            event_bus: Event bus for communication
            deck: Stream Deck device
        """
        self.button_id = button_id
        self.config_dir = config_dir
        self.event_bus = event_bus
        self.deck = deck
        
        # Button directory (e.g., "01_toggle_mute")
        self.button_dir = self._find_button_directory()
        self.working_dir = os.path.join(config_dir, self.button_dir) if self.button_dir else None
        
        # Process manager for this button
        self.process_manager = ProcessManager(self.working_dir) if self.working_dir else None
        
        # Monitor thread for background processes
        self.monitor_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Subscribe to relevant events
        self.event_bus.subscribe("BUTTON_PRESSED", self._handle_button_press)
        self.event_bus.subscribe("FILE_CHANGED", self._handle_file_change)
        
    def load_config(self) -> bool:
        """Load button configuration.
        
        Returns:
            bool: True if configuration loaded successfully
        """
        if not self.working_dir or not os.path.isdir(self.working_dir):
            print(f"Button {self.button_id:02d}: No configuration directory found")
            return False
            
        # Execute update script if exists
        if self.process_manager:
            self.process_manager.start_script("update", "update")
            
        # Update button image
        self.update_image()
        
        return True
        
    def reload(self):
        """Reload button configuration."""
        print(f"Button {self.button_id:02d}: Reloading configuration")
        
        # Stop current processes
        self.stop()
        
        # Re-find button directory (might have been renamed)
        old_dir = self.button_dir
        self.button_dir = self._find_button_directory()
        self.working_dir = os.path.join(self.config_dir, self.button_dir) if self.button_dir else None
        
        if old_dir != self.button_dir:
            print(f"Button {self.button_id:02d}: Directory changed from {old_dir} to {self.button_dir}")
            
        # Update process manager
        if self.working_dir:
            self.process_manager = ProcessManager(self.working_dir)
        else:
            self.process_manager = None
            
        # Load new configuration
        self.load_config()
        self.start()
        
    def start(self):
        """Start button (background processes)."""
        if self.running or not self.process_manager:
            return
            
        self.running = True
        
        # Start background script if exists
        self.process_manager.start_script("background", "background")
        
        # Start monitor thread
        self.monitor_thread = threading.Thread(target=self._monitor_background, daemon=True)
        self.monitor_thread.start()
        
        print(f"Button {self.button_id:02d}: Started")
        
    def stop(self):
        """Stop button (background processes)."""
        if not self.running:
            return
            
        self.running = False
        
        if self.process_manager:
            self.process_manager.cleanup()
            
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
            
        print(f"Button {self.button_id:02d}: Stopped")
        
    def handle_press(self):
        """Handle button press."""
        if not self.process_manager:
            print(f"Button {self.button_id:02d}: No action available")
            return
            
        print(f"Button {self.button_id:02d}: Pressed")
        self.process_manager.start_script("action", "action")
        
    def update_image(self):
        """Update button image on device."""
        if not self.deck or not self.working_dir:
            return
            
        # Find image file
        image_path = self._find_image_file()
        if not image_path:
            return
            
        try:
            # Load and scale image
            image = Image.open(image_path)
            image_bytes = PILHelper.to_native_format(
                self.deck,
                PILHelper.create_scaled_image(self.deck, image)
            )
            
            # Set image on device
            key_index = self.button_id - 1  # Convert to 0-based index
            self.deck.set_key_image(key_index, image_bytes)
            
            print(f"Button {self.button_id:02d}: Image updated from {image_path}")
            
        except Exception as e:
            print(f"Button {self.button_id:02d}: Error updating image: {e}")
            
    def cleanup(self):
        """Clean up resources."""
        self.stop()
        
        # Unsubscribe from events
        self.event_bus.unsubscribe("BUTTON_PRESSED", self._handle_button_press)
        self.event_bus.unsubscribe("FILE_CHANGED", self._handle_file_change)
        
    def _find_button_directory(self) -> Optional[str]:
        """Find button directory by number.
        
        Returns:
            Optional[str]: Directory name or None if not found
        """
        if not os.path.isdir(self.config_dir):
            return None
            
        button_prefix = f"{self.button_id:02d}"
        
        for item in os.listdir(self.config_dir):
            if item.startswith(button_prefix) and os.path.isdir(os.path.join(self.config_dir, item)):
                return item
                
        return None
        
    def _find_image_file(self) -> Optional[str]:
        """Find image file for button.
        
        Returns:
            Optional[str]: Path to image file or None
        """
        if not self.working_dir:
            return None
            
        # Check for image.png, image.jpg, etc.
        for filename in os.listdir(self.working_dir):
            if filename.startswith("image."):
                path = os.path.join(self.working_dir, filename)
                if os.path.isfile(path) or os.path.islink(path):
                    return path
                    
        return None
        
    def _handle_button_press(self, event: Event):
        """Handle button press event.
        
        Args:
            event: Button press event
        """
        if event.data.get("button_id") == self.button_id:
            self.handle_press()
            
    def _handle_file_change(self, event: Event):
        """Handle file change event.
        
        Args:
            event: File change event
        """
        file_path = event.data.get("path", "")
        
        # Check if file belongs to this button
        if not self.working_dir or not file_path.startswith(self.working_dir):
            return
            
        filename = os.path.basename(file_path)
        
        # Handle image changes
        if filename.startswith("image."):
            print(f"Button {self.button_id:02d}: Image file changed")
            self.update_image()
            
        # Handle script changes
        elif filename.startswith("background."):
            print(f"Button {self.button_id:02d}: Background script changed")
            if self.process_manager:
                self.process_manager.stop_script("background")
                self.process_manager.start_script("background", "background")
                
        elif filename.startswith("update."):
            print(f"Button {self.button_id:02d}: Update script changed")
            if self.process_manager:
                self.process_manager.start_script("update", "update")
                self.update_image()  # Update image after update script
                
    def _monitor_background(self):
        """Monitor background process for crashes."""
        while self.running and self.process_manager:
            if self.process_manager.is_running("background"):
                exit_code = self.process_manager.get_exit_code("background")
                if exit_code is not None:
                    print(f"Button {self.button_id:02d}: Background script exited with code {exit_code}")
                    self.process_manager.restart_script("background", "background")
                    
            threading.Event().wait(1)  # Check every second
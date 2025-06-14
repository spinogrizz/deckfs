import os
from typing import Optional, Dict, Any

from ..utils.debouncer import Debouncer
from .files import FileWatcher
from .button import Button
from .hardware import DeviceHardwareManager
from ..utils.config import ConfigManager, get_config
from ..utils.file_utils import *
from ..utils.image_utils import prepare_image_for_deck, load_blank_image, load_error_image
from ..utils import logger


class Coordinator:
    """High-level Stream Deck coordinator.
    
    Orchestrates button management, file watching, and device interaction
    through the DeviceHardwareManager abstraction.
    """
    
    def __init__(self, config_dir: str):
        """Initialize Stream Deck coordinator.
        
        Args:
            config_dir: Configuration directory path
        """
        self.config_dir = config_dir
        self.shutdown_requested = False
        
        # Configuration and file watching
        # Get global config (will initialize automatically if needed)
        self.config_manager = get_config(config_dir)
        debounce_interval = self.config_manager.get_debounce_interval()
        self.debouncer = Debouncer(debounce_interval=debounce_interval)
        self.file_watcher = FileWatcher(self.debouncer, config_dir)
        
        # Button management
        self.buttons: Dict[int, Button] = {}
        
        # Hardware abstraction
        self.hardware = DeviceHardwareManager(
            on_connect=self._on_device_connected,
            on_disconnect=self._on_device_disconnected,
            on_key_press=self._on_key_press
        )
        
        # Event subscriptions
        self.debouncer.subscribe("FILE_CHANGED", self._handle_file_change)
        self.debouncer.subscribe("BUTTON_DIRECTORIES_CHANGED", self._handle_button_directories_changed)
        self.debouncer.subscribe("CONFIG_CHANGED", self._handle_config_change)
        
    def initialize(self) -> bool:
        """Called once at daemon startup to begin device monitoring and file watching.
        
        Returns:
            bool: True if initialization successful
        """
        self.hardware.start_monitoring()
        self.file_watcher.start_watching()
        
        logger.info("Stream Deck coordinator initialized with device monitoring")
        return True
        
    def _get_key_count(self) -> int:
        """Returns device key count or 0 if no device connected."""
        return self.hardware.get_key_count()
        
    def start(self):
        """Called after device connection to start all configured buttons."""
        for button in self.buttons.values():
            button.start()
        logger.info("All buttons started")
        
    def stop(self):
        """Called at daemon shutdown to cleanup all resources and threads."""
        self.shutdown_requested = True
        
        # Clear all buttons before stopping hardware
        self.clear_buttons()
        
        # Stop hardware monitoring
        self.hardware.stop_monitoring()
        
        # Stop all buttons
        for button in self.buttons.values():
            button.stop()
            
        # Stop file watching and debouncer
        self.file_watcher.stop_watching()
        self.debouncer.shutdown()
            
        logger.info("Stream Deck coordinator stopped")
        
    def reload_button(self, button_id: int):
        """Reload specific button.
        
        Args:
            button_id: Button ID to reload (1-based)
        """
        if button_id in self.buttons:
            self.buttons[button_id].stop()
            del self.buttons[button_id]
        
        working_dir = find_button_working_dir(self.config_dir, button_id)
        if working_dir:
            button = Button(working_dir, lambda bid=button_id: self.update_button_image(bid))
            self.buttons[button_id] = button
            if button.load_config():
                button.start()
                self.update_button_image(button_id)
            else:
                # load_config failed, show error image
                self._show_error_image(button_id)
            logger.debug(f"Button {button_id:02d} reloaded")
        else:
            self.clear_buttons(button_id)
            logger.debug(f"Button {button_id:02d} removed")
            
    def reload_all(self):
        """Called when button directories are renamed/moved to recreate all buttons."""
        logger.info("Reloading all buttons...")
        
        for button in self.buttons.values():
            button.stop()
            
        # Recreate buttons (handles renamed/removed directories)
        old_buttons = self.buttons
        self._create_buttons()
        
        for button_id, old_button in old_buttons.items():
            old_button.stop()
                
        self._load_all_buttons()
        self.start()
        
        logger.info("All buttons reloaded")
    
    def update_button_image(self, button_id: int):
        """Update button image on device.
        
        Args:
            button_id: Button ID (1-based)
        """
        if not self.hardware.is_connected():
            return
            
        if button_id not in self.buttons:
            return
            
        button = self.buttons[button_id]
        
        # Get PIL Image from button
        image = button.get_image()
        
        if image:
            # Normal image - prepare and display it
            try:
                image_bytes = prepare_image_for_deck(self.hardware.deck, image)
                if image_bytes:
                    key_index = button_id - 1  # Convert to 0-based index
                    self.hardware.set_key_image(key_index, image_bytes)
                    logger.debug(f"Button {button_id:02d}: Normal image displayed")
                else:
                    logger.error(f"Button {button_id:02d}: Failed to prepare image")
                    button.failed = True
                    self._show_error_image(button_id)
            except Exception as e:
                logger.error(f"Button {button_id:02d}: Error setting image on device: {e}")
                button.failed = True
                self._show_error_image(button_id)
        else:
            # Button has error or no image - show error image
            self._show_error_image(button_id)
        
    
    def clear_buttons(self, button_id: Optional[int] = None):
        """Clear Stream Deck button(s).
        
        Args:
            button_id: Button ID to clear (1-based), or None to clear all
        """
        if not self.hardware.is_connected():
            return
            
        blank_image = load_blank_image()
        if not blank_image:
            return
            
        try:
            image_bytes = prepare_image_for_deck(self.hardware.deck, blank_image)
            if not image_bytes:
                return
            
            if button_id is None:
                key_count = self._get_key_count()
                for key_index in range(key_count):
                    self.hardware.set_key_image(key_index, image_bytes)
                logger.debug(f"All {key_count} buttons cleared")
            else:
                if 1 <= button_id <= self._get_key_count():
                    key_index = button_id - 1
                    self.hardware.set_key_image(key_index, image_bytes)
                    logger.debug(f"Button {button_id:02d} cleared")
                    
        except Exception as e:
            logger.error(f"Error clearing buttons: {e}")
            pass
    
    def _show_error_image(self, button_id: int):
        """Show error image on button.
        
        Args:
            button_id: Button ID (1-based)
        """
        if not self.hardware.is_connected():
            return
            
        error_image = load_error_image()
        if not error_image:
            return
            
        try:
            image_bytes = prepare_image_for_deck(self.hardware.deck, error_image)
            if image_bytes:
                key_index = button_id - 1
                self.hardware.set_key_image(key_index, image_bytes)
                logger.debug(f"Button {button_id:02d}: Error image displayed")
                
        except Exception as e:
            logger.error(f"Button {button_id:02d}: Error showing error image: {e}")
            pass
        
            
    def _create_buttons(self):
        """Scans config directory for button folders and creates Button instances."""
        for button in self.buttons.values():
            button.stop()
        self.buttons.clear()
        
        key_count = self._get_key_count()
        if key_count == 0:
            return
        
        for button_id in range(1, key_count + 1):
            working_dir = find_button_working_dir(self.config_dir, button_id)
            if working_dir:
                button = Button(working_dir, lambda bid=button_id: self.update_button_image(bid))
                self.buttons[button_id] = button
            
    def _load_all_buttons(self):
        """Executes update scripts and loads images for all buttons after device connection."""
        for button_id, button in self.buttons.items():
            if button.load_config():
                self.update_button_image(button_id)
            else:
                # load_config failed, error state is already set in Button.load_config()
                self._show_error_image(button_id)
            
    def _smart_reload_affected_buttons(self, event_type: str, src_path: str, dest_path: str):
        """Smart reload only affected buttons.
        
        Args:
            event_type: Type of directory event
            src_path: Source path
            dest_path: Destination path (for moves)
        """
        affected_buttons = set()
        
        if event_type == "moved":
            src_button_id = extract_button_id_from_path(src_path, self.config_dir, self._get_key_count())
            dest_button_id = extract_button_id_from_path(dest_path, self.config_dir, self._get_key_count())
            
            if src_button_id:
                affected_buttons.add(src_button_id)
            if dest_button_id:
                affected_buttons.add(dest_button_id)
                
        elif event_type in ["created", "deleted", "modified"]:
            button_id = extract_button_id_from_path(src_path, self.config_dir, self._get_key_count())
            if button_id:
                affected_buttons.add(button_id)
        
        logger.debug(f"Reloading affected buttons: {sorted(affected_buttons)}")
        
        for button_id in affected_buttons:
            logger.debug(f"Reloading button {button_id:02d}")
            self.reload_button(button_id)
                
    
    def _on_device_connected(self, deck):
        """Called by DeviceHardwareManager when device connects.
        
        Args:
            deck: Connected Stream Deck device
        """
        if self.buttons:
            logger.warn("Warning: buttons exist during reconnection, cleaning up...")
            for button in self.buttons.values():
                button.stop()
            self.buttons.clear()
            
        # Clear all buttons to ensure clean state on reconnect
        self.clear_buttons()
            
        # Apply configuration settings
        self.config_manager.apply_all_settings(deck, self.debouncer)
            
        self._create_buttons()
        self._load_all_buttons()
        self.start()
        logger.info(f"Device ready with {len(self.buttons)} buttons")
    
    def _on_device_disconnected(self):
        """Called by DeviceHardwareManager when device disconnects."""
        logger.debug(f"Stopping {len(self.buttons)} buttons due to device disconnection...")
        
        # Clear all buttons before cleanup
        self.clear_buttons()
        
        for button_id, button in self.buttons.items():
            logger.debug(f"Stopping button {button_id:02d}")
            button.stop()
        self.buttons.clear()
        logger.debug("All buttons stopped and cleaned up")
    
    def _on_key_press(self, button_id: int):
        """Called by DeviceHardwareManager when physical key is pressed.
        
        Args:
            button_id: Button ID (1-based)
        """
        if button_id in self.buttons:
            logger.debug(f"Button {button_id:02d}: Pressed")
            self.buttons[button_id].handle_press()
    
    def _handle_file_change(self, event):
        """Called by FileWatcher when image or script files change.
        
        Simply tells the button that a file changed, button decides what to do.
        """
        file_path = event.data.get("path", "")
        event_type = event.data.get("event_type", "")
        
        # Only handle relevant event types at the device level
        if event_type not in ["modified", "moved", "created", "closed"]:
            return
        
        button_id = extract_button_id_from_path(file_path, self.config_dir, self._get_key_count())
        if not button_id or button_id not in self.buttons:
            return
            
        filename = os.path.basename(file_path)
        
        # Button decides what to do with the changed file
        file_handled = self.buttons[button_id].file_changed(filename)
        
        # If button says it was an image file, update display
        if file_handled and filename.startswith("image."):
            self.update_button_image(button_id)
        
        
    def _handle_button_directories_changed(self, event):
        """Called by FileWatcher when button directories are created/deleted/renamed.
        
        Stops file watching during reload to prevent infinite loops.
        """
        event_type = event.data.get('event_type')
        src_path = event.data.get('src_path')
        dest_path = event.data.get('dest_path')
        
        logger.debug(f"Button directories changed: {event_type}")
        
        # Critical: prevent infinite reload loops during button directory changes
        # File watcher must be stopped because reload operations trigger new filesystem events
        self.file_watcher.stop_watching()
        
        try:
            # Smart reload - only affected buttons
            self._smart_reload_affected_buttons(event_type, src_path, dest_path)
        finally:
            self.file_watcher.start_watching()
    
    def _handle_config_change(self, event):
        """Called by FileWatcher when config.yaml changes to reload brightness/debounce settings."""
        logger.info("Config file changed, reloading configuration...")
        self.config_manager.reload_config(self.hardware.deck, self.debouncer)

"""Main Stream Deck manager with new architecture."""

import os
import time
import threading
from typing import Optional, Any
from PIL import Image
from StreamDeck.DeviceManager import DeviceManager as SDKDeviceManager
from StreamDeck.ImageHelpers import PILHelper
import pyudev

from ..utils.debouncer import Debouncer
from .files import FileWatcher
from .button import Button
from ..utils.config import ConfigManager
from ..utils.file_utils import *


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
        self.shutdown_requested = False
        
        self.device_monitor_thread = None
        self.device_monitor_lock = threading.Lock()
        self.device_monitor_event = threading.Event()
        self.udev_monitor = None
        self.udev_observer = None
        
        self.config_manager = ConfigManager(config_dir)
        
        debounce_interval = self.config_manager.get_debounce_interval()
        self.debouncer = Debouncer(debounce_interval=debounce_interval)
        self.file_watcher = FileWatcher(self.debouncer, config_dir)
        self.buttons: Dict[int, Button] = {}
        
        self.debouncer.subscribe("FILE_CHANGED", self._handle_file_change)
        
        self.debouncer.subscribe("BUTTON_DIRECTORIES_CHANGED", self._handle_button_directories_changed)
        
        self.debouncer.subscribe("CONFIG_CHANGED", self._handle_config_change)
        
    def initialize(self) -> bool:
        """Called once at daemon startup to begin device monitoring and file watching.
        
        Returns:
            bool: True if initialization successful
        """
        self._start_device_monitoring()
        
        self.file_watcher.start_watching()
        
        print("Stream Deck manager initialized with device monitoring")
        return True
        
    def _get_key_count(self) -> int:
        """Returns device key count or 0 if no device connected.
        
        Safer than calling deck.key_count() directly since device may be None.
        """
        if not self.deck:
            return 0
        try:
            return self.deck.key_count()
        except Exception:
            return 0
        
    def start(self):
        """Called after device connection to start all configured buttons."""
        for button in self.buttons.values():
            button.start()
        print("All buttons started")
        
    def stop(self):
        """Called at daemon shutdown to cleanup all resources and threads."""
        self.shutdown_requested = True
        
        self._stop_udev_monitoring()
        
        self.device_monitor_event.set()
        if self.device_monitor_thread and self.device_monitor_thread.is_alive():
            self.device_monitor_thread.join(timeout=2.0)
        
        for button in self.buttons.values():
            button.stop()
            
        self.file_watcher.stop_watching()
        
        self.debouncer.shutdown()
        
        self._disconnect_device()
            
        print("Stream Deck manager stopped")
        
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
        """Called when button directories are renamed/moved to recreate all buttons."""
        print("Reloading all buttons...")
        
        for button in self.buttons.values():
            button.stop()
            
        # Recreate buttons (handles renamed/removed directories)
        old_buttons = self.buttons
        self._create_buttons()
        
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
        if not self._is_device_connected():
            return
            
        if button_id not in self.buttons:
            return
            
        button = self.buttons[button_id]
        image_path = button._find_image_file()
        
        if not image_path:
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
            pass
        
    @classmethod
    def _load_blank_image(cls) -> Optional[Image.Image]:
        """Loads resources/blank.png once and caches it for clearing buttons efficiently."""
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
        if not self._is_device_connected():
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
                key_count = self._get_key_count()
                for key_index in range(key_count):
                    self.deck.set_key_image(key_index, image_bytes)
                print(f"All {key_count} buttons cleared")
            else:
                if 1 <= button_id <= self._get_key_count():
                    key_index = button_id - 1
                    self.deck.set_key_image(key_index, image_bytes)
                    print(f"Button {button_id:02d} cleared")
                    
        except Exception as e:
            print(f"Error clearing buttons: {e}")
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
                button = Button(working_dir)
                self.buttons[button_id] = button
            
    def _load_all_buttons(self):
        """Executes update scripts and loads images for all buttons after device connection."""
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
        
        print(f"Reloading affected buttons: {sorted(affected_buttons)}")
        
        for button_id in affected_buttons:
            print(f"Reloading button {button_id:02d}")
            self.reload_button(button_id)
                
        
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
        
        if button_id in self.buttons:
            print(f"Button {button_id:02d}: Pressed")
            self.buttons[button_id].handle_press()
    
    def _handle_file_change(self, event):
        """Called by FileWatcher when image or script files change.
        
        Triggers button image updates or script restarts for affected buttons.
        """
        file_path = event.data.get("path", "")
        event_type = event.data.get("event_type", "")
        
        button_id = extract_button_id_from_path(file_path, self.config_dir, self._get_key_count())
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
        """Called by FileWatcher when button directories are created/deleted/renamed.
        
        Stops file watching during reload to prevent infinite loops.
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
    
    def _handle_config_change(self, event):
        """Called by FileWatcher when config.yaml changes to reload brightness/debounce settings."""
        print("Config file changed, reloading configuration...")
        self.config_manager.reload_config(self.deck, self.debouncer)
        
    def _start_device_monitoring(self):
        """Called during initialization to start background thread for USB monitoring."""
        if self.device_monitor_thread is None or not self.device_monitor_thread.is_alive():
            self._start_udev_monitoring()
            self.device_monitor_thread = threading.Thread(
                target=self._device_monitor_loop,
                daemon=True,
                name="DeviceMonitor"
            )
            self.device_monitor_thread.start()
            
    def _device_monitor_loop(self):
        """Background thread that handles USB events and periodic health checks.
        
        Runs until shutdown_requested is True. Triggered by USB events or 10-second timeout.
        """
        print("Device monitoring started")
        
        with self.device_monitor_lock:
            if not self._is_device_connected():
                self._try_connect_device()
        
        health_check_interval = 10.0  # Check health every 10 seconds
        
        while not self.shutdown_requested:
            event_triggered = self.device_monitor_event.wait(timeout=health_check_interval)
            
            if self.shutdown_requested:
                break
                
            with self.device_monitor_lock:
                if event_triggered:
                    self.device_monitor_event.clear()
                    
                    if self.deck and not self._is_device_connected():
                        print("Device disconnected (detected via USB event)")
                        self._handle_device_disconnection()
                
                elif self.deck and not self._is_device_connected():
                    print("Device connection lost (periodic health check)")
                    self._handle_device_disconnection()
                
                # Always try to reconnect if no device connected (handles sleep/wake scenarios)
                if not self._is_device_connected():
                    print("Attempting to reconnect device...")
                    if self._try_connect_device():
                        print("Device reconnected successfully!")
                    else:
                        print("Device reconnection failed, will retry in 10 seconds")
                
        print("Device monitoring stopped")
        
    def _try_connect_device(self) -> bool:
        """Attempts to find and connect to first available Stream Deck device.
        
        Called periodically by monitor thread until connection succeeds.
        Closes any existing connection before opening new one.
        """
        try:
            devices = SDKDeviceManager().enumerate()
            if not devices:
                return False
                
            device = devices[0]
            
            # Close existing connection if any before opening new one
            if self.deck:
                try:
                    self.deck.close()
                except Exception:
                    pass
                    
            device.open()
            device.reset()
            
            self.deck = device
            
            self.config_manager.apply_all_settings(self.deck, self.debouncer)
            
            self.deck.set_key_callback(self._device_key_callback)
            
            device_info = f"{device.deck_type()} (serial: {device.get_serial_number()})"
            print(f"Connected to {device_info} with {self._get_key_count()} buttons")
            
            self._on_device_connected()
            
            return True
            
        except Exception as e:
            print(f"Failed to connect to device: {e}")
            return False
            
    def _is_device_connected(self) -> bool:
        """Returns True if device is physically connected and SDK session is open.
        
        Used by health checks and connection logic to determine device state.
        """
        if not self.deck:
            return False
            
        try:
            connected = self.deck.connected()
            is_open = self.deck.is_open()
            return connected and is_open
        except Exception as e:
            print(f"Device health check failed: {e}")
            return False
            
    def _handle_device_disconnection(self):
        """Called when device health check fails to cleanup buttons and processes."""
        self._disconnect_device()
        
        print(f"Stopping {len(self.buttons)} buttons due to device disconnection...")
        for button_id, button in self.buttons.items():
            print(f"Stopping button {button_id:02d}")
            button.stop()  # This calls ProcessManager.cleanup()
        self.buttons.clear()
        print("All buttons stopped and cleaned up")
        
    def _disconnect_device(self):
        """Closes SDK connection and sets deck to None. Safe to call multiple times."""
        if self.deck:
            try:
                self.deck.close()
            except Exception as e:
                print(f"Error closing device: {e}")
            finally:
                self.deck = None
                
    def _on_device_connected(self):
        """Called after successful device connection to initialize buttons and apply config."""
        if self.buttons:
            print("Warning: buttons exist during reconnection, cleaning up...")
            for button in self.buttons.values():
                button.stop()
            self.buttons.clear()
            
        self._create_buttons()
        self._load_all_buttons()
        self.start()
        print(f"Device ready with {len(self.buttons)} buttons")
        
    def _start_udev_monitoring(self):
        """Sets up pyudev USB monitoring to detect Stream Deck connect/disconnect events."""
        try:
            context = pyudev.Context()
            self.udev_monitor = pyudev.Monitor.from_netlink(context)
            self.udev_monitor.filter_by(subsystem='usb')
            
            self.udev_observer = pyudev.MonitorObserver(
                self.udev_monitor,
                callback=self._on_usb_event,
                name='USBMonitor'
            )
            self.udev_observer.daemon = True
            self.udev_observer.start()
            
            print("USB device monitoring started")
            
        except Exception as e:
            print(f"Failed to start USB monitoring: {e}")
            
    def _stop_udev_monitoring(self):
        """Called during shutdown to stop pyudev observer thread."""
        try:
            if self.udev_observer:
                self.udev_observer.stop()
                self.udev_observer = None
            if self.udev_monitor:
                self.udev_monitor = None
        except Exception as e:
            print(f"Error stopping USB monitoring: {e}")
            
    def _on_usb_event(self, device):
        """Called by pyudev when USB devices are added/removed.
        
        Signals device monitor thread to check for Stream Deck reconnection.
        """
        try:
            action = device.action
            if action in ('add', 'remove'):
                vendor_id = device.get('ID_VENDOR_ID', '').lower()
                product_id = device.get('ID_MODEL_ID', '').lower()
                
                is_potential_streamdeck = (vendor_id == '0fd9' or 
                                         'stream' in device.get('ID_MODEL', '').lower() or
                                         action == 'add')
                
                if is_potential_streamdeck:
                    print(f"USB device {action}: {device.get('DEVNAME', 'unknown')} "
                          f"(vendor: {vendor_id}, model: {product_id})")
                    
                    self.device_monitor_event.set()
                    
        except Exception as e:
            print(f"Error processing USB event: {e}")
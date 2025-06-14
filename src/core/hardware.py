"""Device hardware management for Stream Deck devices."""

import threading
from typing import Optional, Callable, Any
from StreamDeck.DeviceManager import DeviceManager as SDKDeviceManager
import pyudev
from ..utils import logger


class DeviceHardwareManager:
    """Manages hardware-level operations for Stream Deck devices.
    
    Handles device discovery, connection management, USB monitoring,
    and physical key events. Provides a clean interface for higher-level
    components through callbacks.
    """
    
    def __init__(self, 
                 on_connect: Callable[[Any], None],
                 on_disconnect: Callable[[], None],
                 on_key_press: Callable[[int], None]):
        """Initialize hardware manager.
        
        Args:
            on_connect: Callback called when device connects (deck)
            on_disconnect: Callback called when device disconnects
            on_key_press: Callback called on key press (button_id 1-based)
        """
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_key_press = on_key_press
        
        self.deck = None
        self.shutdown_requested = False
        
        # Device monitoring
        self.device_monitor_thread = None
        self.device_monitor_lock = threading.Lock()
        self.device_monitor_event = threading.Event()
        
        # USB monitoring
        self.udev_monitor = None
        self.udev_observer = None
    
    def start_monitoring(self):
        """Start device monitoring and USB event handling."""
        if self.device_monitor_thread is None or not self.device_monitor_thread.is_alive():
            self._start_udev_monitoring()
            self.device_monitor_thread = threading.Thread(
                target=self._device_monitor_loop,
                daemon=True,
                name="DeviceMonitor"
            )
            self.device_monitor_thread.start()
            logger.info("Device hardware monitoring started")
    
    def stop_monitoring(self):
        """Stop device monitoring and cleanup resources."""
        self.shutdown_requested = True
        
        self._stop_udev_monitoring()
        
        self.device_monitor_event.set()
        if self.device_monitor_thread and self.device_monitor_thread.is_alive():
            self.device_monitor_thread.join(timeout=2.0)
        
        self._disconnect_device()
        logger.info("Device hardware monitoring stopped")
    
    def get_key_count(self) -> int:
        """Get number of keys on connected device.
        
        Returns:
            int: Number of keys or 0 if no device connected
        """
        if not self.deck:
            return 0
        try:
            return self.deck.key_count()
        except Exception:
            return 0
    
    def is_connected(self) -> bool:
        """Check if device is physically connected and SDK session is open.
        
        Returns:
            bool: True if device is connected and ready
        """
        if not self.deck:
            return False
            
        try:
            connected = self.deck.connected()
            is_open = self.deck.is_open()
            return connected and is_open
        except Exception as e:
            logger.debug(f"Device health check failed: {e}")
            return False
    
    def set_key_image(self, key_index: int, image_bytes: bytes):
        """Set image on specific key.
        
        Args:
            key_index: Key index (0-based)
            image_bytes: Image data in device-native format
        """
        if not self.is_connected():
            return
            
        try:
            self.deck.set_key_image(key_index, image_bytes)
        except Exception as e:
            logger.error(f"Error setting key {key_index} image: {e}")
    
    def apply_settings(self, brightness: int):
        """Apply device settings.
        
        Args:
            brightness: Brightness level (0-100)
        """
        if not self.is_connected():
            return
            
        try:
            self.deck.set_brightness(brightness)
        except Exception as e:
            logger.error(f"Error setting brightness: {e}")
    
    def get_device_info(self) -> str:
        """Get device information string.
        
        Returns:
            str: Device information or empty string if no device
        """
        if not self.deck:
            return ""
            
        try:
            return f"{self.deck.deck_type()} (serial: {self.deck.get_serial_number()})"
        except Exception:
            return "Unknown device"
    
    def _device_monitor_loop(self):
        """Background thread that handles USB events and periodic health checks."""
        logger.info("Device monitoring started")
        
        with self.device_monitor_lock:
            if not self.is_connected():
                self._try_connect_device()
        
        health_check_interval = 10.0  # Check health every 10 seconds
        
        while not self.shutdown_requested:
            event_triggered = self.device_monitor_event.wait(timeout=health_check_interval)
            
            if self.shutdown_requested:
                break
                
            with self.device_monitor_lock:
                if event_triggered:
                    self.device_monitor_event.clear()
                    
                    if self.deck and not self.is_connected():
                        logger.warn("Device disconnected (detected via USB event)")
                        self._handle_device_disconnection()
                
                elif self.deck and not self.is_connected():
                    logger.warn("Device connection lost (periodic health check)")
                    self._handle_device_disconnection()
                
                # Always try to reconnect if no device connected
                if not self.is_connected():
                    logger.info("Attempting to reconnect device...")
                    if self._try_connect_device():
                        logger.info("Device reconnected successfully!")
                    else:
                        logger.warn("Device reconnection failed, will retry in 10 seconds")
                
        logger.info("Device monitoring stopped")
    
    def _try_connect_device(self) -> bool:
        """Attempt to find and connect to first available Stream Deck device.
        
        Returns:
            bool: True if connection successful
        """
        try:
            devices = SDKDeviceManager().enumerate()
            if not devices:
                return False
                
            device = devices[0]
            
            # Close existing connection if any
            if self.deck:
                try:
                    self.deck.close()
                except Exception:
                    pass
                    
            device.open()
            device.reset()
            
            self.deck = device
            self.deck.set_key_callback(self._device_key_callback)
            
            device_info = self.get_device_info()
            logger.info(f"Connected to {device_info} with {self.get_key_count()} buttons")
            
            # Notify higher-level components
            self.on_connect(self.deck)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to device: {e}")
            return False
    
    def _handle_device_disconnection(self):
        """Handle device disconnection cleanup."""
        self._disconnect_device()
        self.on_disconnect()
    
    def _disconnect_device(self):
        """Close SDK connection and reset deck to None."""
        if self.deck:
            try:
                self.deck.close()
            except Exception as e:
                logger.error(f"Error closing device: {e}")
            finally:
                self.deck = None
    
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
        logger.debug(f"Hardware key {button_id:02d} pressed")
        self.on_key_press(button_id)
    
    def _start_udev_monitoring(self):
        """Set up pyudev USB monitoring to detect device connect/disconnect."""
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
            
            logger.info("USB device monitoring started")
            
        except Exception as e:
            logger.error(f"Failed to start USB monitoring: {e}")
    
    def _stop_udev_monitoring(self):
        """Stop pyudev observer thread."""
        try:
            if self.udev_observer:
                self.udev_observer.stop()
                self.udev_observer = None
            if self.udev_monitor:
                self.udev_monitor = None
        except Exception as e:
            logger.error(f"Error stopping USB monitoring: {e}")
    
    def _on_usb_event(self, device):
        """Handle USB device add/remove events.
        
        Args:
            device: pyudev device object
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
                    logger.debug(f"USB device {action}: {device.get('DEVNAME', 'unknown')} "
                          f"(vendor: {vendor_id}, model: {product_id})")
                    
                    self.device_monitor_event.set()
                    
        except Exception as e:
            logger.error(f"Error processing USB event: {e}")
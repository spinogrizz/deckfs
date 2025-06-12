"""Main stream-deck-fs daemon class."""

import os
import time
import threading
from StreamDeck.DeviceManager import DeviceManager
from watchdog.observers import Observer

from ..handlers.file_handler import ImageChangeHandler
from ..utils.device import DeviceManager as SDDeviceManager
from ..utils.config import CONFIG_DIR


class StreamDeckDaemon:
    """Main daemon class for Stream Deck management."""
    
    def __init__(self, config_dir=None):
        """Initialize daemon.
        
        Args:
            config_dir: Path to configuration directory
        """
        self.config_dir = config_dir or CONFIG_DIR
        self.device_manager = None
        self.observer = None
        self.running = False
        
    def initialize_device(self):
        """Initialize Stream Deck device."""
        self.device_manager = SDDeviceManager()
        if not self.device_manager.initialize():
            raise RuntimeError("Failed to initialize Stream Deck")
    
    def start(self):
        """Start daemon."""
        if self.running:
            return
            
        print("Starting stream-deck-fs daemon...")
        
        # Initialize device
        self.initialize_device()
        
        # Load initial images
        self.device_manager.load_initial_images(self.config_dir)
        
        # Setup file watcher
        self.observer = Observer()
        self.observer.schedule(
            ImageChangeHandler(self.device_manager), 
            path=self.config_dir, 
            recursive=True
        )
        self.observer.start()
        
        self.running = True
        print(f"Daemon started. Monitoring directory: {self.config_dir}")
        print("Press Ctrl+C to exit")
        
    def stop(self):
        """Stop daemon."""
        if not self.running:
            return
            
        print("Shutting down daemon...")
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
            
        if self.device_manager:
            self.device_manager.cleanup()
            
        self.running = False
        print("Daemon stopped")
    
    def run(self):
        """Run main daemon loop."""
        try:
            self.start()
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
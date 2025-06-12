"""Main stream-deck-fs daemon class."""

import time
from .devices import StreamDeckManager
from ..utils.config import CONFIG_DIR


class StreamDeckDaemon:
    """Main daemon class for Stream Deck management."""
    
    def __init__(self, config_dir=None):
        """Initialize daemon.
        
        Args:
            config_dir: Path to configuration directory
        """
        self.config_dir = config_dir or CONFIG_DIR
        self.manager = None
        self.running = False
        
    def start(self):
        if self.running:
            return
            
        print("Starting stream-deck-fs daemon...")
        
        # Initialize Stream Deck manager
        self.manager = StreamDeckManager(self.config_dir)
        if not self.manager.initialize():
            raise RuntimeError("Failed to initialize Stream Deck")
            
        # Start all buttons
        self.manager.start()
        
        self.running = True
        print(f"Daemon started. Monitoring directory: {self.config_dir}")
        print("Press Ctrl+C to exit")
        
    def stop(self):
        if not self.running:
            return
            
        print("Shutting down daemon...")
        
        if self.manager:
            self.manager.stop()
            
        self.running = False
        print("Daemon stopped")
    
    def run(self):
        try:
            self.start()
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
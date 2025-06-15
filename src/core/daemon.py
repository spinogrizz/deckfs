import time
import setproctitle
from .coordinator import Coordinator
from ..utils.config import CONFIG_DIR
from ..utils import logger


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
        
        # Set recognizable process title
        setproctitle.setproctitle("deckfs-daemon")
            
        logger.info("Starting deckfs daemon...")
        
        # Initialize Stream Deck coordinator
        self.manager = Coordinator(self.config_dir)
        self.manager.initialize()
        
        self.running = True
        logger.info(f"Daemon started. Monitoring directory: {self.config_dir}")
        logger.info("Daemon will automatically connect when Stream Deck is available")
        logger.info("Press Ctrl+C to exit")
        
    def stop(self):
        if not self.running:
            return
            
        logger.info("Shutting down daemon...")
        
        if self.manager:
            self.manager.stop()
            
        self.running = False
        logger.info("Daemon stopped")
    
    def run(self):
        try:
            self.start()
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
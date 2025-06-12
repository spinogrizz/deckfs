"""Stream Deck device manager."""

import os
import subprocess
from PIL import Image
from StreamDeck.DeviceManager import DeviceManager as SDKDeviceManager
from StreamDeck.ImageHelpers import PILHelper

from .config import DEFAULT_BRIGHTNESS, SUPPORTED_SCRIPTS


class DeviceManager:
    """Stream Deck device manager."""
    
    def __init__(self):
        """Initialize manager."""
        self.deck = None
        self.key_count = 0
        
    def initialize(self):
        """Initialize Stream Deck device.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            devices = SDKDeviceManager().enumerate()
            if not devices:
                print("Stream Deck device not found")
                return False
                
            self.deck = devices[0]  # use first device
            self.deck.open()
            self.deck.reset()  # clear buttons
            self.deck.set_brightness(DEFAULT_BRIGHTNESS)
            
            self.key_count = self.deck.key_count()
            print(f"Found device: {self.deck.deck_type()} with {self.key_count} buttons")
            
            # Register button event callback
            self.deck.set_key_callback(self._key_change_callback)
            
            return True
            
        except Exception as e:
            print(f"Stream Deck initialization error: {e}")
            return False
    
    def update_key_image(self, key_index, button_dir=None):
        """Update button image.
        
        Args:
            key_index: Button index (starting from 0)
            button_dir: Optional button directory name (for external calls)
        """
        if not self.deck:
            return
            
        config_dir = os.path.expanduser("~/.local/streamdeck")
        
        # Use provided button_dir or find folder that starts with the key number
        if button_dir:
            folder_path = os.path.join(config_dir, button_dir)
            if not os.path.isdir(folder_path):
                folder_path = None
        else:
            # Find folder that starts with the key number (e.g., "01_light", "02_launch_app")
            button_num = f"{key_index+1:02d}"
            folder_path = None
            
            if os.path.exists(config_dir):
                for folder in os.listdir(config_dir):
                    if folder.startswith(button_num) and os.path.isdir(os.path.join(config_dir, folder)):
                        folder_path = os.path.join(config_dir, folder)
                        break
        
        if not folder_path:
            button_ref = button_dir if button_dir else f"button {f'{key_index+1:02d}'}"
            print(f"No folder found for {button_ref}")
            return
            
        img_path = os.path.join(folder_path, "image.png")
        
        # Check file or symlink existence
        if not (os.path.isfile(img_path) or os.path.islink(img_path)):
            print(f"Image file not found: {img_path}")
            return
            
        # If symlink, get real path
        if os.path.islink(img_path):
            real_path = os.path.realpath(img_path)
            if not os.path.isfile(real_path):
                print(f"Symlink points to non-existent file: {real_path}")
                return
            print(f"Updating button {key_index+1} image from {real_path}")
        else:
            print(f"Updating button {key_index+1} image from {img_path}")
        
        try:
            # Load and scale image to button size
            image = Image.open(img_path)
            # Convert to Stream Deck format (BGR or JPEG as needed)
            image_bytes = PILHelper.to_native_format(
                self.deck, 
                PILHelper.create_scaled_image(self.deck, image)
            )
            # Set image on button
            self.deck.set_key_image(key_index, image_bytes)
            print(f"Button {key_index+1} image updated successfully")
            
        except Exception as e:
            print(f"Error updating button {key_index+1} image: {e}")
    
    def load_initial_images(self, config_dir):
        """Load initial images on all buttons.
        
        Args:
            config_dir: Path to configuration directory
        """
        for key in range(self.key_count):
            self.update_key_image(key)
    
    def _key_change_callback(self, deck, key, state):
        """Button press handler.
        
        Args:
            deck: Stream Deck object
            key: Button index
            state: Button state (True - pressed, False - released)
        """
        if not state:  # respond only to press
            return
            
        config_dir = os.path.expanduser("~/.local/streamdeck")
        button_num = f"{key+1:02d}"
        
        # Find folder that starts with the key number
        folder_path = None
        folder_name = None
        
        if os.path.exists(config_dir):
            for folder in os.listdir(config_dir):
                if folder.startswith(button_num) and os.path.isdir(os.path.join(config_dir, folder)):
                    folder_path = os.path.join(config_dir, folder)
                    folder_name = folder
                    break
        
        if not folder_path:
            print(f"No folder found for button {button_num}")
            return
            
        print(f"Button {folder_name} pressed")
        
        # Search and run action script
        for ext, cmd in SUPPORTED_SCRIPTS.items():
            script_path = os.path.join(folder_path, f"action.{ext}")
            if os.path.isfile(script_path):
                # Run script via appropriate interpreter
                subprocess.Popen(cmd + [script_path], cwd=folder_path)
                break
    
    def cleanup(self):
        """Clean up resources."""
        if self.deck:
            self.deck.close()
            self.deck = None
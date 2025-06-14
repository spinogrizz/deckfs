"""Image utility functions for Stream Deck operations."""

import os
from typing import Optional
from PIL import Image
from StreamDeck.ImageHelpers import PILHelper
from . import logger


class ImageCache:
    """Simple image cache for frequently used images."""
    
    _blank_image: Optional[Image.Image] = None
    _error_image: Optional[Image.Image] = None


def load_blank_image() -> Optional[Image.Image]:
    """Load and cache blank.png image for clearing buttons.
    
    Returns:
        Optional[Image.Image]: Blank image or None if loading failed
    """
    if ImageCache._blank_image is None:
        try:
            # Navigate up from src/utils/image_utils.py to find project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            blank_path = os.path.join(project_root, 'resources', 'blank.png')
            ImageCache._blank_image = Image.open(blank_path)
            logger.debug(f"Blank image loaded: {blank_path}")
        except Exception as e:
            logger.error(f"Error loading blank image: {e}")
            return None
    return ImageCache._blank_image


def load_error_image() -> Optional[Image.Image]:
    """Load and cache error.png image for showing button errors.
    
    Returns:
        Optional[Image.Image]: Error image or None if loading failed
    """
    if ImageCache._error_image is None:
        try:
            # Navigate up from src/utils/image_utils.py to find project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            error_path = os.path.join(project_root, 'resources', 'error.png')
            ImageCache._error_image = Image.open(error_path)
            logger.debug(f"Error image loaded: {error_path}")
        except Exception as e:
            logger.error(f"Error loading error image: {e}")
            return None
    return ImageCache._error_image


def prepare_image_for_deck(deck, image: Image.Image) -> Optional[bytes]:
    """Prepare image for Stream Deck device (scale and convert format).
    
    Args:
        deck: Stream Deck device instance
        image: PIL Image to prepare
        
    Returns:
        Optional[bytes]: Image data in device-native format or None if failed
    """
    try:
        scaled_image = PILHelper.create_scaled_image(deck, image)
        image_bytes = PILHelper.to_native_format(deck, scaled_image)
        return image_bytes
    except Exception as e:
        logger.error(f"Error preparing image for deck: {e}")
        return None



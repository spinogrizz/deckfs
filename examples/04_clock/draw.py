#!/usr/bin/env python3

import sys
import io
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# Stream Deck button size (72x72 pixels for most models)
SIZE = (72, 72)
BACKGROUND_COLOR = (0, 0, 0)  # Black background
TEXT_COLOR = (255, 255, 255)  # White text

def generate_clock_image():
    """Generate a clock image with current time."""
    # Create image
    image = Image.new('RGB', SIZE, BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)
    
    # Get current time
    now = datetime.now()
    hours = now.strftime("%H")
    minutes = now.strftime("%M")
    
    try:
        # Try to use a system font - will fall back to default if not found
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    except (OSError, IOError):
        # Fall back to default font
        font = ImageFont.load_default()
    
    # Draw hours (centered, upper portion)
    draw.text((36, 20), hours, font=font, fill=TEXT_COLOR, anchor='mm')
    
    # Draw minutes (centered, lower portion)  
    draw.text((36, 50), minutes, font=font, fill=TEXT_COLOR, anchor='mm')
    
    return image

def send_image(image):
    """Send image using magic delimiters protocol."""
    # Save image to bytes buffer
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    image_bytes = buffer.getvalue()
    
    # Send with magic delimiters
    sys.stdout.buffer.write(b"DECKFS_IMG_START\n")
    sys.stdout.buffer.write(f"{len(image_bytes)}\n".encode())
    sys.stdout.buffer.write(image_bytes)
    sys.stdout.buffer.write(b"DECKFS_IMG_END\n")
    sys.stdout.buffer.flush()

def main():
    """Generate clock images continuously every minute."""
    try:
        while True:
            image = generate_clock_image()
            send_image(image)
            
            # Wait until next minute boundary
            now = datetime.now()
            seconds_to_wait = 60 - now.second
            time.sleep(seconds_to_wait)
            
    except Exception as e:
        # Log error to stderr and exit with error code
        print(f"Error generating clock image: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
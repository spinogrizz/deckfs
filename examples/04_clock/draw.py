#!/usr/bin/env python3

import sys
import io
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

def main():
    """Generate clock image and output to stdout as PNG."""
    try:
        image = generate_clock_image()
        
        # Save image to bytes buffer
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        
        # Output binary data to stdout
        sys.stdout.buffer.write(buffer.getvalue())
        
    except Exception as e:
        # Log error to stderr and exit with error code
        print(f"Error generating clock image: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
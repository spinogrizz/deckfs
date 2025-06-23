#!/usr/bin/env python3

import sys
import io
import os
from PIL import Image, ImageDraw, ImageFont

# Stream Deck button size (72x72 pixels for most models)
SIZE = (72, 72)
TEXT_COLOR = (255, 255, 255)  # White text

def get_load_average():
    """Get current system load average (1-minute)."""
    try:
        # Read from /proc/loadavg
        with open('/proc/loadavg', 'r') as f:
            load_data = f.read().strip().split()
            return float(load_data[0])  # 1-minute load average
    except (OSError, ValueError, IndexError):
        return 0.0

def get_background_color(load_avg):
    """Get background color based on load average."""
    if load_avg < 1.5:
        return (0, 0, 0)        # Black - low load
    elif load_avg < 3.0:
        return (200, 200, 0)    # Yellow - medium load  
    else:
        return (200, 0, 0)      # Red - high load

def generate_load_image():
    """Generate a load average display image."""
    # Get current load
    load_avg = get_load_average()
    
    # Create image with appropriate background color
    background_color = get_background_color(load_avg)
    image = Image.new('RGB', SIZE, background_color)
    draw = ImageDraw.Draw(image)
    
    # Format load average to 1 decimal place
    load_str = f"{load_avg:.1f}"
    
    try:
        # Try to use a system font - will fall back to default if not found
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except (OSError, IOError):
        # Fall back to default font
        font = ImageFont.load_default()
    
    # Calculate text position for centering
    bbox = draw.textbbox((0, 0), load_str, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Center the text - учитываем смещение bbox
    x = (SIZE[0] - text_width) // 2 - bbox[0]
    y = (SIZE[1] - text_height) // 2 - bbox[1]
    
    # Draw the load average
    draw.text((x, y), load_str, fill=TEXT_COLOR, font=font)
    
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
    """Generate load average images continuously every 10 seconds."""
    try:
        import time
        
        while True:
            image = generate_load_image()
            send_image(image)
            
            # Wait 10 seconds before next update
            time.sleep(10)
            
    except Exception as e:
        # Log error to stderr and exit with error code
        print(f"Error generating load average image: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
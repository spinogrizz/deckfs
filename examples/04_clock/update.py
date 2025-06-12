import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

def draw_clock():
    now = datetime.now()
    hours = now.strftime("%H")
    minutes = now.strftime("%M")
    
    image = Image.new('RGB', (72, 72), color='black')
    draw = ImageDraw.Draw(image)
    
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 24)
    except:
        font = ImageFont.load_default()
    
    draw.text((36, 20), hours, font=font, fill='white', anchor='mm')
    draw.text((36, 50), minutes, font=font, fill='white', anchor='mm')
    
    image_path = os.path.join(os.path.dirname(__file__), 'image.png')
    image.save(image_path)

def main():
    draw_clock()

if __name__ == "__main__":
    main()

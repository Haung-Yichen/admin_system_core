"""
Image Processor for Rich Menu.

Converts the generate image to strict LINE Rich Menu requirements:
- Format: JPEG
- Size: 2500x1686
- Max file size: 1MB
"""

from pathlib import Path
from PIL import Image
import os

def process_image():
    input_path = Path(__file__).parent.parent / "static" / "rich_menu.png"
    output_path = Path(__file__).parent.parent / "static" / "rich_menu_final.jpg"
    
    if not input_path.exists():
        print(f"❌ Input image not found: {input_path}")
        return

    try:
        img = Image.open(input_path)
        
        # Convert to RGB (remove alpha)
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        else:
            img = img.convert('RGB')

        # Resize if needed (ensure strict 2500x1686)
        target_size = (2500, 1686)
        if img.size != target_size:
            print(f"⚠️ Resizing image from {img.size} to {target_size}")
            img = img.resize(target_size, Image.Resampling.LANCZOS)
        
        # Save as JPEG with quality adjustment to fit under 1MB
        quality = 95
        while True:
            img.save(output_path, 'JPEG', quality=quality)
            size = os.path.getsize(output_path)
            if size < 1024 * 1024:  # Under 1MB
                break
            quality -= 5
            if quality < 30:
                print("❌ Cannot compress image enough")
                return

        print(f"✅ Image processed: {output_path}")
        print(f"   Size: {size/1024:.1f} KB")
        print(f"   Dimensions: {img.size}")
        
    except Exception as e:
        print(f"❌ Error processing image: {e}")

if __name__ == "__main__":
    process_image()

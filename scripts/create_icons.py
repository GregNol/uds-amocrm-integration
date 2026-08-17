import os
from PIL import Image, ImageDraw, ImageFont


def create_image(width: int, height: int, text: str, output_path: str, radius: int = 12):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background gradient #ec1353 to #7928ca
    for y in range(height):
        ratio = y / height
        r = int(236 * (1 - ratio) + 121 * ratio)
        g = int(19 * (1 - ratio) + 40 * ratio)
        b = int(83 * (1 - ratio) + 202 * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # Mask to rounded rectangle
    mask = Image.new("L", (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), (width - 1, height - 1)], radius=radius, fill=255)

    rounded_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rounded_img.paste(img, (0, 0), mask=mask)

    draw = ImageDraw.Draw(rounded_img)
    font = ImageFont.load_default()

    # Draw UDS text in center
    bbox = draw.textbbox((0, 0), text, font=font) if hasattr(draw, "textbbox") else (0, 0, width * 0.5, height * 0.3)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (width - tw) // 2
    ty = (height - th) // 2
    draw.text((tx, ty), text, fill=(255, 255, 255, 255), font=font)

    rounded_img.save(output_path, format="PNG")
    print(f"Created: {output_path} ({width}x{height})")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    images_dir = os.path.join(base_dir, "widget", "images")
    
    # Official amoCRM image specifications:
    # 1. logo_main.png -> 400x272 px (Widget Main Banner)
    create_image(width=400, height=272, text="UDS", output_path=os.path.join(images_dir, "logo_main.png"), radius=18)
    
    # 2. logo.png -> 130x100 px (Widget Standard Logo)
    create_image(width=130, height=100, text="UDS", output_path=os.path.join(images_dir, "logo.png"), radius=10)
    
    # 3. logo_small.png -> 84x84 px (Widget Small Logo)
    create_image(width=84, height=84, text="UDS", output_path=os.path.join(images_dir, "logo_small.png"), radius=8)
    
    # 4. icon.png -> 60x60 px (Widget Icon)
    create_image(width=60, height=60, text="UDS", output_path=os.path.join(images_dir, "icon.png"), radius=8)
    
    # 5. icon_small.png -> 30x30 px (Widget Small Icon)
    create_image(width=30, height=30, text="UDS", output_path=os.path.join(images_dir, "icon_small.png"), radius=5)

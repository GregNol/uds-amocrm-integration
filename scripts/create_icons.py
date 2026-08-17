import os
from PIL import Image, ImageDraw, ImageFont


def create_gradient_icon(size: int, text: str, output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw rounded rectangle with gradient effect
    radius = int(size * 0.22)
    # Background gradient
    for y in range(size):
        ratio = y / size
        # #ec1353 to #7928ca
        r = int(236 * (1 - ratio) + 121 * ratio)
        g = int(19 * (1 - ratio) + 40 * ratio)
        b = int(83 * (1 - ratio) + 202 * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Mask to rounded rectangle
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), (size - 1, size - 1)], radius=radius, fill=255)

    rounded_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rounded_img.paste(img, (0, 0), mask=mask)

    draw = ImageDraw.Draw(rounded_img)
    # Simple text rendering
    # Try basic drawing for UDS text
    try:
        font_size = int(size * 0.38)
        font = ImageFont.load_default()
    except Exception:
        font = None

    # Draw UDS letters in center
    bbox = draw.textbbox((0, 0), text, font=font) if hasattr(draw, "textbbox") else (0, 0, size * 0.6, size * 0.3)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) // 2
    ty = (size - th) // 2
    draw.text((tx, ty), text, fill=(255, 255, 255, 255), font=font)

    rounded_img.save(output_path, format="PNG")
    print(f"Created: {output_path} ({size}x{size})")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    images_dir = os.path.join(base_dir, "widget", "images")
    create_gradient_icon(size=120, text="UDS", output_path=os.path.join(images_dir, "logo.png"))
    create_gradient_icon(size=60, text="UDS", output_path=os.path.join(images_dir, "icon.png"))
    create_gradient_icon(size=30, text="UDS", output_path=os.path.join(images_dir, "icon_small.png"))

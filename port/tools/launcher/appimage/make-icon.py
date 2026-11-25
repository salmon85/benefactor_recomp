#!/usr/bin/env python3
"""Draw the launcher icon (original artwork, no game assets).

A dark tile with a gold "B" over a small pixel-block motif, saved as a 256x256
PNG for the AppImage desktop entry.
"""
import sys
from PIL import Image, ImageDraw, ImageFont

SIZE = 256


def font(size):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main(out: str) -> int:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Rounded dark tile.
    d.rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=44,
                        fill=(18, 22, 34, 255), outline=(64, 74, 106, 255), width=6)

    # Pixel-block motif along the bottom (original, generic "tiles").
    cols = [(214, 168, 62), (176, 120, 52), (120, 156, 96), (92, 122, 168)]
    x0, y0, cell = 52, 170, 24
    for row in range(2):
        for col in range(4):
            if (row + col) % 3 == 0:
                continue
            x = x0 + col * cell
            y = y0 + row * cell
            d.rectangle((x, y, x + cell - 4, y + cell - 4), fill=cols[(row + col) % 4] + (255,))

    # Gold "B".
    f = font(140)
    text = "B"
    box = d.textbbox((0, 0), text, font=f)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((SIZE - w) / 2 - box[0], 96 - h / 2 - box[1]), text, font=f,
           fill=(232, 186, 74, 255))

    img.save(out)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "benefactor.png"))

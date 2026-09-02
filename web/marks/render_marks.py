"""Renders each specialist's initial as a transparent PNG in Pinyon Script.

Rendered from the font rather than cropped out of a screenshot: cropping a
letter off a dark background leaves a dark fringe baked into the anti-aliased
edge, which shows up as a halo the moment the mark is placed on anything
lighter. Drawing straight from the outlines gives a genuine alpha channel and
any resolution you ask for.

Pinyon Script is SIL Open Font License 1.1, so the font and everything made
with it can ship in this repository.

    python web/marks/render_marks.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = Path(__file__).parent / "PinyonScript-Regular.ttf"
OUT = Path(__file__).parent

# The six specialists and the letter each one carries. chain_of_title and
# churn_early_warning both start with C, as do premiere_pulse and
# performance_war_room, so the letters are drawn from further into each name
# to keep all six distinct.
AGENTS = [
    ("C", "chain_of_title"),
    ("G", "ghost_ads"),
    ("F", "fraud_sentinel"),
    ("P", "premiere_pulse"),
    ("W", "performance_war_room"),
    ("E", "churn_early_warning"),
]

SIZE = 900          # render size; the glyph is cropped out of this canvas
PAD = 24            # transparent margin kept around the inked pixels
COLOUR = (255, 255, 255)   # white, so it can be tinted downstream


def render(letter: str, name: str) -> tuple[str, int, int]:
    font = ImageFont.truetype(str(FONT), SIZE)
    canvas = Image.new("RGBA", (SIZE * 2, SIZE * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.text((SIZE // 2, SIZE // 2), letter, font=font, fill=COLOUR + (255,))

    # Crop to the glyph's own ink, not to the font's metrics box: script faces
    # carry wildly different side bearings and ascenders per letter, so a
    # metrics crop would leave each PNG padded differently and the six would
    # not sit consistently when placed side by side.
    bbox = canvas.getbbox()
    glyph = canvas.crop(bbox)

    out = Image.new("RGBA", (glyph.width + PAD * 2, glyph.height + PAD * 2), (0, 0, 0, 0))
    out.paste(glyph, (PAD, PAD), glyph)
    path = OUT / f"{letter}-{name}.png"
    out.save(path)
    return path.name, out.width, out.height


def main() -> None:
    if not FONT.exists():
        raise SystemExit(f"font not found: {FONT}")
    for letter, name in AGENTS:
        fn, w, h = render(letter, name)
        print(f"  {fn:<40} {w}x{h}")


if __name__ == "__main__":
    main()

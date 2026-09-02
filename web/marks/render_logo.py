"""Renders the Backlot aperture mark to shippable logo files.

The mark is six iris blades — one per specialist — around a hexagonal opening.
One blade outline rotated six times, which is why the six specialist marks are
visibly the same object with a different blade lit.

Outputs into web/marks/:
    backlot-mark.svg            scalable, uses currentColor so it inherits ink
    backlot-mark-brass.png      transparent, brand brass
    backlot-mark-white.png      transparent, white for dark grounds
    backlot-mark-black.png      transparent, black for light grounds
    backlot-lockup-*.png        mark + wordmark, when Caveat is available

    python web/marks/render_logo.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent

# The blade, in the same 100x100 space the console's inline SVG uses. Inner
# edge sits on a r=20 hexagon (the opening); the outer edge is swept 24 degrees
# forward on r=45, which is what makes six of them read as a closing aperture
# rather than a plain hexagonal ring.
BLADE = [(50.70, 30.01), (66.96, 39.40), (94.56, 43.74), (69.73, 9.55)]
BRASS = (201, 169, 97)
WHITE = (255, 255, 255)
BLACK = (10, 10, 12)
SS = 4  # supersample factor; the blades have long diagonals that alias badly


def rotate(p: tuple[float, float], deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    x, y = p[0] - 50, p[1] - 50
    return (50 + x * math.cos(a) - y * math.sin(a),
            50 + x * math.sin(a) + y * math.cos(a))


def mark_png(size: int, colour: tuple[int, int, int], path: Path) -> None:
    big = size * SS
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for k in range(6):
        poly = [rotate(p, k * 60) for p in BLADE]
        d.polygon([(x / 100 * big, y / 100 * big) for x, y in poly], fill=colour + (255,))
    im.resize((size, size), Image.LANCZOS).save(path)


def mark_svg(path: Path) -> None:
    blades = "\n".join(
        f'    <use href="#b" transform="rotate({k * 60} 50 50)"/>' for k in range(6))
    d = " ".join(f"{'M' if i == 0 else 'L'}{x} {y}" for i, (x, y) in enumerate(BLADE)) + " Z"
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
        'width="512" height="512" role="img" aria-label="The Backlot">\n'
        '  <title>The Backlot</title>\n'
        f'  <defs><path id="b" d="{d}"/></defs>\n'
        f'  <g fill="currentColor" color="#c9a961">\n{blades}\n  </g>\n'
        '</svg>\n', encoding="utf-8")


def find_caveat() -> Path | None:
    for p in [OUT / "Caveat-Bold.ttf", OUT / "Caveat-Regular.ttf"]:
        if p.exists():
            return p
    win = Path("C:/Windows/Fonts")
    for n in ("Caveat-Bold.ttf", "caveat.ttf", "Caveat-Regular.ttf"):
        if (win / n).exists():
            return win / n
    return None


def lockup(size: int, colour: tuple[int, int, int], font_path: Path, path: Path) -> None:
    """Mark left, wordmark right, on one transparent canvas."""
    mark = size
    fs = int(size * 0.78)
    font = ImageFont.truetype(str(font_path), fs)
    # Caveat ships as a variable font; without pinning the weight axis it
    # renders at Regular, which is too light to hold its own beside the mark.
    try:
        font.set_variation_by_axes([700])
    except Exception:
        pass
    text = "THE BACKLOT"

    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    tb = probe.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]

    gap = int(size * 0.34)
    pad = int(size * 0.12)
    W, H = pad * 2 + mark + gap + tw, pad * 2 + max(mark, th)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    tmp = OUT / "_tmp_mark.png"
    mark_png(mark, colour, tmp)
    m = Image.open(tmp)
    im.paste(m, (pad, (H - mark) // 2), m)
    tmp.unlink()

    d = ImageDraw.Draw(im)
    d.text((pad + mark + gap - tb[0], (H - th) // 2 - tb[1]), text, font=font,
           fill=colour + (255,))
    im.save(path)


def main() -> None:
    mark_svg(OUT / "backlot-mark.svg")
    print(f"  {'backlot-mark.svg':<34} vector")
    for name, colour in (("brass", BRASS), ("white", WHITE), ("black", BLACK)):
        p = OUT / f"backlot-mark-{name}.png"
        mark_png(1024, colour, p)
        print(f"  {p.name:<34} 1024x1024")

    f = find_caveat()
    if not f:
        print("  Caveat not found locally — skipping lockups "
              "(drop Caveat-Bold.ttf in web/marks/ and re-run)")
        return
    for name, colour in (("brass", BRASS), ("white", WHITE), ("black", BLACK)):
        p = OUT / f"backlot-lockup-{name}.png"
        lockup(256, colour, f, p)
        im = Image.open(p)
        print(f"  {p.name:<34} {im.width}x{im.height}")


if __name__ == "__main__":
    main()

"""Two tonality samples for the specialist initials, side by side with the
size they actually ship at.

Rendered rather than screenshotted so the 54px row is a true 54px — a browser
capture of a scaled pane would misreport exactly the thing being judged.

    python design/render_tone_samples.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from render_plate import (GOLD, INK, aperture_mask, blade_centre, font,
                          letter_mask, plate_metal, tracked, PINYON)

HERE = Path(__file__).parent
AGENTS = [("C", "CHAIN OF TITLE"), ("G", "GHOST ADS"), ("F", "FRAUD SENTINEL"),
          ("P", "PREMIERE PULSE"), ("W", "WAR ROOM"), ("E", "EARLY WARNING")]

# B — black chrome: dark metal carrying the same reflection flip as the gold,
# so it still reads as a material rather than as flat type.
BLACK_CHROME = [
    (0.00, (107, 114, 128)), (0.18, ( 57,  65,  76)), (0.40, ( 18,  22,  28)),
    (0.50, (  5,   7,  10)), (0.55, (139, 149, 163)), (0.72, ( 43,  50,  60)),
    (1.00, ( 13,  17,  22)),
]
# W — near-white. At 54px a mark's letter is only about 8px tall and Pinyon's
# hairlines fall under a pixel, so a ramp with a dark band in the middle simply
# erases them. This one keeps only a light silver dip: enough to read as metal
# at full size, bright enough to survive at shipping size.
BRIGHT = [
    (0.00, (255, 255, 255)), (0.30, (255, 255, 255)), (0.46, (228, 237, 246)),
    (0.52, (196, 210, 224)), (0.58, (255, 255, 255)), (1.00, (255, 255, 255)),
]
# D — oxblood: the curtain's red taken to a metal, warm against the gold.
OXBLOOD = [
    (0.00, (194,  96, 106)), (0.20, (138,  37,  49)), (0.44, ( 61,  11,  18)),
    (0.50, ( 30,   5,   9)), (0.55, (208, 138, 146)), (0.74, (109,  28,  38)),
    (1.00, ( 44,   8,  13)),
]

W, H, SS = 1700, 980, 2
DIM, FAINT, HAIR = (104, 98, 86), (60, 57, 51), (44, 42, 38)


def marks_row(cv, y, size, tone, gap, x0, lscale=0.155):
    # Thicken the hairlines only where they would otherwise vanish.
    weight = 2 if size < 70 else (1 if size < 110 else 0)
    for k, (ch, _) in enumerate(AGENTS):
        x = int(x0 + k * (size + gap))
        dark = Image.new("L", cv.size, 0)
        dark.paste(aperture_mask(size), (x, y))
        layer = Image.new("RGBA", cv.size, (36, 36, 44, 0))
        layer.putalpha(dark)
        cv.alpha_composite(layer)

        lit = Image.new("L", cv.size, 0)
        lit.paste(aperture_mask(size, only=k), (x, y))
        plate_metal(cv, lit, GOLD)

        gx, gy = blade_centre(k)
        lm = letter_mask(ch, int(size * lscale), PINYON, turn=k * 60, weight=weight)
        full = Image.new("L", cv.size, 0)
        full.paste(lm, (int(x + gx / 100 * size - lm.width / 2),
                        int(y + gy / 100 * size - lm.height / 2)))
        plate_metal(cv, full, tone)
    return int(x0 + 6 * (size + gap) - gap)


def sample(tone, label, note, out: Path, lscale=0.23) -> None:
    cw, chh = W * SS, H * SS
    cv = Image.new("RGBA", (cw, chh), INK + (255,))
    d = ImageDraw.Draw(cv)
    S = lambda v: int(v * SS)
    M = S(90)

    mono = font("GeistMono-Regular.ttf", S(23))
    small = font("GeistMono-Regular.ttf", S(17))
    d.line([(M, S(150)), (cw - M, S(150))], fill=HAIR, width=SS)
    tracked(d, (M, S(128)), label, mono, DIM, S(8))
    tracked(d, (M, S(196)), note, small, FAINT, S(4))

    big = S(232)
    marks_row(cv, S(250), big, tone, S(34), M, lscale)

    d.line([(M, S(620)), (cw - M, S(620))], fill=HAIR, width=SS)
    tracked(d, (M, S(672)), "AT SHIPPING SIZE  ·  54 PX", small, FAINT, S(5))
    marks_row(cv, S(710), S(54), tone, S(26), M, lscale)

    # No per-mark captions on this row: the labels are far wider than 54px of
    # spacing and collide into each other. The row exists to show size, and the
    # names are already carried by the large row above.

    d.line([(M, S(900)), (cw - M, S(900))], fill=HAIR, width=SS)
    tracked(d, (M, S(944)), "THE BACKLOT  ·  GOLD BLADE, TONED INITIAL",
            small, FAINT, S(5))

    cv.convert("RGB").resize((W, H), Image.LANCZOS).save(out)
    print(f"  {out.name}")


def main() -> None:
    sample(BRIGHT, "SAMPLE W  ·  NEAR-WHITE, LARGER",
           "LETTER AT 23% OF THE MARK — ONLY A LIGHT SILVER DIP, NO DARK BAND",
           HERE / "tone-W-white.png")
    sample(BLACK_CHROME, "SAMPLE B  ·  BLACK CHROME, LARGER",
           "SAME SIZE INCREASE, DARK METAL",
           HERE / "tone-B-black-chrome.png")
    sample(OXBLOOD, "SAMPLE D  ·  OXBLOOD, LARGER",
           "SAME SIZE INCREASE, THE CURTAIN'S RED",
           HERE / "tone-D-oxblood.png")


if __name__ == "__main__":
    main()

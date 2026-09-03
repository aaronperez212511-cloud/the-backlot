"""Aurum Reflex — Plate VI.

A single gilded plate, rendered under the philosophy in AURUM-REFLEX.md: two
metals against deep ink, one specimen at full scale, the same specimen resolved
through its six phases beneath, and clinical annotation kept to the minimum a
plate needs to be citable.

Everything is drawn at 2x and downsampled once at the end — the aperture is all
long diagonals, and they alias badly at final size.

    python design/render_plate.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
FONTS = Path("C:/Users/ferna/AppData/Roaming/Claude/local-agent-mode-sessions"
             "/skills-plugin/ea1826e4-f23c-46c5-ab19-719d52aee0ae"
             "/31ed2610-e913-4536-8f24-cc25bf85f158/skills/canvas-design/canvas-fonts")
PINYON = HERE.parent / "web" / "marks" / "PinyonScript-Regular.ttf"

W, H = 2400, 2920           # design units; exported at OUT_W
OUT_W = 3840                # 4K-class export
TYPE = 1.42                 # the clinical type was set too fine to read small
SS = 2                      # supersample
INK = (9, 9, 11)

# ── The two metals ──────────────────────────────────────────────────────────
# Gold chrome: amber shoulders, a genuinely brown-black horizon. Driving the
# dark stop to near-black is what stops it reading as flat ochre.
GOLD = [
    (0.00, (255, 250, 231)), (0.13, (255, 238, 186)), (0.29, (232, 200, 116)),
    (0.43, (168, 129,  58)), (0.50, ( 84,  60,  20)), (0.56, (245, 220, 154)),
    (0.71, (255, 238, 192)), (0.87, (255, 251, 240)), (1.00, (201, 169,  97)),
]
# Ultra-bright chrome: whiter peaks and a shallower dark band than the gold, so
# it reads as the more polished of the two metals.
CHROME = [
    (0.00, (255, 255, 255)), (0.20, (255, 255, 255)), (0.36, (220, 231, 241)),
    (0.46, (127, 143, 161)), (0.50, ( 66,  80,  95)), (0.54, (255, 255, 255)),
    (0.76, (255, 255, 255)), (0.88, (207, 220, 232)), (1.00, (255, 255, 255)),
]

HAIR = (44, 42, 38)         # hairline ink, just above the threshold of sight
DIM = (104, 98, 86)         # clinical annotation
FAINT = (60, 57, 51)
WHITE = (255, 255, 255)     # the one label that must read at a glance: agent names

AGENTS = [("C", "CHAIN OF TITLE"), ("G", "GHOST ADS"), ("F", "FRAUD SENTINEL"),
          ("P", "PREMIERE PULSE"), ("W", "WAR ROOM"), ("E", "EARLY WARNING")]

BLADE = [(50.70, 30.01), (66.96, 39.40), (94.56, 43.74), (69.73, 9.55)]
BLADE_R, BLADE_A = 28.16, -43.3      # polar centroid of blade 0


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def ramp(h: int, stops) -> Image.Image:
    """A 1px-wide vertical metal strip, h tall."""
    strip = Image.new("RGB", (1, max(h, 1)))
    px = strip.load()
    for y in range(max(h, 1)):
        t = y / max(h - 1, 1)
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0) if t1 > t0 else 0
                px[0, y] = tuple(round(a + (b - a) * f) for a, b in zip(c0, c1))
                break
    return strip


def plate_metal(canvas: Image.Image, mask: Image.Image, stops, box=None) -> None:
    """Show a metal ramp through `mask`. The ramp spans `box` (default: the
    mask's own bounds), so one light can be shared across separate shapes."""
    bb = box or mask.getbbox()
    if not bb:
        return
    x0, y0, x1, y1 = bb
    strip = ramp(y1 - y0, stops).resize((x1 - x0, y1 - y0))
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    # The strip is bb-sized, so the mask has to be cropped to bb to match it —
    # pasting a full-canvas mask against a cropped source is a size mismatch.
    layer.paste(strip, (x0, y0), mask.crop(bb))
    canvas.alpha_composite(layer)


def bez(p0, p1, p2, p3, n=28):
    """Sample a cubic Bezier. The valance hem and the drape edges are curves;
    approximating them with straight segments reads as a sawtooth, not cloth."""
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append((u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0],
                    u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1]))
    return out


def rot(p, deg, cx=50.0, cy=50.0):
    a = math.radians(deg)
    x, y = p[0] - cx, p[1] - cy
    return (cx + x * math.cos(a) - y * math.sin(a),
            cy + x * math.sin(a) + y * math.cos(a))


def blade_centre(k: int):
    a = math.radians(BLADE_A + 60 * k)
    return 50 + BLADE_R * math.cos(a), 50 + BLADE_R * math.sin(a)


def aperture_mask(size: int, only: int | None = None) -> Image.Image:
    """The six-bladed aperture as an alpha mask. `only` draws a single blade."""
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    for k in range(6):
        if only is not None and k != only:
            continue
        poly = [rot(p, k * 60) for p in BLADE]
        d.polygon([(x / 100 * size, y / 100 * size) for x, y in poly], fill=255)
    return m


WIDEN = 1.34


def letter_mask(ch: str, target: int, fnt_path: Path, turn: float = 0.0,
                weight: int = 0) -> Image.Image:
    """A glyph fitted to a `target` box and turned onto its blade.

    Pinyon's capitals vary enormously in width, so fitting by font-size alone
    leaves the six visibly mismatched. The fit is then stretched horizontally —
    copperplate capitals are tall and narrow, and at a height that fits a wedge
    they look thin. `turn` rotates the glyph with its blade so the six read as
    one turn of a single ring rather than six upright letters.
    """
    f = ImageFont.truetype(str(fnt_path), target * 3)
    tmp = Image.new("L", (target * 9, target * 9), 0)
    ImageDraw.Draw(tmp).text((target * 4, target * 4), ch, font=f, fill=255, anchor="mm")
    g = tmp.crop(tmp.getbbox())
    k = min(target / g.width, target / g.height)
    g = g.resize((max(int(g.width * k * WIDEN), 1), max(int(g.height * k), 1)), Image.LANCZOS)
    # Synthetic weight. Measured on this face, a mark of 54px puts the letter
    # at 13x12 with a thinnest stroke of a single pixel — invisible on gold no
    # matter how white it is made. Dilating the mask thickens the hairlines to
    # something that can actually carry colour. Only needed at small sizes; at
    # 150px the same strokes are already ~3px.
    for _ in range(weight):
        g = g.filter(ImageFilter.MaxFilter(3))
    if turn:
        # expand=True so the corners of a turned glyph are not clipped
        g = g.rotate(-turn, resample=Image.BICUBIC, expand=True)
    return g


def tracked(draw: ImageDraw.ImageDraw, xy, text: str, fnt, fill, track: int, anchor="ls"):
    """Letterspaced text. PIL has no tracking, so glyphs are placed one by one."""
    widths = [draw.textlength(c, font=fnt) for c in text]
    total = sum(widths) + track * (len(text) - 1)
    x, y = xy
    if anchor == "ms":
        x -= total / 2
    for c, w in zip(text, widths):
        draw.text((x, y), c, font=fnt, fill=fill, anchor="ls")
        x += w + track
    return total


def tracked_mask(size, xy, text, fnt, track, anchor="ls") -> Image.Image:
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    tracked(d, xy, text, fnt, 255, track, anchor)
    return m


def curtain(canvas: Image.Image, x0: int, y0: int, w: int, h: int) -> None:
    """The proscenium: a valance whose hem scallops in true curves, tassels at
    the dips, and a drape tied back down each side."""
    sx, sy = w / 200.0, h / 60.0
    P = lambda pt: (x0 + pt[0] * sx, y0 + pt[1] * sy)

    # Drape silhouettes, curved.
    def drape_pts(mirror):
        f = lambda v: (200 - v) if mirror else v
        pts = [(f(0), 0), (f(34), 0)]
        pts += [(f(x), y) for x, y in bez((34, 0), (34, 14), (26, 22), (20, 34))]
        pts += [(f(x), y) for x, y in bez((20, 34), (16, 44), (15, 52), (15, 60))]
        pts += [(f(0), 60)]
        return [P(q) for q in pts]

    m = Image.new("L", canvas.size, 0)
    d = ImageDraw.Draw(m)
    for mirror in (False, True):
        d.polygon(drape_pts(mirror), fill=255)

    # Valance: straight top, curved scalloped hem returning right to left.
    # Four scallops of exactly 50 across 200. A period that does not divide the
    # span leaves the last one overshooting past the edge, and the polygon then
    # closes across that overshoot as a spike out the side.
    hem = [(200, 10)]
    for i in range(4):
        x = 200 - i * 50
        hem += bez((x, 10), (x - 11, 10), (x - 14, 20), (x - 25, 20))
        hem += bez((x - 25, 20), (x - 36, 20), (x - 39, 10), (x - 50, 10))
    pts = [P((0, 0)), P((200, 0))] + [P(q) for q in hem] + [P((0, 10))]
    d.polygon(pts, fill=255)
    plate_metal(canvas, m, GOLD)

    # Folds: fine ink lines, clipped to the cloth so none escape the silhouette.
    fold = Image.new("L", canvas.size, 0)
    fd = ImageDraw.Draw(fold)
    lw = max(int(1.1 * sx), 1)
    inner = [(34, 0), (34, 14), (26, 22), (20, 34), (16, 44), (15, 52), (15, 60)]
    for mirror in (False, True):
        f = lambda v: (200 - v) if mirror else v
        for i in range(1, 11):
            t = i / 11
            cur = [(f(x * t), y) for x, y in
                   bez((34, 0), (34, 14), (26, 22), (20, 34)) +
                   bez((20, 34), (16, 44), (15, 52), (15, 60))]
            fd.line([P(q) for q in cur], fill=62, width=lw, joint="curve")
    for i in range(1, 27):
        x = 200 * i / 27
        fd.line([P((x, 0)), P((x + (2.5 if i % 4 < 2 else -2.5), 16))], fill=44, width=lw)
    fold = Image.composite(fold, Image.new("L", canvas.size, 0), m)
    ink = Image.new("RGBA", canvas.size, INK + (0,))
    ink.putalpha(fold)
    canvas.alpha_composite(ink)

    # Tassels hang from the scallop dips, so hem and trim agree.
    t = Image.new("L", canvas.size, 0)
    td = ImageDraw.Draw(t)
    for cx in (175, 125, 75, 25):
        td.ellipse([P((cx - 2.4, 19.4)), P((cx + 2.4, 24.2))], fill=255)
        td.polygon([P((cx - 1.9, 22.6)), P((cx + 1.9, 22.6)),
                    P((cx + 1.0, 30)), P((cx - 1.0, 30))], fill=255)
    plate_metal(canvas, t, GOLD)


def main() -> None:
    cw, ch = W * SS, H * SS
    cv = Image.new("RGBA", (cw, ch), INK + (255,))
    d = ImageDraw.Draw(cv)
    S = lambda v: int(v * SS)

    mono = lambda s: font("GeistMono-Regular.ttf", S(s * TYPE))
    monob = lambda s: font("GeistMono-Bold.ttf", S(s * TYPE))
    ital = lambda s: font("Italiana-Regular.ttf", S(s))

    M = S(200)                      # margin
    CW = cw - 2 * M                 # content width
    CX = cw // 2

    def rule(y, x0=None, x1=None, col=HAIR):
        d.line([(x0 or M, S(y)), (x1 or cw - M, S(y))], fill=col, width=max(SS, 1))

    # ── header ──────────────────────────────────────────────────────────────
    tracked(d, (M, S(196)), "PLATE VI", mono(21), DIM, S(7))
    t = "ATLAS OF REFLECTIVE FORMS"
    tracked(d, (CX, S(196)), t, mono(21), FAINT, S(7), anchor="ms")
    w = sum(d.textlength(c, font=mono(21)) for c in "SIX-BLADED APERTURE") + S(7) * 18
    tracked(d, (cw - M - w, S(196)), "SIX-BLADED APERTURE", mono(21), DIM, S(7))
    rule(232)

    # ── hero specimen ───────────────────────────────────────────────────────
    hero = S(860)
    hx, hy = CX - hero // 2, S(320)

    # measurement ring: 72 ticks at 5-degree intervals, longer every 30
    for i in range(72):
        a = math.radians(i * 5 - 90)
        r0 = hero * 0.545
        r1 = r0 + (S(26) if i % 6 == 0 else S(12))
        c = HAIR if i % 6 == 0 else FAINT
        d.line([(CX + r0 * math.cos(a), hy + hero / 2 + r0 * math.sin(a)),
                (CX + r1 * math.cos(a), hy + hero / 2 + r1 * math.sin(a))],
               fill=c, width=max(SS, 1))
    for rr in (0.50, 0.605):
        r = hero * rr
        d.ellipse([CX - r, hy + hero / 2 - r, CX + r, hy + hero / 2 + r],
                  outline=FAINT, width=max(SS, 1))

    ap = Image.new("L", (cw, ch), 0)
    ap.paste(aperture_mask(hero), (hx, hy))
    plate_metal(cv, ap, GOLD)

    # six initials, ultra-bright chrome, seated on their own blades
    for k, (ch_, _) in enumerate(AGENTS):
        gx, gy = blade_centre(k)
        lm = letter_mask(ch_, int(hero * 0.145), PINYON, turn=k * 60)
        full = Image.new("L", (cw, ch), 0)
        full.paste(lm, (int(hx + gx / 100 * hero - lm.width / 2),
                        int(hy + gy / 100 * hero - lm.height / 2)))
        plate_metal(cv, full, CHROME)

    rule(1290)

    # ── wordmark ────────────────────────────────────────────────────────────
    f = ital(168)
    m = tracked_mask((cw, ch), (CX, S(1470)), "THE BACKLOT", f, S(26), anchor="ms")
    plate_metal(cv, m, GOLD)

    # ── control room, under its curtain ─────────────────────────────────────
    cur_w, cur_h = S(1080), S(300)
    cur_x, cur_y = CX - cur_w // 2, S(1600)
    curtain(cv, cur_x, cur_y, cur_w, cur_h)
    f2 = ital(74)
    m = tracked_mask((cw, ch), (CX, cur_y + S(228)), "CONTROL ROOM", f2, S(30), anchor="ms")
    plate_metal(cv, m, GOLD)

    rule(1990)

    # ── the six phases ──────────────────────────────────────────────────────
    tracked(d, (M, S(2062)), "SIX BLADES  ·  SIX PHASES", mono(21), DIM, S(7))
    w = sum(d.textlength(c, font=mono(21)) for c in "f/1.4 — f/22") + S(7) * 11
    tracked(d, (cw - M - w, S(2062)), "f/1.4 — f/22", mono(21), FAINT, S(7))

    cell = CW / 6
    sm = int(cell * 0.76)
    for k, (ch_, name) in enumerate(AGENTS):
        cx = M + cell * (k + 0.5)
        sx, sy = int(cx - sm / 2), S(2128)
        base = Image.new("L", (cw, ch), 0)
        base.paste(aperture_mask(sm), (sx, sy))
        ink_layer = Image.new("RGBA", (cw, ch), (38, 36, 33, 0))
        ink_layer.putalpha(base)
        cv.alpha_composite(ink_layer)

        lit = Image.new("L", (cw, ch), 0)
        lit.paste(aperture_mask(sm, only=k), (sx, sy))
        plate_metal(cv, lit, GOLD)

        gx, gy = blade_centre(k)
        lm = letter_mask(ch_, int(sm * 0.155), PINYON, turn=k * 60)
        full = Image.new("L", (cw, ch), 0)
        full.paste(lm, (int(sx + gx / 100 * sm - lm.width / 2),
                        int(sy + gy / 100 * sm - lm.height / 2)))
        plate_metal(cv, full, CHROME)

        d.line([(cx, sy + sm + S(34)), (cx, sy + sm + S(54))], fill=HAIR, width=max(SS, 1))
        tracked(d, (cx, sy + sm + S(96)), f"{k + 1:02d}", mono(19), DIM, S(5), anchor="ms")
        # This was set in FAINT — almost the ink colour itself, effectively
        # invisible against the ground. Bold, white, and a size step up.
        tracked(d, (cx, sy + sm + S(148)), name, monob(19), WHITE, S(3), anchor="ms")

    # ── footer ──────────────────────────────────────────────────────────────
    rule(2648)
    tracked(d, (M, S(2710)), "AURUM REFLEX", mono(21), DIM, S(7))
    w = sum(d.textlength(c, font=mono(21)) for c in "ONE LIGHT · TWO METALS") + S(7) * 21
    tracked(d, (cw - M - w, S(2710)), "ONE LIGHT · TWO METALS", mono(21), FAINT, S(7))

    out = cv.convert("RGB").resize((OUT_W, round(OUT_W * H / W)), Image.LANCZOS)
    p = HERE / "aurum-reflex-plate-vi.png"
    out.save(p, quality=97)
    print(f"  {p.name}  {out.width}x{out.height}")


if __name__ == "__main__":
    main()

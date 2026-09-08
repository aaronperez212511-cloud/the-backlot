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

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
# Vendored, not referenced from wherever they happened to be installed. These
# scripts previously loaded Geist and Italiana from an absolute path on one
# machine, which meant `python design/render_plate.py` was reproducible for
# exactly one person: anyone else cloning the repo got FileNotFoundError. Both
# faces are SIL Open Font License 1.1, so they ship here with their licences,
# the same arrangement web/marks already uses for Pinyon Script.
FONTS = HERE / "fonts"
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

AGENTS = [("C", "CHAIN OF TITLE", "royalty integrity"),
          ("G", "GHOST ADS", "ad-insertion leaks"),
          ("F", "FRAUD SENTINEL", "credential abuse"),
          ("P", "PREMIERE PULSE", "playback health"),
          ("W", "WAR ROOM", "title performance"),
          ("E", "EARLY WARNING", "retention risk")]

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


def plate_metal(canvas: Image.Image, mask: Image.Image, stops, box=None,
                 brush=None, strength=15, n_bands=1100) -> None:
    """Show a metal ramp through `mask`. The ramp spans `box` (default: the
    mask's own bounds), so one light can be shared across separate shapes.

    `brush=(cx, cy)` runs the fill through `brushed()` before compositing, in
    the local (bbox-sized) frame rather than the full canvas — a photographed
    lens iris shows machined streaks radiating from its own centre; without
    this the metal reads as flat paint no matter how carefully the ramp is lit.
    """
    bb = box or mask.getbbox()
    if not bb:
        return
    x0, y0, x1, y1 = bb
    strip = ramp(y1 - y0, stops).resize((x1 - x0, y1 - y0))
    # Built at bbox size, not canvas size — brushed() runs a numpy pass over
    # every pixel it's given, and the plate's canvas is supersampled to ~5800px
    # tall, so doing that pass at full-canvas size for a 150px mark is wasted
    # work several times over.
    local = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    local.paste(strip, (0, 0), mask.crop(bb))
    if brush is not None:
        local = brushed(local, brush[0] - x0, brush[1] - y0, strength=strength, n_bands=n_bands)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(local, (x0, y0), local)
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
                weight: int = 0, widen: float | None = None) -> Image.Image:
    """A glyph fitted to a `target` box.

    Pinyon's capitals vary enormously in width, so fitting by font-size alone
    leaves the six visibly mismatched. The fit is then stretched horizontally by
    `widen` (defaults to the module WIDEN) — copperplate capitals are tall and
    narrow, and at a height that fits a wedge they look thin. That stretch is
    right for a letter sitting on a blade, but wrong for one centred in the
    aperture's round opening: widened past `target` there, it can reach the
    hexagon's flat edges. Pass `widen=1.0` to keep both dimensions within
    `target`. `turn` rotates the glyph with its blade; leave it 0 to keep the
    glyph upright when it is centred rather than riding a blade.
    """
    w = WIDEN if widen is None else widen
    f = ImageFont.truetype(str(fnt_path), target * 3)
    tmp = Image.new("L", (target * 9, target * 9), 0)
    ImageDraw.Draw(tmp).text((target * 4, target * 4), ch, font=f, fill=255, anchor="mm")
    g = tmp.crop(tmp.getbbox())
    k = min(target / g.width, target / g.height)
    g = g.resize((max(int(g.width * k * w), 1), max(int(g.height * k), 1)), Image.LANCZOS)
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


def paper_ground(size: tuple[int, int], base=INK, grain=6, seed=11) -> Image.Image:
    """Flat ink with fine per-pixel grain — paper, not a flat digital fill."""
    w, h = size
    rng = np.random.default_rng(seed)
    noise = rng.integers(-grain, grain + 1, size=(h, w)).astype(np.int16)
    arr = np.zeros((h, w, 3), dtype=np.int16) + np.array(base, dtype=np.int16)
    arr += noise[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def etched_rings(canvas: Image.Image, cx: float, cy: float, step=46, colour=(17, 17, 20)) -> None:
    """Concentric hairlines behind everything, at a contrast so low they only
    read at a glance — the etched-paper/vinyl-record specimen-plate texture."""
    d = ImageDraw.Draw(canvas)
    diag = int((canvas.width ** 2 + canvas.height ** 2) ** 0.5)
    for r in range(step, diag, step):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=colour, width=1)


def brushed(img_rgba: Image.Image, cx: float, cy: float, strength=15, n_bands=1100, seed=3) -> Image.Image:
    """Radial brushed-metal streaks, spoking out from `(cx, cy)` — the finish a
    machined ring actually has, not a generic linear grain. `(cx, cy)` is in
    `img_rgba`'s own coordinate frame, which is normally a local bbox crop, not
    the full canvas — see the note on `plate_metal`. Placing the centre far
    outside the image (a pediment bar's brush point sits thousands of px below
    it) makes the angle barely change across the shape's own height, which is
    what turns this radial technique into near-vertical brushing for a flat bar
    instead of the sunburst it gives a lens iris. Applied only where alpha>0,
    so it never leaks past the shape's own silhouette."""
    arr = np.array(img_rgba).astype(np.int16)
    h, w = arr.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    theta = np.arctan2(yy - cy, xx - cx)
    band = ((theta + np.pi) / (2 * np.pi) * n_bands).astype(np.int64) % n_bands
    rng = np.random.default_rng(seed)
    band_vals = rng.integers(-strength, strength + 1, size=n_bands)
    noise = band_vals[band]
    has_alpha = arr[..., 3] > 0
    for c in range(3):
        arr[..., c] = np.where(has_alpha, np.clip(arr[..., c] + noise, 0, 255), arr[..., c])
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def bevel(canvas: Image.Image, k: int, x: float, y: float, size: float) -> None:
    """A highlight along the blade edge that would face a light from upper-left,
    a shadow along the edge that would face away from it — the two strokes that
    make a flat fill read as a bevel instead of a sticker."""
    poly = [rot(p, k * 60) for p in BLADE]
    pts = [(x + px / 100 * size, y + py / 100 * size) for px, py in poly]
    n = len(pts)
    hi = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(hi)
    for i in range(n):
        p0, p1 = pts[i], pts[(i + 1) % n]
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        facing = (mx - (x + size / 2)) + (my - (y + size / 2))
        if facing < 0:
            hd.line([p0, p1], fill=(255, 246, 214, 130), width=max(int(size * 0.008), 1))
        else:
            hd.line([p0, p1], fill=(20, 14, 4, 150), width=max(int(size * 0.01), 1))
    hi = hi.filter(ImageFilter.GaussianBlur(max(size * 0.004, 1)))
    canvas.alpha_composite(hi)


def blueprint(canvas: Image.Image, cx: float, cy: float, r: float, colour=(58, 50, 30)) -> None:
    """A hint of a studio backlot floor plan, sitting where the aperture's own
    opening will later show it through — a soundstage, a production office, a
    lot road. Legible as *a plan* at a glance; it doesn't have to be literal."""
    d = ImageDraw.Draw(canvas)
    x0, y0 = cx - r, cy - r
    lw = max(int(r * 0.02), 1)

    def rect(fx0, fy0, fx1, fy1):
        d.rectangle([x0 + fx0 * 2 * r, y0 + fy0 * 2 * r, x0 + fx1 * 2 * r, y0 + fy1 * 2 * r],
                    outline=colour, width=lw)

    rect(0.14, 0.16, 0.52, 0.46)
    rect(0.56, 0.14, 0.86, 0.34)
    rect(0.20, 0.54, 0.44, 0.82)
    d.line([x0 + 0.48 * 2 * r, y0 + 0.46 * 2 * r, x0 + 0.48 * 2 * r, y0 + 0.90 * 2 * r], fill=colour, width=lw)
    d.line([x0 + 0.10 * 2 * r, y0 + 0.50 * 2 * r, x0 + 0.90 * 2 * r, y0 + 0.50 * 2 * r], fill=colour, width=max(lw // 2, 1))
    d.ellipse([x0 + 0.58 * 2 * r, y0 + 0.58 * 2 * r, x0 + 0.82 * 2 * r, y0 + 0.82 * 2 * r], outline=colour, width=lw)


def drop_shadow(canvas: Image.Image, mask: Image.Image, dx=8, dy=14, blur=6, opacity=210) -> None:
    """A soft, offset dark pass under a shape — the one cue that most separates
    a photographed object sitting on paper from a flat vector cutout."""
    shifted = Image.new("L", canvas.size, 0)
    shifted.paste(mask, (dx, dy))
    shifted = shifted.filter(ImageFilter.GaussianBlur(blur))
    black = Image.new("RGBA", canvas.size, (0, 0, 0, opacity))
    canvas.alpha_composite(Image.composite(black, Image.new("RGBA", canvas.size, (0, 0, 0, 0)), shifted))


def pediment(canvas: Image.Image, x0: int, y0: int, w: int, h: int) -> None:
    """A fluted brass pediment over CONTROL ROOM — three rounded arches on a
    brushed bar, replacing the fabric curtain so the material reads as forged
    metal rather than cloth. Reuses the earlier valance's bezier-scallop
    technique (real curves, not a sawtooth) at three-fold symmetry to match the
    reference's triple-arch silhouette, in place of a first attempt that spaced
    the arches with straight polygon notches and read as a jagged crown rather
    than an elegant bracket."""
    P = lambda pt: (x0 + pt[0] / 200.0 * w, y0 + pt[1] / 60.0 * h)
    period = 200 / 3
    hem = [(200, 8)]
    for i in range(3):
        x = 200 - i * period
        hem += bez((x, 8), (x - period * 0.20, 8), (x - period * 0.26, 38), (x - period * 0.50, 38))
        hem += bez((x - period * 0.50, 38), (x - period * 0.74, 38), (x - period * 0.80, 8), (x - period, 8))
    pts = [P(q) for q in hem]
    sil = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(sil).polygon([P((0, 0)), P((200, 0))] + pts + [P((0, 8))], fill=255)

    drop_shadow(canvas, sil, dx=int(w * 0.010), dy=int(h * 0.09), blur=max(int(h * 0.05), 1))
    bb = (x0, y0, x0 + w, y0 + h)
    # A brush centre many multiples of h below the bar keeps the local angle
    # nearly constant across its small height — the same radial technique the
    # aperture uses reads as near-vertical brushing on a shape this flat.
    plate_metal(canvas, sil, GOLD, box=bb, brush=(x0 + w / 2, y0 + h * 24), strength=14, n_bands=900)

    hi = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(hi)
    lw = max(int(h * 0.02), 1)
    hd.line([P((0, 0)), P((200, 0))], fill=(255, 246, 214, 150), width=lw)
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]
        col = (255, 246, 214, 120) if p0[1] < y0 + h * 0.35 else (20, 14, 4, 140)
        hd.line([p0, p1], fill=col, width=lw)
    hi = hi.filter(ImageFilter.GaussianBlur(max(h * 0.006, 1)))
    canvas.alpha_composite(hi)


def main() -> None:
    cw, ch = W * SS, H * SS
    cv = paper_ground((cw, ch), grain=5)
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

    # Etched behind everything, centred on the hero specimen — the geometry is
    # computed once here since the hero block below needs it too.
    hero = S(860)
    hx, hy = CX - hero // 2, S(320)
    hero_cx, hero_cy = CX, hy + hero // 2
    etched_rings(cv, hero_cx, hero_cy, step=S(36))

    # ── header ──────────────────────────────────────────────────────────────
    tracked(d, (M, S(196)), "PLATE VI", mono(21), DIM, S(7))
    t = "ATLAS OF REFLECTIVE FORMS"
    tracked(d, (CX, S(196)), t, mono(21), FAINT, S(7), anchor="ms")
    w = sum(d.textlength(c, font=mono(21)) for c in "SIX-BLADED APERTURE") + S(7) * 18
    tracked(d, (cw - M - w, S(196)), "SIX-BLADED APERTURE", mono(21), DIM, S(7))
    rule(232)

    # ── hero specimen ───────────────────────────────────────────────────────
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
    drop_shadow(cv, ap, dx=S(10), dy=S(16), blur=S(8))
    blueprint(cv, hero_cx, hero_cy, hero * 0.20)
    plate_metal(cv, ap, GOLD, brush=(hero_cx, hero_cy), strength=16, n_bands=1300)
    for k in range(6):
        bevel(cv, k, hx, hy, hero)

    # six initials, ultra-bright chrome, seated on their own blades
    for k, (ch_, _, _role) in enumerate(AGENTS):
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
    drop_shadow(cv, m, dx=S(4), dy=S(8), blur=S(5))
    plate_metal(cv, m, GOLD)

    # ── control room, under its pediment ────────────────────────────────────
    cur_w, cur_h = S(1080), S(300)
    cur_x, cur_y = CX - cur_w // 2, S(1600)
    pediment(cv, cur_x, cur_y, cur_w, cur_h)
    f2 = ital(74)
    m = tracked_mask((cw, ch), (CX, cur_y + S(260)), "CONTROL ROOM", f2, S(30), anchor="ms")
    drop_shadow(cv, m, dx=S(3), dy=S(6), blur=S(4))
    plate_metal(cv, m, GOLD)

    rule(1990)

    # ── the six phases ──────────────────────────────────────────────────────
    tracked(d, (M, S(2062)), "SIX BLADES  ·  SIX PHASES", mono(21), DIM, S(7))
    w = sum(d.textlength(c, font=mono(21)) for c in "f/1.4 — f/22") + S(7) * 11
    tracked(d, (cw - M - w, S(2062)), "f/1.4 — f/22", mono(21), FAINT, S(7))

    cell = CW / 6
    sm = int(cell * 0.76)
    for k, (ch_, name, role) in enumerate(AGENTS):
        cx = M + cell * (k + 0.5)
        sx, sy = int(cx - sm / 2), S(2128)
        base = Image.new("L", (cw, ch), 0)
        base.paste(aperture_mask(sm), (sx, sy))
        ink_layer = Image.new("RGBA", (cw, ch), (38, 36, 33, 0))
        ink_layer.putalpha(base)
        cv.alpha_composite(ink_layer)

        lit = Image.new("L", (cw, ch), 0)
        lit.paste(aperture_mask(sm, only=k), (sx, sy))
        plate_metal(cv, lit, GOLD, brush=(sx + sm / 2, sy + sm / 2), strength=12, n_bands=500)
        bevel(cv, k, sx, sy, sm)

        # Centred in the opening, not on the blade — see the note in
        # render_architecture.mark() for why.
        lm = letter_mask(ch_, int(sm * 0.30), PINYON, widen=1.0)
        full = Image.new("L", (cw, ch), 0)
        full.paste(lm, (int(sx + sm / 2 - lm.width / 2),
                        int(sy + sm / 2 - lm.height / 2)))
        plate_metal(cv, full, CHROME)

        d.line([(cx, sy + sm + S(34)), (cx, sy + sm + S(54))], fill=HAIR, width=max(SS, 1))
        # The name takes the slot the specimen number used to hold. A plate
        # numbering its own specimens 01–06 is telling you their order, which
        # is the one thing about this fleet that carries no meaning: the
        # agents are peers, not a sequence. The name is the identifier, so it
        # gets the position and the weight, with the domain under it.
        tracked(d, (cx, sy + sm + S(102)), name, monob(19), WHITE, S(3), anchor="ms")
        tracked(d, (cx, sy + sm + S(146)), role, mono(15), DIM, S(3), anchor="ms")

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

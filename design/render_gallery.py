"""3:2 gallery cards for the Devpost submission.

Devpost recommends a 3:2 aspect ratio, so these are generated at that ratio
rather than cropped to it afterwards — cropping the architecture diagram would
cut the arrows that carry its whole argument.

    python design/render_gallery.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from render_plate import (GOLD, INK, aperture_mask, bevel, blade_centre, font,
                          letter_mask, plate_metal, tracked, PINYON)

HERE = Path(__file__).parent
W, H, SS = 2400, 1600, 3          # 3:2 design units
OUT_W = 3840                      # 4K-class export
TYPE = 1.42                       # the small mono type was set too fine
DIM, FAINT, HAIR = (104, 98, 86), (60, 57, 51), (44, 42, 38)
IVORY = (231, 226, 216)
WHITE = (255, 255, 255)

AGENTS = [("C", "chain_of_title", "royalty integrity"),
          ("G", "ghost_ads", "ad-insertion leaks"),
          ("F", "fraud_sentinel", "credential abuse"),
          ("P", "premiere_pulse", "playback health"),
          ("W", "performance_war_room", "title performance"),
          ("E", "churn_early_warning", "retention risk")]

# The initials are near-white with only a light silver dip: measured on this
# face, a dark band across a small letter erases most of it.
BRIGHT = [(0.00, (255, 255, 255)), (0.30, (255, 255, 255)), (0.46, (228, 237, 246)),
          (0.52, (196, 210, 224)), (0.58, (255, 255, 255)), (1.00, (255, 255, 255))]


def identity_card(out: Path) -> None:
    cw, ch = W * SS, H * SS
    cv = Image.new("RGBA", (cw, ch), INK + (255,))
    d = ImageDraw.Draw(cv)
    S = lambda v: int(v * SS)
    M, CX = S(120), cw // 2
    mono = lambda s: font("GeistMono-Regular.ttf", S(s * TYPE))
    monob = lambda s: font("GeistMono-Bold.ttf", S(s * TYPE))
    ital = lambda s: font("Italiana-Regular.ttf", S(s))

    tracked(d, (M, S(104)), "THE BACKLOT", mono(21), DIM, S(8))
    t = "ONE DATA FOUNDATION · SIX SPECIALISTS · ONE COMMAND CENTER"
    wt = sum(d.textlength(c, font=mono(21)) for c in t) + S(8) * (len(t) - 1)
    tracked(d, (cw - M - wt, S(104)), t, mono(21), FAINT, S(8))
    d.line([(M, S(140)), (cw - M, S(140))], fill=HAIR, width=SS)

    # hero aperture
    ap = S(400)
    ax, ay = CX - ap // 2, S(230)
    m = Image.new("L", (cw, ch), 0)
    m.paste(aperture_mask(ap), (ax, ay))
    plate_metal(cv, m, GOLD, brush=(CX, ay + ap / 2), strength=15, n_bands=1000)
    for k in range(6):
        bevel(cv, k, ax, ay, ap)

    # wordmark
    f = ital(150)
    wm = Image.new("L", (cw, ch), 0)
    tracked(ImageDraw.Draw(wm), (CX, S(830)), "THE BACKLOT", f, 255, S(24), anchor="ms")
    plate_metal(cv, wm, GOLD)
    tracked(d, (CX, S(884)), "CONTROL ROOM", mono(22), (170, 143, 82), S(16), anchor="ms")

    d.line([(M, S(980)), (cw - M, S(980))], fill=HAIR, width=SS)
    tracked(d, (M, S(1032)), "THE FLEET", mono(19), DIM, S(7))

    # six specialist marks
    sm = S(178)
    cell = (cw - 2 * M) / 6
    for k, (ch_, name, role) in enumerate(AGENTS):
        cx = M + cell * (k + 0.5)
        x, y = int(cx - sm / 2), S(1090)
        dark = Image.new("L", (cw, ch), 0)
        dark.paste(aperture_mask(sm), (x, y))
        lay = Image.new("RGBA", (cw, ch), (38, 38, 46, 0))
        lay.putalpha(dark)
        cv.alpha_composite(lay)
        lit = Image.new("L", (cw, ch), 0)
        lit.paste(aperture_mask(sm, only=k), (x, y))
        plate_metal(cv, lit, GOLD, brush=(x + sm / 2, y + sm / 2), strength=12, n_bands=500)
        bevel(cv, k, x, y, sm)
        # Centred in the opening, not on the blade — see the note in
        # render_architecture.mark() for why.
        lm = letter_mask(ch_, int(sm * 0.30), PINYON, widen=1.0)
        full = Image.new("L", (cw, ch), 0)
        full.paste(lm, (int(x + sm / 2 - lm.width / 2),
                        int(y + sm / 2 - lm.height / 2)))
        plate_metal(cv, full, BRIGHT)
        # Same measured constraint as the architecture diagram: at 20 the two
        # longest names touch in adjacent cells. 17 clears it with margin.
        tracked(d, (cx, y + sm + S(50)), name, monob(17), WHITE, S(1), anchor="ms")
        tracked(d, (cx, y + sm + S(78)), role, mono(14), FAINT, S(2), anchor="ms")

    d.line([(M, S(1452)), (cw - M, S(1452))], fill=HAIR, width=SS)
    tracked(d, (M, S(1500)), "GEMINI 2.5 ON VERTEX AI  ·  GOOGLE ADK  ·  CLICKHOUSE CLOUD VIA MCP",
            mono(19), FAINT, S(6))

    cv.convert("RGB").resize((OUT_W, round(OUT_W * H / W)), Image.LANCZOS).save(out)
    print(f"  {out.name}  {OUT_W}x{round(OUT_W * H / W)}")


def main() -> None:
    identity_card(HERE / "gallery-1-identity.png")


if __name__ == "__main__":
    main()

"""Plate VII — the specialist fleet, one specimen per agent.

Plate VI is the identity: one aperture, six blades, the mark itself. This is
its companion and it does a different job — it names every agent in the fleet
and says what each one is for, at a size someone reads across a room rather
than squints at.

The rule it follows, and the reason it exists: **the name is the identifier.**
Plate VI used to number its specimens 01–06 under the marks, which told you
their order — the one property of this fleet that carries no meaning at all.
They are peers, not a sequence. Nothing here is numbered.

Everything is drawn with the plate's own primitives so the two hang together:
the same brushed gold ramp, the same bevel lit from upper left, the same
etched ground and hairline rules. Agent names are struck in metal rather than
set in ink, which is the whole point of a plate — the important things are
made of the material.

    python design/render_fleet_plate.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from render_plate import (AGENTS, CHROME, DIM, FAINT, GOLD, HAIR, PINYON,
                          WHITE, aperture_mask, bevel, blade_centre, blueprint,
                          drop_shadow, etched_rings, font, letter_mask,
                          paper_ground, plate_metal, tracked, tracked_mask)

HERE = Path(__file__).parent
W, H, SS = 2400, 2920, 3        # Plate VI's proportions exactly
OUT_W = 3840
TYPE = 1.42
BRASS = (170, 143, 82)

# One row per agent, in the fleet's canonical order. The tables are the ones
# each specialist actually queries — not the whole schema, because "reads
# everything" is what a dashboard does and the distinction is the product.
DETAIL = [
    ("gemini-2.5-pro",   "rights_contracts · royalty_ledger · play_events"),
    ("gemini-2.5-flash", "ad_events · play_events"),
    ("gemini-2.5-flash", "fraud_signals · play_events"),
    ("gemini-2.5-flash", "play_events"),
    ("gemini-2.5-flash", "play_events · sentiment_events · titles"),
    ("gemini-2.5-flash", "play_events · sentiment_events"),
]


def main() -> None:
    cw, ch = W * SS, H * SS
    cv = paper_ground((cw, ch), grain=5)
    d = ImageDraw.Draw(cv)
    S = lambda v: int(v * SS)

    mono = lambda s: font("GeistMono-Regular.ttf", S(s * TYPE))
    monob = lambda s: font("GeistMono-Bold.ttf", S(s * TYPE))
    ital = lambda s: font("Italiana-Regular.ttf", S(s))

    M = S(200)
    CW = cw - 2 * M
    CX = cw // 2

    def rule(y, x0=None, x1=None, col=HAIR):
        d.line([(x0 or M, S(y)), (x1 or cw - M, S(y))], fill=col, width=max(SS, 1))

    # ── header ──────────────────────────────────────────────────────────────
    tracked(d, (M, S(196)), "PLATE VII", mono(21), DIM, S(7))
    tracked(d, (CX, S(196)), "ATLAS OF REFLECTIVE FORMS", mono(21), FAINT, S(7), anchor="ms")
    t = "THE SPECIALIST FLEET"
    w = sum(d.textlength(c, font=mono(21)) for c in t) + S(7) * (len(t) - 1)
    tracked(d, (cw - M - w, S(196)), t, mono(21), DIM, S(7))
    rule(232)

    # ── hero: the orchestrator ──────────────────────────────────────────────
    hero = S(560)
    hx, hy = CX - hero // 2, S(300)
    hcx, hcy = CX, hy + hero // 2
    etched_rings(cv, hcx, hcy, step=S(34))

    for i in range(72):
        a = math.radians(i * 5 - 90)
        r0 = hero * 0.560
        r1 = r0 + (S(20) if i % 6 == 0 else S(9))
        d.line([(CX + r0 * math.cos(a), hcy + r0 * math.sin(a)),
                (CX + r1 * math.cos(a), hcy + r1 * math.sin(a))],
               fill=HAIR if i % 6 == 0 else FAINT, width=max(SS, 1))
    r = hero * 0.615
    d.ellipse([CX - r, hcy - r, CX + r, hcy + r], outline=FAINT, width=max(SS, 1))

    ap = Image.new("L", (cw, ch), 0)
    ap.paste(aperture_mask(hero), (hx, hy))
    drop_shadow(cv, ap, dx=S(8), dy=S(13), blur=S(7))
    blueprint(cv, hcx, hcy, hero * 0.20)
    # Band count has to scale with the aperture, not be carried over from the
    # plate. Plate VI runs 1300 bands across an 860 hero — about 1.5 per unit.
    # Reusing that count on a 560 hero packs them twice as tight and the metal
    # washes out to near-white, losing the deep gold the ramp is doing.
    plate_metal(cv, ap, GOLD, brush=(hcx, hcy), strength=14,
                n_bands=int(hero / SS * 1.5))
    for k in range(6):
        bevel(cv, k, hx, hy, hero)
    for k, (ch_, _, _r) in enumerate(AGENTS):
        gx, gy = blade_centre(k)
        lm = letter_mask(ch_, int(hero * 0.145), PINYON, turn=k * 60)
        full = Image.new("L", (cw, ch), 0)
        full.paste(lm, (int(hx + gx / 100 * hero - lm.width / 2),
                        int(hy + gy / 100 * hero - lm.height / 2)))
        plate_metal(cv, full, CHROME)

    m = tracked_mask((cw, ch), (CX, S(1024)), "CONTROL ROOM", ital(96), S(22), anchor="ms")
    drop_shadow(cv, m, dx=S(3), dy=S(6), blur=S(4))
    plate_metal(cv, m, GOLD)
    tracked(d, (CX, S(1080)), "GEMINI 2.5 PRO  ·  ROUTES, CORRELATES, SYNTHESISES",
            mono(17), DIM, S(6), anchor="ms")

    rule(1140)
    tracked(d, (M, S(1198)), "SIX SPECIALISTS", mono(19), DIM, S(7))
    t = "ONE SHARED DATA FOUNDATION"
    w = sum(d.textlength(c, font=mono(19)) for c in t) + S(7) * (len(t) - 1)
    tracked(d, (cw - M - w, S(1198)), t, mono(19), FAINT, S(7))

    # ── the six specimens ───────────────────────────────────────────────────
    # Two columns, three rows. A name set at this size needs a column to
    # itself; six across the page is what forces the type down to a caption,
    # which is the thing this plate exists to undo.
    top, row_h = S(1268), S(384)
    col_w = CW // 2
    mark = S(188)

    for k, (ch_, name, role) in enumerate(AGENTS):
        col, r_i = k % 2, k // 2
        x0 = M + col * col_w
        y0 = top + r_i * row_h

        mx, my = x0, y0
        base = Image.new("L", (cw, ch), 0)
        base.paste(aperture_mask(mark), (mx, my))
        ink = Image.new("RGBA", (cw, ch), (38, 36, 33, 0))
        ink.putalpha(base)
        cv.alpha_composite(ink)

        lit = Image.new("L", (cw, ch), 0)
        lit.paste(aperture_mask(mark, only=k), (mx, my))
        plate_metal(cv, lit, GOLD, brush=(mx + mark / 2, my + mark / 2),
                    strength=13, n_bands=600)
        bevel(cv, k, mx, my, mark)
        lm = letter_mask(ch_, int(mark * 0.30), PINYON, widen=1.0)
        full = Image.new("L", (cw, ch), 0)
        full.paste(lm, (int(mx + mark / 2 - lm.width / 2),
                        int(my + mark / 2 - lm.height / 2)))
        plate_metal(cv, full, CHROME)

        # The name, struck in metal. Italiana at 62 keeps the longest of them
        # (FRAUD SENTINEL) inside the column with room to spare; the mono
        # detail lines below sit in ink so the metal stays the thing you see.
        tx = x0 + mark + S(56)
        nm = tracked_mask((cw, ch), (tx, y0 + S(78)), name, ital(62), S(11))
        drop_shadow(cv, nm, dx=S(2), dy=S(4), blur=S(3))
        plate_metal(cv, nm, GOLD)

        tracked(d, (tx, y0 + S(126)), role, monob(16), WHITE, S(4))
        model, tables = DETAIL[k]
        tracked(d, (tx, y0 + S(170)), model, mono(14), BRASS, S(3))
        tracked(d, (tx, y0 + S(208)), tables, mono(13), DIM, S(2))

        if col == 0:
            d.line([(x0 + col_w - S(46), y0 + S(10)), (x0 + col_w - S(46), y0 + S(250))],
                   fill=HAIR, width=max(SS, 1))
        if r_i < 2:
            d.line([(x0 + S(4), y0 + row_h - S(74)), (x0 + col_w - S(90), y0 + row_h - S(74))],
                   fill=(30, 29, 33), width=max(SS, 1))

    # ── the foundation ──────────────────────────────────────────────────────
    fy = top + row_h * 3 - S(46)
    rule(fy / SS)
    tracked(d, (M, S(2492)), "CLICKHOUSE CLOUD  ·  DATABASE  backlot", mono(20), (222, 216, 204), S(7))
    t = "mcp-clickhouse  ·  MCP OVER STDIO"
    w = sum(d.textlength(c, font=mono(16)) for c in t) + S(4) * (len(t) - 1)
    tracked(d, (cw - M - w, S(2492)), t, mono(16), BRASS, S(4))
    tracked(d, (M, S(2546)),
            "titles · play_events · ad_events · rights_contracts · royalty_ledger · fraud_signals · sentiment_events",
            mono(14), DIM, S(2))

    # ── the unattended path ─────────────────────────────────────────────────
    rule(2610)
    tracked(d, (M, S(2668)), "THE WATCHTOWER", mono(19), BRASS, S(7))
    tracked(d, (M, S(2716)),
            "Four standing briefs run the same fleet on a Cloud Scheduler clock, with nobody in the room.",
            mono(15), (222, 216, 204), S(2))
    tracked(d, (M, S(2756)),
            "Findings are triaged alert / notice / clear and written to ClickHouse whether or not anyone is watching.",
            mono(15), DIM, S(2))

    # ── footer ──────────────────────────────────────────────────────────────
    rule(2812)
    tracked(d, (M, S(2870)), "AURUM REFLEX", mono(21), DIM, S(7))
    t = "ONE LIGHT · TWO METALS"
    w = sum(d.textlength(c, font=mono(21)) for c in t) + S(7) * (len(t) - 1)
    tracked(d, (cw - M - w, S(2870)), t, mono(21), FAINT, S(7))

    out = cv.convert("RGB").resize((OUT_W, round(OUT_W * H / W)), Image.LANCZOS)
    p = HERE / "the-backlot-fleet-plate.png"
    out.save(p, quality=97)
    print(f"  {p.name}  {out.width}x{out.height}")


if __name__ == "__main__":
    main()

"""The Backlot — architecture diagram.

Draws the one thing the README's ASCII sketch could not: that delegation
*returns*. Control Room calls a specialist as a tool and gets the finding back,
which is what makes correlating two domains possible at all. The arrows between
the orchestrator and the fleet run both ways, and that is the diagram's point.

    python design/render_architecture.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from render_plate import (GOLD, INK, aperture_mask, blade_centre, font,
                          letter_mask, plate_metal, tracked, PINYON)

HERE = Path(__file__).parent
W, H, SS = 2400, 1600, 3        # design units; exported at OUT_W
OUT_W = 3840                     # 4K-class export
# The clinical labels were set for a 2400px export and are unreadable once
# the image is viewed small. Everything mono grows by this factor.
TYPE = 1.42

DIM, FAINT, HAIR, LINE = (104, 98, 86), (60, 57, 51), (44, 42, 38), (74, 69, 60)
CHROME_TXT = (222, 216, 204)
WHITE = (255, 255, 255)   # intense white for the one label that must never be missed

AGENTS = [
    ("C", "chain_of_title", "royalty integrity"),
    ("G", "ghost_ads", "ad-insertion leaks"),
    ("F", "fraud_sentinel", "credential abuse"),
    ("P", "premiere_pulse", "playback health"),
    ("W", "performance_war_room", "title performance"),
    ("E", "churn_early_warning", "retention risk"),
]
TABLES = ["titles", "play_events", "ad_events", "rights_contracts",
          "royalty_ledger", "fraud_signals", "sentiment_events"]


def arrow(d, x0, y0, x1, y1, col, head=True, w=2, back=False):
    d.line([(x0, y0), (x1, y1)], fill=col, width=w)
    a = math.atan2(y1 - y0, x1 - x0)
    for (px, py, ang) in ([(x1, y1, a)] if head else []) + ([(x0, y0, a + math.pi)] if back else []):
        s = w * 6
        d.polygon([(px, py),
                   (px - s * math.cos(ang - 0.42), py - s * math.sin(ang - 0.42)),
                   (px - s * math.cos(ang + 0.42), py - s * math.sin(ang + 0.42))], fill=col)


def mark(cv, x, y, size, k):
    dark = Image.new("L", cv.size, 0)
    dark.paste(aperture_mask(size), (x, y))
    layer = Image.new("RGBA", cv.size, (38, 38, 46, 0))
    layer.putalpha(dark)
    cv.alpha_composite(layer)
    lit = Image.new("L", cv.size, 0)
    lit.paste(aperture_mask(size, only=k), (x, y))
    plate_metal(cv, lit, GOLD)
    gx, gy = blade_centre(k)
    lm = letter_mask(AGENTS[k][0], int(size * 0.155), PINYON, turn=k * 60)
    full = Image.new("L", cv.size, 0)
    full.paste(lm, (int(x + gx / 100 * size - lm.width / 2),
                    int(y + gy / 100 * size - lm.height / 2)))
    plate_metal(cv, full, [(0.0, (14, 16, 20)), (0.5, (4, 5, 7)), (1.0, (30, 34, 40))])


def main() -> None:
    cw, chh = W * SS, H * SS
    cv = Image.new("RGBA", (cw, chh), INK + (255,))
    d = ImageDraw.Draw(cv)
    S = lambda v: int(v * SS)
    M, CX = S(110), cw // 2

    mono = lambda s: font("GeistMono-Regular.ttf", S(s * TYPE))
    monob = lambda s: font("GeistMono-Bold.ttf", S(s * TYPE))

    # header
    # Two labels, not three. A centred one between two others has nowhere to go
    # once the type grows, and it collided with the right-hand label outright.
    tracked(d, (M, S(96)), "THE BACKLOT  ·  SYSTEM ARCHITECTURE", mono(22), DIM, S(8))
    lbl = "AGENTIC CINEMA · CLICKHOUSE TRACK"
    wlbl = sum(d.textlength(c, font=mono(22)) for c in lbl) + S(8) * (len(lbl) - 1)
    tracked(d, (cw - M - wlbl, S(96)), lbl, mono(22), FAINT, S(8))
    d.line([(M, S(132)), (cw - M, S(132))], fill=HAIR, width=SS)

    # ── ops question ────────────────────────────────────────────────────────
    # Measure the line and size the box from it. A fixed width was fine for the
    # old type size and overflowed the moment the type grew — a box can never be
    # narrower than what it contains.
    q = "“what happened during the premiere — do they share a root cause?”"
    qf = font("GeistMono-Regular.ttf", S(24 * TYPE))
    qtrack = S(2)
    qw = sum(d.textlength(c, font=qf) for c in q) + qtrack * (len(q) - 1)
    bw, bh = int(qw + S(120)), S(116)
    bx, by = CX - bw // 2, S(200)
    tracked(d, (bx, by - S(22)), "OPS", mono(16), FAINT, S(6))
    d.rectangle([bx, by, bx + bw, by + bh], outline=LINE, width=SS)
    tracked(d, (CX, by + S(72)), q, qf, CHROME_TXT, qtrack, anchor="ms")

    arrow(d, CX, by + bh + S(16), CX, S(408), LINE, w=SS)

    # ── control room ────────────────────────────────────────────────────────
    ap = S(230)
    apx, apy = CX - ap // 2, S(424)
    full = Image.new("L", (cw, chh), 0)
    full.paste(aperture_mask(ap), (apx, apy))
    plate_metal(cv, full, GOLD)
    tracked(d, (CX, apy + ap + S(56)), "CONTROL ROOM", mono(26), CHROME_TXT, S(10), anchor="ms")
    tracked(d, (CX, apy + ap + S(92)), "gemini-2.5-pro  ·  routes, correlates, synthesises",
            mono(18), DIM, S(3), anchor="ms")

    # ── the delegation band — the point of the whole diagram ────────────────
    band_y = S(872)
    d.line([(M, band_y), (cw - M, band_y)], fill=HAIR, width=SS)
    tracked(d, (M, band_y - S(62)), "AgentTool  ·  the finding RETURNS to the orchestrator",
            mono(19), (170, 143, 82), S(4))
    tracked(d, (M, band_y - S(26)),
            "sub_agents would transfer control and never hand it back — no correlation possible",
            mono(17), FAINT, S(3))

    # ── specialists ─────────────────────────────────────────────────────────
    sm = S(150)
    cell = (cw - 2 * M) / 6
    tops = []
    for k, (_, name, role) in enumerate(AGENTS):
        cx = M + cell * (k + 0.5)
        x, y = int(cx - sm / 2), S(952)
        tops.append((cx, y))
        # two-way arrow: call down, finding back up
        arrow(d, cx, band_y + S(16), cx, y - S(18), LINE, w=SS, back=True)
        mark(cv, x, y, sm, k)
        # The agent name is the single most load-bearing label in the diagram —
        # bold and pure white, a clear step up from the role/model lines under it.
        # 17, not the 20 first tried: at 20 the two longest names (performance_
        # war_room, churn_early_warning) are wide enough, centred in adjacent
        # cells, that they touch — measured, not eyeballed, after the first
        # render showed it.
        tracked(d, (cx, y + sm + S(46)), name, monob(17), WHITE, S(1), anchor="ms")
        tracked(d, (cx, y + sm + S(74)), role, mono(15), FAINT, S(2), anchor="ms")
        tracked(d, (cx, y + sm + S(106)), "gemini-2.5-flash" if k else "gemini-2.5-pro",
                mono(14), (78, 74, 66), S(2), anchor="ms")

    # ── clickhouse ──────────────────────────────────────────────────────────
    ty = S(1322)
    for cx, y in tops:
        arrow(d, cx, y + sm + S(126), cx, ty - S(16), LINE, w=SS)
    kw, kh = cw - 2 * M, S(150)
    d.rectangle([M, ty, M + kw, ty + kh], outline=LINE, width=SS)
    tracked(d, (M + S(30), ty + S(46)), "CLICKHOUSE CLOUD  ·  database  backlot",
            mono(21), CHROME_TXT, S(7))
    tl = "mcp-clickhouse  ·  MCP over stdio"
    wtl = sum(d.textlength(c, font=mono(17)) for c in tl) + S(4) * (len(tl) - 1)
    tracked(d, (M + kw - S(30) - wtl, ty + S(46)), tl, mono(17), (170, 143, 82), S(4))
    tcell = kw / len(TABLES)
    for i, t in enumerate(TABLES):
        tracked(d, (M + tcell * (i + 0.5), ty + S(108)), t, mono(16), DIM, S(2), anchor="ms")

    d.line([(M, S(1504)), (cw - M, S(1504))], fill=HAIR, width=SS)
    tracked(d, (M, S(1550)), "ONE DATA FOUNDATION  ·  SIX SPECIALISTS  ·  ONE COMMAND CENTER",
            mono(18), FAINT, S(6))

    out = HERE / "the-backlot-architecture.png"
    cv.convert("RGB").resize((OUT_W, round(OUT_W * H / W)), Image.LANCZOS).save(out)
    print(f"  {out.name}  {OUT_W}x{round(OUT_W * H / W)}")


if __name__ == "__main__":
    main()

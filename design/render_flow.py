"""The Backlot — how one investigation actually runs, step by step.

The architecture diagram in `render_architecture.py` answers "what is this
built from". This one answers a different question that a static box-and-arrow
drawing cannot: "what happens, in what order, and what comes out the far end".

Two things it exists to make visible, because both are invisible in a
structural diagram:

- **There are two ways in.** A person asking a question, and a clock. The
  clock path is the one nobody expects a multi-agent demo to have.
- **Delegation is sequenced, not parallel.** The second specialist is asked
  about the window the first one named. Drawn as two separate steps because
  collapsing them into "the orchestrator asks the specialists" is exactly the
  mistake that produced a confident false negative in testing.

The result panel carries real output from an unattended run, not a mock-up.

    python design/render_flow.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from render_plate import (CHROME, GOLD, INK, aperture_mask, bevel, font,
                          letter_mask, paper_ground, plate_metal, tracked,
                          PINYON)

HERE = Path(__file__).parent
W, H, SS = 2400, 1600, 3
OUT_W = 3840
TYPE = 1.42

DIM, FAINT, HAIR, LINE = (104, 98, 86), (60, 57, 51), (44, 42, 38), (74, 69, 60)
CHROME_TXT = (222, 216, 204)
WHITE = (255, 255, 255)
BRASS = (170, 143, 82)
SLATE = (151, 163, 173)
ALERT = (201, 106, 92)

# Blade index per specialist, in the fleet's canonical order — the same order
# render_gallery and render_architecture use, so a given blade means the same
# agent in every asset. LETTERS must stay aligned with it: an earlier version
# carried its own reordered string and silently drew premiere_pulse's blade
# with chain_of_title's initial.
LETTERS = "CGFPWE"
PULSE, ADS = 3, 1   # premiere_pulse, ghost_ads

STEPS = [
    ("01", "TRIGGER",
     "Two ways in. An operator asks a question — or Cloud Scheduler calls",
     "POST /api/watch/run on the hour and nobody is in the room at all."),
    ("02", "ROUTE",
     "Control Room decides which specialists the question actually needs.",
     "A single-domain question consults one. It routes; it does not fan out."),
    ("03", "DELEGATE, IN ORDER",
     "premiere_pulse first: name the worst window, with its cdn_node and",
     "territory. Then ghost_ads — scoped to that window, not the whole day."),
    ("04", "QUERY",
     "Each specialist writes its own SQL and runs it against ClickHouse",
     "Cloud through the official mcp-clickhouse MCP server."),
    ("05", "RETURN",
     "AgentTool hands each finding back to the orchestrator. sub_agents",
     "would transfer control and never return it — no correlation possible."),
    ("06", "CORRELATE",
     "Two findings sharing a node, a territory and a window are not two",
     "incidents. Control Room names the single cause that explains both."),
]

SQL = "WHERE cdn_node = 'sa-east-1b' AND event_time"


def small_mark(cv, x, y, size, k, letter):
    """A specialist mark: dark aperture, one lit blade, bright initial."""
    dark = Image.new("L", cv.size, 0)
    dark.paste(aperture_mask(size), (x, y))
    layer = Image.new("RGBA", cv.size, (38, 38, 46, 0))
    layer.putalpha(dark)
    cv.alpha_composite(layer)
    lit = Image.new("L", cv.size, 0)
    lit.paste(aperture_mask(size, only=k), (x, y))
    plate_metal(cv, lit, GOLD, brush=(x + size / 2, y + size / 2), strength=12, n_bands=500)
    bevel(cv, k, x, y, size)
    lm = letter_mask(letter, int(size * 0.30), PINYON, widen=1.0)
    full = Image.new("L", cv.size, 0)
    full.paste(lm, (int(x + size / 2 - lm.width / 2), int(y + size / 2 - lm.height / 2)))
    plate_metal(cv, full, CHROME)


def arrow(d, x0, y0, x1, y1, col, w=2, head=True):
    d.line([(x0, y0), (x1, y1)], fill=col, width=w)
    if not head:
        return
    import math
    a = math.atan2(y1 - y0, x1 - x0)
    s = w * 5
    d.polygon([(x1, y1),
               (x1 - s * math.cos(a - 0.42), y1 - s * math.sin(a - 0.42)),
               (x1 - s * math.cos(a + 0.42), y1 - s * math.sin(a + 0.42))], fill=col)


def box(d, x0, y0, x1, y1, outline=LINE, w=None):
    d.rectangle([x0, y0, x1, y1], outline=outline, width=w or SS)


def main() -> None:
    cw, chh = W * SS, H * SS
    cv = paper_ground((cw, chh))
    d = ImageDraw.Draw(cv)
    S = lambda v: int(v * SS)
    M = S(110)

    mono = lambda s: font("GeistMono-Regular.ttf", S(s * TYPE))
    monob = lambda s: font("GeistMono-Bold.ttf", S(s * TYPE))

    # ── header ──────────────────────────────────────────────────────────────
    tracked(d, (M, S(96)), "THE BACKLOT  ·  HOW AN INVESTIGATION RUNS", mono(22), DIM, S(8))
    lbl = "AGENTIC CINEMA · CLICKHOUSE TRACK"
    wlbl = sum(d.textlength(c, font=mono(22)) for c in lbl) + S(8) * (len(lbl) - 1)
    tracked(d, (cw - M - wlbl, S(96)), lbl, mono(22), FAINT, S(8))
    d.line([(M, S(132)), (cw - M, S(132))], fill=HAIR, width=SS)

    # ── the six steps ───────────────────────────────────────────────────────
    # Left rail: number + title + two description lines. Right rail: the one
    # visual that carries what the words cannot.
    top, row = S(196), S(168)
    num_x, txt_x, vis_x = M, M + S(118), M + S(1210)

    for i, (n, title, l1, l2) in enumerate(STEPS):
        y = top + row * i
        # A hairline between steps, not a box around each: this is one
        # continuous sequence, and six boxes would read as six separate things.
        if i:
            d.line([(M, y - S(30)), (cw - M, y - S(30))], fill=(30, 29, 33), width=SS)

        nm = Image.new("L", (cw, chh), 0)
        tracked(ImageDraw.Draw(nm), (num_x, y + S(52)), n, monob(34), 255, S(2))
        plate_metal(cv, nm, GOLD)

        tracked(d, (txt_x, y + S(30)), title, monob(20), WHITE, S(7))
        tracked(d, (txt_x, y + S(72)), l1, mono(16), CHROME_TXT, S(2))
        tracked(d, (txt_x, y + S(104)), l2, mono(16), DIM, S(2))

        cy = y + S(64)

        # Every visual below is kept inside cy ± S(62). The row pitch is
        # S(168) with its separator at y + S(138), so anything taller silently
        # crosses into the next step — which it did, until the ClickHouse box
        # was measured against the rule instead of eyeballed.
        if i == 0:
            # Two entry points, drawn as peers. The clock is not a footnote to
            # the question; it is the half nobody expects.
            bw, bh = S(330), S(46)
            for j, (t, col, tc) in enumerate([("OPS QUESTION", LINE, DIM),
                                              ("CLOUD SCHEDULER · HOURLY", BRASS, CHROME_TXT)]):
                by = cy - S(58) + j * S(70)
                box(d, vis_x, by, vis_x + bw, by + bh, outline=col)
                tracked(d, (vis_x + S(16), by + S(31)), t, mono(13), tc, S(3))
                arrow(d, vis_x + bw + S(12), by + bh // 2, vis_x + bw + S(84), cy, LINE, w=SS)
            small_mark(cv, vis_x + bw + S(96), cy - S(44), S(88), 0, "B")

        elif i == 1:
            small_mark(cv, vis_x, cy - S(50), S(100), 0, "B")
            arrow(d, vis_x + S(114), cy, vis_x + S(196), cy, LINE, w=SS)
            for j in range(6):
                mx = vis_x + S(212) + j * S(72)
                if j in (PULSE, ADS):
                    small_mark(cv, mx, cy - S(28), S(56), j, LETTERS[j])
                else:
                    # Idle, not absent. The four the question does not need are
                    # still there — that is the point of the caption.
                    dark = Image.new("L", (cw, chh), 0)
                    dark.paste(aperture_mask(S(56)), (mx, cy - S(28)))
                    lay = Image.new("RGBA", (cw, chh), (30, 30, 36, 0))
                    lay.putalpha(dark)
                    cv.alpha_composite(lay)
            tracked(d, (vis_x + S(212), cy + S(52)), "2 of 6 consulted", mono(12), FAINT, S(2))

        elif i == 2:
            small_mark(cv, vis_x, cy - S(44), S(88), PULSE, LETTERS[PULSE])
            # The label sits ABOVE the arrow with real clearance; at S(14) it
            # collided with the mark it points at.
            tracked(d, (vis_x + S(108), cy - S(22)), "names the window", mono(12), BRASS, S(2))
            arrow(d, vis_x + S(104), cy + S(4), vis_x + S(330), cy + S(4), BRASS, w=SS)
            small_mark(cv, vis_x + S(342), cy - S(44), S(88), ADS, LETTERS[ADS])
            tracked(d, (vis_x + S(446), cy + S(10)), "scoped to it", mono(13), CHROME_TXT, S(2))

        elif i == 3:
            tracked(d, (vis_x, cy - S(30)), SQL, mono(14), SLATE, S(1))
            tracked(d, (vis_x, cy + S(2)), "BETWEEN '19:15' AND '19:30'", mono(14), SLATE, S(1))
            box(d, vis_x, cy + S(20), vis_x + S(560), cy + S(60), outline=LINE)
            tracked(d, (vis_x + S(16), cy + S(48)), "CLICKHOUSE CLOUD  ·  backlot", mono(13), CHROME_TXT, S(4))

        elif i == 4:
            # Horizontal, right to left: the findings travel back to the
            # orchestrator. Drawn vertically before, the arrows ran up out of
            # the row and into step 04's box.
            small_mark(cv, vis_x, cy - S(44), S(88), 0, "B")
            for j, k in enumerate((PULSE, ADS)):
                mx = vis_x + S(300) + j * S(112)
                small_mark(cv, mx, cy - S(28), S(56), k, LETTERS[k])
                arrow(d, mx, cy, vis_x + S(110), cy, BRASS, w=SS)
            # One label, clear of the arrow it names. Two stacked lines put
            # text on both sides of the line and the arrow ran straight
            # through the lower one; the step's own caption already says what
            # AgentTool does, so the second line was repetition anyway.
            tracked(d, (vis_x + S(132), cy - S(22)), "AgentTool", monob(14), BRASS, S(3))

        elif i == 5:
            # Two symptoms in, one cause out — carrying the actual numbers, so
            # the step is an argument rather than a shape.
            for j, t in enumerate(["buffering +840%", "$3,237 ad revenue lost"]):
                by = cy - S(52) + j * S(56)
                tracked(d, (vis_x, by + S(26)), t, mono(13), CHROME_TXT, S(2))
                arrow(d, vis_x + S(300), by + S(20), vis_x + S(372), cy, LINE, w=SS)
            small_mark(cv, vis_x + S(384), cy - S(44), S(88), 0, "B")
            tracked(d, (vis_x + S(492), cy + S(10)), "one root cause", monob(16), WHITE, S(3))

    # ── the result ──────────────────────────────────────────────────────────
    ry = top + row * len(STEPS) + S(16)
    d.line([(M, ry), (cw - M, ry)], fill=HAIR, width=SS)
    tracked(d, (M, ry + S(48)), "THE RESULT", mono(19), DIM, S(7))

    # Severity badge, in the console's own alert colour so the two read as one
    # system rather than a diagram about a product.
    bx = M + S(240)
    box(d, bx, ry + S(22), bx + S(120), ry + S(62), outline=ALERT)
    tracked(d, (bx + S(20), ry + S(50)), "ALERT", monob(14), ALERT, S(4))

    tracked(d, (M, ry + S(110)),
            "CDN node sa-east-1b in Brazil failed between 19:15 and 19:30 UTC, degrading playback and",
            monob(19), WHITE, S(2))
    tracked(d, (M, ry + S(148)),
            "breaking server-side ad insertion at the same time — one cause, two symptoms.",
            monob(19), WHITE, S(2))
    tracked(d, (M, ry + S(192)),
            "$3,237 lost to ssai_stitch_fail  ·  buffering +840%  ·  drop-off +709%  ·  2 specialists  ·  4 ClickHouse queries",
            mono(16), BRASS, S(3))
    tracked(d, (M, ry + S(228)),
            "Produced unattended, on a schedule. Nobody asked for it.",
            mono(16), CHROME_TXT, S(3))

    d.line([(M, chh - S(112)), (cw - M, chh - S(112))], fill=HAIR, width=SS)
    tracked(d, (M, chh - S(66)),
            "GEMINI 2.5 ON VERTEX AI  ·  GOOGLE ADK  ·  CLICKHOUSE CLOUD VIA MCP  ·  CLOUD RUN  ·  CLOUD SCHEDULER",
            mono(18), FAINT, S(6))

    out = HERE / "the-backlot-flow.png"
    cv.convert("RGB").resize((OUT_W, round(OUT_W * H / W)), Image.LANCZOS).save(out)
    print(f"  {out.name}  {OUT_W}x{round(OUT_W * H / W)}")


if __name__ == "__main__":
    main()

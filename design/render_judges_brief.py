"""The judges-only PDF for Devpost's "Additional info" upload.

A judge screening a track has minutes per project, not hours. Everything in
here exists to shorten the distance between "this claims to correlate across
domains unattended" and "I have seen it do that" — starting with two URLs that
prove it in a browser, with nothing installed and nothing cloned.

It deliberately does NOT restate the project description or ship a copy of the
source. The public repo is the authoritative artifact; a second copy inside a
PDF is just a thing that can fall out of date.

    python design/render_judges_brief.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from render_plate import (DIM, FAINT, GOLD, HAIR, font, paper_ground,
                          plate_metal, tracked, tracked_mask)

HERE = Path(__file__).parent
OUT = HERE.parent / "docs" / "the-backlot-judges-brief.pdf"

# A4 landscape at 210 dpi. Wide enough for two columns of monospaced text at a
# size that survives being read on a laptop, small enough that four pages stay
# far under Devpost's 35 MB ceiling.
PW, PH = 2480, 1754
M = 150
COL = (PW - 2 * M - 100) // 2

IVORY = (231, 226, 216)
BRASS = (170, 143, 82)
SLATE = (151, 163, 173)
WHITE = (255, 255, 255)

URL = "https://the-backlot-203953305168.us-central1.run.app"
REPO = "https://github.com/aaronperez212511-cloud/the-backlot"

# (heading, [(kind, text), ...]) — kind drives the styling, so the content
# stays readable as data rather than being interleaved with draw calls.
LEFT = [
    ("VERIFY IT WITHOUT CLONING ANYTHING", [
        ("p", "Two URLs, a browser, about thirty seconds."),
        ("gap", ""),
        ("url", f"{URL}/"),
        ("d", "The Control Room console. The Watchtower panel in the"),
        ("d", "sidebar is already populated on load — those findings"),
        ("d", "were produced on a schedule. Nobody asked for them."),
        ("gap", ""),
        ("url", f"{URL}/api/watch/findings"),
        ("d", "The same findings as raw JSON: the timestamp, the"),
        ("d", "severity the orchestrator assigned itself, which"),
        ("d", "specialists it consulted, and how many queries each"),
        ("d", "ran against ClickHouse."),
    ]),
    ("VERIFY THE GROUND TRUTH", [
        ("cmd", "python clickhouse/verify_anomalies.py"),
        ("d", "20 assertions against the live ClickHouse database."),
        ("d", "Run 7 September 2026: all 20 passed."),
        ("d", "It checks that the seeded anomalies are present — and"),
        ("d", "that the decoys are too. Households sharing devices,"),
        ("d", "venue devices with high account fan-out and nothing"),
        ("d", "else wrong, a VPN and travel baseline, honest payments"),
        ("d", "carrying rounding drift. Detection here is a"),
        ("d", "discrimination problem, not one equality filter."),
        ("gap", ""),
        ("cmd", "python -m google.adk.cli eval orchestrator \\"),
        ("cmd", "  eval/backlot.evalset.json \\"),
        ("cmd", "  --config_file_path eval/test_config.json"),
        ("d", "5 cases, 23 rubrics generated from ANOMALIES.json."),
        ("d", "Two of them check that the fleet does NOT invent a"),
        ("d", "finding — an agent that always finds something is"),
        ("d", "worse than useless in operations."),
    ]),
]

RIGHT = [
    ("THE ARCHITECTURAL CLAIM, IN ONE LINE", [
        ("p", "Specialists are attached to the orchestrator with"),
        ("p", "AgentTool, not sub_agents."),
        ("gap", ""),
        ("d", "In ADK, sub_agents means control TRANSFER: the"),
        ("d", "orchestrator hands the conversation to one specialist"),
        ("d", "and never gets the floor back, so it can never hold two"),
        ("d", "findings at once. Cross-domain correlation is not hard"),
        ("d", "under sub_agents — it is impossible, and no amount of"),
        ("d", "instruction tuning fixes it."),
        ("gap", ""),
        ("d", "AgentTool returns each finding to the orchestrator, and"),
        ("d", "the same question then produces one synthesized"),
        ("d", "root-cause report. See orchestrator/agent.py."),
    ]),
    ("WHAT RUNS WITH NOBODY IN THE ROOM", [
        ("p", "Cloud Scheduler calls POST /api/watch/run hourly."),
        ("gap", ""),
        ("d", "Four standing briefs run against the same orchestrator"),
        ("d", "with no user anywhere in the call stack. The"),
        ("d", "orchestrator triages its own findings into alert /"),
        ("d", "notice / clear and writes them to ClickHouse whether or"),
        ("d", "not anyone has the console open."),
        ("gap", ""),
        ("d", "Asynchronous in both senses: triggered by a clock"),
        ("d", "rather than a request, and non-blocking — the trigger"),
        ("d", "returns 202 in milliseconds while the investigation"),
        ("d", "keeps running for minutes. See common/watchtower.py."),
    ]),
    ("LINKS", [
        ("url", URL),
        ("url", REPO),
    ]),
]

PAGES = [
    ("the-backlot-flow.png", "HOW ONE INVESTIGATION RUNS"),
    ("the-backlot-fleet-plate.png", "THE SPECIALIST FLEET"),
    ("the-backlot-architecture.png", "SYSTEM ARCHITECTURE"),
]


def column(cv, d, x, y, blocks, mono, monob):
    """Draws one column of sections and returns the y it finished at."""
    for heading, rows in blocks:
        tracked(d, (x, y), heading, monob(19), BRASS, 6)
        d.line([(x, y + 22), (x + COL, y + 22)], fill=HAIR, width=2)
        y += 74
        for kind, text in rows:
            if kind == "gap":
                y += 22
                continue
            if kind == "url":
                tracked(d, (x, y), text, mono(19), SLATE, 1)
            elif kind == "cmd":
                tracked(d, (x, y), text, mono(19), SLATE, 1)
            elif kind == "p":
                tracked(d, (x, y), text, monob(19), WHITE, 1)
            else:
                tracked(d, (x, y), text, mono(18), DIM, 1)
            y += 34
        y += 54
    return y


def brief_page() -> Image.Image:
    cv = paper_ground((PW, PH), grain=4)
    d = ImageDraw.Draw(cv)
    mono = lambda s: font("GeistMono-Regular.ttf", s)
    monob = lambda s: font("GeistMono-Bold.ttf", s)
    ital = lambda s: font("Italiana-Regular.ttf", s)

    tracked(d, (M, 96), "THE BACKLOT", mono(21), DIM, 8)
    t = "AGENTIC CINEMA · CLICKHOUSE TRACK · NOTES FOR JUDGES"
    w = sum(d.textlength(c, font=mono(21)) for c in t) + 8 * (len(t) - 1)
    tracked(d, (PW - M - w, 96), t, mono(21), FAINT, 8)
    d.line([(M, 132), (PW - M, 132)], fill=HAIR, width=2)

    m = tracked_mask((PW, PH), (M, 232), "How to check every claim", ital(76), 8)
    plate_metal(cv, m, GOLD)
    tracked(d, (M, 292),
            "Six Gemini specialists on one ClickHouse foundation. An orchestrator correlates them unprompted, on a schedule.",
            mono(19), IVORY, 2)
    d.line([(M, 340), (PW - M, 340)], fill=HAIR, width=2)

    column(cv, d, M, 400, LEFT, mono, monob)
    column(cv, d, M + COL + 100, 400, RIGHT, mono, monob)

    d.line([(M, PH - 120), (PW - M, PH - 120)], fill=HAIR, width=2)
    tracked(d, (M, PH - 66), "AURUM REFLEX", mono(19), DIM, 7)
    t = "ONE LIGHT · TWO METALS"
    w = sum(d.textlength(c, font=mono(19)) for c in t) + 7 * (len(t) - 1)
    tracked(d, (PW - M - w, PH - 66), t, mono(19), FAINT, 7)
    return cv.convert("RGB")


def plate_page(src: Path, caption: str) -> Image.Image:
    """One asset, fitted whole. Cropping a diagram to fill the page would cut
    the arrows that carry its argument, so it is letterboxed instead."""
    cv = paper_ground((PW, PH), grain=4)
    d = ImageDraw.Draw(cv)
    mono = lambda s: font("GeistMono-Regular.ttf", s)

    tracked(d, (M, 96), caption, mono(21), DIM, 8)
    t = "THE BACKLOT"
    w = sum(d.textlength(c, font=mono(21)) for c in t) + 8 * (len(t) - 1)
    tracked(d, (PW - M - w, 96), t, mono(21), FAINT, 8)
    d.line([(M, 132), (PW - M, 132)], fill=HAIR, width=2)

    im = Image.open(src).convert("RGB")
    box_w, box_h = PW - 2 * M, PH - 132 - 150 - 60
    scale = min(box_w / im.width, box_h / im.height)
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    cv.paste(im, ((PW - im.width) // 2, 132 + 60 + (box_h - im.height) // 2))

    d.line([(M, PH - 120), (PW - M, PH - 120)], fill=HAIR, width=2)
    tracked(d, (M, PH - 66), URL.replace("https://", ""), mono(17), DIM, 3)
    return cv.convert("RGB")


def main() -> None:
    pages = [brief_page()]
    for name, caption in PAGES:
        p = HERE / name
        if p.exists():
            pages.append(plate_page(p, caption))
        else:
            print(f"  skipped (missing): {name}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(OUT, save_all=True, append_images=pages[1:],
                  resolution=210.0, quality=88)
    mb = OUT.stat().st_size / 1_048_576
    print(f"  {OUT.name}  {len(pages)} pages  {mb:.1f} MB")


if __name__ == "__main__":
    main()

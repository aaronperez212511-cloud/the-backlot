"""Generates the proscenium curtain SVG that frames "Control Room".

The pleats are computed rather than drawn by hand: each fold line is the drape's
inner edge scaled toward the outer edge, so the folds fan out at the top and
gather at the tie-back exactly the way the drape itself does. Changing the fold
count is one number here instead of forty hand-placed paths.

Prints the SVG; `--write` patches it straight into web/index.html between the
CURTAIN markers.

    python web/marks/render_curtain.py            # print
    python web/marks/render_curtain.py --write    # patch the console
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

W, H = 200.0, 60.0
FOLDS = 9                 # fold lines per drape
CLOTH_HI, CLOTH_LO = "#a8202e", "#5c0d16"
SHADOW, HILIGHT, GOLD = "#3d070d", "#cf3a46", "#c9a961"

# The drape's inner edge, as offsets from the outer edge. Scaling these by a
# fraction t gives a fold line lying t of the way across the drape.
INNER = [(34, 0), (34, 14), (26, 22), (20, 34), (16, 44), (15, 52), (15, 60)]


def fold(t: float, mirror: bool) -> str:
    """One fold line at fraction t across the drape (0 = outer edge)."""
    def x(v: float) -> float:
        v *= t
        return round(W - v, 2) if mirror else round(v, 2)
    p = [(x(px), py) for px, py in INNER]
    return (f"M{p[0][0]} {p[0][1]} "
            f"C{p[1][0]} {p[1][1]} {p[2][0]} {p[2][1]} {p[3][0]} {p[3][1]} "
            f"C{p[4][0]} {p[4][1]} {p[5][0]} {p[5][1]} {p[6][0]} {p[6][1]}")


def drape(mirror: bool) -> str:
    """Fill plus alternating shadow/highlight fold lines, clipped to the drape."""
    out = []
    for i in range(1, FOLDS + 1):
        t = i / (FOLDS + 1)
        # A shadow in each valley with a narrower highlight just inside it is
        # what makes flat fill read as velvet; a single stroke reads as a line
        # drawn on cloth rather than a fold in it.
        out.append(f'<path d="{fold(t, mirror)}" fill="none" stroke="{SHADOW}" '
                   f'stroke-width="1.5" stroke-opacity=".55"/>')
        out.append(f'<path d="{fold(t + 0.035, mirror)}" fill="none" stroke="{HILIGHT}" '
                   f'stroke-width=".7" stroke-opacity=".4"/>')
    return "\n      ".join(out)


def valance_folds() -> str:
    """Gathered folds hanging from the rod down into the scalloped hem."""
    out = []
    for i in range(1, 26):
        x0 = round(W * i / 26, 2)
        # Each gather leans toward the nearest scallop dip, so the hem and the
        # folds agree instead of reading as two separate patterns.
        dip = round(x0 + (6 if (i % 4) < 2 else -6), 2)
        out.append(f'<path d="M{x0} 0 C{x0} 7 {dip} 11 {dip} 17" fill="none" '
                   f'stroke="{SHADOW}" stroke-width="1.1" stroke-opacity=".45"/>')
        out.append(f'<path d="M{round(x0 + 1.6, 2)} 0 C{round(x0 + 1.6, 2)} 7 '
                   f'{round(dip + 1.6, 2)} 11 {round(dip + 1.6, 2)} 17" fill="none" '
                   f'stroke="{HILIGHT}" stroke-width=".55" stroke-opacity=".3"/>')
    return "\n      ".join(out)


LEFT = "M0 0 L34 0 C34 14 26 22 20 34 C16 44 15 52 15 60 L0 60 Z"
RIGHT = "M200 0 L166 0 C166 14 174 22 180 34 C184 44 185 52 185 60 L200 60 Z"
VALANCE = ("M0 0 L200 0 L200 10 "
           "C186 10 182 20 168 20 C154 20 150 10 136 10 "
           "C122 10 118 20 104 20 C90 20 86 10 72 10 "
           "C58 10 54 20 40 20 C26 20 22 10 8 10 L0 10 Z")
HEM = ("M0 10 C14 10 18 20 32 20 C46 20 50 10 64 10 "
       "C78 10 82 20 96 20 C110 20 114 10 128 10 "
       "C142 10 146 20 160 20 C174 20 178 10 192 10 L200 10")


def svg() -> str:
    tassel = lambda cx: (f'<circle cx="{cx}" cy="21" r="1.6"/>'
                         f'<path d="M{cx - 1.6} 21.8 L{cx + 1.6} 21.8 '
                         f'L{cx + .8} 27 L{cx - .8} 27 Z"/>')
    return f'''<svg viewBox="0 0 200 60" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="cv" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="{CLOTH_HI}"/><stop offset="1" stop-color="{CLOTH_LO}"/>
            </linearGradient>
            <linearGradient id="cf" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stop-color="{CLOTH_HI}"/><stop offset=".45" stop-color="{CLOTH_LO}"/>
              <stop offset=".6" stop-color="{CLOTH_HI}"/><stop offset="1" stop-color="{CLOTH_LO}"/>
            </linearGradient>
            <clipPath id="clL"><path d="{LEFT}"/></clipPath>
            <clipPath id="clR"><path d="{RIGHT}"/></clipPath>
            <clipPath id="clV"><path d="{VALANCE}"/></clipPath>
          </defs>

          <path d="{LEFT}" fill="url(#cf)"/>
          <g clip-path="url(#clL)">
      {drape(False)}
          </g>
          <path d="{RIGHT}" fill="url(#cf)"/>
          <g clip-path="url(#clR)">
      {drape(True)}
          </g>

          <path d="{VALANCE}" fill="url(#cv)"/>
          <g clip-path="url(#clV)">
      {valance_folds()}
          </g>
          <path d="{HEM}" fill="none" stroke="{GOLD}" stroke-width="1.1"/>

          <g fill="{GOLD}">{tassel(32)}{tassel(96)}{tassel(160)}</g>
          <path d="M12 34 C18 31 24 31 27 34" fill="none" stroke="{GOLD}" stroke-width="1.2"/>
          <path d="M188 34 C182 31 176 31 173 34" fill="none" stroke="{GOLD}" stroke-width="1.2"/>
        </svg>'''


def main() -> None:
    out = svg()
    if "--write" not in sys.argv:
        print(out)
        return
    idx = Path(__file__).parent.parent / "index.html"
    s = idx.read_text(encoding="utf-8")
    new = re.sub(r"<svg viewBox=\"0 0 200 60\".*?</svg>", out, s, count=1, flags=re.S)
    if new == s:
        raise SystemExit("curtain block not found in index.html")
    idx.write_text(new, encoding="utf-8", newline="\n")
    print(f"patched {idx} — {FOLDS} folds per drape")


if __name__ == "__main__":
    main()

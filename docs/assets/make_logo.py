"""Generate the derailment logo set (docs/assets/).

Concept: a measurement trace that leaves its rails (the harness's own
topic-drift metaphor), plus a wordmark where the tail of "derailment"
progressively leaves the baseline — the word itself derails.
"""

from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ET

OUT = pathlib.Path(__file__).resolve().parent

MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"

ICON_BODY = """  <rect width="64" height="64" rx="14" fill="#0f1115"/>
  <line x1="12" y1="42" x2="52" y2="42" stroke="#3a4150" stroke-width="3" stroke-linecap="round"/>
  <line x1="12" y1="50" x2="52" y2="50" stroke="#3a4150" stroke-width="3" stroke-linecap="round"/>
  <path d="M 12 46 H 32 L 44 31 L 51 16" fill="none" stroke="#2b5278"
        stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="51" cy="16" r="3.5" fill="#ffb84d"/>"""


def icon_svg() -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
        'role="img" aria-label="derailment icon">\n' + ICON_BODY + "\n</svg>\n"
    )


def wordmark_letters(base: str, drift: list[str], exit_color: str) -> str:
    letters = list("derailment")
    styles = [(0, 0, base)] * 6 + [
        (-1, -6, drift[0]),
        (-3.5, -13, drift[1]),
        (-7, -21, drift[2]),
        (-12, -30, exit_color),
    ]
    parts: list[str] = []
    x = 84.0
    for ch, (dy, rot, color) in zip(letters, styles):
        transform = f"translate({x:.1f},{41 + dy})" + (f" rotate({rot})" if rot else "")
        parts.append(
            f'  <text transform="{transform}" fill="{color}" '
            f'font-family="{MONO}" font-size="19">{ch}</text>'
        )
        x += 11.4
    return "\n".join(parts)


def logo_svg(base: str, drift: list[str], exit_color: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 198 64" '
        'role="img" aria-label="derailment">\n'
        "  <!-- mark: a measurement trace that leaves the rails -->\n"
        "  <g>\n" + ICON_BODY + "\n  </g>\n"
        "  <!-- wordmark: the word itself derails -->\n"
        + wordmark_letters(base, drift, exit_color)
        + "\n</svg>\n"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "icon.svg").write_text(icon_svg(), encoding="utf-8")
    (OUT / "logo.svg").write_text(
        logo_svg("#2a3140", ["#4a6fa5", "#3f6db8", "#2f5fc4"], "#d99a2b"),
        encoding="utf-8",
    )
    (OUT / "logo-dark.svg").write_text(
        logo_svg("#e6e6e6", ["#7d9ec8", "#5d8ac0", "#4a7fd0"], "#ffb84d"),
        encoding="utf-8",
    )
    for name in ("icon.svg", "logo.svg", "logo-dark.svg"):
        ET.parse(OUT / name)  # well-formedness gate
        print(name, "OK", (OUT / name).stat().st_size, "bytes")


if __name__ == "__main__":
    main()

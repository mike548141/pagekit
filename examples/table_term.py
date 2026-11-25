#!/usr/bin/env python3
"""Build examples/table_term.html: a page whose first table holds a defined term.

The subject is an invented tool library's lending notice. Its first table has
a defined term in one of its cells, and the page has no tabs and no blocks to
copy, so nothing the probe does after clicking that term moves the mouse
again before the probe reads whether the table's copy button waits to be
pointed at. The probe runs it beside the sample and small pages. Every name
and figure is invented.

    python3 examples/table_term.py [-o OUT.html]

The page is built on demand and not kept in the repository (it is ignored).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
import pagekit  # noqa: E402

BODY = """
<h2>Borrowing a tool</h2>
<p>Anyone living nearby can borrow from the shelves. Bring the tool back clean, on the day it
is due, and tell us if anything broke so the next person is not caught out.</p>
<table>
<thead><tr><th>Tool</th><th>How long</th><th>Before you take it</th></tr></thead>
<tbody>
<tr><td>Ladder</td><td>Two days</td><td>Read the safety card on the shelf</td></tr>
<tr><td>Hedge trimmer</td><td>One day</td><td>Ask for the battery from the counter</td></tr>
<tr><td>Wheelbarrow</td><td>A week</td><td>Check the tyre; there is a pump by the door</td></tr>
<tr><td>Spade</td><td>A week</td><td>Sign the sheet, like every loan</td></tr>
</tbody>
</table>
<h2>When we are open</h2>
<p>Saturday mornings from nine until twelve, and Wednesday evenings from six until eight.
On a public holiday we stay shut.</p>
<h2>Looking after the shelves</h2>
<p>Volunteers sharpen, oil and mend the tools on the first Saturday of each month. Anyone is
welcome to come and learn how.</p>
"""

TERMS = {
    "Sign the sheet": {"text": "Write your name, the tool and the day it is due on the loan sheet.",
                       "source": "An invented lending guide",
                       "source_url": "https://www.example.org/lending/sheet"},
}


def build() -> str:
    return pagekit.link_terms(pagekit.page(
        "Borrowing from the tool library", body=BODY,
        lead="A short invented page whose first table holds a defined term.",
        byline="An invented tool library", meta=["Invented content"],
        description="A PageKit example page with invented content.",
        footer="An invented tool library · invented content for showing the template"),
        {"name": "Term", "entries": TERMS}, "table_term.html")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", type=Path, default=HERE / "table_term.html")
    args = ap.parse_args()
    args.out.write_text(build(), encoding="utf-8")
    probs = pagekit.check(args.out.read_text(encoding="utf-8"))
    print(f"wrote {args.out}" + ("" if not probs else "; " + "; ".join(probs)))
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())

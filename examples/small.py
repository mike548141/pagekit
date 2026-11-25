#!/usr/bin/env python3
"""Build examples/small.html: a short page that uses only some features.

The subject is an invented walking group's notice for one walk. It has a few
sections, one short table and a block to copy, and no tabs, long tables,
charts or defined terms, so the page carries the kit's core and only the
features it uses. The browser probe runs it beside the sample page, which
uses every feature. Every name and figure is invented.

    python3 examples/small.py [-o OUT.html]

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
<h2>The walk</h2>
<p>We meet at the old wharf at nine and follow the shore path to the lighthouse and back.
The path is flat and firm, about eleven kilometres in all, and takes most people four hours
with a stop for lunch.</p>
<h2>What to bring</h2>
<table>
<thead><tr><th>Item</th><th>Why</th></tr></thead>
<tbody>
<tr><td>Two litres of water</td><td>There is no tap past the wharf</td></tr>
<tr><td>A warm layer</td><td>The point is windy even in summer</td></tr>
<tr><td>Lunch</td><td>We stop at the lighthouse for half an hour</td></tr>
</tbody>
</table>
<h2>Telling us you are coming</h2>
<p>Send a message with your name and how many are coming. Copy this and fill it in:</p>
<div class="pk-message"><p>Kia ora, I am coming on the lighthouse walk. Name: ______. Walkers: __.</p></div>
"""


def build() -> str:
    return pagekit.page(
        "The lighthouse walk", body=BODY,
        lead="A short invented page that uses only some of the kit's features.",
        byline="An invented walking group", meta=["Invented content"],
        description="A PageKit example page with invented content.",
        footer="An invented walking group · invented content for showing the template")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", type=Path, default=HERE / "small.html")
    args = ap.parse_args()
    args.out.write_text(build(), encoding="utf-8")
    probs = pagekit.check(args.out.read_text(encoding="utf-8"))
    print(f"wrote {args.out}" + ("" if not probs else "; " + "; ".join(probs)))
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())

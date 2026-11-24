#!/usr/bin/env python3
"""Build examples/sample.html: every pagekit feature on made-up content.

The subject is an invented community garden's season report. Every name,
place and figure is invented. The page is the kit's own test bed: three
parts, long and wide tables, folds, tabs, a drawing and a chart, callouts, chips,
links across parts, an outside link, and te reo Māori with macrons (one word
deliberately written decomposed, to prove the build composes it).

    python3 examples/sample.py [-o OUT.html]
"""
from __future__ import annotations

import argparse
import base64
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
import pagekit  # noqa: E402

BRAND = {
    "name": "Example Trust",
    "name_te_reo": "Te Rōpū Tauira",
    "names_beside_logo": True,
    "palette": {"primary": "#2a7f62", "secondary": "#1f3a5f", "accent": "#c2862b",
                "attention": "#b0413e", "neutral": "#5a5d63", "divider": "#c3c7cc"},
}

LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="168" height="44" viewBox="0 0 168 44">'
    '<rect x="2" y="6" width="32" height="32" rx="7" fill="#2a7f62"/>'
    '<path d="M10 28 L18 14 L26 28 Z" fill="#fff"/>'
    '<text x="44" y="20" font-family="Arial" font-size="13" font-weight="700" fill="#1f3a5f">EXAMPLE</text>'
    '<text x="44" y="36" font-family="Arial" font-size="13" fill="#1f3a5f">TRUST</text></svg>')

#: Written with a combining macron on purpose: the build must compose it.
DECOMPOSED = "Māori"

CROPS = ["Kūmara", "Potatoes", "Silverbeet", "Beans", "Pumpkin", "Lettuce", "Tomatoes",
         "Garlic", "Puha", "Kale", "Carrots", "Corn"]
GROUPS = ["Tuesday crew", "Holiday club", "Kaumātua group", "Weekend volunteers",
          "Seed savers", "Night owls"]
BEDS = ["North terrace", "Glasshouse", "Orchard rows", "Herb spiral", "Raised beds", "Lower paddock"]


def rng() -> random.Random:
    return random.Random(7319)


def plots_table(n: int = 240) -> str:
    r = rng()
    rows = []
    for i in range(1, n + 1):
        state = r.choice(["Thriving", "Thriving", "Thriving", "Not recorded", "Failed"])
        chip = {"Thriving": "ok", "Not recorded": "unk", "Failed": "bad"}[state]
        rows.append(
            f'<tr id="plot-{i}"><td class="num">{i}</td><td>{r.choice(CROPS)}</td>'
            f'<td>{r.choice(GROUPS)}</td><td>{r.choice(BEDS)}</td>'
            f'<td class="num">{r.randint(2, 640) / 10:.1f}</td>'
            f'<td><span class="pk-chip {chip}">{state}</span></td></tr>')
    return ('<div class="pk-tablewrap"><table><caption>Every plot this season, one row each</caption>'
            '<thead><tr><th class="num">Plot</th><th>Crop</th><th>Looked after by</th><th>Where</th>'
            '<th class="num">Harvest (kg)</th><th>How it went</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def season_log(n: int = 120) -> str:
    r = random.Random(5521)
    cols = ["Day", "Rain (mm)", "High (°C)", "Low (°C)", "Watered", "Volunteers", "Hours",
            "Pests seen", "Frost", "Picked (kg)", "Visitors", "Note"]
    head = "".join(f'<th{" class=num" if c not in ("Watered", "Pests seen", "Frost", "Note") else ""}>{c}</th>'
                   for c in cols)
    rows = []
    for i in range(1, n + 1):
        rows.append(
            f'<tr><td class="num">{i}</td><td class="num">{r.randint(0, 34)}</td>'
            f'<td class="num">{r.randint(12, 29)}</td><td class="num">{r.randint(-2, 14)}</td>'
            f"<td>{r.choice(['yes', 'no'])}</td><td class=\"num\">{r.randint(0, 17)}</td>"
            f'<td class="num">{r.randint(0, 60)}</td><td>{r.choice(["none", "aphids", "slugs", "white butterfly"])}</td>'
            f"<td>{r.choice(['no', 'no', 'no', 'light'])}</td><td class=\"num\">{r.randint(0, 95) / 10:.1f}</td>"
            f'<td class="num">{r.randint(0, 40)}</td><td>{r.choice(["", "seedlings out", "compost turned", "working bee"])}</td></tr>')
    return ('<div class="pk-tablewrap"><table style="min-width:1400px">'
            f'<thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


SITE_PLAN = """<figure class="pk-figure"><p class="pk-finding">The glasshouse sits in the middle of the site, so
seedlings reach every bed in a short walk.</p><div class="pk-canvas">
<svg viewBox="0 0 720 220" role="img" aria-labelledby="fig1t"><title id="fig1t">Site plan: six growing
areas around a central glasshouse, with the shed and compost bays by the gate</title>
<g font-family="inherit" font-size="16" fill="currentColor">
<rect x="10" y="10" width="700" height="200" rx="10" fill="none" stroke="currentColor" stroke-dasharray="6 4"/>
<rect x="30" y="30" width="190" height="60" rx="6" fill="none" stroke="currentColor"/><text x="46" y="66">North terrace</text>
<rect x="265" y="30" width="190" height="60" rx="6" fill="none" stroke="currentColor"/><text x="281" y="66">Orchard rows</text>
<rect x="500" y="30" width="190" height="60" rx="6" fill="none" stroke="currentColor"/><text x="516" y="66">Herb spiral</text>
<rect x="265" y="110" width="190" height="40" rx="6" fill="none" stroke="currentColor" stroke-width="2.5"/><text x="310" y="136">Glasshouse</text>
<rect x="30" y="130" width="190" height="60" rx="6" fill="none" stroke="currentColor"/><text x="46" y="166">Raised beds</text>
<rect x="500" y="130" width="190" height="60" rx="6" fill="none" stroke="currentColor"/><text x="516" y="166">Lower paddock</text>
<text x="300" y="190" font-size="14">Shed · compost · gate</text>
</g></svg></div><figcaption>Not to scale. Invented site.</figcaption></figure>"""


def harvest_chart() -> str:
    """A small bar chart, so the sample shows a chart drawing itself when seen."""
    months = [("Nov", 12), ("Dec", 27), ("Jan", 46), ("Feb", 53), ("Mar", 39), ("Apr", 17)]
    base, scale = 200, 3.0
    grid = "".join(f'<line x1="60" x2="700" y1="{base - v * scale:.0f}" y2="{base - v * scale:.0f}" stroke="currentColor" '
                   f'stroke-opacity=".15"/><text x="50" y="{base - v * scale + 5:.0f}" text-anchor="end" font-size="13">{v}</text>'
                   for v in (0, 20, 40))
    cols = []
    for i, (m, v) in enumerate(months):
        x, h = 90 + i * 100, v * scale
        cols.append(f'<rect x="{x}" y="{base - h:.0f}" width="56" height="{h:.0f}" fill="currentColor" fill-opacity=".55"/>'
                    f'<text x="{x + 28}" y="{base - h - 8:.0f}" text-anchor="middle" font-weight="600">{v}</text>'
                    f'<text x="{x + 28}" y="{base + 22}" text-anchor="middle" font-size="13">{m}</text>')
    return (f'<figure class="pk-figure"><p class="pk-finding">The harvest peaked in February.</p>'
            f'<div class="pk-canvas"><svg viewBox="0 0 720 {base + 34}" role="img" aria-labelledby="fig2t">'
            f'<title id="fig2t">Kilograms picked by month, November to April: 12, 27, 46, 53, 39 and 17</title>'
            f'<g font-family="inherit" font-size="15" fill="currentColor">{grid}{"".join(cols)}</g></svg></div>'
            f'<figcaption>Bars rise when the chart scrolls into view. Invented figures.</figcaption></figure>')


def part_plots() -> str:
    return f"""
<p>This part lists every plot we planted this season: what grew, who looked after it, and how it
went. Everything here is invented to show the template.</p>
<ul class="pk-stats"><li class="pk-stat"><b>240</b><span>plots planted</span></li>
<li class="pk-stat"><b>12</b><span>crops, from kūmara to corn</span></li>
<li class="pk-stat"><b>6</b><span>volunteer groups</span></li></ul>
<div class="pk-callout"><p class="pk-callout-title">What to take from this part</p>
<p>Most plots thrived. The ones that failed are listed first in <a href="#harvest">the harvest</a>,
and the goal they bear on is <a href="#goal-3">goal 3 in part 3</a>.</p></div>
<h3 id="register">The plot register</h3>
<p>The table is long, so it opens at its first rows. The button under it shows the rest; the
headings stay in view as you scroll down it.</p>
{plots_table()}
<h3 id="harvest">The harvest</h3>
{harvest_chart()}
<p>Plots marked <span class="pk-chip bad">Failed</span> gave nothing worth picking. Plots marked
<span class="pk-chip unk">Not recorded</span> were picked without anyone writing it down, which is
not the same as failed. <a href="#plot-200">Plot 200</a> is an example deep in the register; the
link opens the table to reach it.</p>
<details class="pk-fold"><summary>How the register was kept</summary><div class="pk-fold-body">
<p>Each group wrote its plots on the shed whiteboard, and the kaimahi (staff) copied the board into
the register every Friday, then weighed a sample of thirty plots to check it.</p>
{check_table()}
</div></details>
<h3 id="next-steps">What happens next</h3>
<p>The day-by-day log behind these numbers is in <a href="#log">part 2</a>.</p>
"""


#: Plots the register shows as failed, counted from the table so the goals agree with it.
FAILED = plots_table().count(">Failed<")


def check_table() -> str:
    return ('<div class="pk-tablewrap"><table><thead><tr><th>Check</th><th>Plots</th><th>Result</th></tr></thead><tbody>'
            '<tr><td>Crop matches the planting plan</td><td class="num">30</td><td><span class="pk-chip ok">30 of 30</span></td></tr>'
            '<tr><td>Weight within a kilogram</td><td class="num">30</td><td><span class="pk-chip warn">24 of 30</span></td></tr>'
            '<tr><td>Group named on the board</td><td class="num">30</td><td><span class="pk-chip ok">29 of 30</span></td></tr>'
            "</tbody></table></div>")


def part_season() -> str:
    return f"""
<p id="season">A season is mostly weather and people. This part shows the site, then every working day
of the season with the rain, the heat and who turned up.</p>
{SITE_PLAN}
<h3 id="log">The season, day by day</h3>
<p>The log is wide as well as long: scroll it sideways and the pinned headings follow.</p>
{season_log()}
<div class="pk-callout attn"><p class="pk-callout-title">Decision needed</p>
<p>The north terrace lost most of its beans to wind in December (GS-02). A windbreak of flax along its
edge would take one working bee, and it is what <a href="#goal-2">goal 2</a> asks for. Two other
ways were looked at as well; <a href="#option-cloth">shade cloth</a> is the cheapest.</p></div>
<h3 id="windbreak-options">Three ways to break the wind</h3>
<p>Each option on its own tab, so they can be read side by side.</p>
<div class="pk-tabs" aria-label="Windbreak options">
<section class="pk-tab"><h4 id="option-flax">Flax hedge</h4>
<p>Harakeke planted a metre apart along the terrace edge. It takes two seasons to grow tall enough,
costs about $300 in plants, and gives weavers a crop as well.</p>
<ul><li>Lasts for decades with a trim each autumn.</li><li>Needs watering through its first summer.</li></ul></section>
<section class="pk-tab"><h4 id="option-fence">Timber fence</h4>
<p>A slatted fence, half open so the wind slows rather than swirls over it. One working bee builds it;
the timber costs about $1,400.</p>
<ul><li>Works from the day it is built.</li><li>Needs staining every few years.</li></ul></section>
<section class="pk-tab" data-pk-title="Shade cloth"><h4 id="option-cloth">Shade cloth on waratahs</h4>
<p>Windbreak cloth stretched between steel posts. About $250, up in an afternoon, but the cloth
tears in a storm and lasts three or four seasons.</p></section>
</div>
<h3 id="working-bee">Calling the working bee</h3>
<p>The note that went to every group, ready to copy into an email or a text:</p>
<div class="pk-message"><p>Kia ora koutou,</p>
<p>Working bee this Saturday from 9 am to build the windbreak on the north terrace. Bring gloves
and a spade; morning tea is on us.</p>
<p>Ngā mihi, the garden committee</p></div>
<p>The watering timer on the glasshouse runs this schedule; copy it into the timer's app:</p>
<pre><code>zone glasshouse  start 06:00  minutes 12  days mon,wed,fri
zone raised-beds start 06:15  minutes 8   days daily
zone orchard     start 19:30  minutes 20  days sat</code></pre>
<h3 id="garden-terms">Words used here</h3>
<dl class="pk-facts"><dt>Working bee</dt><dd>A day when everyone comes to do one big job together.</dd>
<dt>Raised bed</dt><dd>A bed built up above the ground, easier on knees and quicker to warm.</dd>
<dt>Companion planting</dt><dd>Growing plants side by side because each helps the other.</dd></dl>
"""


def part_goals() -> str:
    goals = [
        ("Every group has a plot in a raised bed", "Five of six groups", "warn"),
        ('The north terrace has a windbreak (<a href="#option-fence">the fence</a> is the likeliest)', "Not started", "bad"),
        ("Fewer than one plot in ten fails", f"{FAILED} of 240 failed", "ok" if FAILED < 24 else "warn"),
        ("Seed saved from every heritage crop", "Seven of nine crops", "warn"),
        ("A working bee every month", "Done", "ok"),
    ]
    rows = "".join(
        f'<tr id="goal-{i}"><th scope="row">{i}</th><td>{t}</td><td><span class="pk-chip {c}">{s}</span></td></tr>'
        for i, (t, s, c) in enumerate(goals, 1))
    return f"""
<p>This part sets out the goals we chose for the garden and where each one stands.</p>
<div class="pk-tablewrap"><table><thead><tr><th>#</th><th>Goal</th><th>Where we are</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<h3 id="why">Why these five</h3>
<p>They follow from the plots in <a href="#register">part 1</a> and the season in
<a href="#log">part 2</a>, and from what other gardens have written (GS-02, GS-03). Ideas for more are welcome on the garden's page, for example
<a href="https://www.example.org/garden">the example garden</a> (an outside link).</p>
<h3 id="sources">Sources</h3>
<p>Every source this page cites, with when it was read. A citation such as GS-01 shows its
source when the pointer rests on it.</p>
<div class="pk-tablewrap"><table><thead><tr><th>Key</th><th>Work</th><th>Written by</th><th>Read on</th></tr></thead><tbody>
<tr id="src-gs-01"><td>GS-01</td><td>Growing kūmara in a cool climate</td><td>An invented growers' society</td><td>2025-09-14</td></tr>
<tr id="src-gs-02"><td>GS-02</td><td>Windbreaks for small gardens</td><td>An invented garden trust</td><td>2025-10-02</td></tr>
<tr id="src-gs-03"><td>GS-03</td><td>Keeping a working bee working</td><td>An invented volunteers' network</td><td>2025-11-20</td></tr>
</tbody></table></div>
<details class="pk-fold"><summary>Te reo Māori in this template</summary><div class="pk-fold-body">
<p>Macrons must survive every route a file takes: Māori, kūmara, kaumātua, Ōtautahi, Tāmaki
Makaurau, whānau, tūāpapa. Capitals too: Ā Ē Ī Ō Ū.</p>
<p>This word was typed with a combining macron and composed by the build: {DECOMPOSED}.</p>
</div></details>
"""


def build() -> str:
    logo = "data:image/svg+xml;base64," + base64.b64encode(LOGO_SVG.encode()).decode()
    return pagekit.link_sources(pagekit.page(
        "Our garden's season: what grew, and what we will change",
        brand=BRAND, logo=logo,
        eyebrow="PageKit sample page",
        lead="Three related topics in one file. Choose a part to read; the others stay a click away.",
        audience="For anyone trying the template",
        byline="Prepared by the garden committee", meta=["Version 1", "Invented content"],
        description="A PageKit sample page with invented content.",
        parts=[
            {"id": "plots", "title": "What we grew",
             "summary": "240 plots, who looked after them, and how each went", "html": part_plots()},
            {"id": "the-season", "title": "How the season went",
             "summary": "The site, and every working day of the season", "html": part_season()},
            {"id": "goals", "title": "Our goals",
             "summary": "Five goals and where we stand on each", "html": part_goals()},
        ],
        footer="Example Trust · Te Rōpū Tauira · invented content for showing the template",
        marking="UNCLASSIFIED", watermark="SAMPLE"), "sample.html")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", type=Path, default=HERE / "sample.html")
    args = ap.parse_args()
    args.out.write_text(build(), encoding="utf-8")
    probs = pagekit.check(args.out.read_text(encoding="utf-8"))
    print(f"wrote {args.out}" + ("" if not probs else "; " + "; ".join(probs)))
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())

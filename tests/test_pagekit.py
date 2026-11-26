"""PageKit's own seams: where `apply` puts the kit, what a built page carries,
and that every feature's server-side half does what the page's script expects.

The browser half is exercised by `tools/probe.py` in real engines.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import pagekit as kit

ROOT = Path(__file__).resolve().parents[1]

PAGE = ("<!doctype html><html><head><title>t</title></head><body>"
        "<table><thead><tr><th>a</th></tr></thead><tbody><tr><td>1</td></tr>"
        "</tbody></table><script>var x='</body>';</script></body></html>")

#: A brand for the contrast check that is not the neutral one.
SAMPLE_BRAND = {"name": "Example Trust",
                "palette": {"primary": "#2a7f62", "secondary": "#1f3a5f", "accent": "#c2862b",
                            "attention": "#b0413e", "neutral": "#5a5d63", "divider": "#c3c7cc"}}


def test_apply_places_css_in_head_and_script_last_in_body():
    out = kit.apply(PAGE)
    assert out.index('<style id="pagekit-css">') < out.index("</head>")
    assert out.index('<script id="pagekit-js">') > out.index("var x=")
    assert out.rstrip().endswith("</body></html>")


def test_apply_is_idempotent():
    once = kit.apply(PAGE)
    assert kit.apply(once) == once
    assert once.count('id="pagekit-js"') == 1


def test_apply_without_a_closing_head_keeps_the_doctype_first():
    """HTML lets a page leave </head> out. The styles must then go before
    <body>, never above <!doctype>, which would put the page in quirks mode."""
    page = ('<!doctype html>\n<html lang="en-NZ">\n<head>\n<meta charset="utf-8">\n<title>t</title>\n'
            '<body><p>x</p></body></html>')
    out = kit.apply(page)
    assert out.startswith("<!doctype html>")
    assert out.index("<meta charset") < out.index('<style id="pagekit-css">') < out.index("<body>")
    assert kit.check(out) == []


def test_apply_without_head_or_body_still_carries_the_kit():
    out = kit.apply("<p>fragment</p>")
    assert 'id="pagekit-css"' in out and 'id="pagekit-js"' in out


def test_every_colour_pairing_meets_contrast_for_the_neutral_and_a_sample_brand():
    """Both schemes are derived from the brand, so any brand gets its own dark
    scheme, and every text pairing is checked, not hoped."""
    assert kit.contrast_failures(kit.tokens(None)) == []
    assert kit.contrast_failures(kit.tokens(SAMPLE_BRAND)) == []


def test_a_built_page_travels_as_one_file():
    html = kit.page("Title", brand={"name": "Org", "name_te_reo": "Te Rōpū"},
                    parts=[{"title": "One", "html": "<p>a</p>"},
                           {"title": "Two", "html": "<p>b</p>"}])
    assert kit.check(html) == []
    assert html.index('<meta charset="utf-8">') < 200
    assert 'lang="en-NZ"' in html and 'lang="mi"' in html
    assert html.count('<section class="pk-part" id=') == 2 and 'data-pk-part="part-one"' in html


def test_macrons_are_stored_composed():
    """A macron typed as a letter plus a combining mark is stored as one
    character, so it renders, searches and sorts as the same word."""
    decomposed = "Māori"
    assert "Māori" in kit.page("t", body=f"<p>{decomposed}</p>")
    assert "Māori" in kit.apply(f"<p>{decomposed}</p>")
    assert any("NFC" in m for m in kit.check(f'<meta charset="utf-8"><html lang="en-NZ">{decomposed}'))


def test_check_names_what_stops_a_page_travelling():
    bad = ('<html><head><script src="https://cdn.example/x.js"></script>'
           '<link rel="stylesheet" href="site.css"><style>@import url(a.css)</style></head>'
           '<body><img src="logo.png"></body></html>')
    found = " | ".join(kit.check(bad))
    for what in ("charset", "lang", "external script", "linked stylesheet", "external picture", "@import"):
        assert what in found, what
    ok = '<meta charset="utf-8"><html lang="en-NZ"><img src="data:image/png;base64,AAAA"><svg><use href="#a"/></svg>'
    assert kit.check(ok) == []


def test_compose_scopes_each_page_to_its_part():
    a = ('<html><head><style>:root{--x:1}body{color:red}h2{margin:0}</style></head><body>'
         '<header class="m">MASTHEAD-A</header><a class="skip" href="#c">SKIPLINK-A</a><h1>A</h1>'
         '<h2 id="c">A part</h2><a href="#c">to c</a></body></html>')
    b = '<html><head><style>body{color:blue}</style></head><body><h2 id="c">B</h2></body></html>'
    html = kit.compose("Both", [{"html": a, "title": "A"}, {"html": b, "title": "B"}])
    assert "@scope (#pkc-1) {" in html and "@scope (#pkc-2) {" in html
    assert ":scope{--x:1}" in html and ":scope{color:red}" in html
    assert "MASTHEAD-A" not in html and "SKIPLINK-A" not in html and "<h1>A</h1>" not in html
    assert 'id="p1-c"' in html and 'href="#p1-c"' in html and 'id="p2-c"' in html
    assert kit.check(html) == []


def test_the_sample_page_builds_and_passes_the_check(tmp_path):
    dest = tmp_path / "sample.html"
    out = subprocess.run([sys.executable, str(ROOT / "examples/sample.py"), "-o", str(dest)],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    text = dest.read_text(encoding="utf-8")
    assert "pk-part" in text and "Te Rōpū Tauira" in text
    # The committed copy is the one people open: it must be current.
    assert (ROOT / "examples/sample.html").read_text(encoding="utf-8") == text


def test_a_page_says_when_it_was_published():
    slot = '<div class="docmeta"><b>Report</b><br>Published <time data-pk-published></time></div>'
    out = kit.set_published(slot, "2025-03-19")
    assert '<time data-pk-published datetime="2025-03-19">19 March 2025</time>' in out
    assert kit.published_of(out) == "2025-03-19"
    assert kit.set_published(out, "2025-03-20").count("20 March 2025") == 1


def test_a_change_of_look_is_not_a_new_edition():
    """The published date moves only when the words a reader reads move."""
    a = ('<html lang="en"><head><style>p{color:red}</style></head><body>'
         '<p>Control 1.2.C.01 applies.</p><button>More</button></body></html>')
    b = ('<html lang="en-NZ"><head><style>p{color:blue}</style></head><body>'
         '<p>Control <a href="x">1.2.C.01</a> applies.</p><button>Show more</button></body></html>')
    c = a.replace("applies", "does not apply")
    assert kit.fingerprint(a) == kit.fingerprint(b)
    assert kit.fingerprint(a) != kit.fingerprint(c)


def test_moving_a_page_onto_the_builder_is_not_a_new_edition():
    """The builder's masthead, parts panel, skip link and part numbers are
    furniture; so is another way's masthead and contents, when named."""
    words = "<p>The beds were dug in spring.</p>"
    parts = [{"title": "Spring", "html": words}, {"title": "Summer", "html": "<p>Then summer.</p>"}]
    a = kit.page("Season report", parts=parts, meta=["Draft"], byline="A. Gardener")
    b = kit.page("Season report", parts=parts, meta=["Final", "For members"], byline="B. Gardener")
    assert kit.fingerprint(a) == kit.fingerprint(b)
    changed = [dict(parts[0], html="<p>The beds were dug in autumn.</p>"), parts[1]]
    assert kit.fingerprint(kit.page("Season report", parts=changed)) != kit.fingerprint(a)
    older = ('<a class="skip" href="#m">Skip</a><header class="banner"><b>Garden club</b></header>'
             '<nav class="toc"><a href="#s">Spring</a></nav><h2>Spring</h2>' + words)
    newer = kit.page("Season report", body="<h2>Spring</h2>" + words)
    newer = newer[newer.index('<main'):newer.index('</main>')]
    old_way = ("a.skip", "header.banner", "nav.toc")
    assert kit.fingerprint(older, old_way) == kit.fingerprint(newer, old_way)
    assert kit.fingerprint(older) != kit.fingerprint(newer)
    with pytest.raises(ValueError):
        kit.fingerprint(older, ("header .banner",))


def test_identifiers_link_to_their_source_and_only_known_ones():
    refs = [{"name": "STD", "pattern": r"\b\d+\.\d+\.C\.\d{2}\b", "url": "https://std.example/doc#",
             "entries": {"1.2.C.01": {"anchor": "P-7", "level": "Must", "text": "Do the thing."}}}]
    html = '<p>See 1.2.C.01 and 9.9.C.99.</p><code>1.2.C.01</code><a href="#x">1.2.C.01</a>'
    out = kit.link_refs(html, refs)
    assert out.count('href="https://std.example/doc#P-7"') == 1
    assert 'title="STD 1.2.C.01 (MUST): Do the thing."' in out
    assert "9.9.C.99" in out and "<code>1.2.C.01</code>" in out
    assert kit.link_refs(out, refs) == out


def test_identifiers_link_to_their_document_and_carry_their_entry():
    """An identifier links into the document holding its entry, carries a
    synopsis for the hover card and its whole entry for the side pane."""
    rs = [{"name": "Requirement", "pattern": r"\bREQ-\d+\b", "in_code": True,
           "entries": {"REQ-7": {"anchor": "keep-records", "doc": "guide/Handbook.html",
                                    "also": {"guide/Handbook.html": "keep-records",
                                             "guide/Questions.html": "keep-records"},
                                    "level": "MUST", "title": "Do it",
                                    "fields": [["Description", "Says </script> plainly"]]}}}]
    page = ('<html><body><p>See REQ-7 and <code>REQ-7</code>; REQ-999 is unknown.</p>'
            '<script>var x = "<a>";</script><p>After the script, REQ-7.</p>'
            '<script id="pagekit-js">/* kit */</script></body></html>')
    away = kit.link_refs(page, rs, "notes/Elsewhere.html")
    assert away.count('data-pk-ref="REQ-7"') == 3, "in prose, in code, and after a script"
    assert 'href="../guide/Handbook.html#keep-records"' in away
    assert "REQ-999" in away and 'data-pk-ref="REQ-999"' not in away
    blob = away.split('id="pk-refdata">', 1)[1].split("</script>", 1)[0]
    data = json.loads(blob.replace("<\\/", "</"))
    assert data["REQ-7"]["l"] == "MUST" and data["REQ-7"]["t"] == "Do it"
    assert away.index('id="pk-refdata"') < away.index('id="pagekit-js"'), "data before the kit's script"
    assert kit.link_refs(away, rs, "notes/Elsewhere.html") == away, "idempotent"
    home = kit.link_refs(page, rs, "guide/Questions.html")
    assert 'href="#keep-records"' in home, "a page holding the entry links to itself"


def test_the_theme_is_restored_before_first_paint_and_the_charset_stays_first():
    out = kit.apply('<!doctype html><html><head><meta charset="utf-8"><title>t</title></head><body></body></html>',
                    "en-NZ")
    assert out.index('<meta charset="utf-8">') < out.index('id="pagekit-prepaint"') < out.index("<title>")
    assert kit.check(out) == []
    assert kit.apply(out).count('id="pagekit-prepaint"') == 1


def test_the_kits_own_comments_never_reach_a_page():
    """The kit's comments are for its maintainers; a page goes to readers, who
    can view its source."""
    js_src = (ROOT / "src/pagekit/kit.js").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", js_src, flags=re.S)
    assert "/*" not in code and "*/" not in code, "kit.js holds a comment marker inside code"
    out = kit.apply("<html><head></head><body><p>x</p></body></html>", "en-NZ")
    assert "/*" not in out


def test_a_marking_and_a_watermark_are_set_per_document():
    """The marking follows the Protective Security Requirements' rule for a
    document: capitals, bold, its classification's colour, top and bottom of
    every page. Both are per-document settings."""
    base = kit.apply('<!doctype html><html><head><meta charset="utf-8"><title>t</title></head>'
                     '<body><p>Words.</p></body></html>', "en-NZ")
    marked = kit.set_marks(base, "in-confidence", "DRAFT")
    assert marked.count(">IN-CONFIDENCE</div>") == 2, "top and bottom, in capitals"
    assert '<meta name="protective-marking" content="IN-CONFIDENCE">' in marked
    assert '@top-center' in marked and '@bottom-center' in marked, "on every printed page"
    assert ">DRAFT</div>" in marked
    assert kit.set_marks(marked, "IN-CONFIDENCE", "DRAFT") == marked, "idempotent"
    assert kit.apply(marked, "en-NZ") == marked, "the kit re-applied leaves the marks alone"
    assert kit.set_marks(marked) == base, "an empty value removes both"
    assert kit.fingerprint(marked) == kit.fingerprint(base), "a marking is not a new edition"
    assert kit.classification_of("SECRET//ORCON")[0] == "SECRET"
    assert kit.classification_of("TOP SECRET")[1] == "#ff0000"
    with pytest.raises(ValueError):
        kit.set_marks(base, "PRIVATE")


def test_a_page_names_the_tables_the_kit_leaves_alone():
    base = kit.apply('<!doctype html><html><head><meta charset="utf-8"><title>t</title></head>'
                     '<body><p>x</p></body></html>', "en-NZ")
    out = kit.set_skip(base, 'table.layout, #summary, a[title="x"]')
    assert '<meta name="pk-skip" content="table.layout, #summary, a[title=&quot;x&quot;]">' in out
    assert out.index('name="pk-skip"') < out.index('id="pagekit-css"')
    assert kit.set_skip(out, 'table.layout, #summary, a[title="x"]') == out, "idempotent"
    assert kit.apply(out, "en-NZ") == out, "the kit re-applied leaves it alone"
    assert kit.set_skip(out, "") == base, "empty removes it"
    assert kit.fingerprint(out) == kit.fingerprint(base)
    # Marks and the skip setting both sit just before the kit's styles: either
    # order, re-applied, leaves the page as it was.
    # The skip setting is replaced where it stands, so re-applying it after
    # marks were added (both sit just before the kit's styles) moves nothing.
    marked = kit.set_marks(out, "IN-CONFIDENCE", "DRAFT")
    assert kit.set_skip(kit.apply(marked, "en-NZ"), 'table.layout, #summary, a[title="x"]') == marked


def test_every_section_gets_an_id_from_its_words_and_keeps_its_own():
    page = ('<h2>The gaps</h2><script>var s="<h2>not a heading</h2>"</script>'
            '<h3 id="kept">Kept</h3><h3>The gaps</h3>'
            '<details><summary>How it was <b>built</b></summary></details>'
            '<details><summary><h3>Inner</h3></summary></details><h4>Ōtepoti &amp; more</h4>')
    out = kit.anchor_headings(page)
    assert '<h2 id="the-gaps">' in out and '<h3 id="the-gaps-2">' in out  # unique
    assert '<h3 id="kept">' in out and 'id="kept" id=' not in out          # its own id kept
    assert '<summary id="how-it-was-built">' in out                        # a fold title
    assert '<summary><h3 id="inner">' in out                               # the heading, not its fold
    assert '<h4 id="otepoti-more">' in out                                 # macrons fold to letters
    assert '"<h2>not a heading</h2>"' in out                               # script untouched
    assert kit.anchor_headings(out) == out


def test_a_page_made_another_way_becomes_parts_by_its_section_class():
    page = ('<section class="part" id="s01">\n<h2><span class="num">01</span>What we offer &amp; why</h2></section>'
            '<section class="part" id="s02"><h2 class="x">Two</h2></section><section id="o"><h2>Not a part</h2></section>')
    out = kit.mark_parts(page, "part")
    assert out.count("pk-part\"") == 2 and 'id="o"><h2>Not a part' in out
    assert 'data-pk-title="What we offer &amp; why"' in out          # the number left out
    assert '<h2 class="pk-part-title"><span class="num">01' in out and '<h2 class="x pk-part-title">' in out
    assert kit.mark_parts(out, "part") == out
    assert kit.mark_parts('<section class="part"><h2>Only one</h2></section>', "part").count("pk-part") == 0


def test_a_marking_that_could_break_out_of_its_stylesheet_is_refused():
    base = kit.apply('<!doctype html><html><head><meta charset="utf-8"><title>t</title></head><body></body></html>')
    for bad in ('SENSITIVE</style><img src=x>', 'SENSITIVE"', "IN-CONFIDENCE; color: red"):
        with pytest.raises(ValueError):
            kit.set_marks(base, bad)
    assert ">SENSITIVE//ORCON</div>" in kit.set_marks(base, "SENSITIVE//ORCON")


def test_the_logo_address_is_escaped():
    html = kit.page("T", logo='x" onerror="alert(1)')
    assert 'onerror="alert(1)"' not in html and "&quot; onerror=" in html


def test_a_refset_url_must_be_relative_or_web():
    page = "<p>See 1.2.C.01.</p>"
    entries = {"1.2.C.01": {"anchor": "a"}}
    for bad in ("javascript:alert(1)", " JavaScript:alert(1)", "java\tscript:x", "data:text/html,x"):
        with pytest.raises(ValueError):
            kit.link_refs(page, [{"name": "S", "pattern": r"\b1\.2\.C\.01\b", "url": bad, "entries": entries}])
    for ok in ("https://std.example/doc#", "http://std.example/", "doc.html#", "#", ""):
        kit.link_refs(page, [{"name": "S", "pattern": r"\b1\.2\.C\.01\b", "url": ok, "entries": entries}])


def test_check_finds_more_ways_a_page_reaches_out():
    found = " | ".join(kit.check(
        '<meta charset="utf-8"><html lang="en"><head><base href="https://cdn.example/">'
        '<meta http-equiv="refresh" content="0;url=https://elsewhere.example/">'
        '<link rel="preconnect" href="https://cdn.example"></head><body>'
        '<video poster="https://cdn.example/p.png"></video><svg><image href="https://cdn.example/i.png"/></svg>'
        '<form action="https://forms.example/"></form><a href="#x" ping="https://track.example/">x</a></body></html>'))
    for what in ("base address", "meta refresh", "network ahead", "video poster", "SVG image", "form", "pings"):
        assert what in found, what
    assert kit.check('<meta charset="utf-8"><html lang="en"><svg><image href="data:image/png;base64,AA"/>'
                     '<use href="#a"/></svg><form action="#"></form></html>') == []


def test_the_generator_version_is_the_package_version():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{kit.VERSION}"' in text


SOURCES_PAGE = (
    '<p>As REF-12 and [r-wind] show, and REF-12 again; REF-120 is not one.</p>'
    '<h3 id="references">References</h3><p>Every work cited.</p>'
    '<table><thead><tr><th>Key</th><th>Work</th><th>Author</th><th>Accessed</th></tr></thead><tbody>'
    '<tr id="ref-12"><td>REF-12</td><td>A field guide</td><td>A society</td><td>2025-01-02</td></tr>'
    '<tr id="ref-w"><td><code>[r-wind]</code></td><td><a href="https://e.example/">A note on wind</a></td><td>A trust</td><td></td></tr>'
    '</tbody></table><h3>Next</h3><p>REF-12 later.</p>')


def test_a_cited_source_links_to_its_row_and_carries_who_and_when():
    out = kit.link_sources(SOURCES_PAGE, "a/p.html")
    assert out.count('href="#ref-12"') == 3 and out.count('href="#ref-w"') == 1
    assert "REF-120" in out and 'data-pk-ref="REF-120"' not in out, "a longer id is not a citation"
    assert '<table data-pk-ref="off">' in out, "the list does not link to itself"
    blob = json.loads(out.split('id="pk-refdata">', 1)[1].split("</script>", 1)[0].replace("<\\/", "</"))
    assert blob["REF-12"]["t"] == "A field guide" and blob["REF-12"]["m"] == "A society · 2025-01-02"
    assert blob["REF-12"]["n"] == "Source" and not blob["REF-12"].get("x")
    assert kit.link_sources(out, "a/p.html") == out, "idempotent"
    assert kit.fingerprint(out) == kit.fingerprint(SOURCES_PAGE), "a citation link is not a new edition"


def test_sources_marked_by_attribute_or_list_and_none_left_alone():
    page = ('<p>As [r1] shows.</p><ul data-pk-sources><li id="r-1"><code>[r1]</code> A book, 2024</li></ul>')
    out = kit.link_sources(page)
    assert 'href="#r-1"' in out and 'data-pk-ref="[r1]"' in out
    plain = "<p>No sources here: REF-1.</p>"
    assert kit.link_sources(plain) == plain


def test_a_region_marked_off_is_never_linked():
    refs = [{"name": "STD", "pattern": r"\b1\.2\.C\.01\b", "url": "https://std.example/doc#",
             "entries": {"1.2.C.01": {"anchor": "P-7"}}}]
    page = '<p>1.2.C.01</p><table data-pk-ref="off"><tr><td><table><tr><td>1.2.C.01</td></tr></table>1.2.C.01</td></tr></table><p>1.2.C.01</p>'
    out = kit.link_refs(page, refs)
    assert out.count('data-pk-ref="1.2.C.01"') == 2, "outside the region only, nested tables included"


def test_a_link_the_page_already_makes_to_a_source_gets_its_card():
    page = ('<p>As <a href="#ref-12" title="A field guide">the guide</a> says.</p><h3>References</h3>'
            '<table><thead><tr><th>Key</th><th>Work</th><th>Author</th></tr></thead><tbody>'
            '<tr id="ref-12"><td>REF-12</td><td>A field guide</td><td>A society</td></tr></tbody></table>')
    out = kit.link_sources(page, "p.html")
    assert '<a class="pk-ref" href="#ref-12" title="A field guide" data-pk-ref="REF-12">the guide</a>' in out
    blob = json.loads(out.split('id="pk-refdata">', 1)[1].split("</script>", 1)[0].replace("<\\/", "</"))
    assert blob["REF-12"]["m"] == "A society"
    assert kit.link_sources(out, "p.html") == out



def test_kit_js_never_defines_a_function_twice():
    # kit.js is one scope: a second definition silently replaces the first.
    names = re.findall(r"^\s*function (\w+)\(", (ROOT / "src/pagekit/kit.js").read_text(encoding="utf-8"), re.M)
    twice = sorted({n for n in names if names.count(n) > 1})
    assert not twice, f"defined more than once in kit.js: {twice}"


def test_tabs_show_every_pane_without_the_script_and_on_paper():
    # Tabs are marked up as plain sections, so a page without scripting shows
    # every pane under its heading; on paper the stylesheet shows them all.
    sample = (ROOT / "examples/sample.html").read_text(encoding="utf-8")
    group = re.search(r'<div class="pk-tabs"[^>]*>(.*?)</div>\s*<h3', sample, re.S)
    assert group, "the sample shows tabs"
    panes = re.findall(r'<section class="pk-tab"[^>]*>\s*<h4\b', group.group(1))
    assert len(panes) >= 2 and "hidden" not in group.group(0)
    css = (ROOT / "src/pagekit/kit.css").read_text(encoding="utf-8")
    assert re.search(r"@media print\s*\{[^}]*\.pk-tablist[^}]*display:\s*none", css)
    assert re.search(r"\.pk-tab\[hidden\][^{]*\{[^}]*display:\s*block !important", css)


GLOSSARY = {"name": "Term", "entries": {
    "Raised bed": {"text": "A bed built up above the ground", "doc": "words.html", "anchor": "raised-bed"},
    "Mulch": {"text": "A layer laid over soil", "doc": "words.html", "anchor": "mulch", "also": ["mulched"]},
    "GPS": {"text": "A satellite position", "source_url": "https://www.example.org/gps", "source": "Example Atlas"},
    "Compost": {"text": "Rotted plant matter", "source_url": "javascript:alert(1)"}}}


def _terms(html: str) -> list[tuple[str, str]]:
    return re.findall(r'<a class="pk-ref pk-term" href="([^"]*)" data-pk-ref="term:([^"]+)"', html)


def test_a_defined_term_links_once_per_section_with_its_meaning():
    page = ("<html><body><h2>Raised bed</h2><p>Two raised beds, then a raised bed and some mulch.</p>"
            "<p>Mulched again.</p><h2>Later</h2><p>One more raised   bed.</p></body></html>")
    out = kit.link_terms(page, GLOSSARY, "pages/a.html")
    assert _terms(out) == [("../words.html#raised-bed", "Raised bed"), ("../words.html#mulch", "Mulch"),
                           ("../words.html#raised-bed", "Raised bed")]
    assert ">raised beds</a>" in out and "<h2>Raised bed</h2>" in out, "the reader's own spelling, headings left alone"
    data = json.loads(re.search(r'id="pk-refdata">(.*?)</script>', out).group(1))
    assert data["term:Mulch"]["k"] == "Mulch" and data["term:Mulch"]["t"] == "A layer laid over soil"
    assert kit.link_terms(out, GLOSSARY, "pages/a.html") == out
    assert kit.fingerprint(out) == kit.fingerprint(page), "linking a term changes no word"


def test_an_acronym_matches_only_as_written_and_a_bad_address_links_nowhere():
    page = "<html><body><p>gps is not GPS. Compost <code>GPS</code> <a href='#x'>GPS</a></p></body></html>"
    out = kit.link_terms(page, GLOSSARY, "a.html")
    assert _terms(out) == [("https://www.example.org/gps", "GPS")]
    assert "gps is not" in out and "Compost <code>" in out


def test_terms_leave_a_glossary_list_a_message_and_headings_alone():
    page = ('<html><body><h3>Mulch</h3><dl data-pk-ref="off"><dt>Mulch</dt><dd>A raised bed of mulch</dd></dl>'
            '<div class="pk-message"><p>Bring mulch.</p></div><table><thead><tr><th>Mulch</th></tr></thead>'
            "<tbody><tr><td>mulch</td></tr></tbody></table></body></html>")
    out = kit.link_terms(page, GLOSSARY, "words.html")
    assert _terms(out) == [("#mulch", "Mulch")], "only the table cell, linked in-page on the glossary's own page"


def test_a_part_titled_with_its_own_number_keeps_it():
    """"Part 0 · Soil" is numbered 0, not by its place; a part with no number
    of its own, beside such parts, goes unnumbered."""
    parts = [{"title": "Overview", "html": "<p>a</p>"},
             {"title": "Part 0 · Soil", "html": "<p>b</p>"},
             {"title": "Part 1 · Seeds", "html": "<p>c</p>"}]
    out = kit.page("Season report", parts=parts)
    nav = out[out.index('<nav class="pk-parts"'):out.index("</nav>", out.index('<nav class="pk-parts"'))]
    assert '<span class="pk-pn">0</span><span class="pk-pt">Soil</span>' in nav
    assert '<span class="pk-pn">1</span><span class="pk-pt">Seeds</span>' in nav
    assert '<a href="#part-overview" data-pk-part="part-overview"><span class="pk-pt">Overview</span>' in nav
    assert '<h2 class="pk-part-title" id="part-part-0-soil-h">Part 0 · Soil</h2>' in out
    plain = kit.page("Season report", parts=[{"title": "Soil", "html": "x"}, {"title": "Seeds", "html": "y"}])
    assert '<span class="pk-pn">2</span><span class="pk-pt">Seeds</span>' in plain



#: Classes the script puts on <html> itself, never on an element inside it.
ROOT_CLASSES = ("pk-js", "pk-one", "pk-all", "pk-later", "pk-paneled", "pk-slim", "pk-drawer", "pk-paneopen")


def test_no_rule_looks_for_a_page_class_inside_another_element():
    """The script puts pk-js, pk-one and the rest on <html>, so a rule that
    looks for one inside another element never matches: `.pk-js .pk-one
    .pk-part` left the margins of eleven hidden parts above part 12."""
    css = re.sub(r"/\*.*?\*/", "", (ROOT / "src/pagekit/kit.css").read_text(encoding="utf-8"), flags=re.S)
    selectors = [x.strip() for block in re.findall(r"([^{}]+)\{[^{}]*\}", css) for x in block.split(",")]
    roots = "|".join(c.replace("-", "\\-") for c in ROOT_CLASSES)
    bad = [x for x in selectors if re.search(rf"\S\s+[^\s]*\.(?:{roots})\b", x)]
    assert not bad, f"rules that can never match: {bad}"
    assert re.search(r"\.pk-js\.pk-one \.pk-part \+ \.pk-part \{ margin-top: 0; \}", css)
    assert re.search(r"\.pk-part \+ \.pk-part \{ margin-top: 3rem; \}", css), "every part shown keeps its spacing"
    assert re.search(r"@media print \{[^@]*\.pk-part \+ \.pk-part \{ break-before: page; margin-top: 0; \}", css)


def _body(html: str) -> str:
    """A built page's own markup, without the kit's stylesheet and script."""
    return html.split("<body>", 1)[1].split(f'<script id="{kit.JS_ID}">', 1)[0]


def _nav(html: str) -> str:
    at = html.index('<nav class="pk-parts"')
    return html[at:html.index("</nav>", at)]


def test_part_groups_label_the_contents_and_numbering_runs_on():
    parts = [{"title": "Why", "html": "<p>a</p>", "group": "The story"},
             {"title": "What changes", "html": "<p>b</p>"},
             {"title": "Costs", "html": "<p>c</p>", "group": "The detail"},
             {"title": "Terms", "html": "<p>d</p>", "group": "Reference"}]
    out = kit.page("Plan", parts=parts)
    nav = _nav(out)
    assert nav.count('class="pk-parts-group"') == 3 and nav.count("<ol") == 3 and nav.count("</ol>") == 3
    assert ('<p class="pk-parts-group" id="pk-pg-2">The detail</p><ol aria-labelledby="pk-pg-2">'
            '<li><a href="#part-costs" data-pk-part="part-costs"><span class="pk-pn">3</span>') in nav
    assert re.search(r'<section class="pk-part" id="part-costs"[^>]* data-pk-group="The detail">', out)
    assert 'id="part-what-changes" aria-labelledby="part-what-changes-h" data-pk-title="What changes">' in out
    late = kit.page("Plan", parts=[{"title": "Start", "html": "x"}, {"title": "Notes", "html": "y", "group": "Reference"}])
    assert re.search(r'<ol><li><a href="#part-start".*?</ol><p class="pk-parts-group"', _nav(late)), \
        "a part before the first label sits in an unlabelled list"


def test_a_page_without_part_groups_is_built_as_before():
    out = kit.page("Plan", parts=[{"title": "Why", "html": "<p>a</p>"}, {"title": "How", "html": "<p>b</p>"}])
    assert "pk-parts-group" not in _body(out) and "data-pk-group" not in _body(out)
    assert re.fullmatch(r'<nav class="pk-parts"[^>]*><p class="pk-parts-label">In this document</p><ol><li>.*</li></ol>',
                        _nav(out))
    blank = kit.page("Plan", parts=[{"title": "Why", "html": "<p>a</p>", "group": " "}, {"title": "How", "html": "<p>b</p>"}])
    assert blank == out, "a blank label is no label"


def test_the_title_block_past_the_first_part_is_the_title_alone_on_screen_only():
    css = (ROOT / "src/pagekit/kit.css").read_text(encoding="utf-8")
    js = (ROOT / "src/pagekit/kit.js").read_text(encoding="utf-8")
    screen = re.search(r"@media screen \{\n  \.pk-js\.pk-one\.pk-later \.pk-hero \{.*?\n\}", css, re.S)
    assert screen and ".pk-later .pk-hero h1" in screen.group(0), "the one-line title is for the screen only"
    assert re.search(r"@media print \{[^@]*\.pk-heroaway\[hidden\] \{ display: block !important", css)
    assert re.search(r"\.pk-heroaway\[hidden=\"until-found\"\] \{ margin: 0 !important", css), \
        "what is hidden until found leaves no margin behind"
    assert re.search(r"function showAll\(\) \{\n(?:  .*\n)*?  heroFor\(false\);", js), "every part shown, the block is whole"
    built = kit.page("Plan", eyebrow="Kicker", lead="Lead.", parts=[{"title": "A", "html": "x"}, {"title": "B", "html": "y"}])
    assert _body(built).count("<h1") == 1 and "pk-heroaway" not in _body(built), "the script acts, not the build"


def test_items_shown_by_level_all_show_without_the_script_and_on_paper():
    css = (ROOT / "src/pagekit/kit.css").read_text(encoding="utf-8")
    js = (ROOT / "src/pagekit/kit.js").read_text(encoding="utf-8")
    assert re.search(r"@media screen \{ \.pk-lvl-out[^}]*display: none !important; \}", css), \
        "an item not shown is hidden on screen only, so paper shows every item"
    assert "display: none" not in re.sub(r"@media screen \{[^}]*\}", "", _chunks(ROOT / "src/pagekit/kit.css")["level-filter"]
                                         ).replace(".pk-levelbar { display: none", "")
    assert js.count('tr.classList.contains("pk-filtered") || tr.classList.contains("pk-lvl-out")') == 2, \
        "a copied table leaves out the rows not shown"
    out = kit.page("Needs", body='<ol data-pk-filter="must, should"><li data-pk-levels="must">Lock</li>'
                                 '<li data-pk-levels="should could">Bench</li></ol>')
    assert "level-filter" in kit.features_carried(out) and "pk-lvl-out" not in _body(out)


# ── pages carry the core and only the features they use ──────────────────────

_FENCE = re.compile(r"^/\* pk:feature ([a-z-]+) \*/\n(.*?)^/\* pk:end \1 \*/\n", re.S | re.M)


def _chunks(path: Path) -> dict[str, str]:
    src = path.read_text(encoding="utf-8")
    out = {"core": _FENCE.sub("", src)}
    for m in _FENCE.finditer(src):
        out[m.group(1)] = out.get(m.group(1), "") + m.group(2)
    return out


def _code(js: str) -> str:
    """Script with its comments, strings and regular expressions blanked."""
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    js = re.sub(r"'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"", '""', js)
    return re.sub(r"(?<=[(,=:!&|?{};])\s*/(?![/*])(?:\\.|\[[^\]]*\]|[^/\\\n])+/[gimsuy]*", " RX", js)


def _declared(js: str) -> set[str]:
    """The names a part of kit.js declares at the top of the kit's scope."""
    out = set(re.findall(r"^function ([\w$]+)\(", js, re.M))
    for m in re.finditer(r"^var (.*?);\s*$", js, re.M):
        depth, cur, names = 0, "", []
        for ch in m.group(1):
            depth += (ch in "([{") - (ch in ")]}")
            if ch == "," and not depth:
                names.append(cur)
                cur = ""
            else:
                cur += ch
        names.append(cur)
        out |= {n.split("=")[0].strip() for n in names}
    return out


def test_every_fence_names_a_feature_or_a_shared_part():
    known = set(kit.FEATURES) | set(kit.SHARED)
    for name in ("kit.js", "kit.css"):
        text = (ROOT / "src/pagekit" / name).read_text(encoding="utf-8")
        opened = re.findall(r"^/\* pk:feature ([a-z-]+) \*/$", text, re.M)
        closed = re.findall(r"^/\* pk:end ([a-z-]+) \*/$", text, re.M)
        assert opened == closed and set(opened) <= known, f"{name}: fences {opened} / {closed}"
        assert not re.search(r"^/\* pk:", _FENCE.sub("", text), re.M), f"{name}: a fence is nested or unmatched"
    js = _chunks(ROOT / "src/pagekit/kit.js")
    assert set(js) == {"core"} | known, "every feature and shared part has its script"
    for f, needs in kit.FEATURES.items():
        assert set(needs) <= set(kit.SHARED), f"{f} needs only shared parts"


def test_no_part_of_the_kit_uses_a_name_from_a_feature_it_does_not_need():
    """Left out of a page, a feature's names do not exist there: the core and
    every other feature must reach it only through on() and fire()."""
    chunks = {k: _code(v) for k, v in _chunks(ROOT / "src/pagekit/kit.js").items()}
    declared = {k: _declared(v) for k, v in chunks.items()}
    for k, js in chunks.items():
        mine = {k} | (kit._with_needs([k]) if k in kit.FEATURES else set())
        allowed = declared["core"].union(*(declared[n] for n in mine))
        others = set().union(*(v for n, v in declared.items() if n not in mine and n != "core"))
        used = set(re.findall(r"(?<![\w$.])([A-Za-z_$][\w$]*)\b(?!\s*:(?!:))", js))
        bad = sorted((used & others) - allowed)
        assert not bad, f"{k} uses {bad}, declared only in a feature it does not need"


def test_assets_carry_everything_by_default_and_only_what_is_asked_for_otherwise():
    css, js = kit.assets()
    assert "@PK-KIT@" not in js and f'var KIT = "{" ".join(kit.FEATURES)}";' in js
    assert "function initTabs(" in js and ".pk-tablist" in css
    css0, js0 = kit.assets([])
    assert 'var KIT = "";' in js0 and "function initTabs(" not in js0 and ".pk-tablist" not in css0
    assert "function buildPanel(" in js0 and ".pk-panel" in css0, "the core always comes"
    css1, js1 = kit.assets(["section-links"])
    assert "function copyAs(" in js1 and "function initLinks(" in js1, "a feature brings the parts it needs"
    assert "function paneShow(" not in js1 and ".pk-panehead" not in css1
    with pytest.raises(ValueError):
        kit.assets(["no-such-feature"])


@pytest.mark.parametrize("feature", list(kit.FEATURES))
def test_every_feature_alone_is_well_formed_script(feature, tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("no node here to parse the script; the probe runs it in real engines")
    for names in ([], [feature]):
        f = tmp_path / "kit.js"
        f.write_text(kit.assets(names)[1], encoding="utf-8")
        out = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        assert out.returncode == 0, out.stderr


#: Invented markup for each feature, and markup that looks like it but is not.
USES = {
    "tabs": ('<div class="pk-tabs"><section class="pk-tab"><h3>A</h3></section>'
             '<section class="pk-tab"><h3>B</h3></section></div>',
             '<div class="pk-tabs"><section class="pk-tab"><p>one pane</p></section></div>'),
    "level-filter": ('<ul class="pk-cards" data-pk-filter="must = Must have, could"><li class="pk-card" '
                     'data-pk-levels="must">A</li></ul>',
                     '<ul data-pk-filter="off"><li data-pk-levels="must">A</li></ul><p data-pk-find="off">B</p>'),
    "long-tables": ("<table><tbody>" + "<tr><td>1</td></tr>" * 6 + "</tbody></table>",
                    "<figure><table><tbody>" + "<tr><td>1</td></tr>" * 9 + "</tbody></table></figure>"),
    "pinned-headings": ("<table><thead><tr><th>a</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table>",
                        '<table data-pk="off"><thead><tr><th>a</th></tr></thead></table>'),
    "charts": ('<svg viewBox="0 0 80 40"><line x1="0" y1="38" x2="80" y2="38"/><rect x="1" y="2" width="3" '
               'height="4"/><rect x="5" y="6" width="7" height="8"/><rect x="9" y="1" width="2" height="3"/></svg>',
               '<figure data-pk-motion="off"><svg viewBox="0 0 80 40"><line x1="0" y1="1" x2="9" y2="1"/>'
               '<rect/><rect/><rect/></svg></figure>'),
    "cards": ('<p><a class="pk-ref" href="#r1" data-pk-ref="R-1">R-1</a></p>',
              '<div data-pk-ref="off"><p>R-1</p></div>'),
    "copy-out": ("<table><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></table>",
                 '<p><a href="#x"><svg width="16" height="16" viewBox="0 0 16 16"></svg></a></p>'),
    "copy-blocks": ("<pre>make check</pre>", "<figure><pre>a drawing in text</pre></figure>"),
    "section-links": ("<h3>Soil</h3>", "<header><h2>Masthead</h2></header><h1>Title</h1>"),
}


@pytest.mark.parametrize("feature", list(USES))
def test_a_feature_is_found_in_the_markup_and_only_there(feature):
    yes, no = USES[feature]
    wrap = "<!doctype html><html><head></head><body>{}</body></html>".format
    assert feature in kit.features_needed(wrap(yes)), f"{feature} not found in {yes}"
    assert feature not in kit.features_needed(wrap(no)), f"{feature} found in {no}"


def test_a_page_carries_only_the_features_its_content_uses():
    small = kit.page("A walk", body="<h2>Start</h2><p>At the wharf.</p><h2>Finish</h2><p>At the point.</p>")
    assert kit.features_carried(small) == ["section-links"]
    assert "function initTabs(" not in small and "function initCopy(" not in small
    assert "function buildPanel(" in small and kit.check(small) == []
    every = kit.page("Everything", body="".join(y for y, _ in USES.values()))
    assert kit.features_carried(every) == list(kit.FEATURES), "a page using every feature carries every feature"
    assert len(small) < len(every) - 30_000


def test_a_page_can_name_features_its_markup_does_not_show_and_keeps_them():
    out = kit.page("A walk", body="<p>Filled in later.</p>", features=["tabs"])
    assert '<meta name="pk-features" content="tabs">' in out
    assert kit.features_carried(out) == ["tabs"]
    again = kit.apply(out)
    assert kit.features_carried(again) == ["tabs"] and kit.apply(again) == again, "re-applying keeps the names"
    assert kit.features_carried(kit.page("All", body="<p>x</p>", features="all")) == list(kit.FEATURES)
    with pytest.raises(ValueError):
        kit.page("A walk", body="<p>x</p>", features=["sparkles"])


def test_a_page_running_its_own_script_carries_everything_unless_it_names_its_features():
    own = "<!doctype html><html><head></head><body><p>x</p><script>document.title = 'y';</script></body></html>"
    assert kit.features_carried(kit.apply(own)) == list(kit.FEATURES)
    named = kit.apply(own, features=())
    assert kit.features_carried(named) == [] and '<meta name="pk-features" content="">' in named
    data = '<html><body><script type="application/json" id="x">{}</script><p>x</p></body></html>'
    assert kit.features_carried(kit.apply(data)) == [], "a data block is not a script"


def test_linking_identifiers_after_the_build_brings_the_cards_in():
    built = kit.page("Rules", body="<p>See REF-1 for the rule.</p>")
    assert "cards" not in kit.features_carried(built)
    ref = {"name": "Rule", "pattern": r"REF-\d+", "url": "https://example.org/r#",
           "entries": {"REF-1": {"anchor": "r1", "title": "Keep gates shut"}}}
    out = kit.link_refs(built, [ref])
    assert "cards" in kit.features_carried(out) and "function openPane(" in out
    assert kit.link_refs(out, [ref]) == out


def test_refit_brings_a_changed_page_up_to_date():
    built = kit.page("Rules", body="<p>None yet.</p>")
    grown = built.replace("<p>None yet.</p>", "<pre>make check</pre>")
    assert "copy-blocks" not in kit.features_carried(grown)
    out = kit.refit(grown)
    assert "copy-blocks" in kit.features_carried(out) and kit.refit(out) == out
    assert kit.refit("<html><body><pre>x</pre></body></html>") == "<html><body><pre>x</pre></body></html>"


def test_the_small_page_builds_and_carries_only_some_features(tmp_path):
    dest = tmp_path / "small.html"
    out = subprocess.run([sys.executable, str(ROOT / "examples/small.py"), "-o", str(dest)],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    text = dest.read_text(encoding="utf-8")
    carried = kit.features_carried(text)
    assert carried and set(carried) < set(kit.FEATURES), "the probe's page with only some features"


def test_the_table_term_page_keeps_the_shape_the_probe_needs(tmp_path):
    """A defined term in the first table, and no tabs or copy blocks that would
    move the probe's mouse after it clicks the term."""
    dest = tmp_path / "table_term.html"
    out = subprocess.run([sys.executable, str(ROOT / "examples/table_term.py"), "-o", str(dest)],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    text = dest.read_text(encoding="utf-8")
    carried = kit.features_carried(text)
    assert {"cards", "copy-out"} <= set(carried) and not {"tabs", "copy-blocks"} & set(carried)
    first = re.search(r"<table\b.*?</table>", text, re.S)
    assert first and 'class="pk-ref pk-term"' in first.group(0)

"""PageKit's own seams: where `apply` puts the kit, what a built page carries,
and that every feature's server-side half does what the page's script expects.

The browser half is exercised by `tools/probe.py` in real engines.
"""

from __future__ import annotations

import json
import re
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

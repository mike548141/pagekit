#!/usr/bin/env python3
"""pagekit: one template for every HTML deliverable, for any organisation.

Two ways in:

* ``page(...)`` builds a whole page: masthead, title, an optional set of
  *parts* (one shown at a time, chosen from a selector), the footer, the one
  base stylesheet and the reader features. Branding comes from a brand dict,
  so the same page can wear any organisation's colours, logo and names.
* ``apply(html)`` adds the reader features alone to a page made some other
  way, so older pages gain them without being rebuilt.

``check(html)`` reports anything that would stop a page travelling as one
file: an external script, style, font or picture, a missing or late character
set, a missing language, text that is not in composed Unicode form (macrons
written as a letter plus a combining mark), a page over the size limit.

Every page is one self-contained file. It is built to be opened directly, from
a mail attachment, and from SharePoint, OneDrive or Teams, whose viewers run a
page inside a locked-down frame (no storage, no pop-ups, no downloads, no
print dialog from script). The features degrade to "everything shown" when
scripting is off and on paper.

Standard library only, and nothing in this package names or describes any
organisation: branding and content always come from the caller.

    python3 -m pagekit apply PAGE.html [-o OUT.html] [--lang en-NZ]
    python3 -m pagekit check PAGE.html [PAGE.html ...]
"""

from __future__ import annotations

import argparse
import base64
import html as _html
import re
import sys
import unicodedata
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
VERSION = "0.1.0"   # the package version; a test holds it to pyproject.toml

CSS_ID = "pagekit-css"
JS_ID = "pagekit-js"
BASE_ID = "pagekit-base"
TOKENS_ID = "pagekit-tokens"

#: A page larger than this is still one file, but mails and previews slowly.
SIZE_LIMIT = 4 * 1024 * 1024
LOGO_MEDIA = {".png": "image/png", ".svg": "image/svg+xml", ".jpg": "image/jpeg",
              ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
LOGO_MAX_BYTES = 512 * 1024


def esc(value: Any) -> str:
    return _html.escape(str(value), quote=True)


def nfc(text: str) -> str:
    """Composed Unicode, so a macron vowel is one character (ā, not a + ̄).

    The decomposed form renders as a misplaced mark in some fonts and breaks
    find-in-page and sorting; normalising costs nothing."""
    return unicodedata.normalize("NFC", text)


# ── colour ───────────────────────────────────────────────────────────────────

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")


def _rgb(colour: str) -> tuple[float, float, float]:
    if not _HEX.match(colour):
        raise ValueError(f"a colour is written #rgb or #rrggbb, not {colour!r}")
    h = colour[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex(rgb: Iterable[float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def luminance(colour: str) -> float:
    def lin(c: float) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """The WCAG 2 contrast ratio between two colours, 1 to 21."""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def mix(a: str, b: str, t: float) -> str:
    """``a`` moved a fraction ``t`` of the way to ``b``."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(x + (y - x) * t for x, y in zip(ra, rb, strict=True))


def reach(colour: str, bg: str, ratio: float) -> str:
    """``colour`` moved toward black or white, whichever the background is
    not, just far enough to meet ``ratio`` against ``bg``. Unchanged when it
    already does: the brand colour itself is kept wherever it can be."""
    if contrast(colour, bg) >= ratio:
        return colour
    target = "#000000" if luminance(bg) > 0.18 else "#ffffff"
    lo, hi = 0.0, 1.0
    for _ in range(24):
        mid = (lo + hi) / 2
        if contrast(mix(colour, target, mid), bg) >= ratio:
            hi = mid
        else:
            lo = mid
    return mix(colour, target, hi)


# ── brand ────────────────────────────────────────────────────────────────────

#: A neutral brand: what a page wears when the caller gives none.
NEUTRAL_BRAND: dict[str, Any] = {
    "name": "",
    "palette": {"primary": "#3d5a80", "secondary": "#293241",
                "accent": "#5f7f3a", "attention": "#a4461c",
                "neutral": "#585b60", "divider": "#c4c7cc"},
    "font": '-apple-system,BlinkMacSystemFont,"Segoe UI",Aptos,Calibri,Roboto,'
            '"Helvetica Neue",Arial,sans-serif',
}

LIGHT_BG, LIGHT_INK = "#ffffff", "#1d2125"
DARK_BG, DARK_INK = "#15181b", "#e7eaee"

#: Status colours: meaning, not brand. Each is a text colour on its own tint.
STATUS = {"ok": "#2f6f3e", "warn": "#8a5a00", "bad": "#a3262a",
          "info": "#2b5c8a", "unk": "#5d5f66"}


def tokens(brand: dict | None) -> dict[str, dict[str, str]]:
    """Every colour token for both schemes, derived from the brand.

    The brand's own colours are used as given wherever they meet the contrast
    they are used at; otherwise they are moved just far enough. Dark is
    derived from the same brand, never typed, so a different brand gets its
    own dark scheme."""
    b = brand or {}
    pal = {**NEUTRAL_BRAND["palette"], **(b.get("palette") or {})}
    out: dict[str, dict[str, str]] = {}
    for scheme, bg, ink in (("light", LIGHT_BG, LIGHT_INK), ("dark", DARK_BG, DARK_INK)):
        dark = scheme == "dark"
        surface = mix(bg, pal["primary"], 0.05 if not dark else 0.08)
        surface2 = mix(bg, pal["primary"], 0.10 if not dark else 0.14)
        t = {
            "bg": bg, "ink": ink, "surface": surface, "surface-2": surface2,
            "muted": reach(mix(ink, bg, 0.30), surface, 4.5),
            "line": mix(bg, pal["divider"] if not dark else ink, 0.55 if not dark else 0.22),
            "brand": reach(pal["primary"], bg, 3.0),
            "brand-text": reach(str(pal.get("primary_text") or pal["primary"]) if not dark
                                else pal["primary"], surface, 4.5),
            "brand-2": reach(pal["secondary"], bg, 3.0),
            "brand-2-text": reach(pal["secondary"], surface, 4.5),
            "accent": reach(pal["accent"], bg, 3.0),
            "accent-text": reach(pal["accent"], surface, 4.5),
            "attn": reach(pal["attention"], bg, 3.0),
            "attn-text": reach(pal["attention"], surface, 4.5),
        }
        # A solid brand fill that carries text: the brand, darkened only as far
        # as white text on it needs.
        t["brand-fill"] = reach(pal["primary"], "#ffffff", 4.5)
        t["brand-on"] = "#ffffff"
        for k, c in STATUS.items():
            tint = mix(bg, c, 0.12 if not dark else 0.22)
            t[f"{k}-bg"] = tint
            t[k] = reach(c if not dark else mix(c, "#ffffff", 0.45), tint, 4.5)
        out[scheme] = t
    return out


#: (text token, background token, minimum): every pairing the stylesheet uses.
TEXT_PAIRS = [("ink", "bg", 4.5), ("ink", "surface", 4.5), ("ink", "surface-2", 4.5),
              ("muted", "bg", 4.5), ("muted", "surface", 4.5),
              ("brand-text", "bg", 4.5), ("brand-text", "surface", 4.5),
              ("brand-2-text", "surface", 4.5), ("accent-text", "surface", 4.5),
              ("attn-text", "surface", 4.5), ("brand-on", "brand-fill", 4.5),
              ("brand", "bg", 3.0)] + [(k, f"{k}-bg", 4.5) for k in STATUS]


def contrast_failures(tok: dict[str, dict[str, str]]) -> list[str]:
    out = []
    for scheme, t in tok.items():
        for fg, bg, need in TEXT_PAIRS:
            r = contrast(t[fg], t[bg])
            if r < need:
                out.append(f"{scheme}: {fg} on {bg} is {r:.2f}:1, under {need}:1")
    return out


def tokens_css(brand: dict | None) -> str:
    tok = tokens(brand)
    font = (brand or {}).get("font") or NEUTRAL_BRAND["font"]
    if re.search(r"[;{}<>]", font):
        raise ValueError(f"font stack may not contain ; {{ }} < >: {font!r}")

    def block(t: dict[str, str]) -> str:
        return "".join(f"--{k}:{v};" for k, v in t.items())
    light, dark = block(tok["light"]), block(tok["dark"])
    return (f":root{{--font:{font};{light}color-scheme:light}}\n"
            f"@media (prefers-color-scheme: dark){{:root:not([data-theme=\"light\"]){{{dark}color-scheme:dark}}}}\n"
            f":root[data-theme=\"dark\"]{{{dark}color-scheme:dark}}\n")


def logo_uri(path: str | Path | None, base: Path | None = None) -> str | None:
    """A logo as a data URI, or None. A declared logo that cannot be used
    gives no logo, never a substitute mark, and says why on stderr."""
    if not path:
        return None
    p = Path(str(path)).expanduser()
    if base and not p.is_absolute():
        p = base / p
    media = LOGO_MEDIA.get(p.suffix.lower())
    try:
        blob = p.read_bytes() if media else b""
    except OSError as exc:
        print(f"pagekit: logo {p}: {exc.strerror or exc}; no logo", file=sys.stderr)
        return None
    if not media or not blob or len(blob) > LOGO_MAX_BYTES:
        print(f"pagekit: logo {p}: unsupported, empty or over "
              f"{LOGO_MAX_BYTES:,} bytes; no logo", file=sys.stderr)
        return None
    return f"data:{media};base64," + base64.b64encode(blob).decode("ascii")


# ── assets ───────────────────────────────────────────────────────────────────

def _read(name: str) -> str:
    return (HERE / name).read_text(encoding="utf-8")


def assets() -> tuple[str, str]:
    """The reader features' stylesheet and script, as text, without their
    comments: those are for whoever maintains the kit, and a page is for its
    reader (a comment ships to anyone who views the source)."""
    return _read("kit.css"), _strip_js_comments(_read("kit.js"))


def _strip_js_comments(js: str) -> str:
    """Block comments out. Safe for kit.js, which keeps no ``/*`` inside a
    string or a regular expression (a test holds that)."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"\n\s*\n+", "\n", js)


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


#: Runs before first paint, so a reader who chose dark never sees a light flash.
#: Storage is unavailable in sandboxed previews, hence the try.
PREPAINT_ID = "pagekit-prepaint"
PREPAINT = ('(function(){try{var t=localStorage.getItem("pagekit-theme");'
            'if(t==="dark"||t==="light")document.documentElement.setAttribute("data-theme",t)}'
            'catch(e){}})();')


# ── apply: features onto any page ───────────────────────────────────────────

def _drop(html: str, tag: str, ident: str) -> str:
    return re.sub(rf'<{tag} id="{ident}">.*?</{tag}>\n?', "", html, flags=re.S)


def _set_lang(html: str, lang: str) -> str:
    m = re.search(r"<html\b[^>]*>", html, flags=re.I)
    if not m:
        return html
    tag = m.group(0)
    new = (re.sub(r'\blang="[^"]*"', f'lang="{lang}"', tag) if re.search(r"\blang=", tag)
           else tag[:-1].rstrip() + f' lang="{lang}">')
    return html[:m.start()] + new + html[m.end():]


_ATOMIC = re.compile(r"<(script|style|template)\b.*?</\1\s*>|<!--.*?-->", re.S | re.I)
_HEADING = re.compile(r"<(h[2-4])\b([^>]*)>(.*?)</\1\s*>", re.S | re.I)
_SUMMARY = re.compile(r"<(summary)\b([^>]*)>(.*?)</\1\s*>", re.S | re.I)


def anchor_headings(html: str) -> str:
    """Give every h2 to h4, and every fold title that holds no heading, an id
    made from its words, so a link can point at any section. An id the page
    already has is kept. Made from the words, not the position, so a link
    still lands after a section is added above it; it changes only if the
    heading's own words do. Idempotent."""
    taken = set(re.findall(r'\bid="([^"]+)"', html))
    keep: list[tuple[int, int]] = []

    def inside(at: int) -> bool:
        return any(a <= at < b for a, b in keep)

    def add(m: re.Match) -> str:
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        if inside(m.start()) or re.search(r"\bid=", attrs) or (
                tag.lower() == "summary" and re.search(r"<h[1-6]\b", inner, re.I)):
            return m.group(0)
        words = _html.unescape(re.sub(r"<[^>]+>", " ", inner))
        base = slug(" ".join(words.split()))
        if base == "part" and not words.strip():
            return m.group(0)
        ident, n = base, 2
        while ident in taken:
            ident, n = f"{base}-{n}", n + 1
        taken.add(ident)
        return f'<{tag}{attrs} id="{ident}">{inner}</{tag}>'

    for pattern in (_HEADING, _SUMMARY):
        keep = [(m.start(), m.end()) for m in _ATOMIC.finditer(html)]
        html = pattern.sub(add, html)
    return html


_SECTION = re.compile(r"<section\b[^>]*>", re.I)


def mark_parts(html: str, cls: str) -> str:
    """Make every ``<section>`` carrying the class ``cls`` a part, so the page
    shows one at a time, chosen in the panel, with the rest a click away (and
    still reached by links, search, find-in-page and print). Each part's title
    is its first heading's words, leaving out a number the page shows beside
    it. Idempotent; a page with fewer than two such sections is left alone."""
    def classes(tag: str) -> list[str]:
        m = re.search(r'\bclass="([^"]*)"', tag)
        return m.group(1).split() if m else []

    found = [m for m in _SECTION.finditer(html) if cls in classes(m.group(0))]
    if len(found) < 2:
        return html
    out, at = [], 0
    for m in found:
        tag = m.group(0)
        names = re.search(r'\bclass="([^"]*)"', tag)
        assert names
        if "pk-part" not in names.group(1).split():
            tag = tag.replace(names.group(0), f'class="{names.group(1)} pk-part"', 1)
        if "data-pk-title" not in tag:
            h = re.search(r"<h2\b[^>]*>(.*?)</h2\s*>", html[m.end():], re.S | re.I)
            if h:
                words = re.sub(r'<span class="(?:num|pk-pn)">[^<]*</span>', " ", h.group(1))
                words = " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", words)).split())
                tag = tag[:-1] + f' data-pk-title="{esc(words)}">'
        out.append(html[at:m.start()] + tag)
        at = m.end()
        # Its heading is the part's title: the panel lists the part by it and
        # focuses it when the part is chosen, so it is not listed again inside.
        h2 = re.match(r"\s*(?:<!--.*?-->\s*)*<h2\b([^>]*)>", html[at:], re.S | re.I)
        if h2 and "pk-part-title" not in h2.group(1):
            c = re.search(r'\bclass="([^"]*)"', h2.group(1))
            attrs = (h2.group(1).replace(c.group(0), f'class="{c.group(1)} pk-part-title"', 1) if c
                     else h2.group(1) + ' class="pk-part-title"')
            out.append(html[at:at + h2.start(1)] + attrs + ">")
            at += h2.end()
    return "".join(out) + html[at:]


def apply(html: str, lang: str | None = None) -> str:
    """``html`` with the reader features inlined: their CSS last in the head
    (so it builds on the page's own tokens) and their script last in the
    body. Idempotent. ``lang`` sets the page's language when given."""
    css, js = assets()
    html = nfc(html)
    html = _drop(_drop(_drop(html, "style", CSS_ID), "script", JS_ID), "script", PREPAINT_ID)
    if lang:
        html = _set_lang(html, lang)
    html = anchor_headings(html)
    # A reader's light or dark choice is put back before first paint, so a
    # page never flashes the other scheme. It goes straight after the
    # character set, which must stay within the first 1,024 bytes.
    pre = f'<script id="{PREPAINT_ID}">{PREPAINT}</script>\n'
    cs = re.search(r"<meta\s+charset=[^>]*>\n?", html, flags=re.I)
    hd = re.search(r"<head\b[^>]*>\n?", html, flags=re.I)
    if cs:
        html = html[:cs.end()] + pre + html[cs.end():]
    elif hd:
        html = html[:hd.end()] + pre + html[hd.end():]
    style = f'<style id="{CSS_ID}">\n{_strip_comments(css)}</style>\n'
    script = f'<script id="{JS_ID}">\n{js}</script>\n'
    # The styles go at the end of the head. A page may leave </head> out (HTML
    # allows it), so failing that they go just before <body>, then just after
    # <head> or <html>; never above <!doctype>, which would put the page into
    # the browser's old "quirks" layout.
    at = (re.search(r"</head\s*>", html, flags=re.I) or re.search(r"<body\b", html, flags=re.I))
    if at:
        html = html[:at.start()] + style + html[at.start():]
    else:
        after = re.search(r"<head\b[^>]*>|<html\b[^>]*>|<!doctype[^>]*>", html, flags=re.I)
        html = (html[:after.end()] + "\n" + style + html[after.end():]) if after else style + html
    ends = list(re.finditer(r"</body\s*>", html, flags=re.I))
    body = ends[-1] if ends else None
    html = (html[:body.start()] + script + html[body.start():]) if body else html + script
    return html


_SKIP = re.compile(r'<meta name="pk-skip" content="[^"]*">\n?')


def set_skip(html: str, selectors: str | None = None) -> str:
    """``html`` telling the kit which tables to leave alone, beyond those
    opted out with ``data-pk="off"`` and those inside a figure: ``selectors``
    is a CSS selector list (``table.layout, #summary``), written as
    ``<meta name="pk-skip">``. Meant for pages made another way, whose own
    markup cannot carry the opt-out. Idempotent; ``None`` or empty removes it."""
    want = (selectors or "").strip()
    tag = f'<meta name="pk-skip" content="{esc(want)}">\n' if want else ""
    # A tag already there is replaced where it stands, so this and `set_marks`
    # (which also writes just before the kit's styles) can run in any order,
    # any number of times, and leave the page as it was.
    old = _SKIP.search(html)
    if old:
        return html[:old.start()] + tag + _SKIP.sub("", html[old.end():])
    if not tag:
        return html
    # Before the kit's styles, which `apply` always puts last in the head,
    # so applying the kit again leaves the page exactly as it was.
    at = (re.search(r'<style id="pagekit-css">', html) or re.search(r"</head\s*>", html, flags=re.I)
          or re.search(r"<body\b", html, flags=re.I))
    return html[:at.start()] + tag + html[at.start():] if at else tag + html


# ── markings: a security classification and a watermark ─────────────────────

#: The New Zealand classifications, highest first, with the colour the
#: Protective Security Requirements give each marking ("How to protectively
#: mark information and equipment", protectivesecurity.govt.nz, read
#: November 2026): capitals, bold, at least body size, centred at the top and
#: bottom of every page. UNCLASSIFIED: "Marking is recommended".
CLASSIFICATIONS = (("TOP SECRET", "#ff0000"), ("SECRET", "#0000ff"), ("CONFIDENTIAL", "#00b050"),
                   ("RESTRICTED", "#000000"), ("SENSITIVE", "#000000"), ("IN-CONFIDENCE", "#000000"),
                   ("UNCLASSIFIED", "#000000"))
_MARKS = re.compile(r'<div class="pk-(?:mark|watermark)\b[^"]*" id="pk-(?:mark-top|mark-bottom|watermark)"[^>]*>[^<]*</div>\n?'
                    r'|<meta name="protective-marking" content="[^"]*">\n?'
                    r'|<style id="pk-mark-print">[^<]*</style>\n?')


#: What a protective marking is written in: capitals, digits, spaces, hyphens,
#: colons and slashes (an endorsement after ``//``).
_MARKING_CHARS = re.compile(r"[A-Z0-9][A-Z0-9 /:\-]*")


def classification_of(marking: str) -> tuple[str, str]:
    """The classification word in ``marking`` and its colour. An endorsement
    may sit before it (policy and privacy) or after it, after ``//``
    (national security); a marking with no classification word is refused,
    because the PSR say an endorsement is never used without one."""
    m = marking.upper()
    for word, colour in CLASSIFICATIONS:
        if re.search(rf"(?<![A-Z-]){re.escape(word)}(?![A-Z-])", m):
            if word == "SECRET" and "TOP SECRET" in m:
                continue
            return word, colour
    raise ValueError(f"{marking!r} names no New Zealand classification "
                     f"({', '.join(w for w, _ in CLASSIFICATIONS)})")


def set_marks(html: str, marking: str | None = None, watermark: str | None = None) -> str:
    """``html`` carrying a security classification marking and a watermark,
    each set per document and each optional. Idempotent; ``None`` or an empty
    value removes it.

    The marking is shown as the PSR set out for a document: in capitals, in
    bold, in its classification's colour, centred at the top and bottom of
    the screen and of every printed page. It is also written as
    ``<meta name="protective-marking">`` so a tool can find it. No recognised
    standard labels an HTML file the way Office and PDF files are labelled,
    so that tag is this kit's own convention. The watermark is a word (DRAFT,
    say) across the page, on screen and on paper."""
    html = _MARKS.sub("", html)
    marking = (marking or "").strip().upper()
    watermark = (watermark or "").strip()
    if marking and not _MARKING_CHARS.fullmatch(marking):
        # It is written into a stylesheet for the printed margins, where an
        # escape cannot make arbitrary text safe, so only marking characters pass.
        raise ValueError(f"a marking holds capitals, digits, spaces, hyphens, colons and slashes only: {marking!r}")
    if not marking and not watermark:
        return html
    top = bottom = tag = wm = ""
    if marking:
        _word, colour = classification_of(marking)
        top = (f'<div class="pk-mark pk-mark-top" id="pk-mark-top" data-pk-sticky role="note" '
               f'style="--pk-mark:{colour}">{esc(marking)}</div>\n')
        bottom = (f'<div class="pk-mark pk-mark-bottom" id="pk-mark-bottom" role="note" '
                  f'style="--pk-mark:{colour}">{esc(marking)}</div>\n')
        # On paper the marking goes in the page's own top and bottom margins,
        # where a browser prints running headers, so it never covers a line.
        quoted = marking.replace("\\", "\\\\").replace('"', '\\"')
        box = f'content: "{quoted}"; font: 700 12pt sans-serif; color: {colour};'
        tag = (f'<meta name="protective-marking" content="{esc(marking)}">\n'
               f'<style id="pk-mark-print">@media print {{ @page {{ margin: 16mm 14mm; @top-center {{ {box} }} '
               f'@bottom-center {{ {box} }} }} }}</style>\n')
    if watermark:
        wm = f'<div class="pk-watermark" id="pk-watermark" aria-hidden="true">{esc(watermark)}</div>\n'
    if tag:
        # Before the kit's styles, which `apply` always puts last in the head,
        # so applying the kit again leaves the page exactly as it was.
        at = (re.search(r'<style id="pagekit-css">', html) or re.search(r"</head\s*>", html, flags=re.I)
              or re.search(r"<body\b", html, flags=re.I))
        html = html[:at.start()] + tag + html[at.start():] if at else tag + html
    opened = re.search(r"<body\b[^>]*>\n?", html, flags=re.I)
    if opened:
        html = html[:opened.end()] + top + wm + html[opened.end():]
    else:
        html = top + wm + html
    if bottom:
        ends = [m.start() for m in (re.search(r'<script type="application/json" id="pk-refdata">', html),
                                    re.search(r'<script id="pagekit-js">', html)) if m]
        last = list(re.finditer(r"</body\s*>", html, flags=re.I))
        i = min(ends) if ends else (last[-1].start() if last else len(html))
        html = html[:i] + bottom + html[i:]
    return html


# ── the published date ───────────────────────────────────────────────────────

_PUBLISHED = re.compile(r"<time data-pk-published(?: datetime=\"[^\"]*\")?>[^<]*</time>")


def nz_date(d: Any) -> str:
    """``2026-11-23`` → ``23 November 2026``."""
    import datetime as _dt
    if isinstance(d, str):
        d = _dt.date.fromisoformat(d)
    return f"{d.day} {d:%B %Y}"


def set_published(html: str, date: Any) -> str:
    """Fill every published-date slot (``<time data-pk-published>``)."""
    import datetime as _dt
    iso = date if isinstance(date, str) else date.isoformat()
    _dt.date.fromisoformat(iso)
    return _PUBLISHED.sub(f'<time data-pk-published datetime="{iso}">{nz_date(iso)}</time>', html)


def published_of(html: str) -> str | None:
    m = re.search(r'<time data-pk-published datetime="(\d{4}-\d\d-\d\d)"', html)
    return m.group(1) if m else None


def fingerprint(html: str) -> str:
    """A digest of the words a reader is given, blind to styling, scripts,
    controls, the page language, the masthead and the published date. Two
    versions with the same fingerprint say the same thing, so the later one
    keeps the earlier one's published date: a change of look is not a new
    edition."""
    import hashlib
    t = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    for tag in ("script", "style", "button"):
        t = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", " ", t, flags=re.S | re.I)
    t = re.sub(r'<div class="docmeta">.*?</div>', " ", t, flags=re.S)
    # A marking or a watermark says how to handle the words, not what they say.
    t = _MARKS.sub(" ", t)
    # Labels only a screen reader hears name the page's furniture, not its
    # content: renaming a control column is not a new edition.
    t = re.sub(r'<span class="(?:sr-only|pk-sr)">[^<]*</span>', " ", t)
    t = _PUBLISHED.sub(" ", t)
    # Spacing is not content, and adding a link or a span around a word must
    # not split it into a new one, so all spacing is dropped before hashing.
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\s+", "", _html.unescape(t))
    return hashlib.sha256(nfc(t).encode("utf-8")).hexdigest()


# ── reference links: identifiers that explain themselves ────────────────────

_NO_LINK = {"a", "script", "style", "title", "textarea", "code", "pre", "head", "svg", "button", "summary"}
REFDATA_ID = "pk-refdata"
_PIECES = re.compile(r"(<script\b.*?</script\s*>|<style\b.*?</style\s*>|<!--.*?-->|<[^>]+>)", re.S | re.I)
_REFDATA = re.compile(r'<script type="application/json" id="pk-refdata">.*?</script>\n?', re.S)


def _ref_href(ref: dict, e: dict, here: str) -> tuple[str, bool]:
    """Where an identifier points, and whether that is outside this set of pages.

    An entry with ``doc`` (its document's path from the pages' common root) points
    into that document, or into this page when the page is that document; an
    entry without one points at ``ref["url"] + anchor``."""
    import posixpath
    from urllib.parse import quote
    anchor = e.get("anchor", "")
    doc = e.get("doc")
    if here and here in (e.get("also") or {}):
        return "#" + e["also"][here], False
    if doc:
        if doc == here:
            return "#" + anchor, False
        rel = posixpath.relpath(doc, posixpath.dirname(here) or ".")
        return quote(rel) + ("#" + anchor if anchor else ""), False
    return ref.get("url", "") + anchor, True


def _unsafe_url(url: str) -> bool:
    """A link with a scheme other than http or https. Browsers ignore spaces
    and control characters inside a scheme, so they are dropped first."""
    m = re.match(r"([a-zA-Z][a-zA-Z0-9+.-]*):", re.sub(r"[\x00-\x20]", "", url))
    return m is not None and m.group(1).lower() not in ("http", "https")


def link_refs(html: str, refsets: Sequence[dict], here: str = "") -> str:
    """Turn every identifier a ``refset`` knows into a link that explains itself.

    A refset is ``{"name", "pattern", "url"?, "in_code"?, "entries": {id:
    entry}}``; an entry is ``{"anchor", "doc"?, "level"?, "title"?, "text"?,
    "fields"?: [[label, text], ...]}``. With ``doc`` the identifier links into
    that document (``here`` is this page's path from the same root), else to
    ``url + anchor``. Every linked identifier also carries its entry in a JSON
    block on the page, which the kit shows as a short card on hover and the
    whole entry in a side pane on click. Only identifiers in ``entries`` are
    linked, so a mistyped one stays plain text rather than linking nowhere.
    Text inside a link, a script or a heading's disclosure is left alone, and
    so is code unless the refset says ``in_code``. A refset's ``url`` must be
    relative or ``http(s)``: any other scheme (``javascript:``, ``data:``) is
    refused. Idempotent."""
    import json
    for ref in refsets:
        if _unsafe_url(str(ref.get("url") or "")):
            raise ValueError(f"refset {ref.get('name')!r}: a url must be relative or http(s), not {ref.get('url')!r}")
    sets = [(re.compile(r["pattern"]), r) for r in refsets if r.get("entries")]
    if not sets:
        return html
    used: dict[str, dict] = {}
    old = _REFDATA.search(html)
    if old:
        try:
            used.update(json.loads(old.group(0).split(">", 1)[1].rsplit("</script>", 1)[0].replace("<\\/", "</")))
        except ValueError:
            pass
        html = _REFDATA.sub("", html)
    out: list[str] = []
    skip: list[str] = []
    # A script, a style block or a comment is one piece, never parsed for
    # tags: a script that builds markup in a string would otherwise open or
    # close tags that are not there.
    for piece in _PIECES.split(html):
        if piece.startswith(("<script", "<style", "<!--")):
            out.append(piece)
            continue
        if piece.startswith("<"):
            m = re.match(r"<(/?)([a-zA-Z][\w-]*)", piece)
            if m:
                tag = m.group(2).lower()
                if tag in _NO_LINK and not piece.endswith("/>"):
                    if m.group(1):
                        if tag in skip:
                            while skip and skip.pop() != tag:
                                pass
                    else:
                        skip.append(tag)
            out.append(piece)
            continue
        if not piece.strip():
            out.append(piece)
            continue
        for rx, ref in sets:
            if set(skip) - ({"code"} if ref.get("in_code") else set()):
                continue

            def one(m: re.Match, ref: dict = ref) -> str:
                ident = m.group(0)
                e = ref["entries"].get(ident)
                if not e:
                    return ident
                href, outside = _ref_href(ref, e, here)
                tip = f'{ref["name"]} {ident}'
                if e.get("level"):
                    tip += f' ({e["level"].upper()})'
                line = e.get("title") or e.get("text") or ""
                if line:
                    tip += ": " + (line if len(line) <= 280 else line[:277].rsplit(" ", 1)[0] + "…")
                used[ident] = {k: v for k, v in (("n", ref["name"]), ("l", e.get("level", "")),
                                                  ("t", e.get("title", "")), ("s", e.get("text", "")),
                                                  ("f", e.get("fields") or []), ("u", href), ("x", outside)) if v}
                extra = ' target="_blank" rel="noopener"' if outside else ""
                return (f'<a class="pk-ref" href="{esc(href)}" data-pk-ref="{esc(ident)}" '
                        f'title="{esc(tip)}"{extra}>{ident}</a>')
            piece = rx.sub(one, piece)
        out.append(piece)
    html = "".join(out)
    if used:
        blob = json.dumps(used, ensure_ascii=False, separators=(",", ":"), sort_keys=True).replace("</", "<\\/")
        block = f'<script type="application/json" id="{REFDATA_ID}">{blob}</script>\n'
        # Before the kit's own script, which `apply` always puts last, so
        # applying the kit again leaves the page exactly as it was.
        i = html.find('<script id="pagekit-js">')
        if i < 0:
            i = html.rfind("</body>")
        html = html[:i] + block + html[i:] if i >= 0 else html + block
    return html


# ── page: a whole document ──────────────────────────────────────────────────

def slug(text: str) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "part"


def page(title: str, *, brand: dict | None = None, parts: Sequence[dict] | None = None,
         body: str = "", eyebrow: str = "", lead: str = "", audience: str = "",
         byline: str = "", meta: Sequence[str] = (), footer: str = "",
         lang: str = "en-NZ", logo: str | None = None, description: str = "",
         head_extra: str = "", body_extra: str = "", prose: bool = True,
         published: Any = None, marking: str = "", watermark: str = "") -> str:
    """One self-contained HTML document.

    ``parts`` is a list of ``{"id", "title", "summary", "html"}``; with two or
    more, the reader picks one part at a time from the selector, and with
    scripting off every part shows in order behind a plain contents list.
    Without parts, ``body`` is the page's content. Content is HTML the caller
    has already escaped, and so are ``footer``, ``head_extra`` and
    ``body_extra``, which are written as given; every other argument is plain
    text and is escaped here. ``marking`` (a
    New Zealand classification, e.g. ``IN-CONFIDENCE``) and ``watermark``
    (e.g. ``DRAFT``) are set per document; see `set_marks`."""
    b = brand or NEUTRAL_BRAND
    logo = logo if logo is not None else logo_uri(b.get("logo"))
    name, alt = b.get("name") or "", b.get("name_alt") or b.get("name_te_reo") or ""
    alt_lang = b.get("name_alt_lang") or ("mi" if b.get("name_te_reo") else "")
    base_css = _strip_comments(_read("base.css"))
    kit_css, kit_js = assets()

    mark = ""
    if logo:
        mark = f'<img class="pk-logo" src="{esc(logo)}" alt="{esc(name or "Logo")}">'
        if logo.startswith("data:"):
            mark += "<!-- secretscan:allow: an inline logo image, not a credential -->"
    names = ""
    if (name or alt) and (not logo or b.get("names_beside_logo")):
        names = '<span class="pk-org">' + (
            f'<span class="pk-org-alt" lang="{esc(alt_lang)}">{esc(alt)}</span>' if alt else "") + (
            f'<span class="pk-org-name">{esc(name)}</span>' if name and not logo else "") + "</span>"
    metas = "".join(f"<span>{esc(m)}</span>" for m in meta if m)
    if published:
        metas = "<span>Published <time data-pk-published></time></span>" + metas
    masthead = (
        '<header class="pk-masthead" role="banner"><div class="pk-wrap pk-mast">'
        f'<div class="pk-brand">{mark}{names}</div>'
        f'<div class="pk-docmeta">{f"<span>{esc(byline)}</span>" if byline else ""}{metas}</div>'
        '<button type="button" class="pk-theme" data-pk-theme hidden>'
        '<span class="pk-theme-l">Dark</span><span class="pk-theme-d">Light</span></button>'
        '</div></header>')
    hero = ('<div class="pk-hero"><div class="pk-wrap">'
            + (f'<p class="pk-eyebrow">{esc(eyebrow)}</p>' if eyebrow else "")
            + f'<h1 id="pk-title">{esc(title)}</h1>'
            + (f'<p class="pk-lead">{esc(lead)}</p>' if lead else "")
            + (f'<p class="pk-aud"><span class="pk-chip">{esc(audience)}</span></p>' if audience else "")
            + "</div></div>")

    main_cls = "pk-main pk-prose" if prose else "pk-main"
    if parts and len(parts) >= 2:
        seen: set[str] = set()
        items, sections = [], []
        for n, p in enumerate(parts, 1):
            pid = p.get("id") or "part-" + slug(p["title"])
            while pid in seen:
                pid += "-2"
            seen.add(pid)
            summ = p.get("summary") or ""
            items.append(
                f'<li><a href="#{esc(pid)}" data-pk-part="{esc(pid)}">'
                f'<span class="pk-pn">{n}</span><span class="pk-pt">{esc(p["title"])}</span>'
                + (f'<span class="pk-ps">{esc(summ)}</span>' if summ else "") + "</a></li>")
            show_summary = p.get("show_summary", True)
            sections.append(
                f'<section class="pk-part" id="{esc(pid)}" aria-labelledby="{esc(pid)}-h" '
                f'data-pk-title="{esc(p["title"])}">'
                f'<h2 class="pk-part-title" id="{esc(pid)}-h"><span class="pk-pn">{n}</span> '
                f'{esc(p["title"])}</h2>'
                + (f'<p class="pk-part-summary">{esc(summ)}</p>' if summ and show_summary else "")
                + f'{p["html"]}</section>')
        selector = ('<nav class="pk-parts" aria-label="Parts of this document" data-pk-sticky>'
                    '<p class="pk-parts-label">In this document</p>'
                    f'<ol>{"".join(items)}</ol></nav>')
        content = ('<div class="pk-wrap pk-layout pk-has-parts">'
                   f'<aside class="pk-rail">{selector}</aside>'
                   f'<main id="pk-main" class="{main_cls}" tabindex="-1">{"".join(sections)}</main></div>')
    else:
        inner = body if not parts else parts[0]["html"]
        content = (f'<div class="pk-wrap pk-layout"><main id="pk-main" class="{main_cls}" '
                   f'tabindex="-1">{inner}</main></div>')

    foot = ('<footer class="pk-footer" role="contentinfo"><div class="pk-wrap">'
            + (footer or (esc(name) if name else "")) + "</div></footer>")
    desc = f'<meta name="description" content="{esc(description)}">' if description else ""
    doc = (
        "<!DOCTYPE html>\n"
        f'<html lang="{esc(lang)}">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n{desc}"
        f'<meta name="generator" content="pagekit {VERSION}">\n'
        f'<script id="{PREPAINT_ID}">{PREPAINT}</script>\n'
        f'<style id="{TOKENS_ID}">\n{tokens_css(b)}</style>\n'
        f'<style id="{BASE_ID}">\n{base_css}</style>\n'
        f'<style id="{CSS_ID}">\n{_strip_comments(kit_css)}</style>\n'
        f"{head_extra}</head>\n<body>\n"
        '<a class="pk-skip" href="#pk-main">Skip to the content</a>\n'
        f"{masthead}\n{hero}\n{content}\n{foot}\n{body_extra}"
        f'<script id="{JS_ID}">\n{kit_js}</script>\n</body>\n</html>\n')
    doc = nfc(doc)
    doc = set_marks(doc, marking, watermark)
    return set_published(doc, published) if published else doc


# ── compose: existing pages as the parts of one file ────────────────────────

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
         "source", "track", "wbr"}


def _remove(html: str, spec: str) -> str:
    """Remove every element matching ``spec`` (``tag``, ``tag.class`` or
    ``tag[attr=value]``), nesting respected. Meant for generated, well-formed
    markup, not arbitrary HTML."""
    m0 = re.match(r"^([a-z0-9]+)(?:\.([\w-]+))?(?:\[([\w-]+)=\"?([^\]\"]*)\"?\])?$", spec, re.I)
    if not m0:
        raise ValueError(f"cannot read the element to drop: {spec!r}")
    tag, cls, attr, val = m0.groups()
    opener = re.compile(rf"<{tag}\b[^>]*>", re.I)
    pos = 0
    while True:
        m = opener.search(html, pos)
        if not m:
            return html
        if (cls and not re.search(rf'\bclass="[^"]*\b{re.escape(cls)}\b[^"]*"', m.group(0))) or \
                (attr and not re.search(rf'\b{re.escape(attr)}="{re.escape(val)}"', m.group(0))):
            pos = m.end()
            continue
        if tag.lower() in _VOID:
            html = html[:m.start()] + html[m.end():]
            pos = m.start()
            continue
        depth, i = 1, m.end()
        tok = re.compile(rf"<(/?){tag}\b[^>]*>", re.I)
        while depth:
            t = tok.search(html, i)
            if not t:
                return html
            depth += -1 if t.group(1) else 1
            i = t.end()
        html = html[:m.start()] + html[i:]
        pos = m.start()


def _scope_css(css: str, scope: str) -> str:
    """``css`` made to apply inside ``scope`` only, with CSS @scope. The page
    level (``:root``, ``html``, ``body``) becomes the scope's own root, and
    rules that only work at page level (``@page``, ``@import``) are dropped."""
    css = _strip_comments(css)
    css = re.sub(r"@import[^;]*;", "", css)
    # Keyframes and font faces are page-level definitions: lift them out.
    lifted = []

    def lift(m: re.Match) -> str:
        lifted.append(m.group(0))
        return ""
    css = re.sub(r"@(?:-webkit-)?(?:keyframes|font-face)\b[^{]*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", lift, css)
    css = re.sub(r"@page\b[^{]*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", "", css)
    out, pos = [], 0
    for m in re.finditer(r"([^{};]+)\{", css):
        pre = m.group(1)
        if pre.strip().startswith("@") or re.match(r"\s*(from|to|\d+%)\s*$", pre):
            continue
        sels = re.sub(r"(^|[\s,>+~(])(?::root|html|body)(?=[\s,.:\[>+~)]|$)", r"\1:scope", pre)
        out.append(css[pos:m.start()] + sels + "{")
        pos = m.end()
    out.append(css[pos:])
    return "".join(lifted) + f"\n@scope ({scope}) {{\n{''.join(out)}\n}}\n"


def _prefix_ids(html: str, prefix: str) -> str:
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    if not ids:
        return html

    def ref(m: re.Match) -> str:
        v = m.group(2)
        return m.group(1) + (prefix + v if v in ids else v) + '"'
    html = re.sub(r'(\bid=")([^"]+)"', ref, html)
    html = re.sub(r'(\bhref="#)([^"]+)"', ref, html)
    html = re.sub(r'(\b(?:for|aria-controls|aria-labelledby|aria-describedby|headers)=")([^"]+)"',
                  lambda m: m.group(1) + " ".join(prefix + v if v in ids else v
                                                  for v in m.group(2).split()) + '"', html)
    return html


def compose(title: str, pages: Sequence[dict], *, drop: Sequence[str] = ("a.skip", "header", "h1"),
            **kw: Any) -> str:
    """One pagekit page whose parts are existing, whole HTML pages.

    ``pages`` is a list of ``{"html", "title", "summary"?, "id"?, "drop"?}``. Each
    page keeps its own stylesheet, scoped to its part with CSS ``@scope`` so
    the pages cannot restyle one another, and its own scripts. Its masthead,
    skip link and title are dropped (``drop``: ``tag``, ``tag.class`` or
    ``tag[attr=value]``; a page's own ``drop`` replaces the default), because
    the composed page has one of each. A page with no script has its
    ids prefixed so two pages cannot collide; a page with a script keeps its
    ids, because its script may look them up. It is a bridge: pages composed
    this way read as they did, and move onto the one stylesheet later."""
    parts, scripts, styles = [], [], []
    for n, pg in enumerate(pages, 1):
        h = nfc(pg["html"])
        h = _drop(_drop(h, "style", CSS_ID), "script", JS_ID)
        sheet = "".join(re.findall(r"<style\b[^>]*>(.*?)</style>", h, flags=re.S | re.I))
        own = [m for m in re.findall(r"<script\b[^>]*>(.*?)</script>", h, flags=re.S | re.I) if m.strip()]
        body = re.search(r"<body\b[^>]*>(.*)</body>", h, flags=re.S | re.I)
        inner = body.group(1) if body else h
        inner = re.sub(r"<script\b[^>]*>.*?</script>", "", inner, flags=re.S | re.I)
        for d in pg.get("drop", drop):
            inner = _remove(inner, d)
        sid = f"pkc-{n}"
        if not own:
            inner = _prefix_ids(inner, f"p{n}-")
        styles.append(_scope_css(sheet, f"#{sid}"))
        scripts.extend(own)
        parts.append({"id": pg.get("id"), "title": pg["title"], "summary": pg.get("summary", ""),
                      "show_summary": False,
                      "html": f'<div class="pk-scoped" id="{sid}" data-pk-scoped>{inner}</div>'})
    head = f'<style id="pagekit-composed">\n{"".join(styles)}</style>\n'
    tail = "".join(f"<script>\n{s}\n</script>\n" for s in scripts)
    return page(title, parts=parts, prose=False, head_extra=head, body_extra=tail, **kw)


# ── check: will this page travel as one file? ───────────────────────────────

_EXTERNAL = [
    (re.compile(r"<script\b[^>]*\bsrc\s*=", re.I), "an external script"),
    (re.compile(r"<link\b[^>]*rel=[\"']?(?:stylesheet|preload|icon|modulepreload)[^>]*href=[\"']?(?!data:)", re.I),
     "a linked stylesheet, font or icon"),
    (re.compile(r"<(?:img|source|video|audio|iframe|embed|object)\b[^>]*\b(?:src|srcset|data)\s*=\s*[\"']?(?!data:|#|blob:)[^\s\"'>]", re.I),
     "an external picture or embedded object"),
    (re.compile(r"@import\b", re.I), "a stylesheet @import"),
    (re.compile(r"(?<![\w.$])url\(\s*[\"']?(?!data:|#|[\"']?\))"), "a CSS url() that is not inline"),
    (re.compile(r"<base\b[^>]*\bhref\s*=", re.I), "a base address"),
    (re.compile(r"<meta\b[^>]*http-equiv=[\"']?refresh[^>]*url\s*=", re.I), "a meta refresh to another address"),
    (re.compile(r"<link\b[^>]*rel=[\"']?(?:manifest|prefetch|dns-prefetch|preconnect|prerender)\b", re.I),
     "a link that reaches the network ahead of the reader"),
    (re.compile(r"<video\b[^>]*\bposter\s*=\s*[\"']?(?!data:)[^\s\"'>]", re.I), "an external video poster"),
    (re.compile(r"<image\b[^>]*\b(?:xlink:)?href\s*=\s*[\"']?(?!data:|#)[^\s\"'>]", re.I), "an SVG image from outside the file"),
    (re.compile(r"<form\b[^>]*\baction\s*=\s*[\"']?(?!#|[\"'\s>])", re.I), "a form that sends somewhere"),
    (re.compile(r"<a\b[^>]*\bping\s*=", re.I), "a link that pings an address"),
]


def check(html: str, *, limit: int = SIZE_LIMIT) -> list[str]:
    """Problems that would stop ``html`` travelling as one readable file."""
    out: list[str] = []
    head = html[:1024]
    if not re.search(r"<meta\s+charset=[\"']?utf-8", head, re.I):
        out.append("no <meta charset=\"utf-8\"> in the first 1,024 bytes "
                   "(macrons may show garbled when the file is opened from disk or mail)")
    if not re.search(r"<html\b[^>]*\blang=\"[a-z]{2,3}(-[A-Za-z]{2})?\"", html):
        out.append("the <html> element has no lang attribute")
    if unicodedata.normalize("NFC", html) != html:
        out.append("text is not in composed Unicode (NFC); a macron may be stored "
                   "as a letter plus a combining mark")
    body = re.sub(r"data:[^\"')\s]+", "data:", html)
    for rx, what in _EXTERNAL:
        m = rx.search(body)
        if m:
            out.append(f"{what}: {body[m.start():m.start() + 90]!r}")
    size = len(html.encode("utf-8"))
    if size > limit:
        out.append(f"{size:,} bytes is over the {limit:,}-byte limit")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pagekit", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply", help="inline the reader features into a page")
    a.add_argument("page", type=Path)
    a.add_argument("-o", "--out", type=Path, help="write here (default: in place)")
    a.add_argument("--lang", help="set the page language, e.g. en-NZ")
    c = sub.add_parser("check", help="report what stops a page travelling as one file")
    c.add_argument("pages", type=Path, nargs="+")
    args = ap.parse_args(argv)
    if args.cmd == "apply":
        text = args.page.read_text(encoding="utf-8")
        (args.out or args.page).write_text(apply(text, args.lang), encoding="utf-8")
        print(f"pagekit: applied to {args.out or args.page}")
        return 0
    bad = 0
    for p in args.pages:
        probs = check(p.read_text(encoding="utf-8"))
        bad += bool(probs)
        for msg in probs:
            print(f"{p}: {msg}")
    print(f"pagekit: {len(args.pages) - bad} of {len(args.pages)} page(s) travel as one file")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

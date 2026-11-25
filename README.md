# PageKit

One self-contained HTML file per document, for any organisation: the same
reader features everywhere, and the brand swapped by data, not by editing
styles. Standard-library Python; the page carries its own stylesheet and
script, so it works opened from disk, from a mail attachment, or inside the
locked-down frames that SharePoint, OneDrive and Teams preview a file in.

Licensed under the Apache License 2.0.

```bash
pip install "pagekit @ git+https://github.com/mike548141/pagekit"
python3 -m pagekit check PAGE.html
python3 -m pagekit apply PAGE.html -o OUT.html --lang en-NZ
```

## Ways in

| You have | Use | You get |
|---|---|---|
| New content | `pagekit.page(title, brand=…, parts=[…] or body=…)` | A whole page: masthead, title, parts, the one stylesheet, the features |
| A page made another way | `pagekit.apply(html, "en-NZ")` | That page plus the features |
| Several existing pages to join | `pagekit.compose(title, [{"html", "title"}, …], brand=…)` | One page, one part per page; each keeps its own styles, scoped to its part with CSS `@scope` |
| Any page | `pagekit.check(html)` / `python3 -m pagekit check PAGE…` | What would stop it travelling as one file: anything it loads or sends from outside itself in its markup (scripts, styles, fonts, pictures, embedded objects, a base address, a meta refresh, network hints, form actions, link pings). It does not read what a page's own script fetches |
| Any page | `python3 tools/probe.py PAGE… [--shots DIR]` (needs Playwright) | Every feature exercised in Chromium and WebKit, four ways each (below), and a check that the page carries every feature it uses |
| A page changed after it was built | `pagekit.refit(html)` | Its kit brought up to date with what the page now uses |

`examples/sample.py` builds `examples/sample.html`: every feature on invented
content (a community garden's season report). Open it to see the kit, or use it to test a
hosting route. `examples/small.py` builds `examples/small.html` on demand, a
short page that uses only some features, and `examples/table_term.py` builds
`examples/table_term.html`, a page whose first table holds a defined term.

## The brand

```python
{"name": "Example Trust", "name_te_reo": "Te Rōpū Tauira",   # or name_alt + name_alt_lang
 "logo": "path/to/logo.png",                                  # inlined; none if unusable
 "names_beside_logo": False,                                  # show names when a logo is set
 "font": '"Segoe UI", Aptos, sans-serif',
 "palette": {"primary": "#…", "primary_text": "#…", "secondary": "#…",
             "accent": "#…", "attention": "#…", "neutral": "#…", "divider": "#…"}}
```

Light and dark colours are both derived from the palette. Each brand colour
is kept as given where it meets the contrast it is used at, and moved just far
enough where it does not. `contrast_failures(tokens(brand))` must be empty.

## Features

Written for a laptop or desktop screen of 13" or more; a phone or tablet
gets a working fallback. Every feature is an enhancement: with scripting off,
or on paper, the page shows everything.

**A page carries only the features it uses.** Every page carries the core:
the panel with its search and contents, parts, links that land, light and
dark, markings and watermarks, print. The other features (`pagekit.FEATURES`:
tabs, long tables, pinned headings, charts, cards for identifiers and terms,
copying a table or diagram, copying a block, a link to any section) go into a
page only when its markup uses them, found while the page is built
(`features_needed(html)`); nobody keeps a list. A page names any its markup
does not show (content its own script adds later) with `page(features=…)` or
`apply(html, features=…)`, or `"all"`; the names are kept in the page as
`<meta name="pk-features">`. A page that runs a script of its own and names
none carries every feature. `link_refs`, `link_sources` and `link_terms` bring
the cards with them; after any other change, `refit(html)`. The design, and how
to add a feature, are in `docs/optional-features.md`.

- **The panel**, down the left of every page with sections: a search over the
  whole document (hidden parts, collapsed rows and closed sections included),
  one Expand all / Collapse all control that names what it will do next, the
  light/dark switch as a sun and moon icon, and the contents. Only the current
  section lists its sub-sections. It is read from the page itself: its parts,
  else its own contents bar (`nav.toc`), else its h2 headings. On a smaller
  screen it opens from a Contents button. On a laptop or desktop its « button
  folds it away to a narrow bar of icons, remembered where the browser allows.
  A page opts out with `<html data-pk-panel="off">`. Keep a region out of the
  contents with `data-pk-nav="off"` (a tree of folds is not a list of
  sub-sections), and out of the search with `data-pk-find="off"` (text a page
  holds hidden for its own script).
- **Parts.** Two or more `<section class="pk-part">` (or `parts=` in `page`)
  show one at a time, chosen in the panel. The rest of the file stays
  reachable through links, search, find-in-page and print, and "Show all parts
  on one page" shows everything. With scripting off, every part shows. Parts
  are numbered in order, except that a part titled "Part 2 · Costs" keeps its
  own number, and beside such parts one without a number goes unnumbered. A page
  made another way becomes parts with `mark_parts(html, cls)`: every
  `<section>` carrying the class `cls` turns into a part, titled by its first
  h2 (without a number shown beside it), and its in-page links are then
  followed by the kit, so a link shows the part it points into.
- **Tabs within a section.** A `<div class="pk-tabs">` holding two or more
  `<section class="pk-tab">` shows one pane at a time under a row of tabs:
  options side by side in a decision paper, say. Each tab is named by its
  pane's `data-pk-title`, else by the pane's first heading, which the tab then
  stands in for on screen (screen readers, print and the no-script page still
  have it). Name the group for screen readers with `aria-label` on the
  `div`. Click a tab, or use Left, Right, Home and End once one has focus. A
  link, a search result or find-in-page reaching a pane not shown opens its
  tab (in Safari the find shortcut shows every pane, as it shows every part).
  With scripting off, or on paper, every pane shows under its heading.
- **Published date.** `<time data-pk-published>` in a masthead is filled by
  `set_published(html, date)`. `fingerprint(html)` digests only the words a
  reader reads (not styling, scripts, controls, spacing, or the masthead,
  parts panel and part numbers `page()` writes), so a caller can keep the
  earlier date when only the look changed. `fingerprint(html, furniture)`
  also leaves out elements named `tag.class`, so a page moved onto `page()`
  from pages made another way keeps its date.
- **Identifiers that explain themselves.** `link_refs(html, refsets, here)`
  turns every identifier a refset knows (a requirement number, a control
  number) into a link with a card: resting the pointer on it, or tabbing to
  it, shows what it is, its level and its name; a click opens the whole entry
  in a pane down the right, with a link to its source. An identifier whose
  entry is on this page links there instead. The entries travel in a JSON
  block on the page (only the ones the page cites), so it still works as one
  file. A refset's `url` must be relative or `http(s)`; any other scheme is
  refused. Inside a SharePoint, OneDrive or Teams viewer the pane works, but its
  link to another file or outside site may not (the viewer blocks both).
- **Sources that explain themselves.** `link_sources(html, here)` reads the
  page's own list of sources: what follows an h2 or h3 titled Sources,
  References, Bibliography or Works cited, or any element marked
  `data-pk-sources`. Each table row or list item with an `id` whose first cell
  is a marker (one token, such as `REF-12` or `[r-wind]`) is a source:
  its next cell the title, the rest its details. Every mention of a marker
  elsewhere on the page then links to the source's row and, when the pointer
  rests on it or it takes keyboard focus, shows a card naming the source and
  its details (who, and when it was read). The list's own rows are left
  unlinked (`data-pk-ref="off"`, which keeps any region out of `link_refs`).
- **Defined terms.** `link_terms(html, glossary, here)` links the first
  mention of each defined term in every section (from one h2, or one part, to
  the next) to a card holding what it means. A glossary is `{"name", "url"?,
  "entries": {term: {"text", "doc"?, "anchor"?, "also"?: [other spellings],
  "source"?, "source_url"?}}}`: with `doc` and `anchor` a click goes to where
  the term is defined (on this page, or another page from the same root,
  as identifiers do); with `source_url` (relative or http(s)) it opens the
  meaning in the pane, with a link to its source. A term written in capitals
  after its first letter (an acronym, a product name) matches only as written;
  any other matches in any case, singular or plural. Headings, table headings,
  captions, links, code, a `pk-message` block and any region marked
  `data-pk-ref="off"` (the glossary's own list) are left alone. Linking a term
  changes no word, so it does not move the published date.
- **Long tables** taller than the screen open at three rows, with "Show all N
  rows". Find, print and links into a hidden row open the table. Set a
  table's preview with `data-pk-preview="5"` or `"all"`; leave a table alone
  with `data-pk="off"`. A page made another way can name tables to leave alone
  with `set_skip(html, "table.layout, #summary")`.
- **Filter and sort a long table.** A table long enough to open at its first
  rows also gets a filter box above it and sortable column headings. The
  filter ignores case and macrons, shows every matching row and says how many
  match; clearing it puts the table back as it was. A heading sorts
  ascending, then descending, then back to the table's own order, announced
  through `aria-sort`; numbers sort as numbers, words in New Zealand English
  order, empty cells last. A filtered table copies only the rows shown. Not on
  a table whose cells span rows or whose headings span columns; off with
  `data-pk-tools="off"`. On paper every row prints.
- **Pinned headings.** A table's heading row stays in view while you scroll
  it, including sideways.
- **Charts draw when seen.** When a chart scrolls into view (or the part or
  fold holding it opens), its bars rise from the baseline, a timeline's bars
  grow left to right in date order, and bars in table cells fill; values,
  whiskers and links between bars follow. Once per page view. Nothing to mark
  up: a bar chart is rects standing on a long horizontal line, a timeline is
  rects over a grid of long vertical lines. Off with `data-pk-motion="off"` on
  the figure or `<html>`; never with reduced motion asked for, or on paper.
- **A security marking and a watermark, set per document.**
  `set_marks(html, marking, watermark)`, or `page(marking=, watermark=)`.
  The marking is a New Zealand classification (`IN-CONFIDENCE`, `SENSITIVE`,
  `RESTRICTED`, …, with any endorsement), shown as the Protective Security
  Requirements set out for a document: capitals, bold, its classification's
  colour, centred at the top and bottom of the screen and of every printed page
  (on paper, in the page's own margins). It is also written as
  `<meta name="protective-marking">`; no recognised standard labels an HTML
  file the way Office files and PDFs are labelled, so that tag is this kit's
  own convention. A marking without a classification word is refused, and so
  is one holding anything but capitals, digits, spaces, hyphens, colons and
  slashes (it is written into the page's print stylesheet). The
  watermark is any word (DRAFT, say) across every page. Neither changes the
  published date. Printing the marking in the margins needs CSS page margin
  boxes: measured in Chromium (Chrome, Edge); not verified in Safari.
- **Links that land**: into a closed fold, a collapsed table or another part.
- **A link to any section.** `apply()` gives every h2 to h4, and every fold
  title that holds no heading, an id made from its words (an id the page
  already has is kept), so a link still lands after a section is added above
  it. A link icon beside each one, shown when the pointer is on the heading,
  copies a link to that section: a titled link for a document or an email, and
  the address for anywhere else. A link that arrives opens the fold, table or
  part holding the section. Inside a SharePoint, OneDrive or Teams viewer the
  page cannot see its own address (measured below), so it copies the section's
  tag (`#…`) and says to add it to the file's own link, unless the page
  carries its published address in `<meta name="pk-home"
  content="https://…">`. Off with `data-pk-link="off"`.
- **Take a copy of a table or a diagram.** A copy button shows at the top
  right of a table or diagram when the pointer is over it (or it has keyboard
  focus), one at a time: the innermost item under the pointer. A table copies
  as a table for Word or an email and as cells for Excel, or saves as CSV. A
  diagram copies as a picture (PNG) or as SVG for a drawing tool, or saves as
  either. Pictures are taken in the light scheme at twice screen size, with
  every shape's styles written in. Inside a SharePoint, OneDrive or Teams
  viewer a page may not put a picture on the clipboard or save a file
  (measured below), so there the picture opens in the pane for the browser's
  own *Copy image* or *Save image as*, and the Save items are not offered;
  copying a table or SVG works there. Off for one table or figure with
  `data-pk-copy="off"`.
- **Copy a code or message block.** Every `<pre>` box carries a labelled
  *Copy code* button above its top right corner, always visible; a
  `<div class="pk-message">` (a draft email, a notice, anything a reader will
  send on) carries *Copy message*; any element can name its own label with
  `data-pk-copy-label="Copy command"`. Code copies as plain text; a message
  copies as plain text and as formatted HTML, so it pastes into an email with
  its paragraphs. It uses the copy command, which works inside SharePoint,
  OneDrive and Teams viewers; where even that is refused, the block's text is
  selected for the reader's own Ctrl+C. Off with `data-pk-copy="off"`.
- **Macrons**: UTF-8 declared first, text stored composed (NFC), `lang`
  attributes on the page and on the te reo name.
- **Print**: everything open, every part, black on white, link addresses shown.

## Where it has to work (measured November 2026)

| Route | What happens | Covered by |
|---|---|---|
| Opened from disk, or downloaded from a webmail attachment | Opens in the browser as a plain file | probe `direct` |
| SharePoint and OneDrive file viewer | Runs the page in a frame with `sandbox="allow-scripts allow-forms"`: no storage, pop-ups, downloads or print dialog. The viewer also takes over plain `#` links | probe `sandboxed` and `viewer`, and checked by hand in a SharePoint library |
| SharePoint viewer, copying (Chrome 158) | No `allow=` on the frame, so the browser's clipboard API is refused by policy; pop-ups and downloads blocked; the older copy command works (a table pasted as HTML and as tab-separated text, macrons intact); a diagram can still be drawn as a PNG | probe copy checks in `sandboxed`, `viewer` and `srcdoc` |
| SharePoint viewer, its own address | The page runs as `about:srcdoc` inside a `blob:` frame, with no referrer, so it cannot learn the file's web address. A `#tag` on SharePoint's own address reaches the page (the frame becomes `about:srcdoc#tag`) | probe `srcdoc`: a tag arriving opens and lands |
| Teams file viewer | Loads the page as `about:srcdoc` in a frame. A browser extension cannot see inside it, so Teams itself is not machine-verified | probe `srcdoc` (runs; does not reproduce Teams' link handling) |
| Mail | A mail service may scan an `.html` attachment before delivery; in the case measured the file arrived byte-identical after the scan | — |

Engines: Chromium is what Chrome and Edge run; WebKit is what Safari runs.
The probe uses Playwright's builds of both, not the installed browsers.

## Changing the kit: traps already paid for

- `kit.js` is one scope: check a new function's name is not already taken
  (`grep -n "function name(" src/pagekit/kit.js`). A second `say()` once
  silently replaced one feature's screen-reader announcement with another's
  on-screen notice.
- An optional feature lives between `pk:feature NAME` and `pk:end NAME` lines
  in `kit.js` and `kit.css`, and is named in `FEATURES` with a detector in
  `_Uses`. Nothing outside it may call its functions, because on a page that
  does not use it they do not exist: it lends its behaviour with `on(moment,
  fn)` and the core asks with `fire(moment)`. A test fails on any name used
  across that line.
- Never write a link as text inside the script (`'<a href="' + …`): a link
  checker reading a page may take any `href="` in it as one of the page's own.
  Build it through the DOM (`el("a")`, `setAttribute("href", …)`, `outerHTML`).
- Keep `/*` out of strings and regular expressions in `kit.js`: comments are
  stripped before a page ships, and a test holds that.
- A page's own furniture (its side pane `.pane`, toolbars, headings inside a
  `figure`) gets no kit controls; search leaves the same things out.
- A check that copies must use real mouse clicks (a browser only copies in
  answer to one); a check must wait for the page to act, not for something
  that was already on screen; prove each new check by breaking the feature.
- A closed section's contents still have a box in both engines, laid out
  over what follows the section: `getClientRects()` does not say a thing is on
  screen. Test `details:not([open])` as well.
- A probe check that reads whether something shows only when pointed at must
  move the mouse off the page first: an earlier check may have left it there.
- A caller that stamps a published date should compare `fingerprint()` before
  and after a kit change, so a change of look never moves a date.

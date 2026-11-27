# Changelog

## 0.1.0 (unreleased)

- PageKit now lives in `pagekit/` of the goodcopy repository, still its own
  package: install it with
  `pip install "pagekit @ git+https://github.com/mike548141/goodcopy#subdirectory=pagekit"`.
  The package itself is unchanged by the move.
- First public version: `page`, `apply`, `compose`, `check`, `mark_parts`,
  `link_refs`, `set_marks`, `set_published`, `fingerprint`, `set_skip`; the
  panel, parts, long tables, pinned headings, links that land, a link to any
  section, copying a table or a diagram, charts that draw when seen, markings
  and watermarks; `tools/probe.py` for real-engine checks.
- A marking may hold only capitals, digits, spaces, hyphens, colons and
  slashes; anything else is refused, because it is written into the print
  stylesheet.
- The logo address is escaped; the docstring of `page()` names the three
  arguments written as given (`footer`, `head_extra`, `body_extra`).
- A refset's `url` must be relative or http(s); the page holds to the same.
- `check()` also finds a base address, a meta refresh, network hints, an
  external video poster or SVG image, form actions and link pings.
- The generator version is the package version.
- Filter and sort a long table: a filter box above it and sortable column
  headings, macron- and case-insensitive, announced to screen readers.
- Copy a code or message block: a labelled, always-visible button on every
  `<pre>`, every `.pk-message` and any element with `data-pk-copy-label`.
- `set_skip` replaces its tag where it stands, so it and `set_marks` can be
  re-applied in either order without moving anything.
- A table's filter matches the words in its cells, never the end of one cell
  run into the start of the next.
- Sources that explain themselves: `link_sources` turns every citation of a
  listed source into a link to it with a card naming the source, who wrote
  it and when it was read; `data-pk-ref="off"` keeps a region out of
  `link_refs`.
- A link a page already makes to one of its listed sources gets the source's
  card too.
- Inside a document viewer's frame the kit follows every page's in-page
  links itself, so a link into a closed section opens it there as well.
- Tabs within a section: `<div class="pk-tabs">` with `<section class="pk-tab">`
  panes shows one at a time under a row of tabs, by mouse or keyboard; links,
  search, find-in-page and print reach every pane.
- Defined terms: `link_terms` links the first mention of each glossary term in
  every section to a card with its meaning, and a click goes to where it is
  defined or opens it in the pane with its source.
- One part at a time, the parts not shown no longer leave a gap above the part
  shown: the rule meant to remove their margin never matched, so each hidden
  part above it added 3rem of blank space.
- Part groups: `"group"` on a part in `page(parts=…)`, or `data-pk-group` on a
  part's section, labels a group of parts in the panel and the no-script
  contents; numbering runs on across groups.
- One part at a time, the title block shows whole only with the first part;
  past it the page keeps its h1 on one line, and search and find-in-page still
  reach the rest.
- Show items by level: `data-pk-filter` on a container and `data-pk-levels` on
  its items give a row of buttons (All and one per level) that shows only the
  items carrying a level, with a count read out to screen readers.
- `tools/probe.py`: the copy check brings the copy button itself to the
  middle of the screen before clicking it, so the check no longer depends on
  where an earlier step left the page (a long table's button could sit under
  its pinned heading).
- `fingerprint` leaves out the masthead, parts panel, skip link and part
  numbers `page()` writes, so moving a page onto `page()` keeps its published
  date; `fingerprint(html, furniture)` also leaves out elements named
  `tag.class`, for the furniture of pages made another way.
- `tools/probe.py`: the defined-term check moves the mouse away before each
  hover, since two terms can sit at the same screen point once each is
  scrolled into view and a hover that does not move the mouse shows nothing.
- A part titled "Part 2 · Costs" keeps its own number in the parts panel and
  the contents; beside such parts, a part with no number of its own is shown
  unnumbered rather than out of step.
- A page carries the kit's core and only the features it uses. Tabs, long
  tables, pinned headings, charts, cards, copying a table or diagram, copying
  a block and section links (`FEATURES`) go into a page only when its markup
  uses them (`features_needed`), with the parts they share (cells, the side
  pane, the copy command) included once. `page(features=)` and
  `apply(features=)` name more, kept in the page as `<meta name="pk-features">`;
  a page running a script of its own and naming none carries every feature.
  `link_refs`, `link_sources` and `link_terms` bring the cards with them, and
  `refit` brings any other changed page up to date. `assets()` with no
  argument still returns the whole kit. `features_carried` reads what a page
  carries.
- A link to a row of a long table in a part or tab not on screen now shows
  the part, then the tab, then opens the table; the find shortcut opens long
  tables after showing every part and tab, so a table that can only be
  measured once its part or tab shows is opened after it is measured.
- `tools/probe.py` loads each page again with every feature put back, and
  fails when the page uses a feature whose code was left out, or a feature it
  carries does not act as it does with the whole kit.
- `examples/small.py` builds a short page that uses only some features.
- A table in a closed section no longer pins its heading over the page.
  Both engines keep a box for what a closed section holds, laid out over
  whatever follows it, so on a page with tables in a closed section, two or
  three heading copies could be pinned at once over a table being read.
  `tools/probe.py` checks it on any page with a table in a closed section.
- `tools/probe.py`: the copy check moves the mouse off the page's content
  before reading whether a table's copy button waits to be pointed at. An
  earlier check could leave the mouse over that table (a defined term clicked
  in one of its cells), where the button rightly shows. `examples/table_term.py`
  builds a page with that shape for the probe.

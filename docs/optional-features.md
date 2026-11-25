# Pages carry only the features they use

Every page is one self-contained file, so every byte of the kit travels in
every page. As the kit gains features, a page that uses none of them should
not carry their code. So the kit is a **core**, which every page carries, and
**optional features**, each embedded only in a page that uses it.

## What is core, and why

The core is what makes any page readable, whatever is on it:

- the panel: search over the whole document, the contents, the expand and
  collapse control, folding the panel away;
- parts, one shown at a time;
- links that land in a closed section, a hidden part or a pane not shown;
- light and dark;
- markings and watermarks, and print.

Search and the panel are core because a reader looks for things on every
page. Links that land are core because any page can link into a closed fold.
Each of these is small beside the features below, and leaving one out would
change how every page behaves rather than what one page shows.

Everything else is optional (`pagekit.FEATURES`):

| Feature | Found in the markup as |
|---|---|
| `tabs` | a `div.pk-tabs` holding two or more `section.pk-tab` |
| `long-tables` (and filter and sort) | a table with six or more body rows, not in a figure or opted out |
| `pinned-headings` | a table with a heading row, not in a figure or opted out |
| `charts` | an SVG with a view box, three or more rectangles and a line, or bars in table cells (`.cbarfill`) |
| `cards` (identifiers, sources, terms) | the page's identifier data, or a link marked `pk-ref` |
| `copy-out` (a table or diagram) | a table of two or more rows with two or more cells in a row, or an SVG not drawn small |
| `copy-blocks` | a `pre`, a `.pk-message` or an element with `data-pk-copy-label` |
| `section-links` | an h2 to h4 or a fold title outside the page's furniture (the panel gives headings ids as it runs, so an id is not required) |

## How a page says what it uses

The builder reads the page's own markup while it writes the page
(`features_needed`), so nobody keeps a list per page. The detectors err
towards including a feature: whatever the kit would act on in the browser is
something the detector reports. A table in a closed fold still counts,
because the kit decides it when the fold opens.

Two cases the markup cannot show:

- **Content added after the build.** `link_refs`, `link_sources` and
  `link_terms` add the cards themselves. Any other change: `refit(html)`.
- **Content a page's own script adds when it runs.** A page that runs a
  script of its own carries every feature, unless it names the ones its
  script needs: `page(features=[...])` or `apply(html, features=[...])`
  (an empty list names none; `"all"` names every one). The names are kept in
  the page as `<meta name="pk-features">`, so applying the kit again keeps
  them.

## Features that lean on each other

Some code is used by several features: a table's cells read as text (long
tables sort by it, copying out copies it), the side pane (cards open an
entry in it, copying out shows a picture in it), and the copy command with
its notice (copying out, copying a block and a section link all copy). These
are **shared parts**. A feature names the shared parts it needs; a shared
part comes in once, with whichever feature needs it first, and never on its
own. A diagram drawn as SVG brings `copy-out` with it, because that feature is
found from any SVG of a diagram's size; a new feature that needs the picture
code without the copy buttons would move that code into a shared part.

## How the script is split

`kit.js` and `kit.css` stay one file each, so the one-scope rule and the
traps in `README.md` still read against one file. A feature's code sits
between a `pk:feature NAME` line and a `pk:end NAME` line (it may have several
such stretches, such as its print rules), and the build leaves out the
stretches a page does not need.

Because a left-out feature's functions do not exist on that page, nothing
outside a feature calls into it. A feature lends its behaviour by moment with
`on(moment, fn)`: `table` (each table at load), `start` and `built` (before
and after the panel is built), `open` (make a node visible), `shown`
(something hidden just showed), `find`, `print` and `unprint`, `frame` and
`relayout` (pinned copies follow the page), `inpane`. The core calls
`fire(moment)`, which does nothing when no feature listens. Handlers run in
the order the features sit in the file: tabs come before long tables, so a
link into a table inside a hidden tab shows the tab first and then opens the
table.

The page records what it carries: `var KIT = "…"` in its script, and
`data-pk-kit` on the page once the script runs. `features_carried(html)` reads it.

## How it is proved

- A test reads every stretch of `kit.js` and fails if any part uses a name
  declared only in a feature it does not need. Breaking it once (a call from
  the core to a tab function, and from the copy command to the pane) made it
  fail on both.
- A test checks each feature's detector on invented markup that uses it, and
  on markup that looks like it but is not. Another builds the script for the
  core alone and for each feature alone and parses it.
- `tools/probe.py` loads each page twice in each engine: as built, and with
  every feature put back. It fails when the whole kit acts on the page in a
  way the page's own kit cannot (a feature the page uses whose code was left
  out), and when a feature the page carries does not act as it does with the
  whole kit.

## Adding a feature

1. Write its script between `/* pk:feature NAME */` and `/* pk:end NAME */`
   in `kit.js`, after the core, and its styles (print rules included) the
   same way in `kit.css`. Register its work with `on(...)`; if the core must
   ask it something new, add a moment and `fire` it from the core.
2. Name it in `FEATURES` with the shared parts it needs, and teach `_Uses` to
   find it in markup, erring towards finding it.
3. Add its invented markup to the detector test, and a mark the probe can
   see when it acts to the probe's footprint.
4. Run `make check`, then the probe on a page that uses it and one that does
   not. Break it once to see the probe fail.

# 2026-11-25 16:04 UTC: pages carry only the features they use

**What PageKit gained:**

- Every page now carries the kit's core and only the optional features its
  markup uses. `kit.js` and `kit.css` stay one file each; each optional
  feature, and each part features share, sits between `pk:feature` and
  `pk:end` lines, and the build leaves out what a page does not use. The core
  is the panel (search, contents), parts, links that land, light and dark,
  markings and print; the optional features are tabs, long tables (with
  filter and sort), pinned headings, charts, cards, copying a table or
  diagram, copying a block and section links. The shared parts are a table's
  cells read as text, the side pane and the copy command. The design and the
  steps for adding a feature are in `docs/optional-features.md`.
- The core no longer calls into any feature: a feature lends its behaviour
  with `on(moment, fn)` and the core asks with `fire(moment)`. A test reads
  every stretch of `kit.js` and fails on a name used across that line; it was
  proved by adding a call from the core to a tab function and one from the
  copy command to the pane, which made it fail, then removing them.
- The builder finds the features in the page's markup (`features_needed`);
  `page(features=)` and `apply(features=)` name more, kept in the page; a page
  running a script of its own and naming none carries every feature. The
  identifier, source and term linkers bring the cards with them, and `refit`
  updates any other changed page. `assets()` with no argument still returns
  the whole kit.
- A link into a long table in a part or tab not on screen now shows the part,
  then the tab, then opens the table, and the find shortcut opens long tables
  last, after the parts and tabs.
- The probe loads each page a second time with every feature put back and
  fails when that whole kit acts on the page where the page's own kit cannot,
  or when a carried feature acts differently.
- `examples/small.py` builds, on demand, a short page that uses only some
  features.

**Sizes**, measured on invented pages built before and after: a page of a
title and three short sections came out at about half its old size; the
small example (a short table and a block to copy) at about three quarters;
the sample, which uses every feature, about a kilobyte larger, which is what
the hooks and the split print rules add to a page that carries everything.
The core alone is a little under two fifths of the whole kit.

**Checks:** `make check` passed (guard, ruff, mypy and the tests). The probe
passed every run on the sample page, the small page and the three-section
page (both engines, both widths, all four hosting modes, plus the new feature
check in each engine); on all three the features the whole kit acted on were
exactly the ones the page carried. Proved by breaking it once: the small page
with its block-copy code left out, and the sample with its tabs code left
out, both failed the new check in both engines, while every other probe
check on those pages still passed.

**Next:** new features are built as optional features from the start,
following `docs/optional-features.md`.

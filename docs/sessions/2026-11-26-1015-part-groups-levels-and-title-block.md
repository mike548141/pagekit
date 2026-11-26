# 2026-11-26 10:15 UTC: part groups, items by level, and the title block

**What PageKit gained:**

- **A fix: no blank space above a part shown alone.** The rule meant to drop
  the top margin of the parts not shown was written `.pk-js .pk-one .pk-part +
  .pk-part`, which looks for `pk-one` inside an element carrying `pk-js`. The
  script puts both on `<html>`, so it never matched. Parts not shown are
  hidden "until found" and keep a box of no height, so each kept its 3rem
  margin: measured in Chromium and WebKit on a 15-part page shown at part 12,
  eleven hidden parts' margins of 3rem (48px each) stacked above it. It is now
  `.pk-js.pk-one`, and the space is 0 in both engines; with every part shown
  the gap between parts is still 48px, and the print rules are unchanged. A
  test fails on any rule that looks for one of the classes the script puts on
  `<html>` inside another element (it failed on the old rule, and passes on
  the new one), and the probe measures the space above the last part shown
  alone.
- **Part groups.** `"group"` on a part in `page(parts=…)`, or `data-pk-group`
  on a part's section, starts a group running to the next labelled part. The
  panel shows each label above its parts and names each group's list by its
  label (`aria-labelledby`); the no-script contents list does the same.
  Numbering runs on across groups. A page without groups is built byte for
  byte as before (a test compares the contents list's shape, and a blank
  label builds the same page as none).
- **The title block, one part at a time.** `div.pk-hero` shows whole with
  the first part, with every part shown and on paper. Past the first part it
  is its h1 alone on one line, so the page keeps its one h1 on screen and for
  a screen reader (the masthead does not carry the title). Everything else in
  the block is hidden "until found": search and find-in-page still reach it,
  and reaching it shows the first part.
- **Show items by level** (optional feature `level-filter`).
  `data-pk-filter="must = Must have, should, could"` on a container and
  `data-pk-levels="must could"` on its items give a row of buttons above it
  (All, then one per level, each with its count). A level shows only the
  items carrying it; an item with several shows under each; an item with none
  always shows. Buttons carry `aria-pressed`, and a polite live count says
  "12 of 40 shown". Items can be cards, list items, sections or table rows. A
  search result, a link or the find shortcut reaching an item not shown goes
  back to All; a copied table leaves out rows not shown; with scripting off or
  on paper every item shows. Items not shown are hidden with `display: none`,
  not "until found": a box of no height would still take a cell in a card
  grid.
- The sample page has its three parts in two groups, a card grid of ideas and
  a list of needs, each shown by level.

**Checks:** `make check` passed (guard, ruff, mypy and the tests, with each
feature's script parsed alone). The probe passed every run on the sample, the
small page, the table-term page and an invented 15-part page with three part
groups and a table whose rows are shown by level: both engines, both widths,
all four hosting modes and the feature check. It gained checks for the space
above a part shown alone, the part groups in the panel, the title block (one
part, every part, paper, and search from a later part), and items shown by
level (a level, the keyboard, search, the find shortcut and paper). Proved by
breaking each once: the old margin rule, the title block left whole, the
group lists left unnamed, the level class never set, and the open and find
moments unhooked each failed exactly their own check in Chromium.

**Open:** the level buttons count every item a container holds, so a heading
between items that all go hidden stays on screen; a page that needs it hidden
can carry the heading inside an item.

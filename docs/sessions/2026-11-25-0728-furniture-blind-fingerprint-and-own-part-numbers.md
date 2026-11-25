# 2026-11-25 07:28 UTC: a fingerprint blind to the builder's furniture, and parts that keep their own numbers

**What PageKit gained:**

- `fingerprint` leaves out the masthead, parts panel, skip link and part
  numbers that `page()` writes, so a page rebuilt with `page()` from the
  same words keeps its published date. `fingerprint(html, furniture)` also
  leaves out elements named `tag.class`, for pages made another way being
  moved onto `page()`. Tested with one page built twice with different meta
  lines; the test was proved by emptying the furniture list (`71d4edb`).
- The probe's defined-term check moves the mouse away before each hover: at
  a narrow width two terms can sit at the same screen point once each is
  scrolled into view, and a hover that does not move the mouse fires no
  hover event. After the fix a long page with terms passed every run, both
  engines, every hosting mode, the narrow Chromium runs included
  (`71d4edb`).
- A part titled "Part N · title" keeps its own number in `page()`'s
  contents and in the panel the script builds; its heading keeps its full
  title with no second number, and a part without a number of its own,
  beside such parts, is shown unnumbered (`ff86ccf`).

Both commits passed the publication guard and an independent read for
meaning before they were pushed.

**Next:** nothing queued from this session.

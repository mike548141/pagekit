# 2026-11-24 10:22 UTC: the first public version and three reader features

**What PageKit gained:**

- The repository itself: the package (`page`, `apply`, `compose`, `check`,
  `mark_parts`, `link_refs`, `set_marks`, `set_published`, `fingerprint`,
  `set_skip`), the browser probe, the invented sample (a community garden's
  season report), the publication guard and atelier's floor hooks.
- Hardening before the first release, after an independent review: a
  marking holds only marking characters; the logo address is escaped; a
  refset URL must be relative or http(s); `check()` finds more ways a page
  can reach outside itself; one version number.
- Copy a code or message block; filter and sort a long table (the filter
  matches words within cells); sources that explain themselves
  (`link_sources`).
- On this branch, not yet on `main`: a link a page already makes to a
  listed source gets the card, and inside a viewer's frame the kit follows
  every page's in-page links, so a link into a closed section opens it.
  Probed: every run passed, both engines, every hosting mode.

**Next:** land this branch through the gate; tabs within a section; defined
terms (a page's own glossary as cards, the same engine as sources).

# Changelog

## Unreleased

- Copy a code or message block: a labelled, always-visible button on every
  `<pre>`, every `.pk-message` and any element with `data-pk-copy-label`.
- `set_skip` replaces its tag where it stands, so it and `set_marks` can be
  re-applied in either order without moving anything.

## 0.1.0 (unreleased)

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

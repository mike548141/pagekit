# The repository becomes goodcopy, with a guide to how it is used

## What changed

- **The repository is renamed from `pagekit` to `goodcopy`** and widened: a
  toolkit for turning working files into finished, branded deliverables.
  GitHub keeps a redirect from the old address.
- **PageKit moved into `pagekit/`**, still its own installable package with
  its own `pyproject.toml`, so it can be installed without anything else
  goodcopy will hold:
  `pip install "pagekit @ git+https://github.com/mike548141/goodcopy#subdirectory=pagekit"`.
  The package's files moved unchanged; its tests, examples, probe, feature
  notes, reference and changelog moved with it. The distribution carries its
  own copy of the licence and notice, because a package's licence files must
  sit inside its own folder.
- **The top-level `README.md` is now a guide to how goodcopy is meant to be
  used**: the flow stage by stage (source material, working files, build,
  the brand as data, PageKit, an output folder never edited by hand), every
  kind of working file the toolkit is meant to take, which stages a user
  supplies and which goodcopy provides, a worked example on the invented
  Example Trust's season report, and which pieces are in the repository today.
  The flow is drawn in `docs/flow.svg`, plain boxes and words on a white
  ground so it reads in GitHub's light and dark themes.
- **The guards follow the rename.** The contributor settings are now
  `goodcopy.denylist` and `goodcopy.extraHook`. The guard's exemption for the
  licence text covers a package's copy only while it is byte-identical to the
  top-level `LICENSE`; an edited copy is scanned like any other file (proved by
  editing the copy once: the guard failed).
- `make check` runs the guard over the whole repository, then lint, types and
  tests inside each package with that package's own settings.

## How it was checked

- `make check` in a fresh virtualenv: the guard clean, ruff and mypy clean, the
  PageKit tests passing.
- The worked example in the README was extracted and run as written against
  this tree: it built a three-part page with the brand and the watermark, and
  `pagekit.check` found nothing that would stop it travelling as one file.
- The flow drawing was rendered as an image at the README's width on a dark
  page and read: every label sits inside its box.
- The browser probe was not run: no file of the package changed.

## Owed

- When the build stage and the cross-deliverable checks arrive, the guide's
  table *What is here today* and the drawing's dashed box change with them.

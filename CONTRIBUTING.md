# Contributing

1. `make venv`, `make hooks` (needs a clone of atelier beside this one, or
   `make hooks ATELIER=<path>`), then `make check` before every commit.
2. Every example, test and comment is invented or generic. Nothing in this
   repository, its commit messages included, may name or describe a real
   organisation, its reports or its reasons for wanting a feature: write the
   capability, never the circumstance (`CLAUDE.md` has the full rule).
3. A PageKit feature that runs in the browser gets a check in
   `pagekit/tools/probe.py`, run in both engines, and the check is proved by
   breaking the feature once.
4. A change that adds or changes a stage of the flow brings the guide in
   `README.md`, and its drawing `docs/flow.svg`, up to date in the same change.

# goodcopy: the whole gate. The guard runs first over the whole repository and
# needs only the standard library; lint, type checks and tests run from the
# project virtualenv, package by package, each with its own pyproject.toml.
PY ?= python3
VENV ?= .venv
ATELIER ?= ../atelier
VPY := $(abspath $(VENV))/bin/python

.PHONY: check guard lint types test venv hooks sample

check: guard lint types test

guard:
	$(PY) tools/guard.py

# The repository's own tools are linted with PageKit's settings.
lint:
	cd pagekit && $(VPY) -m ruff check src tests tools examples
	$(VPY) -m ruff check --config pagekit/pyproject.toml tools

types:
	cd pagekit && $(VPY) -m mypy src

test:
	cd pagekit && $(VPY) -m pytest -q

sample:
	cd pagekit && $(VPY) examples/sample.py

# Once per clone: a virtualenv with each package installed in editable mode.
venv:
	$(PY) -m venv $(VENV)
	$(VPY) -m pip install -e './pagekit[dev]'

# Once per clone: atelier's floor on every commit (the guard runs inside it as a
# local check, see .atelier-floor.json) and the guard on every commit message.
# The floor's scanners come from a clone of atelier, by default beside this one.
hooks:
	@test -f '$(ATELIER)/tools/floor.py' || { echo "no atelier clone at $(ATELIER); make hooks ATELIER=<path>"; exit 1; }
	git config core.hooksPath .githooks
	git config hooks.atelierTools "$$(cd '$(ATELIER)/tools' && pwd)"

.PHONY: install lint format format-check typecheck test coverage verify build clean check-uv scan scan-dist

UV := uv

check-uv:
	@command -v $(UV) >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/"; exit 1; }

install: check-uv
	$(UV) sync --all-extras

lint:
	$(UV) run ruff check src tests

format:
	$(UV) run ruff format src tests

format-check:
	$(UV) run ruff format --check src tests

typecheck:
	$(UV) run mypy

test:
	$(UV) run pytest

coverage:
	$(UV) run pytest --cov=src/dev_guru --cov-report=term --cov-report=xml --cov-fail-under=85

verify: lint format-check typecheck test

build: check-uv
	rm -rf dist
	$(UV) build

# Scan the built wheel and sdist the way package firewalls do (secrets, vulnerable dependencies, malicious-code
# heuristics, inventory) with free tools: gitleaks, pip-audit, GuardDog, Bandit. Report in scan-report/.
scan: build scan-dist

scan-dist:
	$(UV) run --no-project python scripts/scan_dist.py --dist dist --out scan-report $(SCAN_ARGS)

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml scan-report .acceptance-venv

# ── Acceptance (capability scenarios + release gate) ─────────────────────────
# See acceptance/README.md. The gate writes acceptance/report/{acceptance.json,summary.md}; BLOCK fails.
UV ?= uv
ACCEPTANCE_VENV := .acceptance-venv
ACCEPTANCE_EXTRAS ?=
ACCEPTANCE_ARGS ?=

.PHONY: acceptance acceptance-wheel acceptance-dist web-journeys
# The web interface in real Chrome on its own temporary workspace (also a scenario in the suite). Needs Node 22+ and Chrome.
web-journeys:
	PATH="$(CURDIR)/.venv/bin:$$PATH" node acceptance/browser/web_journeys.mjs

acceptance:
	$(UV) run --frozen pytest acceptance -n auto -p no:cacheprovider $(ACCEPTANCE_ARGS)

# What ships: build the wheel, install it into a fresh venv and run the suite from there.
acceptance-wheel: build
	$(MAKE) acceptance-dist

# Against an already-built dist/*.whl (CI tests the exact artifact it publishes).
acceptance-dist:
	rm -rf $(ACCEPTANCE_VENV)
	$(UV) venv -q --python 3.12 $(ACCEPTANCE_VENV)
	$(UV) pip install -q --python $(ACCEPTANCE_VENV)/bin/python "$$(ls -t dist/*.whl | head -1)$(if $(ACCEPTANCE_EXTRAS),[$(ACCEPTANCE_EXTRAS)])" \
	  pytest pytest-bdd pytest-xdist pyyaml
	ACCEPTANCE_BIN_DIR=$(CURDIR)/$(ACCEPTANCE_VENV)/bin $(ACCEPTANCE_VENV)/bin/python -m pytest acceptance \
	  -n auto -p no:cacheprovider $(ACCEPTANCE_ARGS)

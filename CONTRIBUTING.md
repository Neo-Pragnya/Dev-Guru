# Contributing

Read [AGENTS.md](AGENTS.md) first: it sets the boundaries between Dev Guru, Ananke Plexus and Dex Trove.

1. `make install`, then make your change with tests.
2. `make verify` must pass (ruff, ruff format, strict mypy, pytest).
3. If you change user-facing behaviour, add or update a scenario in `acceptance/features/` and run
   `make acceptance-wheel`. The gate must not say BLOCK.
4. Update `CHANGELOG.md` under *Unreleased*.

Commits use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`…).

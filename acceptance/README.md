# Capability acceptance suite

Behaviour-level checks for everything Dev Guru promises, run against the real CLI before every release.
Unit tests prove the parts; this suite proves the product.

```bash
make acceptance            # dev environment
make acceptance-wheel      # the built wheel in a fresh venv (what ships)
```

- **Scenarios** (`features/*.feature`) run in sandboxes: a fresh git project from `fixtures/projects/`, its own
  HOME, no colour. `$PROJECT`, `$SANDBOX`, `$FIXTURES`, `$REPO` are set; shell syntax works.
- **Capabilities** (`capabilities.yaml`) group scenarios via `@cap_<id>`; `blocker: true` ones veto a release.
- **The gate** writes `report/summary.md`: PROMOTE (all pass), CONDITIONAL (known issues, unverified, non-blocker
  gaps, low CLI coverage), BLOCK (a blocker failed or has no scenario).
- `@known_issue` = the *correct* behaviour of something currently broken (strict xfail: fails loudly once fixed).
- `@adversarial` probes always sit next to a legitimate twin that must still work.
- Never commit secret-shaped strings: `Given the file "x" with content containing a fake "aws-access-key" credential:`
  (with `{credential}` in the docstring) generates one at runtime.

Step vocabulary and gate rules: see `harness.py` (docstrings) or the capability-acceptance skill.

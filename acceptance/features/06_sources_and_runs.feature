Feature: Internal skills to an explored report, with Dex switched off
  Background:
    Given an empty directory
    And the file "team-skills/deploy-check/SKILL.md" with content:
      """
      ---
      name: deploy-check
      description: Check a deploy before release
      version: 1.0.0
      ---
      Steps.
      """
    And the file ".ananke/config.toml" with content:
      """
      [capability_sources.team]
      root = "team-skills"
      namespace = "acme"
      """
    And the file "shop/cart.py" with content:
      """
      from shop.prices import price

      def total(items):
          return sum(price(i) for i in items)
      """
    And the file "shop/prices.py" with content:
      """
      def price(item):
          return 1
      """

  @cap_sources
  Scenario: An internal skill is discovered, the code is explored in an Ananke run, and Dex is never loaded
    When I run "dev sources --json"
    Then it succeeds
    And the output contains "team:acme/deploy-check"
    When I run "dev explore . -o explorer.html --json"
    Then it succeeds
    And the JSON file "explorer.html.manifest.json" at "ananke_run.protocol" equals "ananke-app/1"
    And a file matching ".ananke/app/runs/*/artifacts/explorer.html" exists
    When I run:
      """
      python3 -c "import sys, dev_guru.service as s, pathlib; from dev_guru.client import connect; s.explore(pathlib.Path('.'), client=connect()); print('dex loaded:', any(m.startswith('dex_trove') for m in sys.modules))"
      """
    Then it succeeds
    And the output contains "dex loaded: False"

  @cap_sources
  Scenario: A learning candidate gets a review page before anything is promoted
    When I run:
      """
      python3 -c "from pathlib import Path; from ananke.plexus.learning import capture; capture(Path('.'), 'deploy-check', description='Check a deploy before release, with a rollback plan. Use before every release.', body='Steps, plus rollback.', cases=[{'id': 'p', 'kind': 'positive', 'command': 'true'}, {'id': 'r', 'kind': 'regression', 'command': 'true'}])"
      """
    Then it succeeds
    When I run "dev learning review deploy-check -o review.html"
    Then it succeeds
    And the output contains "not evaluated yet"
    And the file "review.html" contains "connect-src 'none'"
    And the file "team-skills/deploy-check/SKILL.md" contains "Steps."

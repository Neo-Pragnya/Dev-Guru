Feature: A change is reviewed from Git, the code graph and the project's own reports
  Background:
    Given a fresh project

  @cap_code_review
  Scenario: What changed, who it reaches, and a draft pull request description
    Given the file "shop/prices.py" with content:
      """
      import json


      def price(item):
          return 2
      """
    When I run "dev review . --base HEAD --json --pr-body PR.md"
    Then it succeeds
    And the JSON output at "changed.symbols[0].name" equals "price"
    And the JSON output at "reach.callers[0].id" equals "function:shop/cart.py:total"
    And the JSON output at "verdict" equals "ready for review"
    And the file "PR.md" contains "## Residual risks"

  @cap_code_review @adversarial
  Scenario: An unknown base is refused with a stable code
    When I run "dev review . --base no-such-branch"
    Then the exit code is 2
    And the output contains "INVALID_INPUT"

  @cap_docs_audiences
  Scenario: A documentation site with navigation, and Obsidian notes
    When I run "dev docs . --site site --generator mkdocs"
    Then it succeeds
    And the file "site/mkdocs-nav.yml" contains "Architecture: principal.md"
    And the file "site/principal.md" contains "```mermaid"
    When I run "dev docs . -f obsidian -o notes.md"
    Then it succeeds
    And the file "notes.md" contains "[[shop/"

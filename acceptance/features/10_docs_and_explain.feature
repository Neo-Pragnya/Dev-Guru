Feature: Documentation and explanations come from the code, cited line by line
  Background:
    Given a fresh project

  @cap_docs_audiences
  Scenario: Documentation for each audience, with its provenance and a receipt
    When I run "dev docs . --audience executive -o notes/leaders.md"
    Then it succeeds
    And the file "notes/leaders.md" contains "## Where the risk is"
    And the file "notes/leaders.md" contains "## Provenance"
    And the JSON file "notes/leaders.md.manifest.json" at "audience" equals "executive"
    When I run "dev docs . --audience novice --detail brief -o notes/new.md"
    Then it succeeds
    And the file "notes/new.md" contains "## Words used here"
    And the file "notes/new.md" contains "(../shop/"
    When I run "dev docs . --audience principal -f deck -o notes/arch.html"
    Then it succeeds
    And the file "notes/arch.html" contains "connect-src 'none'"

  @cap_explain_ladder
  Scenario: One file explained from novice to executive
    When I run "dev explain cart.py"
    Then it succeeds
    And the output contains "## In plain words"
    And the output contains "## For developers"
    And the output contains "## For architects"
    And the output contains "## For leaders"
    And the output contains "shop/cart.py"
    When I run "dev explain total --json -l novice"
    Then it succeeds
    And the JSON output at "kind" equals "function"

  @cap_explain_ladder @adversarial
  Scenario: Unknown names and audiences are refused with a stable code
    When I run "dev explain nothing_here"
    Then the exit code is 2
    And the output contains "INVALID_INPUT"
    When I run "dev docs . --audience guru"
    Then the exit code is 2

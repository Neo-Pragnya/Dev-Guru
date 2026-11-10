Feature: dev graph draws a bounded, expandable piece of the code graph
  Background:
    Given a fresh project

  @cap_graph_export
  Scenario: A focused file graph exports as Mermaid, and names how to see more
    When I run "dev graph . --focus cart.py --depth 1"
    Then it succeeds
    And the output contains "flowchart LR"
    And the output contains "shop/prices.py"
    And the output contains "imports"

  @cap_graph_export
  Scenario: The same graph exports as a safe, static SVG and as JSON
    When I run "dev graph . --level symbol -f svg -o graph.svg --static"
    Then it succeeds
    And the file "graph.svg" contains "<svg"
    And the file "graph.svg" does not contain "<script"
    When I run "dev graph . --level package -f json"
    Then it succeeds
    And the JSON output at "schema" equals "dev-guru/subgraph@1"
    And the JSON output at "level" equals "package"

  @cap_graph_export @adversarial
  Scenario: An unknown focus or budget is refused with a stable code
    When I run "dev graph . --focus nothing.py"
    Then the exit code is 2
    And the output contains "INVALID_INPUT"
    When I run "dev graph . --budget 0"
    Then the exit code is 2

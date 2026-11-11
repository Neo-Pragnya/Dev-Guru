@cap_harness
Feature: Dev Guru finds and checks the Ananke harness it runs on

  Scenario: doctor reports a compatible harness and the capabilities Dev Guru needs
    When I run "dev doctor --json"
    Then it succeeds
    And the JSON output at "ok" equals true
    And the JSON output at "harness.transport" equals "in-process"
    And the JSON output at "harness.missing_required" equals []
    And the output contains "graph.build"
    And the output contains "graph.load"

  Scenario: doctor prints a readable summary
    When I run "dev doctor"
    Then it succeeds
    And the output contains "ananke-plexus"
    And the output contains "supported >=0.3.36,<0.4"

  @cap_cli_ux
  Scenario: An unsupported transport is refused, never silently swapped for another
    When I run "dev doctor --transport gateway --json"
    Then the exit code is 2
    And the JSON output at "error.code" equals "UNSUPPORTED_TRANSPORT"
    And it does not crash

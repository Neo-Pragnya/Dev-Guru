@cap_packaging
Feature: The package installs cleanly

  Scenario: dev starts and lists its commands
    When I run "dev --help"
    Then it succeeds
    And it finishes within 6 seconds

  Scenario: The CLI reports the version being released
    When I run "dev --version"
    Then it succeeds
    And the output names the package version

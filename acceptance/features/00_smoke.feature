@cap_packaging
Feature: The package installs cleanly

  Scenario: devguru starts and lists its commands
    When I run "devguru --help"
    Then it succeeds
    And it finishes within 6 seconds

  Scenario: The CLI reports the version being released
    When I run "devguru --version"
    Then it succeeds
    And the output names the package version

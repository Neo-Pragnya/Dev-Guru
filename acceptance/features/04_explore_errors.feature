Feature: dev explore fails clearly when there is nothing to explore

  @cap_explore @cap_cli_ux
  Scenario: An empty folder is a clean error, not an empty report
    Given an empty directory
    When I run "dev explore . -o r.html"
    Then the exit code is 1
    And the output contains "WORKSPACE_INVALID"
    And the file "r.html" does not exist


  @cap_report_browser @cap_explore
  Scenario: Dev Guru explores its own source and the report works in a browser (dogfood)
    # Its own render.py contains the template placeholders, which once corrupted the embedded data.
    When I run "dev explore $REPO/src -o self.html --name 'Dev Guru' && node $REPO/acceptance/browser/report_journeys.mjs self.html"
    Then it succeeds
    And the output contains "journeys passed"

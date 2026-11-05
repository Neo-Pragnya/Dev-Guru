Feature: dev explore turns a codebase into an interactive, offline report
  Background:
    Given a fresh project

  @cap_explore
  Scenario: Exploring a project writes a report and its manifest
    When I run "dev explore . -o out/explorer.html --name shop --json"
    Then it succeeds
    And the JSON output at "project.files" equals 3
    And the file "out/explorer.html" exists
    And the file "out/explorer.html.manifest.json" exists
    And the JSON file "out/explorer.html.manifest.json" at "renderer" equals "dev-guru/explorer-html@1"
    And the JSON file "out/explorer.html.manifest.json" at "transport" equals "in-process"

  @cap_explore
  Scenario: The same code gives the same report content
    When I run:
      """
      dev explore . -o a.html --json > a.json && dev explore . -o b.html --json > b.json
      python -c 'import json; a, b = (json.load(open(f))["input_digest"] for f in ("a.json", "b.json")); assert a == b, (a, b); print("same", a[:19])'
      """
    Then it succeeds
    And the output contains "same sha256:"

  @cap_report_safety @adversarial
  Scenario: Hostile docstrings and comments can't break out of the report
    Given the file "shop/evil.py" with content:
      """
      def evil():
          '''</script><script>window.__pwned = 1</script>'''
          # </script><img src=x onerror=alert(1)>
          return 1
      """
    When I run:
      """
      dev explore . -o r.html
      python -c 'print("closers", open("r.html").read().count("</" + "script>"))'
      """
    Then it succeeds
    And the output contains "closers 6"

  @cap_report_safety
  Scenario: The report references nothing on the network
    When I run "dev explore . -o r.html && grep -Eo '(src|href)=.?(https?:)?//' r.html | wc -l"
    Then it succeeds
    And the output matches "^\s*0\s*$"
    And the file "r.html" contains "connect-src 'none'"

  @cap_report_browser
  Scenario: The report works in a real browser
    Given the file "shop/evil.py" with content:
      """
      def evil():
          '''</script><script>window.__pwned = 1</script>'''
          return 1
      """
    When I run "dev explore . -o r.html && node $REPO/acceptance/browser/report_journeys.mjs r.html --hostile"
    Then it succeeds
    And the output contains "journeys passed"
    And it finishes within 150 seconds

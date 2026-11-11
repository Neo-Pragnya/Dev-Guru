Feature: A process can be walked, edited and read back through Ananke
  Background:
    Given an empty directory

  @cap_process_codesign
  Scenario: Walk the process in a real browser, edit a step, and read the Markdown back
    Given the file "order.md" with content:
      """
      # Order handling

      1. Sales: Receive the order <img src=x onerror=window.__pwned=1>
      2. Finance: Is the credit good?
         - Yes: go to step 3
         - No: go to step 5
      3. Warehouse: Pick and pack
      4. Warehouse: Ship the order. End.
      5. Sales: Tell the customer
      """
    When I run "git init -q . && dev bpmn order.md -o order.html --markdown order.again.md"
    Then it succeeds
    And the file "order.again.md" contains "2. Finance: Is the credit good?"
    When I run "PROCESS_MD_OUT=edited.md node $REPO/acceptance/browser/process_journeys.mjs order.html --hostile"
    Then it succeeds
    And the output contains "journeys passed"
    And the file "edited.md" contains "1. Front desk: Take the order"
    When I run "dev bpmn edited.md -o edited.html"
    Then it succeeds
    And the file "edited.html" contains "Front desk"

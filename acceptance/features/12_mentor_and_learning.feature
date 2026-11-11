Feature: Advice comes from repeated failures, and lessons are mapped, never published
  Background:
    Given a fresh project

  @cap_mentor_feedback
  Scenario: A failure repeated across runs gets advice that names the runs
    When I run "for k in a b c; do ananke app run graph.impact --key $k >/dev/null 2>&1; done; ananke app run workflow.run --key once >/dev/null 2>&1; dev mentor . --level novice"
    Then it succeeds
    And the output contains "worth fixing once"
    And the output contains "Seen once (no advice yet)"
    When I run "dev mentor . --json"
    Then it succeeds
    And the JSON output at "advice[0].count" equals 3
    And the JSON output at "advice[0].code" equals "INVALID_REQUEST"

  @cap_mentor_feedback @adversarial
  Scenario: With no repeated failure there's no advice, and a single occurrence is refused as a threshold
    When I run "dev mentor ."
    Then it succeeds
    And the output contains "there's no advice"
    When I run "dev mentor . --min-repeats 1"
    Then the exit code is 2
    And the output contains "INVALID_INPUT"

  @cap_learning_graph
  Scenario: The learning graph maps a lesson to the files it mentions, and publishes nothing
    Given the file "lesson.md" with content:
      """
      When graph impact fails, pass changed_files, such as shop/cart.py.
      """
    When I run "ananke learning capture impact-lesson --description 'Pass changed_files to graph impact runs so they can find what a change reaches.' --body lesson.md --case 'p:positive:python -c pass' --case 'r:regression:python -c pass' >/dev/null && dev learning graph -f json"
    Then it succeeds
    And the JSON output at "lessons" equals 1
    And the output contains "file:shop/cart.py"
    And the output contains "needs review"

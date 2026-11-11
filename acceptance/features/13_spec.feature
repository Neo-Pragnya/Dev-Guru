Feature: Spec-driven work: a spec from an idea, each requirement traced to the code
  Background:
    Given a fresh project

  @cap_spec_trace
  Scenario: A new spec is traced to the code and kept in Ananke
    When I run "dev spec new 'Cart totals' --idea 'Totals must be right before checkout.'"
    Then it succeeds
    And the file "specs/cart-totals.md" contains "Totals must be right before checkout."
    Given the file "SPEC.md" with content:
      """
      # Cart totals

      ## Requirements

      - **R1** The cart total comes from `total` and each item's price.
      - **R2** Gift cards are refunded by bank transfer.
      """
    When I run "dev spec trace SPEC.md --level practitioner"
    Then it succeeds
    And the output contains "| linked |"
    And the output contains "| unlinked |"
    And the output contains "## The code behind each requirement (practitioner)"
    When I run "ananke app evidence"
    Then it succeeds
    And the output contains "spec-trace.json"

  @cap_spec_trace @adversarial
  Scenario: A spec is never overwritten, and a spec with no requirements is refused
    When I run "dev spec new X && dev spec new X"
    Then the exit code is 2
    And the output contains "already exists"
    Given the file "empty.md" with content:
      """
      # Nothing to trace
      """
    When I run "dev spec trace empty.md"
    Then the exit code is 2
    And the output contains "no requirements"

  @cap_spec_trace
  Scenario: A test-first plan, failing tests, verification and a lock against drift
    Given the file "SPEC.md" with content:
      """
      # Cart

      ## Requirements

      - **R1** The cart total comes from `total` for each item.
      - **R2** A total is never negative, after R1.
      """
    When I run "dev spec plan SPEC.md --json"
    Then it succeeds
    And the JSON output at "requirements[1].after" equals ["R1"]
    When I run "dev spec tests SPEC.md --out tests/spec"
    Then it succeeds
    And the file "tests/spec/test_r1.py" contains "pytest.fail"
    When I run "dev spec verify SPEC.md"
    Then the exit code is 1
    And the output contains "0 of 2 done"
    When I run "dev spec lock SPEC.md && dev spec trace SPEC.md --check-lock"
    Then it succeeds
    And the output contains "No drift."

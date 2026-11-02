Feature: Decks and published reports are safe to share
  Background:
    Given an empty directory

  @cap_present
  Scenario: Markdown slides become one offline, accessible deck
    Given the file "talk.md" with content:
      """
      ---
      title: Review
      ---

      # Review

      ---

      ## Steps

      + one
      + two

      <script>alert(1)</script>
      """
    When I run "dev present talk.md"
    Then it succeeds
    And the file "talk.html" contains "connect-src 'none'"
    And the file "talk.html" contains "&lt;script&gt;alert(1)&lt;/script&gt;"
    And the file "talk.html" does not contain "<script>alert(1)</script>"
    When I run "dev present talk.html --check"
    Then it succeeds

  @cap_present @adversarial
  Scenario: Remote images and missing alt text are refused
    Given the file "talk.md" with content:
      """
      # Title

      ![logo](https://example.com/logo.png)
      """
    When I run "dev present talk.md"
    Then the exit code is 2
    And the output contains "must be local files"
    And the file "talk.html" does not exist

  @cap_report_safety
  Scenario: The public profile leaves no source code in a published report
    Given the file "app/core.py" with content:
      """
      def checkout(cart, url="https://internal.example/pay"):
          \"\"\"Calls the internal payment gateway.\"\"\"
          INTERNAL_SECRET_LOGIC = sum(cart)
          return INTERNAL_SECRET_LOGIC
      """
    When I run "dev explore app -o public.html --profile public"
    Then it succeeds
    And the file "public.html" does not contain "INTERNAL_SECRET_LOGIC"
    And the file "public.html" does not contain "internal payment gateway"
    And the file "public.html" does not contain "internal.example"
    And the JSON file "public.html.manifest.json" at "profile" equals "public"

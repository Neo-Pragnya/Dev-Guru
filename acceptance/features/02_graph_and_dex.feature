Feature: The SDK uses real Ananke analysis, and Dex Trove stays optional
  Background:
    Given a fresh project

  @cap_harness_graph
  Scenario: The SDK summarises the graph Ananke builds for a project
    When I run:
      """
      python -c '
      import json
      from pathlib import Path
      from dev_guru.client import connect
      s = connect().graph_summary(Path("."))
      print(json.dumps(s.model_dump()))'
      """
    Then it succeeds
    And the JSON output at "nodes_by_kind.file" equals 3
    And the JSON output at "nodes_by_kind.class" equals 1
    And the JSON output at "nodes_by_kind.function" equals 2
    And the file ".ananke/graph/metadata.json" exists

  @cap_harness_graph @cap_cli_ux
  Scenario: A missing workspace is a clean error with a stable code
    When I run:
      """
      python -c '
      from pathlib import Path
      from dev_guru import errors
      from dev_guru.client import connect
      try:
          connect().graph_summary(Path("no-such-dir"))
      except errors.GuruError as exc:
          print(exc.code)'
      """
    Then it succeeds
    And the output contains "WORKSPACE_INVALID"

  @cap_dex_optional
  Scenario: Using Dev Guru never imports Dex Trove
    When I run:
      """
      python -c '
      import sys
      from pathlib import Path
      from dev_guru.cli import app
      from dev_guru.client import connect
      connect().info()
      connect().graph_summary(Path("."))
      assert "dex_trove" not in sys.modules, "dex_trove was imported"
      print("dex-free")'
      """
    Then it succeeds
    And the output contains "dex-free"

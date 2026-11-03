Feature: The local gateway lets only this browser session reach the harness
  Background:
    Given an empty directory
    And the file "a.py" with content:
      """
      def one():
          return 1
      """
    And the file "probe.py" with content:
      """
      import http.client, json, re, subprocess, sys, time
      from urllib.parse import urlsplit
      server = subprocess.Popen(["dev", "serve", ".", "--no-open"], stdout=subprocess.PIPE, text=True)
      try:
          server.stdout.readline()
          login = urlsplit(server.stdout.readline().strip())
          assert login.hostname == "127.0.0.1", login
          def ask(method, path, headers=None, body=None):
              c = http.client.HTTPConnection("127.0.0.1", login.port, timeout=30)
              c.request(method, path, body=body, headers=headers or {})
              r = c.getresponse()
              return r.status, dict(r.getheaders()), r.read()
          print("no session:", ask("GET", "/api/v1/health")[0])
          status, headers, _ = ask("GET", login.path + "?" + login.query)
          cookie = headers["Set-Cookie"].split(";")[0]
          print("login:", status, "again:", ask("GET", login.path + "?" + login.query)[0])
          me = {"Cookie": cookie}
          print("rebound:", ask("GET", "/api/v1/health", {**me, "Host": "evil.example"})[0])
          print("page:", ask("GET", "/", me)[0])
          health = json.loads(ask("GET", "/api/v1/health", me)[2])
          print("compatible:", health["ok"])
          token = json.loads(ask("GET", "/api/v1/session", me)[2])["csrf_token"]
          workspace = json.loads(ask("GET", "/api/v1/workspaces", me)[2])["workspaces"][0]["id"]
          body = json.dumps({"workspace": workspace, "kind": "graph.build", "idempotency_key": "one"})
          json_type = {"Content-Type": "application/json"}
          print("no csrf:", ask("POST", "/api/v1/runs", {**me, **json_type, "Origin": f"http://127.0.0.1:{login.port}"}, body)[0])
          good = {**me, **json_type, "Origin": f"http://127.0.0.1:{login.port}", "X-Dev-Guru-CSRF": token}
          print("evil origin:", ask("POST", "/api/v1/runs", {**good, "Origin": "https://evil.example"}, body)[0])
          status, _, data = ask("POST", "/api/v1/runs", good, body)
          run = json.loads(data)
          print("started:", status)
          for _ in range(200):
              state = json.loads(ask("GET", f"/api/v1/runs/{run['run_id']}?workspace={workspace}", me)[2])["state"]
              if state in ("succeeded", "failed", "cancelled"):
                  break
              time.sleep(0.1)
          print("run:", state)
      finally:
          server.terminate()
          server.wait(10)
      """
    And I have run "git init -q . && git add a.py && git -c user.name=t -c user.email=t@example.com commit -qm i"

  @cap_gateway @adversarial
  Scenario: Only the printed link gets in, other origins are refused, and a run reaches real Ananke
    When I run "dev serve --help"
    Then it succeeds
    When I run "python3 probe.py"
    Then it succeeds
    And the output contains each of:
      """
      no session: 401
      login: 303 again: 401
      rebound: 403
      page: 200
      compatible: True
      no csrf: 403
      evil origin: 403
      started: 202
      run: succeeded
      """
    And the output does not contain "Traceback"

  @cap_gateway @adversarial
  Scenario: A workspace that isn't there stops the gateway from starting
    When I run "dev serve ./missing --no-open"
    Then the exit code is 2
    And the output contains "WORKSPACE_INVALID"

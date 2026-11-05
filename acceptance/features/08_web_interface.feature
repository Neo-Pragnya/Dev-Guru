Feature: The web interface is complete in what ships, and the run console holds up in a real browser

  @cap_web_shell
  Scenario: The interface's files come from the installed package, with no Node anywhere
    Given an empty directory
    And the file "a.py" with content:
      """
      def one():
          return 1
      """
    And the file "probe.py" with content:
      """
      import http.client, json, os, re, shutil, subprocess, tempfile
      from importlib import resources
      from urllib.parse import urlsplit
      # a PATH holding only git: nothing started from here can find Node
      bare = tempfile.mkdtemp()
      os.symlink(shutil.which("git"), os.path.join(bare, "git"))
      print("node found:", shutil.which("node", path=bare))
      server = subprocess.Popen([shutil.which("dev"), "serve", ".", "--no-open"], stdout=subprocess.PIPE, text=True, env={**os.environ, "PATH": bare})
      try:
          server.stdout.readline()
          login = urlsplit(server.stdout.readline().strip())
          def ask(path, cookie=""):
              c = http.client.HTTPConnection("127.0.0.1", login.port, timeout=30)
              c.request("GET", path, headers={"Cookie": cookie} if cookie else {})
              r = c.getresponse()
              return r.status, dict(r.getheaders()), r.read()
          _, headers, _ = ask(login.path + "?" + login.query)
          me = headers["Set-Cookie"].split(";")[0]
          _, _, page = ask("/", me)
          static = resources.files("dev_guru.gateway").joinpath("static")
          assert page == static.joinpath("index.html").read_bytes()
          linked = sorted(set(re.findall(r'(?:src|href)="(/[^"]+)"', page.decode())))
          print("linked:", " ".join(linked))
          for path in linked:
              status, headers, body = ask(path, me)
              same = body == static.joinpath(path.lstrip("/")).read_bytes()
              print(f"{path}: {status} {headers['Content-Type'].split(';')[0]} same={same}")
          health = json.loads(ask("/api/v1/health", me)[2])
          print("compatible:", health["ok"])
      finally:
          server.terminate()
          server.wait(10)
      """
    And I have run "git init -q . && git add a.py && git -c user.name=t -c user.email=t@example.com commit -qm i"
    When I run "python3 probe.py"
    Then it succeeds
    And the output contains each of:
      """
      node found: None
      linked: /app.css /app.js /favicon.svg
      /app.css: 200 text/css same=True
      /app.js: 200 text/javascript same=True
      /favicon.svg: 200 image/svg+xml same=True
      compatible: True
      """

  @cap_web_shell
  Scenario: The commands the "not in this version" pages recommend really exist
    Given an empty directory
    When I run "ananke app workflow-preview --help && ananke app workflow-run --help && dev explore --help && dev present --help && dev diagram --help && dev learning review --help"
    Then it succeeds

  @cap_web_shell @cap_run_console @adversarial
  Scenario: Every journey passes in real Chrome on a fresh workspace
    Given an empty directory
    When I run "node $REPO/acceptance/browser/web_journeys.mjs"
    Then it succeeds
    And the output contains each of:
      """
      with no graph yet, Code says so
      reloading while a run is going keeps the run
      events the harness no longer keeps are named as a gap
      losing the connection shows it
      a hostile file name stays text
      journeys passed
      """
    And it finishes within 280 seconds

  @cap_web_shell
  Scenario: The repository views draw a real repository correctly, in real Chrome
    Given an empty directory
    When I run "node $REPO/acceptance/browser/insight_journeys.mjs"
    Then it succeeds
    And the output contains each of:
      """
      a flow runs from the frontend call, through the route, to the tables
      no ERD line runs through a table
      the architecture is drawn from the inferred model
      CVEs say they haven't been checked
      journeys passed
      """


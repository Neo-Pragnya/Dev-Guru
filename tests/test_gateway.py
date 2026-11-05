"""The gateway over real HTTP on a real socket, driving the real Ananke harness."""

from __future__ import annotations

import http.client
import json
import re
import socket
import struct
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

from dev_guru import errors
from dev_guru.client import connect
from dev_guru.gateway import Gateway
from dev_guru.gateway.server import CSRF_HEADER, HOST, MAX_BODY_BYTES


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("def one():\n    return 1\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "commit",
            "-qm",
            "i",
        ],
        check=True,
    )
    return root


@pytest.fixture
def gateway(repo: Path) -> Iterator[Gateway]:
    g = Gateway([repo], connect("in-process"))
    thread = threading.Thread(target=g.serve_forever, daemon=True)
    thread.start()
    yield g
    g.shutdown()


class Browser:
    """Sends exactly the headers a browser would, so each test can take one away."""

    def __init__(self, gateway: Gateway) -> None:
        self.g = gateway
        self.origin = f"http://{HOST}:{gateway.port}"
        self.cookie = ""
        self.workspace = next(iter(gateway.roots))

    def raw(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPConnection(HOST, self.g.port, timeout=30)
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        sent = {"Host": f"{HOST}:{self.g.port}", **(headers or {})}
        if self.cookie and "Cookie" not in sent:
            sent["Cookie"] = self.cookie
        if body is not None:
            sent["Content-Length"] = str(len(body))
        for name, value in sent.items():
            if value:
                conn.putheader(name, value)
        conn.endheaders(body)
        response = conn.getresponse()
        data = response.read()
        result = (response.status, {k.lower(): v for k, v in response.getheaders()}, data)
        conn.close()
        return result

    def login(self) -> Browser:
        split = urlsplit(self.g.login_url)
        status, headers, _ = self.raw("GET", f"{split.path}?{split.query}")
        assert status == 303 and headers["location"] == "/"
        self.cookie = headers["set-cookie"].split(";")[0]
        return self

    def get(self, path: str) -> tuple[int, Any]:
        sep = "&" if "?" in path else "?"
        status, _, data = self.raw("GET", f"{path}{sep}workspace={self.workspace}")
        return status, json.loads(data)

    def post(self, path: str, payload: dict[str, Any], **headers: str) -> tuple[int, Any]:
        sent = {
            "Origin": self.origin,
            "Content-Type": "application/json",
            CSRF_HEADER: self.g.csrf,
            **{k.replace("_", "-"): v for k, v in headers.items()},
        }
        body = json.dumps({"workspace": self.workspace, **payload}).encode()
        status, _, data = self.raw("POST", path, headers=sent, body=body)
        return status, json.loads(data)

    def finish(self, run_id: str) -> dict[str, Any]:
        for _ in range(300):
            status, run = self.get(f"/api/v1/runs/{run_id}")
            assert status == 200
            if run["state"] in ("succeeded", "failed", "cancelled"):
                return run
            time.sleep(0.05)
        raise AssertionError("the run didn't finish")


@pytest.fixture
def browser(gateway: Gateway) -> Browser:
    return Browser(gateway).login()


def code(response: tuple[int, Any]) -> str:
    return str(response[1]["error"]["code"])


# ------------------------------------------------------------------ who gets in
def test_it_listens_on_loopback_only(gateway: Gateway) -> None:
    assert gateway._server.server_address[0] == "127.0.0.1"


def test_the_login_link_works_once_and_leaves_the_url(gateway: Gateway) -> None:
    b = Browser(gateway)
    split = urlsplit(gateway.login_url)
    target = f"{split.path}?{split.query}"
    assert b.raw("GET", target)[0] == 303
    assert b.raw("GET", target)[0] == 401


def test_the_session_cookie_is_strict(gateway: Gateway) -> None:
    b = Browser(gateway)
    split = urlsplit(gateway.login_url)
    cookie = b.raw("GET", f"{split.path}?{split.query}")[1]["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert f"dev_guru_session_{gateway.port}=" in cookie


@pytest.mark.parametrize("path", ["/", "/api/v1/health", "/api/v1/session", "/api/v1/workspaces"])
def test_nothing_is_served_without_a_session(gateway: Gateway, path: str) -> None:
    assert Browser(gateway).raw("GET", path)[0] == 401


def test_a_wrong_token_and_a_wrong_cookie_get_nothing(gateway: Gateway) -> None:
    b = Browser(gateway)
    assert b.raw("GET", "/login?token=guess")[0] == 401
    b.cookie = f"{gateway.cookie_name}=guess"
    assert b.raw("GET", "/api/v1/health")[0] == 401
    b.cookie = "not a ; valid = cookie;;"
    assert b.raw("GET", "/api/v1/health")[0] == 401


@pytest.mark.parametrize(
    "host", ["evil.example", "evil.example:80", "127.0.0.1", "localhost:1", ""]
)
def test_a_rebound_host_is_refused_even_with_a_session(browser: Browser, host: str) -> None:
    status, _, data = browser.raw("GET", "/api/v1/health", headers={"Host": host})
    assert status == 403 and json.loads(data)["error"]["code"] == "HOST_REJECTED"


def test_localhost_is_accepted_as_the_same_server(browser: Browser, gateway: Gateway) -> None:
    host = f"localhost:{gateway.port}"
    assert browser.raw("GET", "/api/v1/health", headers={"Host": host})[0] == 200


# ------------------------------------------------------------------ a page on another site
def test_a_change_needs_origin_csrf_and_json(browser: Browser) -> None:
    payload = {"kind": "graph.build", "idempotency_key": "k"}
    path = "/api/v1/runs"
    assert code(browser.post(path, payload, Origin="https://evil.example")) == "ORIGIN_REJECTED"
    assert code(browser.post(path, payload, Origin="")) == "ORIGIN_REJECTED"
    assert code(browser.post(path, payload, Sec_Fetch_Site="cross-site")) == "ORIGIN_REJECTED"
    assert (
        code(browser.post(path, payload, **{CSRF_HEADER.replace("-", "_"): ""})) == "CSRF_REJECTED"
    )
    assert (
        code(browser.post(path, payload, **{CSRF_HEADER.replace("-", "_"): "guess"}))
        == "CSRF_REJECTED"
    )
    assert code(browser.post(path, payload, Content_Type="text/plain")) == "UNSUPPORTED_MEDIA_TYPE"
    assert (
        code(browser.post(path, payload, Content_Type="application/x-www-form-urlencoded"))
        == "UNSUPPORTED_MEDIA_TYPE"
    )
    assert not (Path(browser.g.roots[browser.workspace]) / ".ananke" / "app" / "runs").exists()


def test_a_read_from_another_origin_is_refused_and_never_gets_cors(browser: Browser) -> None:
    status, headers, _ = browser.raw(
        "GET", "/api/v1/health", headers={"Origin": "https://evil.example"}
    )
    assert status == 403 and "access-control-allow-origin" not in headers
    status, headers, _ = browser.raw("OPTIONS", "/api/v1/runs", headers={"Origin": browser.origin})
    assert status == 405 and "access-control-allow-origin" not in headers
    status, headers, _ = browser.raw("GET", "/api/v1/health", headers={"Origin": browser.origin})
    assert status == 200 and "access-control-allow-origin" not in headers


def test_responses_carry_security_headers(browser: Browser) -> None:
    _, headers, _ = browser.raw("GET", "/")
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in headers["content-security-policy"]


@pytest.mark.parametrize(
    ("body", "expected", "status"),
    [(b"not json", "INVALID_JSON", 400), (b"[1, 2]", "INVALID_JSON", 400)],
)
def test_a_bad_body_is_refused(browser: Browser, body: bytes, expected: str, status: int) -> None:
    sent = {
        "Origin": browser.origin,
        "Content-Type": "application/json",
        CSRF_HEADER: browser.g.csrf,
    }
    got, _, data = browser.raw("POST", "/api/v1/runs", headers=sent, body=body)
    assert got == status and json.loads(data)["error"]["code"] == expected


def test_an_oversized_body_is_refused_without_reading_it(browser: Browser) -> None:
    sent = {
        "Origin": browser.origin,
        "Content-Type": "application/json",
        CSRF_HEADER: browser.g.csrf,
        "Content-Length": str(MAX_BODY_BYTES + 1),
    }
    got, _, data = browser.raw("POST", "/api/v1/runs", headers=sent)
    assert got == 413 and json.loads(data)["error"]["code"] == "TOO_LARGE"


# ------------------------------------------------------------------ scope
def test_a_workspace_is_an_id_and_a_path_reaches_nothing(browser: Browser, tmp_path: Path) -> None:
    status, listed = browser.get("/api/v1/workspaces")
    assert status == 200 and [w["id"] for w in listed["workspaces"]] == [browser.workspace]
    for attempt in (str(tmp_path), "..", "../..", "/etc", "nope"):
        browser.workspace = attempt
        assert code(browser.get("/api/v1/code")) == "WORKSPACE_NOT_FOUND"
        assert (
            code(browser.post("/api/v1/runs", {"kind": "graph.build", "idempotency_key": "x"}))
            == "WORKSPACE_NOT_FOUND"
        )


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/runs/..%2F..%2Fsecrets",
        "/api/v1/runs/run-abc/artifacts/..%2F..%2Frun.json",
        "/api/v1/runs/run-abc/artifacts/.env",
        "/api/v1/shell",
        "/api/v1/exec",
        "/static/../../etc/passwd",
    ],
)
def test_odd_paths_reach_nothing(browser: Browser, path: str) -> None:
    assert browser.get(path)[0] == 404


def test_no_route_runs_a_command(browser: Browser) -> None:
    status, run = browser.post(
        "/api/v1/runs",
        {"kind": "shell", "parameters": {"command": "touch pwned"}, "idempotency_key": "x"},
    )
    assert status == 400 and run["error"]["code"] == "UNKNOWN_RUN_KIND"
    assert not (browser.g.roots[browser.workspace] / "pwned").exists()


def test_an_unknown_workspace_at_start_is_refused(tmp_path: Path) -> None:
    with pytest.raises(errors.GuruError):
        Gateway([tmp_path / "missing"], connect("in-process"))
    with pytest.raises(errors.GuruError):
        Gateway([], connect("in-process"))


# ------------------------------------------------------------------ the real harness behind it
def test_a_run_goes_through_the_harness_with_events_and_artifacts(browser: Browser) -> None:
    status, run = browser.post("/api/v1/runs", {"kind": "graph.build", "idempotency_key": "one"})
    assert status == 202 and run["state"] in ("queued", "running", "succeeded")
    done = browser.finish(run["run_id"])
    assert done["state"] == "succeeded"

    status, seen = browser.get(f"/api/v1/runs/{run['run_id']}/events")
    types = [e["type"] for e in seen["events"]]
    assert types[0] == "run.queued" and types[-1] == "run.succeeded"
    status, later = browser.get(
        f"/api/v1/runs/{run['run_id']}/events?after={seen['events'][-1]['seq']}"
    )
    assert later["events"] == []

    _, listed = browser.get(f"/api/v1/runs/{run['run_id']}/artifacts")
    assert [a["name"] for a in listed["artifacts"]] == ["graph-snapshot.json"]
    status, headers, data = browser.raw(
        "GET",
        f"/api/v1/runs/{run['run_id']}/artifacts/graph-snapshot.json?workspace={browser.workspace}",
    )
    assert status == 200 and json.loads(data)["nodes"]
    assert headers["content-disposition"].startswith("attachment")
    assert headers["content-type"] == "application/octet-stream"
    assert "sandbox" in headers["content-security-policy"]

    status, view = browser.get("/api/v1/code?collapse=file&budget=5")
    assert status == 200 and view["collapse"] == "file"


def test_a_reloaded_tab_and_a_second_tab_see_the_same_run(
    browser: Browser, gateway: Gateway
) -> None:
    _, run = browser.post("/api/v1/runs", {"kind": "graph.build", "idempotency_key": "same"})
    _, again = browser.post("/api/v1/runs", {"kind": "graph.build", "idempotency_key": "same"})
    assert again["run_id"] == run["run_id"]
    assert browser.finish(run["run_id"])["state"] == "succeeded"
    second = Browser(gateway)
    second.cookie = browser.cookie
    assert second.finish(run["run_id"])["state"] == "succeeded"


def test_what_ananke_refuses_keeps_its_code_and_a_fitting_status(browser: Browser) -> None:
    assert code(browser.get("/api/v1/runs/run-0123")) == "RUN_NOT_FOUND"
    assert browser.get("/api/v1/runs/run-0123")[0] == 404
    status, body = browser.get("/api/v1/code")
    assert status == 503 and body["error"]["code"] == "GRAPH_MISSING" and body["error"]["retryable"]
    assert code(browser.get("/api/v1/code?budget=x")) == "INVALID_REQUEST"
    browser.post("/api/v1/runs", {"kind": "graph.build", "idempotency_key": "k"})
    status, conflict = browser.post(
        "/api/v1/runs",
        {"kind": "graph.impact", "parameters": {"changed_files": ["a.py"]}, "idempotency_key": "k"},
    )
    assert status == 409 and conflict["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_a_cancelled_run_stays_cancelled(browser: Browser, monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()
    original = browser.g.drive
    monkeypatch.setattr(
        browser.g, "drive", lambda root, run_id: (release.wait(10), original(root, run_id))
    )
    _, run = browser.post("/api/v1/runs", {"kind": "graph.build", "idempotency_key": "c"})
    status, cancelled = browser.post(f"/api/v1/runs/{run['run_id']}/cancel", {})
    assert status == 200 and cancelled["state"] == "cancelled"
    release.set()
    time.sleep(0.2)
    assert browser.get(f"/api/v1/runs/{run['run_id']}")[1]["state"] == "cancelled"


def test_a_workflow_previews_and_runs_through_the_gateway(browser: Browser) -> None:
    root = browser.g.roots[browser.workspace]
    skill = root / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: demo\ndescription: A demo skill for the gateway test.\nversion: 1.0.0\n---\n# Demo\nSay ping.\n"
    )
    from ananke.plexus.registry.registry import Registry

    Registry.for_project(root, create=True).learn(str(skill), namespace="local")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "commit",
            "-qm",
            "s",
        ],
        check=True,
    )
    draft = {
        "schema_version": "1.0.0",
        "workflow_id": "demo/one",
        "nodes": [
            {
                "id": "a",
                "capability_ref": "local/demo@1.0.0",
                "kind": "skill",
                "inputs": [],
                "outputs": [],
            }
        ],
        "edges": [],
    }
    status, preview = browser.post("/api/v1/plans/prepare", {"draft": draft})
    assert status == 200 and preview["ok"]
    _, run = browser.post(
        "/api/v1/runs",
        {
            "kind": "workflow.run",
            "parameters": {"draft": draft, "backend": "fake", "plan_hash": preview["plan_hash"]},
            "idempotency_key": "w",
        },
    )
    done = browser.finish(run["run_id"])
    assert done["state"] == "succeeded" and done["complete"] is False
    assert {w["code"] for w in done["warnings"]} == {"SIMULATED_BACKEND"}


def test_an_unexpected_error_tells_the_browser_nothing_internal(
    browser: Browser, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_: object, **__: object) -> None:
        raise RuntimeError("secret path /home/me/.env")

    monkeypatch.setattr(browser.g.client, "get_run", boom)
    status, _, data = browser.raw("GET", f"/api/v1/runs/run-1?workspace={browser.workspace}")
    assert status == 500 and b"secret" not in data and b"INTERNAL_ERROR" in data


def test_a_browser_dropping_a_connection_prints_nothing(
    gateway: Gateway, capfd: pytest.CaptureFixture[str]
) -> None:
    conn = socket.create_connection((HOST, gateway.port))
    conn.setsockopt(
        socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)
    )  # close with a reset
    conn.send(b"GET ")
    conn.close()
    time.sleep(0.3)
    assert "Traceback" not in capfd.readouterr().err


@pytest.mark.parametrize(
    ("path", "media"),
    [
        ("/", "text/html"),
        ("/app.js", "text/javascript"),
        ("/app.css", "text/css"),
        ("/favicon.svg", "image/svg+xml"),
    ],
)
def test_the_interface_files_need_a_session_and_have_the_right_type(
    browser: Browser, gateway: Gateway, path: str, media: str
) -> None:
    assert Browser(gateway).raw("GET", path)[0] == 401
    status, headers, body = browser.raw("GET", path)
    assert status == 200 and headers["content-type"].startswith(media) and body


@pytest.mark.parametrize(
    "path", ["/index.html", "/static/app.js", "/../server.py", "/app.js/../../server.py"]
)
def test_only_listed_files_are_served(browser: Browser, path: str) -> None:
    assert browser.raw("GET", path)[0] == 404


def test_the_page_has_no_inline_code_for_the_content_policy_to_block(browser: Browser) -> None:
    _, _, page = browser.raw("GET", "/")
    text = page.decode()
    assert "<style" not in text and " onclick" not in text
    assert all('src="' in tag for tag in text.split("<script")[1:])


# ------------------------------------------------------------------ every route, not just the first ones written
GET_ROUTES = [
    "/",
    "/app.js",
    "/app.css",
    "/favicon.svg",
    "/api/v1/session",
    "/api/v1/health",
    "/api/v1/workspaces",
    "/api/v1/capabilities?workspace=W",
    "/api/v1/sources?workspace=W",
    "/api/v1/code?workspace=W",
    "/api/v1/runs?workspace=W",
    "/api/v1/runs/run-0123?workspace=W",
    "/api/v1/runs/run-0123/events?workspace=W",
    "/api/v1/runs/run-0123/artifacts?workspace=W",
    "/api/v1/runs/run-0123/artifacts/graph-snapshot.json?workspace=W",
]
POST_ROUTES = ["/api/v1/plans/prepare", "/api/v1/runs", "/api/v1/runs/run-0123/cancel"]


@pytest.mark.parametrize("path", GET_ROUTES)
def test_every_read_needs_a_session_and_refuses_other_sites(
    browser: Browser, gateway: Gateway, path: str
) -> None:
    target = path.replace("W", browser.workspace)
    assert Browser(gateway).raw("GET", target)[0] == 401
    for headers in ({"Origin": "https://evil.example"}, {"Sec-Fetch-Site": "cross-site"}):
        status, sent, data = browser.raw("GET", target, headers=headers)
        assert status == 403 and json.loads(data)["error"]["code"] == "ORIGIN_REJECTED"
        assert "access-control-allow-origin" not in sent


@pytest.mark.parametrize("path", POST_ROUTES)
def test_every_change_needs_session_origin_csrf_and_json(
    browser: Browser, gateway: Gateway, path: str
) -> None:
    body = json.dumps({"workspace": browser.workspace}).encode()
    good = {"Origin": browser.origin, "Content-Type": "application/json", CSRF_HEADER: gateway.csrf}
    for change, expected in (
        ({"Origin": ""}, "ORIGIN_REJECTED"),
        ({"Origin": "https://evil.example"}, "ORIGIN_REJECTED"),
        ({"Origin": "null"}, "ORIGIN_REJECTED"),
        ({"Sec-Fetch-Site": "same-site"}, "ORIGIN_REJECTED"),
        ({CSRF_HEADER: ""}, "CSRF_REJECTED"),
        ({CSRF_HEADER: "guess"}, "CSRF_REJECTED"),
        ({"Content-Type": "text/plain"}, "UNSUPPORTED_MEDIA_TYPE"),
    ):
        status, _, data = browser.raw("POST", path, headers={**good, **change}, body=body)
        assert status >= 400 and json.loads(data)["error"]["code"] == expected, change
    assert Browser(gateway).raw("POST", path, headers=good, body=body)[0] == 401
    assert not (browser.g.roots[browser.workspace] / ".ananke" / "app" / "runs").exists()


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "TRACE"])
def test_other_methods_are_refused_with_no_cors(browser: Browser, method: str) -> None:
    status, headers, _ = browser.raw(method, "/api/v1/runs", headers={"Origin": browser.origin})
    assert status == 405 and "access-control-allow-origin" not in headers


@pytest.mark.parametrize(
    ("change", "status", "expected"),
    [
        ({"Cookie": "dev_guru_session_PORT=caf\xe9"}, 401, "NOT_AUTHENTICATED"),
        ({CSRF_HEADER: "caf\xe9"}, 403, "CSRF_REJECTED"),
    ],
)
def test_text_that_isnt_ascii_is_a_refusal_not_a_crash(
    browser: Browser, gateway: Gateway, change: dict[str, str], status: int, expected: str
) -> None:
    sent = {
        "Origin": browser.origin,
        "Content-Type": "application/json",
        CSRF_HEADER: gateway.csrf,
        "Cookie": browser.cookie,
        **{k: v.replace("PORT", str(gateway.port)) for k, v in change.items()},
    }
    body = json.dumps({"workspace": browser.workspace}).encode()
    got, _, data = browser.raw("POST", "/api/v1/runs", headers=sent, body=body)
    assert got == status and json.loads(data)["error"]["code"] == expected


def test_a_login_token_that_isnt_ascii_is_a_refusal_not_a_crash(gateway: Gateway) -> None:
    status, _, data = Browser(gateway).raw("GET", "/login?token=caf%C3%A9")
    assert status == 401 and json.loads(data)["error"]["code"] == "NOT_AUTHENTICATED"


def test_the_content_policy_is_strict_on_everything_served(
    browser: Browser, gateway: Gateway
) -> None:
    answers = [browser.raw("GET", path.replace("W", browser.workspace)) for path in GET_ROUTES[:9]]
    answers.append(Browser(gateway).raw("GET", "/"))  # a refusal
    answers.append(browser.raw("GET", "/nope"))
    for _, headers, _ in answers:
        policy = headers["content-security-policy"]
        assert "default-src 'self'" in policy and "frame-ancestors 'none'" in policy
        assert "base-uri 'none'" in policy and "unsafe" not in policy and "*" not in policy
        assert headers["x-content-type-options"] == "nosniff"


# ------------------------------------------------------------------ what the page does with server text
STATIC = Path(__file__).parents[1] / "src" / "dev_guru" / "gateway" / "static"


def test_server_text_has_no_way_to_become_markup() -> None:
    script = (STATIC / "app.js").read_text()
    for sink in (
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "document.write",
        "eval(",
        "new Function",
        "srcdoc",
        'setAttribute("on',
    ):
        assert sink not in script, sink


def test_every_link_the_page_builds_starts_somewhere_fixed() -> None:
    script = (STATIC / "app.js").read_text()
    hrefs = re.findall(r"\bhref:\s*([^,}]+)", script)
    assert len(hrefs) >= 4
    for value in hrefs:
        assert value.startswith(('"#/', "`#/", "scoped(`/api/v1/")), value
    assert ".href =" not in script and 'setAttribute("href"' not in script
    assert 'if (key === "href" && !LINK.test(value))' in script
    assert "const LINK = /^(#\\/|\\/api\\/v1\\/)/;" in script


def test_the_page_loads_only_this_gateways_files() -> None:
    page = (STATIC / "index.html").read_text()
    assert "http://" not in page and "https://" not in page and "//" not in page.replace("<!--", "")
    assert set(re.findall(r'(?:src|href)="(/[^"]*)"', page)) == {
        "/favicon.svg",
        "/app.css",
        "/map.css",
        "/insights.css",
        "/app.js",
        "/map.js",
        "/insights.js",
        "/studio.js",
    }
    for name in ("app.js", "app.css", "favicon.svg"):
        text = (STATIC / name).read_text()
        assert "http://" not in text.replace("http://www.w3.org/2000/svg", "")
        assert "https://" not in text and "@import" not in text


# ------------------------------------------------------------------ the run console's API
def test_run_history_lists_runs_newest_first(browser: Browser) -> None:
    assert browser.get("/api/v1/runs")[1] == {"total": 0, "runs": []}
    _, one = browser.post("/api/v1/runs", {"kind": "graph.build", "idempotency_key": "one"})
    browser.finish(one["run_id"])
    _, two = browser.post("/api/v1/runs", {"kind": "graph.build", "idempotency_key": "two"})
    browser.finish(two["run_id"])
    status, history = browser.get("/api/v1/runs")
    assert status == 200 and history["total"] == 2
    assert {r["run_id"] for r in history["runs"]} == {one["run_id"], two["run_id"]}
    assert history["runs"][0]["created_at"] >= history["runs"][1]["created_at"]


def test_events_dropped_from_the_record_come_back_as_a_gap_with_the_run(browser: Browser) -> None:
    _, run = browser.post("/api/v1/runs", {"kind": "graph.build", "idempotency_key": "g"})
    browser.finish(run["run_id"])
    log = (
        browser.g.roots[browser.workspace]
        / ".ananke"
        / "app"
        / "runs"
        / run["run_id"]
        / "events.jsonl"
    )
    lines = log.read_text().splitlines()
    log.write_text("\n".join(lines[2:]) + "\n")
    status, seen = browser.get(f"/api/v1/runs/{run['run_id']}/events")
    assert status == 200 and seen["gap"] == {"from": 1, "to": 2}
    assert seen["run"]["state"] == "succeeded" and seen["events"][-1]["type"] == "run.succeeded"
    last = seen["events"][-1]["seq"]
    assert "gap" not in browser.get(f"/api/v1/runs/{run['run_id']}/events?after={last}")[1]

"""A loopback HTTP gateway from one browser session to the Ananke client port.

It holds no domain logic: Ananke compiles, authorizes, runs and records. The gateway's job is to make sure the caller
is this user's browser session, because any web page the user visits can send requests to a local port:

- it binds to the loopback address only, with no option to change that;
- ``Host`` must name this server, which stops DNS rebinding;
- a single-use token from the terminal is exchanged for a session cookie, then scrubbed from the URL;
- requests that change anything also need a same-origin ``Origin``, a CSRF token and a JSON body;
- there are no CORS headers, so other origins can't read a response;
- browsers name a workspace by opaque id, so no request can reach a path outside the roots given at start;
- no route accepts a command or a path to run.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from dev_guru import errors
from dev_guru.client.port import AnankeClient
from dev_guru.gateway import documents
from dev_guru.version import __version__

HOST = "127.0.0.1"
MAX_BODY_BYTES = 2_000_000
RUN_WORKERS = 2
CSRF_HEADER = "X-Dev-Guru-CSRF"
# A fixed list, so no request path ever becomes a file path.
_STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/map.js": ("map.js", "text/javascript; charset=utf-8"),
    "/map.css": ("map.css", "text/css; charset=utf-8"),
    "/insights.css": ("insights.css", "text/css; charset=utf-8"),
    "/lantern.css": ("lantern.css", "text/css; charset=utf-8"),
    "/lantern.js": ("lantern.js", "text/javascript; charset=utf-8"),
    "/insights.js": ("insights.js", "text/javascript; charset=utf-8"),
    "/studio.js": ("studio.js", "text/javascript; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}
_RUN_ID = r"run-[0-9a-f]+"
_ARTIFACT = r"[A-Za-z0-9_][A-Za-z0-9_.-]*"
# The status for what Ananke refuses; anything retryable is 503, and anything else here is 400.
_REFUSAL_STATUS = {
    "RUN_NOT_FOUND": 404,
    "ARTIFACT_NOT_FOUND": 404,
    "SOURCE_NOT_FOUND": 404,
    "IDEMPOTENCY_CONFLICT": 409,
    "STALE_PLAN": 409,
    "DIGEST_MISMATCH": 409,
}


def _same(sent: str, secret: str) -> bool:
    """Compare in constant time. As bytes, because ``compare_digest`` raises on text that isn't ASCII."""
    return hmac.compare_digest(sent.encode("utf-8", "replace"), secret.encode())


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        """A browser dropping a connection is normal, and shouldn't print a stack trace in the user's terminal."""
        if not isinstance(sys.exc_info()[1], ConnectionError):
            super().handle_error(request, client_address)


class _Reject(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class Gateway:
    def __init__(self, roots: list[Path], client: AnankeClient, *, port: int = 0) -> None:
        if not roots:
            raise errors.GuruError(errors.INVALID_INPUT, "the gateway needs at least one workspace")
        self.client = client
        self.roots: dict[str, Path] = {}
        for root in roots:
            resolved = root.expanduser().resolve()
            if not resolved.is_dir():
                raise errors.GuruError(errors.WORKSPACE_INVALID, f"{resolved} is not a directory")
            self.roots[hashlib.sha256(str(resolved).encode()).hexdigest()[:12]] = resolved
        self._session = secrets.token_urlsafe(32)
        self._login_token: str | None = secrets.token_urlsafe(32)
        self._login_lock = threading.Lock()
        self.csrf = hmac.new(self._session.encode(), b"csrf", hashlib.sha256).hexdigest()
        self._server = _Server((HOST, port), _handler_for(self))
        self.port = int(self._server.server_address[1])
        self.cookie_name = f"dev_guru_session_{self.port}"  # cookies aren't separated by port
        self.origins = {f"http://{HOST}:{self.port}", f"http://localhost:{self.port}"}
        self.hosts = {f"{HOST}:{self.port}", f"localhost:{self.port}"}
        self.runs = ThreadPoolExecutor(max_workers=RUN_WORKERS, thread_name_prefix="dev-guru-run")

    @property
    def login_url(self) -> str:
        return f"http://{HOST}:{self.port}/login?token={self._login_token}"

    def redeem(self, token: str) -> bool:
        """The login token works once. A link left in a history or a terminal log opens nothing later."""
        with self._login_lock:
            if self._login_token and _same(token, self._login_token):
                self._login_token = None
                return True
        return False

    def is_session(self, value: str) -> bool:
        return _same(value, self._session)

    def session_cookie(self) -> str:
        return f"{self.cookie_name}={self._session}; HttpOnly; SameSite=Strict; Path=/"

    def serve_forever(self) -> None:
        self._server.serve_forever()

    def shutdown(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self.runs.shutdown(wait=True)

    def workspace(self, workspace_id: object) -> Path:
        root = self.roots.get(str(workspace_id))
        if root is None:
            raise _Reject(404, "WORKSPACE_NOT_FOUND", "no such workspace: see /api/v1/workspaces")
        return root

    def drive(self, root: Path, run_id: str) -> None:
        try:
            self.client.drive_run(root, run_id)
        except (
            Exception
        ):  # the harness records failures on the run itself; this thread has nowhere to report
            return


def _handler_for(gateway: Gateway) -> type[BaseHTTPRequestHandler]:
    class Handler(_Handler):
        pass

    Handler.gateway = gateway
    return Handler


class _Handler(BaseHTTPRequestHandler):
    gateway: Gateway
    server_version = "DevGuruGateway"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        """Silent: a request line can carry the login token."""

    # ------------------------------------------------------------------ responses
    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )

    def _send(self, status: int, body: bytes, media_type: str, *extra: tuple[str, str]) -> None:
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        for name, value in extra:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: object, status: int = 200) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    def _error(self, status: int, code: str, message: str, *, retryable: bool = False) -> None:
        self.close_connection = True  # an unread body mustn't be parsed as the next request
        self._json(
            {"ok": False, "error": {"code": code, "message": message, "retryable": retryable}},
            status,
        )

    # ------------------------------------------------------------------ checks
    def _check_host(self) -> None:
        if self.headers.get("Host", "") not in self.gateway.hosts:
            raise _Reject(403, "HOST_REJECTED", "this request isn't addressed to this gateway")

    def _check_origin(self, *, required: bool) -> None:
        origin = self.headers.get("Origin")
        if origin is None:
            if required:
                raise _Reject(403, "ORIGIN_REJECTED", "a change needs a same-origin Origin header")
        elif origin not in self.gateway.origins:
            raise _Reject(403, "ORIGIN_REJECTED", "requests from other origins aren't accepted")
        if self.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"):
            raise _Reject(403, "ORIGIN_REJECTED", "requests from other sites aren't accepted")

    def _has_session(self) -> bool:
        try:
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
        except CookieError:
            return False
        morsel = cookies.get(self.gateway.cookie_name)
        return morsel is not None and self.gateway.is_session(morsel.value)

    def _check_session(self) -> None:
        if not self._has_session():
            raise _Reject(401, "NOT_AUTHENTICATED", "open the link `dev serve` printed")

    def _check_csrf(self) -> None:
        sent = self.headers.get(CSRF_HEADER, "")
        if not _same(sent, self.gateway.csrf):
            raise _Reject(403, "CSRF_REJECTED", f"a change needs the {CSRF_HEADER} header")

    def _read_json(self) -> dict[str, Any]:
        if self.headers.get_content_type() != "application/json":
            raise _Reject(415, "UNSUPPORTED_MEDIA_TYPE", "send application/json")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise _Reject(411, "LENGTH_REQUIRED", "send a Content-Length") from None
        if not 0 <= length <= MAX_BODY_BYTES:
            raise _Reject(413, "TOO_LARGE", f"a request may be at most {MAX_BODY_BYTES} bytes")
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            raise _Reject(400, "INVALID_JSON", "the body isn't valid JSON") from None
        if not isinstance(body, dict):
            raise _Reject(400, "INVALID_JSON", "the body must be a JSON object")
        return body

    # ------------------------------------------------------------------ dispatch
    def _guarded(self, work: Any) -> None:
        try:
            self._check_host()
            work()
        except _Reject as exc:
            self._error(exc.status, exc.code, exc.message)
        except errors.HarnessRefused as exc:
            status = 503 if exc.retryable else _REFUSAL_STATUS.get(exc.harness_code, 400)
            self._error(status, exc.harness_code, exc.message, retryable=exc.retryable)
        except errors.GuruError as exc:
            self._error(503, exc.code, exc.message)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception:  # never hand internals to a browser
            self._error(500, "INTERNAL_ERROR", "the gateway hit an unexpected error")

    def do_GET(self) -> None:
        self._guarded(self._get)

    def do_POST(self) -> None:
        self._guarded(self._post)

    def _refuse_method(self) -> None:
        self._guarded(lambda: self._error(405, "METHOD_NOT_ALLOWED", "use GET or POST"))

    do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_HEAD = do_TRACE = _refuse_method

    def _get(self) -> None:
        url = urlsplit(self.path)
        query = {k: v[-1] for k, v in parse_qs(url.query).items()}
        if url.path == "/login":
            self._login(query.get("token", ""))
            return
        self._check_origin(required=False)
        self._check_session()
        served = _STATIC.get(url.path)
        if served:
            page = (Path(__file__).parent / "static" / served[0]).read_bytes()
            self._send(200, page, served[1])
            return
        self._api_get(url.path, query)

    def _login(self, token: str) -> None:
        if not self.gateway.redeem(token):
            raise _Reject(401, "NOT_AUTHENTICATED", "this link was already used or isn't valid")
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", self.gateway.session_cookie())
        self.send_header("Content-Length", "0")
        self._security_headers()
        self.end_headers()

    @staticmethod
    def _int(query: dict[str, str], name: str, default: int) -> int:
        try:
            return int(query.get(name, default))
        except ValueError:
            raise _Reject(400, "INVALID_REQUEST", f"{name} must be a whole number") from None

    def _api_get(self, path: str, query: dict[str, str]) -> None:
        gateway, client = self.gateway, self.gateway.client
        if path == "/api/v1/session":
            self._json({"csrf_header": CSRF_HEADER, "csrf_token": gateway.csrf})
        elif path == "/api/v1/health":
            info = client.info()
            self._json(
                {"ok": info.compatible, "gateway": __version__, "harness": info.model_dump()}
            )
        elif path == "/api/v1/workspaces":
            rows = [{"id": k, "name": v.name, "path": str(v)} for k, v in gateway.roots.items()]
            self._json({"workspaces": rows})
        else:
            root = gateway.workspace(query.get("workspace"))
            self._api_get_in(path, query, root)

    def _api_get_in(self, path: str, query: dict[str, str], root: Path) -> None:
        client = self.gateway.client
        if path == "/api/v1/capabilities":
            self._json(client.harness_capabilities(root))
        elif path == "/api/v1/sources":
            found = client.discover_capabilities(root, query.get("q", ""))
            self._json({"capabilities": [c.model_dump() for c in found]})
        elif path == "/api/v1/code":
            self._json(
                client.code_view(
                    root,
                    path_prefix=query.get("path", ""),
                    query=query.get("q", ""),
                    kinds=[k for k in query.get("kinds", "").split(",") if k],
                    budget=self._int(query, "budget", 500),
                    collapse=query.get("collapse", "none"),
                    depth=self._int(query, "depth", 1),
                )
            )
        elif path == "/api/v1/source":
            # Ananke keeps this inside the workspace, and refuses harness state, Git data and environment files
            self._json(
                client.read_source(
                    root,
                    query.get("path", ""),
                    self._int(query, "start", 1),
                    self._int(query, "end", 1) if "end" in query else None,
                )
            )
        elif path == "/api/v1/learning":
            self._json({"candidates": client.learning_candidates(root)})
        elif match := re.fullmatch(r"/api/v1/learning/([\w.-]{1,120})", path):
            self._json(client.learning_candidate(root, match[1]).model_dump())
        elif path == "/api/v1/documents":
            self._json({"documents": documents.listed(root)})
        elif path == "/api/v1/context":
            self._json(
                {
                    **client.context_map(root, budget=self._int(query, "budget", 1500)),
                    **client.context_status(root),
                }
            )
        elif path == "/api/v1/intel":
            self._json(self._latest_intel(root))
        elif path == "/api/v1/runs":
            self._json(client.run_history(root))
        elif match := re.fullmatch(rf"/api/v1/runs/({_RUN_ID})", path):
            self._json(client.get_run(root, match[1]))
        elif match := re.fullmatch(rf"/api/v1/runs/({_RUN_ID})/events", path):
            self._json(client.run_events(root, match[1], self._int(query, "after", 0)))
        elif match := re.fullmatch(rf"/api/v1/runs/({_RUN_ID})/artifacts", path):
            self._json({"artifacts": client.run_artifacts(root, match[1])})
        elif match := re.fullmatch(rf"/api/v1/runs/({_RUN_ID})/artifacts/({_ARTIFACT})", path):
            data = client.read_artifact(root, match[1], match[2])
            # always a download, and sandboxed if opened anyway: an artifact can hold anything
            self._send(
                200,
                data,
                "application/octet-stream",
                ("Content-Disposition", f'attachment; filename="{match[2]}"'),
                ("Content-Security-Policy", "sandbox"),
            )
        else:
            raise _Reject(404, "NOT_FOUND", "no such route")

    def _post(self) -> None:
        self._check_origin(required=True)
        self._check_session()
        self._check_csrf()
        body = self._read_json()
        path = urlsplit(self.path).path
        root = self.gateway.workspace(body.get("workspace"))
        client = self.gateway.client
        if path == "/api/v1/plans/prepare":
            self._json(client.prepare_plan(root, self._object(body, "draft")))
        elif path == "/api/v1/documents/build":
            try:
                self._json(
                    documents.build(
                        root, str(body.get("path", "")), str(body.get("what", "")), client
                    )
                )
            except documents.DocumentError as exc:
                raise _Reject(400, exc.code, str(exc)) from exc
        elif path == "/api/v1/runs":
            run = client.submit_run(
                root,
                str(body.get("kind", "")),
                self._object(body, "parameters", default={}),
                str(body.get("idempotency_key", "")),
            )
            if run["state"] == "queued":
                self.gateway.runs.submit(self.gateway.drive, root, run["run_id"])
            self._json(run, 202)
        elif match := re.fullmatch(rf"/api/v1/runs/({_RUN_ID})/cancel", path):
            self._json(client.cancel_run(root, match[1]))
        else:
            raise _Reject(404, "NOT_FOUND", "no such route")

    def _latest_intel(self, root: Path) -> dict[str, Any]:
        """The newest finished repository analysis. Ananke computes it; a browser starts one as a repo.analyze run."""
        client = self.gateway.client
        for run in client.run_history(root).get("runs", []):
            if run.get("kind") == "repo.analyze" and run.get("state") == "succeeded":
                report: dict[str, Any] = json.loads(
                    client.read_artifact(root, run["run_id"], "repo-intel.json")
                )
                report["run_id"] = run["run_id"]
                report["analysed_at"] = run.get("created_at")
                return report
        raise _Reject(404, "INTEL_MISSING", "this repository hasn't been analysed yet")

    @staticmethod
    def _object(
        body: dict[str, Any], name: str, default: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        value = body.get(name, default)
        if not isinstance(value, dict):
            raise _Reject(400, "INVALID_REQUEST", f"{name} must be a JSON object")
        return value


__all__ = ["CSRF_HEADER", "HOST", "MAX_BODY_BYTES", "Gateway"]

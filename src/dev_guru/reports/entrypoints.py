"""Where a program starts: the files a deployment, a console script or an app initialisation actually runs.

Reading order, the guided tour and "starting point" explanations all begin here, so a test or fixture must never be
chosen. Entry points are found from evidence, strongest first, and every one carries the reason it was chosen:

1. ``deploy``: the command of a Dockerfile (``CMD``/``ENTRYPOINT``), a compose file (``command:``/``entrypoint:``)
   or a Procfile, resolved to a file of the workspace (``python -m pkg.app``, ``python app/main.py``,
   ``uvicorn pkg.main:app``, ``gunicorn pkg.wsgi:application``, ``streamlit run app.py``, ``celery -A pkg worker``…);
2. ``script``: a console script declared in ``pyproject.toml`` (``[project.scripts]``, ``[tool.poetry.scripts]``) or
   ``setup.cfg`` (``console_scripts``);
3. ``app``: a module that creates the application object (``FastAPI(``, ``Flask(__name__``, ``Starlette(``,
   ``get_wsgi_application()``/``get_asgi_application()``, ``typer.Typer(``, ``Celery(``…);
4. ``main``: a module with an ``if __name__ == "__main__":`` block, or a package's ``__main__.py``;
5. ``name``: as a last resort, a conventional file name (``main.py``, ``app.py``, ``manage.py``, ``wsgi.py``…).

Files under tests, fixtures, examples, docs, benchmarks and acceptance suites are never entry points. Nothing is
executed: commands and source are read as text.
"""

from __future__ import annotations

import configparser
import re
import shlex
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ENTRY_NAMES = (
    "__main__.py",
    "main.py",
    "app.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "server.py",
    "cli.py",
)
RANKS = {"deploy": 0, "script": 1, "app": 2, "main": 3, "name": 4}
MAX_DEPLOY_FILES = 50
MAX_SCAN_BYTES = 400_000

_NOT_SOURCE_DIRS = frozenset(
    {
        "test", "tests", "testing", "fixtures", "fixture", "testdata", "test_data", "examples", "example",
        "docs", "doc", "benchmarks", "benchmark", "acceptance", "e2e", "integration_tests", "spec", "specs",
        "node_modules", "site-packages", ".venv", "venv", "build", "dist", "__pycache__",
    }
)  # fmt: skip
_APP_INIT = re.compile(
    r"^\s*\w+\s*(?::[^=]+)?=\s*(?:[\w.]+\.)?"
    r"(?:FastAPI|Flask|Quart|Starlette|Sanic|Litestar|Celery|Typer|Dash|Bottle|Falcon|App)\s*\("
    r"|get_wsgi_application\s*\(|get_asgi_application\s*\(|web\.Application\s*\(",
    re.MULTILINE,
)
_MAIN_BLOCK = re.compile(r"""^if\s+__name__\s*==\s*["']__main__["']\s*:""", re.MULTILINE)
_TOOLING_DIRS = frozenset(
    {"scripts", "script", "tools", "tool", "bin", "hack", "ci", "dev", "devtools", "maint"}
)
_SERVERS = {"uvicorn", "gunicorn", "hypercorn", "daphne", "granian", "waitress-serve"}


@dataclass(frozen=True)
class EntryPoint:
    path: str
    kind: str  # deploy | script | app | main | name
    reason: str
    order: int = 0  # deploy entries keep the order of their deploy files and commands (the first is the main process)

    @property
    def rank(self) -> int:
        return RANKS[self.kind]

    @property
    def tooling(self) -> bool:
        """In a project-tooling folder (scripts/, tools/ …): ranked after the application's own code."""
        return any(part.lower() in _TOOLING_DIRS for part in PurePosixPath(self.path).parts[:-1])


def is_test_like(path: str) -> bool:
    """True for tests, fixtures, examples, docs and similar: never where a program starts."""
    p = PurePosixPath(path)
    name = p.name
    if (
        name == "conftest.py"
        or name.startswith("test_")
        or name.endswith(("_test.py", "_tests.py"))
    ):
        return True
    return any(part.lower() in _NOT_SOURCE_DIRS for part in p.parts[:-1])


def _read(root: Path, rel: str) -> str:
    try:
        path = root / rel
        if path.stat().st_size > MAX_SCAN_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


class _Resolver:
    """Map module names and file arguments found in commands to workspace files."""

    def __init__(self, paths: Iterable[str]) -> None:
        self.paths = sorted(p for p in paths if p.endswith(".py"))
        self.by_module: dict[str, list[str]] = {}
        for p in self.paths:
            parts = p.removesuffix(".py").split("/")
            if parts[-1] == "__init__":
                parts = parts[:-1]
            # every suffix of the dotted path, so "src/pkg/app.py" answers to "pkg.app" as well as "src.pkg.app"
            for i in range(len(parts)):
                self.by_module.setdefault(".".join(parts[i:]), []).append(p)

    def module(self, dotted: str, *, prefer_main: bool = False) -> str | None:
        dotted = dotted.strip().split(":", 1)[0].strip(".")
        if not dotted:
            return None
        found = self.by_module.get(dotted, [])
        if prefer_main:  # `python -m pkg` runs pkg/__main__.py
            mains = self.by_module.get(f"{dotted}.__main__", [])
            found = mains or found
        return self._best(found)

    def file(self, arg: str, workdir: str = "") -> str | None:
        arg = arg.strip().strip("'\"")
        if not arg.endswith(".py"):
            return None
        candidates = [str(PurePosixPath(workdir.strip("/")) / arg).lstrip("./"), arg.lstrip("./")]
        for c in candidates:
            if c in self.paths:
                return c
        tail = [
            p for p in self.paths if p.endswith("/" + arg.lstrip("./")) or p == arg.lstrip("./")
        ]
        return self._best(tail)

    @staticmethod
    def _best(found: list[str]) -> str | None:
        found = [p for p in found if not is_test_like(p)]
        return min(found, key=lambda p: (p.count("/"), p)) if found else None


def _command_targets(command: str, resolver: _Resolver, workdir: str = "") -> list[tuple[str, str]]:
    """(file, how) for each workspace file a shell command would run."""
    out: list[tuple[str, str]] = []
    try:  # quotes first, so `sh -c "a && b"` stays one argument
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    segments: list[list[str]] = [[]]
    for tok in tokens:
        if tok in {"&&", "||", ";", "|"}:
            segments.append([])
        elif tok.endswith(";") and len(tok) > 1:
            segments[-1].append(tok[:-1])
            segments.append([])
        else:
            segments[-1].append(tok)
    for words in segments:
        # drop env assignments and wrappers (`exec`, `sh -c "…"` is handled by recursing into the string)
        while words and (
            ("=" in words[0] and not words[0].startswith("-"))
            or words[0] in {"exec", "env", "nohup"}
        ):
            words = words[1:]
        if (
            len(words) >= 3
            and words[0] in {"sh", "bash", "/bin/sh", "/bin/bash"}
            and words[1] == "-c"
        ):
            out += _command_targets(words[2], resolver, workdir)
            continue
        if not words:
            continue
        tool = PurePosixPath(words[0]).name
        args = words[1:]
        target: str | None = None
        if tool.startswith("python") or tool in {"uv", "poetry", "pipenv"}:
            if tool in {"uv", "poetry", "pipenv"}:  # uv run python x.py / poetry run python -m x
                args = [a for a in args if a not in {"run", "python", "python3"}]
            if "-m" in args and args.index("-m") + 1 < len(args):
                mod = args[args.index("-m") + 1]
                if mod in _SERVERS or mod in {"streamlit", "flask", "celery", "fastapi"}:
                    target = _server_target(mod, args[args.index("-m") + 2 :], resolver, workdir)
                else:
                    target = resolver.module(mod, prefer_main=True)
            else:
                target = next((t for a in args if (t := resolver.file(a, workdir))), None)
        elif tool in _SERVERS or tool in {"streamlit", "flask", "celery", "fastapi"}:
            target = _server_target(tool, args, resolver, workdir)
        else:  # a console script of this project, or a script file run directly
            target = resolver.file(words[0], workdir)
        if target:
            out.append((target, " ".join(words[:4])))
    return out


def _server_target(tool: str, args: list[str], resolver: _Resolver, workdir: str) -> str | None:
    if tool == "streamlit":
        return next((t for a in args if (t := resolver.file(a, workdir))), None)
    if tool == "celery":
        for i, a in enumerate(args):
            if a in {"-A", "--app"} and i + 1 < len(args):
                return resolver.module(args[i + 1])
            if a.startswith("--app="):
                return resolver.module(a.split("=", 1)[1])
        return None
    if tool in {"flask", "fastapi"}:
        for i, a in enumerate(args):
            if a in {"--app", "-A"} and i + 1 < len(args):
                return resolver.module(args[i + 1]) or resolver.file(args[i + 1], workdir)
            if a.startswith("--app="):
                return resolver.module(a.split("=", 1)[1])
        return next((t for a in args if (t := resolver.file(a, workdir))), None)
    # uvicorn / gunicorn / hypercorn / daphne: the first "module:object" (or module) argument
    for a in args:
        if a.startswith("-"):
            continue
        if (":" in a or "." in a) and (found := resolver.module(a)):
            return found
    return None


def _deploy_files(root: Path, files: Iterable[str]) -> list[str]:
    names = []
    for rel in files:
        name = PurePosixPath(rel).name.lower()
        if (
            name == "dockerfile"
            or name.startswith("dockerfile.")
            or name.endswith(".dockerfile")
            or name
            in {
                "procfile",
                "docker-compose.yml",
                "docker-compose.yaml",
                "compose.yml",
                "compose.yaml",
            }
        ) and not is_test_like(rel):
            names.append(rel)
    return sorted(names, key=lambda p: (p.count("/"), p))[:MAX_DEPLOY_FILES]


def _docker_commands(text: str) -> list[tuple[str, str, str]]:
    """(instruction, working directory, command) for each CMD and ENTRYPOINT."""
    out: list[tuple[str, str, str]] = []
    workdir = ""
    joined = re.sub(r"\\\s*\n", " ", text)
    for raw in joined.splitlines():
        m = re.match(r"(?i)^(WORKDIR|CMD|ENTRYPOINT)\s+(.*)$", raw.strip())
        if not m:
            continue
        word, rest = m.group(1).upper(), m.group(2).strip()
        if word == "WORKDIR":
            workdir = rest.strip("'\"")
            continue
        if rest.startswith("["):  # exec form: ["python", "-m", "app"]
            rest = " ".join(shlex.quote(i) for i in re.findall(r'"((?:[^"\\]|\\.)*)"', rest))
        out.append((word, workdir, rest))
    return out


def _compose_commands(text: str) -> list[str]:
    out = []
    for m in re.finditer(r"^\s*(?:command|entrypoint)\s*:\s*(.+)$", text, re.MULTILINE):
        value = m.group(1).strip()
        if value.startswith("["):
            value = " ".join(shlex.quote(i) for i in re.findall(r"""["']([^"']*)["']""", value))
        out.append(value.strip("'\""))
    return out


def _declared_scripts(root: Path) -> list[tuple[str, str]]:
    """(name, "module:function") from pyproject.toml and setup.cfg."""
    out: list[tuple[str, str]] = []
    try:
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
        data = {}
    for table in (
        data.get("project", {}).get("scripts", {}),
        data.get("project", {}).get("gui-scripts", {}),
        data.get("tool", {}).get("poetry", {}).get("scripts", {}),
    ):
        for name, target in (table or {}).items():
            if isinstance(target, str):
                out.append((str(name), target))
            elif isinstance(target, dict) and isinstance(target.get("reference"), str):
                out.append((str(name), target["reference"]))
    cfg = configparser.ConfigParser()
    try:
        cfg.read_string((root / "setup.cfg").read_text(encoding="utf-8"))
        for line in cfg.get("options.entry_points", "console_scripts", fallback="").splitlines():
            if "=" in line:
                name, target = line.split("=", 1)
                out.append((name.strip(), target.strip()))
    except (OSError, configparser.Error, UnicodeDecodeError):
        pass
    return out


def detect(
    root: Path, paths: Iterable[str], *, other_files: Iterable[str] = ()
) -> list[EntryPoint]:
    """Entry points among ``paths`` (workspace-relative Python files), strongest evidence first.

    ``other_files`` are further workspace-relative paths (Dockerfiles, compose files, Procfiles); when empty, the
    workspace is searched for them.
    """
    paths = sorted(set(paths))
    resolver = _Resolver(paths)
    found: dict[str, EntryPoint] = {}

    def add(path: str | None, kind: str, reason: str) -> None:
        if not path or path not in resolver.paths or is_test_like(path):
            return
        current = found.get(path)
        if current is None or RANKS[kind] < current.rank:
            found[path] = EntryPoint(path, kind, reason, len(found) if kind == "deploy" else 0)

    others = list(other_files) or [
        str(p.relative_to(root)).replace("\\", "/")
        for pattern in ("**/Dockerfile*", "**/*.dockerfile", "**/Procfile", "**/*compose*.y*ml")
        for p in root.glob(pattern)
        if p.is_file()
        and not any(part in {"node_modules", ".venv", "venv", ".git"} for part in p.parts)
    ]
    for rel in _deploy_files(root, others):
        text = _read(root, rel)
        name = PurePosixPath(rel).name.lower()
        if name == "procfile":
            for line in text.splitlines():
                if ":" in line:
                    proc, command = line.split(":", 1)
                    for target, how in _command_targets(command, resolver):
                        add(target, "deploy", f"run by `{how}` ({rel}, process `{proc.strip()}`)")
        elif "compose" in name:
            for command in _compose_commands(text):
                for target, how in _command_targets(command, resolver):
                    add(target, "deploy", f"run by `{how}` ({rel})")
        else:
            for word, workdir, command in _docker_commands(text):
                for target, how in _command_targets(command, resolver, workdir):
                    add(target, "deploy", f"run by `{how}` ({rel}, {word})")
    for name, target in _declared_scripts(root):
        add(resolver.module(target), "script", f"console script `{name}` → `{target}`")
    for path in paths:
        if is_test_like(path):
            continue
        text = _read(root, path)
        if app := _APP_INIT.search(text):
            at = text[: app.start()].count("\n") + 1
            add(path, "app", f"creates the application object (line {at})")
        elif PurePosixPath(path).name == "__main__.py":
            add(path, "main", "a package's `__main__.py` (run with `python -m`)")
        elif _MAIN_BLOCK.search(text):
            add(path, "main", 'has an `if __name__ == "__main__":` block')
    if not found:
        for path in paths:
            if PurePosixPath(path).name in ENTRY_NAMES:
                add(path, "name", f"named `{PurePosixPath(path).name}`, a conventional entry file")
    return sorted(
        found.values(), key=lambda e: (e.rank, e.order, e.tooling, e.path.count("/"), e.path)
    )

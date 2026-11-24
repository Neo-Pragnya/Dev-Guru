"""Entry points come from what really runs (deploy commands, console scripts, app objects, __main__), never tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev_guru.reports.entrypoints import detect, is_test_like


def _write(root: Path, files: dict[str, str]) -> list[str]:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return sorted(r for r in files if r.endswith(".py"))


MAIN = 'if __name__ == "__main__":\n    run()\n'


def test_tests_and_fixtures_are_never_entry_points(tmp_path: Path) -> None:
    # the bug: a script in a test folder (named like an entry file, or with a __main__ block) was the starting point
    paths = _write(
        tmp_path,
        {
            "acceptance/fixtures/shop/app.py": "app = FastAPI()\n",
            "tests/app.py": MAIN,
            "tests/test_cli.py": MAIN,
            "tests/conftest.py": "",
            "examples/demo/main.py": MAIN,
            "src/shop/service.py": "def handle():\n    pass\n",
            "src/shop/__main__.py": "from shop.service import handle\nhandle()\n",
        },
    )
    found = detect(tmp_path, paths)
    assert [e.path for e in found] == ["src/shop/__main__.py"]
    assert found[0].kind == "main"


def test_dockerfile_command_wins_and_says_why(tmp_path: Path) -> None:
    paths = _write(
        tmp_path,
        {
            "Dockerfile": 'FROM python:3.12\nWORKDIR /srv\nCOPY . .\nCMD ["uvicorn", "shop.api:app", "--host", "0.0.0.0"]\n',
            "src/shop/api.py": "app = FastAPI()\n",
            "src/shop/tools.py": MAIN,
            "tests/test_api.py": MAIN,
        },
    )
    found = detect(tmp_path, paths)
    assert found[0].path == "src/shop/api.py"
    assert found[0].kind == "deploy"
    assert "uvicorn shop.api:app" in found[0].reason and "Dockerfile" in found[0].reason
    assert [e.path for e in found] == ["src/shop/api.py", "src/shop/tools.py"]


@pytest.mark.parametrize(
    ("deploy_file", "text", "expected"),
    [
        ("Dockerfile", "ENTRYPOINT python -m worker\n", "worker/__main__.py"),
        ("Dockerfile", "WORKDIR /app\nCMD python run.py\n", "run.py"),
        ("docker/Dockerfile.prod", 'CMD ["gunicorn", "web.wsgi:application"]\n', "web/wsgi.py"),
        (
            "Procfile",
            "web: gunicorn web.wsgi:application\nworker: celery -A tasks.queue worker\n",
            "web/wsgi.py",
        ),
        (
            "docker-compose.yml",
            "services:\n  ui:\n    command: streamlit run dashboard.py\n",
            "dashboard.py",
        ),
        (
            "Dockerfile",
            'CMD ["sh", "-c", "alembic upgrade head && python -m worker"]\n',
            "worker/__main__.py",
        ),
    ],
)
def test_deploy_commands_resolve_to_files(
    tmp_path: Path, deploy_file: str, text: str, expected: str
) -> None:
    paths = _write(
        tmp_path,
        {
            deploy_file: text,
            "worker/__init__.py": "",
            "worker/__main__.py": "print('work')\n",
            "run.py": "print('run')\n",
            "web/__init__.py": "",
            "web/wsgi.py": "application = object()\n",
            "tasks/queue.py": "queue = object()\n",
            "dashboard.py": "import streamlit\n",
        },
    )
    found = detect(tmp_path, paths)
    assert found and found[0].path == expected and found[0].kind == "deploy"


def test_console_scripts_and_app_objects(tmp_path: Path) -> None:
    paths = _write(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "shop"\n[project.scripts]\nshop = "shop.cli:main"\n',
            "src/shop/cli.py": "def main():\n    pass\n",
            "src/shop/web.py": "from flask import Flask\napp = Flask(__name__)\n",
            "src/shop/util.py": "X = 1\n",
        },
    )
    found = {e.path: e for e in detect(tmp_path, paths)}
    assert (
        found["src/shop/cli.py"].kind == "script"
        and "shop.cli:main" in found["src/shop/cli.py"].reason
    )
    assert found["src/shop/web.py"].kind == "app"
    assert "src/shop/util.py" not in found


def test_file_names_are_only_a_last_resort(tmp_path: Path) -> None:
    paths = _write(tmp_path, {"service/main.py": "def go():\n    pass\n", "tests/main.py": ""})
    found = detect(tmp_path, paths)
    assert [(e.path, e.kind) for e in found] == [("service/main.py", "name")]


@pytest.mark.parametrize(
    ("path", "test_like"),
    [
        ("tests/x.py", True),
        ("src/pkg/test_x.py", True),
        ("src/pkg/x_test.py", True),
        ("conftest.py", True),
        ("acceptance/fixtures/shop/app.py", True),
        ("docs/conf.py", True),
        ("src/pkg/testing_utils.py", False),
        ("src/contest/app.py", False),
        ("app.py", False),
    ],
)
def test_is_test_like(path: str, test_like: bool) -> None:
    assert is_test_like(path) is test_like


def test_project_tooling_ranks_after_the_application(tmp_path: Path) -> None:
    paths = _write(
        tmp_path,
        {
            "scripts/build_docs.py": MAIN,
            "src/shop/__main__.py": "print('shop')\n",
            "src/shop/__init__.py": "",
        },
    )
    assert [e.path for e in detect(tmp_path, paths)] == [
        "src/shop/__main__.py",
        "scripts/build_docs.py",
    ]

"""Helpers of the end-to-end environment: wipe the database, seed it, build and serve the app."""

import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url

from crm.config import PROJECT_ROOT, settings


logger = logging.getLogger(__name__)


def assert_local_database(url: str) -> None:
    """Refuse to continue unless the database in `url` runs on one of the allowed (local) hosts."""
    host = make_url(url).host
    logger.info("Target database host: %s", host)
    if host not in settings.e2e.allowed_database_hosts:
        raise RuntimeError(
            f"The e2e test empties the database and {host!r} is not in [e2e] allowed_database_hosts"
        )


def reset_database(engine: Engine) -> list[str]:
    """Empty every table of `public` except the preserved ones; return the tables emptied.

    Only `public` is touched: the Supabase credentials (schema `auth`) stay as they are.
    """
    preserved = settings.e2e.preserved_tables
    with engine.begin() as conn:
        tables = [
            row[0] for row in conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name"
            )) if row[0] not in preserved
        ]
        if tables:
            names = ", ".join(f'public."{name}"' for name in tables)
            conn.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))
    logger.info("Database emptied (%d tables, kept: %s)", len(tables), ", ".join(preserved))
    return tables


def run_command(command: list[str], cwd: Path, timeout: int) -> None:
    """Run `command` in `cwd`, raising with its output if it fails (npm needs its .cmd on Windows)."""
    executable = shutil.which(command[0]) or command[0]
    logger.info("Running: %s (in %s)", " ".join(command), cwd)
    result = subprocess.run(
        [executable, *command[1:]], cwd=cwd, capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(command)} failed:\n{result.stdout}\n{result.stderr}")
    logger.info("Finished: %s", " ".join(command))


def migrate_database() -> None:
    """Bring the schema to the latest Alembic revision."""
    run_command([sys.executable, "-m", "alembic", "upgrade", "head"], PROJECT_ROOT, 300)


def build_frontend() -> Path:
    """Build the frontend and return the folder with the result."""
    frontend = PROJECT_ROOT / settings.e2e.frontend_dir
    run_command(settings.e2e.build_command, frontend, settings.e2e.build_timeout_seconds)
    return frontend / "dist"


def base_url() -> str:
    """Return the address the e2e app listens on."""
    return f"http://{settings.e2e.host}:{settings.e2e.port}"


def is_up() -> bool:
    """Return True when something answers /health on the e2e address."""
    try:
        return httpx.get(f"{base_url()}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def stop_previous_server() -> None:
    """Stop the app left running by a previous e2e run (found through its pid file)."""
    pid_file = PROJECT_ROOT / settings.e2e.pid_file
    if pid_file.is_file():
        if is_up():  # only kill the pid while our app is the one answering, never a reused pid
            logger.info("Stopping the previous e2e app (pid file %s)", pid_file)
            try:
                os.kill(int(pid_file.read_text()), signal.SIGTERM)
            except (OSError, ValueError):
                pass
            deadline = time.monotonic() + 10
            while is_up() and time.monotonic() < deadline:
                time.sleep(0.3)
        pid_file.unlink(missing_ok=True)
    if is_up():
        raise RuntimeError(f"Port {settings.e2e.port} is already in use by something that is not the e2e app")


def start_server(static_dir: Path) -> int:
    """Start the API serving the built frontend and leave it running after the tests.

    The process is detached from this one (it survives pytest) and replaces the previous e2e app.
    Return its pid once /health answers.
    """
    stop_previous_server()
    log_file = PROJECT_ROOT / settings.e2e.log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "API_STATIC_DIR": str(static_dir)}
    detach = (
        {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
        if sys.platform == "win32" else {"start_new_session": True}
    )
    with open(log_file, "wb") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "--factory", "crm.api.app:create_app",
             "--host", settings.e2e.host, "--port", str(settings.e2e.port)],
            cwd=PROJECT_ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, **detach,
        )
    deadline = time.monotonic() + settings.e2e.startup_timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"The e2e server stopped while starting; see {log_file}")
        if is_up():
            (PROJECT_ROOT / settings.e2e.pid_file).write_text(str(process.pid))
            logger.info("e2e app running at %s (pid %s, log %s)", base_url(), process.pid, log_file)
            return process.pid
        time.sleep(0.5)
    process.terminate()
    raise RuntimeError(f"The e2e server did not answer /health in time; see {log_file}")

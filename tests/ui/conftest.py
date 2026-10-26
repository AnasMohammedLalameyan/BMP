"""Browser smoke tests for the front end (Playwright).

They are OFF by default so `python -m pytest` still works on a machine with no browser. To run them:

    pip install playwright            # uses an installed Chrome/Edge; no extra download needed (see browser fixture)
    set BMP_UI_TESTS=1                # PowerShell: $env:BMP_UI_TESTS = "1"
    python -m pytest tests/ui -q

They start the real application (scripts/run_server.py) on a free port against the database named in .env, which must hold the
seeded demo data (python scripts/setup_db.py --seed). Sign-in passwords are created in a temporary credentials file.
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[2]

if not os.environ.get("BMP_UI_TESTS"):
    collect_ignore_glob = ["test_*.py"]

USERS = {"admin@bmpco.in": "Admin#Pass123", "manager@bmpco.in": "Manager#Pass123", "client@nexatech.co.in": "Client#Pass123"}


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    sys.path.insert(0, str(BASE))
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
    from app.security import UsersStore
    work = tmp_path_factory.mktemp("ui")
    store = UsersStore(work / "users.json")
    for email, pw in USERS.items():
        store.set_password(email, pw)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(os.environ, USERS_FILE=str(work / "users.json"), STORAGE_DIR=str(work / "storage"), APP_ENV="development",
               APP_SECRET_KEY="ui-tests-" + "x" * 40)
    log = open(work / "server.log", "w")
    proc = subprocess.Popen([sys.executable, str(BASE / "scripts" / "run_server.py"), "--port", str(port)], cwd=BASE, env=env,
                            stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            if urllib.request.urlopen(url + "/api/health", timeout=1).status == 200:
                break
        except Exception:
            time.sleep(0.5)
    else:
        proc.terminate()
        pytest.fail("the application did not start; see " + str(work / "server.log"))
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="session")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome", headless=True)         # the installed Chrome
        except Exception:
            b = p.chromium.launch(headless=True)                             # Playwright's own Chromium, if installed
        yield b
        b.close()


@pytest.fixture
def open_app(browser, server):
    """open_app("manager@bmpco.in", width=1280) -> a page signed in as that user, on the Companies screen."""
    contexts = []

    def _open(email="admin@bmpco.in", width=1280, height=900):
        ctx = browser.new_context(viewport={"width": width, "height": height})
        contexts.append(ctx)
        page = ctx.new_page()
        page.goto(server + "/")
        page.wait_for_selector("#loginView:not(.d-none)")      # the page clears the form once, after its first (401) session check
        page.fill("#loginEmail", email)
        page.fill("#loginPassword", USERS[email])
        page.click("#loginBtn")
        page.wait_for_selector("#launcherView:not(.d-none)")
        page.click("#goDatabase")
        page.wait_for_selector("#appShell:not(.d-none)")
        page.wait_for_selector("#pageTitle:has-text('Companies')")
        return page

    yield _open
    for c in contexts:
        c.close()

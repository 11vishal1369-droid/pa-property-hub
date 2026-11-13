import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from dotenv import dotenv_values

# Tests never use the live database or live Firestore: isolated Mongo namespace + Firebase disabled.
HERE = Path(__file__).parent
LIVE_DB = dotenv_values(HERE.parent / ".env")["DB_NAME"]
TEST_DB = "pa_regression"
PORT = 8123
os.environ["DB_NAME"] = "pa_regression_sync"
os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"] = ""
os.environ["TEST_API"] = f"http://127.0.0.1:{PORT}/api"
assert TEST_DB != LIVE_DB and os.environ["DB_NAME"] != LIVE_DB
_procs = []


def _wait(port, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.5)
    raise RuntimeError(f"port {port} did not open")


def pytest_configure(config):
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    from pymongo import MongoClient
    MongoClient(dotenv_values(HERE.parent / ".env")["MONGO_URL"]).drop_database(TEST_DB)
    env = {**os.environ, "DB_NAME": TEST_DB, "FIREBASE_SERVICE_ACCOUNT_JSON": ""}
    _procs.append(subprocess.Popen([sys.executable, str(HERE / "mock_esign.py")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    _procs.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(PORT)],
                                   cwd=HERE.parent, env=env, stdout=subprocess.DEVNULL, stderr=open("/tmp/pa_test_server.log", "w")))
    _wait(8099)
    _wait(PORT)


def pytest_unconfigure(config):
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    for p in _procs:
        p.terminate()
    from pymongo import MongoClient
    cl = MongoClient(dotenv_values(HERE.parent / ".env")["MONGO_URL"])
    cl.drop_database(TEST_DB)
    cl.drop_database("pa_regression_sync")

import os
import time

import pytest
from fastapi.testclient import TestClient


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(reason="set RUN_INTEGRATION=1 (real OpenAI + live ingest)")
    for item in items:
        if "/integration/" in str(item.fspath) or "\\integration\\" in str(item.fspath):
            item.add_marker(skip)


@pytest.fixture(scope="module")
def client():
    from main import app

    with TestClient(app) as c:
        deadline = time.time() + 20
        while time.time() < deadline:
            st = c.get("/stream/status").json()
            if st.get("event_count", 0) > 0 or st.get("running"):
                break
            time.sleep(1)
        yield c

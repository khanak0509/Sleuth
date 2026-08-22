import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT.parent / ".env")
load_dotenv()


@pytest.fixture
def sample_push():
    return {
        "id": "1234567890",
        "type": "PushEvent",
        "created_at": "2024-06-01T12:00:00Z",
        "repo": {"name": "acme/widget"},
        "actor": {"login": "dev1"},
        "payload": {
            "commits": [
                {"message": "fix flaky test"},
                {"message": "bump ci"},
            ]
        },
    }

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXAMPLES = ROOT / "docs" / "playbook" / "examples"


def load(name: str):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


@pytest.fixture
def req_success():
    return load("request-success.json")


@pytest.fixture
def resp_success():
    return load("response-success.json")


@pytest.fixture
def req_partial():
    return load("request-partial.json")


@pytest.fixture
def resp_partial():
    return load("response-partial.json")


@pytest.fixture
def resp_failed():
    return load("response-failed.json")

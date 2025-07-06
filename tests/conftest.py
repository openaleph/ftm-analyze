from pathlib import Path

import pytest
from anystore.util import rm_rf
from ftmq.io import smart_read_proxies
from juditha.io import load_proxies

FIXTURES_PATH = (Path(__file__).parent / "fixtures").absolute()
DOCUMENTS = "documents.ftm.json"
JUDITHA = "juditha.ftm.json"


@pytest.fixture(scope="module")
def fixtures_path():
    return FIXTURES_PATH


@pytest.fixture(scope="module")
def documents():
    return [x for x in smart_read_proxies(FIXTURES_PATH / DOCUMENTS)]


@pytest.fixture(scope="session", autouse=True)
def juditha():
    load_proxies(FIXTURES_PATH / JUDITHA)
    yield
    rm_rf(".testdata")

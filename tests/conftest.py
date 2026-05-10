import os

import pytest


@pytest.fixture(scope="session")
def database_url():
    url = os.getenv("GMIND_TEST_DATABASE_URL")
    if url is None:
        pytest.skip("GMIND_TEST_DATABASE_URL not set, skipping integration tests")
    return url

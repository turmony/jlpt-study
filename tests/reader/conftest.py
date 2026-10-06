"""Keep persistent caches from tests outside the user's actual cache."""

import os
from unittest.mock import patch

import pytest


@pytest.fixture(scope='session', autouse=True)
def isolated_reader_cache(tmp_path_factory):
    with patch.dict(os.environ, {'XDG_CACHE_HOME': str(tmp_path_factory.mktemp('reader-cache'))}):
        yield

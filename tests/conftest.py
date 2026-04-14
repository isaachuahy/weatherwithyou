import pytest

from weatherwithyou.settings import get_settings


@pytest.fixture(autouse=True)
def clear_cached_settings() -> None:
    """Reset cached settings around each test so env mutations stay isolated."""

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

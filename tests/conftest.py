"""Pytest configuration and fixtures."""

import pytest
from sqlalchemy import create_engine

from accountant.config import Settings, clear_settings_cache
from accountant.db import Base, create_session_factory


@pytest.fixture
def test_settings():
    """In-memory test settings."""
    clear_settings_cache()
    settings = Settings(
        sec_user_agent="Test Agent test@example.com",
        database_url="sqlite:///:memory:",
        accountant_env="test",
        log_level="DEBUG",
    )
    return settings


@pytest.fixture
def test_engine(test_settings):
    """In-memory SQLite database engine."""
    engine = create_engine(test_settings.database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_session(test_engine):
    """Database session for testing."""
    factory = create_session_factory(test_engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sec_client_mock(test_settings, monkeypatch):  # noqa: ARG001
    """Mock SEC client that doesn't make real HTTP requests."""
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.resolve_ticker.return_value = Mock(
        ticker="AAPL",
        cik="0000320193",
        name="Apple Inc.",
    )
    return mock_client

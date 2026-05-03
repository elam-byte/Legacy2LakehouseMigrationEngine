"""pytest fixtures shared across unit and integration tests."""

import pytest


@pytest.fixture
def transpiler():
    from src.transpiler.engine import SqlTranspiler
    return SqlTranspiler(source_dialect="postgres")


@pytest.fixture
def oracle_transpiler():
    from src.transpiler.engine import SqlTranspiler
    return SqlTranspiler(source_dialect="oracle")

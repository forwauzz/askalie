from pathlib import Path

import pytest

from tests.fixtures.make_fixtures import build_fixtures


@pytest.fixture(scope="session")
def fixture_pdf_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-scoped directory of synthetic case PDFs."""
    target = tmp_path_factory.mktemp("fixture_pdfs")
    build_fixtures(target)
    return target

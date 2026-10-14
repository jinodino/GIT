from pathlib import Path

import pytest

from code_review_agent.tools.file_reader import read_file
from code_review_agent.tools.code_search import search_code
from code_review_agent.tools.static_analyzer import run_ruff


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1] / "sample_project"
)


def test_read_file():
    result = read_file(str(PROJECT_ROOT), "calculator.py")

    assert "def divide" in result


def test_block_outside_file():
    with pytest.raises(ValueError):
        read_file(str(PROJECT_ROOT), "../.env")


def test_search_code():
    results = search_code(str(PROJECT_ROOT), "divide(")

    assert len(results) >= 2


def test_run_ruff():
    results = run_ruff(str(PROJECT_ROOT), "calculator.py")

    codes = [item["code"] for item in results]

    assert "F401" in codes  # 미사용 import
    assert "F841" in codes  # 미사용 변수
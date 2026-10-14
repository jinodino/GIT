import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src")
)

from code_review_agent.models.review import (
    ReviewItem,
    ReviewResult,
)


def test_valid_review():
    review = ReviewItem(
        file_name="example.py",
        line=2,
        severity="HIGH",
        category="BUG",
        message="0으로 나눌 가능성이 있습니다.",
        suggestion="입력값을 검증하세요.",
    )

    result = ReviewResult(reviews=[review])

    assert len(result.reviews) == 1


def test_invalid_severity():
    with pytest.raises(ValidationError):
        ReviewItem(
            file_name="example.py",
            line=2,
            severity="CRITICAL",
            category="BUG",
            message="테스트",
            suggestion="테스트",
        )


def test_invalid_line():
    with pytest.raises(ValidationError):
        ReviewItem(
            file_name="example.py",
            line=0,
            severity="HIGH",
            category="BUG",
            message="테스트",
            suggestion="테스트",
        )
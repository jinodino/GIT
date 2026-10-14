import io
import json
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

from code_review_agent.github import pr_reviewer
from code_review_agent.github.pr_reviewer import (
    MARKER,
    GitHubAPIError,
    GitHubClient,
    review_files,
)


def test_changed_files_filters_and_limits():
    github = GitHubClient("token", "owner/repo")
    github.pages = Mock(return_value=iter([
        {"filename": "a.py", "status": "modified"},
        {"filename": "gone.py", "status": "removed"},
        {"filename": "readme.md", "status": "modified"},
        *({"filename": f"src/{i}.py", "status": "added"} for i in range(8)),
    ]))
    assert github.changed_python_files(12) == [
        "a.py", "src/0.py", "src/1.py", "src/2.py", "src/3.py"
    ]


def test_no_changed_python_files():
    github = GitHubClient("token", "owner/repo")
    github.pages = Mock(return_value=iter([{"filename": "a.txt", "status": "added"}]))
    assert github.changed_python_files(1) == []


def test_main_exits_without_python_files(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("PR_NUMBER", "1")
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    client = Mock()
    client.changed_python_files.return_value = []
    monkeypatch.setattr(pr_reviewer, "GitHubClient", Mock(return_value=client))
    agent = Mock()
    monkeypatch.setattr(pr_reviewer, "CodeReviewAgent", agent)
    pr_reviewer.main()
    agent.assert_not_called()
    client.upsert_comment.assert_not_called()


def test_pagination():
    github = GitHubClient("token", "owner/repo")
    github.request = Mock(side_effect=[[{"id": i} for i in range(100)], [{"id": 100}]])
    assert len(list(github.pages("/items"))) == 101
    assert github.request.call_args_list[1].args == (
        "GET", "/items?per_page=100&page=2"
    )


def test_review_files_combines_and_continues(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("x = 2\n")
    agent = Mock()
    agent.review.side_effect = [RuntimeError("secret detail"), "문제 없음"]
    body = review_files(["a.py", "b.py"], tmp_path, agent)
    assert MARKER in body
    assert "### `a.py`" in body and "리뷰 실패: RuntimeError" in body
    assert "### `b.py`" in body and "문제 없음" in body
    assert "secret detail" not in body
    assert agent.review.call_count == 2
    assert agent.review.call_args_list[0].kwargs["max_iterations"] == 5


def test_comment_updates_only_own_marked_comment():
    github = GitHubClient("token", "owner/repo")
    github.request = Mock(side_effect=[{"id": 7}, {"id": 44}])
    github.pages = Mock(return_value=iter([
        {"id": 10, "user": {"id": 8}, "body": MARKER},
        {"id": 11, "user": {"id": 7}, "body": "ordinary comment"},
        {"id": 12, "user": {"id": 7}, "body": MARKER},
    ]))
    github.upsert_comment(3, MARKER + "\nreview")
    assert github.request.call_args_list[0].args == (
        "GET", "/users/github-actions%5Bbot%5D"
    )
    assert github.request.call_args_list[1].args[:2] == (
        "PATCH", "/repos/owner/repo/issues/comments/12"
    )


def test_comment_creates_when_missing():
    github = GitHubClient("token", "owner/repo")
    github.request = Mock(side_effect=[{"id": 7}, {"id": 44}])
    github.pages = Mock(return_value=iter([]))
    github.upsert_comment(3, MARKER)
    assert github.request.call_args_list[1].args[:2] == (
        "POST", "/repos/owner/repo/issues/3/comments"
    )


def test_api_error_and_timeout(monkeypatch):
    github = GitHubClient("token", "owner/repo")

    def fail(request, timeout):
        assert timeout == 15
        raise HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(b"secret"))

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(GitHubAPIError, match="HTTP 403") as error:
        github.request("GET", "/user")
    assert "secret" not in str(error.value)

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: (_ for _ in ()).throw(URLError("offline")))
    with pytest.raises(GitHubAPIError):
        github.request("GET", "/user")


def test_api_rejects_invalid_list_response():
    github = GitHubClient("token", "owner/repo")
    github.request = Mock(return_value={"message": "error"})
    with pytest.raises(GitHubAPIError):
        list(github.pages("/items"))


def test_request_json(monkeypatch):
    github = GitHubClient("token", "owner/repo")
    response = Mock()
    response.__enter__ = Mock(return_value=io.BytesIO(json.dumps({"ok": True}).encode()))
    response.__exit__ = Mock(return_value=None)
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: response)
    assert github.request("GET", "/user") == {"ok": True}

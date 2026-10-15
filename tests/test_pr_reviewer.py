import io
import json
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

from code_review_agent.agent.reviewer import ReviewTrace
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
    client.python_changes.return_value = []
    monkeypatch.setattr(pr_reviewer, "GitHubClient", Mock(return_value=client))
    agent = Mock()
    monkeypatch.setattr(pr_reviewer, "CodeReviewAgent", agent)
    pr_reviewer.main()
    agent.assert_not_called()
    client.upsert_comment.assert_not_called()


def test_main_posts_valid_suggestion(monkeypatch, tmp_path):
    (tmp_path / "a.py").write_text("value = 1\n")
    for key, value in {
        "GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "token", "PR_NUMBER": "1",
        "PR_HEAD_SHA": "abc", "PROJECT_ROOT": str(tmp_path),
    }.items():
        monkeypatch.setenv(key, value)
    client = Mock()
    client.python_changes.return_value = [{
        "filename": "a.py", "status": "modified",
        "patch": "@@ -1 +1 @@\n-value = 0\n+value = 1",
    }]
    monkeypatch.setattr(pr_reviewer, "GitHubClient", Mock(return_value=client))
    agent = Mock()
    agent.review.return_value = "값을 바꾸세요"
    agent.suggest_changes.return_value = [{
        "line": 1, "original": "value = 1", "replacement": "value = 2", "reason": "개선"
    }]
    monkeypatch.setattr(pr_reviewer, "CodeReviewAgent", Mock(return_value=agent))
    pr_reviewer.main()
    client.post_suggestions.assert_called_once_with(1, "abc", [{
        "path": "a.py", "line": 1, "replacement": "value = 2", "reason": "개선"
    }])


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
    assert agent.review.call_args_list[0].kwargs["reflection_rounds"] == 1


def test_review_files_shows_reflection_trace(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n")
    agent = Mock()
    agent.review.return_value = "최종 리뷰"
    agent.last_review_trace = ReviewTrace("초안", ("근거를 보강하세요",), "최종 리뷰")

    body = review_files(["a.py"], tmp_path, agent)

    assert "최종 리뷰" in body
    assert "<summary>리뷰 개선 과정</summary>" in body
    assert "초안" in body
    assert "근거를 보강하세요" in body


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


def test_suggestion_comment_created_once_for_same_head():
    github = GitHubClient("token", "owner/repo")
    github.request = Mock(side_effect=[
        {"head": {"sha": "abc"}}, {"id": 7}, {"id": 44}
    ])
    github.pages = Mock(return_value=iter([]))
    suggestion = {"path": "a.py", "line": 2, "replacement": "    return 1", "reason": "수정"}
    github.post_suggestions(3, "abc", [suggestion])
    method, path, data = github.request.call_args.args
    assert (method, path) == ("POST", "/repos/owner/repo/pulls/3/comments")
    assert data["line"] == 2 and data["side"] == "RIGHT"
    assert "```suggestion\n    return 1\n```" in data["body"]

    github.request.reset_mock()
    github.request.side_effect = [{"head": {"sha": "abc"}}, {"id": 7}]
    github.pages = Mock(return_value=iter([{
        "path": "a.py", "line": 2, "body": data["body"],
        "commit_id": "abc", "user": {"id": 7},
    }]))
    github.post_suggestions(3, "abc", [suggestion])
    assert github.request.call_count == 2


def test_suggestion_skips_stale_head():
    github = GitHubClient("token", "owner/repo")
    github.request = Mock(return_value={"head": {"sha": "new"}})
    github.post_suggestions(3, "old", [{"path": "a.py"}])
    assert github.request.call_count == 1


def test_suggestion_updates_own_comment_instead_of_duplicating():
    github = GitHubClient("token", "owner/repo")
    github.request = Mock(side_effect=[
        {"head": {"sha": "abc"}}, {"id": 7}, {"id": 44}
    ])
    github.pages = Mock(return_value=iter([{
        "id": 12, "path": "a.py", "line": 2,
        "body": MARKER + pr_reviewer.SUGGESTION_MARKER,
        "commit_id": "abc", "user": {"id": 7},
    }]))
    github.post_suggestions(3, "abc", [{
        "path": "a.py", "line": 2, "replacement": "    return 2", "reason": "개선"
    }])
    assert github.request.call_args.args[:2] == (
        "PATCH", "/repos/owner/repo/pulls/comments/12"
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

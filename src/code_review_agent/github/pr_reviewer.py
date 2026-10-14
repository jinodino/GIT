"""Review changed Python files and maintain one PR issue comment."""

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from openai import OpenAIError

from code_review_agent.agent.reviewer import CodeReviewAgent
from code_review_agent.tools.file_reader import read_file

API_ROOT = "https://api.github.com"
MARKER = "<!-- code-review-agent:ai-review -->"
MAX_FILES = 5
MAX_BODY_LENGTH = 60_000


class GitHubAPIError(RuntimeError):
    """A GitHub request failed."""


class GitHubClient:
    def __init__(self, token: str, repository: str):
        if not token:
            raise ValueError("GITHUB_TOKEN이 필요합니다.")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("GITHUB_REPOSITORY 형식이 올바르지 않습니다.")
        self.token = token
        self.repository = repository
        self.base = f"/repos/{repository}"

    def request(self, method: str, path: str, data: dict | None = None):
        body = json.dumps(data).encode("utf-8") if data is not None else None
        request = urllib.request.Request(
            API_ROOT + path,
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "code-review-agent",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise GitHubAPIError(
                f"GitHub API {method} {path}: HTTP {error.code}"
            ) from error
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise GitHubAPIError(f"GitHub API {method} {path} 요청 실패") from error

    def pages(self, path: str):
        page = 1
        while True:
            separator = "&" if "?" in path else "?"
            items = self.request("GET", f"{path}{separator}per_page=100&page={page}")
            if not isinstance(items, list):
                raise GitHubAPIError("GitHub API 목록 응답 형식이 올바르지 않습니다.")
            yield from items
            if len(items) < 100:
                break
            page += 1

    def changed_python_files(self, number: int) -> list[str]:
        files = []
        for item in self.pages(f"{self.base}/pulls/{number}/files"):
            if not isinstance(item, dict):
                raise GitHubAPIError("변경 파일 응답 형식이 올바르지 않습니다.")
            name = item.get("filename")
            if item.get("status") != "removed" and isinstance(name, str) and name.endswith(".py"):
                files.append(name)
                if len(files) == MAX_FILES:
                    break
        return files

    def upsert_comment(self, number: int, body: str):
        if len(body) > MAX_BODY_LENGTH:
            raise ValueError("댓글 길이 제한을 초과했습니다.")
        # Actions uses an installation token; /user is not available to it.
        identity = self.request("GET", "/users/github-actions%5Bbot%5D")
        if not isinstance(identity, dict) or not isinstance(identity.get("id"), int):
            raise GitHubAPIError("현재 GitHub 계정 정보를 확인할 수 없습니다.")
        bot_id = identity["id"]
        for comment in self.pages(f"{self.base}/issues/{number}/comments"):
            if (
                isinstance(comment, dict)
                and isinstance(comment.get("user"), dict)
                and comment["user"].get("id") == bot_id
                and MARKER in comment.get("body", "")
            ):
                return self.request(
                    "PATCH", f"{self.base}/issues/comments/{comment['id']}", {"body": body}
                )
        return self.request("POST", f"{self.base}/issues/{number}/comments", {"body": body})


def review_files(paths: list[str], project_root: Path, agent: CodeReviewAgent) -> str:
    sections = [MARKER, "## AI Code Review"]
    for path in paths:
        # Paths and review text originate in an untrusted PR. Keep them as data.
        title = path.replace("\n", " ").replace("\r", " ").replace("`", "'")
        try:
            read_file(str(project_root), path)
            result = agent.review(path, max_iterations=5)
        except (OSError, UnicodeError, ValueError, RuntimeError, OpenAIError) as error:
            # Never publish exception details or secrets.
            result = f"리뷰 실패: {type(error).__name__}"
        section = f"### `{title}`\n\n{result}"
        remaining = MAX_BODY_LENGTH - len("\n\n".join(sections)) - 100
        if remaining <= 0:
            break
        sections.append(section[:remaining])
    sections.append("---\nAI가 생성한 리뷰이므로 개발자가 최종 확인해야 합니다.")
    return "\n\n".join(sections)


def main() -> None:
    repository = os.environ["GITHUB_REPOSITORY"]
    number = int(os.environ["PR_NUMBER"])
    if number < 1:
        raise ValueError("PR_NUMBER는 양수여야 합니다.")
    project_root = Path(os.environ["PROJECT_ROOT"]).resolve()
    github = GitHubClient(os.environ["GITHUB_TOKEN"], repository)
    paths = github.changed_python_files(number)
    if not paths:
        print("변경된 Python 파일이 없습니다.")
        return
    agent = CodeReviewAgent(project_root=str(project_root))
    github.upsert_comment(number, review_files(paths, project_root, agent))
    print(f"Python 파일 {len(paths)}개 리뷰 댓글을 등록하거나 갱신했습니다.")


if __name__ == "__main__":
    main()

from pathlib import Path


def search_code(
    project_root: str,
    keyword: str,
    max_results: int = 20,
) -> list[dict]:
    """프로젝트의 Python 파일에서 문자열을 검색한다."""

    root = Path(project_root).resolve()

    if not root.is_dir():
        raise ValueError("프로젝트 디렉터리가 없습니다.")

    if not keyword:
        raise ValueError("검색어가 비어 있습니다.")

    if not 1 <= max_results <= 100:
        raise ValueError("검색 결과 제한은 1~100이어야 합니다.")

    results = []

    for file in root.rglob("*.py"):
        if file.is_symlink() or not file.is_file():
            continue

        if not file.resolve().is_relative_to(root):
            continue

        if any(
            part in {".venv", "venv", ".git", "__pycache__"}
            for part in file.relative_to(root).parts
        ):
            continue

        if file.stat().st_size > 100_000:
            continue

        try:
            lines = file.read_text(encoding="utf-8").splitlines()
        except (UnicodeError, OSError):
            continue

        for line_number, line in enumerate(lines, start=1):
            if keyword in line:
                results.append({
                    "file_name": str(file.relative_to(root)),
                    "line": line_number,
                    "content": line.strip()[:300],
                })

                if len(results) >= max_results:
                    return results

    return results
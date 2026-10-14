from pathlib import Path


def read_file(project_root: str, file_path: str) -> str:
    """프로젝트 내부의 Python 파일을 읽는다."""

    root = Path(project_root).resolve()
    target = (root / file_path).resolve()

    if not target.is_relative_to(root):
        raise ValueError("프로젝트 외부 파일은 읽을 수 없습니다.")

    if target.suffix != ".py":
        raise ValueError("Python 파일만 읽을 수 있습니다.")

    if not target.is_file():
        raise FileNotFoundError(file_path)

    if target.stat().st_size > 100_000:
        raise ValueError("파일 크기 제한을 초과했습니다.")

    return target.read_text(encoding="utf-8")
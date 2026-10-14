import json
import subprocess
import sys
from pathlib import Path


def run_ruff(
    project_root: str,
    file_path: str,
) -> list[dict]:
    """Ruff를 이용해 Python 파일을 정적 분석한다."""

    root = Path(project_root).resolve()
    target = (root / file_path).resolve()

    if not target.is_relative_to(root):
        raise ValueError("프로젝트 외부 파일은 분석할 수 없습니다.")

    if target.suffix != ".py" or not target.is_file():
        raise ValueError("존재하는 Python 파일만 분석할 수 있습니다.")

    if target.stat().st_size > 100_000:
        raise ValueError("파일 크기 제한을 초과했습니다.")

    command = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--isolated",
        "--output-format",
        "json",
        "--",
        str(target),
    ]

    result = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    # 0: 문제 없음, 1: 문제 발견, 2 이상: 실행 오류
    if result.returncode not in (0, 1):
        raise RuntimeError(
            f"Ruff 실행 실패: {result.stderr[:500]}"
        )

    return json.loads(result.stdout)
from pathlib import Path

from dotenv import load_dotenv
from code_review_agent.agent.reviewer import CodeReviewAgent


def main():
    # 프로젝트 최상위 경로
    project_path = Path(__file__).resolve().parents[2]

    # .env 파일 로드
    load_dotenv(project_path / ".env")

    # 코드 리뷰 대상 프로젝트
    project_root = project_path / "sample_project"

    agent = CodeReviewAgent(
        project_root=str(project_root)
    )

    result = agent.review(
        file_name="calculator.py",
        max_iterations=5,
    )

    print("\n=== AI 코드 리뷰 결과 ===")
    print(result)


if __name__ == "__main__":
    main()
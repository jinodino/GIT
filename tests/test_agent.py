from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from code_review_agent.agent.reviewer import CodeReviewAgent


def test_agent_loop():
    project_root = (
        Path(__file__).resolve().parents[1]
        / "sample_project"
    )

    # 첫 번째 LLM 응답: read_file 요청
    first_response = SimpleNamespace(
        id="response_1",
        output=[
            SimpleNamespace(
                type="function_call",
                name="read_file",
                arguments='{"file_path":"calculator.py"}',
                call_id="call_1",
            )
        ],
        output_text="",
    )

    # 두 번째 LLM 응답: 최종 리뷰
    second_response = SimpleNamespace(
        id="response_2",
        output=[],
        output_text="미사용 import가 있습니다.",
    )

    mock_client = Mock()
    mock_client.responses.create.side_effect = [
        first_response,
        second_response,
    ]

    agent = CodeReviewAgent(
        project_root=str(project_root),
        client=mock_client,
    )

    result = agent.review(
        file_name="calculator.py",
        max_iterations=3,
    )

    assert result == "미사용 import가 있습니다."
    assert mock_client.responses.create.call_count == 2

    # 두 번째 API 호출에서 도구 결과가 전달되었는지 확인
    second_call = mock_client.responses.create.call_args_list[1]

    assert second_call.kwargs["previous_response_id"] == "response_1"
    assert second_call.kwargs["input"][0]["type"] == "function_call_output"
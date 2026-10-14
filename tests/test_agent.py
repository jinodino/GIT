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
        reflection_rounds=0,
    )

    assert result == "미사용 import가 있습니다."
    assert mock_client.responses.create.call_count == 2

    # 두 번째 API 호출에서 도구 결과가 전달되었는지 확인
    second_call = mock_client.responses.create.call_args_list[1]

    assert second_call.kwargs["previous_response_id"] == "response_1"
    assert second_call.kwargs["input"][0]["type"] == "function_call_output"


def test_reflection_creates_feedback_and_final_review():
    project_root = Path(__file__).resolve().parents[1] / "sample_project"
    responses = [
        SimpleNamespace(id="tool", output=[SimpleNamespace(
            type="function_call", name="read_file",
            arguments='{"file_path":"calculator.py"}', call_id="call_1"
        )], output_text=""),
        SimpleNamespace(id="draft", output=[], output_text="초안"),
        SimpleNamespace(id="critique", output=[], output_text="근거를 보강하세요"),
        SimpleNamespace(id="final", output=[], output_text="수정된 리뷰"),
    ]
    client = Mock()
    client.responses.create.side_effect = responses
    agent = CodeReviewAgent(str(project_root), client=client)

    assert agent.review("calculator.py") == "수정된 리뷰"
    assert client.responses.create.call_count == 4
    assert client.responses.create.call_args_list[2].kwargs["previous_response_id"] == "draft"
    assert client.responses.create.call_args_list[3].kwargs["previous_response_id"] == "critique"
    assert agent.last_review_trace.draft == "초안"
    assert agent.last_review_trace.feedback == ("근거를 보강하세요",)
    assert agent.last_review_trace.final == "수정된 리뷰"


def test_reflection_rounds_are_configurable():
    project_root = Path(__file__).resolve().parents[1] / "sample_project"
    outputs = [
        SimpleNamespace(id="draft", output=[], output_text="초안"),
        SimpleNamespace(id="c1", output=[], output_text="피드백1"),
        SimpleNamespace(id="r1", output=[], output_text="수정1"),
        SimpleNamespace(id="c2", output=[], output_text="피드백2"),
        SimpleNamespace(id="r2", output=[], output_text="수정2"),
    ]
    client = Mock()
    client.responses.create.side_effect = outputs
    agent = CodeReviewAgent(str(project_root), client=client)

    assert agent.review("calculator.py", reflection_rounds=2) == "수정2"
    assert agent.last_review_trace.feedback == ("피드백1", "피드백2")
    assert client.responses.create.call_count == 5


def test_suggest_changes_uses_review_and_changed_lines():
    project_root = Path(__file__).resolve().parents[1] / "sample_project"
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output_text='{"suggestions":[{"line":2,"original":"x = 1",'
        '"replacement":"x = 2","reason":"개선"}]}'
    )
    agent = CodeReviewAgent(str(project_root), client=client)
    assert agent.suggest_changes("calculator.py", "검토 결과", {2: "x = 1"})[0]["line"] == 2
    call = client.responses.create.call_args.kwargs
    assert "검토 결과" in call["input"]
    assert call["tool_choice"] == "none"
    client.responses.create.reset_mock()
    assert agent.suggest_changes("calculator.py", "검토 결과", {}) == []
    client.responses.create.assert_not_called()

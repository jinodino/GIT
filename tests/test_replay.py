from pathlib import Path

from code_review_agent.replay.trace import MAX_VALUE_LENGTH, FlowTrace, safe_value


def test_trace_masks_credentials_and_bounds_values(tmp_path: Path):
    trace = FlowTrace()
    trace.add(
        "비밀 테스트", "Agent", "LLM",
        "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456",
        "Bearer github_pat_abcdefghijklmnopqrstuvwxyz123456",
        "값을 기록",
    )
    output = tmp_path / "review-flow.html"
    trace.write_html(output)
    document = output.read_text(encoding="utf-8")

    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in document
    assert "github_pat_abcdefghijklmnopqrstuvwxyz123456" not in document
    assert "[비공개 값]" in document
    assert len(safe_value("a" * (MAX_VALUE_LENGTH + 100))) == MAX_VALUE_LENGTH


def test_trace_html_escapes_untrusted_script_content(tmp_path: Path):
    trace = FlowTrace()
    trace.add("리뷰 초안", "LLM", "Agent", "입력", "</script><script>alert(1)</script>", "처리")
    output = tmp_path / "flow.html"
    trace.write_html(output)
    document = output.read_text(encoding="utf-8")

    assert "__TRACE_EVENTS_JSON__" not in document
    assert "</script><script>alert(1)</script>" not in document
    assert "\\u003c/script>" in document
    assert document.count('<script id="trace-data"') == 1

from code_review_agent.github.suggestions import added_lines, validate_suggestions


def test_added_lines_across_hunks():
    patch = "@@ -1,2 +1,3 @@\n a = 1\n-old\n+new\n+extra\n@@ -10 +11 @@\n-again\n+last"
    assert added_lines(patch) == {2: "new", 3: "extra", 11: "last"}


def test_only_exact_changed_line_and_valid_python_accepted(tmp_path):
    (tmp_path / "a.py").write_text("def divide(a, b):\n    return a / b\n")
    patch = "@@ -1,2 +1,2 @@\n def divide(a, b):\n-    return a // b\n+    return a / b"
    proposals = [
        {"line": 2, "original": "    return a / b", "replacement": "    return a / (b or 1)", "reason": "0 방지"},
        {"line": 1, "original": "def divide(a, b):", "replacement": "def divide(a, b=1):", "reason": "문맥 줄"},
    ]
    assert validate_suggestions(tmp_path, "a.py", patch, proposals) == [{
        "path": "a.py", "line": 2, "replacement": "    return a / (b or 1)", "reason": "0 방지"
    }]
    proposals[0]["replacement"] = "    return ("
    assert validate_suggestions(tmp_path, "a.py", patch, proposals) == []


def test_stale_or_multiline_suggestions_rejected(tmp_path):
    (tmp_path / "a.py").write_text("value = 1\n")
    patch = "@@ -1 +1 @@\n-value = 0\n+value = 1"
    proposals = [
        {"line": 1, "original": "value = 0", "replacement": "value = 2", "reason": "stale"},
        {"line": 1, "original": "value = 1", "replacement": "value = 2\nprint(2)", "reason": "multi"},
    ]
    assert validate_suggestions(tmp_path, "a.py", patch, proposals) == []

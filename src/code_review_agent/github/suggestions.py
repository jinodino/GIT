"""Validate one-line GitHub suggested changes against the PR diff."""

import ast
import re
from pathlib import Path

from code_review_agent.tools.file_reader import read_file

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def added_lines(patch: str) -> dict[int, str]:
    """Map added right-side line numbers to their exact file text."""
    result = {}
    line_number = None
    for line in patch.splitlines():
        hunk = HUNK.match(line)
        if hunk:
            line_number = int(hunk.group(1))
        elif line_number is not None and line.startswith("+"):
            result[line_number] = line[1:]
            line_number += 1
        elif line_number is not None and line.startswith(" "):
            line_number += 1
        elif line.startswith(("\\", "-")):
            continue
    return result


def validate_suggestions(
    project_root: Path, file_name: str, patch: str, proposals: list[dict]
) -> list[dict]:
    """Reject stale, unrelated, multi-line, or syntactically invalid replacements."""
    source = read_file(str(project_root), file_name)
    lines = source.splitlines()
    changed = added_lines(patch)
    accepted = []
    seen = set()
    for proposal in proposals[:2]:
        if not isinstance(proposal, dict):
            continue
        number = proposal.get("line")
        original = proposal.get("original")
        replacement = proposal.get("replacement")
        reason = proposal.get("reason")
        if (
            type(number) is not int
            or number in seen
            or not isinstance(original, str)
            or not isinstance(replacement, str)
            or not isinstance(reason, str)
            or number < 1
            or number > len(lines)
            or changed.get(number) != original
            or lines[number - 1] != original
            or original == replacement
            or not replacement.strip()
            or "\n" in replacement
            or "\r" in replacement
            or "```" in replacement
            or len(replacement) > 300
        ):
            continue
        revised = lines.copy()
        revised[number - 1] = replacement
        try:
            ast.parse("\n".join(revised) + "\n")
        except SyntaxError:
            continue
        seen.add(number)
        accepted.append({
            "path": file_name,
            "line": number,
            "replacement": replacement,
            "reason": reason.replace("\n", " ").replace("\r", " ")[:500],
        })
    return accepted

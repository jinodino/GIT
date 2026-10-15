"""Collect bounded review events and render a self-contained HTML replay."""

import json
import re
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

MAX_VALUE_LENGTH = 2400
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{12,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{12,}\b"),
    re.compile(r"(?i)\bBearer\s+\S+"),
    re.compile(r"(?i)\b(?:OPENAI_API_KEY|GITHUB_TOKEN)\s*[:=]\s*\S+"),
)


def safe_value(value: object) -> str:
    """Bound display values and mask common credential formats."""
    result = str(value)
    for pattern in SECRET_PATTERNS:
        result = pattern.sub("[비공개 값]", result)
    return result[:MAX_VALUE_LENGTH]


@dataclass
class FlowTrace:
    events: list[dict[str, str | int]] = field(default_factory=list)

    def add(
        self, title: str, source: str, target: str,
        input_value: object, output_value: object, process: str,
    ) -> None:
        self.events.append({
            "step": len(self.events) + 1,
            "title": safe_value(title),
            "source": safe_value(source),
            "target": safe_value(target),
            "input": safe_value(input_value),
            "output": safe_value(output_value),
            "process": safe_value(process),
        })

    def write_html(self, output_path: Path) -> None:
        """Write an offline replay with the captured event data embedded."""
        template = files("code_review_agent.replay").joinpath("template.html").read_text(
            encoding="utf-8"
        )
        payload = json.dumps(self.events, ensure_ascii=False).replace("<", "\\u003c")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(template.replace("__TRACE_EVENTS_JSON__", payload), encoding="utf-8")

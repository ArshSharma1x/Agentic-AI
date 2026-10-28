"""Builds a standalone HTML replay of a match trace: no server, just open the file."""

import json
from pathlib import Path

from .trace import Trace

TEMPLATE = Path(__file__).with_name("ui_template.html")
MARK_START, MARK_END = "/*EVENTS*/", "/*END*/"


def build_html(events: list[dict]) -> str:
    template = TEMPLATE.read_text()
    head, rest = template.split(MARK_START, 1)
    tail = rest.split(MARK_END, 1)[1]
    payload = json.dumps(events).replace("</", "<\\/")  # a "</script>" inside a trace must not end the tag
    return head + payload + tail


def write_replay(trace_path: Path, out_path: Path) -> Path:
    out_path.write_text(build_html(Trace.load(trace_path)))
    return out_path

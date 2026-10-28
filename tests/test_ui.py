import json
import re

from squad.ui import build_html


def test_replay_embeds_the_events_and_survives_a_script_tag_in_the_trace():
    events = [{"type": "tool_result", "t": 0.1, "agent": "FORGE", "tool": "x", "ok": True, "preview": "</script><b>"}]
    html = build_html(events)
    assert html.count("</script>") == 1  # only the template's own closing tag
    payload = re.search(r"const EVENTS = (.*?);\nconst ROLE", html, re.S).group(1)
    assert json.loads(payload.replace("<\\/", "</")) == events

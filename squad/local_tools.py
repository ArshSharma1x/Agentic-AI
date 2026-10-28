"""Tools that run inside the orchestrator process, not over MCP: how agents hand in their work."""

LOCAL_TOOLS: dict[str, dict] = {
    "submit_intel": {
        "name": "submit_intel",
        "description": "Hand in your context brief. Call exactly once when you have gathered what the squad needs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "What the work is and why, in a few sentences."},
                "key_facts": {"type": "array", "items": {"type": "string"}, "description": "Rules, constraints and facts the implementer must respect."},
            },
            "required": ["summary", "key_facts"],
        },
    },
    "submit_plan": {
        "name": "submit_plan",
        "description": "Hand in the plan. Call exactly once.",
        "input_schema": {
            "type": "object",
            "properties": {
                "criteria": {"type": "array", "items": {"type": "string"}, "description": "Testable acceptance criteria."},
                "steps": {"type": "array", "items": {"type": "string"}, "description": "Implementation steps in order."},
            },
            "required": ["criteria", "steps"],
        },
    },
    "submit_work": {
        "name": "submit_work",
        "description": "Declare the implementation finished. Call exactly once, after running the tests yourself.",
        "input_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string", "description": "What you changed and how you checked it."}},
            "required": ["summary"],
        },
    },
    "submit_verdict": {
        "name": "submit_verdict",
        "description": "Give your verdict on the implementation. Call exactly once.",
        "input_schema": {
            "type": "object",
            "properties": {
                "passed": {"type": "boolean"},
                "issues": {"type": "array", "items": {"type": "string"}, "description": "Concrete problems. Empty if passed."},
            },
            "required": ["passed", "issues"],
        },
    },
}

import anthropic

from src.config import ANTHROPIC_API_KEY, PILLARS, SUB_TRACKS

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

EXTRACTION_TOOL = {
    "name": "log_extraction",
    "description": (
        "Extract the logging intent from a free-text message to a personal "
        "activity/time-tracking bot."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["start", "stop", "log_duration", "query", "unclear"],
                "description": (
                    "start = beginning an open-ended activity now. "
                    "stop = the user says they finished/are done with something "
                    "that was already running. "
                    "log_duration = the user reports a completed activity and its "
                    "duration in one message, with no open-ended timer involved. "
                    "query = asking about their own logged history/summary "
                    "(e.g. 'how did I do today'). "
                    "unclear = none of the above fit confidently."
                ),
            },
            "activity_name": {
                "type": "string",
                "description": "Short label for the activity, e.g. 'laundry', 'reading'.",
            },
            "pillar_guess": {
                "type": "string",
                "enum": PILLARS,
                "description": (
                    "Best-guess pillar. Use 'uncategorized' for chores or anything "
                    "you are not reasonably confident about - do not force a guess."
                ),
            },
            "sub_track_guess": {
                "type": ["string", "null"],
                "enum": SUB_TRACKS + [None],
                "description": "Only set when pillar_guess is 'relationships'.",
            },
            "duration_minutes": {
                "type": ["number", "null"],
                "description": "Only for intent=log_duration: the reported duration in minutes.",
            },
            "target_hint": {
                "type": ["string", "null"],
                "description": (
                    "Only for intent=stop: any text the user gave to identify WHICH "
                    "running activity they mean, e.g. 'laundry' in 'done with laundry'. "
                    "Null if they just said a bare 'done'/'finished'."
                ),
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
        },
        "required": ["intent", "activity_name", "pillar_guess", "confidence"],
        "additionalProperties": False,
    },
}


def extract_intent(raw_text: str, now_local_iso: str, open_activity_names: list[str]) -> dict:
    context = (
        f"Current local time: {now_local_iso}. "
        f"Currently open activities for this user: {open_activity_names or 'none'}."
    )
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "log_extraction"},
        messages=[{"role": "user", "content": f"{context}\n\nMessage: {raw_text!r}"}],
    )
    tool_use = next(b for b in response.content if b.type == "tool_use")
    return tool_use.input

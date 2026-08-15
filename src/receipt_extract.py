import base64

import anthropic

from src import api_usage
from src.config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

RECEIPT_EXTRACTION_TOOL = {
    "name": "log_receipt",
    "description": "Extract merchant, purchase date, total amount, and currency from a photo of a receipt.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "merchant": {"type": "string"},
            "purchased_at": {
                "type": ["string", "null"],
                "description": "ISO date YYYY-MM-DD if legible on the receipt, else null.",
            },
            "amount": {"type": ["number", "null"], "description": "The total amount charged."},
            "currency": {
                "type": ["string", "null"],
                "description": "ISO 4217 code, e.g. EUR, USD. Null if not determinable.",
            },
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["merchant", "purchased_at", "amount", "currency", "confidence"],
        "additionalProperties": False,
    },
}


def extract_receipt(image_bytes: bytes, media_type: str, caption: str | None) -> dict:
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    text_prompt = (
        f"Caption: {caption!r}. Extract the receipt's merchant, date, total amount, and currency."
        if caption
        else "No caption. Extract the receipt's merchant, date, total amount, and currency."
    )
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        tools=[RECEIPT_EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "log_receipt"},
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                    {"type": "text", "text": text_prompt},
                ],
            }
        ],
    )
    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None:
        raise RuntimeError("Claude did not return a tool_use block for receipt extraction (possible refusal)")
    api_usage.record(response, purpose="receipt_extract")
    return tool_use.input

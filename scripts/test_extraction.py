#!/usr/bin/env python3
"""Feed canned messages into claude_extract.extract_intent and print results.

Run this before wiring up Telegram at all -- it's the cheapest way to catch
misclassification on the NL parsing, the riskiest piece of the bot.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.claude_extract import extract_intent

NOW = "2026-08-12T19:30:00+02:00"

CASES = [
    {"text": "I started doing laundry", "open": [], "expect_intent": "start"},
    {"text": "I'm done", "open": ["laundry"], "expect_intent": "stop"},
    {"text": "finished", "open": [], "expect_intent": "stop"},
    {"text": "done with laundry", "open": ["laundry", "cooking"], "expect_intent": "stop"},
    {"text": "I've been doing this for 2 hours", "open": [], "expect_intent": "log_duration"},
    {"text": "read for 45 min", "open": [], "expect_intent": "log_duration"},
    {"text": "how did I do today", "open": [], "expect_intent": "query"},
    {"text": "asdkjh qweoiuqwe", "open": [], "expect_intent": "unclear"},
]

if __name__ == "__main__":
    failures = 0
    for case in CASES:
        result = extract_intent(case["text"], NOW, case["open"])
        ok = result.get("intent") == case["expect_intent"]
        if not ok:
            failures += 1
        status = "OK" if ok else "MISMATCH"
        print(f"[{status}] {case['text']!r} (open={case['open']})")
        print(f"       expected intent={case['expect_intent']!r}, got: {result}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} matched expected intent")
    sys.exit(1 if failures else 0)

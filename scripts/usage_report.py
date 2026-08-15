#!/usr/bin/env python3
"""Sum today's and this month's Claude API usage from api_usage and estimate
cost with hardcoded per-model pricing."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_conn

# Pricing per MTok (input, output). Haiku 4.5: $1/$5 (stable). Sonnet 5:
# $2/$10 intro through 2026-08-31, then $3/$15 -- update after that date.
PRICING = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (2.00, 10.00),  # TODO: bump to (3.00, 15.00) after 2026-08-31
}


def _summarize(since: str) -> tuple[int, int, float]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT model, input_tokens, output_tokens FROM api_usage WHERE called_at >= ?",
            (since,),
        ).fetchall()

    total_input = sum(r["input_tokens"] for r in rows)
    total_output = sum(r["output_tokens"] for r in rows)
    cost = 0.0
    for row in rows:
        in_price, out_price = PRICING.get(row["model"], (0.0, 0.0))
        cost += (row["input_tokens"] / 1_000_000) * in_price
        cost += (row["output_tokens"] / 1_000_000) * out_price
    return total_input, total_output, cost


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    today_start = now.strftime("%Y-%m-%dT00:00:00.000000Z")
    month_start = now.strftime("%Y-%m-01T00:00:00.000000Z")

    in_t, out_t, cost_t = _summarize(today_start)
    print(f"Today:      {in_t:>10} input tok, {out_t:>10} output tok, ~${cost_t:.4f}")

    in_m, out_m, cost_m = _summarize(month_start)
    print(f"This month: {in_m:>10} input tok, {out_m:>10} output tok, ~${cost_m:.4f}")

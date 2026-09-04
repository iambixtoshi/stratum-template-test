#!/usr/bin/env python3
"""Pull public Luxor and Bitcoin network data through 2026-09-01 UTC."""
from __future__ import annotations

import datetime as dt
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://mempool.space/api"
START = dt.datetime(2026, 8, 15, tzinfo=dt.timezone.utc)
END = dt.datetime(2026, 9, 2, tzinfo=dt.timezone.utc)  # exclusive
OUT = Path("results/luxor_extension_2026-08-15_to_2026-09-01.json")


def get(path: str):
    url = BASE + path
    for attempt in range(7):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "luxor-backtest-extension/1.0"}
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode()
            time.sleep(0.15)
            return json.loads(raw)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            if attempt == 6:
                raise RuntimeError(f"GET {url}: {exc}") from exc
            time.sleep(min(60, 2**attempt))


def height_at(when: dt.datetime) -> int:
    result = get(f"/v1/mining/blocks/timestamp/{int(when.timestamp())}")
    if isinstance(result, int):
        return result
    return int(result.get("height", result.get("blockHeight")))


start_height = height_at(START)
end_height = height_at(END)
before = end_height
blocks = {}

while before >= start_height:
    batch = get(f"/v1/mining/pool/luxor/blocks/{before}")
    if not batch:
        break
    oldest = before
    for block in batch:
        height = int(block["height"])
        oldest = min(oldest, height)
        timestamp = int(block.get("timestamp", 0))
        if int(START.timestamp()) <= timestamp < int(END.timestamp()):
            blocks[block["id"]] = block
    if oldest <= start_height:
        break
    before = oldest - 1

ordered_blocks = sorted(blocks.values(), key=lambda item: int(item["height"]))
payload = {
    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "source": BASE,
    "period_start": START.date().isoformat(),
    "period_end_inclusive": (END.date() - dt.timedelta(days=1)).isoformat(),
    "period_end_exclusive": END.date().isoformat(),
    "start_height": start_height,
    "end_height": end_height,
    "luxor_block_count": len(ordered_blocks),
    "luxor_blocks": ordered_blocks,
    "luxor_hashrate": get("/v1/mining/pool/luxor/hashrate"),
    "network_hashrate": get("/v1/mining/hashrate/3y"),
    "difficulty_adjustments": get("/v1/mining/difficulty-adjustments/3y"),
    "network_block_fees": get("/v1/mining/blocks/fees/3y"),
}

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(payload, indent=2))
print(
    json.dumps(
        {
            "output": str(OUT),
            "start_height": start_height,
            "end_height": end_height,
            "luxor_block_count": len(ordered_blocks),
        },
        indent=2,
    )
)

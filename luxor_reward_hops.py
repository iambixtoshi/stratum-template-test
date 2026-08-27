#!/usr/bin/env python3
"""Trace current mature Luxor and AntPool coinbase reward hops using mempool.space."""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://mempool.space/api"
USER_AGENT = "luxor-reward-hop-audit/1.0"
LUXOR_LIMIT = 12
ANTPOOL_LIMIT = 40
SLEEP = 0.18
cache = {}


def get(path, json_result=True):
    url = BASE + path
    if url in cache:
        return cache[url]
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=40) as response:
                raw = response.read().decode()
            value = json.loads(raw) if json_result else raw.strip()
            cache[url] = value
            time.sleep(SLEEP)
            return value
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            if attempt == 5:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(url)


def pool_blocks(slug, tip, limit):
    selected = []
    before = None
    seen = set()
    while len(selected) < limit:
        suffix = f"/{before}" if before is not None else ""
        batch = get(f"/v1/mining/pool/{slug}/blocks{suffix}")
        if not batch:
            break
        for block in batch:
            height = int(block["height"])
            if height <= tip - 100 and block["id"] not in seen:
                selected.append(block)
                seen.add(block["id"])
                if len(selected) >= limit:
                    break
        oldest = min(int(block["height"]) for block in batch)
        before = oldest - 1
    return selected


def printable(hex_string):
    try:
        return "".join(chr(b) if 32 <= b < 127 else "." for b in bytes.fromhex(hex_string))
    except Exception:
        return ""


def coinbase_tag(tx):
    vin = tx.get("vin") or []
    return printable(vin[0].get("scriptsig", "")) if vin else ""


def destination(vout):
    return vout.get("scriptpubkey_address") or vout.get("scriptpubkey")


def is_spendable(vout):
    return bool(vout.get("value", 0)) and vout.get("scriptpubkey_type") != "op_return"


def tx(txid):
    return get(f"/tx/{txid}")


def outspends(txid):
    return get(f"/tx/{txid}/outspends")


def block_coinbase(block):
    coinbase_txid = get(f"/block/{block['id']}/txid/0", json_result=False)
    coinbase = tx(coinbase_txid)
    return coinbase_txid, coinbase


def classify_tag(tag):
    low = tag.lower()
    if "antpool" in low:
        return "antpool"
    if "luxor" in low:
        return "luxor"
    if "poolin" in low:
        return "poolin"
    if "binance" in low:
        return "binance"
    if "ultimus" in low:
        return "ultimus"
    if "secpool" in low:
        return "secpool"
    if "braiins" in low or "slush" in low:
        return "braiins"
    return "other"


def trace_block(block, pool):
    coinbase_txid, coinbase = block_coinbase(block)
    spends = outspends(coinbase_txid)
    first_spend_txids = sorted({
        spend.get("txid")
        for index, spend in enumerate(spends)
        if index < len(coinbase.get("vout", []))
        and is_spendable(coinbase["vout"][index])
        and spend.get("spent")
        and spend.get("txid")
    })
    first_destinations = set()
    second_destinations = set()
    input_pool_tags = set()
    direct_cospend = False
    spend_details = []

    for spend_txid in first_spend_txids:
        spend_tx = tx(spend_txid)
        destinations = {
            destination(vout) for vout in spend_tx.get("vout", [])
            if is_spendable(vout) and destination(vout)
        }
        first_destinations.update(destinations)

        input_tags = []
        for vin in spend_tx.get("vin", []):
            previous_txid = vin.get("txid")
            if not previous_txid:
                continue
            previous = tx(previous_txid)
            previous_vin = previous.get("vin") or []
            if previous_vin and previous_vin[0].get("is_coinbase"):
                tag = coinbase_tag(previous)
                label = classify_tag(tag)
                input_pool_tags.add(label)
                input_tags.append({"pool": label, "tag": tag[:140], "txid": previous_txid})
        labels = {item["pool"] for item in input_tags}
        if "luxor" in labels and "antpool" in labels:
            direct_cospend = True

        next_spends = outspends(spend_txid)
        second_txids = sorted({
            item.get("txid") for idx, item in enumerate(next_spends)
            if idx < len(spend_tx.get("vout", []))
            and is_spendable(spend_tx["vout"][idx])
            and item.get("spent") and item.get("txid")
        })
        for second_txid in second_txids:
            second_tx = tx(second_txid)
            second_destinations.update({
                destination(vout) for vout in second_tx.get("vout", [])
                if is_spendable(vout) and destination(vout)
            })

        spend_details.append({
            "txid": spend_txid,
            "input_coinbase_tags": input_tags,
            "destinations": sorted(destinations),
            "second_spend_txids": second_txids,
        })

    return {
        "pool": pool,
        "height": block["height"],
        "block_hash": block["id"],
        "timestamp": block.get("timestamp"),
        "coinbase_txid": coinbase_txid,
        "coinbase_tag": coinbase_tag(coinbase)[:180],
        "first_spend_txids": first_spend_txids,
        "first_destinations": sorted(first_destinations),
        "second_destinations": sorted(second_destinations),
        "coinbase_input_pool_tags_in_first_spends": sorted(input_pool_tags),
        "direct_luxor_antpool_cospend": direct_cospend,
        "spend_details": spend_details,
    }


tip = int(get("/blocks/tip/height", json_result=False))
luxor_blocks = pool_blocks("luxor", tip, LUXOR_LIMIT)
antpool_blocks = pool_blocks("antpool", tip, ANTPOOL_LIMIT)

records = {"luxor": [], "antpool": []}
errors = []
for pool, blocks in (("luxor", luxor_blocks), ("antpool", antpool_blocks)):
    for block in blocks:
        try:
            records[pool].append(trace_block(block, pool))
        except Exception as exc:
            errors.append({"pool": pool, "height": block["height"], "error": f"{type(exc).__name__}: {exc}"})

luxor_first = {x for r in records["luxor"] for x in r["first_destinations"]}
antpool_first = {x for r in records["antpool"] for x in r["first_destinations"]}
luxor_second = {x for r in records["luxor"] for x in r["second_destinations"]}
antpool_second = {x for r in records["antpool"] for x in r["second_destinations"]}
direct = [
    {"height": r["height"], "block_hash": r["block_hash"], "spends": r["first_spend_txids"]}
    for r in records["luxor"] if r["direct_luxor_antpool_cospend"]
]
summary = {
    "tested_at_unix": time.time(),
    "chain_tip": tip,
    "maturity_cutoff_height": tip - 100,
    "requested_blocks": {"luxor": LUXOR_LIMIT, "antpool": ANTPOOL_LIMIT},
    "analyzed_blocks": {pool: len(items) for pool, items in records.items()},
    "spent_coinbases": {
        pool: sum(bool(item["first_spend_txids"]) for item in items)
        for pool, items in records.items()
    },
    "direct_luxor_antpool_cospend_count": len(direct),
    "direct_luxor_antpool_cospends": direct,
    "shared_first_hop_destinations": sorted(luxor_first & antpool_first),
    "shared_second_hop_destinations": sorted(luxor_second & antpool_second),
    "errors": errors,
}
if direct:
    verdict = "SHARED TREASURY EVIDENCE: Luxor and AntPool coinbases were inputs to the same consolidation transaction."
elif summary["shared_first_hop_destinations"]:
    verdict = "SHARED FIRST-HOP EVIDENCE: sampled Luxor and AntPool coinbases reached at least one identical first-hop destination."
elif summary["shared_second_hop_destinations"]:
    verdict = "SHARED SECOND-HOP EVIDENCE: sampled Luxor and AntPool reward flows reached at least one identical second-hop destination."
else:
    verdict = "NO SHARED HOP FOUND IN THIS SAMPLE. This does not prove separate ownership or custody."
summary["verdict"] = verdict

output = {"summary": summary, "records": records}
Path("results").mkdir(exist_ok=True)
Path("results/luxor_reward_hops.json").write_text(json.dumps(output, indent=2))
lines = [
    "# Luxor vs AntPool reward-hop audit",
    "",
    f"- Verdict: **{verdict}**",
    f"- Chain tip: {tip}",
    f"- Mature-block cutoff: {tip - 100}",
    f"- Luxor blocks analyzed: {len(records['luxor'])}",
    f"- AntPool blocks analyzed: {len(records['antpool'])}",
    f"- Spent Luxor coinbases: {summary['spent_coinbases']['luxor']}",
    f"- Spent AntPool coinbases: {summary['spent_coinbases']['antpool']}",
    f"- Direct mixed-pool consolidation transactions: {len(direct)}",
    f"- Shared first-hop destinations: {len(summary['shared_first_hop_destinations'])}",
    f"- Shared second-hop destinations: {len(summary['shared_second_hop_destinations'])}",
    "",
    "This audit is independent of block-template similarity. A negative sample does not prove separate custody.",
    "",
    "## Shared first-hop destinations",
    "",
    *[f"- {value}" for value in summary["shared_first_hop_destinations"]],
    "",
    "## Shared second-hop destinations",
    "",
    *[f"- {value}" for value in summary["shared_second_hop_destinations"]],
    "",
    "## Errors",
    "",
    "~~~json",
    json.dumps(errors, indent=2),
    "~~~",
]
Path("results/LUXOR_REWARD_HOPS.md").write_text("\n".join(lines) + "\n")
print(json.dumps(summary, indent=2))

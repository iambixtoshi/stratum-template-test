#!/usr/bin/env python3
"""Compare Luxor and AntPool coinbase-reward graphs across defined periods.

The script uses only public mempool.space APIs. It records all destinations at
each visited transaction and recursively follows a bounded set of high-value
outputs for up to five hops. This avoids treating a pool's miner payout fan-out
as thousands of treasury-controlled branches.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.getenv("MEMPOOL_API", "https://mempool.space/api")
USER_AGENT = "antpool-friends-reward-audit/2.0"
MAX_HOPS = int(os.getenv("MAX_HOPS", "5"))
MAX_RECURSIVE_OUTPUTS = int(os.getenv("MAX_RECURSIVE_OUTPUTS", "3"))
FANOUT_STOP = int(os.getenv("FANOUT_STOP", "50"))
MIN_VALUE_FRACTION = float(os.getenv("MIN_VALUE_FRACTION", "0.05"))
LUXOR_LIMIT = int(os.getenv("LUXOR_LIMIT", "25"))
ANTPOOL_LIMIT = int(os.getenv("ANTPOOL_LIMIT", "100"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "0.16"))
PERIOD_FILTER = {x.strip() for x in os.getenv("AUDIT_PERIODS", "pre_change,post_change,current").split(",") if x.strip()}
CACHE_PATH = Path(os.getenv("AUDIT_CACHE", "results/api_cache.json"))
cache: dict[str, object] = {}
KNOWN_SERVICE_ADDRESSES = {
    "bc1qn2cpj0hrl37wqh5q94kwrlhtj2lx8ahtw7ef5rg35tswxsqtvufqfmmrq2": {
        "entity": "OKX",
        "label": "Hot Wallet_41442",
        "source": "https://www.oklink.com/bitcoin/address/bc1qn2cpj0hrl37wqh5q94kwrlhtj2lx8ahtw7ef5rg35tswxsqtvufqfmmrq2/balance",
    }
}


def utc_timestamp(value: str) -> int:
    return int(dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc).timestamp())


today = dt.datetime.now(dt.timezone.utc).date()
periods = {
    "pre_change": (utc_timestamp("2023-09-08"), utc_timestamp("2023-12-07")),
    "post_change": (utc_timestamp("2023-12-08"), utc_timestamp("2024-03-08")),
    "current": (
        int(dt.datetime.combine(today - dt.timedelta(days=90), dt.time(), tzinfo=dt.timezone.utc).timestamp()),
        int(dt.datetime.combine(today + dt.timedelta(days=1), dt.time(), tzinfo=dt.timezone.utc).timestamp()),
    ),
}


def load_cache() -> None:
    global cache
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text())
        except Exception:
            cache = {}


def save_cache() -> None:
    CACHE_PATH.parent.mkdir(exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache))


def get(path: str, json_result: bool = True):
    url = BASE + path
    if url in cache:
        return cache[url]
    for attempt in range(7):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=45) as response:
                raw = response.read().decode()
            result = json.loads(raw) if json_result else raw.strip()
            cache[url] = result
            if len(cache) % 100 == 0:
                save_cache()
            time.sleep(REQUEST_DELAY)
            return result
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            if attempt == 6:
                raise RuntimeError(f"GET {url}: {exc}") from exc
            time.sleep(min(45, 2 ** attempt))


def height_at(timestamp: int) -> int:
    result = get(f"/v1/mining/blocks/timestamp/{timestamp}")
    if isinstance(result, int):
        return result
    if isinstance(result, dict):
        for key in ("height", "blockHeight"):
            if key in result:
                return int(result[key])
    raise ValueError(f"Unexpected height response: {result!r}")


def evenly_sample(items: list[dict], limit: int) -> list[dict]:
    if len(items) <= limit:
        return items
    if limit == 1:
        return [items[len(items) // 2]]
    indices = {round(i * (len(items) - 1) / (limit - 1)) for i in range(limit)}
    return [items[i] for i in sorted(indices)]


def pool_blocks(slug: str, start: int, end: int, tip: int, limit: int) -> list[dict]:
    start_height = height_at(start)
    end_height = min(height_at(end), tip - 100)
    before = end_height
    candidates: list[dict] = []
    seen: set[str] = set()
    while before >= start_height:
        batch = get(f"/v1/mining/pool/{slug}/blocks/{before}")
        if not batch:
            break
        oldest = before
        for block in batch:
            height = int(block["height"])
            oldest = min(oldest, height)
            timestamp = int(block.get("timestamp", 0))
            if start <= timestamp < end and height <= tip - 100 and block["id"] not in seen:
                candidates.append(block)
                seen.add(block["id"])
        if oldest <= start_height:
            break
        before = oldest - 1
    candidates.sort(key=lambda x: int(x["height"]))
    return evenly_sample(candidates, limit)


def tx(txid: str) -> dict:
    return get(f"/tx/{txid}")


def outspends(txid: str) -> list[dict]:
    return get(f"/tx/{txid}/outspends")


def printable(hex_string: str) -> str:
    try:
        return "".join(chr(b) if 32 <= b < 127 else "." for b in bytes.fromhex(hex_string))
    except Exception:
        return ""


def coinbase_tag(transaction: dict) -> str:
    vin = transaction.get("vin") or []
    return printable(vin[0].get("scriptsig", "")) if vin else ""


def classify_tag(tag: str) -> str:
    low = tag.lower()
    labels = {
        "antpool": ("antpool",), "luxor": ("luxor",), "poolin": ("poolin",),
        "binance": ("binance",), "ultimus": ("ultimus",), "secpool": ("secpool",),
        "braiins": ("braiins", "slush"), "btc.com": ("btc.com", "btccom"),
    }
    for label, needles in labels.items():
        if any(needle in low for needle in needles):
            return label
    return "other"


def destination(vout: dict) -> str | None:
    return vout.get("scriptpubkey_address") or vout.get("scriptpubkey")


def spendable(vout: dict) -> bool:
    return bool(vout.get("value", 0)) and vout.get("scriptpubkey_type") != "op_return"


def input_coinbase_labels(transaction: dict) -> list[dict]:
    labels = []
    for vin in transaction.get("vin", []):
        previous_txid = vin.get("txid")
        if not previous_txid:
            continue
        previous = tx(previous_txid)
        previous_vin = previous.get("vin") or []
        if previous_vin and previous_vin[0].get("is_coinbase"):
            tag = coinbase_tag(previous)
            labels.append({"pool": classify_tag(tag), "tag": tag[:160], "txid": previous_txid})
    return labels


def recursive_candidates(transaction: dict, spends: list[dict]) -> tuple[list[tuple[int, str]], str | None]:
    outputs = [
        (index, int(vout.get("value", 0)), spends[index].get("txid"))
        for index, vout in enumerate(transaction.get("vout", []))
        if index < len(spends) and spendable(vout) and spends[index].get("spent") and spends[index].get("txid")
    ]
    if len(transaction.get("vout", [])) > FANOUT_STOP:
        return [], f"fanout>{FANOUT_STOP}"
    total = sum(value for _, value, _ in outputs) or 1
    outputs.sort(key=lambda item: item[1], reverse=True)
    selected = [item for item in outputs if item[1] / total >= MIN_VALUE_FRACTION][:MAX_RECURSIVE_OUTPUTS]
    if outputs and not selected:
        selected = outputs[:1]
    return [(index, txid) for index, _, txid in selected], None


def walk_transaction(txid: str, hop: int, graph: dict, visited: set[str]) -> None:
    if txid in visited or hop > MAX_HOPS:
        return
    visited.add(txid)
    transaction = tx(txid)
    outputs = [
        {"index": i, "value": vout.get("value"), "destination": destination(vout), "type": vout.get("scriptpubkey_type")}
        for i, vout in enumerate(transaction.get("vout", [])) if spendable(vout)
    ]
    graph["txids_by_hop"].setdefault(str(hop), []).append(txid)
    graph["addresses_by_hop"].setdefault(str(hop), []).extend(
        item["destination"] for item in outputs if item["destination"]
    )
    spends = outspends(txid)
    candidates, pruned = recursive_candidates(transaction, spends)
    graph["transactions"][txid] = {
        "hop": hop,
        "outputs": outputs,
        "input_coinbases": input_coinbase_labels(transaction) if hop == 1 else [],
        "recursive_outputs": [{"vout": index, "spend_txid": child} for index, child in candidates],
        "pruned": pruned,
    }
    for _, child in candidates:
        walk_transaction(child, hop + 1, graph, visited)


def trace_block(block: dict, pool: str) -> dict:
    coinbase_txid = get(f"/block/{block['id']}/txid/0", json_result=False)
    coinbase = tx(coinbase_txid)
    spends = outspends(coinbase_txid)
    first_spends = sorted({
        spend.get("txid") for index, spend in enumerate(spends)
        if index < len(coinbase.get("vout", [])) and spendable(coinbase["vout"][index])
        and spend.get("spent") and spend.get("txid")
    })
    graph = {"txids_by_hop": {}, "addresses_by_hop": {}, "transactions": {}}
    visited: set[str] = set()
    for first in first_spends:
        walk_transaction(first, 1, graph, visited)
    for values in graph["addresses_by_hop"].values():
        values[:] = sorted(set(values))
    for values in graph["txids_by_hop"].values():
        values[:] = sorted(set(values))
    direct_labels = {
        item["pool"] for node in graph["transactions"].values()
        for item in node.get("input_coinbases", [])
    }
    return {
        "pool": pool, "height": block["height"], "block_hash": block["id"],
        "timestamp": block.get("timestamp"), "coinbase_txid": coinbase_txid,
        "coinbase_tag": coinbase_tag(coinbase)[:180], "first_spend_txids": first_spends,
        "direct_input_pool_labels": sorted(direct_labels), "graph": graph,
    }


def aggregate(records: list[dict]) -> dict:
    txids: set[str] = set()
    addresses: set[str] = set()
    by_hop_tx: dict[str, set[str]] = {}
    by_hop_address: dict[str, set[str]] = {}
    for record in records:
        for hop, values in record["graph"]["txids_by_hop"].items():
            by_hop_tx.setdefault(hop, set()).update(values); txids.update(values)
        for hop, values in record["graph"]["addresses_by_hop"].items():
            by_hop_address.setdefault(hop, set()).update(values); addresses.update(values)
    return {
        "txids": sorted(txids), "addresses": sorted(addresses),
        "txids_by_hop": {k: sorted(v) for k, v in by_hop_tx.items()},
        "addresses_by_hop": {k: sorted(v) for k, v in by_hop_address.items()},
    }


def compare(luxor_records: list[dict], antpool_records: list[dict]) -> dict:
    luxor, antpool = aggregate(luxor_records), aggregate(antpool_records)
    shared_txids = sorted(set(luxor["txids"]) & set(antpool["txids"]))
    shared_addresses = sorted(set(luxor["addresses"]) & set(antpool["addresses"]))
    service_matches = [
        {"address": address, **KNOWN_SERVICE_ADDRESSES[address]}
        for address in shared_addresses if address in KNOWN_SERVICE_ADDRESSES
    ]
    unattributed_matches = [address for address in shared_addresses if address not in KNOWN_SERVICE_ADDRESSES]
    direct = []
    for record in luxor_records:
        if {"luxor", "antpool"}.issubset(set(record["direct_input_pool_labels"])):
            direct.append({"height": record["height"], "first_spends": record["first_spend_txids"]})
    depth_matches = []
    for l_hop, l_values in luxor["addresses_by_hop"].items():
        for a_hop, a_values in antpool["addresses_by_hop"].items():
            common = sorted(set(l_values) & set(a_values))
            if common:
                depth_matches.append({"luxor_hop": int(l_hop), "antpool_hop": int(a_hop), "addresses": common})
    return {
        "direct_mixed_coinbase_consolidations": direct,
        "shared_transaction_nodes": shared_txids,
        "shared_addresses_any_hop": shared_addresses,
        "shared_known_service_addresses": service_matches,
        "shared_unattributed_addresses": unattributed_matches,
        "shared_addresses_by_depth": depth_matches,
        "luxor_graph_counts": {"transactions": len(luxor["txids"]), "addresses": len(luxor["addresses"])},
        "antpool_graph_counts": {"transactions": len(antpool["txids"]), "addresses": len(antpool["addresses"])},
    }


load_cache()
tip = int(get("/blocks/tip/height", json_result=False))
result = {
    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "method": {
        "max_hops": MAX_HOPS, "fanout_stop": FANOUT_STOP,
        "max_recursive_outputs": MAX_RECURSIVE_OUTPUTS, "min_value_fraction": MIN_VALUE_FRACTION,
        "maturity_cutoff": tip - 100,
    },
    "periods": {},
}
for period_name, (start, end) in periods.items():
    if period_name not in PERIOD_FILTER:
        continue
    period_result = {"start": start, "end": end, "pools": {}, "errors": []}
    for pool, slug, limit in (("luxor", "luxor", LUXOR_LIMIT), ("antpool", "antpool", ANTPOOL_LIMIT)):
        blocks = pool_blocks(slug, start, end, tip, limit)
        records = []
        for index, block in enumerate(blocks, 1):
            try:
                records.append(trace_block(block, pool))
                print(f"{period_name} {pool}: {index}/{len(blocks)} height={block['height']}", flush=True)
            except Exception as exc:
                period_result["errors"].append({"pool": pool, "height": block.get("height"), "error": str(exc)})
        period_result["pools"][pool] = {"candidate_count": len(blocks), "records": records}
    period_result["comparison"] = compare(
        period_result["pools"]["luxor"]["records"], period_result["pools"]["antpool"]["records"]
    )
    result["periods"][period_name] = period_result
    save_cache()

Path("results").mkdir(exist_ok=True)
Path("results/reward_cluster_audit.json").write_text(json.dumps(result, indent=2))
summary = ["# Luxor and AntPool reward-cluster audit", "", f"Generated: {result['generated_at']}", ""]
for name, period in result["periods"].items():
    comparison = period["comparison"]
    summary.extend([
        f"## {name.replace('_', ' ').title()}", "",
        f"- Luxor coinbases analyzed: {len(period['pools']['luxor']['records'])}",
        f"- AntPool coinbases analyzed: {len(period['pools']['antpool']['records'])}",
        f"- Direct mixed-pool consolidations: {len(comparison['direct_mixed_coinbase_consolidations'])}",
        f"- Shared transaction nodes: {len(comparison['shared_transaction_nodes'])}",
        f"- Shared addresses within five hops: {len(comparison['shared_addresses_any_hop'])}",
        f"- Shared known exchange/service addresses: {len(comparison['shared_known_service_addresses'])}",
        f"- Shared unattributed addresses: {len(comparison['shared_unattributed_addresses'])}",
        f"- API/trace errors: {len(period['errors'])}", "",
    ])
    if comparison["shared_known_service_addresses"]:
        summary.extend(["Known downstream services:", ""] + [
            f"- `{item['address']}`: {item['entity']} {item['label']}"
            for item in comparison["shared_known_service_addresses"]
        ] + [""])
    if comparison["shared_unattributed_addresses"]:
        summary.extend(["Unattributed shared addresses requiring investigation:", ""] + [
            f"- `{address}`" for address in comparison["shared_unattributed_addresses"]
        ] + [""])
Path("results/REWARD_CLUSTER_AUDIT.md").write_text("\n".join(summary) + "\n")
save_cache()
print(json.dumps({name: data["comparison"] for name, data in result["periods"].items()}, indent=2))

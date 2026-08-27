#!/usr/bin/env python3
"""Capture and compare live Stratum V1 jobs from Luxor Pool and AntPool."""
import json
import os
import socket
import statistics
import threading
import time
from pathlib import Path

DURATION = int(os.getenv("DURATION", "420"))
PAIR_WINDOW = int(os.getenv("PAIR_WINDOW", "45"))
POOLS = {
    "luxor": {
        "host": "stratum.luxor.com",
        "port": 3333,
        "user": os.getenv("LUXOR_USER", "publicobserver.worker"),
    },
    "antpool": {
        "host": "btc.antpool.com",
        "port": 3333,
        "user": os.getenv("ANTPOOL_USER", "publicobserver.worker"),
    },
}
jobs = {name: [] for name in POOLS}
diagnostics = {name: {"responses": [], "errors": []} for name in POOLS}
lock = threading.Lock()


def printable_hex(*parts):
    try:
        raw = bytes.fromhex("".join(parts))
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in raw)
        return text[:300]
    except Exception as exc:
        return f"<decode-error:{exc}>"


def weighted_similarity(a, b):
    """0xB10C weighted similarity: sum(1 / 2**(1+l-i)), i is one-indexed."""
    length = min(len(a), len(b))
    return sum(
        0.5 ** (length - index)
        for index in range(length)
        if a[index] == b[index]
    )


def listen(name, cfg):
    sock = None
    try:
        sock = socket.create_connection((cfg["host"], cfg["port"]), timeout=20)
        sock.settimeout(10)
        subscribe = {
            "id": 1,
            "method": "mining.subscribe",
            "params": ["public-template-observer/1.0"],
        }
        authorize = {
            "id": 2,
            "method": "mining.authorize",
            "params": [cfg["user"], "x"],
        }
        sock.sendall((json.dumps(subscribe) + "\n").encode())
        sock.sendall((json.dumps(authorize) + "\n").encode())

        buffer = b""
        deadline = time.time() + DURATION
        while time.time() < deadline:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                diagnostics[name]["errors"].append("server closed connection")
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if not line:
                    continue
                try:
                    message = json.loads(line.decode(errors="replace"))
                except Exception as exc:
                    diagnostics[name]["errors"].append(f"JSON decode: {exc}")
                    continue

                if message.get("method") != "mining.notify":
                    diagnostics[name]["responses"].append(message)
                    continue

                params = message.get("params", [])
                if len(params) < 9:
                    diagnostics[name]["errors"].append(
                        f"short mining.notify params: {len(params)}"
                    )
                    continue

                job = {
                    "captured_at": time.time(),
                    "job_id": params[0],
                    "prev_hash": params[1],
                    "coinbase1": params[2],
                    "coinbase2": params[3],
                    "merkle_branches": params[4],
                    "version": params[5],
                    "nbits": params[6],
                    "ntime": params[7],
                    "clean_jobs": params[8],
                    "coinbase_printable": printable_hex(params[2], params[3]),
                }
                with lock:
                    jobs[name].append(job)
                print(
                    f"{name}: job={job['job_id']} branches={len(job['merkle_branches'])} "
                    f"prev={job['prev_hash'][-12:]} tag={job['coinbase_printable'][:100]}",
                    flush=True,
                )
    except Exception as exc:
        diagnostics[name]["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


threads = [
    threading.Thread(target=listen, args=(name, cfg), daemon=True)
    for name, cfg in POOLS.items()
]
started_at = time.time()
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
finished_at = time.time()

pairs = []
for luxor_job in jobs["luxor"]:
    candidates = [
        antpool_job
        for antpool_job in jobs["antpool"]
        if antpool_job["prev_hash"] == luxor_job["prev_hash"]
        and abs(antpool_job["captured_at"] - luxor_job["captured_at"]) <= PAIR_WINDOW
    ]
    if not candidates:
        continue
    antpool_job = min(
        candidates,
        key=lambda item: abs(item["captured_at"] - luxor_job["captured_at"]),
    )
    a = luxor_job["merkle_branches"]
    b = antpool_job["merkle_branches"]
    common_length = min(len(a), len(b))
    exact_positions = [index for index in range(common_length) if a[index] == b[index]]
    pairs.append(
        {
            "time_delta_seconds": round(
                abs(antpool_job["captured_at"] - luxor_job["captured_at"]), 3
            ),
            "prev_hash": luxor_job["prev_hash"],
            "luxor_job_id": luxor_job["job_id"],
            "antpool_job_id": antpool_job["job_id"],
            "luxor_branch_count": len(a),
            "antpool_branch_count": len(b),
            "matching_positions_zero_indexed": exact_positions,
            "matching_branch_count": len(exact_positions),
            "weighted_similarity": weighted_similarity(a, b),
            "identical_branch_lists": a == b,
            "luxor_coinbase_printable": luxor_job["coinbase_printable"],
            "antpool_coinbase_printable": antpool_job["coinbase_printable"],
        }
    )

scores = [pair["weighted_similarity"] for pair in pairs]
identical_count = sum(pair["identical_branch_lists"] for pair in pairs)
summary = {
    "started_at_unix": started_at,
    "finished_at_unix": finished_at,
    "duration_seconds": round(finished_at - started_at, 3),
    "endpoints": {
        name: f"{cfg['host']}:{cfg['port']}" for name, cfg in POOLS.items()
    },
    "job_counts": {name: len(items) for name, items in jobs.items()},
    "paired_comparisons": len(pairs),
    "mean_weighted_similarity": statistics.mean(scores) if scores else None,
    "median_weighted_similarity": statistics.median(scores) if scores else None,
    "minimum_weighted_similarity": min(scores) if scores else None,
    "maximum_weighted_similarity": max(scores) if scores else None,
    "identical_template_pairs": identical_count,
    "diagnostics": diagnostics,
}

if not jobs["luxor"] or not jobs["antpool"]:
    verdict = "INCONCLUSIVE: one or both endpoints supplied no observable jobs."
elif not pairs:
    verdict = "INCONCLUSIVE: jobs were captured but no same-tip pairs fell within the pairing window."
elif summary["mean_weighted_similarity"] >= 0.80 or identical_count / len(pairs) >= 0.50:
    verdict = "CONSISTENT WITH SHARED/PROXIED TEMPLATES during this observation window."
elif summary["mean_weighted_similarity"] < 0.10 and identical_count == 0:
    verdict = "CONSISTENT WITH INDEPENDENT TEMPLATES during this observation window."
else:
    verdict = "PARTIAL/AMBIGUOUS SIMILARITY: longer sampling and branch-position analysis are required."

summary["verdict"] = verdict
output = {
    "summary": summary,
    "pairs": pairs,
    "jobs": jobs,
}
Path("results").mkdir(exist_ok=True)
Path("results/stratum_comparison.json").write_text(json.dumps(output, indent=2))

lines = [
    "# Luxor vs AntPool live Stratum comparison",
    "",
    f"- Verdict: **{verdict}**",
    f"- Duration: {summary['duration_seconds']} seconds",
    f"- Luxor jobs: {summary['job_counts']['luxor']}",
    f"- AntPool jobs: {summary['job_counts']['antpool']}",
    f"- Paired comparisons: {summary['paired_comparisons']}",
    f"- Mean weighted similarity: {summary['mean_weighted_similarity']}",
    f"- Median weighted similarity: {summary['median_weighted_similarity']}",
    f"- Similarity range: {summary['minimum_weighted_similarity']} to {summary['maximum_weighted_similarity']}",
    f"- Identical branch-list pairs: {summary['identical_template_pairs']}",
    "",
    "The score uses 0xB10C's published weighting, where later Merkle branches carry more weight.",
    "This verdict applies only to the tested endpoints and observation window.",
    "",
    "## Diagnostics",
    "",
    "~~~json",
    json.dumps(diagnostics, indent=2),
    "~~~",
]
Path("results/SUMMARY.md").write_text("\n".join(lines) + "\n")
print(json.dumps(summary, indent=2), flush=True)

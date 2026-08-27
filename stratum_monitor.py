#!/usr/bin/env python3
"""Authorized rolling Luxor vs AntPool Stratum V1 monitor."""
import json
import os
import socket
import statistics
import threading
import time
from pathlib import Path

DURATION = int(os.getenv("DURATION", "1800"))
PAIR_WINDOW = int(os.getenv("PAIR_WINDOW", "45"))
LUXOR_USER = os.getenv("LUXOR_USER", "")
LUXOR_PASSWORD = os.getenv("LUXOR_PASSWORD", "x")
POOLS = {
    "luxor": ("btc.global.luxor.tech", 700, LUXOR_USER, LUXOR_PASSWORD),
    "antpool": ("btc.antpool.com", 3333, os.getenv("ANTPOOL_USER", "publicobserver.worker"), os.getenv("ANTPOOL_PASSWORD", "x")),
}
jobs = {name: [] for name in POOLS}
diagnostics = {name: [] for name in POOLS}


def weighted(a, b):
    length = min(len(a), len(b))
    return sum(0.5 ** (length - i) for i in range(length) if a[i] == b[i])


def listen(name, config):
    host, port, username, password = config
    try:
        sock = socket.create_connection((host, port), timeout=20)
        sock.settimeout(10)
        for request in (
            {"id": 1, "method": "mining.subscribe", "params": ["antpool-friends-monitor/1.0"]},
            {"id": 2, "method": "mining.authorize", "params": [username, password]},
        ):
            sock.sendall((json.dumps(request) + "\n").encode())
        buffer = b""; deadline = time.time() + DURATION
        while time.time() < deadline:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                try:
                    message = json.loads(line)
                except Exception:
                    continue
                if message.get("method") != "mining.notify":
                    diagnostics[name].append(message); continue
                p = message.get("params", [])
                if len(p) >= 9:
                    jobs[name].append({"time": time.time(), "job_id": p[0], "prev_hash": p[1], "branches": p[4], "coinbase1": p[2]})
        sock.close()
    except Exception as exc:
        diagnostics[name].append({"error": f"{type(exc).__name__}: {exc}"})


if not LUXOR_USER:
    raise SystemExit("LUXOR_USER is required for continuous Luxor jobs")
threads = [threading.Thread(target=listen, args=item, daemon=True) for item in POOLS.items()]
started = time.time()
for thread in threads: thread.start()
for thread in threads: thread.join()
pairs = []
for luxor in jobs["luxor"]:
    candidates = [a for a in jobs["antpool"] if a["prev_hash"] == luxor["prev_hash"] and abs(a["time"] - luxor["time"]) <= PAIR_WINDOW]
    if candidates:
        antpool = min(candidates, key=lambda a: abs(a["time"] - luxor["time"]))
        matches = [i for i in range(min(len(luxor["branches"]), len(antpool["branches"]))) if luxor["branches"][i] == antpool["branches"][i]]
        pairs.append({"luxor_job": luxor["job_id"], "antpool_job": antpool["job_id"], "matching_positions": matches, "score": weighted(luxor["branches"], antpool["branches"])})
scores = [p["score"] for p in pairs]
record = {
    "started_at": started, "finished_at": time.time(),
    "job_counts": {k: len(v) for k, v in jobs.items()}, "pair_count": len(pairs),
    "mean_similarity": statistics.mean(scores) if scores else None,
    "median_similarity": statistics.median(scores) if scores else None,
    "pairs": pairs, "diagnostics": diagnostics,
}
Path("results/stratum").mkdir(parents=True, exist_ok=True)
stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(started))
Path(f"results/stratum/{stamp}.json").write_text(json.dumps(record, indent=2))
print(json.dumps(record, indent=2))

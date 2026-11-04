"""Append-only JSONL audit log."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def snapshot_hash(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()[:12]


def log(path, event, **fields):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, **fields}
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")

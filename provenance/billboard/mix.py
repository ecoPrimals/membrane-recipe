#!/usr/bin/env python3
"""Billboard mixer generator — reads braid, loads snapshots, writes billboard-mix.json"""
import json, os, sys

BRAID = "/opt/membrane/provenance/billboard/billboard.jsonl"
SNAP_DIR = "/opt/membrane/provenance/billboard"
OUT = "/opt/membrane/live-terminal/billboard-mix.json"

entries = []
with open(BRAID) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass

mix = []
for e in entries:
    item = {"title": e.get("title", ""), "ts": e.get("ts", ""), "links": e.get("links", [])}
    snap = e.get("snapshot")
    if snap:
        snap_path = os.path.join(SNAP_DIR, snap)
        if os.path.exists(snap_path):
            with open(snap_path) as sf:
                item["text"] = sf.read().strip()
    if "text" not in item:
        item["text"] = item["title"]
    mix.append(item)

with open(OUT, "w") as f:
    json.dump({"billboards": mix, "count": len(mix), "wave": 171}, f, indent=2)

print(f"{len(mix)} chapters -> {OUT}")

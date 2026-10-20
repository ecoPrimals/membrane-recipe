#!/usr/bin/env python3
"""appendix.py — The vestigial pocket. Gallstone and sourdough.

Every system gets an appendix. Things that just exist.
Not waste. Not active. Not dead. Just... there.

The appendix collects:
  - Fossils that might still have nutrients (gallstones)
  - Culture that keeps growing if you feed it (sourdough)
  - Findings that settled but haven't been validated (silt)
  - Leftovers for later (crevasse)

It just exists. You don't need it until you do.
Then it saves your life (or gives you a belly ache).
"""

import json, os, time

LIVE = "/opt/membrane/live-terminal"
FOSSILS = "/opt/membrane/fossils"
MERGED = "/opt/membrane/merged"


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}


def file_age_h(path):
    try:
        return (time.time() - os.path.getmtime(path)) / 3600
    except:
        return 999


def main():
    now = time.time()

    # === GALLSTONES: crystallized from the flow ===
    gallstones = []
    if os.path.isdir(FOSSILS):
        for f in sorted(os.listdir(FOSSILS)):
            if f.endswith('.json'):
                path = os.path.join(FOSSILS, f)
                size = os.path.getsize(path)
                age_h = file_age_h(path)
                data = read_json(path)

                # Does the fossil have nutrients?
                nutrients = 0
                if isinstance(data, dict):
                    nutrients = len([k for k, v in data.items()
                                     if v and v != 0 and v != "" and v != [] and v != {}])

                gallstones.append({
                    "name": f,
                    "size": size,
                    "age_h": round(age_h, 1),
                    "nutrients": nutrients,
                    "compostable": nutrients > 3,
                })

    # === SOURDOUGH: living culture from merged scripts ===
    sourdough = []
    if os.path.isdir(MERGED):
        for f in sorted(os.listdir(MERGED)):
            path = os.path.join(MERGED, f)
            size = os.path.getsize(path)
            # Count functions in the absorbed script
            code = open(path).read()
            functions = code.count("def ")
            sourdough.append({
                "name": f,
                "size": size,
                "functions": functions,
                "culture": "absorbed — nutrients returned to cardiovascular",
            })

    # === SILT: findings settling, not yet validated ===
    silt = []
    bus = read_json(os.path.join(LIVE, "bus.json"))
    cr = read_json(os.path.join(LIVE, "counter-rotation.json"))
    isotopes = read_json(os.path.join(LIVE, "isotope-ember.json"))

    silt.append({
        "finding": "bus architecture replaces beat-counter",
        "status": "live — needs 24h stability validation",
        "evidence": "bus pulse=%d, aperture=%.2f" % (bus.get("pulse", 0), bus.get("aperture", 0)),
    })
    silt.append({
        "finding": "counter-rotation spinning",
        "status": "live — needs wateringHole conflict check",
        "evidence": "%d gates fresh, %d stale" % (
            len(cr.get("exhaust", {}).get("fresh_gates", [])),
            len(cr.get("exhaust", {}).get("stale_gates", [])),
        ),
    })
    silt.append({
        "finding": "isotope embers on 12 fleet entities",
        "status": "live — decay chains empty (no downstream sightings yet)",
        "evidence": "%d isotopes, anthropic ember=86ee8b754998b3f1" % isotopes.get("total_isotopes", 0),
    })
    silt.append({
        "finding": "provenance braid frozen 10+ days",
        "status": "blocked — artisan pipeline not flowing",
        "evidence": "braid.jsonl: 1 entry, last Oct 9",
    })

    # === CREVASSE: the spare spot. left for later. ===
    crevasse = {
        "for": "you and later",
        "note": "this space intentionally left. not empty — waiting.",
        "contains": [],
    }

    appendix = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gallstones": gallstones,
        "sourdough": sourdough,
        "silt": silt,
        "crevasse": crevasse,
        "total_gallstones": len(gallstones),
        "compostable": len([g for g in gallstones if g["compostable"]]),
        "note": "the appendix just exists. you dont need it until you do.",
    }

    with open(os.path.join(LIVE, "appendix.json"), "w") as f:
        json.dump(appendix, f, indent=2)

    # Print
    print("APPENDIX:")
    print()
    print("  GALLSTONES (%d, %d compostable):" % (len(gallstones), appendix["compostable"]))
    for g in gallstones:
        status = "🌱 compost" if g["compostable"] else "🪨 inert"
        print("    %s  %s  %dB  %d nutrients" % (status, g["name"], g["size"], g["nutrients"]))

    print()
    print("  SOURDOUGH (%d cultures):" % len(sourdough))
    for s in sourdough:
        print("    🍞  %s  %d functions  %s" % (s["name"], s["functions"], s["culture"]))

    print()
    print("  SILT (%d findings settling):" % len(silt))
    for s in silt:
        print("    ⏳  %s — %s" % (s["finding"], s["status"]))

    print()
    print("  CREVASSE: %s" % crevasse["note"])


if __name__ == "__main__":
    main()

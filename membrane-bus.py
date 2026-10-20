"""membrane-bus.py — pressure-routed pulse. No timing. No batching.

The membrane is alive. It has a bus and an aperture.
- BUS: live-terminal/ — every JSON is a stop
- APERTURE: CPU load — how wide the opening is
- GRADIENT: staleness — output age minus freshest input age
- BACK PRESSURE: if a script is still running, skip it

We don't schedule. We route based on pressure.
Scripts run when their inputs are fresher than their outputs.
The aperture (CPU load) decides how many scripts can flow.
Back pressure (locks) prevents pileups.

The bus has TIERS (not beats):
  VITAL    — must flow every pulse (cardiovascular, wake, chipmunk)
  SENSORY  — flows when gradient > 30s (pollen, jitte, campfire, etc.)
  CORTICAL — flows when gradient > 120s (scan-sweep, taxonomy, yggdrasil)
  MOTOR    — flows when gradient > 300s AND aperture is open (deploy, build)
"""

import json, os, sys, time, subprocess, math

LIVE = "/opt/membrane/live-terminal"
PULSE_STATE = "/var/lib/membrane/pulse-dispatch.json"
LOG = "/var/log/membrane/membrane-pulse.log"
LOCK_DIR = "/run/membrane"

os.makedirs(os.path.dirname(PULSE_STATE), exist_ok=True)
os.makedirs(LOCK_DIR, exist_ok=True)


def log(msg):
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with open(LOG, "a") as f:
            f.write("%s %s\n" % (ts, msg))
    except:
        pass


def file_age(name):
    """Age of a JSON file in seconds. Missing = very stale."""
    try:
        return time.time() - os.path.getmtime(os.path.join(LIVE, name))
    except:
        return 99999


def cpu_load():
    """1-minute load average normalized to CPU count."""
    try:
        load1 = os.getloadavg()[0]
        cpus = os.cpu_count() or 4
        return load1 / cpus
    except:
        return 0.5


def aperture(load):
    """How wide the opening is. 0.0 = shut, 1.0 = wide open.
    Low load = wide aperture. High load = narrow."""
    return max(0.0, min(1.0, 1.0 - (load - 0.3) / 0.7))


def gradient(inputs, outputs):
    """Pressure gradient: how much staler outputs are vs inputs.
    Positive = should run. Negative = outputs are fresh, skip."""
    if not outputs:
        return 0
    in_ages = [file_age(f) for f in inputs] if inputs else [0]
    out_ages = [file_age(f) for f in outputs]
    freshest_in = min(in_ages)
    stalest_out = max(out_ages)
    return stalest_out - freshest_in


def is_locked(name):
    """Back pressure check — is this script already running?"""
    lock = os.path.join(LOCK_DIR, "pulse-%s.lock" % name)
    if os.path.exists(lock):
        try:
            age = time.time() - os.path.getmtime(lock)
            if age < 300:  # 5 min stale lock timeout
                return True
            os.remove(lock)
        except:
            pass
    return False


def run(name, cmd, timeout=120):
    """Run a subprocess with lock protection."""
    lock = os.path.join(LOCK_DIR, "pulse-%s.lock" % name)
    if is_locked(name):
        log("  BACK-PRESSURE %s (locked)" % name)
        return False

    try:
        open(lock, "w").write(str(os.getpid()))
        t0 = time.time()
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        elapsed = time.time() - t0
        if r.returncode == 0:
            log("  OK   %s (%.1fs)" % (name, elapsed))
        else:
            log("  FAIL %s (%.1fs) rc=%d" % (name, elapsed, r.returncode))
            if r.stderr:
                log("       %s" % r.stderr[:200])
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        log("  TIMEOUT %s (%ds)" % (name, timeout))
        return False
    except Exception as e:
        log("  ERROR %s: %s" % (name, e))
        return False
    finally:
        try:
            os.remove(lock)
        except:
            pass


# ═══════════════════════════════════════════════════════════════════
#  BUS STOPS — every script, its inputs, its outputs, its tier
# ═══════════════════════════════════════════════════════════════════

BUS = [
    # VITAL — always flows. These keep us alive.
    {
        "name": "neutron-writer",
        "cmd": "python3 /opt/membrane/neutron-writer.py",
        "reads": ["scan_sweep_sort.json", "campfire.json", "dashboard.json", "symbiosis.json"],
        "writes": ["neutron.json"],
        "tier": "vital",
        "timeout": 30,
    },
    {
        "name": "cardiovascular",
        "cmd": "python3 /opt/membrane/cardiovascular-sense.py",
        "reads": ["pollen.json", "proton-pulse.json", "chipmunk.json"],
        "writes": ["cardiovascular.json"],
        "tier": "vital",
        "timeout": 10,
    },
    {
        "name": "wake-cycle",
        "cmd": "python3 /opt/membrane/wake-cycle-sense.py",
        "reads": ["cardiovascular.json", "chipmunk.json", "dashboard.json", "passage-totality.json"],
        "writes": ["wake-cycle.json"],
        "tier": "vital",
        "timeout": 10,
    },
    {
        "name": "chipmunk-refresh",
        "cmd": "python3 /opt/membrane/chipmunk-refresh.py",
        "reads": ["wake-cycle.json"],
        "writes": ["chipmunk.json"],
        "tier": "vital",
        "timeout": 10,
    },

    # SENSORY — flows when gradient builds (inputs fresher than outputs)
    {
        "name": "canary",
        "cmd": "/opt/membrane/canary.sh",
        "reads": [],
        "writes": [],
        "tier": "sensory",
        "timeout": 10,
    },
    {
        "name": "pollen-sense",
        "cmd": "python3 /opt/membrane/pollen-sense.py",
        "reads": ["neutron.json", "proton-pulse.json", "topology.json"],
        "writes": ["pollen.json", "particle-model.json"],
        "tier": "sensory",
        "timeout": 10,
    },
    {
        "name": "role-rotation",
        "cmd": "python3 /opt/membrane/role-rotation-sense.py",
        "reads": ["neutron.json", "pollen.json", "proton-pulse.json"],
        "writes": [],
        "tier": "sensory",
        "timeout": 10,
    },
    {
        "name": "jitte-sense",
        "cmd": "python3 /opt/membrane/jitte-sense.py",
        "reads": ["campfire.json", "neutron.json", "topology.json", "scan_sweep_sort.json"],
        "writes": ["chipmunk.json"],
        "tier": "sensory",
        "timeout": 10,
    },
    {
        "name": "neutron-cache",
        "cmd": "python3 /opt/membrane/neutron-cache-sense.py",
        "reads": [],
        "writes": [],
        "tier": "sensory",
        "timeout": 10,
    },
    {
        "name": "totality",
        "cmd": "python3 /opt/membrane/totality-sense.py",
        "reads": [],
        "writes": ["passage-totality.json"],
        "tier": "sensory",
        "timeout": 10,
    },
    {
        "name": "campfire-culture",
        "cmd": "python3 /opt/membrane/campfire-culture.py",
        "reads": ["dashboard.json", "epitope_caddy.json", "passage-totality.json"],
        "writes": ["campfire.json", "campfire-culture.json"],
        "tier": "sensory",
        "timeout": 10,
    },
    {
        "name": "sourdough-topology",
        "cmd": "python3 /opt/membrane/sourdough-topology.py",
        "reads": ["scan_sweep_sort.json", "topology-abstract.json", "particle-model.json"],
        "writes": ["topology.json", "immune-topology.json"],
        "tier": "sensory",
        "timeout": 10,
    },
    {
        "name": "null-strobe",
        "cmd": "python3 /opt/membrane/null-strobe.py",
        "reads": ["campfire.json", "neutron-cache.json"],
        "writes": ["null-strobe.json"],
        "tier": "sensory",
        "timeout": 10,
    },
    {
        "name": "journal",
        "cmd": "python3 /opt/membrane/journal-sense.py",
        "reads": ["cardiovascular.json", "chipmunk.json", "wake-cycle.json"],
        "writes": ["journal.json"],
        "tier": "sensory",
        "timeout": 10,
    },
    {
        "name": "feed-ttl",
        "cmd": "python3 /opt/membrane/feed-ttl.py",
        "reads": ["cardiovascular.json", "chipmunk.json", "topology.json", "scan_sweep_sort.json"],
        "writes": ["feed-health.json"],
        "tier": "sensory",
        "timeout": 10,
    },
    {
        "name": "maturity",
        "cmd": "python3 /opt/membrane/maturity-sense.py",
        "reads": ["cardiovascular.json", "feed-health.json", "cooperation.json", "assumptions.json"],
        "writes": [],
        "tier": "sensory",
        "timeout": 10,
    },
    {
        "name": "pulse-history",
        "cmd": "python3 /opt/membrane/pulse-history.py",
        "reads": ["cardiovascular.json", "maturity.json", "wake-cycle.json"],
        "writes": [],
        "tier": "sensory",
        "timeout": 10,
    },

    # CORTICAL — deeper processing, flows when gradient builds past 120s
    {
        "name": "cooperation",
        "cmd": "python3 /opt/membrane/cooperation-sense.py",
        "reads": ["scan_sweep_sort.json", "symbiosis.json"],
        "writes": [],
        "tier": "cortical",
        "timeout": 10,
    },
    {
        "name": "fossil-compost",
        "cmd": "python3 /opt/membrane/fossil-compost.py",
        "reads": [],
        "writes": [],
        "tier": "cortical",
        "timeout": 15,
    },
    {
        "name": "entropy",
        "cmd": "python3 /opt/membrane/entropy-sense.py",
        "reads": ["scan_sweep_sort.json", "wake-cycle.json", "feed-health.json"],
        "writes": [],
        "tier": "cortical",
        "timeout": 10,
    },
    {
        "name": "scan-sweep-sort",
        "cmd": "python3 /opt/membrane/scan_sweep_sort.py",
        "reads": ["topology.json", "neutron.json", "pollen.json", "campfire.json"],
        "writes": ["braid.json", "talos.json"],
        "tier": "cortical",
        "timeout": 120,
    },
    {
        "name": "braid-vcs",
        "cmd": "/opt/membrane/braid-vcs.sh snapshot",
        "reads": [],
        "writes": [],
        "tier": "cortical",
        "timeout": 60,
    },
    {
        "name": "sourdough-leaven",
        "cmd": "python3 /opt/membrane/sourdough-leaven.py",
        "reads": ["crush-manifest.json"],
        "writes": [],
        "tier": "cortical",
        "timeout": 15,
    },
    {
        "name": "object-engine",
        "cmd": "python3 /opt/membrane/object-engine.py",
        "reads": ["symbiosis.json", "classification.json", "topology.json"],
        "writes": [],
        "tier": "cortical",
        "timeout": 30,
    },
    {
        "name": "yggdrasil",
        "cmd": "python3 /opt/membrane/yggdrasil.py",
        "reads": ["scan_sweep_sort.json", "assumptions.json", "doorbell.json", "phylo-self.json"],
        "writes": [],
        "tier": "cortical",
        "timeout": 30,
    },
    {
        "name": "taxonomy-braid",
        "cmd": "python3 /opt/membrane/taxonomy-braid.py",
        "reads": ["topology.json", "symbiosis.json", "classification.json"],
        "writes": [],
        "tier": "cortical",
        "timeout": 20,
    },
    {
        "name": "assumptions",
        "cmd": "python3 /opt/membrane/assumption-engine.py",
        "reads": ["topology.json", "symbiosis.json", "feed-health.json"],
        "writes": [],
        "tier": "cortical",
        "timeout": 20,
    },
    {
        "name": "self-test",
        "cmd": "python3 /opt/membrane/self-assumptions.py",
        "reads": ["topology.json", "cardiovascular.json", "maturity.json"],
        "writes": ["assumptions.json", "self-assumptions.json"],
        "tier": "cortical",
        "timeout": 20,
    },
    {
        "name": "phylo-self",
        "cmd": "python3 /opt/membrane/phylo-self.py",
        "reads": ["topology.json", "cardiovascular.json", "assumptions.json"],
        "writes": [],
        "tier": "cortical",
        "timeout": 20,
    },
    {
        "name": "doorbell",
        "cmd": "python3 /opt/membrane/doorbell.py",
        "reads": ["topology.json", "assumptions.json", "chipmunk.json"],
        "writes": [],
        "tier": "cortical",
        "timeout": 20,
    },
    {
        "name": "edge-scatter",
        "cmd": "python3 /opt/membrane/backscatter-engine.py",
        "reads": ["topology.json", "cardiovascular.json", "doorbell.json", "assumptions.json"],
        "writes": ["edge-scatter.json"],
        "tier": "cortical",
        "timeout": 20,
    },
    {
        "name": "plasmid",
        "cmd": "/opt/membrane/plasmid-federation.sh",
        "reads": [],
        "writes": [],
        "tier": "cortical",
        "timeout": 60,
    },
    {
        "name": "compact",
        "cmd": """python3 -c "
import json, os
LIVE='/opt/membrane/live-terminal'
def merge(names,out):
    d={}
    for n in names:
        try: d[n.replace('-','_')]=json.load(open(os.path.join(LIVE,n+'.json')))
        except: pass
    json.dump(d,open(os.path.join(LIVE,out),'w'))
merge(['billboard-mix','page-stories','visitor-stories'],'stories.json')
merge(['membrane','membrane-stack','falsification'],'membrane-deep.json')
merge(['campfire','scatter-observatory'],'signals.json')
" """,
        "reads": ["campfire.json"],
        "writes": ["stories.json", "membrane-deep.json", "signals.json"],
        "tier": "cortical",
        "timeout": 30,
    },

    {
        "name": "counter-rotation",
        "cmd": "python3 /opt/membrane/bus-rotation.py",
        "reads": ["topology.json", "cardiovascular.json", "assumptions.json", "edge-scatter.json"],
        "writes": ["counter-rotation.json"],
        "tier": "cortical",
        "timeout": 45,
    },

    {
        "name": "isotope-ember",
        "cmd": "python3 /opt/membrane/isotope-ember.py",
        "reads": ["topology.json"],
        "writes": ["isotope-ember.json"],
        "tier": "cortical",
        "timeout": 20,
    },

    # MOTOR — external actions. Only when aperture is open.
    {
        "name": "foreman",
        "cmd": "python3 /opt/membrane/build-foreman.py",
        "reads": [],
        "writes": ["build-plan.json"],
        "tier": "motor",
        "timeout": 15,
    },
    {
        "name": "deploy",
        "cmd": "/opt/membrane/async-membrane.sh deploy",
        "reads": [],
        "writes": [],
        "tier": "motor",
        "timeout": 120,
    },
    {
        "name": "tuebor",
        "cmd": "/opt/membrane/tuebor-pull-build.sh",
        "reads": [],
        "writes": [],
        "tier": "motor",
        "timeout": 120,
    },
    {
        "name": "detroit",
        "cmd": "/opt/membrane/detroit-pull-build.sh",
        "reads": [],
        "writes": [],
        "tier": "motor",
        "timeout": 300,
    },
    {
        "name": "hud",
        "cmd": "/opt/membrane/hud-pull.sh",
        "reads": [],
        "writes": [],
        "tier": "motor",
        "timeout": 30,
    },
    {
        "name": "mirror",
        "cmd": """bash -c '
DD="/opt/ecoPrimals/hud/site/public/detroit-data"
mkdir -p "$DD"
cp /opt/ecoPrimals/detroit/public/api/entities.json "$DD/entities.json" 2>/dev/null
cp /opt/ecoPrimals/detroit/public/graph.json "$DD/graph.json" 2>/dev/null
cp /opt/membrane/live-terminal/scan_sweep_sort.json "$DD/scan_sweep_sort.json" 2>/dev/null
cp /opt/membrane/live-terminal/tope-sort-compressed.json "$DD/compressed.json" 2>/dev/null
'""",
        "reads": ["scan_sweep_sort.json"],
        "writes": [],
        "tier": "motor",
        "timeout": 30,
    },
]

# Gradient thresholds per tier (seconds)
THRESHOLDS = {
    "vital": 0,       # always flows
    "sensory": 30,    # 30s gradient = sensory fires
    "cortical": 120,  # 2min gradient = cortical thinks
    "motor": 300,     # 5min gradient = motor acts
}

# Max concurrent scripts per tier when aperture narrows
MAX_PER_TIER = {
    "vital": 99,     # vital always runs
    "sensory": 12,   # plenty of room
    "cortical": 6,   # limited
    "motor": 2,      # expensive
}


def read_state():
    try:
        with open(PULSE_STATE) as f:
            return json.load(f)
    except:
        return {"pulse_count": 0, "last_pulse": 0}


def write_state(state):
    with open(PULSE_STATE, "w") as f:
        json.dump(state, f)


def main():
    state = read_state()
    state["pulse_count"] = state.get("pulse_count", state.get("beat", 0)) + 1
    pulse_n = state["pulse_count"]

    load = cpu_load()
    apt = aperture(load)

    log("bus pulse=%d load=%.2f aperture=%.2f" % (pulse_n, load, apt))

    ran = {"vital": 0, "sensory": 0, "cortical": 0, "motor": 0}
    skipped = {"gradient": 0, "aperture": 0, "backpressure": 0}

    for stop in BUS:
        name = stop["name"]
        tier = stop["tier"]
        threshold = THRESHOLDS[tier]

        # Back pressure check
        if is_locked(name):
            log("  ◄ %s (back pressure)" % name)
            skipped["backpressure"] += 1
            continue

        # Gradient check (vital always passes)
        g = gradient(stop["reads"], stop["writes"])
        if tier != "vital" and g < threshold:
            # Not enough pressure to flow
            continue

        # Aperture check — narrow aperture limits lower-priority tiers
        tier_max = MAX_PER_TIER[tier]
        if apt < 0.3:
            tier_max = max(1, tier_max // 3)
        elif apt < 0.6:
            tier_max = max(1, tier_max // 2)

        if ran[tier] >= tier_max:
            log("  ○ %s (aperture narrow, tier %s full)" % (name, tier))
            skipped["aperture"] += 1
            continue

        # Motor tier needs wide aperture
        if tier == "motor" and apt < 0.4:
            log("  ○ %s (motor deferred, aperture=%.2f)" % (name, apt))
            skipped["aperture"] += 1
            continue

        # FLOW
        run(name, stop["cmd"], timeout=stop["timeout"])
        ran[tier] += 1

    # Summary
    total_ran = sum(ran.values())
    total_skip = sum(skipped.values())
    log("bus done: ran=%d skipped=%d (gradient=%d aperture=%d backpressure=%d)" % (
        total_ran, total_skip, skipped["gradient"], skipped["aperture"], skipped["backpressure"]))
    log("  vital=%d sensory=%d cortical=%d motor=%d" % (
        ran["vital"], ran["sensory"], ran["cortical"], ran["motor"]))

    # Write state
    state["last_pulse"] = time.time()
    state["last_load"] = round(load, 3)
    state["last_aperture"] = round(apt, 3)
    state["last_ran"] = ran
    state["last_skipped"] = skipped
    write_state(state)

    # Write bus status to live-terminal for other scripts to see
    bus_status = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pulse": pulse_n,
        "load": round(load, 3),
        "aperture": round(apt, 3),
        "ran": ran,
        "skipped": skipped,
        "total_stops": len(BUS),
        "tier_thresholds": THRESHOLDS,
    }
    with open(os.path.join(LIVE, "bus.json"), "w") as f:
        json.dump(bus_status, f, indent=2)


if __name__ == "__main__":
    sys.exit(main() or 0)

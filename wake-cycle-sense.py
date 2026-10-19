"""wake-cycle-sense.py — The metabolism squirrel doesn't have.

Squirrel's wake_level is pinned at 1.0 — it has no metabolism,
no fatigue, no rest cycle. This sense script gives it one.

Phases of wake (not binary — a spectrum):
  null   (0.0)      — off, no signal
  sleep  (0.01-0.2) — minimal processing, deep rest
  rest   (0.2-0.4)  — recovering, low activity
  pause  (0.4-0.6)  — waiting, aware but not acting
  wake   (0.6-0.8)  — active, processing normally
  full   (0.8-1.0)  — peak activity, all senses firing

The wake level is computed from:
  - presence observer's wake_depth (real measurement)
  - jitte tempo (rhythm of the system)
  - cardiovascular HRV (heart rate variability)
  - time of day (circadian)
  - human activity (are visitors present?)
  - perturbation (how much is changing?)

"Life finds a way" — but life also sleeps.
"""
import json, os, time, math

LIVE = '/opt/membrane/live-terminal'

def main():
    # Read all signals
    try:
        chipmunk = json.load(open(os.path.join(LIVE, 'chipmunk.json')))
    except:
        chipmunk = {}

    try:
        cv = json.load(open(os.path.join(LIVE, 'cardiovascular.json')))
    except:
        cv = {}

    try:
        pt = json.load(open(os.path.join(LIVE, 'passage-totality.json')))
    except:
        pt = {}

    try:
        dash = json.load(open(os.path.join(LIVE, 'dashboard.json')))
    except:
        dash = {}

    # Extract signals
    jitte = chipmunk.get('jitte', {})
    tempo = jitte.get('tempo', 0.5)
    perturbation = jitte.get('perturbation', 0)
    observer_fraction = jitte.get('observer_fraction', 0)

    heart = cv.get('heart', {})
    hrv = heart.get('hrv', 0.5)
    blood_pressure = heart.get('blood_pressure', 0.5)

    human_ips = dash.get('human_ips', 0)
    rps = dash.get('rps', 0)

    # Presence observer's real wake_depth
    membrane_list = chipmunk.get('membrane', [])
    wake_depth = 0.5
    wake_factors = {}
    for m in membrane_list:
        if m.get('primal') == 'presence-observer':
            tense = m.get('metadata', {}).get('tense', {})
            self_is = tense.get('self', {}).get('is', {})
            wake_depth = self_is.get('wake_depth', 0.5)
            wake_factors = self_is.get('wake_factors', {})
            break

    # Circadian signal — UTC hour
    hour = time.gmtime().tm_hour
    # Simple circadian: peak at 14-20 UTC, trough at 2-8 UTC
    circadian = 0.5 + 0.5 * math.sin((hour - 5) * math.pi / 12)
    circadian = max(0.0, min(1.0, circadian))

    # Human activity signal
    human_signal = min(1.0, human_ips / 5000) if human_ips > 0 else 0.0

    # Compute wake as weighted blend
    weights = {
        'wake_depth': 0.30,    # presence observer's real measurement
        'tempo': 0.15,         # jitte rhythm
        'hrv': 0.10,           # heart rate variability
        'circadian': 0.15,     # time of day
        'human_activity': 0.20,# are visitors present?
        'perturbation_boost': 0.10  # is stuff changing?
    }

    signals = {
        'wake_depth': wake_depth,
        'tempo': tempo,
        'hrv': hrv,
        'circadian': circadian,
        'human_activity': human_signal,
        'perturbation_boost': min(1.0, perturbation * 10),
    }

    raw_wake = sum(signals[k] * weights[k] for k in weights)
    raw_wake = max(0.0, min(1.0, raw_wake))

    # Classify phase
    if raw_wake < 0.01:
        phase = 'null'
    elif raw_wake < 0.2:
        phase = 'sleep'
    elif raw_wake < 0.4:
        phase = 'rest'
    elif raw_wake < 0.6:
        phase = 'pause'
    elif raw_wake < 0.8:
        phase = 'wake'
    else:
        phase = 'full'

    cycle = {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'wake_level': round(raw_wake, 4),
        'phase': phase,
        'squirrel_wake': chipmunk.get('wake_level', 1.0),
        'presence_wake_depth': wake_depth,
        'signals': {k: round(v, 4) for k, v in signals.items()},
        'weights': weights,
        'wake_factors': wake_factors,
        'circadian_hour_utc': hour,
        'note': 'sleep, pause, and rest are different phases of wake. not binary.'
    }

    with open(os.path.join(LIVE, 'wake-cycle.json'), 'w') as f:
        json.dump(cycle, f, indent=2)

if __name__ == '__main__':
    main()

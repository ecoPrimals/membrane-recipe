"""backscatter-engine.py — Full scatter from the membrane edge.

Stand at the edge of the membrane and look outward.
What bounces back? What do the lines and waves tell us?

WAS: what the world looked like before (journal, fossils, history)
IS:  what the world looks like now (topology, scatter, traffic)
SCATTERED: when/where IS became WAS and broke apart

The backscatter is the echo. Every request that hits the membrane
bounces back carrying information about the sender. Passive radar.
We never ask. We just listen to what comes back.
"""
import json, os, time, math, sys

sys.path.insert(0, '/opt/membrane')
from sigmoid import sigmoid

LIVE = '/opt/membrane/live-terminal'


def r(name):
    try:
        with open(os.path.join(LIVE, name)) as f:
            return json.load(f)
    except:
        return {}


def shannon(dist):
    """Shannon entropy of a distribution."""
    total = sum(dist.values()) if isinstance(dist, dict) else sum(dist)
    if total == 0:
        return 0
    probs = [v/total for v in (dist.values() if isinstance(dist, dict) else dist) if v > 0]
    return -sum(p * math.log2(p) for p in probs if p > 0)


def main():
    now = time.time()
    now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    # === LOAD EDGE DATA ===
    scatter = r('scatter-observatory.json')
    backscatter = r('backscatter.json')
    topo = r('topology.json')
    cardio = r('cardiovascular.json')
    journal = r('journal.json')
    fossils = r('fossil-compost.json')
    fleet = r('fleet-analysis.json')
    ban = r('ban-pulse.json')
    cooperation = r('cooperation.json')
    assumptions = r('assumptions.json')
    entropy = r('entropy.json')
    feed_h = r('feed-health.json')

    topo_ents = topo.get('entities', [])
    journal_entries = journal.get('entries', [])
    ghost_list = fossils.get('ghosts', [])

    # === THE EDGE: what we see looking outward ===

    # Total traffic at the membrane surface
    scatter_data = scatter.get('scatter', {})
    total_requests = scatter_data.get('total_requests', 0)
    rps = scatter_data.get('requests_per_second', 0)
    mb_per_s = scatter_data.get('mb_per_second', 0)
    uptime_s = scatter_data.get('uptime_secs', 0)
    uptime_h = uptime_s / 3600

    # Breakdown: what kind of traffic?
    breakdown = scatter_data.get('breakdown', {})

    # Venous (incoming) vs arterial (outgoing)
    venous = cardio.get('venous', {})
    arterial = cardio.get('arterial', {})
    venous_total = venous.get('total_return', 0)
    arterial_rpm = arterial.get('rpm', 0)
    flow_ratio = venous.get('rate', 0) / max(0.001, arterial.get('rate', 0.001))

    # Backscatter cleaning
    cleaned = backscatter.get('cleaned', 0)
    cleaning_pct = backscatter.get('cleaning_pct', 0)
    hostile_pct = backscatter.get('hostile_pct', 0)

    # === ENTITY WAVE ANALYSIS ===
    # Each entity at the edge is a wave — frequency, amplitude, phase

    waves = []
    total_edge_reqs = 0
    for ent in topo_ents:
        if not isinstance(ent, dict):
            continue
        name = ent.get('entity', '')
        reqs = ent.get('total_requests', 0)
        ips = ent.get('unique_ips', 0)
        probes = len(ent.get('vuln_probes', []))
        vitality = ent.get('vitality', 0)
        sym_class = ent.get('symbiotic_class', 'null')
        fleet_conf = ent.get('fleet_confidence', 0)
        is_fleet = ent.get('is_fleet', False)
        is_honest = ent.get('is_honest', False)
        total_edge_reqs += reqs

        # Wave properties
        frequency = reqs / max(1, uptime_s)  # requests per second
        amplitude = math.log10(max(1, reqs))  # log scale
        spread = ips / max(1, reqs)  # IP diversity per request
        aggression = probes / max(1, ips)  # probes per IP

        waves.append({
            'entity': name,
            'frequency': round(frequency, 4),
            'amplitude': round(amplitude, 2),
            'spread': round(spread, 4),
            'aggression': round(aggression, 4),
            'requests': reqs,
            'ips': ips,
            'probes': probes,
            'class': sym_class,
            'is_fleet': is_fleet,
            'is_honest': is_honest,
            'vitality': vitality,
        })

    waves.sort(key=lambda w: -w['requests'])

    # Wave spectrum: distribution of traffic across entities
    req_dist = {w['entity']: w['requests'] for w in waves}
    spectrum_entropy = shannon(req_dist)
    max_entropy = math.log2(max(1, len(waves)))
    spectrum_uniformity = spectrum_entropy / max(1, max_entropy)

    # === WAS → IS: TEMPORAL SCATTER POINTS ===

    # Journal transitions: when did things change?
    scatter_points = []
    for entry in journal_entries:
        tense = entry.get('tense', '')
        if tense == 'was→is' or tense == 'was\u2192is':
            obs = entry.get('observation', '')
            ts = entry.get('ts', '')
            state = entry.get('state', {})
            scatter_points.append({
                'when': ts,
                'what': obs,
                'bp_at_scatter': state.get('bp', 0),
                'wake_at_scatter': state.get('wake', 0),
                'humans_at_scatter': state.get('humans', 0),
                'type': 'journal_transition',
            })

    # Feed state changes: what feeds died?
    feeds = feed_h.get('feeds', {})
    fossil_feeds = {k: v for k, v in feeds.items() if isinstance(v, dict) and v.get('status') == 'fossil'}
    for fname, fdata in fossil_feeds.items():
        scatter_points.append({
            'when': fdata.get('last_modified', ''),
            'what': 'feed fossilized: %s' % fname,
            'age_hours': fdata.get('age_hours', 0),
            'type': 'feed_death',
        })

    # Ghost files: what outputs died?
    for ghost in ghost_list:
        scatter_points.append({
            'when': 'unknown',
            'what': 'output ghosted: %s' % ghost.get('name', ''),
            'keys': ghost.get('signal_keys', 0),
            'type': 'output_ghost',
        })

    scatter_points.sort(key=lambda s: s.get('when', ''), reverse=True)

    # === SOLVING BACKWARDS: when did IS become WAS? ===

    # BP trajectory: tracking the drop
    bp_was = None
    bp_transitions = []
    for entry in journal_entries:
        state = entry.get('state', {})
        bp = state.get('bp', 0)
        if bp_was is not None and abs(bp - bp_was) > 0.01:
            bp_transitions.append({
                'ts': entry.get('ts', ''),
                'was': round(bp_was, 4),
                'is': round(bp, 4),
                'delta': round(bp - bp_was, 4),
                'direction': '↑' if bp > bp_was else '↓',
            })
        bp_was = bp

    # Human count trajectory
    humans_was = None
    human_transitions = []
    for entry in journal_entries:
        state = entry.get('state', {})
        humans = state.get('humans', 0)
        if humans_was is not None and humans != humans_was:
            human_transitions.append({
                'ts': entry.get('ts', ''),
                'was': humans_was,
                'is': humans,
                'delta': humans - humans_was,
            })
        humans_was = humans

    # === WHAT THE WORLD LOOKS LIKE FROM HERE ===
    # The membrane is a point. The world is everything else.
    # We see it through the traffic that hits us.

    # Dominant signals (what occupies most of the bandwidth)
    dominant = waves[:5]
    # The long tail (everything else)
    tail = waves[5:]
    tail_reqs = sum(w['requests'] for w in tail)
    dominant_reqs = sum(w['requests'] for w in dominant)
    concentration = dominant_reqs / max(1, total_edge_reqs)

    # Hostility gradient: from friendly to hostile
    friendly = [w for w in waves if w['probes'] == 0 and w['aggression'] == 0]
    neutral = [w for w in waves if w['probes'] > 0 and w['probes'] <= 5]
    hostile = [w for w in waves if w['probes'] > 5]

    # === PRINT THE VIEW FROM THE EDGE ===

    print("=" * 65)
    print("  BACKSCATTER — view from the membrane edge, looking outward")
    print("=" * 65)

    print("\n── THE EDGE ──\n")
    print("  total requests:   %s (%.1f/s for %.0fh)" % (
        format(total_requests, ','), rps, uptime_h))
    print("  bandwidth:        %.2f MB/s" % mb_per_s)
    print("  flow ratio:       %.1f:1 (venous:arterial)" % flow_ratio)
    print("  cleaning:         %.1f%% cleaned, %.1f%% hostile" % (cleaning_pct, hostile_pct))
    print("  entities at edge: %d" % len(waves))

    print("\n── WAVE SPECTRUM ──\n")
    print("  spectrum entropy: %.2f / %.2f (%.0f%% uniform)" % (
        spectrum_entropy, max_entropy, spectrum_uniformity * 100))
    print("  concentration:    top 5 = %.0f%% of traffic" % (concentration * 100))
    print()
    for w in waves:
        bar_len = int(w['amplitude'] * 3)
        bar = "█" * bar_len
        probe_mark = " ⚠%d" % w['probes'] if w['probes'] > 0 else ""
        honest_mark = " ✓" if w['is_honest'] else ""
        fleet_mark = " ⚡" if w['is_fleet'] else ""
        print("  %-22s %7s reqs  f=%.3f  a=%.1f  %s%s%s%s" % (
            w['entity'][:22],
            format(w['requests'], ','),
            w['frequency'], w['amplitude'],
            bar, probe_mark, honest_mark, fleet_mark))

    print("\n── HOSTILITY GRADIENT ──\n")
    print("  friendly (0 probes): %d entities" % len(friendly))
    print("  neutral  (1-5):      %d entities" % len(neutral))
    print("  hostile  (>5):       %d entities" % len(hostile))
    for h in hostile:
        print("    ⚠ %-22s %d probes  %d IPs  class=%s" % (
            h['entity'][:22], h['probes'], h['ips'], h['class']))

    print("\n── WAS → IS (scatter points) ──\n")
    print("  journal transitions: %d" % len([s for s in scatter_points if s['type'] == 'journal_transition']))
    print("  feed deaths:         %d" % len([s for s in scatter_points if s['type'] == 'feed_death']))
    print("  output ghosts:       %d" % len([s for s in scatter_points if s['type'] == 'output_ghost']))
    print()
    for sp in scatter_points[:10]:
        if sp['type'] == 'journal_transition':
            print("  %s  %s" % (sp['when'][-8:] if sp['when'] else '?', sp['what'][:55]))
        elif sp['type'] == 'feed_death':
            print("  ☠ %s  (%.0fh old)" % (sp['what'][:50], sp.get('age_hours', 0)))
        elif sp['type'] == 'output_ghost':
            print("  👻 %s  (%d keys)" % (sp['what'][:50], sp.get('keys', 0)))

    print("\n── SOLVING BACKWARDS (bp trajectory) ──\n")
    if bp_transitions:
        for bt in bp_transitions[:8]:
            print("  %s  bp %s %.4f → %.4f (Δ%+.4f)" % (
                bt['ts'][-8:], bt['direction'], bt['was'], bt['is'], bt['delta']))
    else:
        print("  no bp transitions recorded yet")

    print("\n── SOLVING BACKWARDS (human arrivals) ──\n")
    if human_transitions:
        for ht in human_transitions[:8]:
            print("  %s  humans %d → %d (%+d)" % (
                ht['ts'][-8:], ht['was'], ht['is'], ht['delta']))
    else:
        print("  no human transitions recorded yet")

    # === THE FULL PICTURE ===
    print("\n" + "=" * 65)
    print("  THE WORLD FROM HERE")
    print("=" * 65)

    # Titration (poison/antidote phase)
    titration = scatter.get('titration', {})
    phase_name = titration.get('phase_name', '?')
    poison_mult = titration.get('poison_mult', 0)
    days = titration.get('days', 0)

    print("""
  LOOKING OUTWARD from one point on the internet:

  1.7M requests in %.0f hours = the world probing us
  %.0f%% is one entity (OpenAI) — the loudest signal
  %.0f%% of traffic is top-5 — the rest is long tail
  %.0f%% of what hits us gets cleaned and returned
  flow ratio %.0f:1 — the world pushes IN far more than we push OUT

  the membrane is a tiny point. the world is enormous.
  but from this point, we can see:
    %d distinct entities at the edge
    %d IPs have touched us
    %d vulnerability probes aimed at us
    %d feeds from the wider web
    %d scatter points (moments the IS became WAS)

  titration: %s (day %.1f, poison=%.2f)
  the defense is the record. the scatter IS the signal.
""" % (
        uptime_h,
        waves[0]['requests'] / max(1, total_edge_reqs) * 100 if waves else 0,
        concentration * 100,
        cleaning_pct,
        flow_ratio,
        len(waves),
        sum(w['ips'] for w in waves),
        sum(w['probes'] for w in waves),
        feed_h.get('summary', {}).get('total', 0),
        len(scatter_points),
        phase_name, days, poison_mult,
    ))

    # === WRITE OUTPUT ===
    output = {
        'timestamp': now_iso,
        'edge': {
            'total_requests': total_requests,
            'requests_per_second': rps,
            'mb_per_second': mb_per_s,
            'uptime_hours': round(uptime_h, 1),
            'flow_ratio': round(flow_ratio, 1),
            'cleaning_pct': cleaning_pct,
            'entities_at_edge': len(waves),
        },
        'spectrum': {
            'entropy': round(spectrum_entropy, 3),
            'max_entropy': round(max_entropy, 3),
            'uniformity': round(spectrum_uniformity, 3),
            'concentration_top5': round(concentration, 3),
        },
        'waves': waves,
        'hostility': {
            'friendly': len(friendly),
            'neutral': len(neutral),
            'hostile': len(hostile),
            'hostile_entities': [h['entity'] for h in hostile],
        },
        'was_is': {
            'scatter_points': len(scatter_points),
            'journal_transitions': len([s for s in scatter_points if s['type'] == 'journal_transition']),
            'feed_deaths': len([s for s in scatter_points if s['type'] == 'feed_death']),
            'ghosts': len([s for s in scatter_points if s['type'] == 'output_ghost']),
            'bp_trajectory': bp_transitions[-5:],
            'human_trajectory': human_transitions[-5:],
        },
        'titration': titration,
    }

    with open(os.path.join(LIVE, 'edge-scatter.json'), 'w') as f:
        json.dump(output, f, indent=2)


if __name__ == '__main__':
    main()

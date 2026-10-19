"""taxonomy-braid.py — Cross-reference every branch of Yggdrasil.

When multiple taxonomy systems agree on an entity, confidence rises.
When they disagree, that's interesting too — it means the entity
sits at a boundary, a transition, an edge.

The braid measures:
  - convergence: how many systems agree
  - divergence: where systems disagree
  - boundaries: entities that straddle categories
  - depth: how many layers deep classification goes

This is the mycorrhizal network of the tree.
The roots talk to the branches through here.
"""
import json, os, time, sys

sys.path.insert(0, '/opt/membrane')
from sigmoid import sigmoid

LIVE = '/opt/membrane/live-terminal'
DETROIT = '/opt/ecoPrimals/detroit/public'
OUTPUT = os.path.join(LIVE, 'taxonomy-braid.json')


def r(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}


def normalize_class(cls):
    """Map different taxonomy names to a common polarity."""
    positive = {'self', 'mutualist', 'commensal', 'cooperating', 'fresh',
                'leavened', 'gold', 'human', 'alive'}
    negative = {'non-self', 'parasite', 'pathogen', 'defecting', 'expired',
                'fossil', 'stealth', 'dead'}
    neutral = {'null', 'partial', 'other', 'ghost', 'stale', 'rising',
               'raw', 'silver', 'bronze', 'iron', 'unknown'}

    cls_lower = cls.lower().replace('-', '').replace('_', '')
    if cls_lower in positive or any(p in cls_lower for p in positive):
        return 'positive'
    elif cls_lower in negative or any(n in cls_lower for n in negative):
        return 'negative'
    else:
        return 'neutral'


def main():
    now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    # Load all taxonomy sources
    cls_data = r(os.path.join(DETROIT, 'classification.json'))
    cls_entities = cls_data.get('entities', {})

    sss = r(os.path.join(LIVE, 'scan_sweep_sort.json'))
    scan = sss.get('scan', {})

    sym = r(os.path.join(LIVE, 'symbiosis.json'))
    sym_entities = sym.get('entities', [])

    coop = r(os.path.join(LIVE, 'cooperation.json'))
    coop_responses = coop.get('responses', {})

    obj = r(os.path.join(LIVE, 'object-engine.json'))
    gold_objects = {g['name']: g for g in obj.get('gold', [])}

    # Build entity polarity from each system
    entity_polarities = {}

    # 1. Classification system
    for name, data in cls_entities.items():
        if not isinstance(data, dict):
            continue
        cls = data.get('classification', 'unknown')
        polarity = normalize_class(cls)
        if name not in entity_polarities:
            entity_polarities[name] = {}
        entity_polarities[name]['classification'] = {
            'class': cls,
            'polarity': polarity,
            'confidence': data.get('confidence', 0),
        }

    # 2. Symbiosis system
    if isinstance(sym_entities, list):
        for ent in sym_entities:
            if not isinstance(ent, dict):
                continue
            name = ent.get('id', ent.get('name', ''))
            if not name:
                continue
            cls = ent.get('classification', ent.get('symbiotic_class', ''))
            polarity = normalize_class(cls)
            if name not in entity_polarities:
                entity_polarities[name] = {}
            entity_polarities[name]['symbiosis'] = {
                'class': cls,
                'polarity': polarity,
            }

    # 3. Cooperation system
    for name, data in coop_responses.items():
        if not isinstance(data, dict):
            continue
        action = data.get('action', '')
        polarity = 'positive' if action == 'cooperate' else 'negative'
        if name not in entity_polarities:
            entity_polarities[name] = {}
        entity_polarities[name]['cooperation'] = {
            'action': action,
            'response': data.get('response', ''),
            'polarity': polarity,
            'score': data.get('coop_score', 0),
        }

    # 4. Object tier system
    for name, data in gold_objects.items():
        if name not in entity_polarities:
            entity_polarities[name] = {}
        entity_polarities[name]['tier'] = {
            'tier': 'gold',
            'rank': data.get('rank', 0),
            'score': data.get('score', 0),
            'polarity': 'positive',
        }

    # Compute braid metrics
    convergent = []  # all systems agree
    divergent = []   # systems disagree
    boundary = []    # mixed signals
    deep = []        # classified by 3+ systems

    for name, systems in entity_polarities.items():
        system_count = len(systems)
        polarities = [s.get('polarity', 'neutral') for s in systems.values()]
        unique_polarities = set(polarities)

        entry = {
            'name': name,
            'systems': system_count,
            'polarities': {sys_name: sys_data.get('polarity', 'neutral')
                          for sys_name, sys_data in systems.items()},
            'classes': {sys_name: sys_data.get('class', sys_data.get('action', sys_data.get('tier', '?')))
                       for sys_name, sys_data in systems.items()},
        }

        if system_count >= 3:
            deep.append(entry)

        if len(unique_polarities) == 1 and system_count >= 2:
            entry['convergence'] = 'strong'
            convergent.append(entry)
        elif len(unique_polarities) > 1 and 'positive' in unique_polarities and 'negative' in unique_polarities:
            entry['convergence'] = 'divergent'
            divergent.append(entry)
        elif len(unique_polarities) > 1:
            entry['convergence'] = 'boundary'
            boundary.append(entry)

    # Compute overall braid strength
    total = len(entity_polarities)
    multi_system = sum(1 for v in entity_polarities.values() if len(v) >= 2)
    braid_strength = sigmoid(multi_system / max(1, total), 0.3, 8) if total > 0 else 0

    result = {
        'timestamp': now_iso,
        'name': 'taxonomy-braid',
        'description': 'the mycorrhizal network of Yggdrasil — cross-referencing every branch',
        'summary': {
            'total_entities': total,
            'multi_system': multi_system,
            'braid_strength': round(braid_strength, 3),
            'convergent': len(convergent),
            'divergent': len(divergent),
            'boundary': len(boundary),
            'deep_classified': len(deep),
        },
        'convergent': sorted(convergent, key=lambda x: -x['systems'])[:20],
        'divergent': sorted(divergent, key=lambda x: -x['systems'])[:20],
        'boundary': sorted(boundary, key=lambda x: -x['systems'])[:10],
        'deep': sorted(deep, key=lambda x: -x['systems'])[:10],
        'note': 'convergence = confidence. divergence = edges. boundaries = transitions.',
    }

    with open(OUTPUT, 'w') as f:
        json.dump(result, f, indent=2)

    s = result['summary']
    print("taxonomy braid:")
    print("  %d entities, %d multi-system (%.0f%%)" % (
        s['total_entities'], s['multi_system'],
        s['multi_system'] / max(1, s['total_entities']) * 100))
    print("  braid strength: %.3f" % s['braid_strength'])
    print("  convergent: %d  divergent: %d  boundary: %d  deep: %d" % (
        s['convergent'], s['divergent'], s['boundary'], s['deep_classified']))

    if convergent:
        print("\n  convergent (all systems agree):")
        for c in convergent[:5]:
            print("    %-30s %d systems → %s" % (
                c['name'][:30], c['systems'], list(c['polarities'].values())[0]))

    if divergent:
        print("\n  divergent (systems disagree):")
        for d in divergent[:5]:
            print("    %-30s %d systems → %s" % (
                d['name'][:30], d['systems'], d['polarities']))

    if deep:
        print("\n  deep (3+ systems classify):")
        for dp in deep[:5]:
            print("    %-30s %d systems: %s" % (
                dp['name'][:30], dp['systems'], dp['classes']))


if __name__ == '__main__':
    main()

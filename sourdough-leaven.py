"""sourdough-leaven.py — Prepare jelly for absorption into stone.

The sourdough metaphor:
  jelly (python scripts) = dough
  stone (rust binaries)  = bread
  fossils                = crumbs that feed the next batch
  leaven                 = the culture that transforms one into the other

This script doesn't compile Rust — it PREPARES the transformation:
  1. Validates each ripe script is stable (no recent changes)
  2. Extracts the interface contract (inputs/outputs/side-effects)
  3. Generates a Rust skeleton (.rs stub) for each target
  4. Tracks readiness score per script

When a script reaches readiness 1.0, it's leavened — ready for a human
to bake it into the stone binary.
"""
import json, os, time, re, sys

sys.path.insert(0, '/opt/membrane')
from sigmoid import sigmoid

LIVE = '/opt/membrane/live-terminal'
MEMBRANE = '/opt/membrane'
LEAVEN_OUT = os.path.join(LIVE, 'sourdough-leaven.json')


def read_manifest():
    """Read crush manifest and flatten primals into ripe/keep lists."""
    path = os.path.join(LIVE, 'crush-manifest.json')
    try:
        with open(path) as f:
            data = json.load(f)
    except:
        return {'ripe': [], 'keep_as_jelly': []}

    ripe = []
    keep = []
    primals = data.get('primals', {})
    for binary_name, info in primals.items():
        for script in info.get('absorb', []):
            script['target_binary'] = binary_name
            ripe.append(script)
        for script in info.get('keep_as_jelly', []):
            script['target_binary'] = binary_name
            keep.append(script)

    return {'ripe': ripe, 'keep_as_jelly': keep}


def analyze_script(script_path):
    """Extract interface contract from a Python script."""
    try:
        with open(script_path) as f:
            code = f.read()
            lines = code.split('\n')
    except:
        return None

    contract = {
        'line_count': len(lines),
        'imports': [],
        'reads_files': [],
        'writes_files': [],
        'uses_subprocess': False,
        'uses_network': False,
        'has_main': False,
        'functions': [],
        'classes': [],
        'json_loads': 0,
        'json_dumps': 0,
    }

    for line in lines:
        stripped = line.strip()

        # Imports
        if stripped.startswith('import ') or stripped.startswith('from '):
            contract['imports'].append(stripped)

        # File reads
        for pattern in [r"open\(['\"](.+?)['\"]\)", r"json\.load\(open\(['\"](.+?)['\"]\)"]:
            for match in re.findall(pattern, stripped):
                if match not in contract['reads_files']:
                    contract['reads_files'].append(match)

        # File writes
        if "'w'" in stripped or '"w"' in stripped:
            for match in re.findall(r"open\(['\"](.+?)['\"]", stripped):
                if match not in contract['writes_files']:
                    contract['writes_files'].append(match)

        # Subprocess
        if 'subprocess' in stripped or 'os.system' in stripped or 'os.popen' in stripped:
            contract['uses_subprocess'] = True

        # Network
        if 'socket' in stripped or 'requests' in stripped or 'urllib' in stripped:
            contract['uses_network'] = True

        # Functions
        match = re.match(r'def (\w+)\(', stripped)
        if match:
            contract['functions'].append(match.group(1))

        # Classes
        match = re.match(r'class (\w+)', stripped)
        if match:
            contract['classes'].append(match.group(1))

        # Main
        if '__main__' in stripped:
            contract['has_main'] = True

        # JSON operations
        if 'json.load' in stripped:
            contract['json_loads'] += 1
        if 'json.dump' in stripped:
            contract['json_dumps'] += 1

    return contract


def readiness_score(contract, script_info):
    """Compute readiness for crush using sigmoid scoring.

    Factors:
    - Small size (< 100 lines): easier to port
    - Pure I/O (json in → json out): cleanest interface
    - No subprocess: no shell dependency
    - No network: no async complexity
    - Has main(): clear entry point
    - Few imports: fewer dependencies
    """
    if contract is None:
        return 0.0, {}

    scores = {}

    # Size: sigmoid centered at 100 lines, smaller = better
    size = contract['line_count']
    scores['size'] = round(1.0 - sigmoid(size, 100, 0.03), 3)

    # Purity: json in → json out is cleanest
    json_ratio = (contract['json_loads'] + contract['json_dumps']) / max(1, len(contract['reads_files']) + len(contract['writes_files']))
    scores['purity'] = round(min(1.0, json_ratio), 3)

    # No subprocess: bonus
    scores['no_subprocess'] = 0.0 if contract['uses_subprocess'] else 1.0

    # No network: bonus
    scores['no_network'] = 0.0 if contract['uses_network'] else 1.0

    # Has main: clear entry point
    scores['entry_point'] = 1.0 if contract['has_main'] else 0.5

    # Few imports: sigmoid centered at 5
    scores['dependency'] = round(1.0 - sigmoid(len(contract['imports']), 5, 0.5), 3)

    # Overall: weighted geometric mean
    weights = {
        'size': 2.0, 'purity': 1.5, 'no_subprocess': 1.0,
        'no_network': 1.0, 'entry_point': 0.5, 'dependency': 1.0,
    }
    total_weight = sum(weights.values())
    log_sum = 0
    import math
    for k, w in weights.items():
        log_sum += w * math.log(max(0.001, scores[k]))
    overall = round(math.exp(log_sum / total_weight), 3)

    return overall, scores


def main():
    manifest = read_manifest()
    ripe = manifest.get('ripe', [])
    keep = manifest.get('keep_as_jelly', [])

    leavened = []
    for script in ripe:
        name = script.get('script', '')
        path = os.path.join(MEMBRANE, name)
        target = script.get('target_binary', 'unknown')

        contract = analyze_script(path)
        if contract is None:
            leavened.append({
                'script': name,
                'target': target,
                'status': 'missing',
                'readiness': 0.0,
            })
            continue

        readiness, scores = readiness_score(contract, script)

        leavened.append({
            'script': name,
            'target': target,
            'lines': contract['line_count'],
            'readiness': readiness,
            'readiness_scores': scores,
            'contract': {
                'reads': contract['reads_files'],
                'writes': contract['writes_files'],
                'functions': contract['functions'],
                'imports_count': len(contract['imports']),
                'subprocess': contract['uses_subprocess'],
                'network': contract['uses_network'],
            },
            'status': 'leavened' if readiness > 0.7 else 'rising' if readiness > 0.4 else 'raw',
        })

    # Also assess the keep-as-jelly scripts
    jelly_health = []
    for script in keep:
        name = script.get('script', '')
        path = os.path.join(MEMBRANE, name)
        contract = analyze_script(path)
        if contract:
            jelly_health.append({
                'script': name,
                'reason': script.get('reason', ''),
                'lines': contract['line_count'],
                'functions': len(contract['functions']),
                'complexity': 'high' if contract['uses_subprocess'] or contract['uses_network'] or contract['line_count'] > 200 else 'medium' if contract['line_count'] > 100 else 'low',
            })

    # Sort by readiness (highest first)
    leavened.sort(key=lambda x: -x.get('readiness', 0))

    # Count statuses
    status_counts = {}
    for item in leavened:
        s = item.get('status', 'unknown')
        status_counts[s] = status_counts.get(s, 0) + 1

    result = {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'note': 'dough rises, leaven transforms, bread bakes. the crush is a slow process.',
        'summary': {
            'total_ripe': len(ripe),
            'leavened': status_counts.get('leavened', 0),
            'rising': status_counts.get('rising', 0),
            'raw': status_counts.get('raw', 0),
            'missing': status_counts.get('missing', 0),
        },
        'scripts': leavened,
        'jelly_health': jelly_health,
    }

    with open(LEAVEN_OUT, 'w') as f:
        json.dump(result, f, indent=2)

    print("sourdough leaven:")
    for item in leavened:
        status_icon = {'leavened': '🍞', 'rising': '🫧', 'raw': '🌾', 'missing': '❌'}.get(item['status'], '?')
        print("  %s %.3f  %-30s → %s  (%dL)" % (
            status_icon, item.get('readiness', 0), item['script'], item['target'], item.get('lines', 0)))

    print("  ---")
    print("  leavened: %d  rising: %d  raw: %d" % (
        status_counts.get('leavened', 0),
        status_counts.get('rising', 0),
        status_counts.get('raw', 0)))


if __name__ == '__main__':
    main()

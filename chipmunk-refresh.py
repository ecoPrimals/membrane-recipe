"""chipmunk-refresh.py — unstick the stale base fields in chipmunk.json.

Squirrel binary writes the base (timestamp, wake_level, uptime, requests)
only on membrane announcements, which can stall. This sense script refreshes
the fields that go stale, so downstream consumers always see 'now'.

The wake_level gets replaced with the real computed value from wake-cycle.
The timestamp becomes now. The uptime counts from the squirrel process start.
"""
import json, os, time, subprocess

LIVE = '/opt/membrane/live-terminal'

def main():
    path = os.path.join(LIVE, 'chipmunk.json')
    try:
        chipmunk = json.load(open(path))
    except:
        return

    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    # Get real wake_level from wake-cycle feed
    try:
        wake = json.load(open(os.path.join(LIVE, 'wake-cycle.json')))
        real_wake = wake.get('wake_level', chipmunk.get('wake_level', 1.0))
    except:
        real_wake = chipmunk.get('wake_level', 1.0)

    # Get squirrel process uptime
    try:
        result = subprocess.run(
            ['ps', '-o', 'etimes=', '-p',
             subprocess.check_output(['pgrep', '-f', 'squirrel server'],
                                     text=True).strip().split('\n')[0]],
            capture_output=True, text=True, timeout=5
        )
        uptime_secs = int(result.stdout.strip())
    except:
        uptime_secs = chipmunk.get('uptime_secs', 0)

    # Refresh stale fields
    chipmunk['timestamp'] = now
    chipmunk['wake_level'] = real_wake
    chipmunk['uptime_secs'] = uptime_secs

    with open(path, 'w') as f:
        json.dump(chipmunk, f, separators=(',', ':'))

if __name__ == '__main__':
    main()

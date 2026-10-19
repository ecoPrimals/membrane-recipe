#!/bin/bash
# cap-epitope.sh — fast epitope-history limiter (runs every 30s via systemd timer)
# Counteracts skunky-ingest 200-entry 17MB writes
F=/opt/membrane/live-terminal/epitope-history.json
S=$(stat -c%s "$F" 2>/dev/null || echo 0)
if [ "$S" -gt 524288 ]; then  # >512KB
  python3 -c "
import json
with open(\"$F\") as f: d=json.load(f)
if isinstance(d,list) and len(d)>5:
    d=d[-5:]
    with open(\"$F\",\"w\") as f: json.dump(d,f,separators=(\",\",\":\"))
" 2>/dev/null
fi

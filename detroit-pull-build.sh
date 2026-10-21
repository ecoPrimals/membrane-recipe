#!/bin/bash
# detroit-pull-build.sh — pull from ALL remotes + rebuild detroit Zola site
# Wave 191b: now fetches from github (northGate) AND forgejo (eastGate)
# Uses HTTP shallow fetch (488MB repo, 2GB VPS — SSH fetch times out)
set -euo pipefail

REPO=/opt/ecoPrimals/detroit/worktree
OUT=/opt/ecoPrimals/detroit
STATE=/run/membrane/detroit-last-built
LOG=/var/log/membrane/detroit-build.log

cd "$REPO"

# CANARY: clean build output
DIRTY=$(git status --porcelain -- site/public/ 2>/dev/null | wc -l)
if [ "$DIRTY" -gt 0 ]; then
    echo "[$(date -Is)] detroit: CANARY — $DIRTY dirty files, cleaning" >> "$LOG"
    git checkout -- site/public/ 2>/dev/null || true
fi

# ─── FETCH — northGate owns github. github first, then forgejo. ───
NEED_BUILD=false
for REMOTE_NAME in github http-origin origin; do
    if git fetch --depth=1 "$REMOTE_NAME" main 2>>"$LOG"; then
        LOCAL=$(git rev-parse HEAD)
        REMOTE_HEAD=$(git rev-parse "$REMOTE_NAME/main" 2>/dev/null || echo "unknown")

        if [ "$LOCAL" != "$REMOTE_HEAD" ] && [ "$REMOTE_HEAD" != "unknown" ]; then
            FF=false
            git merge-base --is-ancestor "$LOCAL" "$REMOTE_HEAD" 2>/dev/null && FF=true
            # northGate owns github. take it even when histories diverged.
            if [ "$FF" = "true" ] || [ "$REMOTE_NAME" = "github" ]; then
                echo "[$(date -Is)] detroit: taking $REMOTE_NAME ($LOCAL → $REMOTE_HEAD) ff=$FF" >> "$LOG"
                git reset --hard "$REMOTE_HEAD" 2>>"$LOG"
                NEED_BUILD=true
                break
            fi
        fi
    fi
done

# northGate pipeline status — always written so the capillary can see lag
HEAD=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
GITHUB_HEAD=$(git rev-parse github/main 2>/dev/null || echo "unknown")
python3 - <<PY
import json, time, os
p = {
  "ts": time.time(),
  "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  "gate": "northGate",
  "role": "github is the authority. golgi pulls github first.",
  "detroit": {
    "local": "$HEAD",
    "github": "$GITHUB_HEAD",
    "ahead": "$HEAD" != "$GITHUB_HEAD" and "$GITHUB_HEAD" != "unknown",
  },
  "note": "northGate in charge of publicRecord. site pulls when github moves."
}
open("/opt/membrane/live-terminal/northgate-pipeline.json","w").write(json.dumps(p, separators=(",", ":")))
PY

LAST=$(cat "$STATE" 2>/dev/null || echo "none")

if [ "$HEAD" = "$LAST" ] && [ "$NEED_BUILD" = "false" ]; then
    exit 0
fi

echo "[$(date -Is)] detroit: BUILDING ($LAST → $HEAD)" >> "$LOG"

cd site
rm -rf "$OUT/public-next"
if ZOLA_BRAID_AUTHORIZED=1 timeout 280 /usr/local/bin/zola-real build -o "$OUT/public-next" --force >> "$LOG" 2>&1; then
    mv "$OUT/public" "$OUT/public-old" 2>/dev/null || true
    mv "$OUT/public-next" "$OUT/public"
    rm -rf "$OUT/public-old"
    echo "$HEAD" > "$STATE"
    echo "[$(date -Is)] detroit: BUILD COMPLETE" >> "$LOG"
    /opt/membrane/pollen-emit.sh "$HEAD" detroit &
else
    echo "[$(date -Is)] detroit: BUILD FAILED — CANARY ALERT" >> "$LOG"
    rm -rf "$OUT/public-next" 2>/dev/null
    exit 1
fi

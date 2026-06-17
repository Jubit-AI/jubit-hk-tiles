#!/usr/bin/env bash
# Detailed-only re-integration (stitch->harmonize->grade->dzi) for hole fixes.
# Deterministic, so re-uploading to R2 is incremental. Skips the non-deterministic
# nanobanana cute step (preserves the existing cute look + avoids API cost).
# Args: district out-dir names (e.g. mongkok-hd central-hd ...).
set -euo pipefail
cd "$(dirname "$0")/.."
for d in "$@"; do
  D="scripts/out/$d"
  [ -d "$D" ] || { echo "SKIP $d (no out-dir)"; continue; }
  echo "=== $d: detailed ==="
  uv run python scripts/stitch_grid.py --in "$D" --out "$D/_stitched.png" 2>&1 | tail -1
  uv run python scripts/harmonize_sea.py --in "$D/_stitched.png" --out "$D/_stitched_sea.png" 2>&1 | tail -1
  uv run python scripts/grade_viz.py --in "$D/_stitched_sea.png" --out "$D/_graded.png" 2>&1 | tail -1
  rm -rf "viewer/${d}_files" "viewer/$d.dzi"
  uv run python scripts/make_dzi.py --in "$D/_graded.png" --out "viewer/$d" 2>&1 | tail -1
  rm -f "$D/_stitched.png" "$D/_stitched_sea.png" "$D/_graded.png" 2>/dev/null
done
echo "=== DETAILED INTEGRATE DONE ==="

#!/usr/bin/env bash
# Targeted re-bake of specific hole/missing tiles. Longer settle + lower
# concurrency than the bulk bake, to clear persistent render-failures.
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.bun/bin:$PATH"
JOBS=(
  "central-hd:22.290,114.164:r4_c4,r5_c0"
  "causeway-hd:22.280,114.184:r5_c2"
  "the-peak-hd:22.2759,114.1455:r4_c7,r5_c3"
  "north-point-hd:22.2910,114.2000:r4_c5,r5_c0"
  "kai-tak-hd:22.3280,114.1990:r4_c3,r5_c6,r5_c4"
  "sha-tin-hd:22.3820,114.1880:r0_c4,r0_c7,r2_c6"
  "aberdeen-hd:22.2480,114.1540:r4_c0,r4_c1,r4_c2,r4_c3"
)
for j in "${JOBS[@]}"; do
  dir="${j%%:*}"; rest="${j#*:}"; ctr="${rest%%:*}"; only="${rest##*:}"
  echo "=== HOLE-REBAKE $dir --only $only ==="
  uv run python scripts/central_render_bake.py --viewmap "$ctr,8,6,1500" \
    --layer visualisation --style raw --out-dir "$dir" \
    --concurrency 2 --settle-ms 10000 --tile-timeout 150000 --only "$only" 2>&1 | grep -E "baked|❌" | tail -2
done
echo "=== HOLE REBAKE DONE ==="

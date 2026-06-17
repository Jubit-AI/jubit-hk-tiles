#!/usr/bin/env bash
# Re-bake every map with flat tiles using the HARDENED baker (auto-retries the
# silent f2-flat failures). Small maps first so the retry behaviour is visible fast.
# Audits each map right after. settle 9s base; the baker retries flats at 1.6x/2.2x.
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.bun/bin:$PATH"
JOBS=(
  "kennedy-town-hku-hd:22.2820,114.1280"
  "sai-kung-hd:22.3820,114.2730"
  "hk-disneyland-hd:22.3130,114.0430"
  "repulse-bay-hd:22.2350,114.1960"
  "north-point-hd:22.2910,114.2000"
  "ocean-park-hd:22.2460,114.1750"
  "tsing-ma-bridge-hd:22.3510,114.0730"
  "stanley-hd:22.2188,114.2130"
  "aberdeen-hd:22.2480,114.1540"
)
for j in "${JOBS[@]}"; do
  dir="${j%%:*}"; ctr="${j##*:}"
  echo "=== REBAKE $dir ($ctr) ==="
  uv run python scripts/central_render_bake.py --viewmap "$ctr,8,6,1500" \
    --layer visualisation --style raw --out-dir "$dir" \
    --concurrency 2 --settle-ms 9000 --tile-timeout 160000 2>&1 | grep -E "baked|❌|⟳|FLAT-FAIL" | tail -4
  uv run python scripts/audit_flat.py "${dir%-hd}" 2>&1 | grep -E "flat"
done
echo "=== REBAKE_FLAT DONE ==="

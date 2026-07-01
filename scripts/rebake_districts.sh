#!/usr/bin/env bash
# Re-bake all 12 curated HD DISTRICTS (not landmarks) with a longer settle to
# clear timing-holes (empty tiles). Phase-C four (central/causeway/mongkok/tst)
# first — older bakes, most likely to have holes. Resumable (skips 48/48 dirs).
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.bun/bin:$PATH"
DISTRICTS=(
  "central:22.290,114.164"
  "causeway:22.280,114.184"
  "mongkok:22.319,114.169"
  "tst:22.295,114.172"
  "the-peak:22.2759,114.1455"
  "sham-shui-po:22.3303,114.1622"
  "wan-chai:22.2770,114.1730"
  "north-point:22.2910,114.2000"
  "stanley:22.2188,114.2130"
  "aberdeen:22.2480,114.1540"
  "kai-tak:22.3280,114.1990"
  "sha-tin:22.3820,114.1880"
)
for spec in "${DISTRICTS[@]}"; do
  name="${spec%%:*}"; ctr="${spec##*:}"; dir="${name}-hd"
  n=$(ls "scripts/out/$dir"/r*_c*.png 2>/dev/null | wc -l | tr -d ' ')
  if [ "$n" -ge 48 ]; then echo "=== SKIP $dir ($n/48) ==="; continue; fi
  echo "=== REBAKE $dir ($ctr) ==="
  uv run python scripts/central_render_bake.py --viewmap "$ctr,8,6,1500" \
    --layer visualisation --style raw --out-dir "$dir" \
    --concurrency 4 --settle-ms 6000 --tile-timeout 90000 2>&1 | grep -E "baked|❌|TEXTURE-FAIL" | tail -2
done
echo "=== ALL REBAKE DONE ==="
for spec in "${DISTRICTS[@]}"; do name="${spec%%:*}"; echo "${name}-hd: $(ls scripts/out/${name}-hd/r*_c*.png 2>/dev/null|wc -l|tr -d ' ')/48"; done

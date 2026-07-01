#!/usr/bin/env bash
# Re-bake the 3 districts that silently rendered flat (f2 layer didn't paint before
# the screenshot gate fired) — longer settle + lower concurrency lets f2 load.
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.bun/bin:$PATH"
JOBS=("stanley-hd:22.2188,114.2130" "aberdeen-hd:22.2480,114.1540" "north-point-hd:22.2910,114.2000")
for j in "${JOBS[@]}"; do
  dir="${j%%:*}"; ctr="${j##*:}"
  echo "=== REBAKE $dir ($ctr) ==="
  uv run python scripts/central_render_bake.py --viewmap "$ctr,8,6,1500" \
    --layer visualisation --style raw --out-dir "$dir" \
    --concurrency 2 --settle-ms 10000 --tile-timeout 160000 2>&1 | grep -E "baked|❌" | tail -1
  uv run python -c "
import glob,numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
flat=sum(1 for p in glob.glob('scripts/out/$dir/r*_c*.png') if np.asarray(Image.open(p).convert('RGB'),np.float32).reshape(-1,3).std(0).mean()<6)
print(f'$dir: {flat}/48 flat after rebake')
"
done
echo "=== REBAKE3 DONE ==="

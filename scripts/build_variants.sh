#!/usr/bin/env bash
# Phase B (weather variants) + Phase C (hero district) post-processing.
# Run after the day map (_graded.png) and the central-hd bake exist.
# Weather variants are HALF-RES (mood overview; day map holds full detail) to
# keep the deploy file-count sane.
set -euo pipefail
cd "$(dirname "$0")/.."
D=scripts/out/territory-real
HD=scripts/out/central-hd

echo "=== Phase B: half-res weather base ==="
uv run python - <<'PY'
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
im=Image.open("scripts/out/territory-real/_graded.png").convert("RGB")
im.resize((im.size[0]//2, im.size[1]//2), Image.LANCZOS).save("scripts/out/territory-real/_graded_half.png")
print("half-res base:", im.size[0]//2, "x", im.size[1]//2)
PY

for s in golden night rain typhoon; do
  echo "=== Phase B: weather '$s' → DZI ==="
  uv run python scripts/weather_grade.py --scenario "$s" \
    --in $D/_graded_half.png --out $D/_$s.png
  uv run python scripts/make_dzi.py --in $D/_$s.png --out viewer/territory-$s
done

echo "=== Phase C: hero district (central-hd) stitch → harmonize → grade → DZI ==="
uv run python scripts/stitch_grid.py --in $HD --out $HD/_stitched.png
uv run python scripts/harmonize_sea.py --in $HD/_stitched.png --out $HD/_stitched_sea.png
uv run python scripts/grade_viz.py --in $HD/_stitched_sea.png --out $HD/_graded.png
uv run python scripts/make_dzi.py --in $HD/_graded.png --out viewer/central-hd

echo "=== DONE build_variants ==="
ls -1 viewer/*.dzi
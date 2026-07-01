#!/usr/bin/env bash
# Post-process curated HD hero districts: detailed (painting) + nanobanana cute.
# Args: district out-dir names (default the curated 3). Key from /tmp/.pk.
set -euo pipefail
cd "$(dirname "$0")/.."
KEY=$(cat /tmp/.pk)
PROMPT="Cute cozy isometric Hong Kong city diorama, soft hand-painted game art: teal harbour water, lush green hills, warm parchment ground, stone-and-glass buildings with gentle cel shading and clean soft ink outlines, vibrant but tasteful colours, miniature toy-town feel. Keep the EXACT same buildings, streets, coastline and terrain layout - recolour and stylise only, do not move, add or invent geometry."
DISTRICTS=("${@:-causeway-hd mongkok-hd tst-hd}")
for d in ${DISTRICTS[@]}; do
  D="scripts/out/$d"
  echo "=== $d: detailed ==="
  uv run python scripts/stitch_grid.py --in "$D" --out "$D/_stitched.png" 2>&1 | tail -1
  uv run python scripts/harmonize_sea.py --in "$D/_stitched.png" --out "$D/_stitched_sea.png" 2>&1 | tail -1
  uv run python scripts/grade_viz.py --in "$D/_stitched_sea.png" --out "$D/_graded.png" 2>&1 | tail -1
  rm -rf "viewer/${d}_files" "viewer/$d.dzi"
  uv run python scripts/make_dzi.py --in "$D/_graded.png" --out "viewer/$d" 2>&1 | tail -1
  echo "=== $d: cute (nanobanana) ==="
  uv run python -c "
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
im=Image.open('$D/_graded.png').convert('RGB'); s=min(1248/im.width,1248/im.height,1.0)
im.resize((int(im.width*s),int(im.height*s)),Image.LANCZOS).save('/tmp/cutesrc_$d.png')"
  URL=$(curl -s -X POST -H "Authorization: Bearer $KEY" -F "file=@/tmp/cutesrc_$d.png" https://media.pollinations.ai/upload | python3 -c "import sys,json;print(json.load(sys.stdin)['url'])")
  W=$(python3 -c "from PIL import Image;print(Image.open('/tmp/cutesrc_$d.png').size[0])")
  H=$(python3 -c "from PIL import Image;print(Image.open('/tmp/cutesrc_$d.png').size[1])")
  P=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$PROMPT")
  curl -s --max-time 240 -H "Authorization: Bearer $KEY" "https://gen.pollinations.ai/image/$P?model=nanobanana&image=$URL&width=$W&height=$H&nologo=true" -o "/tmp/cute_$d.png"
  python3 -c "d=open('/tmp/cute_$d.png','rb').read(3); exit(0 if d==b'\xff\xd8\xff' else 'cute fail $d')"
  rm -rf "viewer/cute-${d}_files" "viewer/cute-$d.dzi"
  uv run python scripts/make_dzi.py --in "/tmp/cute_$d.png" --out "viewer/cute-$d" 2>&1 | tail -1
  # free the big intermediates immediately (DZIs are built) — keeps disk low across many districts
  rm -f "$D/_stitched.png" "$D/_stitched_sea.png" "$D/_graded.png" "/tmp/cute_$d.png" "/tmp/cutesrc_$d.png" 2>/dev/null
done
echo "=== HD INTEGRATE DONE ==="
ls -1 viewer/causeway-hd.dzi viewer/mongkok-hd.dzi viewer/tst-hd.dzi viewer/cute-causeway-hd.dzi 2>/dev/null

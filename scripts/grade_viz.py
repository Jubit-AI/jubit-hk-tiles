#!/usr/bin/env python3
"""Light vibrance grade for the f2 visualisation-map stitch.

The f2 ("Visualisation Map" = 3d.map.gov.hk) aerial textures are real but dark
and muted. This applies the approved *light* grade — gentle gamma-lift + gain,
then a vibrance (saturation) and a small contrast bump — so the photoreal
all-layers map (harbour water, green Peak, real skyline, coastline, roads,
vegetation) reads bright and cute WITHOUT the cel/outline pass that mushed the
detail. This is the treatment chosen for the *detailed* map (style=raw bake +
this grade), distinct from the AI "✨ Stylize" cute overview.

Treatment (locked): gamma 0.82, gain 1.10, saturation 1.45, contrast 1.08.

Usage:
  uv run python scripts/grade_viz.py --in scripts/out/territory-real/_stitched.png \
      --out scripts/out/territory-real/_graded.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

# Trusted bake output (territory stitch ~402M px) exceeds Pillow's bomb guard.
Image.MAX_IMAGE_PIXELS = None

# Locked grade constants (see module docstring / plan R2/R4).
GAMMA = 0.82
GAIN = 1.10
SATURATION = 1.45
CONTRAST = 1.08


def grade(src: Path, out: Path) -> None:
    im = Image.open(src).convert("RGB")
    a = np.asarray(im, dtype=np.float32) / 255.0
    # gamma-lift + gain (brighten the dark aerial without crushing highlights)
    a = np.clip(a ** GAMMA * GAIN, 0.0, 1.0)
    im = Image.fromarray((a * 255.0 + 0.5).astype(np.uint8), "RGB")
    # vibrance + gentle contrast
    im = ImageEnhance.Color(im).enhance(SATURATION)
    im = ImageEnhance.Contrast(im).enhance(CONTRAST)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    print(f"graded {src} -> {out}  ({im.size[0]}x{im.size[1]})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Light vibrance grade for f2 viz stitch")
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--out", dest="out", required=True, type=Path)
    args = ap.parse_args()
    grade(args.src, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

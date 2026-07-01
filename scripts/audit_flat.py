#!/usr/bin/env python3
"""Canonical flat-tile audit — total flat-tile count per map (NO neighbor filter).

A silent f2 render-failure is a flat fill (mean pixel-std ~0.8); real textured
content is std > 8. This replaces the unreliable "flat tile surrounded by >=2 city
tiles" hole-detector, which missed whole-region/whole-district failures (a fully
flat map has no city neighbors to trigger it).

Usage:
  uv run python scripts/audit_flat.py            # all 12 districts + 10 landmarks
  uv run python scripts/audit_flat.py stanley kai-tak   # specific maps
Exit code is the number of maps with flat tiles (0 = all clean).
"""
import glob
import os
import re
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

DISTRICTS = ["central", "causeway", "mongkok", "tst", "the-peak", "sham-shui-po",
             "wan-chai", "north-point", "stanley", "aberdeen", "kai-tak", "sha-tin"]
LANDMARKS = ["tian-tan-buddha", "hk-disneyland", "hk-airport", "tsing-ma-bridge",
             "wong-tai-sin", "ocean-park", "repulse-bay", "cheung-chau",
             "sai-kung", "kennedy-town-hku"]
FLAT_STD = 6.0
OUT = os.path.join(os.path.dirname(__file__), "out")


def scan(name):
    """Return (tile_count, [flat_tile_labels]) for <name>-hd, or (None, []) if no tiles."""
    ps = glob.glob(os.path.join(OUT, f"{name}-hd", "r*_c*.png"))
    if not ps:
        return None, []
    flat = []
    for p in ps:
        a = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)
        if a.reshape(-1, 3).std(0).mean() < FLAT_STD:
            flat.append(re.search(r"(r\d+_c\d+)", os.path.basename(p)).group(1))
    return len(ps), sorted(flat)


def main():
    names = sys.argv[1:] or (DISTRICTS + LANDMARKS)
    maps_with_flat = 0
    for name in names:
        tot, flat = scan(name)
        if tot is None:
            print(f"{name}-hd: NO RAW TILES")
            continue
        if flat:
            maps_with_flat += 1
        extra = f"  {flat}" if 0 < len(flat) <= 12 else ""
        print(f"{name}-hd: {len(flat)}/{tot} flat{' ⚠' if flat else ''}{extra}")
    print(f"\n{maps_with_flat} map(s) with flat tiles")
    sys.exit(maps_with_flat)


if __name__ == "__main__":
    main()

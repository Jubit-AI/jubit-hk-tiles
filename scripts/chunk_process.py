#!/usr/bin/env python3
"""Memory-safe harmonize-sea + grade in one strip pass — for territory-scale stitches
that OOM the whole-image numpy path (harmonize_sea.py + grade_viz.py) on 16GB RAM.

Replicates those two steps EXACTLY, per horizontal strip (so peak memory is one strip,
not the full 400M-px image):
  harmonize: recolour the clear-colour sea to WATER_RGB + a screen-space (x,y) ripple;
  grade:     gamma-lift+gain, then saturation (per-pixel), then a mild contrast.
The only deviation: grade's contrast uses a fixed 0.5 pivot instead of the global mean
— at CONTRAST=1.08 (8%) that's visually identical and removes the one global statistic,
so strips are seamless. Ripple uses the GLOBAL y offset, so it stays continuous.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# harmonize_sea.py constants
CLEAR_RGB = np.array([53, 101, 92], np.float32)
WATER_RGB = np.array([36, 55, 49], np.float32)
TOL = 12
# grade_viz.py constants
GAMMA, GAIN, SATURATION, CONTRAST = 0.82, 1.10, 1.45, 1.08
LUMA = np.array([0.299, 0.587, 0.114], np.float32)  # PIL "L" weights


def process(src: Path, out: Path, strip: int = 1024) -> None:
    src_im = Image.open(src).convert("RGB")
    W, H = src_im.size
    full = np.asarray(src_im, np.uint8)          # load once (~1.2GB at territory scale)
    del src_im
    result = np.empty_like(full)
    sea_px = 0
    for y0 in range(0, H, strip):
        y1 = min(H, y0 + strip)
        arr = full[y0:y1].astype(np.float32)     # strip copy (small)
        h = y1 - y0
        # --- harmonize sea ---
        mask = np.abs(arr - CLEAR_RGB).sum(2) < TOL
        yy, xx = np.mgrid[y0:y1, 0:W]            # GLOBAL y → ripple continuous across strips
        ripple = (np.sin(xx * 0.06) + np.cos(yy * 0.045) + np.sin((xx + yy) * 0.03)) * 2.2
        arr[mask] = WATER_RGB
        arr[mask, 1] += ripple[mask]
        arr[mask, 2] += ripple[mask] * 0.8
        np.clip(arr, 0, 255, out=arr)
        sea_px += int(mask.sum())
        # --- grade: gamma/gain → saturation → contrast ---
        a = np.clip((arr / 255.0) ** GAMMA * GAIN, 0.0, 1.0)
        gray = (a * LUMA).sum(2, keepdims=True)
        a = gray + (a - gray) * SATURATION       # ImageEnhance.Color
        a = 0.5 + (a - 0.5) * CONTRAST           # ImageEnhance.Contrast (fixed pivot)
        np.clip(a, 0.0, 1.0, out=a)
        result[y0:y1] = (a * 255.0 + 0.5).astype(np.uint8)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(result, "RGB").save(out)
    print(f"chunk-processed {W}x{H} → {out}  (sea {100 * sea_px / (W * H):.1f}%)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Chunked harmonize+grade (memory-safe)")
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--out", dest="out", required=True, type=Path)
    ap.add_argument("--strip", type=int, default=1024)
    args = ap.parse_args()
    process(args.src, args.out, args.strip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Phase B — weather & time-of-day variants of the detailed f2 map.

Derives golden-hour / night / rain / typhoon looks from the SINGLE graded
territory stitch (scripts/out/territory-real/_graded.png) as a deterministic
numpy post-process — NO per-scenario re-bake. Each variant is then DZI'd and
the viewer's scenario switcher (viewer/index.html #scenarios) toggles between
them. "day" is the graded image itself (territory.dzi), so it is not produced
here.

This mirrors the live-render `uNight`/weather axis in softStylise.js (same
scenario names + intent) but operates on the baked pixels so the deployed map
gets every scenario for the cost of one bake. Grades are screen-space
deterministic (rain/typhoon streaks key off absolute pixel coords) so they stay
tileable / seamless across the DZI pyramid.

Usage:
  uv run python scripts/weather_grade.py --scenario golden \
      --in scripts/out/territory-real/_graded.png \
      --out scripts/out/territory-real/_golden.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

# Trusted bake output (~402M px) exceeds Pillow's bomb guard — same lift as the
# rest of the pipeline (grade_viz.py / make_dzi.py).
Image.MAX_IMAGE_PIXELS = None

SCENARIOS = ("golden", "night", "rain", "typhoon")


def _luma(a: np.ndarray) -> np.ndarray:
    """Per-pixel luma (H,W) from an (H,W,3) float array."""
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def _chroma(a: np.ndarray) -> np.ndarray:
    """Per-pixel chroma = max-min channel (H,W)."""
    return a.max(axis=-1) - a.min(axis=-1)


def _streaks(h: int, w: int, period: float, slant: float, width: float) -> np.ndarray:
    """Deterministic diagonal rain streaks as an (H,W) float mask in [0,1].

    Keyed off ABSOLUTE pixel coords (not time/random) so the pattern is identical
    on every regenerate and seamless across DZI tiles. Fine period (a few px) → a
    subtle texture that only reads when zoomed in, never a band of scratches.
    """
    xs = np.arange(w, dtype=np.float32) * slant
    ys = np.arange(h, dtype=np.float32)
    phase = (ys[:, None] + xs[None, :]) % period       # (H,W) broadcast
    s = phase / period
    # narrow bright line near s==0 (ramps down over `width` of the period)
    return np.clip(1.0 - s / max(width, 1e-3), 0.0, 1.0)


def _golden(a: np.ndarray) -> np.ndarray:
    """Golden-hour: warm low-sun grade + amber wash into the shadows."""
    warm = a * np.array([1.14, 1.01, 0.80], np.float32)        # push warm, cut blue
    l = _luma(a)[..., None]
    amber = np.array([1.00, 0.78, 0.43], np.float32)
    out = warm * 0.88 + amber * ((1.0 - l) * 0.30)            # amber in shadows/mids
    out = (out - 0.5) * 1.08 + 0.5 + 0.015                    # gentle contrast + lift
    return out


def _night(a: np.ndarray) -> np.ndarray:
    """Night: deep-harbour dusk; bright windows + saturated signs ignite warm."""
    l = _luma(a)[..., None]
    ch = _chroma(a)[..., None]
    deep = np.array([0.05, 0.10, 0.16], np.float32)           # deep dusk blue
    base = (deep * (1.0 - np.clip(l * 1.2, 0, 1)) + a * 0.5 * np.clip(l * 1.2, 0, 1)) * 0.62
    is_light = np.clip((l - 0.55) / 0.25, 0, 1)               # lit windows (bright)
    is_accent = np.clip((ch - 0.18) / 0.16, 0, 1) * (1.0 - np.clip((l - 0.7) / 0.2, 0, 1))
    glow = np.clip(is_light + is_accent * 0.8, 0, 1)          # neon/window mask
    warm_light = np.clip(a * 1.6 + np.array([0.25, 0.18, 0.05], np.float32), 0, 1)
    return base * (1.0 - glow) + warm_light * glow


def _rain(a: np.ndarray) -> np.ndarray:
    """Rain: desaturated, cool, light fog veil + fine diagonal streaks."""
    l = _luma(a)[..., None]
    gray = a * 0.45 + l * 0.55                                 # desaturate
    cool = gray * np.array([0.93, 0.97, 1.05], np.float32)     # cool cast
    fog = np.array([0.60, 0.64, 0.70], np.float32)
    out = cool * 0.82 + fog * 0.18                             # fog veil
    streak = _streaks(a.shape[0], a.shape[1], period=7.0, slant=0.5, width=0.18)
    return (out + streak[..., None] * 0.06) * 0.96


def _typhoon(a: np.ndarray) -> np.ndarray:
    """Typhoon: heavy low-key grey-green, thick fog, harder streaks, darker."""
    l = _luma(a)[..., None]
    gray = a * 0.28 + l * 0.72                                 # heavy desaturate
    greygreen = gray * np.array([0.86, 0.92, 0.88], np.float32)
    fog = np.array([0.52, 0.56, 0.57], np.float32)
    out = (greygreen * 0.72 + fog * 0.28) * 0.82              # fog + darken
    streak = _streaks(a.shape[0], a.shape[1], period=5.0, slant=0.8, width=0.30)
    return out + streak[..., None] * 0.05


_GRADERS = {"golden": _golden, "night": _night, "rain": _rain, "typhoon": _typhoon}


def grade(src: Path, out: Path, scenario: str) -> None:
    if scenario not in _GRADERS:
        raise ValueError(f"unknown scenario {scenario!r}; choose from {SCENARIOS}")
    im = Image.open(src).convert("RGB")
    a = np.asarray(im, dtype=np.float32) / 255.0
    a = np.clip(_GRADERS[scenario](a), 0.0, 1.0)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((a * 255.0 + 0.5).astype(np.uint8), "RGB").save(out)
    print(f"{scenario}: {src} -> {out}  ({im.size[0]}x{im.size[1]})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Weather/time variants of the f2 map")
    ap.add_argument("--scenario", required=True, choices=SCENARIOS)
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--out", dest="out", required=True, type=Path)
    args = ap.parse_args()
    grade(args.src, args.out, args.scenario)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Reproduce the per-map MTR line coverage table by PROJECTION (not lat/lon boxes).

Which MTR lines belong on each map level is not a bounding-box question — the map is a
rotated, foreshortened, ellipsoid dimetric projection, so a line can be "near" in lat/lon
yet project off-frame (and vice versa). This script projects every station of every line
through each map's geo manifest and reports which lines actually land in each frame — the
authoritative source for the `MTR_LINES_FOR` table in `life/mtr_network.js`.

Run:  uv run python scripts/audit_mtr_coverage.py [--manifests <path>] [--margin 0.02] [--min 1]
It prints a human table and a JSON `{ dzi: [codes...] }` suggestion. Curate marginal
single-station lines by hand; this keeps the shipped table honest when manifests change.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import geo_transform as gt

SCRIPTS = Path(__file__).resolve().parent
STATIONS_JSON = SCRIPTS / "mtr_network.json"
DEFAULT_MANIFESTS = SCRIPTS.parent / "viewer" / "manifests.json"

# Maps we place transit on, overview → district (others get no MTR).
MAPS = [
    "territory.dzi", "hk-island-strip.dzi", "central.dzi",
    "downtown-b5.dzi", "downtown-b6.dzi", "downtown-b7.dzi",
    "downtown-c5.dzi", "downtown-c6.dzi", "downtown-c7.dzi",
    "central-hd.dzi", "wan-chai-hd.dzi", "causeway-hd.dzi", "north-point-hd.dzi",
    "kennedy-town-hku-hd.dzi", "tst-hd.dzi", "mongkok-hd.dzi", "sham-shui-po-hd.dzi",
    "kai-tak-hd.dzi", "sha-tin-hd.dzi", "wong-tai-sin-hd.dzi", "aberdeen-hd.dzi",
    "ocean-park-hd.dzi", "hk-airport-hd.dzi", "hk-disneyland-hd.dzi",
]


def in_frame(m: dict, lat: float, lon: float, margin: float) -> bool:
    w, h = m["image"]["width"], m["image"]["height"]
    px, py = gt.project(m, lat, lon)
    return -margin * w <= px <= (1 + margin) * w and -margin * h <= py <= (1 + margin) * h


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifests", type=Path, default=DEFAULT_MANIFESTS)
    ap.add_argument("--margin", type=float, default=0.02)
    ap.add_argument("--min", type=int, default=1, help="min in-frame stations to list a line")
    args = ap.parse_args()

    manifests = json.loads(args.manifests.read_text())
    net = json.loads(STATIONS_JSON.read_text())
    lines = {code: [(s["lat"], s["lon"]) for s in v["stations"]] for code, v in net.items()}

    suggestion: dict[str, list[str]] = {}
    print(f"{'map':24} lines in-frame (station count, margin {args.margin:g})")
    for dzi in MAPS:
        m = manifests.get(dzi)
        if not m:
            print(f"{dzi:24} (no manifest)")
            continue
        hits = {c: sum(1 for la, lo in pts if in_frame(m, la, lo, args.margin))
                for c, pts in lines.items()}
        hits = {c: n for c, n in hits.items() if n > 0}
        ordered = sorted(hits, key=lambda c: -hits[c])
        suggestion[dzi] = [c for c in ordered if hits[c] >= args.min]
        shown = ", ".join(f"{c}:{hits[c]}" for c in ordered) or "(none)"
        # territory shows everything → [] convention (whole network)
        print(f"{dzi:24} {shown}")
    suggestion["territory.dzi"] = []  # convention: [] = whole network
    print("\nJSON suggestion (curate marginal single-station lines by hand):")
    print(json.dumps(suggestion, indent=0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

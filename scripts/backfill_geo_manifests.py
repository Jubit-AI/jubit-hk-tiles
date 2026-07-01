#!/usr/bin/env python3
"""Backfill geotransform manifests for the already-baked DZIs.

Future bakes emit `<name>.geo.json` automatically (make_dzi.py --geo-meta). This
script backfills the EXISTING DZIs whose bake params we recovered from the rebake
scripts. It writes one `<name>.geo.json` per DZI into viewer/ AND a consolidated
`viewer/manifests.json` (keyed by dzi filename) that the living-world overlay loads
same-origin — no per-file R2 round-trips.

HD districts are EXACT: every one baked `--viewmap "<lat,lon>,8,6,1500"` → an
8192×6144 image at azimuth -15°, elevation -26.565° (central_render_bake defaults).

Overview maps (territory / central / hk-island-strip) were baked ad-hoc and their
center+view_height were never recorded. They are emitted as `provisional` with
best-estimate params — good enough for overview-zoom actor placement (a few hundred
metres of error is sub-pixel there), to be tightened by a targeted re-bake (which
will auto-emit an exact manifest) or a landmark fit. Precision needs scale with
zoom; the districts, where you see individual streets, are exact.
"""
from __future__ import annotations

import json
from pathlib import Path

import geo_transform as gt

# name -> (center_lat, center_lon). All HD districts: --viewmap "<c>,8,6,1500".
DISTRICTS = {
    "central": (22.290, 114.164),
    "causeway": (22.280, 114.184),
    "mongkok": (22.319, 114.169),
    "tst": (22.295, 114.172),
    "the-peak": (22.2759, 114.1455),
    "sham-shui-po": (22.3303, 114.1622),
    "wan-chai": (22.2770, 114.1730),
    "north-point": (22.2910, 114.2000),
    "stanley": (22.2188, 114.2130),
    "aberdeen": (22.2480, 114.1540),
    "kai-tak": (22.3280, 114.1990),
    "sha-tin": (22.3820, 114.1880),
    "tian-tan-buddha": (22.2540, 113.9050),
    "hk-disneyland": (22.3130, 114.0430),
    "hk-airport": (22.3100, 113.9200),
    "tsing-ma-bridge": (22.3510, 114.0730),
    "wong-tai-sin": (22.3420, 114.1930),
    "ocean-park": (22.2460, 114.1750),
    "repulse-bay": (22.2350, 114.1960),
    "cheung-chau": (22.2100, 114.0270),
    "sai-kung": (22.3820, 114.2730),
    "kennedy-town-hku": (22.2820, 114.1280),
}
# All HD districts share the same grid: 8 cols × 6 rows × 1024 canvas.
HD_IMAGE = (8 * 1024, 6 * 1024)  # 8192 × 6144
HD_VIEW_HEIGHT = 1500.0

# Overview maps — PROVISIONAL params (see module docstring). image sizes are the
# real baked DZI dimensions; center/view_height are best-estimates pending a fit.
OVERVIEW = {
    "territory": {"image": (24576, 20480), "center": (22.340, 114.140), "vh": 48000.0},
    "hk-island-strip": {"image": (6144, 4096), "center": (22.283, 114.165), "vh": 6000.0},
    "central": {"image": (3072, 3072), "center": (22.285, 114.158), "vh": 2400.0},
}


def main() -> int:
    viewer = Path(__file__).resolve().parent.parent / "viewer"
    viewer.mkdir(parents=True, exist_ok=True)
    manifests: dict[str, dict] = {}

    for name, (clat, clon) in sorted(DISTRICTS.items()):
        dzi = f"{name}-hd.dzi"
        m = gt.build_manifest(
            dzi=dzi, image_width=HD_IMAGE[0], image_height=HD_IMAGE[1],
            center_lat=clat, center_lon=clon, view_height_meters=HD_VIEW_HEIGHT,
        )
        (viewer / f"{name}-hd.geo.json").write_text(json.dumps(m, indent=2))
        manifests[dzi] = m

    for name, cfg in OVERVIEW.items():
        dzi = f"{name}.dzi"
        m = gt.build_manifest(
            dzi=dzi, image_width=cfg["image"][0], image_height=cfg["image"][1],
            center_lat=cfg["center"][0], center_lon=cfg["center"][1],
            view_height_meters=cfg["vh"],
        )
        m["provisional"] = True  # center/view_height are estimates — see backfill docstring
        (viewer / f"{name}.geo.json").write_text(json.dumps(m, indent=2))
        manifests[dzi] = m

    consolidated = viewer / "manifests.json"
    consolidated.write_text(json.dumps(manifests, indent=2))
    print(f"backfilled {len(DISTRICTS)} district + {len(OVERVIEW)} overview manifests")
    print(f"consolidated → {consolidated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

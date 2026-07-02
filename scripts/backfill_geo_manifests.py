#!/usr/bin/env python3
"""Backfill geotransform manifests for the already-baked DZIs.

Future bakes emit `<name>.geo.json` automatically (make_dzi.py --geo-meta). This
script backfills the EXISTING DZIs whose bake params we recovered from the rebake
scripts. It writes one `<name>.geo.json` per DZI into viewer/ AND a consolidated
`viewer/manifests.json` (keyed by dzi filename) that the living-world overlay loads
same-origin — no per-file R2 round-trips.

HD districts are EXACT: every one baked `--viewmap "<lat,lon>,8,6,1500"` → an
8192×6144 image at azimuth -15°, elevation -26.565° (central_render_bake defaults).

Overview maps: ALL EXACT. `territory` and `central` from recovered bake commands
(territory from its rebake, central from the documented `--viewmap
"22.2815,114.160,3,3,1200"` in viewer/README.md). `hk-island-strip` was re-baked
2026-07-02 (its original 6×4 scale-test params were never recorded): first landmark-
fitted from IFC + Central Pier 7 pixels, then re-baked with those fitted values as
the new canonical params — exact by construction. Precision needs scale with zoom;
the districts, where you see individual streets, were always exact.
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
    "hk-airport": (22.315, 113.9200),   # enlarged re-bake (vh 3300, see VH_OVERRIDE)
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
# Per-district view_height overrides (re-baked with a wider frame than the 1500 default).
VH_OVERRIDE = {"hk-airport": 3300.0}  # enlarged to fit the whole ~4km HKIA

# Overview maps — PROVISIONAL params (see module docstring). image sizes are the
# real baked DZI dimensions; center/view_height are best-estimates pending a fit.
OVERVIEW = {
    # territory RE-BAKED to cover the whole HK Island east (Chai Wan/Shek O/Cape
    # D'Aguilar) + the west airport area — EXACT params (validated), not provisional.
    "territory": {"image": (32768, 12288), "center": (22.335, 114.065), "vh": 18400.0, "provisional": False},
    # central: EXACT — bake was `--viewmap "22.2815,114.160,3,3,1200"` (viewer/README.md);
    # centre = map centre, vh = full-image view-plane height → 3072×3072 @ vh 1200.
    "central": {"image": (3072, 3072), "center": (22.2815, 114.160), "vh": 1200.0, "provisional": False},
    # hk-island-strip: EXACT — re-baked 2026-07-02 with the landmark-fitted values as the
    # new canonical params: `--viewmap "22.2820,114.1720,6,4,2250" --layer visualisation
    # --style raw` (the same f2 raw look as the live tile; crop verified ≈ identical at
    # level-10). The original 6×4 scale-test params were never recorded; this bake defines
    # them. Note the live cute-hk-island-strip predates this re-bake (still the old tile).
    "hk-island-strip": {"image": (6144, 4096), "center": (22.2820, 114.1720), "vh": 2250.0, "provisional": False},
    # downtown grid cells — the territory map's 3×8 grid (rows A/B/C × cols 1..8), cells
    # B5..C7 = the HKSAR downtown core (all of HK Island + Kowloon), each re-baked as its
    # own HD map. EXACT by construction: centres = Newton-inverted territory cell-centre
    # pixels; vh = 18400·(4096/12288); baked `--viewmap "<c>,12,12,6133.33" --layer
    # visualisation --style raw` + γ0.78 (2 px/m — the strip family's density).
    "downtown-b5": {"image": (12288, 12288), "center": (22.3422, 114.0938), "vh": 6133.33, "provisional": False},
    "downtown-b6": {"image": (12288, 12288), "center": (22.3566, 114.1512), "vh": 6133.33, "provisional": False},
    "downtown-b7": {"image": (12288, 12288), "center": (22.3711, 114.2087), "vh": 6133.33, "provisional": False},
    "downtown-c5": {"image": (12288, 12288), "center": (22.2228, 114.1281), "vh": 6133.33, "provisional": False},
    "downtown-c6": {"image": (12288, 12288), "center": (22.2372, 114.1855), "vh": 6133.33, "provisional": False},
    "downtown-c7": {"image": (12288, 12288), "center": (22.2517, 114.2430), "vh": 6133.33, "provisional": False},
}


def main() -> int:
    viewer = Path(__file__).resolve().parent.parent / "viewer"
    viewer.mkdir(parents=True, exist_ok=True)
    manifests: dict[str, dict] = {}

    for name, (clat, clon) in sorted(DISTRICTS.items()):
        dzi = f"{name}-hd.dzi"
        m = gt.build_manifest(
            dzi=dzi, image_width=HD_IMAGE[0], image_height=HD_IMAGE[1],
            center_lat=clat, center_lon=clon,
            view_height_meters=VH_OVERRIDE.get(name, HD_VIEW_HEIGHT),
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
        if cfg.get("provisional", True):  # some overviews are still best-estimates
            m["provisional"] = True
        (viewer / f"{name}.geo.json").write_text(json.dumps(m, indent=2))
        manifests[dzi] = m

    consolidated = viewer / "manifests.json"
    consolidated.write_text(json.dumps(manifests, indent=2))
    print(f"backfilled {len(DISTRICTS)} district + {len(OVERVIEW)} overview manifests")
    print(f"consolidated → {consolidated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Ortho-dimetric geo <-> image projection for the seamless HK DZI maps.

This is the SHARED source of truth for turning a WGS84 (lat, lon) into a pixel in
one of our baked DZI images, and back. Three consumers depend on it:
  - the runtime "living world" overlay (deterministic + real-data actors),
  - the real-HK-data feed layer (place a train/plane/ferry on the right street),
  - the static-vignette placement pass (turn landcover cells into lat/lon).

It reproduces the projection the renderer bakes with (web_render/main.js
`positionCamera` → `WGS84_ELLIPSOID.getObjectFrame(lat,lon,TARGET_HEIGHT,az,el)`
+ an OrthographicCamera whose vertical extent is `view_height_meters`, tiled
seamlessly with `setViewOffset`). The bake's own `central_render_bake.map_grid`
docstring pins the ground relationship we mirror EXACTLY:

  * longitude (east–west) maps to screen-horizontal at FULL scale,
  * latitude  (north–south) maps to screen-vertical FORESHORTENED by sin(elev)
    (elev = -26.565° → sin = 0.4472 = the classic 2:1 dimetric ratio),
  * flat-earth metres/degree = 111320 (NOT the ellipsoid radius — match the bake),
  * a camera azimuth (heading, default -15°) rotates the whole ground plane in-frame.

Because the map is orthographic and each area spans at most a few tens of km, a
local-ENU tangent-plane approximation is sub-pixel accurate — no ECEF needed.

AZIMUTH SIGN: getObjectFrame's heading-sign convention is pinned empirically in
the verification step (project a known landmark, eyeball it on the DZI). The sign
lives in ONE place: `_rotate` below. If a landmark lands rotated the wrong way
about the centre, flip `AZIMUTH_SIGN`.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

# Flat-earth metres per degree of latitude — the constant the bake uses
# (central_render_bake.map_grid: `dlat = depth_m / 111320.0`). Do not "improve"
# this to the WGS84 radius; matching the bake byte-for-byte matters more.
METERS_PER_DEG_LAT = 111320.0

# Default camera rig (web_render/view.json). Overridable per manifest.
DEFAULT_AZIMUTH_DEG = -15.0
DEFAULT_ELEVATION_DEG = -26.565
DEFAULT_TARGET_HEIGHT_M = 5.0

# Empirically-pinned heading sign (see module docstring). +1 rotates the ground
# plane by -azimuth into screen axes; flip to -1 if landmark validation says so.
AZIMUTH_SIGN = 1.0


def _meters_per_deg_lon(center_lat: float) -> float:
    return METERS_PER_DEG_LAT * math.cos(math.radians(center_lat))


def _rotate(east: float, north: float, azimuth_deg: float) -> tuple[float, float]:
    """Rotate an ENU ground offset (m) into (screen-right, screen-forward) axes."""
    a = math.radians(azimuth_deg) * AZIMUTH_SIGN
    ca, sa = math.cos(a), math.sin(a)
    xr = east * ca + north * sa    # screen-right (metres, full scale)
    yf = -east * sa + north * ca   # screen-forward along ground (metres, foreshortened)
    return xr, yf


def _unrotate(xr: float, yf: float, azimuth_deg: float) -> tuple[float, float]:
    a = math.radians(azimuth_deg) * AZIMUTH_SIGN
    ca, sa = math.cos(a), math.sin(a)
    east = xr * ca - yf * sa
    north = xr * sa + yf * ca
    return east, north


def _proj(manifest: dict[str, Any]) -> dict[str, float]:
    p = manifest["projection"]
    img = manifest["image"]
    return {
        "clat": manifest["center"]["lat"],
        "clon": manifest["center"]["lon"],
        "az": p["azimuthDeg"],
        "sin_el": math.sin(math.radians(abs(p["elevationDeg"]))) or 1.0,
        "ppm": img["height"] / p["viewHeightMeters"],  # px per screen-metre (isotropic)
        "w": img["width"],
        "h": img["height"],
    }


def project(manifest: dict[str, Any], lat: float, lon: float) -> tuple[float, float]:
    """(lat, lon) -> (px, py) in the DZI's full-resolution image pixels."""
    m = _proj(manifest)
    east = (lon - m["clon"]) * _meters_per_deg_lon(m["clat"])
    north = (lat - m["clat"]) * METERS_PER_DEG_LAT
    xr, yf = _rotate(east, north, m["az"])
    px = m["w"] / 2.0 + xr * m["ppm"]
    py = m["h"] / 2.0 - yf * m["sin_el"] * m["ppm"]  # north/forward = up, image-y down
    return px, py


def unproject(manifest: dict[str, Any], px: float, py: float) -> tuple[float, float]:
    """(px, py) -> (lat, lon). Exact inverse of project()."""
    m = _proj(manifest)
    xr = (px - m["w"] / 2.0) / m["ppm"]
    yf = (m["h"] / 2.0 - py) / (m["ppm"] * m["sin_el"])
    east, north = _unrotate(xr, yf, m["az"])
    lon = m["clon"] + east / _meters_per_deg_lon(m["clat"])
    lat = m["clat"] + north / METERS_PER_DEG_LAT
    return lat, lon


def bbox_of(manifest: dict[str, Any]) -> list[float]:
    """Ground-extent envelope [w, s, e, n] from the four image corners.

    Convenience bounds only — the real transform is dimetric, so a naive bbox lerp
    is WRONG. Consumers must use project()/unproject(), not this.
    """
    w, h = manifest["image"]["width"], manifest["image"]["height"]
    corners = [unproject(manifest, x, y) for x, y in ((0, 0), (w, 0), (0, h), (w, h))]
    lats = [c[0] for c in corners]
    lons = [c[1] for c in corners]
    return [min(lons), min(lats), max(lons), max(lats)]


def build_manifest(
    *,
    dzi: str,
    image_width: int,
    image_height: int,
    center_lat: float,
    center_lon: float,
    view_height_meters: float,
    azimuth_deg: float = DEFAULT_AZIMUTH_DEG,
    elevation_deg: float = DEFAULT_ELEVATION_DEG,
    target_height_meters: float = DEFAULT_TARGET_HEIGHT_M,
    tile_size: int = 256,
    overlap: int = 1,
    fmt: str = "png",
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schemaVersion": 1,
        "dzi": dzi,
        "image": {"width": image_width, "height": image_height},
        "tile": {"size": tile_size, "overlap": overlap, "format": fmt},
        "center": {"lat": center_lat, "lon": center_lon},
        "projection": {
            "type": "orthographic-dimetric",
            "azimuthDeg": azimuth_deg,
            "elevationDeg": elevation_deg,
            "viewHeightMeters": view_height_meters,
            "targetHeightMeters": target_height_meters,
            "metersPerDegLat": METERS_PER_DEG_LAT,
        },
    }
    manifest["bboxOrder"] = "[w,s,e,n]"
    manifest["bbox"] = bbox_of(manifest)
    manifest["note"] = (
        "geo<->image is the dimetric ortho projection (azimuth+elevation "
        "foreshortening), NOT a bbox lerp. Use scripts/geo_transform.py / "
        "life/geo/project.js. bbox is a bounds hint only."
    )
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="Emit / query the geo manifest")
    ap.add_argument("--out", type=Path, help="write <out>.geo.json")
    ap.add_argument("--dzi", required=True)
    ap.add_argument("--image-width", type=int, required=True)
    ap.add_argument("--image-height", type=int, required=True)
    ap.add_argument("--center-lat", type=float, required=True)
    ap.add_argument("--center-lon", type=float, required=True)
    ap.add_argument("--view-height", type=float, required=True)
    ap.add_argument("--azimuth", type=float, default=DEFAULT_AZIMUTH_DEG)
    ap.add_argument("--elevation", type=float, default=DEFAULT_ELEVATION_DEG)
    ap.add_argument("--probe", nargs=2, type=float, metavar=("LAT", "LON"),
                    help="print the pixel for a lat/lon and exit")
    args = ap.parse_args()

    manifest = build_manifest(
        dzi=args.dzi, image_width=args.image_width, image_height=args.image_height,
        center_lat=args.center_lat, center_lon=args.center_lon,
        view_height_meters=args.view_height, azimuth_deg=args.azimuth,
        elevation_deg=args.elevation,
    )
    if args.probe:
        px, py = project(manifest, args.probe[0], args.probe[1])
        print(f"({args.probe[0]}, {args.probe[1]}) -> px={px:.1f}, py={py:.1f} "
              f"of {args.image_width}x{args.image_height}")
        return 0
    text = json.dumps(manifest, indent=2)
    if args.out:
        args.out.with_suffix(".geo.json").write_text(text)
        print(f"geo manifest → {args.out.with_suffix('.geo.json')}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

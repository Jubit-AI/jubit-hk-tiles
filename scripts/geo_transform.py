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
seamlessly with `setViewOffset`). The tiles are placed on the TRUE WGS84 ELLIPSOID
(ECEF), so we project on the ellipsoid too — a flat-earth tangent-plane drifts from
the tiles by the Earth's curvature + the ellipsoid flattening + the tangent-plane
sagitta (a few px at district scale but ~90 px at the whole-HK territory edges).

Forward projection (geo → pixel), matching the bake:
  * (lat, lon, h=TARGET_HEIGHT) → ECEF on the WGS84 ellipsoid, expressed in the map
    centre's East/North/Up basis (the exact ellipsoid ground offset, with the
    tangent-plane sagitta as the Up component);
  * azimuth (heading, default -15°) rotates East/North into screen axes;
  * elevation (-26.565°) foreshortens the screen-forward axis by sin(elev) AND the
    Up/sagitta by cos(elev) — the classic 2:1 dimetric tilt;
  * scale by ppm = image_height / view_height_meters, centre on the image.

AZIMUTH SIGN (`AZIMUTH_SIGN`, default +1): the getObjectFrame heading convention,
verified against a known-bearing landmark pair (see test_geo_transform). The rotate
lives in `project`; flip the constant if the bearing test fails. (A direct port of
getObjectFrame's full 3D Euler flips the screen-x — the decomposed form here keeps
the empirically-verified orientation, so don't "simplify" it to a raw matrix.)

The inverse `unproject` (pixel → geo) keeps a cheap flat-earth approximation — it is
only used for the `bbox` bounds hint + a COARSE nearest-district pick, where metre-
level error is irrelevant. `project` is the authoritative, ellipsoid-exact direction.
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

# WGS84 ellipsoid — the exact figure the bake places tiles on (3d-tiles-renderer's
# WGS84_ELLIPSOID). We project on this same ellipsoid so actors don't drift from the
# tiles by the Earth's curvature + flattening (tens of px at whole-HK territory scale).
WGS84_A = 6378137.0                      # semi-major axis (m)
WGS84_F = 1.0 / 298.257223563            # flattening
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)     # first eccentricity squared


def _ecef(lat: float, lon: float, height: float) -> tuple[float, float, float]:
    """Geodetic (lat, lon, h) -> ECEF (X, Y, Z) on the WGS84 ellipsoid (metres)."""
    la, lo = math.radians(lat), math.radians(lon)
    n = WGS84_A / math.sqrt(1.0 - WGS84_E2 * math.sin(la) ** 2)
    cos_la = math.cos(la)
    return (
        (n + height) * cos_la * math.cos(lo),
        (n + height) * cos_la * math.sin(lo),
        (n * (1.0 - WGS84_E2) + height) * math.sin(la),
    )


def _enu_basis(lat: float, lon: float) -> tuple[tuple[float, float, float], ...]:
    """East / North / Up unit vectors (ECEF) of the tangent frame at (lat, lon)."""
    la, lo = math.radians(lat), math.radians(lon)
    sin_la, cos_la, sin_lo, cos_lo = (
        math.sin(la), math.cos(la), math.sin(lo), math.cos(lo),
    )
    east = (-sin_lo, cos_lo, 0.0)
    north = (-sin_la * cos_lo, -sin_la * sin_lo, cos_la)
    up = (cos_la * cos_lo, cos_la * sin_lo, sin_la)
    return east, north, up


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _meters_per_deg_lon(center_lat: float) -> float:
    """Flat-earth metres/deg lon — used only by the coarse `unproject` inverse."""
    return METERS_PER_DEG_LAT * math.cos(math.radians(center_lat))


def _unrotate(xr: float, yf: float, azimuth_deg: float) -> tuple[float, float]:
    a = math.radians(azimuth_deg) * AZIMUTH_SIGN
    ca, sa = math.cos(a), math.sin(a)
    east = xr * ca - yf * sa
    north = xr * sa + yf * ca
    return east, north


def _proj(manifest: dict[str, Any]) -> dict[str, Any]:
    """Derive (and pre-compute the ellipsoid frame for) a manifest's projection.

    The centre's ECEF position + ENU basis are the same for every point on a map, so
    they're computed once here rather than per actor per frame.
    """
    p = manifest["projection"]
    img = manifest["image"]
    clat, clon = manifest["center"]["lat"], manifest["center"]["lon"]
    target_h = p.get("targetHeightMeters", DEFAULT_TARGET_HEIGHT_M)
    east, north, up = _enu_basis(clat, clon)
    el = math.radians(abs(p["elevationDeg"]))
    return {
        "clat": clat, "clon": clon,
        "az": p["azimuthDeg"],
        "sin_el": math.sin(el) or 1.0,
        "cos_el": math.cos(el),
        "ppm": img["height"] / p["viewHeightMeters"],  # px per screen-metre (isotropic)
        "w": img["width"],
        "h": img["height"],
        "target_h": target_h,
        "c_ecef": _ecef(clat, clon, target_h),
        "E": east, "N": north, "U": up,
    }


def project(manifest: dict[str, Any], lat: float, lon: float) -> tuple[float, float]:
    """(lat, lon) -> (px, py) in the DZI's full-resolution image pixels.

    Exact WGS84-ellipsoid projection: the point's ECEF offset from the map centre is
    resolved onto the centre's East/North/Up axes, azimuth-rotated into screen axes,
    then the forward axis is foreshortened by sin(el) and the Up/sagitta term by
    cos(el) — matching the bake's getObjectFrame + dimetric orthographic camera.
    """
    m = _proj(manifest)
    p = _ecef(lat, lon, m["target_h"])
    c = m["c_ecef"]
    d = (p[0] - c[0], p[1] - c[1], p[2] - c[2])
    east = _dot(m["E"], d)     # exact ellipsoid ground offset (curvature + flattening)
    north = _dot(m["N"], d)
    up = _dot(m["U"], d)       # tangent-plane sagitta (≈ -curve drop at the edges)
    a = math.radians(m["az"]) * AZIMUTH_SIGN
    ca, sa = math.cos(a), math.sin(a)
    xr = east * ca + north * sa                 # screen-right (metres, full scale)
    yf = -east * sa + north * ca                # screen-forward along ground (metres)
    px = m["w"] / 2.0 + xr * m["ppm"]
    py = m["h"] / 2.0 - (yf * m["sin_el"] + up * m["cos_el"]) * m["ppm"]
    return px, py


def unproject(manifest: dict[str, Any], px: float, py: float) -> tuple[float, float]:
    """(px, py) -> (lat, lon). COARSE flat-earth inverse of project().

    NOT the exact inverse of the ellipsoid `project()` — it neglects curvature +
    flattening + sagitta (the very terms `project` adds), so it drifts by ~metres in a
    district and ~tens of metres at the territory edge. That's fine for its only two
    callers — the `bbox` bounds hint and the coarse nearest-district pick — where the
    answer is a rough envelope / an argmin, not a placement. Never use it to place an
    actor; use `project()` for anything ellipsoid-exact.
    """
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

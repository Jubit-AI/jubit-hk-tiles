#!/usr/bin/env python3
"""Week 2 Central pilot — data-half verification.

Proves end-to-end that we can pull real HK building geometry for the Central
bbox from the Lands Department Cesium 3D Tiles API. This is the foundation the
Three.js render layer (next) sits on.

What it does:
  1. Fetch the root building tileset.json (key from HK_LANDSD_API_KEY env).
  2. Recursively walk the tile tree, collecting tiles whose boundingVolume
     intersects the Central bbox.
  3. Resolve each matching tile's `content.uri` to an absolute URL.
  4. Probe the first few content URIs (HEAD/GET) to confirm real payload
     (b3dm / glb / nested json) comes back.
  5. Print a summary the operator can eyeball for the Week 2 gate.

Run:
    HK_LANDSD_API_KEY=... python3 scripts/central_pilot_fetch.py
or with .env.local present:
    python3 scripts/central_pilot_fetch.py

Read-only. Makes GET requests to data.map.gov.hk only. Writes nothing except
an optional --dump of the manifest to scripts/out/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import requests

# Allow `from isometric_nyc.data import hk_lands_dept` when run from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from isometric_nyc.data.hk_lands_dept import (  # noqa: E402
    API_BASE,
    DISTRICT_BBOXES,
    ENDPOINT_BUILDING,
    HKBoundingBox,
)


def load_env_local() -> None:
    """Minimal .env.local loader (no python-dotenv dep)."""
    env_path = Path(__file__).resolve().parent.parent / ".env.local"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def degrees_to_radians(d: float) -> float:
    return d * 3.141592653589793 / 180.0


def region_intersects_bbox(bv: dict[str, Any], bbox: HKBoundingBox) -> Optional[bool]:
    """Best-effort intersection test for a Cesium boundingVolume vs lat/lng bbox.

    Cesium boundingVolumes come as `region` (radians: [w, s, e, n, minH, maxH]),
    `box`, or `sphere`. Only `region` is directly comparable in geographic
    coords; for `box`/`sphere` we return None (can't cheaply decide) and let the
    caller treat None as "descend anyway" so we don't miss tiles.
    """
    region = bv.get("region")
    if region is None:
        return None
    w, s, e, n = region[0], region[1], region[2], region[3]
    bw = degrees_to_radians(bbox.west)
    bs = degrees_to_radians(bbox.south)
    be = degrees_to_radians(bbox.east)
    bn = degrees_to_radians(bbox.north)
    # Standard AABB overlap test.
    return not (e < bw or w > be or n < bs or s > bn)


def walk_tileset(
    tile: dict[str, Any],
    base_url: str,
    bbox: HKBoundingBox,
    api_key: str,
    session: requests.Session,
    matches: list[dict[str, Any]],
    depth: int = 0,
    max_depth: int = 12,
) -> None:
    """Recursively collect content URIs of tiles intersecting bbox.

    Follows `content.uri` that point to nested tileset .json (external tilesets)
    one level, and records leaf content (b3dm/glb/json payloads).
    """
    if depth > max_depth:
        return

    bv = tile.get("boundingVolume", {})
    hit = region_intersects_bbox(bv, bbox)
    # hit is True (intersects), False (disjoint), or None (box/sphere — descend).
    if hit is False:
        return

    content = tile.get("content")
    if content and "uri" in content:
        uri = content["uri"]
        abs_url = urljoin(base_url, uri)
        matches.append(
            {
                "depth": depth,
                "uri": uri,
                "abs_url": abs_url,
                "geometricError": tile.get("geometricError"),
                "bv_kind": next(iter(bv), None),
            }
        )
        # If the content is itself a nested tileset .json, descend into it.
        if uri.endswith(".json") and depth < max_depth:
            try:
                sep = "&" if "?" in abs_url else "?"
                resp = session.get(f"{abs_url}{sep}key={api_key}", timeout=30)
                resp.raise_for_status()
                nested = resp.json()
                nested_root = nested.get("root")
                if nested_root:
                    # base for nested children is the nested json's own URL dir.
                    nested_base = abs_url.rsplit("/", 1)[0] + "/"
                    walk_tileset(
                        nested_root, nested_base, bbox, api_key, session,
                        matches, depth + 1, max_depth,
                    )
            except Exception as exc:  # noqa: BLE001 — pilot script, surface + continue
                matches[-1]["nested_error"] = str(exc)

    for child in tile.get("children", []):
        walk_tileset(child, base_url, bbox, api_key, session, matches, depth + 1, max_depth)


def main() -> int:
    parser = argparse.ArgumentParser(description="HK Central pilot data fetch")
    parser.add_argument("--district", default="central", help="district bbox key")
    parser.add_argument("--probe", type=int, default=3, help="how many content URIs to probe")
    parser.add_argument("--dump", action="store_true", help="write manifest JSON to scripts/out/")
    args = parser.parse_args()

    load_env_local()
    api_key = os.environ.get("HK_LANDSD_API_KEY")
    if not api_key:
        print("ERROR: HK_LANDSD_API_KEY not set (env or .env.local). "
              "See scripts/request-hk-api-key.md", file=sys.stderr)
        return 2

    bbox = DISTRICT_BBOXES.get(args.district)
    if bbox is None:
        print(f"ERROR: unknown district {args.district!r}; "
              f"known: {list(DISTRICT_BBOXES)}", file=sys.stderr)
        return 2

    root_url = f"{API_BASE}{ENDPOINT_BUILDING}"
    base_url = root_url.rsplit("/", 1)[0] + "/"
    session = requests.Session()

    print(f"=== HK Central pilot fetch — district={args.district} ===")
    print(f"bbox (WGS84): S={bbox.south} W={bbox.west} N={bbox.north} E={bbox.east}")
    print(f"root tileset: {root_url}")

    resp = session.get(f"{root_url}?key={api_key}", timeout=30)
    resp.raise_for_status()
    tileset = resp.json()
    root = tileset.get("root")
    if not root:
        print("ERROR: no root in tileset.json", file=sys.stderr)
        return 1

    asset = tileset.get("asset", {})
    print(f"asset version={asset.get('version')} "
          f"tilesetVersion={asset.get('tilesetVersion')} "
          f"root.geometricError={root.get('geometricError')}")

    matches: list[dict[str, Any]] = []
    walk_tileset(root, base_url, bbox, api_key, session, matches)

    print(f"\nmatched content tiles intersecting {args.district}: {len(matches)}")
    by_depth: dict[int, int] = {}
    for m in matches:
        by_depth[m["depth"]] = by_depth.get(m["depth"], 0) + 1
    print(f"  by depth: {dict(sorted(by_depth.items()))}")

    # Probe a handful of content URIs to confirm real payload.
    leaf = [m for m in matches if not m["uri"].endswith(".json")][: args.probe]
    print(f"\nprobing {len(leaf)} leaf content URIs:")
    for m in leaf:
        try:
            sep = "&" if "?" in m["abs_url"] else "?"
            r = session.get(f"{m['abs_url']}{sep}key={api_key}", timeout=30, stream=True)
            ctype = r.headers.get("Content-Type", "?")
            clen = r.headers.get("Content-Length", "?")
            # peek first 4 bytes — b3dm/glTF magic
            head = next(r.iter_content(4), b"")
            magic = head.decode("ascii", "replace")
            r.close()
            print(f"  [{r.status_code}] {ctype} len={clen} magic={magic!r} {m['uri'][:60]}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR probing {m['uri'][:60]}: {exc}")

    if args.dump:
        out_dir = Path(__file__).resolve().parent / "out"
        out_dir.mkdir(exist_ok=True)
        out_file = out_dir / f"central_manifest_{args.district}.json"
        out_file.write_text(json.dumps({"bbox": bbox.__dict__, "matches": matches}, indent=2))
        print(f"\nwrote manifest: {out_file}")

    print("\n=== Week 2 gate (data half): "
          f"{'PASS' if matches else 'FAIL — no tiles matched'} ===")
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())

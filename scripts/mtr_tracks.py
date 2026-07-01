#!/usr/bin/env python3
"""Build real MTR line TRACK geometry for the living-world isometric HK map.

The living-world overlay draws each MTR line as a coloured route and glides real
trains along it. Straight station→station chords look wrong on a curved dimetric map,
so we fetch the ACTUAL track alignment from OpenStreetMap and snap it to our canonical
station list (`mtr_network.json`). Output is one small vendored JSON the browser loads
same-origin (CSP `script-src 'self'`).

Pipeline, per line:
  A. Overpass `rel[route=subway][network~MTR][ref=<CODE>]` → the line's route relations
     (usually one per direction; some lines have branch/variant relations too).
  B. For each relation `rel(id); way(r); out geom;` → its member ways WITH geometry.
     Drop `railway=platform` loops; keep the running-rail ways.
  C. Greedy nearest-endpoint STITCH of those ways → one ordered polyline; orient it to
     our W/N→E/S station order; SNAP each of the line's stations to the nearest polyline
     vertex. Pick the relation whose chain covers ALL our stations, monotonically, with
     the smallest max snap distance.

Output schema (`mtr_tracks.json`):
  { schemaVersion, generated, source,
    lines: { ISL: { color, path:[[lat,lon]…], stationVertexIdx:{CODE:idx},
                    stationLatLon:{CODE:[lat,lon]}, stationName:{CODE:name} }, … },
    _meta: { ISL: { relationId, wayCount, vertexCount, maxSnapM, stationCount, monotonic } } }

`path[stationVertexIdx[A] : stationVertexIdx[B]+1]` is the curved sub-polyline between
adjacent stations A→B — exactly what a train tweens along.

FAIL LOUD: if any requested line can't stitch or snap all its stations monotonically
within `--snap-threshold-m`, exit non-zero and write NOTHING (never a partial asset).
The runtime degrades on its own to straight chords when the asset is missing.

Attribution: track geometry © OpenStreetMap contributors (ODbL). Keep it in the UI.
"""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

SCRIPTS = Path(__file__).resolve().parent
STATIONS_JSON = SCRIPTS / "mtr_network.json"
DEFAULT_OUT = SCRIPTS.parent / "viewer" / "mtr_tracks.json"

BBOX = "22.15,113.8,22.6,114.4"  # whole HK
MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
UA = "jubit-hk-tiles/mtr-tracks (+https://jubit.ai)"
TRACK_RAILWAY = {"subway", "rail", "light_rail", "narrow_gauge"}
COORD_DP = 5  # ~1.1 m — sub-metre precision is wasted on an isometric map

# Official MTR line colours (fallback if a relation omits `colour`).
OFFICIAL_COLOURS = {
    "ISL": "#007dc5", "TWL": "#e2231a", "KTL": "#00a650", "TCL": "#f7943e",
    "AEL": "#00888a", "TML": "#923011", "EAL": "#5eb6e4", "TKL": "#7d499d",
    "SIL": "#bac429", "DRL": "#f550a7",
}


class LineBuildError(RuntimeError):
    """A line could not be built to spec (unstitchable / un-snappable / no relation)."""


# --------------------------------------------------------------------------- fetch
def _http_post(url: str, data: str) -> str:
    req = urllib.request.Request(
        url, data=data.encode("utf-8"),
        headers={"User-Agent": UA, "Accept": "application/json",
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read().decode("utf-8", "replace")


def overpass(query: str, *, mirrors: tuple[str, ...] = MIRRORS, retries: int = 4,
             sleep: float = 6.0, poster: Callable[[str, str], str] = _http_post) -> dict:
    """POST an Overpass query, rotating mirrors with backoff. Raises on total failure.

    Overpass returns HTML (429/406/504) under load, so a non-JSON or empty body is a
    failure, not data — retry it rather than parse garbage.
    """
    last = ""
    for attempt in range(retries):
        for url in mirrors:
            try:
                text = poster(url, "data=" + quote(query))
            except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
                last = f"{url}: {e}"
                continue
            t = text.lstrip()
            if not t or t[0] not in "{[":
                last = f"{url}: non-JSON ({t[:80]!r})"
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                last = f"{url}: bad JSON ({e})"
        if attempt < retries - 1:
            time.sleep(sleep * (attempt + 1))  # linear backoff; polite to the free API
    raise LineBuildError(f"Overpass failed after {retries} tries: {last}")


# ------------------------------------------------------------------------- geometry
def _dist_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Equirectangular metres — accurate + cheap at HK latitude."""
    mlat = (a[0] + b[0]) * 0.5
    dlat = (a[0] - b[0]) * 111320.0
    dlon = (a[1] - b[1]) * 111320.0 * math.cos(math.radians(mlat))
    return math.hypot(dlat, dlon)


def _way_points(way: dict) -> list[tuple[float, float]]:
    return [(p["lat"], p["lon"]) for p in way.get("geometry", [])]


def _is_track(way: dict) -> bool:
    pts = _way_points(way)
    if len(pts) < 2:
        return False
    if way.get("tags", {}).get("railway") not in TRACK_RAILWAY:
        return False
    return pts[0] != pts[-1]  # drop closed loops (platforms drawn as areas)


def stitch(segments: list[list[tuple[float, float]]]) -> tuple[list[tuple[float, float]], float]:
    """Greedily join track ways end-to-end into one ordered polyline.

    Repeatedly attach the unused segment whose endpoint is nearest to either end of the
    growing chain (reversing it as needed). Returns (chain, max_join_gap_m); a large gap
    means the ways don't actually form one line (caller can reject on it).
    """
    segs = [list(s) for s in segments]
    chain = segs.pop(0)
    max_gap = 0.0
    while segs:
        best = None  # (dist, seg_index, mode)
        for i, s in enumerate(segs):
            for mode, cend, send in (
                ("append", chain[-1], s[0]), ("append_rev", chain[-1], s[-1]),
                ("prepend", chain[0], s[-1]), ("prepend_rev", chain[0], s[0]),
            ):
                d = _dist_m(cend, send)
                if best is None or d < best[0]:
                    best = (d, i, mode)
        d, i, mode = best
        s = segs.pop(i)
        max_gap = max(max_gap, d)
        if mode == "append":
            chain = chain + s
        elif mode == "append_rev":
            chain = chain + s[::-1]
        elif mode == "prepend":
            chain = s + chain
        else:
            chain = s[::-1] + chain
    return chain, max_gap


def _nearest_vertex(chain: list[tuple[float, float]], la: float, lo: float) -> tuple[float, int]:
    best = (float("inf"), -1)
    for k, v in enumerate(chain):
        d = _dist_m((la, lo), v)
        if d < best[0]:
            best = (d, k)
    return best


def snap_stations(chain: list[tuple[float, float]], stations: list[tuple[str, float, float]]):
    """Orient the chain to station order, then snap each station to its nearest vertex.

    Returns (chain, idx_by_code, snap_by_code, monotonic). `chain` may be reversed so
    vertex order runs first-station→last-station.
    """
    i0 = _nearest_vertex(chain, stations[0][1], stations[0][2])[1]
    iN = _nearest_vertex(chain, stations[-1][1], stations[-1][2])[1]
    if i0 > iN:
        chain = chain[::-1]
    idx: dict[str, int] = {}
    snap: dict[str, float] = {}
    for code, la, lo in stations:
        d, k = _nearest_vertex(chain, la, lo)
        idx[code] = k
        snap[code] = d
    order = [idx[c] for c, _, _ in stations]
    monotonic = all(order[i] < order[i + 1] for i in range(len(order) - 1))
    return chain, idx, snap, monotonic


# ------------------------------------------------------------------------- per line
def build_line(code: str, stations: list[tuple[str, float, float]], *,
               fetch: Callable[[str], dict], threshold_m: float) -> dict:
    """Fetch + stitch + snap one line, choosing the best relation. Raises on failure.

    Exactly TWO Overpass calls per line regardless of relation count: (1) the route
    relations WITH their way members, (2) all those ways' geometry in one batch. Every
    relation is then scored LOCALLY (stitch + snap), so a line like EAL with ~20 branch/
    variant relations costs 2 fetches, not 20.
    """
    rel_json = fetch(
        f'[out:json][timeout:90];rel["route"="subway"]["network"~"MTR"]'
        f'["ref"="{code}"]({BBOX});out body;'
    )
    relations = [e for e in rel_json.get("elements", []) if e.get("type") == "relation"]
    if not relations:
        raise LineBuildError(f"{code}: no OSM route relation found")
    way_ids = sorted({m["ref"] for r in relations
                      for m in r.get("members", []) if m.get("type") == "way"})
    if not way_ids:
        raise LineBuildError(f"{code}: route relations carry no way members")
    ways_json = fetch(
        f'[out:json][timeout:120];way(id:{",".join(map(str, way_ids))});out geom;'
    )
    geom = {w["id"]: w for w in ways_json.get("elements", []) if w.get("type") == "way"}

    # Score every relation; keep the best by (covers-all-monotonically, coverage, -maxsnap).
    best = None  # (score, payload)
    for rel in relations:
        member_ids = [m["ref"] for m in rel.get("members", []) if m.get("type") == "way"]
        tracks = [_way_points(geom[wid]) for wid in member_ids
                  if wid in geom and _is_track(geom[wid])]
        if not tracks:
            continue
        chain, _gap = stitch(tracks)
        chain, idx, snap, monotonic = snap_stations(chain, stations)
        covered = sum(1 for c in idx if snap[c] <= threshold_m)
        max_snap = max(snap.values()) if snap else float("inf")
        colour = rel.get("tags", {}).get("colour") or OFFICIAL_COLOURS.get(code, "#888888")
        score = (covered == len(stations) and monotonic, covered, -max_snap)
        payload = {
            "relationId": rel["id"], "color": colour, "chain": chain, "idx": idx,
            "snap": snap, "monotonic": monotonic, "maxSnap": max_snap,
            "wayCount": len(tracks),
        }
        if best is None or score > best[0]:
            best = (score, payload)

    if best is None:
        raise LineBuildError(f"{code}: no relation yielded track geometry")
    p = best[1]
    if not (p["monotonic"] and p["maxSnap"] <= threshold_m):
        worst = max(p["snap"], key=p["snap"].get)
        raise LineBuildError(
            f"{code}: no relation covered all stations cleanly — best {p['relationId']} "
            f"monotonic={p['monotonic']} maxSnap={p['maxSnap']:.0f}m at {worst} "
            f"(threshold {threshold_m:g}m)"
        )
    return p


def assemble(codes: list[str], net: dict, *, fetch: Callable[[str], dict],
             threshold_m: float, generated: str) -> dict:
    """Build every requested line into the final mtr_tracks.json document."""
    lines: dict[str, Any] = {}
    meta: dict[str, Any] = {}
    errors: list[str] = []
    for code in codes:
        print(f"  … {code}", flush=True)
        stas = [(s["code"], s["lat"], s["lon"]) for s in net[code]["stations"]]
        names = {s["code"]: s["name"] for s in net[code]["stations"]}
        try:
            p = build_line(code, stas, fetch=fetch, threshold_m=threshold_m)
        except LineBuildError as e:
            errors.append(str(e))
            print(f"  ✗ {e}")
            continue
        lines[code] = {
            "color": p["color"],
            "path": [[round(la, COORD_DP), round(lo, COORD_DP)] for la, lo in p["chain"]],
            "stationVertexIdx": p["idx"],  # snapped path index — for slicing the train sub-path
            "stationLatLon": {s[0]: [round(s[1], COORD_DP), round(s[2], COORD_DP)] for s in stas},
            "stationName": names,          # TRUE station coord — for drawing dots/labels
        }
        meta[code] = {
            "relationId": p["relationId"], "wayCount": p["wayCount"],
            "vertexCount": len(p["chain"]), "maxSnapM": round(p["maxSnap"], 1),
            "stationCount": len(stas), "monotonic": p["monotonic"],
        }
    if errors:  # fail loud: report EVERY bad line in one run, write nothing
        raise LineBuildError(f"{len(errors)} line(s) failed:\n  " + "\n  ".join(errors))
    return {
        "schemaVersion": 1, "generated": generated,
        "source": "OpenStreetMap contributors (ODbL) via Overpass",
        "lines": lines, "_meta": meta,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build MTR track geometry from OSM")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--lines", type=str, default="", help="comma codes; default = all")
    # Gate against picking a WRONG relation (km off). Real platform-vs-rail offsets reach
    # ~230 m at newer deep stations (e.g. TML Sung Wong Toi), and dots are drawn at the
    # TRUE coord anyway (the snapped index only slices the train path), so 300 m is safe.
    ap.add_argument("--snap-threshold-m", type=float, default=300.0)
    ap.add_argument("--sleep", type=float, default=6.0, help="inter-request delay (s)")
    ap.add_argument("--mirror", type=str, default=",".join(MIRRORS))
    args = ap.parse_args()

    net = json.loads(STATIONS_JSON.read_text())
    codes = [c.strip().upper() for c in args.lines.split(",") if c.strip()] or list(net.keys())
    mirrors = tuple(m.strip() for m in args.mirror.split(",") if m.strip())

    def fetch(q: str) -> dict:
        time.sleep(args.sleep)  # polite: avoid the free API's rate limiter
        return overpass(q, mirrors=mirrors, sleep=args.sleep)

    generated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    doc = assemble(codes, net, fetch=fetch, threshold_m=args.snap_threshold_m,
                   generated=generated)  # raises LineBuildError → no file written

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    print(f"mtr_tracks → {args.out}  ({len(doc['lines'])} lines)")
    print(f"{'line':5} {'rel':>10} {'ways':>5} {'verts':>6} {'maxSnap':>8} mono")
    for code, m in doc["_meta"].items():
        print(f"{code:5} {m['relationId']:>10} {m['wayCount']:>5} {m['vertexCount']:>6} "
              f"{m['maxSnapM']:>7.1f}m {'ok' if m['monotonic'] else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

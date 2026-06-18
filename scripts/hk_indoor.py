#!/usr/bin/env python3
"""Producer: HK indoor floor plans (Open3Dhk indoor WFS) -> hk-indoor-<venue>.json
for the tiny-planet interior mode. Data (c) HK Lands Dept via DATA.GOV.HK (transformed)."""
import json, math, sys, urllib.parse, urllib.request

WFS = "https://mapapi.hkmapservice.gov.hk/ogc/wfs/indoor"
APM = "429bac14-d8c8-4c48-a7aa-ae54b65882d7"
MTR_VENUE = "b9b2f6ff-582d-40b0-b82d-027e950e6791"  # Admiralty Station (4-line interchange)


def project(lon, lat, origin):
    mlon = 111320.0 * math.cos(math.radians(origin[1]))
    return [(lon - origin[0]) * mlon, (lat - origin[1]) * 110540.0]


def _rings(geom):
    """Outer ring(s) of a Polygon/MultiPolygon, or the line(s) of a *LineString, each as a
    list of [x, y(, z)]. ALL MultiPolygon parts are kept (MTR units/levels are often
    multi-part). Unknown/Point geometry returns [] so callers skip it instead of unpacking
    a scalar coordinate."""
    c = geom.get("coordinates") or []
    t = geom.get("type")
    if t == "Polygon":
        return [c[0]] if c else []
    if t == "MultiPolygon":
        return [poly[0] for poly in c if poly]
    if t == "LineString":
        return [c] if c else []
    if t == "MultiLineString":
        return [seg for seg in c if seg]
    return []


def _clean(ring):
    """Keep only coordinates that are at least an [x, y] pair (guards Point/3D/malformed)."""
    return [p for p in ring if isinstance(p, (list, tuple)) and len(p) >= 2]


def _ring_area(ring):
    n = len(ring)
    a = 0.0
    for i in range(n):
        a += ring[i][0] * ring[(i + 1) % n][1] - ring[(i + 1) % n][0] * ring[i][1]
    return abs(a) * 0.5


def poly_centroid(ring):
    """Area-weighted (shoelace) centroid of one ring; vertex mean for a degenerate ring."""
    n = len(ring)
    a = cx = cy = 0.0
    for i in range(n):
        x0, y0 = ring[i][0], ring[i][1]
        x1, y1 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(a) < 1e-12:
        return [round(sum(p[0] for p in ring) / n, 3), round(sum(p[1] for p in ring) / n, 3)]
    a *= 0.5
    return [round(cx / (6 * a), 3), round(cy / (6 * a), 3)]


def _area_weighted_centroid(rings):
    """Centroid across all polygon parts, weighted by each part's area."""
    sx = sy = tot = 0.0
    for r in rings:
        c = poly_centroid(r)
        a = _ring_area(r)
        sx += c[0] * a
        sy += c[1] * a
        tot += a
    if tot < 1e-12:
        r = rings[0]
        return (sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r))
    return (sx / tot, sy / tot)


def _point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _interior_point(ring, cx, cy):
    """A guaranteed-interior representative point: the area centroid if it lies inside, else
    the midpoint of the widest interior span on the scanline y = cy. Handles concave /
    L-shaped / elongated units (MTR platforms, corridor walkways) whose area centroid would
    otherwise fall outside the footprint and misplace the delivery node."""
    if _point_in_ring(cx, cy, ring):
        return [round(cx, 3), round(cy, 3)]
    xs = []
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i][0], ring[i][1]
        x1, y1 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if (y0 > cy) != (y1 > cy):
            xs.append(x0 + (cy - y0) * (x1 - x0) / (y1 - y0))
    xs.sort()
    best, bw = None, -1.0
    for k in range(0, len(xs) - 1, 2):
        w = xs[k + 1] - xs[k]
        if w > bw:
            bw, best = w, (xs[k] + xs[k + 1]) / 2
    return [round(best if best is not None else cx, 3), round(cy, 3)]


def _lvl(props):
    """level_ordinal coerced to int; None if absent or non-numeric (WFS may send strings)."""
    try:
        return int(props["level_ordinal"])
    except (KeyError, TypeError, ValueError):
        return None


def curate(levels_fc, units_fc, doors_fc, keep_levels, shop_cats, origin):
    keep = set(int(x) for x in keep_levels)
    levels, seen = [], set()
    for f in levels_fc["features"]:
        o = _lvl(f["properties"])
        if o is None or o not in keep or o in seen:  # dedup: many ground-level exits share ordinal 0
            continue
        seen.add(o)
        p = f["properties"]
        levels.append({"ordinal": o, "z": p.get("level_z_value", 0), "name": p.get("level_name_en", "")})
    levels.sort(key=lambda l: l["ordinal"])
    units = []
    for f in units_fc["features"]:
        p = f["properties"]
        o = _lvl(p)
        if o is None or o not in keep or p.get("unit_category") not in shop_cats:
            continue
        rings = [r for r in (_clean(rg) for rg in _rings(f["geometry"])) if len(r) >= 3]
        if not rings:
            continue
        proj = [[project(pt[0], pt[1], origin) for pt in r] for r in rings]
        big = max(proj, key=_ring_area)  # largest part drives the box footprint + interior point
        cx, cy = _area_weighted_centroid(proj)
        units.append({"level": o, "poly": [[round(pt[0], 2), round(pt[1], 2)] for pt in big],
                      "centroid": _interior_point(big, cx, cy), "category": p.get("unit_category"),
                      "name": p.get("unit_name_en") or p.get("unit_unitnumbername") or "Shop"})
    doors = []
    for f in doors_fc["features"]:
        o = _lvl(f["properties"])
        if o is None or o not in keep:
            continue
        for ring in _rings(f["geometry"]):
            cs = [project(pt[0], pt[1], origin) for pt in _clean(ring)]
            if len(cs) < 2:
                continue
            doors.append({"level": o, "a": [round(cs[0][0], 2), round(cs[0][1], 2)],
                          "b": [round(cs[-1][0], 2), round(cs[-1][1], 2)]})
            break
    return {"levels": levels, "units": units, "doors": doors}


def fetch(layer, venue_id, key):
    q = {"key": key, "service": "WFS", "version": "2.0.0", "request": "GetFeature",
         "outputFormat": "application/json", "cql_filter": f"venue_id='{venue_id}'"}
    url = f"{WFS}/{layer}?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "jubuddy/1.0"}), timeout=90) as r:
        return json.load(r)


def venue_origin(levels_fc):
    """Bounding-box centre of every level polygon's full coordinate set (all MultiPolygon
    parts, all vertices equally) — avoids the vertex-density skew of a plain vertex average."""
    xs, ys = [], []
    for f in levels_fc["features"]:
        for ring in _rings(f["geometry"]):
            for p in _clean(ring):
                xs.append(p[0])
                ys.append(p[1])
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)


if __name__ == "__main__":
    key = next((a for a in sys.argv[1:] if not a.startswith("--")), "")
    mtr = "--mtr" in sys.argv
    pre = "mtr_" if mtr else ""                       # MTR layers are mtr_-prefixed on the same WFS
    venue = MTR_VENUE if mtr else APM
    default_levels = ["0", "-2", "-3", "-4"] if mtr else ["0", "1", "2"]
    keep = [int(x) for x in (sys.argv[sys.argv.index("--levels") + 1].split(",")
                             if "--levels" in sys.argv else default_levels)]
    lv = fetch(pre + "level_polygon", venue, key)
    un = fetch(pre + "unit_polygon", venue, key)
    op = fetch(pre + "opening_line", venue, key)
    origin = venue_origin(lv)
    cats = ({"platform", "walkway", "lobby", "room", "unspecified", "movingwalkway",
             "escalator", "stairs", "steps", "elevator", "restroom.unisex", "restroom.female"} if mtr
            else {"room", "foodservice", "unspecified", "lobby", "auditorium", "theater",
                  "mothersroom", "office", "restroom.female", "restroom.male", "restroom.wheelchair"})
    doc = curate(lv, un, op, keep, cats, origin)
    if not doc["units"]:  # fail loud rather than write a silently-empty venue (schema drift / wrong venue)
        sys.exit(f"FATAL: no units matched keep_levels={keep} / categories for venue {venue} — schema drift?")
    doc["venue"] = {"id": venue, "name": "Admiralty Station" if mtr else "APM Millennium City 5"}
    doc["origin"] = {"lon": origin[0], "lat": origin[1]}
    # `doors` are real WFS openings, retained for a future door-accurate nav graph; the current
    # consumer (interior.ts) builds connectivity from K-nearest unit centroids, not doors.
    out = "/Users/jubit_nb0/jubuddy-hk/src/planet/" + ("hk-indoor-mtr.json" if mtr else "hk-indoor-apm.json")
    json.dump(doc, open(out, "w"))
    print(f"{'MTR ' if mtr else ''}levels={len(doc['levels'])} units={len(doc['units'])} doors={len(doc['doors'])} -> {out}")

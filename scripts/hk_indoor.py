#!/usr/bin/env python3
"""Producer: HK indoor floor plans (Open3Dhk indoor WFS) -> hk-indoor-<venue>.json
for the tiny-planet interior mode. Data (c) HK Lands Dept via DATA.GOV.HK (transformed)."""
import json, math, sys, urllib.parse, urllib.request

WFS = "https://mapapi.hkmapservice.gov.hk/ogc/wfs/indoor"
APM = "429bac14-d8c8-4c48-a7aa-ae54b65882d7"


def project(lon, lat, origin):
    mlon = 111320.0 * math.cos(math.radians(origin[1]))
    return [(lon - origin[0]) * mlon, (lat - origin[1]) * 110540.0]


def poly_centroid(ring):
    n = len(ring)
    return [round(sum(p[0] for p in ring) / n, 3), round(sum(p[1] for p in ring) / n, 3)]


def _outer_ring(geom):
    c = geom.get("coordinates") or []
    t = geom.get("type")
    if t == "Polygon":
        return c[0] if c else []
    if t == "MultiPolygon":              # MTR levels/units are often MultiPolygon — take the first ring
        return c[0][0] if c and c[0] else []
    if t == "MultiLineString":
        return c[0] if c else []
    return c                             # LineString / other


def curate(levels_fc, units_fc, doors_fc, keep_levels, shop_cats, origin):
    levels = sorted(
        ({"ordinal": p["level_ordinal"], "z": p.get("level_z_value", 0), "name": p.get("level_name_en", "")}
         for f in levels_fc["features"] for p in [f["properties"]] if p["level_ordinal"] in keep_levels),
        key=lambda l: l["ordinal"])
    units = []
    for f in units_fc["features"]:
        p = f["properties"]
        if p["level_ordinal"] not in keep_levels or p.get("unit_category") not in shop_cats:
            continue
        ring = [project(x, y, origin) for x, y in _outer_ring(f["geometry"])]
        if len(ring) < 3:
            continue
        units.append({"level": p["level_ordinal"], "poly": [[round(x, 2), round(y, 2)] for x, y in ring],
                      "centroid": poly_centroid(ring), "category": p.get("unit_category"),
                      "name": p.get("unit_name_en") or p.get("unit_unitnumbername") or "Shop"})
    doors = []
    for f in doors_fc["features"]:
        p = f["properties"]
        if p["level_ordinal"] not in keep_levels:
            continue
        cs = [project(x, y, origin) for x, y in _outer_ring(f["geometry"])]
        if len(cs) < 2:
            continue
        doors.append({"level": p["level_ordinal"], "a": [round(cs[0][0], 2), round(cs[0][1], 2)],
                      "b": [round(cs[-1][0], 2), round(cs[-1][1], 2)]})
    return {"levels": levels, "units": units, "doors": doors}


def fetch(layer, venue_id, key):
    q = {"key": key, "service": "WFS", "version": "2.0.0", "request": "GetFeature",
         "outputFormat": "application/json", "cql_filter": f"venue_id='{venue_id}'"}
    url = f"{WFS}/{layer}?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "jubuddy/1.0"}), timeout=90) as r:
        return json.load(r)


def venue_origin(levels_fc):
    pts = []
    for f in levels_fc["features"]:
        for coord in _outer_ring(f["geometry"]):
            pts.append((coord[0], coord[1]))
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _to2d(fc):
    """Strip Z from all coordinates so curate() unpacking (x, y) works on 3D WFS data."""
    import copy
    fc2 = copy.deepcopy(fc)
    for f in fc2["features"]:
        g = f["geometry"]
        def drop_z(coords):
            if not coords:
                return coords
            if isinstance(coords[0], (int, float)):
                return coords[:2]
            return [drop_z(c) for c in coords]
        g["coordinates"] = drop_z(g["coordinates"])
    return fc2


MTR_VENUE = "b9b2f6ff-582d-40b0-b82d-027e950e6791"  # Admiralty Station (4-line interchange)

if __name__ == "__main__":
    key = next((a for a in sys.argv[1:] if not a.startswith("--")), "")
    mtr = "--mtr" in sys.argv
    pre = "mtr_" if mtr else ""                       # MTR layers are mtr_-prefixed on the same WFS
    venue = MTR_VENUE if mtr else APM
    default_levels = ["0", "-2", "-3", "-4"] if mtr else ["0", "1", "2"]
    keep = [int(x) for x in (sys.argv[sys.argv.index("--levels") + 1].split(",")
                             if "--levels" in sys.argv else default_levels)]
    lv = _to2d(fetch(pre + "level_polygon", venue, key))
    un = _to2d(fetch(pre + "unit_polygon", venue, key))
    op = _to2d(fetch(pre + "opening_line", venue, key))
    origin = venue_origin(lv)
    cats = ({"platform", "walkway", "lobby", "room", "unspecified", "movingwalkway",
             "escalator", "stairs", "steps", "elevator", "restroom.unisex", "restroom.female"} if mtr
            else {"room", "foodservice", "unspecified", "lobby", "auditorium", "theater",
                  "mothersroom", "office", "restroom.female", "restroom.male", "restroom.wheelchair"})
    doc = curate(lv, un, op, keep, cats, origin)
    doc["venue"] = {"id": venue, "name": "Admiralty Station" if mtr else "APM Millennium City 5"}
    doc["origin"] = {"lon": origin[0], "lat": origin[1]}
    out = "/Users/jubit_nb0/jubuddy-hk/src/planet/" + ("hk-indoor-mtr.json" if mtr else "hk-indoor-apm.json")
    json.dump(doc, open(out, "w"))
    print(f"{'MTR ' if mtr else ''}levels={len(doc['levels'])} units={len(doc['units'])} doors={len(doc['doors'])} -> {out}")

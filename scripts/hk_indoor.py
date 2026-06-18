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
    c = geom["coordinates"]
    return c[0] if geom["type"] == "Polygon" else c


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
        units.append({"level": p["level_ordinal"], "poly": [[round(x, 2), round(y, 2)] for x, y in ring],
                      "centroid": poly_centroid(ring), "category": p.get("unit_category"),
                      "name": p.get("unit_name_en") or p.get("unit_unitnumbername") or "Shop"})
    doors = []
    for f in doors_fc["features"]:
        p = f["properties"]
        if p["level_ordinal"] not in keep_levels:
            continue
        cs = [project(x, y, origin) for x, y in _outer_ring(f["geometry"])]
        doors.append({"level": p["level_ordinal"], "a": [round(cs[0][0], 2), round(cs[0][1], 2)],
                      "b": [round(cs[-1][0], 2), round(cs[-1][1], 2)]})
    return {"levels": levels, "units": units, "doors": doors}

#!/usr/bin/env python3
"""Producer: real HK building footprints + heights from Open3Dhk (Lands Dept) 3D
Tiles -> ~/jubuddy-hk/src/planet/hk-buildings.json for the tiny-planet.

Source: https://data.map.gov.hk/api/3d-data/3dsd/WGS84/building/tileset.json (Cesium
3D Tiles, ECEF + per-tile transforms). We DON'T parse meshes; we traverse the tileset
tree, accumulate transforms, and read each geometry tile's oriented bounding box ->
centroid (lon/lat) + footprint + height. Data (c) HK Lands Dept via DATA.GOV.HK —
transformative use only, attribution kept.

Usage: hk_buildings.py <API_KEY> [--probe] [--lon0 --lat0 --lon1 --lat1]
"""
import json, math, sys, urllib.request, urllib.error

KEY = next((a for a in sys.argv[1:] if not a.startswith("--")), "")
PROBE = "--probe" in sys.argv
BUILDING_TS = "https://data.map.gov.hk/api/3d-data/3dsd/WGS84/building/tileset.json"
LON0, LAT0, LON1, LAT1 = 114.14, 22.27, 114.21, 22.33  # Central + Victoria Harbour + TST core
MAX_FETCH = 1200
OUT = "/Users/jubit_nb0/jubuddy-hk/src/planet/hk-buildings.json"

_fetches = [0]
IDENT = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
GEOM = (".glb", ".b3dm", ".cmpt", ".gltf")


def fetch_json(url):
    if "key=" not in url:
        url += ("&" if "?" in url else "?") + "key=" + KEY
    _fetches[0] += 1
    req = urllib.request.Request(url, headers={"User-Agent": "jubuddy-hk/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def mat_mul(a, b):  # 4x4 column-major a*b
    r = [0.0] * 16
    for col in range(4):
        for row in range(4):
            r[col * 4 + row] = sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
    return r


def xform_point(m, p):
    x, y, z = p
    return (m[0]*x+m[4]*y+m[8]*z+m[12], m[1]*x+m[5]*y+m[9]*z+m[13], m[2]*x+m[6]*y+m[10]*z+m[14])


def xform_vec(m, v):
    x, y, z = v
    return (m[0]*x+m[4]*y+m[8]*z, m[1]*x+m[5]*y+m[9]*z, m[2]*x+m[6]*y+m[10]*z)


def transform_box(box, m):
    c = xform_point(m, box[0:3])
    return list(c) + list(xform_vec(m, box[3:6])) + list(xform_vec(m, box[6:9])) + list(xform_vec(m, box[9:12]))


def ecef_to_lla(x, y, z):
    a = 6378137.0
    e2 = 6.69437999014e-3
    b = math.sqrt(a * a * (1 - e2))
    ep2 = (a * a - b * b) / (b * b)
    p = math.hypot(x, y)
    th = math.atan2(a * z, b * p)
    lon = math.atan2(y, x)
    lat = math.atan2(z + ep2 * b * math.sin(th) ** 3, p - e2 * a * math.cos(th) ** 3)
    return math.degrees(lat), math.degrees(lon)


def box_to_building(tbox):  # tbox already in ECEF
    cx, cy, cz = tbox[0:3]
    axes = [tbox[3:6], tbox[6:9], tbox[9:12]]
    lat, lon = ecef_to_lla(cx, cy, cz)
    un = math.sqrt(cx * cx + cy * cy + cz * cz) or 1.0
    up = (cx / un, cy / un, cz / un)
    mags = [math.sqrt(sum(c * c for c in ax)) for ax in axes]
    align = [abs(sum(axes[k][i] * up[i] for i in range(3))) / (mags[k] or 1) for k in range(3)]
    hi = align.index(max(align))
    foot = [2 * mags[k] for k in range(3) if k != hi]
    return lat, lon, foot[0], foot[1], 2 * mags[hi]


def box_overlaps_bbox(tbox):
    lat, lon = ecef_to_lla(*tbox[0:3])
    half = max(math.sqrt(sum(c * c for c in tbox[3:6])), math.sqrt(sum(c * c for c in tbox[6:9])),
               math.sqrt(sum(c * c for c in tbox[9:12])))
    dlat = half / 111000.0
    dlon = half / (111000.0 * max(0.1, math.cos(math.radians(lat))))
    return not (lon + dlon < LON0 or lon - dlon > LON1 or lat + dlat < LAT0 or lat - dlat > LAT1)


def resolve(uri, parent_url):
    if uri.startswith("http"):
        return uri
    return parent_url.split("?")[0].rsplit("/", 1)[0] + "/" + uri


buildings = []


def walk(tileset_url, incoming):
    if _fetches[0] >= MAX_FETCH:
        return
    try:
        ts = fetch_json(tileset_url)
    except (urllib.error.URLError, ValueError, TimeoutError, OSError):
        return
    stack = [(ts["root"], incoming)]
    while stack:
        t, parent_x = stack.pop()
        x = mat_mul(parent_x, t["transform"]) if t.get("transform") else parent_x
        box = t.get("boundingVolume", {}).get("box")
        tbox = transform_box(box, x) if box else None
        if tbox and not box_overlaps_bbox(tbox):
            continue
        c = t.get("content") or (t.get("contents") or [{}])[0]
        uri = (c or {}).get("uri") or (c or {}).get("url") or ""
        kids = t.get("children", [])
        if uri.endswith(".json"):
            walk(resolve(uri, tileset_url), x)
        elif uri and uri.lower().endswith(GEOM) and tbox and not kids:  # leaf geometry only
            lat, lon, w, d, h = box_to_building(tbox)
            if LON0 <= lon <= LON1 and LAT0 <= lat <= LAT1 and 3 < h < 600 and max(w, d) < 180:
                buildings.append({"lon": round(lon, 6), "lat": round(lat, 6),
                                  "w": round(w, 1), "d": round(d, 1), "h": round(h, 1)})
        for ch in kids:
            stack.append((ch, x))


walk(BUILDING_TS, IDENT)

MAX_OUT = 12000  # InstancedMesh-friendly; keep the tallest (the skyline reads first)
if len(buildings) > MAX_OUT:
    buildings.sort(key=lambda b: -b["h"])
    buildings = buildings[:MAX_OUT]

if buildings:
    hs = sorted(b["h"] for b in buildings)
    ws = sorted(max(b["w"], b["d"]) for b in buildings)
    print(f"fetches={_fetches[0]}  buildings in bbox={len(buildings)}")
    print(f"height m    min/med/max = {hs[0]:.0f} / {hs[len(hs)//2]:.0f} / {hs[-1]:.0f}")
    print(f"footprint m min/med/max = {ws[0]:.0f} / {ws[len(ws)//2]:.0f} / {ws[-1]:.0f}")
    print(f"sample: {buildings[len(buildings)//2]}")
else:
    print(f"fetches={_fetches[0]}  NO buildings collected")

if not PROBE and buildings:
    doc = {"source": "Open3Dhk / HK Lands Dept via DATA.GOV.HK (3D Spatial Data, transformed)",
           "bbox": [LON0, LAT0, LON1, LAT1], "origin": {"lon": (LON0 + LON1) / 2, "lat": (LAT0 + LAT1) / 2},
           "buildings": buildings}
    with open(OUT, "w") as f:
        json.dump(doc, f)
    print(f"wrote {len(buildings)} buildings -> {OUT}")

#!/usr/bin/env python3
"""Producer: HK 3D Pedestrian Network (Lands Dept) -> hk-strata.json for the tiny-planet's
vertical-strata nav-graph. Real walkways / footbridges / escalators / lifts, each vertex
carrying a z elevation (mPD). Data (c) HK Lands Dept via DATA.GOV.HK (transformed, cropped).

ENDPOINT (discovered, KEYLESS — verified 2026-06-18):
  ArcGIS MapServer, single layer 0 "PedestrianRoute" (esriGeometryPolyline, hasZ, 3D):
    https://portal.csdi.gov.hk/server/rest/services/common/landsd_rcd_1637222018065_52265/MapServer/0/query
  Query with outSR=4326&returnZ=true&f=geojson returns WGS84 lon/lat + z(metres) LineStrings
  with rich attributes (FeatureType, Location, WheelchairAccess, StreetNameEN, ...).
  Native spatialReference is WKID 2326 (HK1980 Grid); we request outSR=4326 so the server
  reprojects to lon/lat for us. `to_lonlat(..., src="hk1980")` is the fallback TM inverse for
  any 2326-native query (verified: grid origin 836694.05E/819069.80N -> 114.178555E/22.312133N).
  Resolved from DATA.GOV.HK dataset `hk-landsd-openmap-3d-pedestrian-network` ->
  CSDI datasetId `landsd_rcd_1637222018065_52265` (the data.gov.hk resource URLs point at the
  CSDI geoportal landing page; the queryable MapServer was found in the CSDI ISO19115 record).
  The Esri-China-Hub item 48e295256fd84032a87b27000cea35cd is a static File Geodatabase (no
  live FeatureServer behind it — its geojson streaming download 500s), so we use CSDI's MapServer.

STRATUM z-BAND HEURISTIC (documented, derived from a ~15k-feature real CORE sample, see report):
  Absolute z is elevation above the HK sea datum (mPD), so it conflates terrain slope (HK's
  Mid-Levels / Peak rise to 400 m) with structural height. We therefore classify by a HYBRID
  of FeatureType (semantic) + an absolute z-band, mirroring how hk_indoor uses unit_category +
  level_ordinal together:
    - Footbridge / elevated FeatureTypes  -> always SKYBRIDGE (an elevated deck by definition;
      HK footbridges sample z ~8-18 m mPD over a street that sits at z ~3-5 m).
    - ground footway  z <= STREET_Z (12 m) -> STREET
    - ground footway  STREET_Z < z <= PODIUM_Z (30 m) -> PODIUM  (raised deck / mid-rise plaza)
    - ground footway  z > PODIUM_Z (30 m)            -> SKYBRIDGE (high elevated walkway net)
  STREET_Z=12 sits above the street p50 (~10 m) so normal pavement reads as street; PODIUM_Z=30
  is the elevated-deck floor. These bands mirror the Phase-2 derive thresholds (podium vs tall
  vs skybridge) in spirit: a documented, single-source-of-truth cutpoint set.
"""
import json, math, sys, urllib.parse, urllib.request

MAPSERVER = ("https://portal.csdi.gov.hk/server/rest/services/common/"
             "landsd_rcd_1637222018065_52265/MapServer/0/query")

# Same CORE crop as hk-buildings / realSurface, so the walkways match the visible marble.
CORE = (114.15, 22.27, 114.195, 22.32)

# FeatureType coded values (from the layer's domain).
FT_FOOTWAY = 1
FT_FOOTBRIDGE = 2
FT_SUBWAY = 4
FT_ESCALATOR = 8
FT_TRAVELATOR = 9
FT_LIFT = 10
FT_STAIRCASE = 12

# FeatureTypes that are inherently ELEVATED decks (skybridge stratum regardless of terrain z).
ELEVATED_FT = {FT_FOOTBRIDGE}
# FeatureType -> the courier's ride/transit kind for that edge.
TRANSIT_BY_FT = {
    FT_FOOTBRIDGE: "skybridge", FT_ESCALATOR: "escalator", FT_TRAVELATOR: "escalator",
    FT_LIFT: "lift", FT_STAIRCASE: "stair", FT_SUBWAY: "stair",
}

# z-band cutpoints (metres above the HK sea datum, mPD). See the module docstring.
STREET_Z = 12.0
PODIUM_Z = 30.0

# HK1980 Grid (EPSG:2326) Transverse Mercator inverse params (International 1924 ellipsoid).
_A = 6378388.0
_F = 1 / 297.0
_E2 = 2 * _F - _F * _F
_LAT0 = math.radians(22.312133)
_LON0 = math.radians(114.178555)
_FE, _FN, _K0 = 836694.05, 819069.80, 1.0


def _meridian_arc(lat):
    e2, e4, e6 = _E2, _E2 * _E2, _E2 ** 3
    return _A * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * lat
                 - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * lat)
                 + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * lat)
                 - (35 * e6 / 3072) * math.sin(6 * lat))


_M0 = _meridian_arc(_LAT0)


def to_lonlat(x, y, src="wgs84"):
    """Project a vertex to WGS84 lon/lat. `src='wgs84'` is an identity passthrough (the
    MapServer already reprojects when we pass outSR=4326). `src='hk1980'` runs the EPSG:2326
    Transverse Mercator inverse for any 2326-native easting/northing."""
    if src == "wgs84":
        return (x, y)
    e2 = _E2
    m = _M0 + (y - _FN) / _K0
    mu = m / (_A * (1 - e2 / 4 - 3 * e2 * e2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    lat1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 * e1 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
            + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    ep2 = e2 / (1 - e2)
    c1 = ep2 * math.cos(lat1) ** 2
    t1 = math.tan(lat1) ** 2
    n1 = _A / math.sqrt(1 - e2 * math.sin(lat1) ** 2)
    r1 = _A * (1 - e2) / (1 - e2 * math.sin(lat1) ** 2) ** 1.5
    d = (x - _FE) / (n1 * _K0)
    lat = lat1 - (n1 * math.tan(lat1) / r1) * (
        d * d / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 * c1 - 9 * ep2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 * t1 - 252 * ep2 - 3 * c1 * c1) * d ** 6 / 720)
    lon = _LON0 + (d - (1 + 2 * t1 + c1) * d ** 3 / 6
                   + (5 - 2 * c1 + 28 * t1 - 3 * c1 * c1 + 8 * ep2 + 24 * t1 * t1) * d ** 5 / 120
                   ) / math.cos(lat1)
    return (math.degrees(lon), math.degrees(lat))


def classify_stratum(feature_type, z):
    """Stratum of a node from its FeatureType (semantic) + absolute z elevation (mPD). See the
    module docstring for the z-band rationale."""
    if feature_type in ELEVATED_FT:
        return "skybridge"
    if z <= STREET_Z:
        return "street"
    if z <= PODIUM_Z:
        return "podium"
    return "skybridge"


def transit_for(feature_type):
    """Ride/transit kind for an edge of this FeatureType ('walk' for plain footways)."""
    return TRANSIT_BY_FT.get(feature_type, "walk")


def in_core(lon, lat):
    return CORE[0] <= lon <= CORE[2] and CORE[1] <= lat <= CORE[3]


def _snap_key(lon, lat):
    """Snap a vertex to a ~0.5 m grid (5 decimal places ~ 1.1 m) so shared endpoints of
    adjacent segments collapse to ONE node id — the network's connectivity comes from segments
    meeting at the same coordinate, exactly like hk_indoor builds connectivity from shared geom."""
    return (round(lon, 5), round(lat, 5))


def curate(fc, src="wgs84"):
    """Crop to CORE, project to lon/lat, classify strata, and emit the strata graph:
    {strata, nodes:[{id,stratum,lon,lat,height,kind}], edges:[{a,b,transit}], attribution}.
    Nodes are de-duplicated by snapped lon/lat; edges are reciprocal (undirected, by node id)."""
    node_id = {}                       # snap-key -> id string
    nodes = []                         # node dicts in id order
    edge_seen = set()                  # undirected edge keys, dedup a|b == b|a
    edges = []

    def node_for(lon, lat, z, ft):
        key = _snap_key(lon, lat)
        nid = node_id.get(key)
        if nid is not None:
            return nid
        nid = f"ped-{len(nodes)}"
        node_id[key] = nid
        stratum = classify_stratum(ft, z)
        kind = "walk" if transit_for(ft) == "walk" else "transit"
        nodes.append({"id": nid, "stratum": stratum, "lon": round(lon, 6),
                      "lat": round(lat, 6), "height": round(z, 2), "kind": kind})
        return nid

    for f in fc.get("features", []):
        geom = f.get("geometry") or {}
        if geom.get("type") != "LineString":
            continue
        coords = geom.get("coordinates") or []
        ft = (f.get("properties") or {}).get("FeatureType")
        # Project + crop every vertex; keep the polyline's in-CORE run as a chain of nodes.
        chain = []
        for c in coords:
            if not isinstance(c, (list, tuple)) or len(c) < 2:
                continue
            lon, lat = to_lonlat(c[0], c[1], src=src)
            if not in_core(lon, lat):
                chain = []                 # break the chain at the crop boundary
                continue
            z = c[2] if len(c) >= 3 else 0.0
            chain.append(node_for(lon, lat, z, ft))
        # consecutive vertices -> reciprocal edges tagged by the segment's transit kind
        kind = transit_for(ft)
        for a, b in zip(chain, chain[1:]):
            if a == b:
                continue
            ek = (a, b) if a < b else (b, a)
            if ek in edge_seen:
                continue
            edge_seen.add(ek)
            edges.append({"a": a, "b": b, "transit": kind})

    return _emit(nodes, edges)


def _emit(nodes, edges):
    strata_present = sorted({n["stratum"] for n in nodes},
                            key=lambda s: ["street", "podium", "skybridge"].index(s)
                            if s in ("street", "podium", "skybridge") else 99)
    gravity = {"street": "outward", "podium": "outward", "skybridge": "outward"}
    return {
        "strata": [{"id": s, "gravity": gravity.get(s, "outward")} for s in strata_present],
        "nodes": nodes,
        "edges": edges,
        "attribution": "HK Lands Dept / DATA.GOV.HK derived data",
    }


def simplify_graph(doc):
    """Collapse the raw per-vertex polyline graph to its TOPOLOGY for a lean nav-graph: keep only
    junction/endpoint nodes (degree != 2) and replace each degree-2 chain between two kept nodes
    with one edge (carrying the chain's dominant transit kind). Preserves connectivity + strata
    while cutting ~82k vertices to ~7k junctions — the import is a nav-graph, not a render mesh.
    Pure: takes/returns the {strata,nodes,edges,attribution} doc."""
    by_id = {n["id"]: n for n in doc["nodes"]}
    adj = {}
    for e in doc["edges"]:
        adj.setdefault(e["a"], []).append((e["b"], e["transit"]))
        adj.setdefault(e["b"], []).append((e["a"], e["transit"]))

    def degree(nid):
        return len(adj.get(nid, []))

    kept = {nid for nid in by_id if degree(nid) != 2}
    # An all-degree-2 loop has no junction; anchor it on one node so it isn't dropped entirely.
    if not kept and by_id:
        kept = {next(iter(by_id))}

    out_edges = []
    seen = set()
    for start in kept:
        for first_nb, first_kind in adj.get(start, []):
            # walk the degree-2 chain from `start` through `first_nb` until the next kept node
            prev, cur, kind = start, first_nb, first_kind
            while cur not in kept:
                nxt = next((nb for nb, _ in adj.get(cur, []) if nb != prev), None)
                if nxt is None or nxt == cur:
                    break
                # prefer a transit (ride) kind over plain walk for the collapsed edge
                cur_kind = next((k for nb, k in adj.get(cur, []) if nb == nxt), kind)
                if kind == "walk" and cur_kind != "walk":
                    kind = cur_kind
                prev, cur = cur, nxt
            end = cur
            if end == start or end not in kept:
                continue
            ek = (start, end) if start < end else (end, start)
            if ek in seen:
                continue
            seen.add(ek)
            out_edges.append({"a": ek[0], "b": ek[1], "transit": kind})

    out_nodes = [by_id[nid] for nid in by_id if nid in kept]
    return _emit(out_nodes, out_edges)


def fetch_core(page=3000, src="wgs84"):
    """Page the MapServer layer-0 query over the CORE bbox, returning one merged FeatureCollection
    of WGS84 lon/lat + z LineStrings. outSR=4326 makes the server reproject from WKID 2326 for us."""
    out_sr = "4326" if src == "wgs84" else "2326"
    features, offset = [], 0
    while True:
        q = {"geometry": ",".join(str(v) for v in CORE), "geometryType": "esriGeometryEnvelope",
             "inSR": "4326", "outSR": out_sr, "spatialRel": "esriSpatialRelIntersects",
             "outFields": "OBJECTID,FeatureType,Location,WheelchairAccess,StreetNameEN",
             "returnZ": "true", "resultRecordCount": str(page), "resultOffset": str(offset),
             "f": "geojson"}
        url = MAPSERVER + "?" + urllib.parse.urlencode(q)
        with urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "jubuddy/1.0"}), timeout=120) as r:
            fc = json.load(r)
        batch = fc.get("features", [])
        features.extend(batch)
        if not fc.get("exceededTransferLimit") and not (fc.get("properties") or {}).get(
                "exceededTransferLimit"):
            break
        if not batch:
            break
        offset += len(batch)
    return {"type": "FeatureCollection", "features": features}


if __name__ == "__main__":
    src = "hk1980" if "--hk1980" in sys.argv else "wgs84"
    fc = fetch_core(src=src)
    doc = curate(fc, src=src)
    if not doc["nodes"]:  # fail loud rather than write a silently-empty network (schema/endpoint drift)
        sys.exit("FATAL: no pedestrian nodes in the CORE crop — endpoint/schema drift?")
    raw_n = len(doc["nodes"])
    doc = simplify_graph(doc)  # collapse per-vertex polylines to a junction-topology nav-graph
    if not doc["nodes"]:
        sys.exit("FATAL: simplification emptied the graph — connectivity drift?")
    out = ("/Users/jubit_nb0/.config/superpowers/worktrees/jubuddy-game/graft-real-planet/"
           "apps/web/src/planet/sphere/assets/hk-strata.json")
    json.dump(doc, open(out, "w"))
    counts = {}
    for n in doc["nodes"]:
        counts[n["stratum"]] = counts.get(n["stratum"], 0) + 1
    print(f"raw_vertices={raw_n} -> nodes={len(doc['nodes'])} edges={len(doc['edges'])} "
          f"strata={counts} -> {out}")

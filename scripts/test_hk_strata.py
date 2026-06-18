import math
from hk_strata import (
    to_lonlat,
    classify_stratum,
    transit_for,
    in_core,
    curate,
    simplify_graph,
    CORE,
    FT_FOOTBRIDGE,
    FT_FOOTWAY,
    FT_ESCALATOR,
    FT_LIFT,
    FT_SUBWAY,
)


def test_to_lonlat_passthrough_wgs84():
    # When the MapServer query already returns WGS84 (outSR=4326), the producer fetches
    # lon/lat directly — to_lonlat must be an identity passthrough for already-geographic coords.
    lon, lat = to_lonlat(114.155, 22.284, src="wgs84")
    assert abs(lon - 114.155) < 1e-9 and abs(lat - 22.284) < 1e-9


def test_to_lonlat_hk1980_grid_lands_in_hong_kong():
    # HK1980 Grid (EPSG:2326) easting/northing for a point near Central should reproject to
    # ~114.16E / 22.28N. Reference: HK1980 grid origin 836694.05E / 819069.80N at 114.178555E /
    # 22.312133N. A point ~1 km SW of the grid origin must land in the Victoria Harbour CORE.
    lon, lat = to_lonlat(835000.0, 816000.0, src="hk1980")
    assert 114.0 < lon < 114.4, lon
    assert 22.1 < lat < 22.5, lat


def test_classify_stratum_ground_footway_is_street():
    # Footways at near-datum elevation (HK street z ~3-8 m mPD) are the street stratum.
    assert classify_stratum(FT_FOOTWAY, 3.9) == "street"
    assert classify_stratum(FT_FOOTWAY, 7.5) == "street"


def test_classify_stratum_footbridge_is_skybridge_regardless_of_terrain():
    # A Footbridge is an ELEVATED deck by definition (HK footbridges sample z ~8-18 m mPD).
    # Semantic FeatureType wins so a low-numbered z on a hillside footbridge is still a skybridge.
    assert classify_stratum(FT_FOOTBRIDGE, 11.4) == "skybridge"
    assert classify_stratum(FT_FOOTBRIDGE, 9.9) == "skybridge"


def test_classify_stratum_midlevel_footway_is_podium():
    # A plain footway in the podium z-band (mid elevation) reads as the podium deck.
    assert classify_stratum(FT_FOOTWAY, 18.0) == "podium"


def test_classify_stratum_high_footway_is_skybridge():
    # A footway high above the datum (elevated walkway network) reads as skybridge.
    assert classify_stratum(FT_FOOTWAY, 40.0) == "skybridge"


def test_transit_maps_feature_type_to_ride_kind():
    # Transition FeatureTypes carry the courier's ride animation.
    assert transit_for(FT_ESCALATOR) == "escalator"
    assert transit_for(FT_LIFT) == "lift"
    assert transit_for(FT_FOOTBRIDGE) == "skybridge"
    assert transit_for(FT_SUBWAY) == "stair"
    assert transit_for(FT_FOOTWAY) == "walk"


def test_in_core_crops_to_planet_bbox():
    cx = (CORE[0] + CORE[2]) / 2
    cy = (CORE[1] + CORE[3]) / 2
    assert in_core(cx, cy)
    assert not in_core(114.0, 22.28)  # west of the CORE crop
    assert not in_core(cx, 22.40)     # north of the CORE crop


def _feat(coords, ft):
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {"FeatureType": ft, "Location": 1, "StreetNameEN": "Test St"}}


def test_curate_builds_reciprocal_edges_by_node_id():
    # Two segments sharing an endpoint must produce ONE shared node (snapped) and reciprocal
    # edges. A street footway + a footbridge climbing off it gives a street->skybridge climb.
    fc = {"features": [
        _feat([[114.160, 22.290, 4.0], [114.161, 22.291, 4.2]], FT_FOOTWAY),
        _feat([[114.161, 22.291, 4.2], [114.1615, 22.2915, 12.0]], FT_FOOTBRIDGE),
    ]}
    doc = curate(fc, src="wgs84")
    # 3 distinct vertices -> 3 nodes (the shared [114.161,22.291] snaps to one id)
    assert len(doc["nodes"]) == 3
    ids = {n["id"] for n in doc["nodes"]}
    # every edge references real node ids, reciprocal pairs collapse to one undirected edge
    for e in doc["edges"]:
        assert e["a"] in ids and e["b"] in ids and e["a"] != e["b"]
    # the shared node connects both segments (degree >= 2 somewhere)
    deg = {}
    for e in doc["edges"]:
        deg[e["a"]] = deg.get(e["a"], 0) + 1
        deg[e["b"]] = deg.get(e["b"], 0) + 1
    assert max(deg.values()) >= 2
    # strata present: a street node and a skybridge node
    strata = {n["stratum"] for n in doc["nodes"]}
    assert "street" in strata and "skybridge" in strata


def test_curate_drops_segments_outside_core():
    fc = {"features": [
        _feat([[114.0, 22.28, 4.0], [114.001, 22.281, 4.2]], FT_FOOTWAY),  # west of CORE
    ]}
    doc = curate(fc, src="wgs84")
    assert doc["nodes"] == [] and doc["edges"] == []


def test_curate_emits_strata_and_attribution():
    fc = {"features": [_feat([[114.160, 22.290, 4.0], [114.161, 22.291, 4.2]], FT_FOOTWAY)]}
    doc = curate(fc, src="wgs84")
    assert "strata" in doc and any(s["id"] == "street" for s in doc["strata"])
    assert "Lands Dept" in doc["attribution"] and "DATA.GOV.HK" in doc["attribution"]
    for n in doc["nodes"]:
        assert {"id", "stratum", "lon", "lat", "height", "kind"} <= set(n)


def test_simplify_collapses_degree2_chain_keeping_junctions_and_transit():
    # A street footway with an intermediate degree-2 vertex, climbing into a footbridge:
    #   A(street) - B(street, deg2 pass-through) - C(footbridge junction) - D(footbridge)
    # Simplify must drop B (degree 2) and keep A, C, D, with one A->C edge carrying the
    # FOOTBRIDGE transit kind it passed through (ride kind beats plain walk).
    fc = {"features": [
        _feat([[114.160, 22.290, 4.0], [114.1605, 22.2905, 4.1]], FT_FOOTWAY),       # A-B
        _feat([[114.1605, 22.2905, 4.1], [114.161, 22.291, 12.0]], FT_FOOTBRIDGE),    # B-C
        _feat([[114.161, 22.291, 12.0], [114.1615, 22.2915, 12.2]], FT_FOOTBRIDGE),   # C-D
        _feat([[114.161, 22.291, 12.0], [114.1612, 22.2913, 12.1]], FT_FOOTBRIDGE),   # C-E (makes C deg3)
    ]}
    simple = simplify_graph(curate(fc, src="wgs84"))
    # B is a pure degree-2 pass-through -> dropped; A, C, D, E (junctions/endpoints) kept.
    n_street = sum(1 for n in simple["nodes"] if n["stratum"] == "street")
    assert n_street == 1, simple["nodes"]            # only A survives (B collapsed)
    # the collapsed A-C edge carries the ride kind it crossed, not plain walk
    ids = {n["id"]: n for n in simple["nodes"]}
    assert any(e["transit"] == "skybridge" for e in simple["edges"])
    # every edge still references real, distinct node ids (reciprocal/by id contract preserved)
    for e in simple["edges"]:
        assert e["a"] in ids and e["b"] in ids and e["a"] != e["b"]


def test_simplify_preserves_strata_set():
    fc = {"features": [
        _feat([[114.160, 22.290, 4.0], [114.161, 22.291, 4.2]], FT_FOOTWAY),
        _feat([[114.161, 22.291, 4.2], [114.1615, 22.2915, 12.0]], FT_FOOTBRIDGE),
        _feat([[114.1615, 22.2915, 12.0], [114.162, 22.292, 12.5]], FT_FOOTBRIDGE),
    ]}
    simple = simplify_graph(curate(fc, src="wgs84"))
    strata = {s["id"] for s in simple["strata"]}
    assert "street" in strata and "skybridge" in strata
    assert "Lands Dept" in simple["attribution"]

import math
from hk_indoor import project, poly_centroid, curate, _rings, _interior_point, _point_in_ring

def test_project_is_local_metres_from_origin():
    origin = (114.2244, 22.3116)
    x, y = project(114.2244, 22.3116, origin)
    assert abs(x) < 1e-6 and abs(y) < 1e-6
    east, _ = project(114.2244 + 0.001, 22.3116, origin)
    assert 90 < east < 110

def test_poly_centroid_of_unit_square():
    assert poly_centroid([[0, 0], [2, 0], [2, 2], [0, 2]]) == [1.0, 1.0]

def test_rings_keeps_all_multipolygon_parts():
    # a two-part unit (e.g. a split platform) must not silently lose its second part
    geom = {"type": "MultiPolygon", "coordinates": [
        [[[0, 0], [1, 0], [1, 1], [0, 1]]],
        [[[5, 5], [6, 5], [6, 6], [5, 6]]]]}
    assert len(_rings(geom)) == 2

def test_rings_point_geometry_is_skipped_not_crashed():
    assert _rings({"type": "Point", "coordinates": [114.2, 22.3]}) == []

def test_interior_point_lands_inside_concave_L_shape():
    # an L: the vertex/area centroid (~1.33, 1.33) sits in the notch (outside the footprint)
    L = [[0, 0], [3, 0], [3, 1], [1, 1], [1, 3], [0, 3]]
    pt = _interior_point(L, 1.33, 1.33)
    assert _point_in_ring(pt[0], pt[1], L)

def test_curate_coerces_string_level_ordinal():
    origin = (114.2244, 22.3116)
    levels_fc = {"features": [{"properties": {"level_ordinal": "0", "level_z_value": 0, "level_name_en": "G/F"}}]}
    units_fc = {"features": [
        {"properties": {"level_ordinal": "0", "unit_category": "room", "unit_name_en": "S1"},
         "geometry": {"type": "Polygon", "coordinates": [[[114.2244, 22.3116], [114.2245, 22.3116], [114.2245, 22.3117], [114.2244, 22.3117]]]}}]}
    out = curate(levels_fc, units_fc, {"features": []}, keep_levels=[0], shop_cats={"room"}, origin=origin)
    assert len(out["units"]) == 1 and out["units"][0]["level"] == 0

def test_curate_keeps_only_requested_levels_and_shop_units():
    origin = (114.2244, 22.3116)
    levels_fc = {"features": [
        {"properties": {"level_ordinal": 0, "level_z_value": 0, "level_name_en": "G/F"}},
        {"properties": {"level_ordinal": 1, "level_z_value": 5, "level_name_en": "1/F"}},
        {"properties": {"level_ordinal": 9, "level_z_value": 40, "level_name_en": "9/F"}},
    ]}
    units_fc = {"features": [
        {"properties": {"level_ordinal": 0, "unit_category": "retail", "unit_name_en": "Shop A"},
         "geometry": {"type": "Polygon", "coordinates": [[[114.2244, 22.3116], [114.2245, 22.3116], [114.2245, 22.3117], [114.2244, 22.3117]]]}},
        {"properties": {"level_ordinal": 0, "unit_category": "road", "unit_name_en": "DRIVEWAY"},
         "geometry": {"type": "Polygon", "coordinates": [[[114.2244, 22.3116], [114.2245, 22.3116], [114.2245, 22.3117]]]}},
        {"properties": {"level_ordinal": 9, "unit_category": "retail", "unit_name_en": "Far Shop"},
         "geometry": {"type": "Polygon", "coordinates": [[[114.2244, 22.3116], [114.2245, 22.3116], [114.2245, 22.3117]]]}},
    ]}
    doors_fc = {"features": [
        {"properties": {"level_ordinal": 0}, "geometry": {"type": "LineString", "coordinates": [[114.2244, 22.3116], [114.2245, 22.3116]]}},
        {"properties": {"level_ordinal": 9}, "geometry": {"type": "LineString", "coordinates": [[114.2244, 22.3116], [114.2245, 22.3116]]}},
    ]}
    out = curate(levels_fc, units_fc, doors_fc, keep_levels=[0, 1], shop_cats={"retail", "foodservice"}, origin=origin)
    assert [l["ordinal"] for l in out["levels"]] == [0, 1]
    assert len(out["units"]) == 1 and out["units"][0]["name"] == "Shop A" and out["units"][0]["level"] == 0
    assert all("poly" in u and "centroid" in u for u in out["units"])
    assert len(out["doors"]) == 1 and out["doors"][0]["level"] == 0

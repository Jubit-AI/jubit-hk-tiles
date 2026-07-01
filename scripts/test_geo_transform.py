"""Tests for the ortho-dimetric geo<->image projection (scripts/geo_transform.py).

These encode WHY the projection must behave as it does (not just that it runs):
the bake foreshortens latitude by sin(elevation) and leaves longitude full-scale,
so an actor placed by real lat/lon lands on the right street. A change that broke
the 2:1 dimetric ratio, the north-is-up flip, or the fwd/inverse symmetry would
silently misplace every train, ferry, and vignette — these tests fail if it does.
"""
import math

import pytest

import geo_transform as gt


def _manifest(az=-15.0, el=-26.565, vh=3000.0, w=4000, h=3000,
              clat=22.2816, clon=114.1578):
    return gt.build_manifest(
        dzi="test.dzi", image_width=w, image_height=h,
        center_lat=clat, center_lon=clon, view_height_meters=vh,
        azimuth_deg=az, elevation_deg=el,
    )


def test_center_maps_to_image_center():
    m = _manifest()
    px, py = gt.project(m, m["center"]["lat"], m["center"]["lon"])
    assert px == pytest.approx(m["image"]["width"] / 2, abs=1e-6)
    assert py == pytest.approx(m["image"]["height"] / 2, abs=1e-6)


@pytest.mark.parametrize("dlat,dlon", [
    (0.0, 0.0), (0.010, 0.0), (0.0, 0.012), (-0.008, 0.006), (0.02, -0.015),
])
def test_project_unproject_round_trip(dlat, dlon):
    m = _manifest()
    lat = m["center"]["lat"] + dlat
    lon = m["center"]["lon"] + dlon
    px, py = gt.project(m, lat, lon)
    back_lat, back_lon = gt.unproject(m, px, py)
    assert back_lat == pytest.approx(lat, abs=1e-9)
    assert back_lon == pytest.approx(lon, abs=1e-9)


def test_pixel_round_trip():
    m = _manifest()
    for px, py in [(0, 0), (1234, 987), (m["image"]["width"], m["image"]["height"])]:
        lat, lon = gt.unproject(m, px, py)
        bx, by = gt.project(m, lat, lon)
        assert bx == pytest.approx(px, abs=1e-6)
        assert by == pytest.approx(py, abs=1e-6)


def test_azimuth_zero_east_is_horizontal_north_is_up():
    # With no heading rotation, longitude drives px only, latitude drives py only.
    m = _manifest(az=0.0)
    cx, cy = m["image"]["width"] / 2, m["image"]["height"] / 2
    px_e, py_e = gt.project(m, m["center"]["lat"], m["center"]["lon"] + 0.01)  # due east
    assert px_e > cx and py_e == pytest.approx(cy, abs=1e-6)
    px_n, py_n = gt.project(m, m["center"]["lat"] + 0.01, m["center"]["lon"])  # due north
    assert py_n < cy and px_n == pytest.approx(cx, abs=1e-6)  # north = up = smaller y


def test_latitude_foreshortened_by_sin_elevation():
    # The 2:1 dimetric ratio: equal ground metres N and E, but N is squashed by
    # sin(elevation). sin(26.565°) ≈ 0.4472 → north pixel-offset ≈ 0.447 × east.
    m = _manifest(az=0.0, el=-26.565)
    cx, cy = m["image"]["width"] / 2, m["image"]["height"] / 2
    # equal ground metres: 0.01° lat vs the lon-degrees giving the same metres east
    d_lat = 0.01
    m_north = d_lat * gt.METERS_PER_DEG_LAT
    d_lon = m_north / (gt.METERS_PER_DEG_LAT * math.cos(math.radians(m["center"]["lat"])))
    _, py_n = gt.project(m, m["center"]["lat"] + d_lat, m["center"]["lon"])
    px_e, _ = gt.project(m, m["center"]["lat"], m["center"]["lon"] + d_lon)
    north_px = cy - py_n
    east_px = px_e - cx
    assert north_px / east_px == pytest.approx(math.sin(math.radians(26.565)), rel=1e-6)


def test_azimuth_rotates_the_ground_plane():
    # A due-north point should NOT stay on the vertical axis once the camera has a
    # heading — the whole map is rotated in-frame by the azimuth.
    m = _manifest(az=-15.0)
    cx = m["image"]["width"] / 2
    px_n, _ = gt.project(m, m["center"]["lat"] + 0.01, m["center"]["lon"])
    assert px_n != pytest.approx(cx, abs=1.0)  # rotated off the centre column


def test_bbox_brackets_the_center():
    m = _manifest()
    w, s, e, n = m["bbox"]
    assert s < m["center"]["lat"] < n
    assert w < m["center"]["lon"] < e


def test_build_manifest_schema():
    m = _manifest()
    assert m["schemaVersion"] == 1
    assert m["projection"]["type"] == "orthographic-dimetric"
    assert m["projection"]["metersPerDegLat"] == gt.METERS_PER_DEG_LAT
    assert m["bboxOrder"] == "[w,s,e,n]"
    assert set(m["image"]) == {"width", "height"}

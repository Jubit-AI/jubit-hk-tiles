"""Tests for the WGS84-ellipsoid ortho-dimetric projection (scripts/geo_transform.py).

These encode WHY the projection must behave as it does (not just that it runs). The
bake places tiles on the true WGS84 ellipsoid (getObjectFrame) and renders them with a
dimetric ortho camera, so `project` must: foreshorten the ground-forward axis by
sin(elevation), leave the ground-right axis full-scale, add the tangent-plane sagitta
via cos(elevation), and rotate the ground plane by the azimuth in the ONE validated
direction (AZIMUTH_SIGN=+1). A change that broke the 2:1 dimetric ratio, dropped the
ellipsoid/sagitta terms, or flipped the heading would silently misplace every train,
ferry, and plane — these tests fail if it does.

`unproject` is a deliberately COARSE flat-earth inverse (only used for the bbox hint +
the nearest-district pick), so its round-trip tests assert "close", not "exact".
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


def _enu(clat, clon, lat, lon):
    """True ellipsoid East/North/Up metres of (lat,lon) from the centre (test helper)."""
    e, n, u = gt._enu_basis(clat, clon)
    c = gt._ecef(clat, clon, gt.DEFAULT_TARGET_HEIGHT_M)
    p = gt._ecef(lat, lon, gt.DEFAULT_TARGET_HEIGHT_M)
    d = (p[0] - c[0], p[1] - c[1], p[2] - c[2])
    return gt._dot(e, d), gt._dot(n, d), gt._dot(u, d)


def test_center_maps_to_image_center():
    m = _manifest()
    px, py = gt.project(m, m["center"]["lat"], m["center"]["lon"])
    assert px == pytest.approx(m["image"]["width"] / 2, abs=1e-6)
    assert py == pytest.approx(m["image"]["height"] / 2, abs=1e-6)


@pytest.mark.parametrize("dlat,dlon", [
    (0.0, 0.0), (0.010, 0.0), (0.0, 0.012), (-0.008, 0.006), (0.02, -0.015),
])
def test_unproject_is_a_coarse_inverse(dlat, dlon):
    # unproject is flat-earth by design (see its docstring): it neglects the curvature
    # + sagitta terms `project` adds, so the round-trip returns to within tens of metres,
    # NOT exactly. That's all its callers (bbox hint, nearest-district argmin) need.
    m = _manifest()
    lat = m["center"]["lat"] + dlat
    lon = m["center"]["lon"] + dlon
    px, py = gt.project(m, lat, lon)
    back_lat, back_lon = gt.unproject(m, px, py)
    # 3e-4 deg ≈ 33 m — comfortably above the measured ~13 m worst case, still tight
    # enough to catch a genuinely broken inverse (which would be off by whole degrees).
    assert back_lat == pytest.approx(lat, abs=3e-4)
    assert back_lon == pytest.approx(lon, abs=3e-4)


def test_pixel_round_trip_is_coarse():
    # pixel → coarse-geo → exact-pixel closes to within a handful of px (the ellipsoid
    # vs flat-earth gap at the probed ground point), never wildly off.
    m = _manifest()
    for px, py in [(0, 0), (1234, 987), (m["image"]["width"], m["image"]["height"])]:
        lat, lon = gt.unproject(m, px, py)
        bx, by = gt.project(m, lat, lon)
        assert math.hypot(bx - px, by - py) < 15.0


def test_due_north_stays_on_the_centre_column_east_swings_right():
    # With no heading, a due-NORTH point (same longitude) lands EXACTLY on the centre
    # column — an ellipsoid invariant: the meridian plane is symmetric about the centre's
    # up/north, so its ENU-east is identically zero. A due-EAST point swings right and
    # stays on the centre row to within sub-pixel (parallel curvature is second-order).
    m = _manifest(az=0.0)
    cx, cy = m["image"]["width"] / 2, m["image"]["height"] / 2
    px_e, py_e = gt.project(m, m["center"]["lat"], m["center"]["lon"] + 0.01)  # due east
    assert px_e > cx
    assert py_e == pytest.approx(cy, abs=1.0)          # curvature makes it ~0.06 px, not 0
    px_n, py_n = gt.project(m, m["center"]["lat"] + 0.01, m["center"]["lon"])  # due north
    assert py_n < cy                                   # north = up = smaller y
    assert px_n == pytest.approx(cx, abs=1e-6)         # exact meridian symmetry


def test_forward_axis_foreshortened_by_sin_elevation():
    # The 2:1 dimetric ratio: per metre of true ground distance, the forward (north-ish)
    # axis is squashed to sin(elevation) of the right (east-ish) axis. Measured against
    # the TRUE ellipsoid ENU distances (small offsets → sagitta is negligible), so this
    # is exact ellipsoid physics, not a flat-earth coincidence.
    m = _manifest(az=0.0)
    clat, clon = m["center"]["lat"], m["center"]["lon"]
    ppm = m["image"]["height"] / m["projection"]["viewHeightMeters"]
    cx, cy = m["image"]["width"] / 2, m["image"]["height"] / 2
    _, n_m, _ = _enu(clat, clon, clat + 0.003, clon)         # north step, ENU metres
    e_m, _, _ = _enu(clat, clon, clat, clon + 0.003)         # east step, ENU metres
    _, py_n = gt.project(m, clat + 0.003, clon)
    px_e, _ = gt.project(m, clat, clon + 0.003)
    north_px_per_m = (cy - py_n) / n_m
    east_px_per_m = (px_e - cx) / e_m
    assert north_px_per_m / east_px_per_m == pytest.approx(
        math.sin(math.radians(26.565)), rel=1e-3)
    assert east_px_per_m == pytest.approx(ppm, rel=1e-3)     # right axis is full-scale


def test_azimuth_rotates_the_ground_plane():
    # A due-north point should NOT stay on the vertical axis once the camera has a
    # heading — the whole map is rotated in-frame by the azimuth.
    m = _manifest(az=-15.0)
    cx = m["image"]["width"] / 2
    px_n, _ = gt.project(m, m["center"]["lat"] + 0.01, m["center"]["lon"])
    assert px_n != pytest.approx(cx, abs=1.0)  # rotated off the centre column


def test_azimuth_sign_pinned_by_landmark_bearing():
    # Rigorously pin AZIMUTH_SIGN against a known-bearing landmark pair on the exact
    # central-hd manifest: the Central Star Ferry pier → the TST Star Ferry pier (true
    # compass bearing ≈ 52° NE). Under the validated rig (AZIMUTH_SIGN=+1) this projects
    # to a screen bearing of ≈ 59° measured clockwise from screen-up; flipping the sign
    # would swing it to ≈ 79°. A ±8° window admits +1 and excludes -1 — so this test
    # fails loudly if anyone flips the heading convention.
    m = gt.build_manifest(
        dzi="central-hd.dzi", image_width=8192, image_height=6144,
        center_lat=22.29, center_lon=114.164, view_height_meters=1500,
        azimuth_deg=-15.0, elevation_deg=-26.565,
    )
    central_star_ferry = (22.28955, 114.16175)
    tst_star_ferry = (22.2945, 114.1685)
    ax, ay = gt.project(m, *central_star_ferry)
    bx, by = gt.project(m, *tst_star_ferry)
    screen_bearing = math.degrees(math.atan2(bx - ax, -(by - ay)))  # cw from screen-up
    assert screen_bearing == pytest.approx(59.0, abs=8.0)
    assert gt.AZIMUTH_SIGN == 1.0  # the value the bearing above was validated against


def test_ellipsoid_terms_are_active_at_range():
    # The whole point of the upgrade: at territory range the sagitta (up·cos_el) term is
    # materially present — a flat tangent plane would drop it. Confirm a point ~24 km
    # from the centre sits tens of metres below the tangent plane (negative up), matching
    # the closed-form sagitta d²/2R, so the correction can't silently regress to flat.
    clat, clon = 22.335, 114.065                 # territory centre
    cape_daguilar = (22.2093, 114.2530)          # ~24 km ESE, HK Island's eastern tip
    east, north, up = _enu(clat, clon, *cape_daguilar)
    dist = math.hypot(east, north)
    assert dist == pytest.approx(23860, rel=0.02)
    assert up == pytest.approx(-dist * dist / (2 * gt.WGS84_A), rel=0.05)
    assert up < -30.0                            # not flat: a real, sizeable drop


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

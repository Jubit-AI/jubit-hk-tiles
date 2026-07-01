"""Tests for the OSM MTR track producer (scripts/mtr_tracks.py).

Offline: captured Overpass responses for the Island Line live in testdata/ and are
injected via the producer's `fetch` seam, so CI never hits the network. Two calls per
line: relations WITH members (`out body`) + all their ways' geometry (`way(id:…)`).
These encode WHY the geometry must be right: a gap in the stitched chain teleports a
train; a non-monotonic station index makes a train run backwards; an un-snapped station
means a branch/wrong relation was chosen. Each assertion guards one of those.
"""
import json
from pathlib import Path

import pytest

import mtr_tracks as mt

TD = Path(__file__).resolve().parent / "testdata"
REL_BODY = json.loads((TD / "isl_rel_body.json").read_text())    # step A: relations + members
WAYS = json.loads((TD / "isl_ways_by_id.json").read_text())      # step B: ways + geometry
NET = json.loads(mt.STATIONS_JSON.read_text())
ISL = [(s["code"], s["lat"], s["lon"]) for s in NET["ISL"]["stations"]]
GEOM = {w["id"]: w for w in WAYS["elements"] if w["type"] == "way"}


def isl_fetch(query: str) -> dict:
    """Inject the captured ISL responses by query shape."""
    if "out body;" in query:
        return REL_BODY
    if "way(id:" in query:
        return WAYS
    return {"elements": []}


def _relation(rid):
    return next(r for r in REL_BODY["elements"] if r["type"] == "relation" and r["id"] == rid)


def _relation_track_ids(rid):
    """Track (non-platform) member way ids of one relation."""
    return [m["ref"] for m in _relation(rid)["members"]
            if m["type"] == "way" and m["ref"] in GEOM and mt._is_track(GEOM[m["ref"]])]


def _relation_tracks(rid):
    return [mt._way_points(GEOM[w]) for w in _relation_track_ids(rid)]


ISL_DIR = 4432666  # the Kennedy Town → Chai Wan direction relation


def test_platform_ways_are_filtered():
    platforms = [w for w in WAYS["elements"] if w.get("tags", {}).get("railway") == "platform"]
    assert platforms, "fixture should contain platform loops to exclude"
    assert all(not mt._is_track(w) for w in platforms)     # platforms rejected
    assert len(_relation_tracks(ISL_DIR)) == 17            # only running-rail ways per direction


def test_stitch_produces_single_ordered_chain():
    tracks = _relation_tracks(ISL_DIR)
    chain, max_gap = mt.stitch(tracks)
    assert len(chain) == sum(len(t) for t in tracks)       # every vertex consumed once
    assert max_gap < 1.0                                   # ways join end-to-end (no teleport)


def test_every_station_snaps_within_threshold():
    chain, _ = mt.stitch(_relation_tracks(ISL_DIR))
    _, _, snap, _ = mt.snap_stations(chain, ISL)
    assert max(snap.values()) <= 300.0                     # platform centroids ≈ rail


def test_station_indices_are_monotonic():
    chain, _ = mt.stitch(_relation_tracks(ISL_DIR))
    _, idx, _, monotonic = mt.snap_stations(chain, ISL)
    assert monotonic
    order = [idx[c] for c, _, _ in ISL]
    assert order == sorted(order) and len(set(order)) == len(order)  # strictly increasing


def test_chain_oriented_to_our_station_order():
    chain, _ = mt.stitch(_relation_tracks(ISL_DIR))
    chain, _, _, _ = mt.snap_stations(chain, ISL)
    first, last = (ISL[0][1], ISL[0][2]), (ISL[-1][1], ISL[-1][2])
    # west end nearer Kennedy Town, east end nearer Chai Wan (rail overshoots the termini
    # into sidings, so assert orientation, not coincidence with the platform points).
    assert mt._dist_m(chain[0], first) < mt._dist_m(chain[0], last)
    assert mt._dist_m(chain[-1], last) < mt._dist_m(chain[-1], first)


def test_build_line_and_schema_valid():
    doc = mt.assemble(["ISL"], NET, fetch=isl_fetch, threshold_m=300.0,
                      generated="2026-07-02T00:00:00Z")
    assert doc["schemaVersion"] == 1 and doc["lines"]["ISL"]
    line = doc["lines"]["ISL"]
    assert set(line) == {"color", "path", "stationVertexIdx", "stationLatLon", "stationName"}
    assert len(line["color"]) == 7 and line["color"][0] == "#"
    assert all(len(pt) == 2 for pt in line["path"])
    codes = {s[0] for s in ISL}
    assert set(line["stationVertexIdx"]) == codes
    assert set(line["stationLatLon"]) == codes
    assert set(line["stationName"]) == codes
    assert all(len(v) == 2 for v in line["stationLatLon"].values())
    assert all(0 <= i < len(line["path"]) for i in line["stationVertexIdx"].values())
    assert doc["_meta"]["ISL"]["monotonic"] is True


def test_colour_is_official():
    doc = mt.assemble(["ISL"], NET, fetch=isl_fetch, threshold_m=300.0, generated="t")
    assert doc["lines"]["ISL"]["color"].lower() == "#007dc5"   # from the OSM relation tag


def test_coordinates_rounded():
    doc = mt.assemble(["ISL"], NET, fetch=isl_fetch, threshold_m=300.0, generated="t")
    for la, lo in doc["lines"]["ISL"]["path"]:
        assert round(la, mt.COORD_DP) == la and round(lo, mt.COORD_DP) == lo


def test_missing_line_fails_loud_on_tight_threshold():
    # An impossibly tight snap threshold means stations can't reach the rail → fail loud.
    with pytest.raises(mt.LineBuildError):
        mt.build_line("ISL", ISL, fetch=isl_fetch, threshold_m=5.0)


def test_no_relation_fails_loud():
    with pytest.raises(mt.LineBuildError):
        mt.build_line("ISL", ISL, fetch=lambda q: {"elements": []}, threshold_m=300.0)


def test_all_lines_failing_are_reported_together():
    # assemble collects every bad line (not just the first) so one run surfaces them all.
    with pytest.raises(mt.LineBuildError, match="line.s. failed"):
        mt.assemble(["ISL"], NET, fetch=isl_fetch, threshold_m=5.0, generated="t")


def test_scorer_prefers_the_full_trunk_over_a_spur():
    # Two candidate relations: id 1 = the full line, id 2 = a one-way spur. Scored purely
    # locally, the producer must pick the relation covering all stations.
    full_ids = _relation_track_ids(ISL_DIR)

    def two_rel_fetch(q: str) -> dict:
        if "out body;" in q:
            return {"elements": [
                {"type": "relation", "id": 1, "tags": {"ref": "ISL", "colour": "#007dc5"},
                 "members": [{"type": "way", "ref": w} for w in full_ids]},
                {"type": "relation", "id": 2, "tags": {"ref": "ISL", "colour": "#007dc5"},
                 "members": [{"type": "way", "ref": full_ids[0]}]},   # a single-way spur
            ]}
        if "way(id:" in q:
            return WAYS
        return {"elements": []}
    p = mt.build_line("ISL", ISL, fetch=two_rel_fetch, threshold_m=300.0)
    assert p["relationId"] == 1

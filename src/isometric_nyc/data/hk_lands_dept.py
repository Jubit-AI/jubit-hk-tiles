"""HK Lands Department 3D Visualisation Map / 3D Spatial Data adapter.

Replaces `nyc_opendata.py` in the Hong Kong adaptation. The upstream NYC
ingest pulled building footprints from Socrata; the HK pipeline instead
fetches **Cesium 3D Tiles tilesets** directly from the Lands Department,
which already includes textured 3D geometry — so the photoreal layer is
free and we skip the upstream's satellite-compositing step.

See `docs/HK-ADAPTATION-PLAN.md` for week-by-week status and
`scripts/request-hk-api-key.md` for the API-key request flow.

Endpoints we use:
  - https://data.map.gov.hk/api/3d-data/3dsd/WGS84/building/tileset.json
  - https://data.map.gov.hk/api/3d-data/3dsd/WGS84/infrastructure/tileset.json
  - https://data.map.gov.hk/api/3d-data/3dtiles/f2/tileset.json   (visualisation map)

API key is issued free of charge on email request to 3dmap@landsd.gov.hk;
fair-use limits are 5 GB/sec bandwidth and 100 concurrent users.

Spatial reference: WGS84 (EPSG:4326) — already matches the upstream
renderer's expectations.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

import requests

API_BASE = "https://data.map.gov.hk/api/3d-data"

# Endpoint paths — keep this list in sync with `docs/legal/attribution.md`.
ENDPOINT_BUILDING = "/3dsd/WGS84/building/tileset.json"
ENDPOINT_INFRASTRUCTURE = "/3dsd/WGS84/infrastructure/tileset.json"
ENDPOINT_VISUALISATION = "/3dtiles/f2/tileset.json"

Layer = Literal["building", "infrastructure", "visualisation"]


@dataclass(frozen=True)
class HKBoundingBox:
    """Lat/lng bounding box in WGS84 (degrees). South-West / North-East."""

    south: float
    west: float
    north: float
    east: float

    def __post_init__(self) -> None:
        if not (-90 <= self.south <= self.north <= 90):
            raise ValueError(f"invalid lat range: south={self.south} north={self.north}")
        if not (-180 <= self.west <= 180 and -180 <= self.east <= 180):
            raise ValueError(f"invalid lng range: west={self.west} east={self.east}")


# Useful canonical bboxes — populated as we add districts in the per-week schedule.
# Initial pilot target is Central; coordinates derived from HK GeoData reference.
DISTRICT_BBOXES: Dict[str, HKBoundingBox] = {
    "central": HKBoundingBox(south=22.273, west=114.150, north=22.290, east=114.170),
    # tst, causeway_bay, kowloon, etc. — populate as Week 7-10 districts come online.
}


class HKLandsDeptClient:
    """Lightweight Cesium 3D Tiles client for the HK Lands Department.

    Mirrors the shape of `nyc_opendata.NYCOpenDataClient` so callers in the
    upstream pipeline can swap one for the other with minimal churn.

    Usage:
        client = HKLandsDeptClient()  # reads HK_LANDSD_API_KEY from env
        tileset = client.fetch_tileset("building")
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = API_BASE):
        self._api_key = api_key or os.environ.get("HK_LANDSD_API_KEY")
        self._base_url = base_url.rstrip("/")
        if not self._api_key:
            # Don't raise yet — allow Week 1 scaffold to import the module
            # without the key. Methods that hit the network will raise.
            pass

    def _require_key(self) -> str:
        if not self._api_key:
            raise RuntimeError(
                "HK_LANDSD_API_KEY is not set. "
                "See scripts/request-hk-api-key.md for the request flow."
            )
        return self._api_key

    @staticmethod
    def _endpoint_path(layer: Layer) -> str:
        if layer == "building":
            return ENDPOINT_BUILDING
        if layer == "infrastructure":
            return ENDPOINT_INFRASTRUCTURE
        if layer == "visualisation":
            return ENDPOINT_VISUALISATION
        raise ValueError(f"unknown layer: {layer!r}")

    def fetch_tileset(self, layer: Layer, timeout_s: float = 30.0) -> Dict[str, Any]:
        """Fetch the root tileset.json for a given layer.

        Returns the parsed Cesium 3D Tiles tileset definition. The bbox
        filtering happens by traversing the tile tree client-side — this
        method only returns the root entrypoint.

        Network call. Raises RuntimeError if the API key isn't configured.
        """
        api_key = self._require_key()
        url = f"{self._base_url}{self._endpoint_path(layer)}"
        response = requests.get(
            url,
            params={"key": api_key},
            timeout=timeout_s,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()

    def list_districts(self) -> Dict[str, HKBoundingBox]:
        """Convenience accessor for the canonical district bboxes."""
        return dict(DISTRICT_BBOXES)


__all__ = [
    "API_BASE",
    "DISTRICT_BBOXES",
    "HKBoundingBox",
    "HKLandsDeptClient",
    "Layer",
]

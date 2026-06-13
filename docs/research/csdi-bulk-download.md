# CSDI / bulk-download mechanics for the full-territory bake

**Verified 2026-06-13** against the live data.gov.hk dataset pages. This is the source-of-truth for *where Output A (the full-territory map) pulls its data from* — distinct from the live `3dsd` API used for the Central pilot. Read alongside `docs/legal/attribution.md`.

## TL;DR

- The full-territory bake should use the **3D Visualisation Map (Tile-based models)** download portal at `3d.map.gov.hk` — it's listed as a resource on the data.gov.hk dataset page, so it's the **open-data-terms** path, and it's the textured product we want.
- **Avoid 3D-BIT00 for now**: its bulk download routes through `www.hkmapservice.gov.hk/OneStopSystem/…`, the *same host family* the FINAL research flagged as the stricter-terms regime. This **refines** PR #3, which had suggested 3D-BIT00 as a clean bulk source — the host raises a terms flag. Verify hkmapservice One-Stop-System terms in writing before using it.
- Both bulk products download via **interactive map-selector portals**, not direct programmatic file URLs. A fully-automated fetcher needs portal-internal-API work — deferred (see "Why no automated fetcher yet").

## Verified resources

### 3D Visualisation Map (Tile-based models) — TEXTURED — RECOMMENDED bulk source
data.gov.hk dataset: `hk-landsd-openmap-3d-visualisation-map-tile-based-models`
Provider: Lands Department · Update: "as and when there is update" · Coverage: whole territory

| Format | Download | Terms |
|---|---|---|
| OBJ | `https://3d.map.gov.hk/mapviewer/app/download-api?l=en-US` | open-data (listed on data.gov.hk) |
| OSGB | `https://3d.map.gov.hk/mapviewer/app/download-api?l=en-US` | open-data |
| **Cesium 3D Tiles** | `https://3d.map.gov.hk/mapviewer/app/download-api?l=en-US` | open-data |
| API | `https://portal.csdi.gov.hk/geoportal/?datasetId=landsd_rcd_1671677054006_62261` | open-data (CSDI) |

This is the same `3d.map.gov.hk/download-api` the operator originally referenced. The Cesium-3D-Tiles bulk export matches the pilot's `b3dm` format, so the renderer consumes both identically.

### 3D Spatial Data 3D-BIT00 — TEXTURED — ⚠️ terms-flagged, do not use yet
data.gov.hk dataset: `hk-landsd-openmap-development-hkms-digital-3d-bit00`
Provider: Lands Department · Update: **every 2 months** (fresher than Tile-based) · geometry + texture + textual attributes

| Format | Download | Terms |
|---|---|---|
| MAX / 3DS / FBX / VRML | `https://www.hkmapservice.gov.hk/OneStopSystem/map-search?product=OSSCatB&series=3D-BIT00` | ⚠️ **hkmapservice host — verify before use** |
| API | `https://portal.csdi.gov.hk/geoportal/?datasetId=landsd_rcd_1637306559892_42396` | open-data (CSDI) |

The 3D-BIT00 textual attributes (building type/height/footprint) are valuable for Phase-2 Output G (district-board lane suggestions) — but only adopt this product once the hkmapservice download terms are confirmed open-data in writing. The CSDI Portal API path may be the clean alternative for the attributes.

## Why no automated fetcher yet (Rule 2 — nothing speculative)

Both bulk products download through **interactive portals** (`3d.map.gov.hk/mapviewer/app` viewer; hkmapservice One-Stop-System map-search), where the user selects tiles/districts on a map and the portal bundles a download. There is no documented direct-file URL pattern. A programmatic fetcher would require reverse-engineering each portal's internal request API — speculative work we won't do blind.

**Path forward (next session, deliberate):**
1. Open `3d.map.gov.hk/mapviewer/app/download-api` in a browser, select a Central tile, and capture the actual download request (DevTools network tab) → that reveals the real internal endpoint + params.
2. Build the fetcher against that captured endpoint, district-batched (Central → TST → … per the plan's coverage schedule).
3. Fall back to the live `3dsd` API (already wired in `hk_lands_dept.py`) for the Central pilot — that path is proven and open-data.

## Decision

- **Pilot (now)**: live `3dsd` API — proven, open-data. No change.
- **Full territory (Weeks 7–10)**: Tile-based models Cesium-3D-Tiles bulk via `3d.map.gov.hk/download-api`, district-batched. Capture the portal's internal endpoint first.
- **3D-BIT00 attributes (Phase 2)**: only after hkmapservice terms are confirmed open-data in writing.

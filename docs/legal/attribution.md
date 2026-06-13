# Legal compliance — attribution + permitted use

## HK Lands Department / DATA.GOV.HK terms

Source: [DATA.GOV.HK Terms and Conditions](https://data.gov.hk/en/terms-and-conditions). The dataset is permissive for both commercial and non-commercial use, **free of charge**, with the following load-bearing conditions:

### Mandatory

1. **Attribution**: clearly identify "Government of HK SAR" / "Lands Department" / "DATA.GOV.HK" as the data source in every consumer surface that ships data derived from it.
2. **IP acknowledgement**: state that the Government of HK SAR retains copyright in the underlying data, even in derivative works.
3. **No resale of the data**: this is the one explicit prohibition in the FAQ. Selling a *game* containing derivative stylized assets is permitted (transformative product). Selling the *tiles themselves* as an asset pack is the prohibited line.
4. **Indemnity**: you indemnify the Government against third-party infringement claims arising from your use.

### Two licensing regimes — do not confuse them (FINAL research, 2026-06-13)

HK gov 3D data is served from confusingly-similar hosts under **different terms**. Getting this wrong is a compliance failure, so it's a hard rule:

| Source | Terms | Use |
|---|---|---|
| **3D Spatial Data API** — `data.map.gov.hk/api/3d-data/3dsd/…` | Open-data regime: attribution-only, **no logo-on-map-face** | ✅ Central pilot (live). Our Week 2 adapter uses this — verified safe. |
| **CSDI bulk downloads** — `geodata.gov.hk/gs/`, `portal.csdi.gov.hk` | Open-data regime (same as above) | ✅ **The full-territory bake source** — cleanest terms, doesn't hammer the live API. |
| **Legacy Map API** — `api.portal.hkmapservice.gov.hk` (topographic/imagery) | **Stricter**: Lands Dept logo *on the map face* + bundled Sentinel-2/Landsat/MODIS imagery, each with own attribution | ❌ **Never ingest from it.** Defeats "stay on the government mesh." |

**Hard rules:**
- The offline bake ingests **only** from CSDI bulk downloads (or the `3dsd` API for the pilot). Never the legacy Map API.
- ⚠️ **Before commercial launch**: confirm the exact `3dsd` open-data terms in writing with Lands Dept. The "safe" finding is strong but the FINAL research flagged the two-regime split as a trap — get it in writing.

### Textured, not whitebox (FINAL research, 2026-06-13)

Target **textured** products only. The headline ~220K Sept-2025 **"3D Visualisation Map (Non-textured models)"** is geometry-only whitebox — the exact thing the upstream NYC artist abandoned (untextured geometry → image-model hallucination). Textured sources: the `3dsd` Tile-based models (live, verified textured b3dm), **"3D Spatial Data 3D-BIT00" (FBX)** or **"Individualised models" (glTF)** for bulk.

### Trademark / signage caveat (not covered by the data license)

The open-data license covers the geospatial data. It does **not** grant trademark rights to logos that appear baked into textures — IFC, ICC, Bank of China Tower, MTR, named retail chains. Recognizable corporate signage in a commercial product is a separate trademark question. Architectural *shapes* are free under HK Copyright Ordinance §71 (public-place depiction exemption); only logos/signage/names are protected.

**Mitigation in our pipeline**: the soft-stylised re-style at Stage 2A naturally abstracts most signage into unreadable color blocks. The Week 11 legal spot-check (per `docs/HK-ADAPTATION-PLAN.md`) verifies this on the hero-location crops (which get the most user attention).

## Cannoneyed/isometric-nyc upstream — MIT

Upstream license: **MIT**, retained.

The original `LICENSE` file in this repo is the upstream MIT license. We do not replace it. Our additions (HK adaptation code, docs, training data) are added under the same MIT terms unless individually noted.

## Where attribution must appear

| Consumer surface | Attribution location |
|---|---|
| `dseek.ai/data/life` (Output A) | Page footer + about modal. Wording: *"Built on Hong Kong Lands Department 3D Visualisation Map (data.map.gov.hk / DATA.GOV.HK). © Government of HK SAR. Pipeline forked from cannoneyed/isometric-nyc (MIT)."* |
| `jubuddy-hk` game (Output B) | In-game credits screen + About menu. Same wording. |
| This repo (`jubit-hk-tiles`) | `README.md` (already present) + this file. |

## Compliance checklist (run before any consumer surface ships)

- [ ] Attribution text present on the consumer surface
- [ ] Attribution links to data.gov.hk and cannoneyed/isometric-nyc work
- [ ] No third-party satellite imagery composited into outputs (HK mesh only)
- [ ] No public marketing of "asset pack" / "tile pack" sale
- [ ] Visual spot-check: <5% of sampled tiles contain legibly-readable trademark text
- [ ] MIT license file present at repo root unchanged

## Out of scope (deferred to legal review if pursued)

- Reselling the tile library as an asset pack. Currently prohibited by HK terms.
- Compositing third-party satellite imagery (Google / Esri / Mapbox) into outputs. Their licenses don't extend to commercial game distribution.
- Use of trademarked landmarks (IFC, ICC, Bank of China Tower) at legible scale in Output B backdrops. Requires either deeper stylization or separate trademark clearance.

## References

- [DATA.GOV.HK Terms and Conditions](https://data.gov.hk/en/terms-and-conditions)
- [HK Lands Dept 3D Mapping](https://www.landsd.gov.hk/en/survey-mapping/mapping/3d-mapping.html)
- [Upstream LICENSE (MIT)](../../LICENSE) — `cannoneyed/isometric-nyc`

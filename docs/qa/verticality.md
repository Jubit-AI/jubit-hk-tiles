# R&D: HK-specific verticality occlusion

**Status**: Open problem. Resolution targeted for Week 2 (Central pilot).

## The problem in one sentence

A 400m tower next to a 6-storey tong lau on a 30° slope, viewed at a fixed isometric camera angle, occludes everything behind it.

## Why this is new (NYC didn't have it)

The upstream `cannoneyed/isometric-nyc` works because NYC's vertical scale is comparatively uniform — Manhattan skyscrapers vary but stand on flat ground in a regular grid. The standard isometric camera (`azimuth 45°, elevation -45°` per upstream's `whitebox.py`) projects cleanly onto that geometry.

Hong Kong is not that. Three compounding factors break the assumption:

1. **Extreme height variation** at fine spatial scale. Central has 30+ towers above 200m intermixed with 4–10 storey tong lau. A single 256-pixel isometric tile can contain both, and the tall building hides the shorter one entirely.
2. **Slopes**. Mid-Levels, The Peak, Pok Fu Lam, the New Territories hillside developments — building bases sit at radically different elevations within a single tile. A flat camera projects them on top of each other.
3. **Dense pedestrian-level features** that we want to preserve (street markets, MTR exits, footbridges) get crushed by the towers above them at any usable zoom.

The upstream NYC pipeline has no tooling for this — Central Park is not the Peak, and Wall Street is not Mid-Levels.

## Options for Week 2 to evaluate

In rough order of preference:

### Option A — Tile-local camera angle (recommended starting point)

Adjust the orthographic camera elevation per tile based on the local height distribution. Tiles dominated by tall towers get a steeper (more top-down) angle; pedestrian-density tiles get the standard 45° isometric. Implementation:

- Compute height variance in the tile bbox before render
- Map variance → elevation in `[-45°, -70°]`
- Tag each tile's camera angle in `generation_config.json`

Pro: preserves stylistic consistency within each tile; reduces occlusion proportionally to need.
Con: tile boundaries can show camera-angle seams. Mitigation: ease the angle across neighbour tiles.

### Option B — Accept the occlusion stylistically

Treat tall-building occlusion as part of the aesthetic — "looking up at HK's towers." Use the standard isometric angle territory-wide. Add a stylized "shadow side" treatment so occluded ground reads as intentional, not missing data.

Pro: no per-tile complexity; matches the SimCity 2000 inspiration where tall buildings simply hide what's behind them.
Con: loses pedestrian-level detail in dense districts (the whole point of HK).

### Option C — Multi-pass render with foreground/background masks

Render each tile twice: once standard (foreground = nearest 100m of geometry), once top-down (background = far geometry). Composite with a soft gradient mask. The AI infill in Stage 2A glues the two passes together.

Pro: preserves both pedestrian detail and skyline.
Con: doubles render time and Modal spend. May confuse Qwen fine-tune unless training set explicitly includes composited examples.

### Option D — Reduce coverage of pathological tiles

For the worst tiles (Central core, ICC area), generate at higher zoom — show each block individually instead of the full district in one tile. Stitch in the DZI viewer.

Pro: clean per-block legibility, no occlusion within a tile.
Con: complicates the DZI generation; not all districts need it.

## Recommendation for Week 2 pilot

Render Central with **Option A** (per-tile camera angle, height-variance-driven). Use Central specifically because it has the worst version of this problem — if A works there, it works everywhere. Fall back to **Option B** if A produces unacceptable tile-boundary seams. Reserve **Option C** for Week 7–10 if needed for select Mid-Levels and Peak districts.

## Decision log (update as Week 2 progresses)

**2026-06-13 — data-half findings (pre-render).** Confirmed against the live API before any render:
- HK building tiles use **`box` bounding volumes** in ECEF (center + 3 half-axis vectors), with a `transform` on the root tile, `REPLACE` refinement, 44 root children. This matters for the camera work two ways:
  1. **Cropping**: we can't filter to a district with a cheap lat/lng test (the volumes aren't geographic `region`s). Decode the box + apply the root transform → ECEF, then test against the district bbox; or crop via the camera frustum at render time.
  2. **Verticality**: the box half-axes give us per-tile height extent directly (the vertical half-axis magnitude). That's exactly the signal Option A needs — we can drive the per-tile camera elevation off the box's vertical extent without a separate height-variance pass. Bonus: Option A got cheaper.
- Real `b3dm` payloads confirmed (textured mesh, ~150 KB/tile). The renderer will consume `b3dm`, not `glb` directly — `3d-tiles-renderer` handles `b3dm` natively, so no format conversion needed.

**2026-06-13 — first Central render done (20 tiles).** Used a **constant** camera angle territory-wide (azimuth -15°, true-iso elevation -35.264°, `view_height_meters=350`) — i.e. **Option B (accept stylistic occlusion)** for the pilot, NOT yet the per-tile Option A. Findings:
- Dense-core tiles (e.g. tile_10, Central towers) show mild verticality occlusion — tall towers overlap shorter buildings behind them — but the result is legible and characterful (SimCity-esque), so it's **accepted for the pilot** per the plan's gate ("FAIL = re-tune camera or accept stylistic occlusion").
- The constant angle gives clean tileability (no per-tile seams), which matters for the eventual seamless map (Output A).
- **Option A (per-tile elevation from the box vertical half-axis) is deferred** to the full-territory pass, and only IF specific dense tiles (Mid-Levels / ICC / IFC) prove unacceptable. The `central_pilot_fetch.py` walk already exposes each tile's box; wiring `view_height` per-tile from `hz` is the upgrade path if needed.
- `TARGET_HEIGHT=5` + `view_height=350` framed the buildings acceptably; harbour-edge tiles (SW/NE corners of the bbox) are correctly building-sparse, not a framing bug.

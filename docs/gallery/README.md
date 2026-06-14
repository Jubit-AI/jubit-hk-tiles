# Gallery — Yok-Iso HK: soft isometric parchment city

Sample output of the deterministic (no-AI) soft-stylise pipeline — the locked
**"Yok-Iso HK: soft isometric parchment city"** style (`yok_iso_hk_soft_pictorial`):
soft isometric diorama with pixel-CLEAN edges (NOT crunchy retro pixel-art),
Yok-palette hex-locked to Codex's `jubuddy-game` tokens under a 70 parchment /
20 ink / 6 teal-neon / 3 cinnabar / 1 gold budget. All regenerable from live HK
Lands Dept 3D open data — these PNGs are committed only as a visual reference.

| Image | What it shows |
|---|---|
| `central-seamless-map.png` | **Seamless Output-A map** — a 3×3 `--viewmap` stitch (one shared ortho projection via setViewOffset), the deep-zoom map served in `viewer/` via OpenSeaDragon. No tile seams; towers align across boundaries. |
| `hk-island-strip-map.png` | **Scale test** — a 6×4 (24-tile) multi-district `--viewmap`: Central → Wan Chai → Causeway Bay + Kowloon. Seamless at 6144×4096, 0 failures. Validates the pipeline at multi-district scale. |
| `central.png` | CBD towers — dense verticality, ink contours, concrete massing |
| `mong-kok.png` | Dense urban grid — the tuning test bed |
| `mong-kok-night.png` | **Day↔night re-light** (`--night`) — same geometry dropped into a deep-harbour dusk, accents ignited |
| `mong-kok-vector.png` | **Stylized-vector-illustration** preset (`--vector`) — flat graphic masses, bold outlines, no grain |
| `sham-shui-po.png` | Tong-lau tenement density |
| `victoria-harbour.png` | Harbour treatment — big rice-paper negative space, piers reaching in |
| `prop-mongkok-block.png` | A **transparent prop sprite** (jubuddy-HK identity layer) — block isolated on alpha |

## Regenerate

```bash
# bun must be on PATH: PATH="$HOME/.bun/bin:$PATH"

# 12 hero-location backdrop tiles (full scene, styled)
uv run python scripts/central_render_bake.py \
  --locations scripts/locations.json --pixel 6 --out-dir hero-soft

# Transparent prop sprites (game-ready, alpha-isolated landmarks)
uv run python scripts/central_render_bake.py \
  --locations scripts/props.json --transparent --pixel 6 --out-dir props
```

Output lands in `scripts/out/<out-dir>/` (gitignored). The bake reports a live
textured-mesh count per tile (`N/N tex`) and fails loud on a real whitebox
(untextured fraction > 20% or transcoder-init failure).

## Notes
- **Hero tiles** = backdrops / location-card art (full scene, sky filled).
- **Prop sprites** (`--transparent`) = the jubuddy-HK *identity layer*: tightly-
  framed HK landmarks on a transparent background, to drop onto a hand-authored
  ground layer. In dense HK the dimetric frame catches a vertical *slab* of a
  block (the merged b3dm meshes aren't individually addressable), so these are
  "block props" — single-building isolation is a later per-object-rebake step.

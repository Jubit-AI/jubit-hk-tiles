# Gallery — Soft-Stylised Dimetric HK

Sample output of the deterministic (no-AI) soft-stylise pipeline, Yok-palette
hex-locked to Codex's `jubuddy-game` tokens. All regenerable from live HK Lands
Dept 3D open data — these PNGs are committed only as a visual reference.

| Image | What it shows |
|---|---|
| `central.png` | CBD towers — dense verticality, ink contours, concrete massing |
| `mong-kok.png` | Dense urban grid — the tuning test bed |
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

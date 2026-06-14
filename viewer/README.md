# Viewer — Output A deep-zoom map (dseek.ai/data/life pixel mode)

OpenSeaDragon deep-zoom viewer for the seamless Yok-Iso HK map. `index.html` is
committed; the DZI pyramid (`*.dzi` + `*_files/`) is **generated, gitignored**,
and regenerated from the bake.

## Full pipeline (proven end-to-end at Central scale)

```bash
# bun on PATH: PATH="$HOME/.bun/bin:$PATH"

# 1. Bake a SEAMLESS styled map grid (one shared ortho projection via
#    setViewOffset — tiles stitch perfectly, towers align across boundaries).
#    Args: center_lat,center_lon,cols,rows,full_view_height_m
uv run python scripts/central_render_bake.py \
  --viewmap "22.2815,114.160,3,3,1200" --out-dir viewmap-soft

# 2. Stitch the r{row}_c{col} tiles into one image.
uv run python scripts/stitch_grid.py \
  --in scripts/out/viewmap-soft --out scripts/out/viewmap-soft/_stitched.png

# 3. Build the DZI pyramid (pure Pillow — no libvips/sharp needed).
uv run python scripts/make_dzi.py \
  --in scripts/out/viewmap-soft/_stitched.png --out viewer/central

# 4. Serve + view (OpenSeaDragon loads central.dzi).
cd viewer && python3 -m http.server 8899   # → http://localhost:8899/index.html
```

`index.html?dzi=<name>.dzi` switches the source.

## Why this is seamless

The map is **not** independently-framed tiles (those leave gaps + sliced-tower
seams). It is ONE orthographic projection of the whole area, sub-tiled with
`camera.setViewOffset()` — every tile is a viewport window into the same
projection, so a tower straddling a boundary renders its top in the tile above
and base in the tile below, exactly aligned. See `aesthetic-spec §7`.

## Deploy (Vercel static — dseek.ai/data/life)

`viewer/` is a self-contained static site (`index.html` + `vercel.json` + the
generated DZI). `vercel.json` sets `immutable` cache on the tile pyramid. The DZI
is gitignored but **is** uploaded by `vercel deploy` (it respects `.vercelignore`,
not `.gitignore`), so generate it first (steps 1–3 above), then:

```bash
cd viewer

# Preview deploy (temporary *.vercel.app URL — validate on Vercel's CDN):
vercel deploy --yes

# Production promotion to dseek.ai/data/life — run deliberately:
#   vercel link            # link to the dseek project once
#   vercel deploy --prod   # then alias /data/life to this deployment
```

> Scope is `m1zwell`; the dseek project is `dseek-20250516` (not yet deployed to
> production). The production push to the public dseek.ai domain is a deliberate,
> outward-facing step — run it yourself / confirm before going live. Keep the HK
> Lands Dept attribution in `index.html`.

## Notes / polish backlog
- `imageSmoothingEnabled:false` keeps zoomed-in edges crisp (pixel-clean), but
  faint DZI tile-grid lines can show on flat parchment at some zooms — tune
  `overlap` in `make_dzi.py` or flip smoothing if it bothers a given surface.
- Territory scale: bake larger `cols×rows` (or batched districts) → stitch →
  DZI. LOD tuning + the live-API-vs-CSDI-bulk source decision come at that scale.
- **Attribution in `index.html` is REQUIRED by the HK Lands Dept open-data terms
  — do not remove.**

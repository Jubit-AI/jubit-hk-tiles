#!/usr/bin/env python3
"""Week-2 render-half: bake ~20 Central HK isometric PNG tiles.

Drives the HK-retargeted src/web_render page headlessly via Playwright and
writes tile_XX.png to scripts/out/central/. Reuses the exact, proven export
contract from src/isometric_nyc/export_views.py (launch args, networkidle,
window.TILES_LOADED gate, page.screenshot) — see the blueprint at
~/.claude/plans (render-half-blueprint workflow).

Standalone by design: no generation_dir / quadrants.db / bounds coupling.
That NYC machinery is out of scope for a 20-tile pilot (Rule 2/3).

Usage:
  uv run python scripts/central_render_bake.py             # all 20 tiles
  uv run python scripts/central_render_bake.py --limit 1   # single smoke tile
  uv run python scripts/central_render_bake.py --disable-web-security  # if CORS blocks

Read-only against data.map.gov.hk (key from .env.local via the Vite bundle).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
WEB_RENDER_DIR = REPO / "src" / "web_render"
PORT = 5174  # avoid clashing with a manually-run vite on 5173

# Central bbox — proven in hk_lands_dept.DISTRICT_BBOXES["central"].
S, W, N, E = 22.273, 114.150, 22.290, 114.170
COLS, ROWS = 5, 4  # 20 tiles
VIEW_HEIGHT_M = 350.0  # ground footprint per tile (m); Central's tall massing
# Constant azimuth (tileability) + SC2000 dimetric elevation. -26.565° (the
# classic 2:1 "military projection") shows more tower FACE than true-iso
# (-35.264°), which better conveys HK's taller/denser verticality and is more
# SimCity-2000-authentic. Chosen by visual A/B on dense Mong Kok. Override per
# render with --elevation. See docs/qa/verticality.md.
AZ, EL = -15.0, -26.565
WIDTH = HEIGHT = 1024


def grid_centers():
    """20 tile centers across the Central bbox, row-major.

    Yields (label, lat, lon, view_height_m) — view_height fixed to the
    Central default for the uniform grid.
    """
    for r in range(ROWS):
        for c in range(COLS):
            lat = S + (N - S) * (r + 0.5) / ROWS
            lon = W + (E - W) * (c + 0.5) / COLS
            yield f"tile_{r * COLS + c:02d}", lat, lon, VIEW_HEIGHT_M


def map_grid(center_lat, center_lon, cols, rows, footprint_m, elevation_deg, azimuth_deg):
    """Seamless tile centers for a deep-zoom MAP (Output A), row-major from NW.

    Unlike grid_centers (a loose Week-2 pilot grid), spacing == the tile's true
    GROUND coverage so adjacent tiles abut. For an orthographic camera at
    elevation θ, a tile of `footprint_m` view-height covers:
      • footprint_m wide  along the screen-horizontal axis
      • footprint_m / sin θ deep along the screen-vertical axis (foreshortened)
    With azimuth 0 the screen axes align with E (lon) / N (lat), so:
      dLon = footprint_m / (111320·cos lat) ,  dLat = (footprint_m/sin θ)/111320
    (Tall buildings still overhang a tile's top edge — that seam is what the
    empirical montage test measures; if bad, an overlap-blend pass is needed.)
    """
    import math
    if abs(azimuth_deg) > 1e-6:
        print(f"   ⚠️  map_grid assumes azimuth 0 for axis-aligned tiling "
              f"(got {azimuth_deg}); seams will skew.")
    sin_el = math.sin(math.radians(abs(elevation_deg))) or 1.0
    depth_m = footprint_m / sin_el
    dlat = depth_m / 111320.0
    dlon = footprint_m / (111320.0 * math.cos(math.radians(center_lat)))
    lat0 = center_lat + (rows - 1) / 2.0 * dlat   # row 0 = north
    lon0 = center_lon - (cols - 1) / 2.0 * dlon   # col 0 = west
    for r in range(rows):
        for c in range(cols):
            yield f"r{r}_c{c}", lat0 - r * dlat, lon0 + c * dlon, footprint_m


def viewmap_tiles(center_lat, center_lon, cols, rows, view_height_m):
    """Seamless map tiles via the renderer's setViewOffset (THE seamless method).

    Every tile shares ONE ortho projection (center lat/lon = map centre,
    view_height = the FULL grid's view-plane height); each tile is a viewport
    window (tile_col,tile_row) into it. Tiles stitch perfectly and a tower
    straddling a boundary aligns across tiles — no spacing calibration, no blend.
    Yields 5-tuples: (label, lat, lon, view_height, extra_url_params).
    """
    for r in range(rows):
        for c in range(cols):
            yield (f"r{r}_c{c}", center_lat, center_lon, view_height_m,
                   {"tile_cols": cols, "tile_rows": rows, "tile_col": c, "tile_row": r})


def named_locations(locations_path: Path):
    """Yield (id, lat, lon, view_height_m) for each renderable named location.

    Skips entries flagged needs_infra (rural/marine landmarks that render
    sparse from the building layer — they need the infrastructure endpoint,
    deferred). See scripts/locations.json.
    """
    data = json.loads(locations_path.read_text())
    for loc in data.get("locations", []):
        if loc.get("needs_infra"):
            continue
        yield (loc["id"], float(loc["lat"]), float(loc["lon"]),
               float(loc.get("view_height_m", VIEW_HEIGHT_M)))


SERVER_LOG = Path("/tmp") / f"hk-vite-{PORT}.log"


def start_server() -> subprocess.Popen:
    # `bun --bun` runs vite on bun's runtime, not Node. Required because the
    # active node here is 18.x and Vite 7 needs Node 20+ (crypto.hash). Bun is
    # Node-compatible and has the API, so this sidesteps the version wall.
    #
    # Stream vite's output to a LOG FILE (not PIPE): reading a PIPE from a
    # still-running child blocks forever, which caused an earlier hang. A log
    # file is always safe to read and lets us detect readiness from vite's
    # own "ready" banner rather than racing a socket poll.
    log_fh = open(SERVER_LOG, "w")
    proc = subprocess.Popen(
        ["bun", "--bun", "run", "dev", "--port", str(PORT)],
        cwd=WEB_RENDER_DIR,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
    )
    print(f"🌐 starting vite on :{PORT} …")
    deadline = time.time() + 40.0
    while time.time() < deadline:
        if proc.poll() is not None:  # vite exited = startup error
            raise RuntimeError(
                f"vite exited (code {proc.returncode}) during startup:\n"
                f"{SERVER_LOG.read_text()[:800]}"
            )
        log = SERVER_LOG.read_text() if SERVER_LOG.exists() else ""
        if "ready in" in log or f":{PORT}" in log:
            time.sleep(1.0)  # grace after the ready banner
            print(f"   ✅ vite up on http://localhost:{PORT}")
            return proc
        time.sleep(0.5)
    proc.terminate()
    raise RuntimeError(
        f"vite did not become ready in 40s:\n{SERVER_LOG.read_text()[:800]}"
    )


def render_tile(browser, tile, args, az, el, out_dir) -> bool:
    """Render one tile in a fresh context. Returns True if it FAILED (whitebox/
    init failure). Shared by the sequential and concurrent paths so the proven
    per-tile logic lives in exactly one place."""
    label, lat, lon, view_h = tile[:4]
    extra = tile[4] if len(tile) > 4 else {}
    params = {
        "export": "true", "lat": lat, "lon": lon,
        "width": WIDTH, "height": HEIGHT,
        "azimuth": az, "elevation": el, "view_height": view_h,
    }
    params.update(extra)  # e.g. setViewOffset tile_col/row/cols/rows
    if args.style == "soft":
        params["style"] = "soft"
        if args.pixel is not None:
            params["pixel"] = args.pixel
        if args.palette is not None:
            params["palette"] = args.palette
        if args.night:
            params["night"] = "true"
        if args.vector:
            params["vector"] = "true"
    if args.transparent:
        params["transparent"] = "true"
    q = urlencode(params)
    # Per-tile texture-failure tracker (Rule: fail loud, never silently save a
    # whitebox). With the transcoder hosted locally these are normally empty.
    tex_errors: list[str] = []
    # EVERYTHING below is wrapped so a browser crash / FD exhaustion / nav error
    # is CONTAINED as a failed tile (returns True) and the context/page are ALWAYS
    # closed — otherwise, in concurrent mode, one bad tile would crash the worker
    # thread (losing its remaining chunk) and leak the page/context.
    ctx = page = None
    failed = False
    try:
        ctx = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1,
        )
        page = ctx.new_page()

        def _on_console(m, _bucket=tex_errors):
            if m.type in ("error", "warning"):
                print(f"   [browser:{m.type}] {m.text[:160]}")
            if "Couldn't load texture" in m.text or "KTX2" in m.text:
                _bucket.append(m.text[:120])

        page.on("console", _on_console)
        page.on("pageerror", lambda e: print(f"   [pageerror] {str(e)[:160]}"))
        url = f"http://localhost:{PORT}/?{q}"
        page.goto(url, wait_until="networkidle")
        try:
            page.wait_for_function("window.TILES_LOADED === true", timeout=args.tile_timeout)
            loaded = True
        except Exception:
            loaded = False
            print(f"   ⚠️  {label}: TILES_LOADED timeout, capturing anyway")
        # TILES_LOADED fires on geometry load; KTX2 textures transcode after, so
        # settle before screenshot or we capture untextured (whitebox) buildings.
        page.wait_for_timeout(args.settle_ms)
        # Gate on the TRUE signal — the live textured-mesh inventory, NOT the noisy
        # console (one transient "Couldn't load texture" is harmless when N/N meshes
        # end up textured). A real whitebox = a large untextured fraction or init fail.
        inv = page.evaluate("""() => {
          const out = {initFailed: !!window.KTX2_INIT_FAILED, total: 0, noMap: 0};
          const root = window.__scene;
          if (!root) { out.noScene = true; return out; }
          root.traverse(o => {
            if (!o.isMesh) return;
            out.total++;
            const mats = Array.isArray(o.material) ? o.material : [o.material];
            if (!mats.some(m => m && m.map)) out.noMap++;
          });
          return out;
        }""")
        out_path = out_dir / f"{label}.png"
        page.screenshot(path=str(out_path), omit_background=args.transparent)
        size = out_path.stat().st_size
        total = inv.get("total", 0)
        no_map = inv.get("noMap", 0)
        untex_frac = (no_map / total) if total else 1.0
        tex_note = f"{total - no_map}/{total} tex"
        if not loaded:
            status, icon = "timeout", "⚠️ "
        elif inv.get("initFailed") or untex_frac > 0.20:
            status, icon = f"TEXTURE-FAIL({tex_note})", "❌"
            failed = True
        else:
            status, icon = f"ok {tex_note}", "✅"
            if tex_errors:
                status += f" ({len(tex_errors)} transient)"
        print(f"   {icon} {label}.png "
              f"({lat:.4f},{lon:.4f}) vh={view_h:.0f} {size//1024}KB [{status}]")
    except Exception as e:
        failed = True
        print(f"   ❌ {label}.png — render error (contained): {str(e)[:160]}")
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass
    return failed


def render_all(tiles, args, az, el, out_dir, launch_args) -> tuple[int, int]:
    """Render every tile; returns (saved, failed). concurrency==1 is the proven
    sequential path; >1 runs N worker threads, each with its OWN browser sharing
    the one vite server (overlaps network/transcode/settle waits)."""
    conc = max(1, args.concurrency)
    if conc == 1:
        saved = failed = 0
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=launch_args)
            for tile in tiles:
                if render_tile(browser, tile, args, az, el, out_dir):
                    failed += 1
                saved += 1
            browser.close()
        return saved, failed

    # Concurrent: round-robin tiles into `conc` chunks, one browser per worker
    # thread (Playwright sync API is fine per-thread with its own instance).
    from concurrent.futures import ThreadPoolExecutor
    chunks = [tiles[i::conc] for i in range(conc)]

    def worker(chunk):
        if not chunk:
            return 0, 0
        s = f = 0
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=launch_args)
            for tile in chunk:
                if render_tile(browser, tile, args, az, el, out_dir):
                    f += 1
                s += 1
            browser.close()
        return s, f

    print(f"⚙️  rendering {len(tiles)} tiles with concurrency={conc}")
    saved = failed = 0
    with ThreadPoolExecutor(max_workers=conc) as ex:
        for s, f in ex.map(worker, chunks):
            saved += s
            failed += f
    return saved, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Bake HK isometric tiles (grid or named locations)")
    parser.add_argument("--limit", type=int, default=None, help="render only the first N tiles")
    parser.add_argument("--locations", type=Path, default=None,
                        help="render named locations from a JSON file (e.g. scripts/locations.json) "
                             "instead of the Central grid")
    parser.add_argument("--out-dir", type=str, default=None,
                        help="subdir name under scripts/out/ (default: 'central' for grid, "
                             "'locations' for --locations)")
    parser.add_argument("--disable-web-security", action="store_true",
                        help="add Chromium flag if data.map.gov.hk CORS blocks the browser fetch")
    parser.add_argument("--tile-timeout", type=int, default=60000, help="ms to wait for TILES_LOADED")
    parser.add_argument("--settle-ms", type=int, default=3500,
                        help="ms to wait after TILES_LOADED for KTX2 textures to transcode "
                             "before screenshot (avoids untextured whitebox capture)")
    parser.add_argument("--concurrency", type=int, default=1,
                        help="parallel render workers (each its own browser, shared vite "
                             "server). >1 overlaps the per-tile network/transcode/settle waits "
                             "for territory-scale throughput. Default 1 = sequential.")
    parser.add_argument("--azimuth", type=float, default=AZ,
                        help=f"camera azimuth deg (default {AZ})")
    parser.add_argument("--elevation", type=float, default=EL,
                        help=f"camera elevation deg; default {EL} = SC2000 dimetric 2:1 "
                             "(arctan 0.5, better for HK verticality). true-iso ≈ -35.264 "
                             "(comparison reference; flatter default shows more tower-face)")
    parser.add_argument("--style", choices=["raw", "soft"], default="soft",
                        help="soft (default) = deterministic soft-stylise post-process, the "
                             "shippable look, no AI; raw = unstyled render (the input the "
                             "optional AI restyle would consume)")
    parser.add_argument("--pixel", type=float, default=None,
                        help="soft only: mosaic block in screen px. Default 1 = soft-clean "
                             "diorama (the shipped 'Yok-Iso HK' look). >1 = OPTIONAL chunky "
                             "pixel variant (e.g. --pixel 6); not the default style.")
    parser.add_argument("--palette", type=float, default=None,
                        help="soft only: 0..1 snap strength to the 15-colour Yok palette "
                             "(default 0.85; 1.0 = hard hex-lock)")
    parser.add_argument("--night", action="store_true",
                        help="soft only: day↔night re-light — deep-harbour dusk city with "
                             "ignited neon accents (same geometry, never a new composition)")
    parser.add_argument("--vector", action="store_true",
                        help="soft only: stylized-vector-illustration preset — flatter cel "
                             "fills, hard palette flats, bold clean outline, no grain")
    parser.add_argument("--transparent", action="store_true",
                        help="no sky fill; bake transparent PNGs (game-ready PROP SPRITES). "
                             "Pair with a tight view_height per location to isolate a landmark.")
    parser.add_argument("--map", type=str, default=None,
                        help="[superseded by --viewmap] move-camera grid: "
                             "'lat,lon,cols,rows,footprint_m'. Leaves seams; kept for reference.")
    parser.add_argument("--viewmap", type=str, default=None,
                        help="SEAMLESS deep-zoom map via setViewOffset: 'lat,lon,cols,rows,"
                             "view_height_m' — one shared ortho projection, each tile a viewport "
                             "window. Perfectly stitchable (scripts/stitch_grid.py). Tiles "
                             "r{row}_c{col}. view_height_m = the WHOLE grid's view-plane height.")
    args = parser.parse_args()
    az, el = args.azimuth, args.elevation

    # Choose tile source: seamless viewmap, (legacy) move-camera map, named, pilot.
    if args.viewmap:
        clat, clon, cols, rows, vh = args.viewmap.split(",")
        tiles = list(viewmap_tiles(float(clat), float(clon), int(cols), int(rows), float(vh)))
        out_dir = REPO / "scripts" / "out" / (args.out_dir or "viewmap")
        print(f"🧩 seamless viewmap: {cols}×{rows} via setViewOffset, "
              f"center ({clat},{clon}), full view_height={vh}m, el={el} az={az}")
    elif args.map:
        clat, clon, cols, rows, fp = args.map.split(",")
        tiles = list(map_grid(float(clat), float(clon), int(cols), int(rows),
                              float(fp), el, az))
        out_dir = REPO / "scripts" / "out" / (args.out_dir or "map")
        print(f"🗺️  map grid: {cols}×{rows} @ {fp}m footprint, "
              f"center ({clat},{clon}), el={el} az={az}")
    elif args.locations:
        tiles = list(named_locations(args.locations))
        out_dir = REPO / "scripts" / "out" / (args.out_dir or "locations")
    else:
        tiles = list(grid_centers())
        out_dir = REPO / "scripts" / "out" / (args.out_dir or "central")
    if args.limit:
        tiles = tiles[: args.limit]
    out_dir.mkdir(parents=True, exist_ok=True)

    # --disk-cache-size caps Chromium's HTTP cache so fetched b3dm tiles don't
    # accumulate to GBs across a large bake (the ENOSPC cause at territory scale).
    launch_args = ["--enable-webgl", "--use-gl=angle", "--ignore-gpu-blocklist",
                   "--disk-cache-size=1", "--media-cache-size=1"]
    if args.disable_web_security:
        launch_args += ["--disable-web-security", f"--user-data-dir=/tmp/hk-bake-{PORT}"]

    server = start_server()
    saved, failed = 0, 0
    try:
        saved, failed = render_all(tiles, args, az, el, out_dir, launch_args)
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()

    print(f"\n=== baked {saved} tile(s) → {out_dir} (failed={failed}) ===")
    return 0 if saved else 1


if __name__ == "__main__":
    raise SystemExit(main())

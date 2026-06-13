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
    parser.add_argument("--azimuth", type=float, default=AZ,
                        help=f"camera azimuth deg (default {AZ})")
    parser.add_argument("--elevation", type=float, default=EL,
                        help=f"camera elevation deg; true-iso={EL}, SC2000 dimetric=-26.565 "
                             "(flatter = more tower-face, better for HK verticality)")
    args = parser.parse_args()
    az, el = args.azimuth, args.elevation

    # Choose tile source: named locations or the uniform Central grid.
    if args.locations:
        tiles = list(named_locations(args.locations))
        out_dir = REPO / "scripts" / "out" / (args.out_dir or "locations")
    else:
        tiles = list(grid_centers())
        out_dir = REPO / "scripts" / "out" / (args.out_dir or "central")
    if args.limit:
        tiles = tiles[: args.limit]
    out_dir.mkdir(parents=True, exist_ok=True)

    launch_args = ["--enable-webgl", "--use-gl=angle", "--ignore-gpu-blocklist"]
    if args.disable_web_security:
        launch_args += ["--disable-web-security", f"--user-data-dir=/tmp/hk-bake-{PORT}"]

    server = start_server()
    saved, failed = 0, 0
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=launch_args)
            for label, lat, lon, view_h in tiles:
                q = urlencode({
                    "export": "true", "lat": lat, "lon": lon,
                    "width": WIDTH, "height": HEIGHT,
                    "azimuth": az, "elevation": el, "view_height": view_h,
                })
                ctx = browser.new_context(
                    viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1,
                )
                page = ctx.new_page()
                # Capture browser console + errors — catches CORS / WebGL failures
                # (the blueprint's top risks). Only print warnings/errors to stay quiet.
                page.on("console", lambda m: (
                    print(f"   [browser:{m.type}] {m.text[:160]}")
                    if m.type in ("error", "warning") else None))
                page.on("pageerror", lambda e: print(f"   [pageerror] {str(e)[:160]}"))
                url = f"http://localhost:{PORT}/?{q}"
                page.goto(url, wait_until="networkidle")
                try:
                    page.wait_for_function("window.TILES_LOADED === true", timeout=args.tile_timeout)
                    loaded = True
                except Exception:
                    loaded = False
                    print(f"   ⚠️  {label}: TILES_LOADED timeout, capturing anyway")
                out_path = out_dir / f"{label}.png"
                page.screenshot(path=str(out_path))
                size = out_path.stat().st_size
                status = "ok" if loaded else "timeout"
                print(f"   {'✅' if loaded else '⚠️ '} {label}.png "
                      f"({lat:.4f},{lon:.4f}) vh={view_h:.0f} {size//1024}KB [{status}]")
                saved += 1
                page.close()
                ctx.close()
            browser.close()
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

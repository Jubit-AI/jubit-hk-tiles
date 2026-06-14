# game-demo — jubuddy-HK isometric TD board (proof)

A self-contained, dependency-free isometric Tower-Defense board that proves the
**jubuddy-HK renderer path** with the *real* Yok-Iso assets — before scaffolding
the full jubuddy-hk repo. It composes the two asset layers (aesthetic-spec §7):

- **ground tiles** — `game-tiles/iso/iso-*.png` (the `TileKind` diamonds)
- **identity prop** — `game-tiles/props/prop-mongkok-block.png` (HK landmark sprite)

…into a live board: enemies walk `spawn → goal` along the `path` lane, towers on
`slot` pads auto-fire, click a slot to place a tower. Pure `<canvas>` + vanilla
JS, no build.

**Output G — curated district boards.** The boards load from
`game-tiles/boards/districts.json` (Central CBD grid · Mong Kok neon maze ·
Kowloon canyon corridor) — each a `MapData`-shaped `{cols,rows,path,slots,blocked}`
def from which the renderer derives the `TileKind` grid. A picker switches
districts live; `?board=<id>` deep-links one.

## Run
Serve from the **repo root** (the demo references `/game-tiles/...` absolutely):
```bash
cd ~/jubit-hk-tiles && python3 -m http.server 8901
# → http://localhost:8901/game-demo/index.html
```

## What it demonstrates (Output G pilot, plan Week 13–14)
- **Iso renderer**: `screen = (OX + (c−r)·HW, OY + (c+r)·HH)`; ground tiles drawn
  row-major (iso depth order); dynamic actors depth-sorted by screen-y.
- **Board = a `MapData`-style `TileKind` grid + a `path`** (the same shape
  jubuddy-game's `buddy-core` simulator already consumes — so the real TD sim can
  drop in later instead of this demo's toy loop).
- **Props on clean ground**: the HK landmark sprite sits on the board without the
  ground tiles carrying photoreal HK detail — keeps the ground reusable.
- **Yok-Iso throughout**: parchment lanes, gold slot rings, ink towers with
  teal/gold accents, cinnabar enemies — the city tiles and the game read as one.

## Not included (deliberately)
The real game = the **jubuddy-hk repo** (scaffolded from jubuddy-game): inherits
`buddy-core` (TD sim, `MapData`, waves, economy) and replaces this file's toy loop
with that simulator behind the same isometric renderer. This demo de-risks that
renderer; the toy `update()` here is a placeholder for `buddy-core`.

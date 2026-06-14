# Game tiles — jubuddy-HK asset set (Phase 2)

The two-layer asset model from the plan (aesthetic-spec §7). jubit-hk-tiles is the
asset **producer**; the jubuddy-HK game (a later spin-off from jubuddy-game) is the
**consumer**. Both layers are the locked **Yok-Iso HK** style (`yok_iso_hk_soft_pictorial`).

## Layers

| Layer | Dir | Source | Role |
|---|---|---|---|
| **Ground / gameplay** | `iso/` | `scripts/make_ground_tiles.py` (deterministic) | clean, reusable, instantly readable board tiles — gameplay legibility always wins |
| **Identity props** | (bake) | `central_render_bake.py --transparent` → hand-clean | HK landmarks as transparent sprites, dropped onto the ground |

The ground layer is **hand-authored / deterministic** — NOT from the city AI/bake
pipeline (which is worst at repeated game tiles). HK-ness comes from props on clean
ground, so the ground stays reusable across boards.

## Ground tileset (`iso/`)

Isometric 2:1 diamonds for the jubuddy-game `TileKind` vocabulary
(`packages/buddy-core/src/maps/types.ts`): `empty · path · slot · blocked · spawn · goal`.
PNGs + a `tiles.json` manifest matching the jubuddy-game stage-tile shape
(`{name,w,h}`), so jubuddy-HK consumes them like any other stage-tile kit.

| TileKind | Read |
|---|---|
| `empty` | calm concrete ground (buildable-adjacent) |
| `path` | bright parchment lane (the enemy route) |
| `slot` | concrete + antique-gold ring (tower pad — place here) |
| `blocked` | ink-dark stone (impassable) |
| `spawn` | parchment + cinnabar inbound chevron (enemy entry) |
| `goal` | parchment + teal/jade gate marker (the objective) |

Regenerate: `uv run python scripts/make_ground_tiles.py --out game-tiles/iso`

## How jubuddy-HK uses these (later)
- `MapData.tiles[][]` (a `TileKind` grid) selects which diamond to draw per cell.
- The new isometric renderer places tiles at `screen = ((col-row)·W/2, (col+row)·H/2)`
  and composites HK prop sprites on top of `slot`/decorative cells.
- Creature/character cards stay on the existing character pipeline (most saturated
  in frame); pink is reserved for them, never fielded on these tiles.

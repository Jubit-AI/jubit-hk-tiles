# Aesthetic Spec — "Yok-Iso HK: soft isometric parchment city"

**Style name (LOCKED 2026-06-14):** **Yok-Iso HK: soft isometric parchment city**. Manifest key: **`yok_iso_hk_soft_pictorial`**. (Supersedes the working title "Soft-Stylised Dimetric HK".)

**LOCKED** (refined 2026-06-14; built 2026-06-13 from the styling-DNA workflow that extracted jubuddy-game Codex + Pictorial Book + GPT-image DNA). Canonical target for: (a) the fine-tune training-set "after" images (`inference/training-set/`), and (b) the deterministic render camera/lighting (`src/web_render/`). Hex values are exact.

**One-line lock:** *a warm 2.5D **soft isometric** Hong Kong seen at dimetric 2:1 / 26.57°, readable like a board game — **polished mobile-game diorama art, NOT crunchy retro pixel-art**: pixel-CLEAN edges and restrained pixel-sharp outlines, flat cel fills on visible rice-paper grain, three faces (top·left·right, front never shown), under a 70% parchment / 20% ink / 6% HK teal-neon / 3% cinnabar / 1% antique-gold budget (neon as an accent, never the mood — harbour mist, lantern glow, wet stone, market colour, vertical-city silhouettes, not cyberpunk), day-primary with a day↔night re-light axis — harmonized with the plush Pictorial-Book folklore characters by shared paper, shared light, shared warmth, and a strict saturation hierarchy where the character is always the brightest thing in frame.*

**Why soft, not strict pixel-art:** strict pixel art is beautiful but makes AI/render consistency much harder — repeated tiles expose every mismatch. The production choice for Jubuddy is **soft isometric + hand-cleaned sprite cells + restrained pixel-sharp outlines**, which matches the existing anime/Jubuddy assets better than crunchy retro pixel. (The deterministic shader keeps an optional `uPixelSize > 1` mosaic for a pixel variant, but the **shipped default is soft-clean** — `uPixelSize 1`.)

This welds the city tiles to the Codex character line: both paint from the same swatches, same paper grain, same light, same single soft-graffiti contour rule. Built on `jubuddy-game` `prompt-themes/yok.ts` (palette/texture), `arcane.ts` (environment/lighting), `buddy-core/tokens` (mascot/brand), and the production-asset taste rubric (read-first / chunky-silhouette / quiet-center).

## 0. The locked LoRA contract

| Constant | Value | Where |
|---|---|---|
| **Trigger token** | `<jubit hk soft iso>` | `inference/train.py` `HK_TRIGGER_TOKEN`; generation prompts must emit it verbatim once trained (checklist #11-14) |
| **LoRA model id** | `jubit-hk-soft-iso` | `train.py` `HK_LORA_MODEL_ID`; served via `server.py` `LORA_MODEL_ID` |
| **Modal volume** | `hk-tiles-lora-vol` | LoRA saved to `/data/loras/jubit-hk-soft-iso/`; `server.py` loads from the same volume (checklist #6) |
| **Base model** | `Qwen/Qwen-Image-Edit` | unchanged from upstream |

**LOCKED 2026-06-13.** The token is a one-line contract the LoRA + every generation prompt must agree on — changing it means retraining. `inference/train.py` is the fine-tune entrypoint (was missing); it trains the 40-pair set (§5) to respond to this token and saves to the volume `server.py` reads.

## 1. Palette — 70 parchment / 20 ink / 6 harbour-teal / 3 cinnabar / 1 gold

**PALETTE ANCHOR (LOCKED 2026-06-14) — the canonical 8.** Every surface (shader snap, ground tiles, cards, tram, UI backgrounds) keys off these:

| Role | Hex |
|---|---|
| Rice paper (substrate / lightest face) | `#F3E7CF` |
| Parchment (mid base / second tone) | `#D9C59C` |
| Ink (contour + deepest creases) | `#1A1A17` |
| Deep harbour (water shadow / night water) | `#0D3D46` |
| Harbour teal (water + the restrained brand accent) | `#1F6F73` |
| Tram jade (Star Ferry / goal / jade accents) | `#2E8C7D` |
| Cinnabar (tram/ding-ding, lantern, one sign) | `#B64734` |
| Antique gold (divider/trim/highlight — never chrome) | `#C7A25B` |

*Functional concrete ramp (derived, not anchor): warm mids `~#A38F61` / `~#5E5238` between parchment and ink, so the city massing has a smooth ramp.* The shader (`softStylise.js`) snaps to these; the 4 saturated accents (deep-harbour / harbour-teal / tram-jade / cinnabar) are chroma-gated so grey concrete never mis-snaps to them.

**Locked HK visual formula:** **70% warm parchment + 20% ink structure + 6% harbour-teal + 3% cinnabar + 1% antique gold.** Teal is an accent, never the whole mood (harbour mist, lantern glow — not cyberpunk). Pink is **reserved for the characters/creatures**, never fielded on city tiles. (Earlier cooler palette — rice `#F6F1E8`, concrete `#C9C2B6/#A89F90/#8A8378`, brand teal `#14B8A6`, jade `#7C9C8E` — superseded by the warmer, harbour-forward anchor above.)

**Note:** building-only renders rarely trigger the harbour/teal/jade accents (raw water renders sky-pale → snaps to rice paper); those colours live in the **game tiles** (goal/spawn markers, water), the **tram**, and a future water-treatment pass.

**Material/support colours (not budget accents):** jade `#7C9C8E` (Star Ferry/piers), water-jade `#A8B8A3` (harbour).

**Sky/water:** day sky warm wash `#EFE7D8`→`#E3D6BE` (25–40% negative space, no hard gradient); harbour water jade-grey `#A8B8A3` + ink ripples `#1F1A17` @12%, gold reflection `#C7A25B` only at the waterline.

**HK neon (reserve):** day = dormant desaturated sign shapes (−60% sat); night = ignited — hot pink-orange `#FF5E7A`, electric yellow `#FFE600`, sky-cyan `#00E5FF`, magenta `#FF0080`, shimmer green `#3FFF7A` (rare). Night is a **re-light of the same tile**, never a new composition. (Shimmer green `#3FFF7A` is the exact Codex `arcane.ts ZAUN_PALETTE[0]` — the night/neon family is inherited from Codex's Zaun palette.)

**Codex-token fidelity (verified 2026-06-14).** The accent + structure swatches are hex-locked to the *real* tokens the Codex agent authored in `jubuddy-game`, not approximations: teal `#14B8A6` / pink `#EC4899` / gold `#C7A25B` = `packages/prompt-themes/src/themes/yok.ts` jubit family; cream `#F0E2C9` / copper `#C8A36A` = `arcane.ts PILTOVER_PALETTE`; jade `#7C9C8E` / water-jade `#A8B8A3` = `apps/web …/yok.ts` swatches; cinnabar `#B64734` = Yok `traditional` family. The rice-paper `#F6F1E8` substrate is the exact mascot/character paper, so HK tiles and the jubuddy character line literally share one sheet. The **concrete ramp** (`#C9C2B6`/`#A89F90`/`#8A8378`), **off-white** `#EFE7D8`, and **sky** `#E3D6BE` are deliberate HK-original extensions (no Codex equivalent — HK needs a concrete-massing base the character palette doesn't carry).

## 2. Texture / edge — the soft-stylised lock

| Quality | DO | BANNED |
|---|---|---|
| Edge | soft anti-aliased lip (grid-sliceable but not jaggy) | crisp 1px pixel, dither, "pixel sprite" |
| Outline | ONE soft-graffiti ink `#1F1A17` contour per major form; rest clean cel-flats | heavy outline on every shape; zero-outline vector |
| Faces | flat cel fills, gentle internal gradient only | photoreal gradient, gloss, chrome |
| Substrate | rice-paper grain visible across whole tile, subtle | clean digital flat; competing paper noise |
| Metal | matte antique gold, brushed | chrome/mirror |
| Shadow | soft, low-contrast | heavy drop/cast shadows |
| Colors | ~24–40 working (SC2K discipline, soft execution) | unbounded photographic |

Surface verdict: **"flat illustration with a soft brush, painted on rice paper"** — Arcane's painted-texture-over-2.5D through Yok's flat low-contrast discipline.

## 3. Lighting — `src/web_render` (applied)

**Day (primary) — current defaults in `main.js`:**
- DirectionalLight: intensity **1.9**, color **`#FFEAC4`** (warm key), upper-left (matches camera azimuth)
- HemisphereLight: intensity **1.35**, sky **`#F0E2C9`**, ground **`#A89F90`**
- *Follow-up*: soft **ambient occlusion** (0.55–0.7, small radius) in creases/canyon-gaps only — needs an EffectComposer SAO/SSAO pass; deferred to keep the deterministic bake simple. Governing rule: **soft in the gaps, flat on the faces.**

**Night/neon (controllable 2nd axis, not yet wired):** key 0.6 cool `#4A5568`; ambient 0.5 `#2A2F3A`/`#1F2937`; emissive layer ignites Jubit teal/pink + HK neon; AO ~0.8. Same geometry + camera — a re-light only.

## 4. Camera — SC2000 dimetric (applied)

**elevation −26.565° (arctan 0.5, dimetric 2:1), azimuth −15° (constant for tileability), orthographic.** Chosen by visual A/B on dense Mong Kok AND independently by this workflow. Beats true-iso 35.264° for HK because the lower angle shows more tower **face** (where HK identity lives — windows/balconies/AC/light-bleed), occludes less in dense clusters, locks the SC2K nostalgia signal, and gives clean 2:1 grid-slicing. (Spec's ideal azimuth is 45° for exactly-3-faces; we use −15° matching the upstream renderer's convention — revisit if the 3-face read needs it.) **Same angle on every training image — mixed angles poison the LoRA.**

## 4b. Deterministic shader path (IMPLEMENTED — "shaders now, AI later")

The soft-stylised look is reached **deterministically, no AI/Modal**, via a Three.js post-process — because HK's textured `b3dm` input already carries real building texture (the reason isometric-nyc needed AI doesn't apply as hard here). This is the **shippable baseline**; the LoRA (`inference/train.py`) is optional A/B polish later.

- `src/web_render/softStylise.js` — `EffectComposer` chain: (optional mosaic, off by default) → cel posterize (lifted into the warm-concrete range, **no black crush**) → warm grade → restrained pixel-sharp contour (luminance-step Sobel) → subtle rice-paper grain (fixed ~2px paper cell) → **snap to the 15-colour Yok palette** (§1, hard hex-lock).
- **Soft-clean default (the "Yok-Iso HK" lock).** `uPixelSize` defaults to **1** = clean native edges, NOT a crunchy mosaic. The look = polished mobile-game diorama: flat cel fills + limited palette + crisp restrained outlines + subtle parchment grain. `uPixelSize > 1` (e.g. `--pixel 6`) is an **optional** chunky pixel variant, not the shipped style.
- **Yok palette snap.** Every pixel snaps to the nearest of the §1 swatches (rice-paper / off-white / concrete lt·md·sh / ink / cream / copper / antique-gold / sky / water / jade / **Jubit teal** / **Jubit pink** / cinnabar). The three high-chroma brand accents are **chroma-gated** — a grey concrete pixel can't mis-snap to teal/pink; only genuinely-colourful pixels reach them — so the brand colours appear *as accents* (the 6% intent), not as a field, with no AI. Strength = `uPaletteMix` (default 0.85; 1.0 = full hex-lock).
- Enabled by `style=soft` URL param; **`scripts/central_render_bake.py --style soft` is the default** (soft-clean), with optional `--pixel N` / `--palette 0..1` overrides (and `--settle-ms` for KTX2 transcode). `--style raw` emits the unstyled render = the input the optional AI restyle would consume.
- Tuned on dense Mong Kok (soft-clean): shadow floor 0.30 (deep concrete, not black), restrained pixel-sharp contour 0.32 on a fixed 1.5px tap, paper grain on a fixed 2px cell, `uPixelSize 1`. Reads as **soft isometric parchment-city diorama** — clean edges + form-defining ink outline, harmonised with the jubuddy-game Yok character line by shared palette + paper + light.
- **Still deterministic** (grain keyed off screen position, not time) → identical re-renders, required for tileability.
- Remaining gaps (candidates for the optional AI pass): semantic accent *placement* (a shader can't know which sign is the hero), the day↔night neon re-light axis, in-crease AO. The soft Yok-Iso baseline is achieved with zero AI.

## 5. The 40-pair training rubric (grades every "after" image)

1. **Projection** — dimetric 2:1, identical angle every image, 3 faces, front never shown.
2. **Base palette (70%)** — warm concrete `#C9C2B6`→`#8A8378`, rice-paper, jade water; no SC2K brown, no photoreal grey-blue; 24–40 colors.
3. **Structure/accent/punctuation (20/8/2)** — copper/cream/gold; Jubit teal+pink hero accents 5–10%; ≤2 punctuation; neon dormant in day. Budget is graded.
4. **Edge/texture** — soft AA lip + one soft-graffiti contour; flat cel fills; rice-paper grain; matte. Not pixel, not clean-3D.
5. **Lighting** — fixed upper-left warm key, 3-tone faces, soft AO in creases. Matches character cel-shadow logic.
6. **Density legibility** — tower-face emphasis, varied silhouettes per cluster (no two adjacent identical), dark canyon gaps, one focal motif. Parse per-building @100%, per-cluster @25%.
7. **Day↔night axis** — day-primary; night = same geometry re-lit, neon ignited.

**Harmonization gate (vs the character line):** shared paper grain; shared single soft-graffiti accent contour; shared palette family per scene; same cel-shade + light direction + warmth; gold reserved for the same role; **strict saturation hierarchy — the placed character is ALWAYS the most saturated thing in frame.**

**40-image composition:** all six tile families × {day, night, a few seam/edge}, deliberate silhouette spread. Text-free, logo-free, original stylized HK forms, grid-sliceable.

## 6. HK stage motifs → per-tile treatment

Each tile = one dominant read; all obey 70/20/6/3/1 + 25–40% negative space + rice-paper grain + single soft-graffiti contour; must read at 64px.

| Family | Focal | Treatment |
|---|---|---|
| **Harbour** | water plane + one pier | ivory water + ink ripples; junk/skyline as distant edge motif; gold reflection at waterline only; big negative space |
| **Neon canyon** | the value-contrast canyon | deep dark gaps + bright lit upper faces; neon = single soft-graffiti glow line (teal/pink), NOT a flood; depth via value; day = dormant |
| **Skybridge** | calm horizontal deck | chunky read-first silhouette; copper railings; deck kept to canvas edges |
| **Tram/ferry** | the single charming vehicle | soft plush vehicle-keepsake; ding-ding cinnabar `#B64734`, Star Ferry jade `#7C9C8E`; strong 3/4 silhouette + wake/track sweep |
| **Island pier** | stilts + gangway + lantern string | wood/earth textures (tea-brown `#8D6B4D`, kraft grain); paper-lantern string as warm punctuation |
| **Transit concourse** | repeating column/turnstile rhythm | metal vocabulary softened to designer-toy matte; quiet center, readable lane |

## 7. Layer split (LOCKED 2026-06-14) — what comes from where

The HK Jubuddy theme is built in four separable layers, each with its own production source. Mixing them is what makes the theme cohere without the pipeline fighting gameplay readability.

| Layer | What | Source | Rule |
|---|---|---|---|
| **Ground tiles** | path · tower pads · blocked · spawn · goal | **hand-authored** (NOT the bake/AI pipeline) | clean, reusable, instantly readable; no photoreal HK detail. Gameplay legibility always wins. |
| **Identity props** | HK-flavoured one-off sprites | hybrid: `--transparent` bake → hand-clean | dropped onto the clean ground; carry the HK-ness so the ground stays reusable |
| **Backdrops** | painterly isometric stage cards | full-scene styled bake (hero tiles) | location-card / world-map art; the calm parchment stage |
| **Characters / creatures** | Pictorial-Book folklore fused with HK roles | existing character pipeline (Paper Doll / roster) | always the most saturated thing in frame; pink lives here, not on tiles |

**HK identity prop vocabulary:** ferry · pier lamps · tong-lau blocks · market awnings · footbridges · tram-like carriage · station entrances · harbour railings. (Each a single soft-iso sprite on transparency.)

**HK creature roster (Pictorial-Book × HK roles):** ferry piglet · neon yokai imp · paper-air spirit · gate mimic · flower-spirit crab · cloud dragonling. (Stay on the character pipeline; the city is their stage, never rendered by the city pipeline.)

## Deferred follow-ups
- ✅ **Seamless map — SOLVED** (Output A): the move-the-camera `map_grid` left gaps; replaced by `--viewmap` = ONE shared ortho projection sub-tiled via `camera.setViewOffset()`. Every tile is a viewport window into the same projection, so tiles stitch perfectly AND a tower straddling a boundary aligns across tiles (no gaps, no spacing calibration, no overlap-blend — the isometric-nyc "hard 90%" dissolved by construction). Proven on a 3×3 raw Central stitch. Remaining for the map: (a) per-tile soft-stylise contour can leave faint seam lines → style the *stitched* image (or render raw → stitch → style → DZI); (b) the DZI/OpenSeaDragon deep-zoom viewer; (c) LOD tuning at territory scale.
- AO pass (EffectComposer SAO/SSAO) for the in-crease shadow.
- Night/neon emissive axis in the renderer (the 6% teal-neon day↔night ignite).
- 45° azimuth experiment (exactly-3-faces) vs the current −15°.
